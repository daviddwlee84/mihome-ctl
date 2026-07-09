from mihome_ctl.core import operations as ops
from mihome_ctl.core.miot import coerce_value
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


def test_coerce_value():
    assert coerce_value("26") == 26
    assert coerce_value("true") is True
    assert coerce_value("false") is False
    assert coerce_value("3.5") == 3.5
    assert coerce_value("[1, 2]") == [1, 2]
    assert coerce_value("cool") == "cool"
    assert coerce_value('"q"') == "q"


def test_find_device():
    rows = [{"did": "a", "name": "x"}, {"did": "b"}]
    assert ops.find_device(rows, "b") == {"did": "b"}
    assert ops.find_device(rows, "z") is None


def test_miot_get_payload(monkeypatch):
    cap = {}

    def fake_api(conn, country, path, payload):
        cap.update(country=country, path=path, payload=payload)
        return {"code": 0, "result": [{"did": "d", "siid": 2, "piid": 1, "value": 42}]}

    monkeypatch.setattr(ops, "api", fake_api)
    assert ops.miot_get(None, "d", "tw", 2, 1) == 42
    assert cap["path"] == "/miotspec/prop/get"
    assert cap["country"] == "tw"
    assert cap["payload"] == {"params": [{"did": "d", "siid": 2, "piid": 1}]}


def test_miot_set_payload(monkeypatch):
    cap = {}

    def fake_api(conn, country, path, payload):
        cap.update(path=path, payload=payload)
        return {"code": 0}

    monkeypatch.setattr(ops, "api", fake_api)
    r = ops.miot_set(None, "d", "tw", 2, 2, 26)
    assert r.ok
    assert cap["path"] == "/miotspec/prop/set"
    assert cap["payload"] == {"params": [{"did": "d", "siid": 2, "piid": 2, "value": 26}]}


def test_miot_call_payload(monkeypatch):
    cap = {}

    def fake_api(conn, country, path, payload):
        cap.update(path=path, payload=payload)
        return {"code": 0}

    monkeypatch.setattr(ops, "api", fake_api)
    r = ops.miot_call(None, "d", "cn", 2, 5, [1, 2])
    assert r.ok
    assert cap["path"] == "/miotspec/action"
    assert cap["payload"] == {"params": {"did": "d", "siid": 2, "aiid": 5, "in": [1, 2]}}


def test_miot_get_many_payload_and_mapping(monkeypatch):
    cap = {}

    def fake_api(conn, country, path, payload):
        cap.update(path=path, payload=payload)
        # results out of request order, plus one failing entry (code!=0) to be skipped
        return {
            "code": 0,
            "result": [
                {"did": "d", "siid": 3, "piid": 1, "value": 22},
                {"did": "d", "siid": 2, "piid": 1, "value": True},
                {"did": "d", "siid": 9, "piid": 9, "code": -1},
            ],
        }

    monkeypatch.setattr(ops, "api", fake_api)
    got = ops.miot_get_many(None, "d", "tw", [(2, 1), (3, 1), (9, 9)])
    assert cap["path"] == "/miotspec/prop/get"
    assert cap["payload"] == {
        "params": [
            {"did": "d", "siid": 2, "piid": 1},
            {"did": "d", "siid": 3, "piid": 1},
            {"did": "d", "siid": 9, "piid": 9},
        ]
    }
    assert got == {(2, 1): True, (3, 1): 22}  # keyed by result siid/piid; failing entry dropped


def test_miot_get_many_empty():
    assert ops.miot_get_many(None, "d", "tw", []) == {}
