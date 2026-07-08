"""``action`` — call a MIoT action (cloud by default; ``--local`` via python-miio)."""

from __future__ import annotations

import json
import sys

from ..config import StateDir
from ..core.miot import coerce_value
from ..core.operations import find_device, local_call, miot_call
from ..session import new_connector


def action(
    did: str, siid: int, aiid: int, args: str = "[]", local: bool = False, relogin: bool = False
) -> int:
    """Call a MIoT action (--did --siid --aiid [--args '[...]']). Cloud by default; --local uses the LAN."""
    state = StateDir.resolve()
    if not state.tokens_json.exists():
        print(f"[mihome-ctl] {state.tokens_json} not found; run extract first", file=sys.stderr)
        return 1
    rows = json.loads(state.tokens_json.read_text(encoding="utf-8"))
    dev = find_device(rows, did)
    if not dev:
        print(f"[mihome-ctl] did={did} not found (run `mihome-ctl devices`)", file=sys.stderr)
        return 1
    a = coerce_value(args)
    if not isinstance(a, list):
        a = [a]
    name = dev.get("name", "")
    if local:
        res = local_call(dev, siid, aiid, a)
        print(f"[mihome-ctl] {name} action siid={siid} aiid={aiid} in={a} -> {res}")
        return 0
    conn, _ = new_connector(state, force_login=relogin)
    r = miot_call(conn, did, dev.get("region", "cn"), siid, aiid, a)
    print(
        f"[mihome-ctl] {'OK action' if r.ok else 'FAIL'} {name} siid={siid} aiid={aiid} in={a}"
        + ("" if r.ok else f" -> {r.resp}")
    )
    return 0 if r.ok else 1
