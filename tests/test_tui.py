"""TUI tests — headless via Textual's Pilot, no network (ops are monkeypatched).

Skipped entirely when the ``[tui]`` extra (Textual) isn't installed. Driven with
``asyncio.run`` so the suite stays stdlib-only (no pytest-asyncio).
"""

import asyncio

import pytest

pytest.importorskip("textual")

import mihome_ctl.tui.app as tui_app  # noqa: E402
from mihome_ctl.config import StateDir  # noqa: E402
from mihome_ctl.core import operations as ops  # noqa: E402
from mihome_ctl.core.operations import AcResult, SendResult  # noqa: E402

FAKE_IR = {
    "did.tv": {
        "name": "Living TV",
        "model": "miir.tv.x",
        "region": "tw",
        "keys": 2,
        "kind": "brand-paired",
        "controller_id": 5,
        "parent_model": "spk",
        "raw_keys": {
            "result": {
                "keys": [
                    {"id": 1, "name": "POWER", "display_name": "Power"},
                    {"id": 2, "name": "VOL_UP", "display_name": "Vol+"},
                ]
            }
        },
    },
    "did.ac": {
        "name": "Bedroom AC",
        "model": "miir.aircondition.ac",
        "region": "tw",
        "keys": 0,
        "kind": "brand-paired",
        "raw_keys": {"result": {"keys": []}},
    },
}

FAKE_DEVICES = [
    {
        "name": "Plug",
        "model": "x.plug",
        "did": "did.plug",
        "region": "tw",
        "token": "t",
        "localip": "1.2.3.4",
    },
]


def test_device_get_cloud(monkeypatch):
    seen = {}

    def fake_get(conn, did, country, siid, piid):
        seen.update(did=did, country=country, siid=siid, piid=piid)
        return 1

    monkeypatch.setattr(ops, "miot_get", fake_get)
    monkeypatch.setattr(tui_app, "connector_from_session", lambda state: object())
    monkeypatch.setattr(tui_app.miotspec, "describe", lambda state, model: None)

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR, devices=FAKE_DEVICES)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one(tui_app.TabbedContent).active = "tab-dev"
            await pilot.pause()
            app.query_one("#devices", tui_app.DataTable).move_cursor(row=0)
            await pilot.pause()
            app.query_one("#dev-siid", tui_app.Input).value = "2"
            app.query_one("#dev-piid", tui_app.Input).value = "1"
            app.on_button_pressed(tui_app.Button.Pressed(app.query_one("#dev-get", tui_app.Button)))
            await app.workers.wait_for_complete()
            await pilot.pause()

    asyncio.run(scenario())
    assert seen == {"did": "did.plug", "country": "tw", "siid": 2, "piid": 1}


def _fake_spec():
    from mihome_ctl.core.miotspec import DeviceSpec, SpecAction, SpecProp

    return DeviceSpec(
        model="x.plug",
        urn="urn:x",
        props=[
            SpecProp(2, 1, "Switch", "On", "bool", ["read", "write"]),
            SpecProp(
                2,
                2,
                "Light",
                "Mode",
                "uint8",
                ["read", "write"],
                value_list=[
                    {"value": 0, "description": "Auto"},
                    {"value": 2, "description": "Night"},
                ],
            ),
            SpecProp(2, 3, "Light", "Bright", "uint8", ["read", "write"], value_range=[1, 100, 1]),
            SpecProp(3, 1, "Env", "Temp", "float", ["read"]),  # read-only
        ],
        actions=[SpecAction(4, 1, "Svc", "Do", in_=[6])],
    )


async def _open_device_panel(app, pilot):
    await pilot.pause()
    app.query_one(tui_app.TabbedContent).active = "tab-dev"
    await pilot.pause()
    app.query_one("#devices", tui_app.DataTable).move_cursor(row=0)
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


