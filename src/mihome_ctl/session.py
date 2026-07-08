"""QR session 快取（``mi-session.json``）與 connector 工廠。

session schema 固定為 ``{"userId", "ssecurity", "serviceToken"}``，與舊工具相容；
能沿用就不重掃 QR。``new_connector(force_login=True)`` 強制重登。
"""

from __future__ import annotations

import json

from .config import StateDir, write_secret
from .connector import QrCodeXiaomiCloudConnector


def load_session(state: StateDir) -> dict | None:
    p = state.session_json
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_session(state: StateDir, conn: QrCodeXiaomiCloudConnector) -> None:
    write_secret(
        state.session_json,
        json.dumps(
            {
                "userId": conn.userId,
                "ssecurity": conn._ssecurity,
                "serviceToken": conn._serviceToken,
            },
            indent=2,
        ),
    )


def install_terminal_qr(conn: QrCodeXiaomiCloudConnector) -> None:
    """把登入 QR 直接畫在終端機（python-qrcode）；browser :31415 仍保留為 fallback。"""
    try:
        import qrcode
    except ImportError:
        return
    orig = conn.login_step_2

    def step2():
        url = getattr(conn, "_login_url", None)
        if url:
            print("\n[mihome-ctl] 用『米家 App』掃描下方 QR：\n")
            qr = qrcode.QRCode(border=1)
            qr.add_data(url)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
        return orig()

    conn.login_step_2 = step2


def new_connector(
    state: StateDir, force_login: bool = False, host: str = "127.0.0.1"
) -> tuple[QrCodeXiaomiCloudConnector, bool]:
    """回傳 (connector, reused)。能沿用已存 session 就不重掃 QR。"""
    conn = QrCodeXiaomiCloudConnector(host=host)
    sess = None if force_login else load_session(state)
    if sess and sess.get("serviceToken") and sess.get("ssecurity") and sess.get("userId"):
        conn.userId = sess["userId"]
        conn._ssecurity = sess["ssecurity"]
        conn._serviceToken = sess["serviceToken"]
        return conn, True
    install_terminal_qr(conn)
    print("[mihome-ctl] 免密碼 QR 登入（掃終端機 QR，或開 http://127.0.0.1:31415）：")
    if not conn.login():
        raise SystemExit("[mihome-ctl] 登入失敗（QR 逾時或被取消）")
    save_session(state, conn)
    return conn, False
