"""IR 碼庫（IRDB）編解碼後端。

``NativeIRCodec`` 是預設、且是套件唯一內建的後端（純 pycryptodome，MIT）。
未來可另加「外部 CLI adapter」等後端——只要符合 :class:`IRCodecBackend`。
"""

from __future__ import annotations

from .native import IRDBError, IRDBGatedError, NativeIRCodec

__all__ = ["IRDBError", "IRDBGatedError", "NativeIRCodec", "default_backend"]


def default_backend() -> NativeIRCodec:
    return NativeIRCodec()