def test_device_panel_build(monkeypatch):
    monkeypatch.setattr(tui_app.miotspec, "describe", lambda state, model: _fake_spec())

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR, devices=FAKE_DEVICES)
        async with app.run_test() as pilot:
            await _open_device_panel(app, pilot)
            assert len(app.query(".dev-row")) == 5  # 4 props + 1 action
            app.query_one("#w_2_1", tui_app.Switch)  # writable bool → Switch
            app.query_one("#w_2_2", tui_app.Select)  # value-list → Select
            app.query_one("#w_2_3", tui_app.Input)  # writable range → Input
            assert not app.query("#w_3_1")  # read-only → no editor
            app.query_one("#pget_3_1", tui_app.Button)  # read-only still gets Get
            assert not app.query("#pset_3_1")  # …but no Set
            app.query_one("#acall_4_1", tui_app.Button)  # action → Call
            app.query_one("#ain_4_1", tui_app.Input)  # action with inputs → args box

    asyncio.run(scenario())


def test_device_panel_set(monkeypatch):
    seen = {}
    monkeypatch.setattr(tui_app.miotspec, "describe", lambda state, model: _fake_spec())
    monkeypatch.setattr(
        ops,
        "miot_set",
        lambda conn, did, country, siid, piid, value: (
            seen.update(siid=siid, piid=piid, value=value) or AcResult(True, "prop/set")
        ),
    )
    monkeypatch.setattr(tui_app, "connector_from_session", lambda state: object())

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR, devices=FAKE_DEVICES)
        async with app.run_test() as pilot:
            await _open_device_panel(app, pilot)
            app.query_one("#w_2_1", tui_app.Switch).value = True
            app.on_button_pressed(
                tui_app.Button.Pressed(app.query_one("#pset_2_1", tui_app.Button))
            )
            await app.workers.wait_for_complete()
            await pilot.pause()

    asyncio.run(scenario())
    assert seen == {"siid": 2, "piid": 1, "value": True}


def test_device_panel_refresh(monkeypatch):
    monkeypatch.setattr(tui_app.miotspec, "describe", lambda state, model: _fake_spec())
    monkeypatch.setattr(
        ops,
        "miot_get_many",
        lambda conn, did, country, items: {(2, 1): True, (2, 3): 60, (3, 1): 22},
    )
    monkeypatch.setattr(tui_app, "connector_from_session", lambda state: object())

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR, devices=FAKE_DEVICES)
        async with app.run_test() as pilot:
            await _open_device_panel(app, pilot)
            app.on_button_pressed(
                tui_app.Button.Pressed(app.query_one("#dev-refresh", tui_app.Button))
            )
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert str(app.query_one("#cur_3_1", tui_app.Label).render()) == "22"
            assert app.query_one("#w_2_1", tui_app.Switch).value is True
            assert app.query_one("#w_2_3", tui_app.Input).value == "60"

    asyncio.run(scenario())


def test_device_panel_enum_set(monkeypatch):
    seen = {}
    monkeypatch.setattr(tui_app.miotspec, "describe", lambda state, model: _fake_spec())
    monkeypatch.setattr(
        ops,
        "miot_set",
        lambda conn, did, country, siid, piid, value: (
            seen.update(siid=siid, piid=piid, value=value) or AcResult(True, "prop/set")
        ),
    )
    monkeypatch.setattr(tui_app, "connector_from_session", lambda state: object())

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR, devices=FAKE_DEVICES)
        async with app.run_test() as pilot:
            await _open_device_panel(app, pilot)
            app.query_one("#w_2_2", tui_app.Select).value = 2  # dropdown → typed int
            app.on_button_pressed(
                tui_app.Button.Pressed(app.query_one("#pset_2_2", tui_app.Button))
            )
            await app.workers.wait_for_complete()
            await pilot.pause()

    asyncio.run(scenario())
    assert seen == {"siid": 2, "piid": 2, "value": 2}


def test_device_panel_action_call(monkeypatch):
    seen = {}
    monkeypatch.setattr(tui_app.miotspec, "describe", lambda state, model: _fake_spec())
    monkeypatch.setattr(
        ops,
        "miot_call",
        lambda conn, did, country, siid, aiid, args: (
            seen.update(siid=siid, aiid=aiid, args=args) or AcResult(True, "action")
        ),
    )
    monkeypatch.setattr(tui_app, "connector_from_session", lambda state: object())

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR, devices=FAKE_DEVICES)
        async with app.run_test() as pilot:
            await _open_device_panel(app, pilot)
            app.query_one("#ain_4_1", tui_app.Input).value = "[7, 8]"  # parsed JSON args
            app.on_button_pressed(
                tui_app.Button.Pressed(app.query_one("#acall_4_1", tui_app.Button))
            )
            await app.workers.wait_for_complete()
            await pilot.pause()

    asyncio.run(scenario())
    assert seen == {"siid": 4, "aiid": 1, "args": [7, 8]}


