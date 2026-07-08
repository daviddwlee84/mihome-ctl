"""HA 匯出：把 ``mi-tokens.json`` 轉成 Home Assistant（al-one/hass-xiaomi-miot）設定。

UI 無關、可測、不 print。產出：

* 每個 region 一份 ``xiaomi_miot.device_customizes`` YAML 區塊（強制 ``miot_local``），
  只含 **WiFi + 有 token** 的裝置（自動排除 ``miir.*`` 虛擬遙控、BLE、無 token）。
* 分 region × 分網段（/24）的裝置清單，含即時 IP（ARP 反查）。
* 「stale IP / 無 LAN 路徑」建議。

安全：本模組**永不**把 token 明碼放進任何回傳結構（``DeviceRow`` 根本沒有 token 欄，
只有 ``has_token: bool``），YAML 也不含 token（al-one 本地模式的 token 由雲端登入自動帶入）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .lan import arp_ip_for

# RFC1918 私有網段（只有這些才可能被 HA 本地直連）
_PRIVATE = re.compile(r"^(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)")
_IPV4 = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")


def _is_private(ip: str) -> bool:
    return bool(ip) and bool(_PRIVATE.match(ip))


def _subnet(ip: str) -> str:
    """取 /24；非 IPv4 或空字串回 ``""``。"""
    m = _IPV4.match(ip or "")
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}.0/24" if m else ""


@dataclass
class DeviceRow:
    """單一裝置的 HA 視角摘要（**無 token 明碼**）。"""

    name: str
    model: str
    did: str
    region: str
    cloud_ip: str
    live_ip: str  # ARP 反查（只在與本機同 LAN 時才查得到）
    subnet: str  # 最佳可用 IP 的 /24；無則 ""
    has_token: bool
    is_ir: bool  # miir.* 虛擬遙控
    is_ble: bool  # BLE（beaconkey / did 含 blt）
    local_candidate: bool  # WiFi + 有 token + 非 IR/BLE → 可放進 device_customizes
    local_ready: bool  # local_candidate 且目前有私有 LAN IP → 現在就能本地直連
    stale: bool  # cloud 私有 IP 與即時 IP 不符 → 建議 DHCP 綁定


@dataclass
class HaExport:
    rows: list[DeviceRow]
    regions: list[str]
    yaml_by_region: dict[str, str] = field(default_factory=dict)
    # (region, subnet) → rows，依 region、subnet 排序
    groups: list[tuple[str, str, list[DeviceRow]]] = field(default_factory=list)
    stale: list[DeviceRow] = field(default_factory=list)  # 私有 IP 但即時 IP 變了
    unreachable: list[DeviceRow] = field(default_factory=list)  # 想本地卻無 LAN 路徑

    def full_yaml(self) -> str:
        """把各 region 的 device_customizes 區塊串起來。"""
        return "\n\n".join(self.yaml_by_region[r] for r in self.regions if r in self.yaml_by_region)


def _classify(row: dict, resolve_live_ip: bool) -> DeviceRow:
    model = row.get("model", "")
    did = row.get("did", "")
    cloud_ip = row.get("localip") or ""
    has_token = bool(row.get("token"))
    is_ir = model.startswith("miir")
    is_ble = bool(row.get("beaconkey")) or "blt" in did.lower()

    live_ip = arp_ip_for(row.get("mac", "")) if resolve_live_ip else ""
    best_ip = live_ip or cloud_ip
    local_candidate = has_token and not is_ir and not is_ble
    local_ready = local_candidate and _is_private(best_ip)
    stale = bool(has_token and _is_private(cloud_ip) and live_ip and live_ip != cloud_ip)

    return DeviceRow(
        name=row.get("name", ""),
        model=model,
        did=did,
        region=row.get("region", ""),
        cloud_ip=cloud_ip,
        live_ip=live_ip,
        subnet=_subnet(best_ip),
        has_token=has_token,
        is_ir=is_ir,
        is_ble=is_ble,
        local_candidate=local_candidate,
        local_ready=local_ready,
        stale=stale,
    )


def _yaml_block(region: str, models: list[str]) -> str:
    """單一 region 的 device_customizes 區塊（手刻字串，零 YAML 相依）。"""
    head = (
        f"# ==== region={region} → 貼進該家 HA 的 configuration.yaml ====\n"
        "xiaomi_miot:\n"
        "  device_customizes:"
    )
    if not models:
        return head + "\n    # （此區沒有可本地控的 WiFi 裝置）"
    body = "\n".join(f"    '{m}':\n      miot_local: true" for m in models)
    return f"{head}\n{body}"


def plan_ha_export(rows: list[dict], resolve_live_ip: bool = True) -> HaExport:
    """``mi-tokens.json`` 的 list → HaExport（YAML 區塊 + 分網段清單 + 建議）。"""
    devices = [_classify(r, resolve_live_ip) for r in rows]
    regions = sorted({d.region for d in devices})

    # 每 region 一份 device_customizes（去重 model、排序，維持一家一台的乾淨對應）
    yaml_by_region: dict[str, str] = {}
    for reg in regions:
        models = sorted({d.model for d in devices if d.region == reg and d.local_candidate})
        yaml_by_region[reg] = _yaml_block(reg, models)

    # 分 region × 分網段；無 LAN IP 者歸到 "(無 LAN IP / 公網或雲端)"
    NO_LAN = "(無 LAN IP / 公網或雲端)"
    buckets: dict[tuple[str, str], list[DeviceRow]] = {}
    for d in devices:
        key = (d.region, d.subnet or NO_LAN)
        buckets.setdefault(key, []).append(d)
    groups = [
        (reg, sub, sorted(buckets[(reg, sub)], key=lambda x: (x.model, x.name)))
        for reg, sub in sorted(buckets, key=lambda k: (k[0], k[1] == NO_LAN, k[1]))
    ]

    stale = [d for d in devices if d.stale]
    unreachable = [d for d in devices if d.local_candidate and not d.local_ready]

    return HaExport(
        rows=devices,
        regions=regions,
        yaml_by_region=yaml_by_region,
        groups=groups,
        stale=stale,
        unreachable=unreachable,
    )
