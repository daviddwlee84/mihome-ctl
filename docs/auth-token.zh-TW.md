# 認證與 Token（前置需求）

不管你選哪種控制方式，第一步都是先**拿到認證**。米家有兩種認證：

| 認證 | 取得方式 | 適用控制路徑 | 受區域影響？ |
|---|---|---|---|
| 裝置 **token** | 從小米雲端拉取，或離線抽 App 備份 | 本地 miIO/LAN 直控 | ✅ 要對區 |
| 帳號 **QR 登入** | 掃碼登入小米帳號 | 雲端 API | ✅ 登入到對應區 |

!!! danger "token 是裝置機密"
    device token 等於該裝置的控制金鑰，**不要**提交進 git／貼到公開場合。`mihome-ctl`
    抽出來的 token 寫在 state dir（`0600`，見 [首頁](index.md) 的 state dir 說明），預設
    不進版控。

!!! warning "先看這個"
    - `miiocli cloud`（底層 `micloud`）現在**多半登入失敗**——小米在密碼流加了 captcha＋
      2FA，且 locale 清單**沒有 `tw`**，台灣帳號抓不到。詳見[登入疑難排解](login-troubleshooting.md)。
    - 走第三方 proxy 的 QR 工具（如 `mijiaAPI` / `miot-mcp`）會**把 session token 送到
      `api.mijia.tech`**，而且拿不到 local token——只適合純雲端控制。
    - **要 token 就用 `mihome-ctl`**（薄包
      [Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor)：
      免密碼 QR、只連官方、支援 tw/sg）。

## 推薦：`mihome-ctl`（官方 QR 抽 token）

免密碼 QR 登入**官方**小米雲，抽出每台 token + 本地 IP + BLE key：

```bash
mihome-ctl extract
#  → 終端機畫出 QR（或開 http://127.0.0.1:31415），用「米家 App」掃碼
#  → 掃完抓 tw sg cn 三區，寫到 state dir 的 mi-tokens.json (chmod 600) + devices.md
mihome-ctl list                # 離線重印（token 預設遮蔽，--show 顯示）
mihome-ctl verify --did <DID>  # 用 python-miio 本地驗證某台 token 可用（需 [verify]）
```

- 只連 `account.xiaomi.com` + `{region}.api.io.mi.com`（官方），**不經第三方**。
- 預設掃 `tw sg cn`；`--server tw sg` 可指定（注意：空白分隔，非重複旗標）。
- 拿到 token 後即可本地直控：`miiocli device --ip <IP> --token <TOKEN> info`。

## 其他方法

| 你要 | 用 |
|---|---|
| **local token 做 LAN 直控**（推薦） | `mihome-ctl`（官方 QR） |
| 純雲端控制、給 Claude、可接受第三方 proxy | `mijiaAPI` / `miot-mcp`（QR，走 `api.mijia.tech`） |
| 完全離線、有配對過的舊 Android | `miio-extract-tokens`（app-backup） |
| （歷史）`miiocli cloud` | 多半已壞，見[登入疑難排解](login-troubleshooting.md) |

深入的失敗原因、安全驗證、tw 區陷阱 → **[登入疑難排解](login-troubleshooting.md)**。
