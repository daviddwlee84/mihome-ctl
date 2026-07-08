# 本地 IR 控制（含把 `miir.*` 雲端碼抽回本地）

米家 App 有「學習遙控器 → 記下某顆按鍵 → 之後重播」的功能。這件事**可以完全本地做**
（`python-miio` 直打 miIO，不經雲端）——前提是 IR blaster 的**型號對**、且碼的**格式對得
上**。這頁回答核心問題：**能不能把雲端 `miir.*` 裡錄好的碼抽出來、自己重播？**

!!! info "先講結論"
    - **能抽**：帳號裡的 `miir.*` 遙控可透過官方雲 API 讀出（`{region}.api.io.mi.com/app/v2/irdevice/...`）。
    - **DIY 學習的鍵**：raw code 存在帳號上 → 可直接重播。**品牌配對的遙控**：只存參照，
      真碼在小米碼庫、是 **AES-ECB+gzip 加密 → 微秒時序 → Pronto**，且只有 `chuangmi.ir.v2` 能播。
    - **格式綁 blaster**：chuangmi base64 ≠ acpartner `FE` ≠ pronto，不能互換。`lumi.acpartner.v2`
      只能重播「在 acpartner 上學的」碼；抽出來的 TV/chuangmi 碼它送不了。

## 哪些設備能本地噴 IR

| 型號 | `python-miio` 類別 | 本地 learn/play？ | 備註 |
|---|---|---|---|
| `chuangmi.ir.v2` / `chuangmi.remote.v2`（萬能遙控器） | `ChuangmiIr` | ✅ `learn`/`read`/`play`/`play_pronto` 完整 | **任意碼最乾淨** |
| `lumi.acpartner.v2`（空調伴侶） | `AirConditioningCompanion` | ✅ `learn`/`send_ir_code`（**FE 格式**） | 冷氣最佳；可學 TV/風扇，但碼是 acpartner 專屬 |
| `lumi.acpartner.mcn02` | `AirConditioningCompanionMcn02` | ❌ 只有 on/off/status/send_command | 本地**學不了** IR |
| `xiaomi.wifispeaker.*`（帶 IR 的小愛音箱） | `WifiSpeaker` | ❌ 無任何本地 IR 方法 | 有 IR 硬體但 `WifiSpeaker` 無本地 IR API → **只能雲端** |

!!! warning "「叫小愛用 IR 開電視」是雲端技能，不是本地"
    就算是帶 IR 的小愛，`python-miio` 的 `WifiSpeaker` 類別**沒有任何 IR 方法**——它的 IR
    完全靠小米雲/語音場景驅動。**沒有任何一款小愛音箱能當本地 IR 發射器。**要本地就用
    `chuangmi.ir.v2` 或 `acpartner.v2`。

## Path 1：把雲端 `miir.*` 的碼抽出來

`miir.tv.ir01`、`miir.aircondition.ir02`、`miir.fan.ir01`… 沒 token、沒 `localip`，因為它們
不是實體裝置，而是米家在真實 blaster 上疊的「家電定義」。但**錄好的碼可以透過官方雲 API
抽出來**，用 `mihome-ctl` 已經有的 `serviceToken`/`ssecurity` 簽名呼叫。

### 端點（POST，官方 `api.io.mi.com`，非第三方）

| 端點 | 參數 | 用途 |
|---|---|---|
| `/v2/irdevice/controllers` | `{parent_id}` | 列出某實體 blaster 底下的虛擬遙控 |
| `/v2/irdevice/controller/keys` | `{did}` | 列出某遙控的**按鍵**（DIY 的話含 `code`） |
| `/v2/irdevice/controller/info` | `{did}` | 遙控資訊，含品牌配對的 `controller_id`（matchid） |
| `/v2/irdevice/controller/key/click` | `{did, key_id}` | **雲端**觸發一顆鍵（今天就能動） |

決定「能不能本地重播」的關鍵是每個 `miir.*` 的 **`parent_id`**（哪顆實體 blaster 生的），
它決定碼的格式：

| 情況 | 碼格式 | 本地重播 |
|---|---|---|
| DIY 學習、parent = chuangmi blaster/小愛 | chuangmi base64（magic `0xA567`） | ✅ `chuangmi.ir.v2` `play('raw:…')` |
| DIY 學習、parent = acpartner | `FE…` frame | ✅ 同一顆 `acpartner.v2` 用 `send_ir_code` 重播 |
| **品牌配對** | 碼庫加密：base64 → AES-ECB(`fd7e915003168929c1a9b0ec32a60788`) → gzip → 微秒時序 → **Pronto** | ✅ 只有 `chuangmi.ir.v2` `play('pronto:…')` |

### 用 `mihome-ctl ir` 查你的遙控

```bash
mihome-ctl ir   # 登入 QR 直接畫在終端機（掃不到再開 :31415），掃一次後 session 快取
```

