"""``extract`` — QR 登入官方小米雲，抽每台裝置 token/本地IP/BLE key → .secrets/。"""

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
    """QR 登入並抽 token（預設掃 tw sg cn；--server 覆蓋）。"""
    regions = server or DEFAULT_REGIONS
    state = StateDir.resolve()
    out_path = out or state.tokens_json
    md_path = md or state.devices_md
    conn, _ = new_connector(state, force_login=relogin)
    rows = extract_tokens(conn, regions)
    if not rows:
        print(
            f"[mihome-ctl] 這些區沒找到裝置：{regions}。"
            "改用 --server 指定或留空掃全部（tw sg cn de us ru in i2）。",
            file=sys.stderr,
        )
    write_secret(out_path, json.dumps(rows, ensure_ascii=False, indent=2))
    write_secret(md_path, render_md(rows, reveal=True) + "\n")
    print(f"[mihome-ctl] {len(rows)} 台裝置 → {out_path} (chmod 600) + {md_path}")
    print()
    print(render_md(rows, reveal=show))
    if not show:
        print("\n（token 已遮蔽；完整值在上面的 .secrets/ 檔，或加 --show）")
    return 0
