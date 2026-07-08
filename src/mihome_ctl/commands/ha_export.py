"""``ha-export`` — 從已抽的 token 產生 Home Assistant（al-one）設定。

輸出：每個 region 一份 ``xiaomi_miot.device_customizes``（強制本地）＋分網段裝置清單
＋stale-IP / 無 LAN 路徑建議。**不含 token 明碼**（al-one 本地 token 由雲端登入自帶）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import StateDir, write_secret
from ..core.haexport import DeviceRow, HaExport, plan_ha_export


def _status(d: DeviceRow) -> str:
    if d.is_ir:
        return "☁️ IR(雲端)"
    if d.is_ble:
        return "☁️ BLE"
    if not d.has_token:
        return "☁️ 無token"
    if d.local_ready:
        return "✅ 本地"
    return "⚠️ 需固定IP"


def _render(exp: HaExport) -> str:
    out: list[str] = []
    out.append("# ============ device_customizes（貼進各家 HA）============\n")
    out.append(exp.full_yaml())

    out.append("\n\n# ============ 分區 × 分網段裝置清單 ============")
    for region, subnet, rows in exp.groups:
        out.append(f"\n## region={region}  subnet={subnet}  （{len(rows)} 台）")
        out.append("| 裝置 | model | cloud IP | 即時IP(ARP) | 本地 |")
        out.append("|---|---|---|---|---|")
        for d in rows:
            out.append(
                f"| {d.name} | `{d.model}` | {d.cloud_ip or '-'} | {d.live_ip or '-'} | {_status(d)} |"
            )

    if exp.stale:
        out.append("\n\n# ============ 建議：cloud IP 已過期（做 DHCP 靜態綁定）============")
        for d in exp.stale:
            out.append(f"- {d.name}（`{d.model}`）cloud={d.cloud_ip} → 即時={d.live_ip}")

    if exp.unreachable:
        out.append("\n\n# ============ 想本地但目前無 LAN 路徑 ============")
        out.append("# （在該家 LAN／HA 主機上重跑 `ha-export` 才會用 ARP 解到它們的即時 IP；")
        out.append("#   公網 IP 或 26.26.26.x 佔位表示雲端未回真實 LAN IP → 需 DHCP 綁定或手填 host/token）")
        for d in exp.unreachable:
            out.append(f"- {d.name}（`{d.model}`, region={d.region}）cloud IP={d.cloud_ip or '無'}")

    return "\n".join(out)


def ha_export(out: Path | None = None, region: str | None = None, no_arp: bool = False) -> int:
    """產生 HA 的 device_customizes(miot_local) + 分網段清單（不印 token 明碼）。"""
    state = StateDir.resolve()
    path = state.tokens_json
    if not path.exists():
        print(f"[mihome-ctl] 找不到 {path}，請先跑 extract", file=sys.stderr)
        return 1
    rows = json.loads(path.read_text(encoding="utf-8"))
    if region:
        rows = [r for r in rows if r.get("region") == region]
        if not rows:
            print(f"[mihome-ctl] region={region} 沒有裝置", file=sys.stderr)
            return 1

    exp = plan_ha_export(rows, resolve_live_ip=not no_arp)
    report = _render(exp)
    print(report)

    if out:
        write_secret(out, report + "\n")
        print(f"\n[mihome-ctl] 已寫入 {out}", file=sys.stderr)
    return 0
