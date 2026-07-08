"""``ir`` — 列出雲端 miir.* 遙控：parent blaster + DIY/品牌配對，原始 keys/info 存檔。"""

from __future__ import annotations

import json
import sys

from ..config import StateDir, write_secret
from ..core.operations import enumerate_ir
from ..session import new_connector

DEFAULT_REGIONS = ["tw", "sg", "cn"]


def ir(server: list[str] | None = None, relogin: bool = False) -> int:
    """列出雲端 miir.* 遙控（沿用已存 session；--relogin 強制重登）。"""
    regions = server or DEFAULT_REGIONS
    state = StateDir.resolve()
    conn, reused = new_connector(state, force_login=relogin)
    dump, rows = enumerate_ir(conn, regions)
    if not dump and reused:
        print("[mihome-ctl] session 可能過期，改重新 QR 登入 …")
        conn, reused = new_connector(state, force_login=True)
        dump, rows = enumerate_ir(conn, regions)
    if reused:
        print("[mihome-ctl] 沿用已存 session（--relogin 可強制重登）")
    if not rows:
        print(f"[mihome-ctl] 這些區沒找到 miir.* 遙控：{regions}", file=sys.stderr)
        return 1
    write_secret(state.ir_json, json.dumps(dump, ensure_ascii=False, indent=2))
    parents = sorted({r.parent_model for r in rows})
    print(
        f"\n[mihome-ctl] {len(rows)} 個 miir.* 遙控 → {state.ir_json} (chmod 600，含原始 keys/info)\n"
    )
    print("| 遙控 model | 名稱 | parent blaster | 鍵數 | 類型 | matchid |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(
            f"| {r.model} | {r.name} | {r.parent_model} | {r.keys} | {r.kind} | {r.controller_id or '—'} |"
        )
    print(f"\nparent blaster：{', '.join(parents)}")
    print(
        "判讀：品牌配對 → 碼在小米碼庫(matchid)，可解成 pronto；DIY(自學) → 雲端 learn、碼不直接匯出。"
    )
    print("兩者本地重播都需一顆能本地控的 blaster（chuangmi.ir.v2）；小愛音箱沒有本地 IR API。")
    return 0
