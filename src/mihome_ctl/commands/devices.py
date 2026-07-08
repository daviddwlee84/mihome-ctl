"""``devices`` — list extracted devices (name / model / did / region / IP) for control."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tabulate import tabulate

from ..config import StateDir

_HEADERS = ["device", "model", "did", "region", "local IP"]


def devices(out: Path | None = None, md: bool = False) -> int:
    """List extracted devices with their did (for prop-get / prop-set / action). --md for markdown."""
    state = StateDir.resolve()
    path = out or state.tokens_json
    if not path.exists():
        print(f"[mihome-ctl] {path} not found; run extract first", file=sys.stderr)
        return 1
    rows = json.loads(path.read_text(encoding="utf-8"))
    table = [
        [
            r.get("name", ""),
            r.get("model", ""),
            r.get("did", ""),
            r.get("region", ""),
            r.get("localip", ""),
        ]
        for r in rows
    ]
    fmt = "github" if md else "rounded_outline"
    print(tabulate(table, headers=_HEADERS, tablefmt=fmt))
    return 0
