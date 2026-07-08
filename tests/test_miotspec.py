import mihome_ctl.core.miotspec as ms
from mihome_ctl.config import StateDir


class _Resp:
    def __init__(self, data):
        self._d = data

    def json(self):
        return self._d


CATALOG = {
    "instances": [
        {"model": "x.plug", "type": "urn:v2", "version": 2, "status": "released"},
        {"model": "x.plug", "type": "urn:v1", "version": 1, "status": "released"},
    ]
}
INSTANCE = {
    "services": [
        {
            "iid": 2,
            "description": "Switch",
            "type": "urn:miot-spec-v2:service:switch:x",
            "properties": [
                {
                    "iid": 1,
                    "description": "Switch Status",
                    "format": "bool",
                    "access": ["read", "write"],
                },
                {
                    "iid": 3,
                    "description": "Brightness",
                    "format": "uint8",
                    "access": ["read", "write"],
                    "value-range": [1, 100, 1],
                },
            ],
            "actions": [{"iid": 1, "description": "toggle", "in": []}],
        }
    ]
}


def test_urn_describe_and_cache(monkeypatch, tmp_path):
    calls = {"n": 0}

    def fake_get(url, **kw):
        calls["n"] += 1
        return _Resp(CATALOG if "instances" in url else INSTANCE)

    monkeypatch.setattr(ms.requests, "get", fake_get)
    state = StateDir(tmp_path)

    assert ms.urn_for_model(state, "x.plug") == "urn:v2"  # highest version
    d = ms.describe(state, "x.plug")
    assert d is not None and d.model == "x.plug"
    names = [(p.siid, p.piid, p.name) for p in d.props]
    assert (2, 1, "Switch Status") in names
    br = next(p for p in d.props if p.piid == 3)
    assert br.value_range == [1, 100, 1]
    assert ms.access_flags(br) == "RW"
    assert ms.prop_constraint(br) == "1..100"
    assert [(a.siid, a.aiid, a.name) for a in d.actions] == [(2, 1, "toggle")]

    n_before = calls["n"]
    ms.describe(state, "x.plug")  # served entirely from disk cache
    assert calls["n"] == n_before


def test_describe_unknown_model(monkeypatch, tmp_path):
    monkeypatch.setattr(ms.requests, "get", lambda url, **kw: _Resp({"instances": []}))
    assert ms.describe(StateDir(tmp_path), "no.such.model") is None
