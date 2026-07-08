import pytest

from mihome_ctl.core.lan import norm_mac


def test_normalizes_and_uppercases():
    assert norm_mac("a:b:cc:1:02:ff") == "0A:0B:CC:01:02:FF"


def test_already_normal():
    assert norm_mac("AA:BB:CC:DD:EE:F0") == "AA:BB:CC:DD:EE:F0"


def test_malformed_raises():
    with pytest.raises(ValueError):
        norm_mac("zz:zz")
