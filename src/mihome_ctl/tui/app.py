"""Interactive Textual TUI (``mihome-ctl tui``). Requires ``mihome-ctl[tui]``.

Browses remotes/keys from the cached ``mi-ir.json`` and devices from
``mi-tokens.json`` (no cloud call to browse). Sending a key, controlling the A/C, or
a device MIoT get/set/action hits the cloud inside a worker thread, reusing the cached
QR session via :func:`connector_from_session` — it never pops a QR (run ``mihome-ctl ir``
first if there is no session). All ``core.operations`` calls go through the module
object so tests can monkeypatch them.
"""

from __future__ import annotations

import json

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Digits,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    RadioButton,
    RadioSet,
    RichLog,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from ..config import StateDir
from ..core import operations as ops
from ..core.miot import AC_MODES, coerce_value
from ..session import connector_from_session
from .screens import NoDataScreen

_NO_SESSION = (
    "Not logged in or the session expired — run `mihome-ctl ir` once in a terminal "
    "(scan the QR), then reopen the TUI."
)


class MihomeApp(App):
    TITLE = "mihome-ctl"
    CSS = """
    #remotes { width: 45%; }
    #keys { width: 55%; }
    #devices { height: 55%; }
    #dev-form Input { width: 14; }
    #log { height: 25%; border-top: solid $accent; }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "reload", "Reload"),
        Binding("slash", "search", "Search"),
        Binding("escape", "clear_search", "Clear filter", show=False),
    ]

    temp: reactive[int] = reactive(26)

    def __init__(
        self,
        ir: dict | None = None,
        state: StateDir | None = None,
        devices: list[dict] | None = None,
    ) -> None:
        super().__init__()
        self.state = state or StateDir.resolve()
        self._ir: dict | None = ir
        self._devices_arg = devices  # test injection
        self._devices: list[dict] = []
        self._cur_remote: tuple[str, dict] | None = None
        self._cur_device: dict | None = None
        self._ac: tuple[str, dict] | None = None

    # ------------------------------------------------------------------ layout
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="tab-remotes"):
            with TabPane("Remotes", id="tab-remotes"):
                yield Input(placeholder="filter remotes…", id="filter")
                with Horizontal():
                    yield DataTable(id="remotes", cursor_type="row", zebra_stripes=True)
                    yield OptionList(id="keys")
            with TabPane("Air-Con", id="tab-ac"):
                yield Label("(no AC remote)", id="ac-name")
                with Horizontal(id="ac-temp"):
                    yield Button("-", id="temp-down")
                    yield Digits("26", id="temp")
                    yield Button("+", id="temp-up")
                with RadioSet(id="mode"):
                    for m in AC_MODES:
                        yield RadioButton(m, value=(m == "cool"), id=f"mode-{m}")
                with Horizontal(id="ac-actions"):
                    yield Button("On", id="ac-on", variant="success")
                    yield Button("Off", id="ac-off", variant="error")
                    yield Button("Status", id="ac-status")
            with TabPane("Devices", id="tab-dev"):
                yield DataTable(id="devices", cursor_type="row", zebra_stripes=True)
                yield Label("(select a device)", id="dev-name")
                with Horizontal(id="dev-form"):
                    yield Input(placeholder="siid", id="dev-siid")
                    yield Input(placeholder="piid", id="dev-piid")
                    yield Input(placeholder="aiid", id="dev-aiid")
                    yield Input(placeholder="value / args", id="dev-value")
                    yield Checkbox("local", id="dev-local")
                with Horizontal(id="dev-actions"):
                    yield Button("Get", id="dev-get")
                    yield Button("Set", id="dev-set", variant="warning")
                    yield Button("Call", id="dev-call", variant="warning")
        yield RichLog(id="log", highlight=True, markup=True)
        yield Footer()

    # ------------------------------------------------------------------ data
    def on_mount(self) -> None:
        self.query_one("#remotes", DataTable).add_columns("name", "model", "keys", "kind")
        self.query_one("#devices", DataTable).add_columns("name", "model", "did")
        self._reload()
        self._reload_devices()
        self.query_one("#remotes", DataTable).focus()

    def _load_ir(self) -> dict | None:
        if self._ir is not None:
            return self._ir
        if not self.state.ir_json.exists():
            return None
        return json.loads(self.state.ir_json.read_text(encoding="utf-8"))

    def _current_devices(self) -> list[dict]:
        if self._devices_arg is not None:
            return self._devices_arg
        if not self.state.tokens_json.exists():
            return []
        try:
            return json.loads(self.state.tokens_json.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _reload(self, query: str = "") -> None:
        ir = self._load_ir()
        if ir is None:
            # No IR cache. Only take over the whole screen if there are no devices
            # either; otherwise leave the tabs usable (Devices still works).
            if not self._current_devices():
                if not isinstance(self.screen, NoDataScreen):
                    self.push_screen(NoDataScreen(str(self.state.ir_json)))
            else:
                self._log("No mi-ir.json (run `mihome-ctl ir`) — Remotes/Air-Con empty.")
            return
        if isinstance(self.screen, NoDataScreen):
            self.pop_screen()
        self._ir = ir
        table = self.query_one("#remotes", DataTable)
        table.clear()
        for did, r in ops.filter_remotes(ir, query).items():
            table.add_row(
                r.get("name", ""),
                r.get("model", ""),
                str(r.get("keys", 0)),
                r.get("kind", ""),
                key=did,  # RowKey.value == did → used directly in RowHighlighted
            )
        self._pick_ac_remote(ir)

    def _reload_devices(self) -> None:
        self._devices = self._current_devices()
        try:
            t = self.query_one("#devices", DataTable)
        except Exception:
            return
        t.clear()
        for d in self._devices:
            t.add_row(
                d.get("name", ""), d.get("model", ""), d.get("did", ""), key=str(d.get("did", ""))
            )

    def _pick_ac_remote(self, ir: dict) -> None:
        acs = ops.ac_remotes(ir, None)
        self._ac = acs[0] if acs else None
        label = self._ac[1].get("name", "") if self._ac else "(no AC remote)"
        try:
            self.query_one("#ac-name", Label).update(label)
        except Exception:
            pass

    # ------------------------------------------------------------------ search
    def action_reload(self) -> None:
        try:
            q = self.query_one("#filter", Input).value
        except Exception:
            q = ""
        self._reload(q)
        self._reload_devices()

    def action_search(self) -> None:
        self.query_one("#filter", Input).focus()

    def action_clear_search(self) -> None:
        self.query_one("#filter", Input).value = ""
        self._reload()

    def on_input_changed(self, message: Input.Changed) -> None:
        if message.input.id == "filter":
            self._reload(message.value)

    # ------------------------------------------------------------------ table selection
    def on_data_table_row_highlighted(self, message: DataTable.RowHighlighted) -> None:
        did = message.row_key.value
        if message.data_table.id == "remotes":
            if not self._ir or did not in self._ir:
                return
            r = self._ir[did]
            self._cur_remote = (did, r)
            keys = self.query_one("#keys", OptionList)
            keys.clear_options()
            for k in ops.remote_keys(r):
                label = f"{str(k.get('name', '')):<16} {k.get('display_name', '')}"
                keys.add_option(Option(label, id=str(k["id"])))
        elif message.data_table.id == "devices":
            dev = ops.find_device(self._devices, did)
            self._cur_device = dev
            if dev is not None:
                self.query_one("#dev-name", Label).update(
                    f"{dev.get('name', '')}  ({dev.get('model', '')})  region={dev.get('region', '')}"
                )

    def on_data_table_row_selected(self, message: DataTable.RowSelected) -> None:
        if message.data_table.id == "remotes":
            self.query_one("#keys", OptionList).focus()

    # ------------------------------------------------------------------ remotes → send key
    def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
        if self._cur_remote is None:
            return
        did, r = self._cur_remote
        k = next((x for x in ops.remote_keys(r) if str(x["id"]) == message.option_id), None)
        if k is not None:
            self._send_key(did, r, k, 1)

    @work(thread=True, group="cloud")
    def _send_key(self, did: str, r: dict, k: dict, repeat: int) -> None:
        conn = connector_from_session(self.state)
        if conn is None:
            self.call_from_thread(self._log, _NO_SESSION)
            return
        try:
            res = ops.send_key(conn, did, r, k, repeat)
        except Exception as e:  # noqa: BLE001 - report, never crash the UI
            self.call_from_thread(self._log, f"[red]error[/] {type(e).__name__}: {e}")
            return
        tag = "[green]OK Sent[/]" if res.ok else "[red]FAIL[/]"
        self.call_from_thread(
            self._log, f"{tag} {res.key_name} -> {res.remote_name} (x{res.repeat})"
        )

    # ------------------------------------------------------------------ buttons
    def watch_temp(self, _old: int, new: int) -> None:
        try:
            self.query_one("#temp", Digits).update(str(new))
        except Exception:
            pass

    def _selected_mode(self) -> str:
        rs = self.query_one("#mode", RadioSet)
        btn = rs.pressed_button
        if btn is not None and btn.id:
            return btn.id.removeprefix("mode-")
        return "cool"

    def on_button_pressed(self, message: Button.Pressed) -> None:
        bid = message.button.id
        if bid == "temp-up":
            self.temp = min(30, self.temp + 1)
            return
        if bid == "temp-down":
            self.temp = max(16, self.temp - 1)
            return
        if bid in ("dev-get", "dev-set", "dev-call"):
            self._device_action(bid)
            return
        if self._ac is None:
            self._log("No AC remote (miir.aircondition.*).")
            return
        did, r = self._ac
        country = r.get("region", "cn")
        if bid == "ac-on":
            self._ac_apply(did, country, self.temp, self._selected_mode())
        elif bid == "ac-off":
            self._ac_off(did, country)
        elif bid == "ac-status":
            self._ac_status(did, country)

    @work(thread=True, group="cloud")
    def _ac_apply(self, did: str, country: str, temp: int, mode: str) -> None:
        conn = connector_from_session(self.state)
        if conn is None:
            self.call_from_thread(self._log, _NO_SESSION)
            return
        p = ops.ac_set_props(conn, did, country, temp, AC_MODES.get(mode))
        s = ops.ac_send_on(conn, did, country)
        self.call_from_thread(
            self._log,
            f"set {mode} {temp}C -> props {'OK' if p.ok else 'FAIL'}; send {'OK' if s.ok else 'FAIL'}",
        )

    @work(thread=True, group="cloud")
    def _ac_off(self, did: str, country: str) -> None:
        conn = connector_from_session(self.state)
        if conn is None:
            self.call_from_thread(self._log, _NO_SESSION)
            return
        res = ops.ac_off(conn, did, country)
        self.call_from_thread(self._log, "OK AC off" if res.ok else f"FAIL {res.resp}")

    @work(thread=True, group="cloud")
    def _ac_status(self, did: str, country: str) -> None:
        conn = connector_from_session(self.state)
        if conn is None:
            self.call_from_thread(self._log, _NO_SESSION)
            return
        st = ops.ac_status(conn, did, country)
        self.call_from_thread(self._log, f"ac_state: {st}")

    # ------------------------------------------------------------------ devices → MIoT
    def _int_input(self, wid: str) -> int | None:
        try:
            return int(self.query_one(wid, Input).value.strip())
        except (ValueError, AttributeError):
            return None

    def _device_action(self, bid: str) -> None:
        dev = self._cur_device
        if dev is None:
            self._log("Select a device first.")
            return
        local = self.query_one("#dev-local", Checkbox).value
        siid = self._int_input("#dev-siid")
        if siid is None:
            self._log("siid is required (integer).")
            return
        if bid == "dev-get":
            piid = self._int_input("#dev-piid")
            if piid is None:
                self._log("piid is required for Get.")
                return
            self._dev_get(dev, siid, piid, local)
        elif bid == "dev-set":
            piid = self._int_input("#dev-piid")
            if piid is None:
                self._log("piid is required for Set.")
                return
            value = coerce_value(self.query_one("#dev-value", Input).value)
            self._dev_set(dev, siid, piid, value, local)
        elif bid == "dev-call":
            aiid = self._int_input("#dev-aiid")
            if aiid is None:
                self._log("aiid is required for Call.")
                return
            args = coerce_value(self.query_one("#dev-value", Input).value or "[]")
            if not isinstance(args, list):
                args = [args]
            self._dev_call(dev, siid, aiid, args, local)

    def _cloud_conn(self):
        conn = connector_from_session(self.state)
        if conn is None:
            self.call_from_thread(self._log, _NO_SESSION)
        return conn

    @work(thread=True, group="cloud")
    def _dev_get(self, dev: dict, siid: int, piid: int, local: bool) -> None:
        try:
            if local:
                val = ops.local_get(dev, siid, piid)
            else:
                conn = self._cloud_conn()
                if conn is None:
                    return
                val = ops.miot_get(conn, dev["did"], dev.get("region", "cn"), siid, piid)
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self._log, f"[red]error[/] {type(e).__name__}: {e}")
            return
        self.call_from_thread(self._log, f"{dev.get('name', '')} siid={siid} piid={piid} = {val}")

    @work(thread=True, group="cloud")
    def _dev_set(self, dev: dict, siid: int, piid: int, value, local: bool) -> None:
        try:
            if local:
                res = ops.local_set(dev, siid, piid, value)
                ok, detail = True, str(res)
            else:
                conn = self._cloud_conn()
                if conn is None:
                    return
                r = ops.miot_set(conn, dev["did"], dev.get("region", "cn"), siid, piid, value)
                ok, detail = r.ok, ("" if r.ok else str(r.resp))
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self._log, f"[red]error[/] {type(e).__name__}: {e}")
            return
        tag = "[green]OK set[/]" if ok else "[red]FAIL[/]"
        self.call_from_thread(
            self._log, f"{tag} {dev.get('name', '')} siid={siid} piid={piid} = {value!r} {detail}"
        )

    @work(thread=True, group="cloud")
    def _dev_call(self, dev: dict, siid: int, aiid: int, args: list, local: bool) -> None:
        try:
            if local:
                res = ops.local_call(dev, siid, aiid, args)
                ok, detail = True, str(res)
            else:
                conn = self._cloud_conn()
                if conn is None:
                    return
                r = ops.miot_call(conn, dev["did"], dev.get("region", "cn"), siid, aiid, args)
                ok, detail = r.ok, ("" if r.ok else str(r.resp))
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self._log, f"[red]error[/] {type(e).__name__}: {e}")
            return
        tag = "[green]OK action[/]" if ok else "[red]FAIL[/]"
        self.call_from_thread(
            self._log, f"{tag} {dev.get('name', '')} siid={siid} aiid={aiid} in={args} {detail}"
        )

    def _log(self, msg: str) -> None:
        self.query_one("#log", RichLog).write(msg)


def run_tui(state: StateDir | None = None) -> int:
    MihomeApp(state=state).run()
    return 0


def main() -> None:
    raise SystemExit(run_tui())
