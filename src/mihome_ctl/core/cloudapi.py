"""雲端 API 封裝：登入後的裝置/家庭列舉、IR controller 端點、回應解析。

全部接受一個登入好的 connector，回傳原始 dict/list（不 print）。
"""

from __future__ import annotations

import json
from typing import Any


def api(conn, country: str, path: str, payload: dict) -> Any:
    """對某區呼叫一個加密 API 端點（如 ``/v2/irdevice/controller/keys``）。"""
    url = conn.get_api_url(country) + path
    params = {"data": json.dumps(payload, separators=(",", ":"))}
    return conn.execute_api_call_encrypted(url, params)


def _homes(conn, country: str) -> list[tuple]:
    """回傳 (home_id, owner)：自家 home + 被分享的 share_family。"""
    homes: list[tuple] = []
    h = conn.get_homes(country)
    if h and h.get("result"):
        for x in h["result"].get("homelist", []) or []:
            homes.append((x["id"], conn.userId))
    cnt = conn.get_dev_cnt(country)
    if cnt and cnt.get("result"):
        for x in cnt["result"].get("share", {}).get("share_family", []) or []:
            homes.append((x["home_id"], x["home_owner"]))
    return homes


def collect(conn, regions: list[str]) -> list[dict]:
    """逐區抓 home → device_info，跨區以 did 去重，回傳 token 列表（dict）。"""
    devices: dict[str, dict] = {}
    for country in regions:
        for home_id, owner in _homes(conn, country):
            resp = conn.get_devices(country, home_id, owner)
            info = ((resp or {}).get("result") or {}).get("device_info") or []
            for d in info:
                did = d.get("did", "")
                if not did or did in devices:
                    continue
                rec = {
                    "name": d.get("name", ""),
                    "model": d.get("model", ""),
                    "did": did,
                    "region": country,
                    "localip": d.get("localip", ""),
                    "token": d.get("token", ""),
                    "mac": d.get("mac", ""),
                }
                if "blt" in did:  # BLE 裝置：多抓 beaconkey
                    bk = conn.get_beaconkey(country, did)
                    if bk and bk.get("result"):
                        rec["beaconkey"] = bk["result"].get("beaconkey", "")
                devices[did] = rec
    return list(devices.values())


def fetch_devices(conn, regions: list[str]) -> dict:
    """did -> {model,name,region,parent_id}，跨區（供 IR 對照 parent blaster）。"""
    devmap: dict[str, dict] = {}
    for country in regions:
        for home_id, owner in _homes(conn, country):
            resp = conn.get_devices(country, home_id, owner)
            for d in ((resp or {}).get("result") or {}).get("device_info") or []:
                did = str(d.get("did", ""))
                if did and did not in devmap:
                    devmap[did] = {
                        "model": d.get("model", ""),
                        "name": d.get("name", ""),
                        "region": country,
                        "parent_id": str(d.get("parent_id", "") or ""),
                    }
    return devmap


def keys_have_code(keys_resp) -> tuple[int, bool]:
    """(鍵數, 是否有任何 raw code)。回應結構不確定，盡量容錯。"""
    res = (keys_resp or {}).get("result")
    keys = res.get("keys") or res.get("list") or [] if isinstance(res, dict) else (res or [])
    has_code = any(
        isinstance(k, dict) and (k.get("code") or k.get("ir_code") or k.get("value"))
        for k in (keys if isinstance(keys, list) else [])
    )
    return (len(keys) if isinstance(keys, list) else 0), has_code
