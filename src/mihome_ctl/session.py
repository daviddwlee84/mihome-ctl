"""QR session cache (``mi-session.json``) and connector factory.

The session schema is fixed as ``{"userId", "ssecurity", "serviceToken"}`` for
compatibility with older tools; a reusable session avoids re-scanning the QR.
``new_connector(force_login=True)`` forces a re-login.
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
    """Draw the login QR directly in the terminal (python-qrcode); the browser :31415 flow stays as a fallback."""
    try:
        import qrcode
    except ImportError:
        return
    orig = conn.login_step_2

    def step2():
        url = getattr(conn, "_login_url", None)
        if url:
            print("\n[mihome-ctl] Scan the QR below with the Mi Home app:\n")
            qr = qrcode.QRCode(border=1)
            qr.add_data(url)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
        return orig()

    conn.login_step_2 = step2


def new_connector(
    state: StateDir, force_login: bool = False, host: str = "127.0.0.1"
) -> tuple[QrCodeXiaomiCloudConnector, bool]:
    """Return (connector, reused). Reuse a stored session to avoid re-scanning the QR."""
    conn = QrCodeXiaomiCloudConnector(host=host)
    sess = None if force_login else load_session(state)
    if sess and sess.get("serviceToken") and sess.get("ssecurity") and sess.get("userId"):
        conn.userId = sess["userId"]
        conn._ssecurity = sess["ssecurity"]
        conn._serviceToken = sess["serviceToken"]
        return conn, True
    install_terminal_qr(conn)
    print(
        "[mihome-ctl] Passwordless QR login (scan the terminal QR, or open http://127.0.0.1:31415):"
    )
    if not conn.login():
        raise SystemExit("[mihome-ctl] Login failed (QR timed out or was cancelled)")
    save_session(state, conn)
    return conn, False
