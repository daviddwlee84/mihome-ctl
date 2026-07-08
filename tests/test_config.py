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
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cfg.platformdirs, "user_state_dir", lambda name: str(tmp_path / "state"))
    assert StateDir.resolve().root == (tmp_path / "state")


def test_xdg_state_home_wins(monkeypatch, tmp_path):
    # XDG_STATE_HOME honored even on macOS; legacy dir absent → use XDG path.
    monkeypatch.delenv("MIHOME_CTL_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cfg.platformdirs, "user_state_dir", lambda name: str(tmp_path / "legacy-none")
    )
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    assert StateDir.resolve().root == (tmp_path / "xdg" / "mihome-ctl")


def test_xdg_keeps_legacy_when_it_has_data(monkeypatch, tmp_path):
    # XDG set but its dir doesn't exist yet, while legacy already holds data → keep legacy.
    monkeypatch.delenv("MIHOME_CTL_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    monkeypatch.setattr(cfg.platformdirs, "user_state_dir", lambda name: str(legacy))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-absent"))
    assert StateDir.resolve().root == legacy


def test_paths():
    s = StateDir(Path("/x"))
    assert s.tokens_json.name == "mi-tokens.json"
    assert s.devices_md.name == "devices.md"
    assert s.session_json.name == "mi-session.json"
    assert s.ir_json.name == "mi-ir.json"
    assert s.ir_code_json("xm_1_199").name == "ir-code-xm_1_199.json"
