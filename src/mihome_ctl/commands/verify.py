"""``verify`` — run a LAN-local check against a device (python-miio, auto-resolves the current IP via ARP)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import StateDir
from ..core.operations import verify_device


def verify(did: str, out: Path | None = None) -> int:
    """Verify a device's token locally (requires mihome-ctl[verify])."""
    state = StateDir.resolve()
    path = out or state.tokens_json
    if not path.exists():
        print(f"[mihome-ctl] {path} not found; run extract first", file=sys.stderr)
        return 1
    rows = json.loads(path.read_text(encoding="utf-8"))
    dev = next((r for r in rows if r.get("did") == did), None)
    if not dev:
        print(f"[mihome-ctl] did={did} not found", file=sys.stderr)
        return 1
    res = verify_device(dev)
    if res.ok:
        print(
            f"[mihome-ctl] ✅ {dev.get('name', '')} ({dev.get('model', '')}) @ {res.ip} locally controllable"
            f" — model={res.model} fw={res.firmware}"
        )
        return 0
    print(
        f"[mihome-ctl] ❌ {res.model} @ {res.ip or '-'} local check failed: {res.message}",
        file=sys.stderr,
    )
    return 1
