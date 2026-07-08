"""UI 無關的操作層：登入後的每個「動作」在這裡，回傳結構化結果（dataclass/dict），
**不 print、不讀 argv**。CLI（Tyro）、MCP server、未來 TUI 都呼叫這一層。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cloudapi import api, collect, fetch_devices, keys_have_code
from .lan import arp_ip_for
from .miot import AC_MODES, miot_ok

# ---------------------------------------------------------------- extract / tokens


def extract_tokens(conn, regions: list[str]) -> list[dict]:
    """QR 登入後：抓所有裝置的 token/ip/mac/beaconkey（dict 列表，跨區去重）。"""
    return collect(conn, regions)


# ---------------------------------------------------------------- verify (LAN)


@dataclass
class VerifyResult:
    ok: bool
    ip: str
    message: str
    model: str = ""
    firmware: str = ""


def verify_device(dev: dict) -> VerifyResult:
    """對單一裝置做 LAN 本地驗證（python-miio）。ARP 解即時 IP。"""
    model = dev.get("model", "")
    token = dev.get("token")
    if not token:
        return VerifyResult(False, "", "沒有 token（IR 虛擬遙控/雲端裝置），無法本地驗證", model)
    ip = dev.get("localip") or ""
    live = arp_ip_for(dev.get("mac", ""))
    if live:
        ip = live
    if not ip:
        return VerifyResult(False, "", "沒有可用 IP（多半不在你目前的 LAN）", model)
    try:
        from miio import Device
    except ModuleNotFoundError as e:
        raise SystemExit(
            "[mihome-ctl] verify 需要 python-miio：pip install 'mihome-ctl[verify]'"
        ) from e
    try:
        info = Device(ip, token).info()
        return VerifyResult(True, ip, "本地可控", info.model, info.firmware_version)
    except Exception as e:  # noqa: BLE001 - 回報任何本地失敗
        return VerifyResult(False, ip, f"{type(e).__name__}: {e}", model)


# ---------------------------------------------------------------- IR: enumerate


@dataclass
class RemoteRow:
    did: str
    model: str
    name: str
    region: str
    parent_id: str
    parent_model: str
    parent_name: str
    keys: int
    kind: str
    controller_id: int
    brand_id: Any


def enumerate_ir(conn, regions: list[str]) -> tuple[dict, list[RemoteRow]]:
    """列出雲端 miir.* 遙控 + parent blaster + DIY/品牌配對。回傳 (dump, rows)。"""
    devmap = fetch_devices(conn, regions)
    miirs = {did: v for did, v in devmap.items() if v["model"].startswith("miir")}
    dump: dict[str, dict] = {}
    rows: list[RemoteRow] = []
    for did, v in miirs.items():
        country = v["region"]
        parent = devmap.get(v["parent_id"], {})
        keys_resp = api(conn, country, "/v2/irdevice/controller/keys", {"did": did})
        info_resp = api(conn, country, "/v2/irdevice/controller/info", {"did": did})
        nkeys, _ = keys_have_code(keys_resp)
        info_res = (info_resp or {}).get("result") or {}
        try:
            cid = int(info_res.get("controller_id") or 0)
        except (TypeError, ValueError):
            cid = 0
        brand = info_res.get("brand_id")
        if cid > 0:
            kind = "品牌配對"
        elif info_res.get("controller_id") is not None:
            kind = "DIY(自學)"
        else:
            kind = "未知"
        dump[did] = {
            "model": v["model"],
            "name": v["name"],
            "region": country,
            "parent_id": v["parent_id"],
            "parent_model": parent.get("model", "?"),
            "parent_name": parent.get("name", ""),
            "keys": nkeys,
            "kind": kind,
            "controller_id": cid,
            "brand_id": brand,
            "raw_keys": keys_resp,
            "raw_info": info_resp,
        }
        rows.append(
            RemoteRow(
                did,
                v["model"],
                v["name"],
                country,
                v["parent_id"],
                parent.get("model", "?"),
                parent.get("name", ""),
                nkeys,
                kind,
                cid,
                brand,
            )
        )
    return dump, rows


# ---------------------------------------------------------------- IR: send key


def find_remote(ir: dict, query: str) -> tuple[str, dict] | None:
    """以子字串（名稱/型號/did）在已存的 ir dump 裡找一個遙控。"""
    q = query.lower()
    for did, r in ir.items():
        if q in (str(r.get("name", "")) + r.get("model", "") + did).lower():
            return did, r
    return None


def remote_keys(r: dict) -> list[dict]:
    return ((r.get("raw_keys") or {}).get("result") or {}).get("keys") or []


def find_key(keys: list[dict], query: str) -> dict | None:
    qq = query.upper()
    return next(
        (
            x
            for x in keys
            if qq in (str(x.get("name", "")) + str(x.get("display_name", ""))).upper()
        ),
        None,
    )


@dataclass
class SendResult:
    ok: bool
    key_name: str
    display_name: str
    remote_name: str
    parent_model: str
    repeat: int
    resp: Any = None


def send_key(conn, did: str, r: dict, k: dict, repeat: int = 1) -> SendResult:
    """雲端觸發某遙控的某鍵（經 parent blaster 發射）；repeat 次。"""
    cid = int(r.get("controller_id") or 0)
    country = r.get("region", "cn")
    payload = {"did": did, "key_id": int(k["id"])}
    if cid:
        payload["controller_id"] = cid
    resp = api(conn, country, "/v2/irdevice/controller/key/click", payload)
    ok = isinstance(resp, dict) and resp.get("code") == 0
    if ok:
        for _ in range(max(0, repeat - 1)):
            api(conn, country, "/v2/irdevice/controller/key/click", payload)
    return SendResult(
        ok,
        k.get("name", ""),
        k.get("display_name", ""),
        r.get("name", ""),
        r.get("parent_model", ""),
        repeat,
        resp,
    )


# ---------------------------------------------------------------- IR: air-conditioner


def ac_remotes(ir: dict, query: str | None) -> list[tuple[str, dict]]:
    """挑冷氣遙控：有 query 用子字串；否則所有 miir.aircondition.*。"""
    if query:
        q = query.lower()
        return [
            (did, r)
            for did, r in ir.items()
            if q in (str(r.get("name", "")) + r.get("model", "") + did).lower()
        ]
    return [(did, r) for did, r in ir.items() if r["model"].startswith("miir.aircondition")]


@dataclass
class AcResult:
    ok: bool
    step: str
    resp: Any = None


def ac_status(conn, did: str, country: str) -> Any:
    info = api(conn, country, "/v2/irdevice/controller/info", {"did": did})
    return (info or {}).get("result", {}).get("ac_state")


def ac_off(conn, did: str, country: str) -> AcResult:
    resp = api(
        conn, country, "/miotspec/action", {"params": {"did": did, "siid": 2, "aiid": 5, "in": []}}
    )
    return AcResult(miot_ok(resp), "off", resp)


def ac_set_props(conn, did: str, country: str, temp: int | None, mode_val: int | None) -> AcResult:
    props = []
    if mode_val is not None:
        props.append({"did": did, "siid": 2, "piid": 1, "value": mode_val})
    if temp is not None:
        props.append({"did": did, "siid": 2, "piid": 2, "value": temp})
    if not props:
        return AcResult(True, "no-props")
    resp = api(conn, country, "/miotspec/prop/set", {"params": props})
    return AcResult(miot_ok(resp), "set-props", resp)


def ac_send_on(conn, did: str, country: str) -> AcResult:
    resp = api(
        conn, country, "/miotspec/action", {"params": {"did": did, "siid": 2, "aiid": 6, "in": []}}
    )
    return AcResult(miot_ok(resp), "send/on", resp)


def ac_control(
    conn,
    did: str,
    country: str,
    temp: int | None = None,
    mode: str | None = None,
    turn_on: bool = False,
    turn_off: bool = False,
) -> list[AcResult]:
    """一站式冷氣控制（MCP/TUI 用）：關機 / 設溫度模式 + 送出。回傳各步驟結果。"""
    if turn_off:
        return [ac_off(conn, did, country)]
    mode_val = AC_MODES.get(mode.lower()) if mode else None
    steps = [ac_set_props(conn, did, country, temp, mode_val)]
    steps.append(ac_send_on(conn, did, country))
    return steps
