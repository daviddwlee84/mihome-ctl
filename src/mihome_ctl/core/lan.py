"""LAN helpers: MAC normalization, ARP lookup of a MAC's current IP.

The ``localip`` returned by the cloud is often stale; an ARP lookup of the
current value before local verification is more reliable.
"""

from __future__ import annotations

import re
import subprocess


def norm_mac(mac: str) -> str:
    """Normalize any MAC notation to uppercase, zero-padded, colon-separated (``0A:0B:CC:01:02:FF``)."""
    return ":".join(f"{int(p, 16):02X}" for p in mac.split(":"))


def arp_ip_for(mac: str) -> str | None:
    """Look up this MAC's current IP on the LAN; return ``None`` if not found."""
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
