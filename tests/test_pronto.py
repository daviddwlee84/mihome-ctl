from mihome_ctl.core.pronto import timings_to_pronto


def test_golden_lead_pair():
    # freq word: round(1e6/(38000*0.241246)) = 109 = 0x6D
    # cycles: 9000µs->342=0x156, 4500µs->171=0xAB
    assert timings_to_pronto([9000, 4500], 38000) == "0000 006D 0001 0000 0156 00AB"


def test_odd_length_pads_with_one():
    assert timings_to_pronto([9000], 38000) == "0000 006D 0001 0000 0156 0001"


def test_min_cycle_is_one():
    out = timings_to_pronto([1, 1], 38000).split()
    assert out[4] == "0001" and out[5] == "0001"
