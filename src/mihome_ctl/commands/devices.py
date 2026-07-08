"""``devices`` — list extracted devices (name / model / did / region / IP) for control."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import StateDir


def devices(out: Path | None = None) -> int:
    """List extracted devices with their did (for prop-get / prop-set / action)."""
    state = StateDir.resolve()
    path = out or state.tokens_json
    if not path.exists():
        print(f"[mihome-ctl] {path} not found; run extract first", file=sys.stderr)
        return 1
    rows = json.loads(path.read_text(encoding="utf-8"))
    print("| device | model | did | region | local IP |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(
            f"| {r.get('name', '')} | `{r.get('model', '')}` | {r.get('did', '')} "
            f"| {r.get('region', '')} | {r.get('localip', '')} |"
        )
    return 0
