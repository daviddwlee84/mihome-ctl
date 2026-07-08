from mihome_ctl.core.miot import AC_MODES, miot_ok


def test_ac_modes():
    assert AC_MODES == {"auto": 0, "cool": 1, "dry": 2, "heat": 3, "fan": 4}


def test_miot_ok_simple():
    assert miot_ok({"code": 0}) is True
    assert miot_ok({"code": -1}) is False
    assert miot_ok(None) is False
    assert miot_ok("nope") is False


def test_miot_ok_list_result():
    assert miot_ok({"code": 0, "result": [{"code": 0}, {"code": 0}]}) is True
    assert miot_ok({"code": 0, "result": [{"code": 0}, {"code": -704}]}) is False
