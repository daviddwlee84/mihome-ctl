from mihome_ctl.core.ircodec.native import decode_code, encode_code


def test_roundtrip_even():
    t = [9000, 4500, 560, 560, 560, 1690, 560, 39000]
    assert decode_code(encode_code(t)) == t


def test_roundtrip_odd_length():
    t = [1, 2, 3]
    assert decode_code(encode_code(t)) == t


def test_roundtrip_single():
    t = [12345]
    assert decode_code(encode_code(t)) == t
