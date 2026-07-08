"""MCP server：把 core.operations 包成 MCP tools，供 Claude / agent 直接控制 IR。

需要 ``mihome-ctl[mcp]``。登入採**非互動**：只沿用終端機先前 ``mihome-ctl ir`` 掃 QR
存下的 session（``mi-session.json``）；沒有有效 session 時 tool 回錯誤字串、**不**在
server 端彈 QR。啟動：``mihome-ctl-mcp``（stdio）。
"""

from __future__ import annotations

import json

from .config import StateDir
from .connector import QrCodeXiaomiCloudConnector
from .core import operations as ops
from .core.miot import AC_MODES
from .session import load_session

_NO_SESSION = "尚未登入或 session 過期。請先在終端機跑一次 `mihome-ctl ir`（掃 QR），再用 MCP。"


def _conn(state: StateDir) -> QrCodeXiaomiCloudConnector | None:
    sess = load_session(state)
    if not (sess and sess.get("serviceToken") and sess.get("ssecurity") and sess.get("userId")):
        return None
    c = QrCodeXiaomiCloudConnector()
    c.userId = sess["userId"]
    c._ssecurity = sess["ssecurity"]
    c._serviceToken = sess["serviceToken"]
    return c


def _load_ir(state: StateDir) -> dict | None:
    if not state.ir_json.exists():
        return None
    return json.loads(state.ir_json.read_text(encoding="utf-8"))


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as e:  # pragma: no cover
        raise SystemExit("[mihome-ctl] MCP server 需要：pip install 'mihome-ctl[mcp]'") from e

    mcp = FastMCP("mihome-ctl")

    @mcp.tool()
    def list_remotes() -> str:
        """列出雲端 IR 遙控（名稱/型號/類型/鍵數）。資料來自快取；先跑過 `mihome-ctl ir`。"""
        ir = _load_ir(StateDir.resolve())
        if ir is None:
            return "找不到 mi-ir.json；請先在終端機跑 `mihome-ctl ir`。"
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
        """列出某遙控的所有按鍵名稱（remote 為名稱/型號子字串）。"""
        ir = _load_ir(StateDir.resolve())
        if ir is None:
            return "找不到 mi-ir.json；請先在終端機跑 `mihome-ctl ir`。"
        tgt = ops.find_remote(ir, remote)
        if not tgt:
            return f"找不到遙控「{remote}」。可用：" + ", ".join(
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
        """雲端觸發某遙控的某鍵（經 parent blaster 發射）。remote/key 皆可子字串。"""
        state = StateDir.resolve()
        ir = _load_ir(state)
        if ir is None:
            return "找不到 mi-ir.json；請先在終端機跑 `mihome-ctl ir`。"
        tgt = ops.find_remote(ir, remote)
        if not tgt:
            return f"找不到遙控「{remote}」。"
        did, r = tgt
        k = ops.find_key(ops.remote_keys(r), key)
        if not k:
            return f"遙控「{r.get('name')}」沒有含「{key}」的鍵。"
        conn = _conn(state)
        if conn is None:
            return _NO_SESSION
        res = ops.send_key(conn, did, r, k, repeat)
        return f"{'✅ 已送出' if res.ok else '❌ 失敗'}：{res.key_name} → {res.remote_name}（×{res.repeat}）"

    @mcp.tool()
    def ir_ac(
        temp: int | None = None,
        mode: str | None = None,
        off: bool = False,
        status: bool = False,
        remote: str | None = None,
    ) -> str:
        """冷氣絕對控制：temp 16-30 / mode(auto|cool|dry|heat|fan) / off / status。"""
        state = StateDir.resolve()
        ir = _load_ir(state)
        if ir is None:
            return "找不到 mi-ir.json；請先在終端機跑 `mihome-ctl ir`。"
        matches = ops.ac_remotes(ir, remote)
        if not matches:
            return "找不到冷氣遙控（miir.aircondition.*）。"
        if len(matches) > 1:
            return "有多台冷氣遙控，請用 remote 指定：" + "、".join(r["name"] for _, r in matches)
        did, r = matches[0]
        country = r.get("region", "cn")
        conn = _conn(state)
        if conn is None:
            return _NO_SESSION
        if status:
            return f"{r['name']} ac_state：{ops.ac_status(conn, did, country)}"
        if off:
            res = ops.ac_off(conn, did, country)
            return "✅ 已關冷氣" if res.ok else f"❌ {res.resp}"
        if temp is not None and not (16 <= temp <= 30):
            return "temp 需 16-30"
        mode_val = AC_MODES.get(mode.lower()) if mode else None
        if mode and mode_val is None:
            return "mode 需為 auto/cool/dry/heat/fan"
        p = ops.ac_set_props(conn, did, country, temp, mode_val)
        s = ops.ac_send_on(conn, did, country)
        return f"設定 {(mode or '')} {temp if temp is not None else ''} → props={'✅' if p.ok else '❌'} send={'✅' if s.ok else '❌'}"

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
