"""IR code database backend interface.

A backend decodes an IRDB ``matchid`` into ``{key_name: {"frequency", "pronto"}}``.
The bundled :class:`~mihome_ctl.core.ircodec.native.NativeIRCodec` uses pure-Python
decoding; future backends could "invoke an external CLI the user installs themselves
(e.g. the AGPL ysard, opt-in, not bundled)".
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IRCodecBackend(Protocol):
    name: str

    def decode_matchid(self, matchid: str, country: str = "CN") -> dict:
        """Return ``{key_name: {"frequency": int, "pronto": str} | {"error": str}}``."""
        ...
