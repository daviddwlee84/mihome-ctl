"""``ir-send`` — trigger a remote's key over the cloud (via the parent blaster; no local hardware, works for DIY and brand remotes)."""

from __future__ import annotations

import json
import sys

from ..config import StateDir
from ..core.operations import find_key, find_remote, remote_keys, send_key
from ..session import new_connector


def ir_send(remote: str, key: str | None = None, repeat: int = 1, relogin: bool = False) -> int:
    """Trigger a remote's key over the cloud; omit --key to list the remote's available keys."""
    state = StateDir.resolve()
    if not state.ir_json.exists():
        print(f"[mihome-ctl] Run `ir` first to create {state.ir_json}", file=sys.stderr)
        return 1
    ir = json.loads(state.ir_json.read_text(encoding="utf-8"))
    tgt = find_remote(ir, remote)
    if not tgt:
        print(
            "[mihome-ctl] Remote not found. Available: "
            + ", ".join(r.get("name", "") for r in ir.values()),
            file=sys.stderr,
        )
        return 1
    did, r = tgt
    keys = remote_keys(r)
    if not key:
        print(f"[mihome-ctl] {r['name']} ({r['model']}) available keys ({len(keys)}):")
        for x in keys:
            print(f"  {str(x.get('name', '')):16} {x.get('display_name', '')}")
        return 0
    k = find_key(keys, key)
    if not k:
        print(
            f"[mihome-ctl] {r['name']} has no key matching '{key}'. Available: "
            + ", ".join(f"{x['id']}:{x['name']}" for x in keys),
            file=sys.stderr,
        )
        return 1
    conn, _ = new_connector(state, force_login=relogin)
    res = send_key(conn, did, r, k, repeat)
    print(
        f"[mihome-ctl] {'✅ Sent' if res.ok else '❌ Failed'}: {res.key_name}"
        f" ({res.display_name}) → {res.remote_name} (cloud → emitted by {res.parent_model})"
        + ("" if res.ok else f" — {res.resp}")
    )
    if res.ok and repeat > 1:
        print(f"[mihome-ctl]   (sent {repeat} times total)")
    return 0 if res.ok else 1
