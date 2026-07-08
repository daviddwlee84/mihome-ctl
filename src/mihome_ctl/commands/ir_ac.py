"""``ir-ac`` — absolute AC control (set temperature/mode/power via MIoT-spec; only stateful appliances support absolute control)."""

from __future__ import annotations

import json
import sys
from typing import Literal

from ..config import StateDir
from ..core.miot import AC_MODES
from ..core.operations import ac_off, ac_remotes, ac_send_on, ac_set_props, ac_status
from ..session import new_connector

Mode = Literal["auto", "cool", "dry", "heat", "fan"]


def ir_ac(
    remote: str | None = None,
    temp: int | None = None,
    mode: Mode | None = None,
    on: bool = False,
    off: bool = False,
    status: bool = False,
    relogin: bool = False,
) -> int:
    """Absolute AC control: --temp 16-30 / --mode / --on / --off / --status."""
    state = StateDir.resolve()
    if not state.ir_json.exists():
        print(f"[mihome-ctl] Run `ir` first to create {state.ir_json}", file=sys.stderr)
        return 1
    ir = json.loads(state.ir_json.read_text(encoding="utf-8"))
    matches = ac_remotes(ir, remote)
    if not matches:
        print(
            "[mihome-ctl] No AC remote found (miir.aircondition.*); run `ir` to see the list",
            file=sys.stderr,
        )
        return 1
    if len(matches) > 1:
        print(
            "[mihome-ctl] Multiple AC remotes; specify one with --remote: "
            + ", ".join(r["name"] for _, r in matches),
            file=sys.stderr,
        )
        return 1
    did, r = matches[0]
    country = r.get("region", "cn")
    print(f"[mihome-ctl] Target AC: {r['name']} ({r['model']})")
    if temp is not None and not (16 <= temp <= 30):
        print("[mihome-ctl] --temp must be 16-30", file=sys.stderr)
        return 1
    mode_val = AC_MODES.get(mode) if mode else None
    conn, _ = new_connector(state, force_login=relogin)
    if status:
        print(f"[mihome-ctl] {r['name']} current ac_state: {ac_status(conn, did, country)}")
        return 0
    if off:
        res = ac_off(conn, did, country)
        print(f"[mihome-ctl] {'✅ AC turned off' if res.ok else '❌ ' + str(res.resp)}")
        return 0 if res.ok else 1
    if temp is None and mode is None and not on:
        print(
            "[mihome-ctl] Specify one of --temp / --mode / --on / --off / --status", file=sys.stderr
        )
        return 1
    if temp is not None or mode is not None:
        p = ac_set_props(conn, did, country, temp, mode_val)
        tag = (mode or "") + (f" {temp}°C" if temp is not None else "")
        print(f"[mihome-ctl] Set {tag}: {'✅' if p.ok else '❌ ' + str(p.resp)}")
    s = ac_send_on(conn, did, country)
    print(
        f"[mihome-ctl] Power on/send: {'✅ Sent (check whether the AC responds)' if s.ok else '❌ ' + str(s.resp)}"
    )
    return 0
