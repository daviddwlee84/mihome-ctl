from pathlib import Path

import mihome_ctl.config as cfg
from mihome_ctl.config import StateDir


def test_override_wins():
    assert StateDir.resolve(override="/tmp/xyz").root == Path("/tmp/xyz")


def test_env_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("MIHOME_CTL_HOME", str(tmp_path / "home"))
    assert StateDir.resolve().root == (tmp_path / "home")


def test_nearest_secrets(monkeypatch, tmp_path):
    monkeypatch.delenv("MIHOME_CTL_HOME", raising=False)
    (tmp_path / ".secrets").mkdir()
    monkeypatch.chdir(tmp_path)
    assert StateDir.resolve().root == (tmp_path / ".secrets")


def test_platformdirs_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("MIHOME_CTL_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cfg.platformdirs, "user_state_dir", lambda name: str(tmp_path / "state"))
    assert StateDir.resolve().root == (tmp_path / "state")


def test_paths():
    s = StateDir(Path("/x"))
    assert s.tokens_json.name == "mi-tokens.json"
    assert s.devices_md.name == "devices.md"
    assert s.session_json.name == "mi-session.json"
    assert s.ir_json.name == "mi-ir.json"
    assert s.ir_code_json("xm_1_199").name == "ir-code-xm_1_199.json"
