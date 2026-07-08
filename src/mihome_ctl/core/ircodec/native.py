"""原生（clean-room）IRDB 解碼：AES-128-ECB + gzip + 微秒時序 → Pronto。

實作依據**公開協議**（本 repo ``docs/control/ir.md``、官方 miot-plugin-sdk 的
ircontroller.js 等），不含任何 AGPL 程式碼、不 vendor、不在執行期下載 AGPL 工具。

小米 IR 碼庫的每顆鍵是：``base64( AES-ECB( gzip( 微秒時序文字 ) ) )``，
金鑰為公開常數 ``fd7e915003168929c1a9b0ec32a60788``（16-byte，AES-128）。

限制（誠實說明）：公開的 ``{region}-urc.io.mi.com/controller/code/1`` 端點目前需
Mi Home app 簽章（未帶簽章回 ``status:19``），故「線上以 matchid 取碼」這條路徑
無法在無簽章下驗證，標為實驗性。解碼本身（``decode_code``）以自製 round-trip
測試驗證（見 tests）。要離線解碼可直接餵 raw 加密碼給 ``decode_code``。
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

# 公開協議常數（亦見 docs/control/ir.md）。
_AES_KEY = bytes.fromhex("fd7e915003168929c1a9b0ec32a60788")
_URC_URL = "https://{region}-urc.io.mi.com/controller/code/1"
_UA = "MISmartHome/6.4.9"


class IRDBError(RuntimeError):
    """IRDB 取碼/解碼失敗。"""


class IRDBGatedError(IRDBError):
    """公開 IRDB 端點需 app 簽章（回 status:19 之類），無法匿名取碼。"""


def _aes_decrypt(data: bytes) -> bytes:
    return AES.new(_AES_KEY, AES.MODE_ECB).decrypt(data)


def _aes_encrypt(data: bytes) -> bytes:
    pad = (-len(data)) % 16
    return AES.new(_AES_KEY, AES.MODE_ECB).encrypt(data + b"\x00" * pad)


def _gunzip(data: bytes) -> bytes:
    """解 gzip；容忍 AES 補位造成的尾端多餘位元組（zlib 讀完一個 member 即停）。"""
    d = zlib.decompressobj(31)
    out = d.decompress(data)
    return out + d.flush()


def decode_code(enc: str) -> list[int]:
    """單顆鍵的加密碼 → 微秒 ON/OFF 時序 list。"""
    raw = base64.b64decode(enc)
    payload = _gunzip(_aes_decrypt(raw))
    text = payload.decode("ascii", "ignore")
    return [int(x) for x in re.findall(r"\d+", text)]


def encode_code(timings: list[int]) -> str:
    """微秒時序 → 加密碼（``decode_code`` 的逆運算；供測試 round-trip）。"""
    text = " ".join(str(int(t)) for t in timings).encode("ascii")
    gz = gzip.compress(text, mtime=0)
    return base64.b64encode(_aes_encrypt(gz)).decode()


def fetch_matchid(matchid: str, country: str = "CN") -> dict:
    """打公開 IRDB 端點取某 matchid 的碼；被簽章擋下時 raise :class:`IRDBGatedError`。"""
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
        raise IRDBError(f"IRDB 取碼失敗：{type(e).__name__}: {e}") from e
    d = data.get("data") if isinstance(data, dict) else None
    if not isinstance(d, dict) or not d.get("key"):
        status = data.get("status") if isinstance(data, dict) else None
        if status not in (0, None):
            raise IRDBGatedError(
                f"IRDB 回應 status={status}：公開 {url} 端點目前需 Mi Home app 簽章，"
                "無法匿名以 matchid 取碼。可改餵 raw 加密碼給 decode_code，"
                "或用外部後端（見 README）。"
            )
        raise IRDBError(f"IRDB 查無 matchid={matchid}")
    return d


def decode_matchid(matchid: str, country: str = "CN") -> dict:
    """matchid → ``{按鍵名: {"frequency", "pronto"} | {"error"}}``。"""
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
    """預設後端：純 Python 解碼（無 AGPL 依賴）。"""

    name = "native"

    def decode_matchid(self, matchid: str, country: str = "CN") -> dict:
        return decode_matchid(matchid, country)
