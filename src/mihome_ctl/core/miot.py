"""MIoT-spec helpers: air-conditioner mode mapping, response success check, value parsing."""

from __future__ import annotations

import json
from typing import Any

# ir-mode (siid 2 / piid 1): auto/cool/dry/heat/fan = 0..4
AC_MODES: dict[str, int] = {"auto": 0, "cool": 1, "dry": 2, "heat": 3, "fan": 4}


def coerce_value(s: str) -> Any:
    """Parse a CLI value string: JSON first (26->int, true->bool, [26]->list); bare string otherwise."""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return s


def miot_ok(resp: Any) -> bool:
    """Whether a MIoT prop/set / action response succeeded overall."""
    if not isinstance(resp, dict) or resp.get("code") != 0:
        return False
    res = resp.get("result")
    if isinstance(res, list):
        return all(x.get("code", 0) == 0 for x in res if isinstance(x, dict))
    return True
