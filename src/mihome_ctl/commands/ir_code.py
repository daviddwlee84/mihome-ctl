"""``ir-code`` — IRDB matchid → per-key Pronto (native decoding, no AGPL dependency).

Note: the public IRDB endpoint currently requires a Mi Home app signature (returns
status:19 without one), so fetching codes online by matchid is marked experimental;
the decoding itself is validated by a homegrown round-trip test (see tests).
"""

from __future__ import annotations

import json
import sys

from ..config import StateDir, write_secret
from ..core.ircodec import IRDBError, IRDBGatedError, default_backend


def ir_code(matchid: str, country: str = "CN") -> int:
    """IRDB matchid → per-key Pronto (for chuangmi.ir.v2 play_pronto)."""
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
    print(f"[mihome-ctl] matchid={matchid} freq={freq}Hz, {len(out)} keys → {path}")
    for btn, v in list(out.items())[:8]:
        print(f"  {btn:18} {str(v.get('pronto', v.get('error', '')))[:52]}…")
    print("\nReplay: chuangmi.ir.v2 → play_pronto('<hex>') (or HA remote.send_command).")
    return 0
