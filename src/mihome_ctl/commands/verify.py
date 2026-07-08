"""``verify`` — 對某台裝置做 LAN 本地驗證（python-miio，自動 ARP 解即時 IP）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import StateDir
from ..core.operations import verify_device


def verify(did: str, out: Path | None = None) -> int:
    """本地驗證某台 token（需 mihome-ctl[verify]）。"""
    state = StateDir.resolve()
    path = out or state.tokens_json
    if not path.exists():
        print(f"[mihome-ctl] 找不到 {path}，請先跑 extract", file=sys.stderr)
        return 1
    rows = json.loads(path.read_text(encoding="utf-8"))
    dev = next((r for r in rows if r.get("did") == did), None)
    if not dev:
        print(f"[mihome-ctl] 找不到 did={did}", file=sys.stderr)
        return 1
    res = verify_device(dev)
    if res.ok:
        print(
            f"[mihome-ctl] ✅ {dev.get('name', '')}（{dev.get('model', '')}）@ {res.ip} 本地可控"
            f" — model={res.model} fw={res.firmware}"
        )
        return 0
    print(f"[mihome-ctl] ❌ {res.model} @ {res.ip or '-'} 本地失敗：{res.message}", file=sys.stderr)
    return 1
