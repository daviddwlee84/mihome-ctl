"""``miio`` — raw local miIO call via python-miio (on-LAN only)."""

from __future__ import annotations

import json
import sys

from ..config import StateDir
from ..core.miot import coerce_value
from ..core.operations import find_device, local_send


def miio(did: str, method: str, params: str = "[]") -> int:
    """Raw local miIO call (--did --method [--params '[...]']). LAN only; needs mihome-ctl[verify]."""
    state = StateDir.resolve()
    if not state.tokens_json.exists():
        print(f"[mihome-ctl] {state.tokens_json} not found; run extract first", file=sys.stderr)
        return 1
    rows = json.loads(state.tokens_json.read_text(encoding="utf-8"))
    dev = find_device(rows, did)
    if not dev:
        print(f"[mihome-ctl] did={did} not found (run `mihome-ctl devices`)", file=sys.stderr)
        return 1
    p = coerce_value(params)
    if not isinstance(p, list):
        p = [p]
    res = local_send(dev, method, p)
    print(f"[mihome-ctl] {dev.get('name', '')} {method}({p}) -> {res}")
    return 0
