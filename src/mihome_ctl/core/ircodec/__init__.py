"""IR code database (IRDB) codec backend.

``NativeIRCodec`` is the default and the only backend bundled with the package
(pure pycryptodome, MIT). Other backends (e.g. an "external CLI adapter") may be
added later — as long as they conform to :class:`IRCodecBackend`.
"""

from __future__ import annotations

from .native import IRDBError, IRDBGatedError, NativeIRCodec

__all__ = ["IRDBError", "IRDBGatedError", "NativeIRCodec", "default_backend"]


def default_backend() -> NativeIRCodec:
    return NativeIRCodec()
