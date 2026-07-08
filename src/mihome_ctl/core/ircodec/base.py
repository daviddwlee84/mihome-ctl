"""IR 碼庫後端介面。

一個後端把 IRDB ``matchid`` 解成 ``{按鍵名: {"frequency", "pronto"}}``。
內建的 :class:`~mihome_ctl.core.ircodec.native.NativeIRCodec` 走純 Python 解碼；
未來可加「呼叫使用者自行安裝的外部 CLI（如 AGPL 的 ysard，opt-in、不打包）」等後端。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IRCodecBackend(Protocol):
    name: str

    def decode_matchid(self, matchid: str, country: str = "CN") -> dict:
        """回傳 ``{按鍵名: {"frequency": int, "pronto": str} | {"error": str}}``。"""
        ...
