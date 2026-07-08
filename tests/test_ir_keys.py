from mihome_ctl.core.cloudapi import keys_have_code


def test_keys_with_code():
    assert keys_have_code({"result": {"keys": [{"code": "x"}]}}) == (1, True)


def test_list_without_code():
    assert keys_have_code({"result": {"list": [{"name": "a"}]}}) == (1, False)


def test_ir_code_field():
    assert keys_have_code({"result": {"keys": [{"ir_code": "y"}, {"name": "n"}]}}) == (2, True)


def test_empty_and_none():
    assert keys_have_code(None) == (0, False)
    assert keys_have_code({}) == (0, False)
