"""Native (clean-room) IRDB decoding: AES-128-ECB + gzip + microsecond timings → Pronto.

The implementation follows the **public protocol** (this repo's ``docs/control/ir.md``,
the official miot-plugin-sdk's ircontroller.js, etc.); it contains no AGPL code,
vendors nothing, and downloads no AGPL tool at runtime.

Each key in the Xiaomi IR code database is ``base64( AES-ECB( gzip( microsecond-timing text ) ) )``,
with the key being the public constant ``fd7e915003168929c1a9b0ec32a60788`` (16-byte, AES-128).

Limitations (stated honestly): the public ``{region}-urc.io.mi.com/controller/code/1``
endpoint currently requires a Mi Home app signature (returns ``status:19`` without one),
so the "fetch a code online by matchid" path cannot be verified without a signature and
is marked experimental. The decoding itself (``decode_code``) is validated by an in-house
round-trip test (see tests). For offline decoding, feed a raw encrypted code directly to
``decode_code``.
"""

from __future__ import annotations

import base64
import gzip
import re
import zlib

import requests

from ..pronto import timings_to_pronto

try:
    from Crypto.Cipher import AES
except ModuleNotFoundError:  # pragma: no cover
    from Cryptodome.Cipher import AES

# Public protocol constants (see also docs/control/ir.md).
_AES_KEY = bytes.fromhex("fd7e915003168929c1a9b0ec32a60788")
_URC_URL = "https://{region}-urc.io.mi.com/controller/code/1"
_UA = "MISmartHome/6.4.9"


class IRDBError(RuntimeError):
    """IRDB code fetch/decode failure."""


class IRDBGatedError(IRDBError):
    """The public IRDB endpoint requires an app signature (returns something like status:19); anonymous code fetch is impossible."""


def _aes_decrypt(data: bytes) -> bytes:
    return AES.new(_AES_KEY, AES.MODE_ECB).decrypt(data)


def _aes_encrypt(data: bytes) -> bytes:
    pad = (-len(data)) % 16
    return AES.new(_AES_KEY, AES.MODE_ECB).encrypt(data + b"\x00" * pad)


def _gunzip(data: bytes) -> bytes:
    """Gunzip; tolerate trailing bytes from AES padding (zlib stops after reading one member)."""
    d = zlib.decompressobj(31)
    out = d.decompress(data)
    return out + d.flush()


def decode_code(enc: str) -> list[int]:
    """A single key's encrypted code → a list of microsecond ON/OFF timings."""
    raw = base64.b64decode(enc)
    payload = _gunzip(_aes_decrypt(raw))
    text = payload.decode("ascii", "ignore")
    return [int(x) for x in re.findall(r"\d+", text)]


def encode_code(timings: list[int]) -> str:
    """Microsecond timings → encrypted code (inverse of ``decode_code``; for round-trip tests)."""
    text = " ".join(str(int(t)) for t in timings).encode("ascii")
    gz = gzip.compress(text, mtime=0)
    return base64.b64encode(_aes_encrypt(gz)).decode()


def fetch_matchid(matchid: str, country: str = "CN") -> dict:
    """Hit the public IRDB endpoint to fetch a matchid's code; raise :class:`IRDBGatedError` when blocked by the signature gate."""
    url = _URC_URL.format(region=country.lower())
    try:
        r = requests.get(
            url,
            params={"matchid": matchid, "vendor": "mi"},
            headers={"User-Agent": _UA},
            timeout=15,
        )
        data = r.json()
    except Exception as e:  # noqa: BLE001
        raise IRDBError(f"IRDB code fetch failed: {type(e).__name__}: {e}") from e
    d = data.get("data") if isinstance(data, dict) else None
    if not isinstance(d, dict) or not d.get("key"):
        status = data.get("status") if isinstance(data, dict) else None
        if status not in (0, None):
            raise IRDBGatedError(
                f"IRDB responded status={status}: the public {url} endpoint currently requires a "
                "Mi Home app signature, so a code cannot be fetched anonymously by matchid. "
                "Feed a raw encrypted code to decode_code instead, "
                "or use an external backend (see README)."
            )
        raise IRDBError(f"IRDB found no matchid={matchid}")
    return d


def decode_matchid(matchid: str, country: str = "CN") -> dict:
    """matchid → ``{key_name: {"frequency", "pronto"} | {"error"}}``."""
    d = fetch_matchid(matchid, country)
    freq = int(d.get("frequency") or 38000)
    out: dict[str, dict] = {}
    for btn, enc in d["key"].items():
        try:
            out[btn] = {"frequency": freq, "pronto": timings_to_pronto(decode_code(enc), freq)}
        except Exception as e:  # noqa: BLE001
            out[btn] = {"error": f"{type(e).__name__}: {e}"}
    return out


class NativeIRCodec:
    """Default backend: pure-Python decoding (no AGPL dependency)."""

    name = "native"

    def decode_matchid(self, matchid: str, country: str = "CN") -> dict:
        return decode_matchid(matchid, country)
