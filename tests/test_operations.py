from mihome_ctl.core.operations import filter_remotes

IR = {
    "a": {"name": "Living TV", "model": "miir.tv.x"},
    "b": {"name": "Bedroom AC", "model": "miir.aircondition.y"},
}


def test_filter_empty_returns_all():
    assert filter_remotes(IR, "") == IR


def test_filter_by_name():
    assert list(filter_remotes(IR, "tv")) == ["a"]


def test_filter_by_model():
    assert list(filter_remotes(IR, "aircondition")) == ["b"]


def test_filter_no_match():
    assert filter_remotes(IR, "zzz") == {}
