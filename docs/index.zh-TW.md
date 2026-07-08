# mihome-ctl

免密碼 QR 登入**官方**小米雲，抽每台裝置的 miIO **token** / 本地 IP / BLE key，並
**控制雲端 IR 遙控**（TV / 冷氣 / 風扇 / DIY on-off）——經家裡的 parent blaster（如小
愛音箱）發射，**免本地硬體、免 Home Assistant**。

- 只連官方網域：`account.xiaomi.com` + `{region}.api.io.mi.com`
- 支援 `tw` / `sg`（`python-miio`/`micloud` 的 locale 清單沒有 `tw`）
- 產出 per-device token + 本地 IP + BLE key
- 免密碼（走 QR）；機密輸出 chmod 600

## 安裝與快速上手

```bash
uv tool install mihome-ctl          # 或 pipx install mihome-ctl
mihome-ctl extract                  # QR 登入抽 token（掃 tw sg cn）
mihome-ctl ir                       # 列出雲端 IR 遙控
mihome-ctl ir-send --remote <名稱> --key MUTE
mihome-ctl ir-ac --temp 26 --mode cool
```

## 內容

- [認證與 Token](auth-token.md)：怎麼拿到 token / QR 登入，各方法比較。
- [登入疑難排解](login-troubleshooting.md)：`Access denied`、locale 沒 `tw`、第三方 proxy 安全驗證。
- [本地 IR 控制](ir.md)：`miir.*` 雲端碼怎麼抽、DIY vs 品牌配對、Pronto、能不能本地重播。

原始碼與 issue：<https://github.com/daviddwlee84/mihome-ctl>
