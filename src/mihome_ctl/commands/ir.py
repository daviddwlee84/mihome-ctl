"""``ir`` — list cloud miir.* remotes: parent blaster + DIY/brand pairings, saving raw keys/info."""

from __future__ import annotations

import json
import sys

from ..config import StateDir, write_secret
from ..core.operations import enumerate_ir
from ..session import new_connector

DEFAULT_REGIONS = ["tw", "sg", "cn"]


def ir(server: list[str] | None = None, relogin: bool = False) -> int:
    """List cloud miir.* remotes (reuses a stored session; --relogin forces a re-login)."""
    regions = server or DEFAULT_REGIONS
    state = StateDir.resolve()
    conn, reused = new_connector(state, force_login=relogin)
    dump, rows = enumerate_ir(conn, regions)
    if not dump and reused:
        print("[mihome-ctl] Session may have expired; falling back to a fresh QR login …")
        conn, reused = new_connector(state, force_login=True)
        dump, rows = enumerate_ir(conn, regions)
    if reused:
        print("[mihome-ctl] Reusing stored session (--relogin forces a re-login)")
    if not rows:
        print(f"[mihome-ctl] No miir.* remotes found in these regions: {regions}", file=sys.stderr)
        return 1
    write_secret(state.ir_json, json.dumps(dump, ensure_ascii=False, indent=2))
    parents = sorted({r.parent_model for r in rows})
    print(
        f"\n[mihome-ctl] {len(rows)} miir.* remotes → {state.ir_json} (chmod 600, with raw keys/info)\n"
    )
    print("| remote model | name | parent blaster | keys | kind | matchid |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(
            f"| {r.model} | {r.name} | {r.parent_model} | {r.keys} | {r.kind} | {r.controller_id or '—'} |"
        )
    print(f"\nparent blaster: {', '.join(parents)}")
    print(
        "How to read: brand pairing → code lives in Xiaomi's code library (matchid), decodable to pronto; DIY (self-learned) → learned in the cloud, code not directly exportable."
    )
    print(
        "Local replay of either needs a locally controllable blaster (chuangmi.ir.v2); the Xiao AI speaker has no local IR API."
    )
    return 0
