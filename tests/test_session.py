import os
import stat
from types import SimpleNamespace

from mihome_ctl.config import StateDir
from mihome_ctl.session import load_session, save_session


def test_session_roundtrip_and_perms(tmp_path):
    state = StateDir(tmp_path)
    conn = SimpleNamespace(userId=6421538300, _ssecurity="zVuj==", _serviceToken="tok")
    save_session(state, conn)
    assert load_session(state) == {
        "userId": 6421538300,
        "ssecurity": "zVuj==",
        "serviceToken": "tok",
    }
    mode = stat.S_IMODE(os.stat(state.session_json).st_mode)
    assert mode == 0o600


def test_missing_session_returns_none(tmp_path):
    assert load_session(StateDir(tmp_path)) is None
