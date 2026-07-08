"""純呈現：把裝置列表渲染成 Markdown 表格（CLI / devices.md 用）。"""

from __future__ import annotations


def render_md(rows: list[dict], reveal: bool) -> str:
    """裝置列表 → Markdown 表格。``reveal=False`` 時遮蔽 token。"""

    def tok(v: str) -> str:
        if not v:
            return ""
        return v if reveal else "…redacted…"

    lines = [
        "| 裝置 | 型號 (model) | 區 | 本地 IP | token | MAC |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('name', '')} | `{r.get('model', '')}` | {r.get('region', '')} "
            f"| {r.get('localip', '')} | {tok(r.get('token', ''))} | {r.get('mac', '')} |"
        )
    return "\n".join(lines)
