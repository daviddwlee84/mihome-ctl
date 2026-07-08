"""mihome-ctl — 免密碼 QR 登入官方小米雲，抽 per-device miIO token / BLE key，
並控制雲端 IR 遙控（經 parent blaster 發射；免本地硬體或 Home Assistant）。

核心邏輯放在 :mod:`mihome_ctl.core`（UI 無關、回傳結構化資料），
CLI（Tyro）、MCP server、未來的 TUI 都只是薄呈現層。
"""

from __future__ import annotations

__version__ = "0.1.0"
