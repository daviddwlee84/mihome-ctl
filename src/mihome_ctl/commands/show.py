"""``list`` — 離線重印上次 extract 的結果（不連線）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import StateDir
from ..render import render_md


def list_(out: Path | None = None, show: bool = False) -> int:
    """離線重印上次 extract 結果。"""
    state = StateDir.resolve()
    path = out or state.tokens_json
    if not path.exists():
        print(f"[mihome-ctl] 找不到 {path}，請先跑 extract", file=sys.stderr)
        return 1
    rows = json.loads(path.read_text(encoding="utf-8"))
    print(render_md(rows, reveal=show))
    return 0
