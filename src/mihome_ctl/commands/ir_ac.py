"""``ir-ac`` — 冷氣絕對控制（設溫度/模式/開關，走 MIoT-spec；狀態式家電才做得到絕對）。"""

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
    """冷氣絕對控制：--temp 16-30 / --mode / --on / --off / --status。"""
    state = StateDir.resolve()
    if not state.ir_json.exists():
        print(f"[mihome-ctl] 先跑 `ir` 建立 {state.ir_json}", file=sys.stderr)
        return 1
    ir = json.loads(state.ir_json.read_text(encoding="utf-8"))
    matches = ac_remotes(ir, remote)
    if not matches:
        print("[mihome-ctl] 找不到冷氣遙控（miir.aircondition.*）；用 `ir` 看清單", file=sys.stderr)
        return 1
    if len(matches) > 1:
        print(
            "[mihome-ctl] 有多台冷氣遙控，請用 --remote 指定："
            + "、".join(r["name"] for _, r in matches),
            file=sys.stderr,
        )
        return 1
    did, r = matches[0]
    country = r.get("region", "cn")
    print(f"[mihome-ctl] 目標冷氣：{r['name']}（{r['model']}）")
    if temp is not None and not (16 <= temp <= 30):
        print("[mihome-ctl] --temp 需 16-30", file=sys.stderr)
        return 1
    mode_val = AC_MODES.get(mode) if mode else None
    conn, _ = new_connector(state, force_login=relogin)
    if status:
        print(f"[mihome-ctl] {r['name']} 目前 ac_state：{ac_status(conn, did, country)}")
        return 0
    if off:
        res = ac_off(conn, did, country)
        print(f"[mihome-ctl] {'✅ 已關冷氣' if res.ok else '❌ ' + str(res.resp)}")
        return 0 if res.ok else 1
    if temp is None and mode is None and not on:
        print("[mihome-ctl] 指定 --temp / --mode / --on / --off / --status 其一", file=sys.stderr)
        return 1
    if temp is not None or mode is not None:
        p = ac_set_props(conn, did, country, temp, mode_val)
        tag = (mode or "") + (f" {temp}°C" if temp is not None else "")
        print(f"[mihome-ctl] 設定{tag}：{'✅' if p.ok else '❌ ' + str(p.resp)}")
    s = ac_send_on(conn, did, country)
    print(
        f"[mihome-ctl] 開機/送出：{'✅ 已送出（看冷氣有沒有反應）' if s.ok else '❌ ' + str(s.resp)}"
    )
    return 0
