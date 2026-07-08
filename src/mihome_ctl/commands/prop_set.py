"""``prop-set`` — write one MIoT property (cloud by default; ``--local`` via python-miio)."""

from __future__ import annotations

import json
import sys

from ..config import StateDir
from ..core.miot import coerce_value
from ..core.operations import find_device, local_set, miot_set
from ..session import new_connector


def prop_set(
    did: str, siid: int, piid: int, value: str, local: bool = False, relogin: bool = False
) -> int:
    """Write a MIoT property (--did --siid --piid --value). Cloud by default; --local uses the LAN."""
    state = StateDir.resolve()
    if not state.tokens_json.exists():
        print(f"[mihome-ctl] {state.tokens_json} not found; run extract first", file=sys.stderr)
        return 1
    rows = json.loads(state.tokens_json.read_text(encoding="utf-8"))
    dev = find_device(rows, did)
    if not dev:
        print(f"[mihome-ctl] did={did} not found (run `mihome-ctl devices`)", file=sys.stderr)
        return 1
    v = coerce_value(value)
    name = dev.get("name", "")
    if local:
        res = local_set(dev, siid, piid, v)
        print(f"[mihome-ctl] {name} set siid={siid} piid={piid} = {v!r} -> {res}")
        return 0
    conn, _ = new_connector(state, force_login=relogin)
    r = miot_set(conn, did, dev.get("region", "cn"), siid, piid, v)
    print(
        f"[mihome-ctl] {'OK set' if r.ok else 'FAIL'} {name} siid={siid} piid={piid} = {v!r}"
        + ("" if r.ok else f" -> {r.resp}")
    )
    return 0 if r.ok else 1
