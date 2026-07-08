"""``list`` — reprint the last extract result offline (no network)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import StateDir
from ..render import render_md


def list_(out: Path | None = None, show: bool = False) -> int:
    """Reprint the last extract result offline."""
    state = StateDir.resolve()
    path = out or state.tokens_json
    if not path.exists():
        print(f"[mihome-ctl] {path} not found; run extract first", file=sys.stderr)
        return 1
    rows = json.loads(path.read_text(encoding="utf-8"))
    print(render_md(rows, reveal=show))
    return 0
