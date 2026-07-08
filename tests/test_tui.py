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


def test_device_spec_picker(monkeypatch):
    from mihome_ctl.core.miotspec import DeviceSpec, SpecProp

    fake = DeviceSpec(
        model="x.plug",
        urn="urn:x",
        props=[
            SpecProp(
                siid=2,
                piid=1,
                service="Switch",
                name="Switch Status",
                format="bool",
                access=["read", "write"],
            )
        ],
        actions=[],
    )
    monkeypatch.setattr(tui_app.miotspec, "describe", lambda state, model: fake)

    async def scenario():
        app = tui_app.MihomeApp(ir=FAKE_IR, devices=FAKE_DEVICES)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one(tui_app.TabbedContent).active = "tab-dev"
            await pilot.pause()
            app.query_one("#devices", tui_app.DataTable).move_cursor(row=0)
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.query_one("#dev-props", tui_app.OptionList).option_count == 1
            app._pick_spec_option("p:2:1")
            assert app.query_one("#dev-siid", tui_app.Input).value == "2"
            assert app.query_one("#dev-piid", tui_app.Input).value == "1"

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
