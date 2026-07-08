"""Message screen shown when there is no cached ``mi-ir.json`` yet."""

from __future__ import annotations

from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Static


class NoDataScreen(Screen):
    BINDINGS = [("r", "app.reload", "Reload"), ("q", "app.quit", "Quit")]

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    def compose(self):
        with Middle(), Center():
            yield Static(
                f"No cached remotes found:\n  {self._path}\n\n"
                "Run `mihome-ctl ir` in a terminal first (scan the QR), then press r."
            )