def test_device_open_autoloads(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(tui_app.miotspec, "describe", lambda state, model: _fake_spec())

    def fake_many(conn, did, country, items):
        calls["n"] += 1
        return {(2, 1): True}

    monkeypatch.setattr(ops, "miot_get_many", fake_many)
    monkeypatch.setattr(tui_app, "connector_from_session", lambda state: object())

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR, devices=FAKE_DEVICES)
        async with app.run_test() as pilot:
            await _open_device_panel(app, pilot)
            app.query_one("#devices", tui_app.DataTable).focus()
            await pilot.pause()
            await pilot.press("enter")  # RowSelected → _refresh_current auto-load
            await app.workers.wait_for_complete()
            await pilot.pause()

    asyncio.run(scenario())
    assert calls["n"] >= 1  # opening a device fired a batched read


def test_stale_refresh_ignored(monkeypatch):
    monkeypatch.setattr(tui_app.miotspec, "describe", lambda state, model: _fake_spec())

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR, devices=FAKE_DEVICES)
        async with app.run_test() as pilot:
            await _open_device_panel(app, pilot)
            # a late response for a device we've navigated away from must not touch this panel
            app._apply_refresh({"did": "other", "name": "Other"}, {(2, 1): True})
            await pilot.pause()
            assert str(app.query_one("#cur_2_1", tui_app.Label).render()) == "—"
            assert app.query_one("#w_2_1", tui_app.Switch).value is False

    asyncio.run(scenario())


def test_select_remote_populates_keys():
    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#remotes", tui_app.DataTable).move_cursor(row=0)
            await pilot.pause()
            assert app.query_one("#keys", tui_app.OptionList).option_count == 2

    asyncio.run(scenario())


def test_enter_sends_selected_key(monkeypatch):
    calls = {}

    def fake_send(conn, did, r, k, repeat=1):
        calls.update(did=did, key=k["name"], repeat=repeat)
        return SendResult(True, k["name"], k.get("display_name", ""), r["name"], "", repeat)

    monkeypatch.setattr(ops, "send_key", fake_send)
    monkeypatch.setattr(tui_app, "connector_from_session", lambda state: object())

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#remotes", tui_app.DataTable).move_cursor(row=0)
            await pilot.pause()
            keys = app.query_one("#keys", tui_app.OptionList)
            keys.focus()
            keys.highlighted = 0
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()

    asyncio.run(scenario())
    assert calls == {"did": "did.tv", "key": "POWER", "repeat": 1}


def test_ac_on_calls_set_props_and_send(monkeypatch):
    from textual.widgets import Button

    seen = {}
    monkeypatch.setattr(
        ops,
        "ac_set_props",
        lambda c, d, co, t, m: seen.update(temp=t, mode_val=m) or AcResult(True, "set-props"),
    )
    monkeypatch.setattr(ops, "ac_send_on", lambda c, d, co: AcResult(True, "send/on"))
    monkeypatch.setattr(tui_app, "connector_from_session", lambda state: object())

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.on_button_pressed(Button.Pressed(app.query_one("#temp-up", Button)))  # 26 -> 27
            app.on_button_pressed(Button.Pressed(app.query_one("#ac-on", Button)))
            await app.workers.wait_for_complete()
            await pilot.pause()

    asyncio.run(scenario())
    assert seen == {"temp": 27, "mode_val": 1}  # default mode "cool" -> 1


def test_no_cached_remotes_shows_message_screen(tmp_path):
    async def scenario():
        app = tui_app.MihomeApp(ir=None, state=StateDir(tmp_path))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, tui_app.NoDataScreen)

    asyncio.run(scenario())
