import sys

from mihome_ctl import __main__, __version__


def test_version_flag(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["mihome-ctl", "--version"])
    __main__.main()
    assert __version__ in capsys.readouterr().out


def test_version_short_flag(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["mihome-ctl", "-V"])
    __main__.main()
    assert __version__ in capsys.readouterr().out
