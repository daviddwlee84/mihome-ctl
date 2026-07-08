"""``tui`` — interactive terminal UI to browse remotes and send keys / control the A/C."""

from __future__ import annotations

import sys

from ..config import StateDir


def tui() -> int:
    """Launch the interactive terminal UI (requires `pip install 'mihome-ctl[tui]'`)."""
    try:
        from ..tui.app import run_tui
    except ModuleNotFoundError as e:
        if e.name and e.name.split(".")[0] == "textual":
            print(
                "[mihome-ctl] The TUI needs Textual: pip install 'mihome-ctl[tui]'",
                file=sys.stderr,
            )
            return 1
        raise
    state = StateDir.resolve()
    if not state.ir_json.exists():
        # Still launch — the app shows a message screen with a reload hint.
        print(f"[mihome-ctl] {state.ir_json} missing — run `mihome-ctl ir` first.", file=sys.stderr)
    return run_tui(state)
