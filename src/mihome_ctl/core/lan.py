"""LAN 小工具：MAC 正規化、以 ARP 反查某 MAC 的即時 IP。

雲端回的 ``localip`` 常過期，本地驗證前用 ARP 查現值較可靠。
"""

from __future__ import annotations

import re
import subprocess


def norm_mac(mac: str) -> str:
    """把各種 MAC 寫法正規化成大寫、補零、冒號分隔（``0A:0B:CC:01:02:FF``）。"""
    return ":".join(f"{int(p, 16):02X}" for p in mac.split(":"))


def arp_ip_for(mac: str) -> str | None:
    """查目前 LAN 上這個 MAC 的即時 IP；查不到回 ``None``。"""
    if not mac:
        return None
    try:
        target = norm_mac(mac)
    except ValueError:
        return None
    out = subprocess.run(["arp", "-an"], capture_output=True, text=True).stdout
    for ln in out.splitlines():
        if "incomplete" in ln:
            continue
        m = re.search(r"\(([\d.]+)\) at ([0-9a-fA-F:]+)", ln)
        if not m:
            continue
        try:
            if norm_mac(m.group(2)) == target:
                return m.group(1)
        except ValueError:
            continue
    return None
