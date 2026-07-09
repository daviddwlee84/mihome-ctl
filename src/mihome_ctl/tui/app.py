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
from textual.containers import Horizontal, VerticalScroll
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
    Select,
    Switch,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option
from textual.widgets.select import InvalidSelectValueError

from ..config import StateDir
from ..core import miotspec
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
    #devices { height: 30%; }
    #dev-panel { height: 40%; border: round $primary-darken-2; }
    .dev-row { height: auto; }
    .dev-row .pname { width: 30; content-align: left middle; }
    .dev-row .pcur { width: 12; color: $text-muted; content-align: left middle; }
    .dev-row Input { width: 18; }
    .dev-row Select { width: 24; }
    #dev-form Input { width: 14; }
    #log { height: 20%; border-top: solid $accent; }
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
                with Horizontal(id="dev-head"):
                    yield Label("(select a device)", id="dev-name")
                    yield Button("Refresh values", id="dev-refresh")
                    yield Checkbox("local", id="dev-local")
                yield VerticalScroll(id="dev-panel")
                with Horizontal(id="dev-form"):
                    yield Input(placeholder="siid", id="dev-siid")
                    yield Input(placeholder="piid", id="dev-piid")
                    yield Input(placeholder="aiid", id="dev-aiid")
                    yield Input(placeholder="value / args", id="dev-value")
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
                if self.query_one(TabbedContent).active == "tab-dev":
                    self._resolve_spec(dev)

    def on_tabbed_content_tab_activated(self, event) -> None:
        if self.query_one(TabbedContent).active == "tab-dev" and self._cur_device is not None:
            self._resolve_spec(self._cur_device)

    def on_data_table_row_selected(self, message: DataTable.RowSelected) -> None:
        if message.data_table.id == "remotes":
            self.query_one("#keys", OptionList).focus()
        elif message.data_table.id == "devices":
            self._refresh_current()  # opening a device auto-loads its current values

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
        if bid == "dev-refresh":
            self._refresh_current()
            return
        if bid and (bid.startswith("pget_") or bid.startswith("pset_") or bid.startswith("acall_")):
            self._panel_button(bid)
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
        except (Exception, SystemExit) as e:  # noqa: BLE001 - incl. SystemExit from local ops
            self.call_from_thread(self._log, f"[red]error[/] {type(e).__name__}: {e}")
            return
        self.call_from_thread(self._dev_get_done, dev, siid, piid, val)

    def _dev_get_done(self, dev: dict, siid: int, piid: int, val) -> None:
        if self._stale(dev):
            return
        self._set_cur(siid, piid, str(val))
        self._sync_widget(siid, piid, val)
        self._log(f"{dev.get('name', '')} siid={siid} piid={piid} = {val}")

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
        except (Exception, SystemExit) as e:  # noqa: BLE001 - incl. SystemExit from local ops
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
        except (Exception, SystemExit) as e:  # noqa: BLE001 - incl. SystemExit from local ops
            self.call_from_thread(self._log, f"[red]error[/] {type(e).__name__}: {e}")
            return
        tag = "[green]OK action[/]" if ok else "[red]FAIL[/]"
        self.call_from_thread(
            self._log, f"{tag} {dev.get('name', '')} siid={siid} aiid={aiid} in={args} {detail}"
        )

    # ------------------------------------------------------------------ device MIoT-spec panel
    @work(thread=True, group="spec", exclusive=True)
    def _resolve_spec(self, dev: dict) -> None:
        model = dev.get("model", "")
        try:
            spec = miotspec.describe(self.state, model)
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self._build_panel, None, model, f"{type(e).__name__}: {e}")
            return
        self.call_from_thread(self._build_panel, spec, model, None)

    async def _build_panel(self, spec, model: str, err) -> None:
        """Rebuild the per-property widget rows for the selected device (runs on the UI thread)."""
        cur = self._cur_device
        if cur is None or model != cur.get("model", ""):
            return  # device changed while resolving; a newer _build_panel will win
        panel = self.query_one("#dev-panel", VerticalScroll)
        rows: list = []
        if err:
            rows.append(Label(f"spec error: {err}", classes="dev-row"))
        elif spec is None:
            rows.append(
                Label(f"no MIoT spec for {model} — use the manual form below", classes="dev-row")
            )
        else:
            rows.extend(self._prop_row(p) for p in spec.props)
            rows.extend(self._action_row(a) for a in spec.actions)
            if not rows:
                rows.append(Label(f"spec for {model} has no properties/actions", classes="dev-row"))
        # batch() takes the widget lock so overlapping device switches serialize (no DuplicateIds).
        async with panel.batch():
            await panel.remove_children()
            await panel.mount(*rows)

    def _prop_row(self, p) -> Horizontal:
        children: list = [
            Label(f"{p.service} · {p.name}", classes="pname"),
            Label("—", id=f"cur_{p.siid}_{p.piid}", classes="pcur"),
        ]
        writable = miotspec.is_writable(p)
        if writable:
            children.append(self._editor_for(p))
        if miotspec.is_readable(p):
            children.append(Button("Get", id=f"pget_{p.siid}_{p.piid}"))
        if writable:
            children.append(Button("Set", id=f"pset_{p.siid}_{p.piid}", variant="warning"))
        return Horizontal(*children, id=f"row_p_{p.siid}_{p.piid}", classes="dev-row")

    def _editor_for(self, p):
        wid = f"w_{p.siid}_{p.piid}"
        kind = miotspec.widget_kind(p)
        if kind == "bool":
            return Switch(id=wid)
        if kind == "enum":
            return Select(miotspec.enum_options(p), allow_blank=True, id=wid)
        if kind == "range":
            rng = miotspec.range_spec(p) or (0, 0, 1)
            itype = "integer" if (p.format or "").startswith(("int", "uint")) else "number"
            return Input(type=itype, placeholder=f"{rng[0]}..{rng[1]}", id=wid)
        return Input(placeholder=p.format or "value", id=wid)

    def _action_row(self, a) -> Horizontal:
        children: list = [Label(f"{a.service} · {a.name}", classes="pname")]
        if a.in_:
            children.append(Input(placeholder="JSON args", id=f"ain_{a.siid}_{a.aiid}"))
        children.append(Button("Call", id=f"acall_{a.siid}_{a.aiid}", variant="warning"))
        return Horizontal(*children, id=f"row_a_{a.siid}_{a.aiid}", classes="dev-row")

    # ------------------------------------------------------------------ panel: refresh / row buttons
    def _refresh_current(self) -> None:
        dev = self._cur_device
        if dev is None:
            self._log("Select a device first.")
            return
        local = self.query_one("#dev-local", Checkbox).value
        self._dev_refresh(dev, local)

    def _panel_button(self, bid: str) -> None:
        dev = self._cur_device
        if dev is None:
            self._log("Select a device first.")
            return
        local = self.query_one("#dev-local", Checkbox).value
        parts = bid.split("_")
        try:
            kind, a, b = parts[0], int(parts[1]), int(parts[2])
        except (IndexError, ValueError):
            return
        if kind == "pget":
            self._dev_get(dev, a, b, local)
        elif kind == "pset":
            value, ok = self._read_widget_value(a, b)
            if not ok:
                self._log(f"no value entered for siid={a} piid={b}")
                return
            self._dev_set(dev, a, b, value, local)
        elif kind == "acall":
            self._dev_call(dev, a, b, self._read_action_args(a, b), local)

    def _read_widget_value(self, siid: int, piid: int):
        """Read a property's editing widget (main thread). Returns ``(value, ok)``."""
        try:
            w = self.query_one(f"#w_{siid}_{piid}")
        except Exception:
            return None, False
        if isinstance(w, Switch):
            return w.value, True
        if isinstance(w, Select):
            if w.value is Select.NULL:
                return None, False
            return w.value, True
        if isinstance(w, Input):
            if w.value == "":
                return None, False
            return coerce_value(w.value), True
        return None, False

    def _read_action_args(self, siid: int, aiid: int) -> list:
        try:
            raw = self.query_one(f"#ain_{siid}_{aiid}", Input).value
        except Exception:
            return []
        if not raw.strip():
            return []
        args = coerce_value(raw)
        return args if isinstance(args, list) else [args]

    def _stale(self, dev: dict) -> bool:
        """True if `dev` is no longer the selected device (a late worker result to discard)."""
        cur = self._cur_device
        return cur is None or dev.get("did") != cur.get("did")

    def _set_cur(self, siid: int, piid: int, text: str) -> None:
        try:
            self.query_one(f"#cur_{siid}_{piid}", Label).update(text)
        except Exception:
            pass

    def _sync_widget(self, siid: int, piid: int, val) -> None:
        """Reflect a freshly-read value into the row's editing widget, if any."""
        try:
            w = self.query_one(f"#w_{siid}_{piid}")
        except Exception:
            return
        if isinstance(w, Switch):
            w.value = bool(val)
        elif isinstance(w, Select):
            try:
                w.value = val
            except InvalidSelectValueError:
                w.clear()
        elif isinstance(w, Input):
            w.value = "" if val is None else str(val)

    @work(thread=True, group="cloud")
    def _dev_refresh(self, dev: dict, local: bool) -> None:
        model = dev.get("model", "")
        try:
            spec = miotspec.describe(self.state, model)
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self._log, f"[red]spec error[/] {type(e).__name__}: {e}")
            return
        if spec is None:
            self.call_from_thread(self._log, f"no MIoT spec for {model} — nothing to refresh")
            return
        readable = [(p.siid, p.piid) for p in spec.props if miotspec.is_readable(p)]
        if not readable:
            self.call_from_thread(self._log, "no readable properties")
            return
        got: dict = {}
        try:
            if local:
                for s, pi in readable:
                    try:
                        got[(s, pi)] = ops.local_get(dev, s, pi)
                    except SystemExit as e:  # device-wide: no token/IP or python-miio missing
                        self.call_from_thread(self._log, f"[red]local[/] {e}")
                        break
                    except Exception as e:  # noqa: BLE001 - one prop failing shouldn't stop the rest
                        self.call_from_thread(self._log, f"[red]{s}/{pi} {type(e).__name__}: {e}")
            else:
                conn = self._cloud_conn()
                if conn is None:
                    return
                got = ops.miot_get_many(conn, dev["did"], dev.get("region", "cn"), readable)
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self._log, f"[red]error[/] {type(e).__name__}: {e}")
            return
        self.call_from_thread(self._apply_refresh, dev, got)

    def _apply_refresh(self, dev: dict, got: dict) -> None:
        if self._stale(dev):
            return  # a late response for a device we've since navigated away from
        for (s, pi), val in got.items():
            self._set_cur(s, pi, str(val))
            self._sync_widget(s, pi, val)
        self._log(f"[green]refreshed[/] {dev.get('name', '')} ({len(got)} values)")

    def _log(self, msg: str) -> None:
        self.query_one("#log", RichLog).write(msg)


def run_tui(state: StateDir | None = None) -> int:
    MihomeApp(state=state).run()
    return 0


def main() -> None:
    raise SystemExit(run_tui())
