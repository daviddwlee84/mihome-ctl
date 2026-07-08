"""Cloud API wrappers: post-login device/home enumeration, IR controller endpoints, response parsing.

All take a logged-in connector and return raw dict/list (no print).
"""

from __future__ import annotations

import json
from typing import Any


def api(conn, country: str, path: str, payload: dict) -> Any:
    """Call one encrypted API endpoint for a region (e.g. ``/v2/irdevice/controller/keys``)."""
    url = conn.get_api_url(country) + path
    params = {"data": json.dumps(payload, separators=(",", ":"))}
    return conn.execute_api_call_encrypted(url, params)


def _homes(conn, country: str) -> list[tuple]:
    """Return (home_id, owner): own homes plus shared share_family."""
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
    """Fetch home → device_info per region, dedupe across regions by did, return a token list (dicts)."""
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
                if "blt" in did:  # BLE device: also fetch beaconkey
                    bk = conn.get_beaconkey(country, did)
                    if bk and bk.get("result"):
                        rec["beaconkey"] = bk["result"].get("beaconkey", "")
                devices[did] = rec
    return list(devices.values())


def fetch_devices(conn, regions: list[str]) -> dict:
    """did -> {model,name,region,parent_id}, across regions (for matching IR remotes to the parent blaster)."""
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
    """(key count, whether any raw code exists). The response shape is uncertain, so stay tolerant."""
    res = (keys_resp or {}).get("result")
    keys = res.get("keys") or res.get("list") or [] if isinstance(res, dict) else (res or [])
    has_code = any(
        isinstance(k, dict) and (k.get("code") or k.get("ir_code") or k.get("value"))
        for k in (keys if isinstance(keys, list) else [])
    )
    return (len(keys) if isinstance(keys, list) else 0), has_code
