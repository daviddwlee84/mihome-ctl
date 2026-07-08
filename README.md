# mihome-ctl

**免密碼 QR 登入官方小米雲**，抽每台裝置的 miIO **token**／本地 IP／BLE beaconkey，
並**控制雲端 IR 遙控**（TV / 冷氣 / 風扇 / DIY on-off）——經家裡的 parent blaster
（如小愛音箱）發射，**免本地硬體、免 Home Assistant**。

- 只連官方網域：`account.xiaomi.com` + `{region}.api.io.mi.com`
- 支援 `tw` / `sg` 伺服器（miiocli/micloud 的 locale 清單根本沒有 `tw`）
- 產出 per-device token + 本地 IP + BLE key（mijiaAPI 之類拿不到）
- 免密碼（走 QR）；機密輸出 chmod 600、放進 gitignore 的 state dir

> 這是 [PiotrMachowski/Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor)（MIT）
> 連線器的薄包裝 + 一層雲端 IR 控制。連線器已精簡 vendored 進 `mihome_ctl/connector.py`
> （見 `THIRD_PARTY_LICENSES/`）。

## 安裝

```bash
uv tool install mihome-ctl          # 或 pipx install mihome-ctl
# 或從原始碼：
uv sync && uv run mihome-ctl --help
```

選用 extras：

```bash
uv tool install 'mihome-ctl[verify]'   # verify：LAN 本地驗證（python-miio）
uv tool install 'mihome-ctl[mcp]'      # MCP server（給 Claude / agent）
```

## 用法

```bash
mihome-ctl extract               # QR 登入抽 token（預設掃 tw sg cn）
mihome-ctl extract --server tw sg   # 只掃指定區（注意：空白分隔，非重複旗標）
mihome-ctl list                  # 離線重印上次結果
mihome-ctl verify --did <DID>    # LAN 本地驗證某台（需 [verify]）

mihome-ctl ir                    # 列出雲端 miir.* 遙控 + parent blaster
mihome-ctl ir-send --remote <名稱> --key VOL+ [--repeat 3]
mihome-ctl ir-send --remote <名稱>            # 省略 --key → 列出可用鍵
mihome-ctl ir-ac --temp 26 --mode cool        # 冷氣絕對控制（狀態式）
mihome-ctl ir-ac --off | --status
mihome-ctl ir-code --matchid xm_1_199         # IRDB matchid → 每鍵 Pronto（見下）
```

第一次跑會在終端機畫出 QR（或開 `http://127.0.0.1:31415`），用**米家 App** 掃一次；
session 會快取在 state dir 的 `mi-session.json`，之後免重掃。`--relogin` 可強制重登。

## State dir（機密/快取放哪）

以下優先序解析（機密檔名沿用 `mi-tokens.json` / `mi-session.json` / `mi-ir.json` …）：

1. 環境變數 `MIHOME_CTL_HOME`
2. 從 cwd 往上找最近的 `./.secrets/`（方便在既有 repo 內當 submodule 用）
3. 退回 `platformdirs` 的 user state dir（獨立安裝）

所有機密以 `0600` 寫入。

## 架構（CLI / MCP / TUI 共用一個核心）

`mihome_ctl.core` 是 UI 無關的操作層（登入、雲端 API、IR 編解碼、operations），
**只做事、回傳結構化資料**。上層都是薄呈現：

- `mihome_ctl.commands` + `__main__` — **Tyro** CLI（本頁指令）
- `mihome_ctl.mcp_server` — **MCP** server（`mihome-ctl-mcp`，需 `[mcp]`）
- 未來 **TUI** 也只是同一個 core 的另一層呈現

## `ir-code` 與授權（重要）

`ir-code` 把小米 IRDB 的 `matchid` 解成 Pronto：`base64 → AES-128-ECB → gzip → 微秒時序 → Pronto`。
解碼是**原生 clean-room 實作**（依公開協議，`pycryptodome`），**本套件不含任何 AGPL 程式碼、
不 vendor、不在執行期下載 AGPL 工具**——維持乾淨的 MIT。

限制（誠實說明）：公開的 `{region}-urc.io.mi.com/controller/code/1` 端點目前需 Mi Home
app 簽章（未帶簽章回 `status:19`），因此「線上以 matchid 取碼」這條路徑無法在無簽章下
驗證，標為**實驗性**。解碼本身以自製 round-trip 測試驗證。若要用外部（如 AGPL 的
`ysard/mi_remote_database`）碼庫工具，請**自行安裝**、opt-in 呼叫，並自負其 AGPL 義務——
本套件刻意不依賴、不打包它（`core/ircodec/base.py` 的 `IRCodecBackend` 保留了外部後端的擴充點）。

## 開發

```bash
uv sync --extra verify --extra mcp
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

## License

MIT（見 `LICENSE`）。內含之 Xiaomi 連線器衍生自上游 MIT 專案，見 `THIRD_PARTY_LICENSES/`。
