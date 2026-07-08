"""``extract`` — QR login to the official Xiaomi cloud, extract each device's token/local IP/BLE key → .secrets/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import StateDir, write_secret
from ..core.operations import extract_tokens
from ..render import render_md
from ..session import new_connector

DEFAULT_REGIONS = ["tw", "sg", "cn"]


def extract(
    server: list[str] | None = None,
    show: bool = False,
    out: Path | None = None,
    md: Path | None = None,
    relogin: bool = False,
) -> int:
    """QR login and extract tokens (scans tw sg cn by default; --server overrides)."""
    regions = server or DEFAULT_REGIONS
    state = StateDir.resolve()
    out_path = out or state.tokens_json
    md_path = md or state.devices_md
    conn, _ = new_connector(state, force_login=relogin)
    rows = extract_tokens(conn, regions)
    if not rows:
        print(
            f"[mihome-ctl] No devices found in these regions: {regions}. "
            "Use --server to specify, or leave blank to scan all (tw sg cn de us ru in i2).",
            file=sys.stderr,
        )
    write_secret(out_path, json.dumps(rows, ensure_ascii=False, indent=2))
    write_secret(md_path, render_md(rows, reveal=True) + "\n")
    print(f"[mihome-ctl] {len(rows)} devices → {out_path} (chmod 600) + {md_path}")
    print()
    print(render_md(rows, reveal=show))
    if not show:
        print("\n(tokens are masked; full values are in the .secrets/ file above, or add --show)")
    return 0
