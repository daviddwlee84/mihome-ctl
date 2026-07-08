"""``prop-get`` — read one MIoT property (cloud by default; ``--local`` via python-miio)."""

from __future__ import annotations

import json
import sys

from ..config import StateDir
from ..core.operations import find_device, local_get, miot_get
from ..session import new_connector


def prop_get(did: str, siid: int, piid: int, local: bool = False, relogin: bool = False) -> int:
    """Read a MIoT property (--did --siid --piid). Cloud by default; --local uses the LAN."""
    state = StateDir.resolve()
    if not state.tokens_json.exists():
        print(f"[mihome-ctl] {state.tokens_json} not found; run extract first", file=sys.stderr)
        return 1
    rows = json.loads(state.tokens_json.read_text(encoding="utf-8"))
    dev = find_device(rows, did)
    if not dev:
        print(f"[mihome-ctl] did={did} not found (run `mihome-ctl devices`)", file=sys.stderr)
        return 1
    if local:
        val = local_get(dev, siid, piid)
    else:
        conn, _ = new_connector(state, force_login=relogin)
        val = miot_get(conn, did, dev.get("region", "cn"), siid, piid)
    print(f"[mihome-ctl] {dev.get('name', '')} siid={siid} piid={piid} = {val}")
    return 0
