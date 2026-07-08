import mihome_ctl.core.haexport as hx
from mihome_ctl.core.haexport import plan_ha_export

# mac → 即時 IP，讓測試不真的呼叫 arp
FAKE_ARP = {
    "AA:BB:CC:00:00:01": "192.168.8.21",  # tw 燈，即時 IP == cloud → 非 stale
    "AA:BB:CC:00:00:02": "192.168.110.55",  # cn 掃地機，cloud 是 .99 → stale
    "AA:BB:CC:00:00:03": "192.168.31.77",  # cn 投影機，cloud 是 26.26.26.x 佔位 → ready
}

# token/beaconkey 用不會誤中任何 model/name 子字串的哨兵值
ROWS = [
    # tw WiFi + token，即時 IP 與 cloud 相同 → local_ready、非 stale
    {"name": "客廳燈", "model": "yeelink.light.ceiling22", "did": "1", "region": "tw",
     "localip": "192.168.8.21", "token": "SECRETTOK_ONE", "mac": "AA:BB:CC:00:00:01"},
    # cn WiFi + token，cloud 私有但即時 IP 變了 → stale
    {"name": "掃地機", "model": "dreame.vacuum.p2008", "did": "2", "region": "cn",
     "localip": "192.168.110.99", "token": "SECRETTOK_TWO", "mac": "AA:BB:CC:00:00:02"},
    # cn WiFi + token，cloud 是 26.26.26.x 佔位（非私有）；即時 IP 解到私有 → local_ready
    {"name": "投影機", "model": "fengmi.projector.m045j", "did": "3", "region": "cn",
     "localip": "26.26.26.1", "token": "SECRETTOK_THREE", "mac": "AA:BB:CC:00:00:03"},
    # IR 虛擬遙控 → 排除
    {"name": "電視", "model": "miir.tv.ir01", "did": "4", "region": "cn",
     "localip": "", "token": "", "mac": ""},
    # BLE（有 beaconkey）→ 排除
    {"name": "溫濕度計", "model": "miaomiaoce.sensor_ht.t1", "did": "blt.5.abc", "region": "cn",
     "localip": "", "token": "SECRETTOK_FIVE", "mac": "AA:BB:CC:00:00:05", "beaconkey": "SECRETBK_FIVE"},
    # WiFi 但無 token → 排除
    {"name": "牆壁開關", "model": "zimi.switch.dhkg02", "did": "6", "region": "cn",
     "localip": "", "token": "", "mac": "AA:BB:CC:00:00:06"},
    # cn WiFi + token 但 cloud 回公網 IP、ARP 查不到 → local_candidate 但非 ready（unreachable）
    {"name": "空調伴侶", "model": "lumi.acpartner.mcn02", "did": "7", "region": "cn",
     "localip": "153.34.17.9", "token": "SECRETTOK_SEVEN", "mac": "AA:BB:CC:00:00:07"},
]

SECRETS = ["SECRETTOK_ONE", "SECRETTOK_TWO", "SECRETTOK_THREE", "SECRETTOK_FIVE",
           "SECRETTOK_SEVEN", "SECRETBK_FIVE"]


def _run(monkeypatch):
    monkeypatch.setattr(hx, "arp_ip_for", lambda mac: FAKE_ARP.get(mac))
    return plan_ha_export(ROWS, resolve_live_ip=True)


def test_device_customizes_excludes_ir_ble_and_tokenless(monkeypatch):
    exp = _run(monkeypatch)
    yaml = exp.full_yaml()
    # 只該有 WiFi + token 的 model
    assert "yeelink.light.ceiling22" in yaml
    assert "dreame.vacuum.p2008" in yaml
    assert "fengmi.projector.m045j" in yaml
    assert "lumi.acpartner.mcn02" in yaml  # 即使無 LAN 路徑仍列入（al-one 拿到 IP 後可本地）
    # 排除項
    assert "miir.tv.ir01" not in yaml
    assert "miaomiaoce.sensor_ht" not in yaml
    assert "zimi.switch.dhkg02" not in yaml
    assert "miot_local: true" in yaml


def test_yaml_is_per_region(monkeypatch):
    exp = _run(monkeypatch)
    assert set(exp.regions) == {"tw", "cn"}
    # tw 區塊只含 tw 的 model，不含 cn 的
    tw_block = exp.yaml_by_region["tw"]
    assert "yeelink.light.ceiling22" in tw_block
    assert "dreame.vacuum.p2008" not in tw_block
    assert "region=tw" in tw_block


def test_subnet_grouping(monkeypatch):
    exp = _run(monkeypatch)
    subnets = {(reg, sub) for reg, sub, _ in exp.groups}
    assert ("tw", "192.168.8.0/24") in subnets
    assert ("cn", "192.168.110.0/24") in subnets
    assert ("cn", "192.168.31.0/24") in subnets  # 投影機經 ARP 解到 .31 網段
    # IR / BLE / 無 IP 者落在「無 LAN IP」桶
    assert ("cn", "(無 LAN IP / 公網或雲端)") in subnets


def test_stale_and_unreachable(monkeypatch):
    exp = _run(monkeypatch)
    stale_models = {d.model for d in exp.stale}
    assert "dreame.vacuum.p2008" in stale_models  # cloud .99 != 即時 .55
    assert "yeelink.light.ceiling22" not in stale_models  # 即時 == cloud
    unreachable_models = {d.model for d in exp.unreachable}
    assert "lumi.acpartner.mcn02" in unreachable_models  # 公網 IP、ARP 查不到


def test_no_token_plaintext_anywhere(monkeypatch):
    exp = _run(monkeypatch)
    blob = exp.full_yaml()
    for _reg, _sub, rows in exp.groups:
        for d in rows:
            blob += repr(d)
    for secret in SECRETS:
        assert secret not in blob
    # DeviceRow 結構上就沒有 token / beaconkey 欄
    field_names = set(exp.rows[0].__dataclass_fields__)
    assert "token" not in field_names
    assert "beaconkey" not in field_names
