"""Pure presentation: render the device list as a Markdown table (for the CLI / devices.md)."""

from __future__ import annotations


def render_md(rows: list[dict], reveal: bool) -> str:
    """Device list → Markdown table. Masks the token when ``reveal=False``."""

    def tok(v: str) -> str:
        if not v:
            return ""
        return v if reveal else "…redacted…"

    lines = [
        "| Device | Model | Region | Local IP | token | MAC |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('name', '')} | `{r.get('model', '')}` | {r.get('region', '')} "
            f"| {r.get('localip', '')} | {tok(r.get('token', ''))} | {r.get('mac', '')} |"
        )
    return "\n".join(lines)
