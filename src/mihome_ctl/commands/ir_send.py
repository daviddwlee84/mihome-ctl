"""``ir-send`` — 雲端觸發遙控某鍵（經 parent blaster；免本地硬體，DIY/品牌皆可）。"""

from __future__ import annotations

import json
import sys

from ..config import StateDir
from ..core.operations import find_key, find_remote, remote_keys, send_key
from ..session import new_connector


def ir_send(remote: str, key: str | None = None, repeat: int = 1, relogin: bool = False) -> int:
    """雲端觸發遙控某鍵；省略 --key 則列出該遙控可用鍵。"""
    state = StateDir.resolve()
    if not state.ir_json.exists():
        print(f"[mihome-ctl] 先跑 `ir` 建立 {state.ir_json}", file=sys.stderr)
        return 1
    ir = json.loads(state.ir_json.read_text(encoding="utf-8"))
    tgt = find_remote(ir, remote)
    if not tgt:
        print(
            "[mihome-ctl] 找不到遙控。可用：" + ", ".join(r.get("name", "") for r in ir.values()),
            file=sys.stderr,
        )
        return 1
    did, r = tgt
    keys = remote_keys(r)
    if not key:
        print(f"[mihome-ctl] {r['name']}（{r['model']}）可用的鍵（{len(keys)}）：")
        for x in keys:
            print(f"  {str(x.get('name', '')):16} {x.get('display_name', '')}")
        return 0
    k = find_key(keys, key)
    if not k:
        print(
            f"[mihome-ctl] {r['name']} 沒有含「{key}」的鍵。可用："
            + ", ".join(f"{x['id']}:{x['name']}" for x in keys),
            file=sys.stderr,
        )
        return 1
    conn, _ = new_connector(state, force_login=relogin)
    res = send_key(conn, did, r, k, repeat)
    print(
        f"[mihome-ctl] {'✅ 已送出' if res.ok else '❌ 失敗'}：{res.key_name}"
        f"（{res.display_name}）→ {res.remote_name}（雲端 → {res.parent_model} 發射）"
        + ("" if res.ok else f" — {res.resp}")
    )
    if res.ok and repeat > 1:
        print(f"[mihome-ctl]   （共送 {repeat} 次）")
    return 0 if res.ok else 1