會列出每個 `miir.*` 的 **parent blaster**、鍵數、以及 **DIY(自學) vs 品牌配對(matchid)**，
原始 keys/info 寫進 state dir 的 `mi-ir.json`。

!!! note "常見結論"
    帶 IR 的小愛音箱底下常掛一批 `miir.*`（TV／冷氣／風扇＋幾個 DIY 自學），但**小愛音箱
    沒有本地 IR API**，所以這批**沒有一個能經 speaker 本地重播**。要本地控電視，最實際 =
    加一顆 `chuangmi.ir.v2`，再用 SmartIR 選碼庫或重學。

### 現在就能用：雲端觸發 `ir-send`（免硬體）

不必等買 blaster——`/v2/irdevice/controller/key/click` 讓雲端叫 parent blaster 發射，
**DIY / 品牌配對都行**：

```bash
mihome-ctl ir-send --remote <TV 名稱> --key VOL+
mihome-ctl ir-send --remote <風扇名稱> --key POWER --repeat 2
mihome-ctl ir-send --remote <TV 名稱>          # 省略 --key → 列出全部按鍵
```

缺點：走雲端（依賴網路＋小米）、且要 speaker 在家電 IR 射程內。但**零硬體、可腳本化 /
給 Claude**。

!!! note "「設音量到 30」——電視做不到，冷氣可以"
    IR 電視是**無狀態、單向、無回饋**——只有 `VOL+`/`VOL-`，沒有絕對「設到 30」。但**冷氣是
    狀態式的**（`ac_state`），可絕對設定。

### 冷氣絕對控制 `ir-ac`（走 MIoT-spec）

```bash
mihome-ctl ir-ac --status                # 讀目前 ac_state
mihome-ctl ir-ac --temp 26 --mode cool   # 設 26°C 制冷並開機
mihome-ctl ir-ac --off                   # 關機
```

走 `/miotspec/prop/set`（ir-mode `siid2/piid1`：auto/cool/dry/heat/fan＝0–4；ir-temperature
`siid2/piid2`：16–30）＋ `/miotspec/action`（開 aiid6 / 關 aiid5）。

### `ir-code`：把 IRDB matchid 解成 Pronto（本地重播用）

```bash
mihome-ctl ir-code --matchid xm_1_199
```

抓碼庫 → AES-ECB/gzip 解 → 每顆鍵輸出 **Pronto**（可餵給 `chuangmi.ir.v2` 的 `play_pronto`）。
解碼為原生 clean-room 實作（無 AGPL 依賴）。

!!! warning "線上取碼目前需 app 簽章"
    公開的 `{region}-urc.io.mi.com/controller/code/1` 端點目前對匿名請求回 `status:19`
    （需 Mi Home app 簽章），故「線上以 matchid 取碼」標為實驗性；解碼本身以自製 round-trip
    測試驗證。另外，帳號的 `controller_id`（品牌配對遙控的 ID）**不是**公開 IRDB 的 matchid，
    不能直接拿來查——要本地電視碼，最實際是 SmartIR 或在 `chuangmi.ir.v2` 上重學。

> 參考：[`al-one/hass-xiaomi-miot`](https://github.com/al-one/hass-xiaomi-miot) 的 `remote.py`、
> [`MiEcosystem/miot-plugin-sdk`](https://github.com/MiEcosystem/miot-plugin-sdk) 的 `ircontroller.js`（官方 API）。

## Path 2：直接在本地重學（不抽取，最單純）

拿原廠遙控對著可本地控的 blaster 學一次：

```python
from miio import ChuangmiIr
d = ChuangmiIr("<BLASTER_IP>", "<TOKEN>")
d.learn(1); print(d.read(1))    # armed slot 1 → 對著按遙控 → 得 base64 code
d.play("<BASE64_CODE>")         # 重播（也吃 'pronto:HEX'）
```

先用 [`mihome-ctl verify`](auth-token.md) 確認 blaster 的 token + 即時 IP（cloud 的
`localip` 常過期，工具會自動 ARP-by-MAC 解）。

## Path 3：Home Assistant `remote` + SmartIR（最佳 UX）

把萬能遙控器用 `xiaomi_miio` 的 `remote` 平台（host+token 直打 LAN）加進 HA，支援
`chuangmi.ir.v2`/`chuangmi.remote.v2`；再用
[SmartIR](https://github.com/litinoveweedle/SmartIR) 依電視型號長出完整 `media_player`。

!!! warning "SmartIR 的 Xiaomi = 萬能遙控器 remote 實體"
    SmartIR 的 Xiaomi 控制器**特指** `xiaomi_miio` 的 **ChuangmiIr `remote` 實體**——**不能**
    驅動 `lumi.acpartner`、也不能驅動音箱。
