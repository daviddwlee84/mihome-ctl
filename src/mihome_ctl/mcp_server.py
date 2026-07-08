"""MCP server: wrap core.operations as MCP tools so Claude / an agent can control IR directly.

Requires ``mihome-ctl[mcp]``. Login is **non-interactive**: it only reuses the session
(``mi-session.json``) saved by a prior terminal ``mihome-ctl ir`` QR scan; with no valid
session a tool returns an error string and does **not** pop a QR on the server side.
Start with: ``mihome-ctl-mcp`` (stdio).
"""

from __future__ import annotations

import json

from .config import StateDir
from .connector import QrCodeXiaomiCloudConnector
from .core import operations as ops
from .core.miot import AC_MODES
from .session import connector_from_session

_NO_SESSION = "Not logged in or the session has expired. Run `mihome-ctl ir` once in a terminal (scan the QR), then use MCP."


def _conn(state: StateDir) -> QrCodeXiaomiCloudConnector | None:
    return connector_from_session(state)


def _load_ir(state: StateDir) -> dict | None:
    if not state.ir_json.exists():
        return None
    return json.loads(state.ir_json.read_text(encoding="utf-8"))


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as e:  # pragma: no cover
        raise SystemExit("[mihome-ctl] MCP server requires: pip install 'mihome-ctl[mcp]'") from e

    mcp = FastMCP("mihome-ctl")

    @mcp.tool()
    def list_remotes() -> str:
        """List cloud IR remotes (name/model/kind/key count). Data comes from the cache; run `mihome-ctl ir` first."""
        ir = _load_ir(StateDir.resolve())
        if ir is None:
            return "mi-ir.json not found; run `mihome-ctl ir` in a terminal first."
        return json.dumps(
            [
                {
                    "name": r.get("name"),
                    "model": r.get("model"),
                    "kind": r.get("kind"),
                    "keys": r.get("keys"),
                    "parent": r.get("parent_model"),
                }
                for r in ir.values()
            ],
            ensure_ascii=False,
        )

    @mcp.tool()
    def list_keys(remote: str) -> str:
        """List all key names for a remote (remote is a name/model substring)."""
        ir = _load_ir(StateDir.resolve())
        if ir is None:
            return "mi-ir.json not found; run `mihome-ctl ir` in a terminal first."
        tgt = ops.find_remote(ir, remote)
        if not tgt:
            return f"Remote '{remote}' not found. Available: " + ", ".join(
                r.get("name", "") for r in ir.values()
            )
        _did, r = tgt
        keys = ops.remote_keys(r)
        return json.dumps(
            [{"name": k.get("name"), "display_name": k.get("display_name")} for k in keys],
            ensure_ascii=False,
        )

    @mcp.tool()
    def ir_send(remote: str, key: str, repeat: int = 1) -> str:
        """Trigger a remote's key over the cloud (emitted via the parent blaster). remote/key both accept substrings."""
        state = StateDir.resolve()
        ir = _load_ir(state)
        if ir is None:
            return "mi-ir.json not found; run `mihome-ctl ir` in a terminal first."
        tgt = ops.find_remote(ir, remote)
        if not tgt:
            return f"Remote '{remote}' not found."
        did, r = tgt
        k = ops.find_key(ops.remote_keys(r), key)
        if not k:
            return f"Remote '{r.get('name')}' has no key matching '{key}'."
        conn = _conn(state)
        if conn is None:
            return _NO_SESSION
        res = ops.send_key(conn, did, r, k, repeat)
        return f"{'✅ Sent' if res.ok else '❌ Failed'}: {res.key_name} → {res.remote_name} (×{res.repeat})"

    @mcp.tool()
    def ir_ac(
        temp: int | None = None,
        mode: str | None = None,
        off: bool = False,
        status: bool = False,
        remote: str | None = None,
    ) -> str:
        """Absolute AC control: temp 16-30 / mode(auto|cool|dry|heat|fan) / off / status."""
        state = StateDir.resolve()
        ir = _load_ir(state)
        if ir is None:
            return "mi-ir.json not found; run `mihome-ctl ir` in a terminal first."
        matches = ops.ac_remotes(ir, remote)
        if not matches:
            return "No AC remote found (miir.aircondition.*)."
        if len(matches) > 1:
            return "Multiple AC remotes; specify one with remote: " + ", ".join(
                r["name"] for _, r in matches
            )
        did, r = matches[0]
        country = r.get("region", "cn")
        conn = _conn(state)
        if conn is None:
            return _NO_SESSION
        if status:
            return f"{r['name']} ac_state: {ops.ac_status(conn, did, country)}"
        if off:
            res = ops.ac_off(conn, did, country)
            return "✅ AC turned off" if res.ok else f"❌ {res.resp}"
        if temp is not None and not (16 <= temp <= 30):
            return "temp must be 16-30"
        mode_val = AC_MODES.get(mode.lower()) if mode else None
        if mode and mode_val is None:
            return "mode must be auto/cool/dry/heat/fan"
        p = ops.ac_set_props(conn, did, country, temp, mode_val)
        s = ops.ac_send_on(conn, did, country)
        return f"Set {(mode or '')} {temp if temp is not None else ''} → props={'✅' if p.ok else '❌'} send={'✅' if s.ok else '❌'}"

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
