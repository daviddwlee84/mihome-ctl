"""``ir-code`` — IRDB matchid → 每鍵 Pronto（原生解碼，無 AGPL 依賴）。

注意：公開 IRDB 端點目前需 Mi Home app 簽章（未帶簽章回 status:19），故線上以
matchid 取碼標為實驗性；解碼本身以自製 round-trip 測試驗證（見 tests）。
"""

from __future__ import annotations

import json
import sys

from ..config import StateDir, write_secret
from ..core.ircodec import IRDBError, IRDBGatedError, default_backend


def ir_code(matchid: str, country: str = "CN") -> int:
    """IRDB matchid → 每鍵 Pronto（給 chuangmi.ir.v2 play_pronto）。"""
    state = StateDir.resolve()
    backend = default_backend()
    try:
        out = backend.decode_matchid(matchid, country)
    except IRDBGatedError as e:
        print(f"[mihome-ctl] {e}", file=sys.stderr)
        return 2
    except IRDBError as e:
        print(f"[mihome-ctl] {e}", file=sys.stderr)
        return 1
    path = state.ir_code_json(matchid)
    write_secret(path, json.dumps(out, ensure_ascii=False, indent=2))
    freq = next((v.get("frequency") for v in out.values() if "frequency" in v), None)
    print(f"[mihome-ctl] matchid={matchid} freq={freq}Hz，{len(out)} 顆鍵 → {path}")
    for btn, v in list(out.items())[:8]:
        print(f"  {btn:18} {str(v.get('pronto', v.get('error', '')))[:52]}…")
    print("\n重播：chuangmi.ir.v2 → play_pronto('<hex>')（或 HA remote.send_command）。")
    return 0
