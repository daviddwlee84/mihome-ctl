"""mihome-ctl — password-free QR login to the official Xiaomi cloud, extract
per-device miIO token / BLE key, and control cloud IR remotes (transmitted via
the parent blaster; no local hardware or Home Assistant needed).

Core logic lives in :mod:`mihome_ctl.core` (UI-agnostic, returns structured
data); the CLI (Tyro), MCP server, and future TUI are just thin presentation
layers.
"""

from __future__ import annotations

__version__ = "0.5.1"
