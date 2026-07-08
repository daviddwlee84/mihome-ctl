"""UI-agnostic operations layer: every post-login "action" lives here and returns
structured results (dataclass/dict), **no print, no argv reads**. The CLI (Tyro),
MCP server, and future TUI all call into this layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cloudapi import api, collect, fetch_devices, keys_have_code
from .lan import arp_ip_for
from .miot import AC_MODES, miot_ok

# ---------------------------------------------------------------- extract / tokens


def extract_tokens(conn, regions: list[str]) -> list[dict]:
    """After QR login: fetch every device's token/ip/mac/beaconkey (list of dicts, deduped across regions)."""
    return collect(conn, regions)


# ---------------------------------------------------------------- verify (LAN)


@dataclass
class VerifyResult:
    ok: bool
    ip: str
    message: str
    model: str = ""
    firmware: str = ""


def _resolve_ip(dev: dict) -> str | None:
    """The device's current LAN IP: ARP-resolved (cloud localip is often stale), else localip."""
    return arp_ip_for(dev.get("mac", "")) or (dev.get("localip") or None)


def verify_device(dev: dict) -> VerifyResult:
    """Run LAN-local verification for a single device (python-miio). ARP resolves the current IP."""
    model = dev.get("model", "")
    token = dev.get("token")
    if not token:
        return VerifyResult(
            False, "", "no token (IR virtual remote / cloud device), cannot verify locally", model
        )
    ip = _resolve_ip(dev)
    if not ip:
        return VerifyResult(False, "", "no usable IP (most likely not on your current LAN)", model)
    try:
        from miio import Device
    except ModuleNotFoundError as e:
        raise SystemExit(
            "[mihome-ctl] verify requires python-miio: pip install 'mihome-ctl[verify]'"
        ) from e
    try:
        info = Device(ip, token).info()
        return VerifyResult(True, ip, "locally controllable", info.model, info.firmware_version)
    except Exception as e:  # noqa: BLE001 - report any local failure
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
    """List cloud miir.* remotes + parent blaster + DIY/brand pairing. Returns (dump, rows)."""
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
            kind = "brand-paired"
        elif info_res.get("controller_id") is not None:
            kind = "DIY (self-learned)"
        else:
            kind = "unknown"
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
    """Find a remote in the saved ir dump by substring (name/model/did)."""
    q = query.lower()
    for did, r in ir.items():
        if q in (str(r.get("name", "")) + r.get("model", "") + did).lower():
            return did, r
    return None


def filter_remotes(ir: dict, query: str) -> dict:
    """Subset of the ir dump whose name/model/did contains `query` (case-insensitive)."""
    if not query:
        return dict(ir)
    q = query.lower()
    return {
        did: r
        for did, r in ir.items()
        if q in (str(r.get("name", "")) + r.get("model", "") + did).lower()
    }


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
    """Trigger a remote's key via the cloud (transmitted by the parent blaster); repeat times."""
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
    """Pick air-conditioner remotes: use the substring if a query is given; otherwise all miir.aircondition.*."""
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
    """One-stop air-conditioner control (for MCP/TUI): turn off / set temperature & mode + send. Returns per-step results."""
    if turn_off:
        return [ac_off(conn, did, country)]
    mode_val = AC_MODES.get(mode.lower()) if mode else None
    steps = [ac_set_props(conn, did, country, temp, mode_val)]
    steps.append(ac_send_on(conn, did, country))
    return steps


# ---------------------------------------------------------------- device: generic MIoT (cloud)


def find_device(rows: list[dict], did: str) -> dict | None:
    """Find an extracted device row by did."""
    return next((r for r in rows if str(r.get("did", "")) == str(did)), None)


def miot_get(conn, did: str, country: str, siid: int, piid: int) -> Any:
    """Read one MIoT property over the cloud. Returns the value (or the raw resp on odd shapes)."""
    resp = api(
        conn, country, "/miotspec/prop/get", {"params": [{"did": did, "siid": siid, "piid": piid}]}
    )
    res = resp.get("result") if isinstance(resp, dict) else None
    if isinstance(res, list) and res and isinstance(res[0], dict) and "value" in res[0]:
        return res[0]["value"]
    return resp


def miot_set(conn, did: str, country: str, siid: int, piid: int, value: Any) -> AcResult:
    """Write one MIoT property over the cloud."""
    resp = api(
        conn,
        country,
        "/miotspec/prop/set",
        {"params": [{"did": did, "siid": siid, "piid": piid, "value": value}]},
    )
    return AcResult(miot_ok(resp), "prop/set", resp)


def miot_call(
    conn, did: str, country: str, siid: int, aiid: int, args: list | None = None
) -> AcResult:
    """Call a MIoT action over the cloud."""
    resp = api(
        conn,
        country,
        "/miotspec/action",
        {"params": {"did": did, "siid": siid, "aiid": aiid, "in": args or []}},
    )
    return AcResult(miot_ok(resp), "action", resp)


# ---------------------------------------------------------------- device: local (python-miio)


def _require_miio():
    try:
        import miio
    except ModuleNotFoundError as e:
        raise SystemExit(
            "[mihome-ctl] local device control requires python-miio: pip install 'mihome-ctl[verify]'"
        ) from e
    return miio


def _local_target(dev: dict) -> tuple[str, str]:
    token = dev.get("token")
    ip = _resolve_ip(dev)
    if not token or not ip:
        raise SystemExit(
            f"[mihome-ctl] {dev.get('model', '')} has no token/IP for local control "
            "(not on your LAN?)"
        )
    return ip, token


def local_get(dev: dict, siid: int, piid: int) -> Any:
    ip, token = _local_target(dev)
    return _require_miio().MiotDevice(ip, token).get_property_by(siid, piid)


def local_set(dev: dict, siid: int, piid: int, value: Any) -> Any:
    ip, token = _local_target(dev)
    return _require_miio().MiotDevice(ip, token).set_property_by(siid, piid, value)


def local_call(dev: dict, siid: int, aiid: int, args: list | None = None) -> Any:
    ip, token = _local_target(dev)
    return _require_miio().MiotDevice(ip, token).call_action_by(siid, aiid, args or [])


def local_send(dev: dict, method: str, params: list | None = None) -> Any:
    ip, token = _local_target(dev)
    return _require_miio().Device(ip, token).send(method, params or [])
