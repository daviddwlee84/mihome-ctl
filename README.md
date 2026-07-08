# mihome-ctl

Passwordless **QR login to the *official* Xiaomi cloud** — extract every device's
miIO **token** / local IP / BLE beacon-key, and **control cloud IR remotes**
(TV / air-conditioner / fan / DIY on-off) through your home's parent blaster
(e.g. a Xiao AI speaker). **No local hardware, no Home Assistant required.**

- Talks only to official hosts: `account.xiaomi.com` + `{region}.api.io.mi.com`
- Supports the `tw` / `sg` regions (python-miio / micloud have no `tw` locale)
- Produces per-device token + local IP + BLE key
- Passwordless (QR); secrets written with `chmod 600`

[![CI](https://github.com/daviddwlee84/mihome-ctl/actions/workflows/ci.yml/badge.svg)](https://github.com/daviddwlee84/mihome-ctl/actions/workflows/ci.yml)
&nbsp;·&nbsp; Docs: **https://daviddwlee84.github.io/mihome-ctl/** &nbsp;·&nbsp; 中文說明見文件站

> A thin wrapper over the [Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor)
> connector (MIT, vendored + trimmed into `mihome_ctl/connector.py`, see
> `THIRD_PARTY_LICENSES/`) plus a cloud-IR control layer.

## Install

```bash
uv tool install mihome-ctl          # or: pipx install mihome-ctl
# From source:
uv sync && uv run mihome-ctl --help
```

Optional extras:

```bash
uv tool install 'mihome-ctl[verify]'   # verify: LAN token check (python-miio)
uv tool install 'mihome-ctl[mcp]'      # MCP server (for Claude / agents)
```

## Usage

```bash
mihome-ctl extract               # QR login, extract tokens (scans tw sg cn)
mihome-ctl extract --server tw sg   # specific regions (space-separated, not repeated flags)
mihome-ctl list                  # reprint last result offline
mihome-ctl verify --did <DID>    # LAN-verify one device (needs [verify])

mihome-ctl ir                    # list cloud miir.* remotes + parent blaster
mihome-ctl ir-send --remote <name> --key VOL+ [--repeat 3]
mihome-ctl ir-send --remote <name>            # omit --key to list a remote's keys
mihome-ctl ir-ac --temp 26 --mode cool        # absolute A/C control (state-based)
mihome-ctl ir-ac --off | --status
mihome-ctl ir-code --matchid xm_1_199         # IRDB matchid → per-key Pronto (see notes)
```

On first run a QR is drawn in the terminal (or open `http://127.0.0.1:31415`) — scan
once with the **Mi Home app**; the session is cached in the state dir's
`mi-session.json`, so subsequent runs skip the scan. Use `--relogin` to force a re-login.

## State directory

Resolved in this order (secret filenames: `mi-tokens.json` / `mi-session.json` /
`mi-ir.json` / `devices.md`):

1. `MIHOME_CTL_HOME` environment variable
2. the nearest `./.secrets/` walking up from the cwd (convenient when embedded as a
   submodule inside another repo)
3. otherwise `platformdirs` user state dir

All secrets are written with mode `0600`.

## Architecture — one core, many front-ends

`mihome_ctl.core` is a UI-agnostic layer (connector, cloud API, IR codec,
operations) that **only does work and returns structured data**. Everything on top
is a thin presentation layer:

- `mihome_ctl.commands` + `__main__` — the **Tyro** CLI (commands above)
- `mihome_ctl.mcp_server` — an **MCP** server (`mihome-ctl-mcp`, needs `[mcp]`)
- a future **TUI** would be one more presentation layer over the same core

## `ir-code` and licensing (important)

`ir-code` decodes a Xiaomi IRDB `matchid` into Pronto:
`base64 → AES-128-ECB → gzip → microsecond timings → Pronto`. The decoder is a
**clean-room implementation** (from the public protocol, using `pycryptodome`), so
this package contains **no AGPL code**, vendors nothing AGPL, and downloads no AGPL
tool at runtime — it stays cleanly MIT.

Limitation (stated honestly): the public `{region}-urc.io.mi.com/controller/code/1`
endpoint currently requires a Mi Home app signature (anonymous requests return
`status:19`), so fetching codes online by `matchid` is **experimental**. The decoder
itself is verified by a round-trip test. To use an external IRDB tool (e.g. the
AGPL-licensed `ysard/mi_remote_database`), install it yourself and opt in — this
package deliberately does not depend on or bundle it (`core/ircodec/base.py` keeps an
`IRCodecBackend` extension point for an external backend).

## Development

```bash
uv sync --extra verify --extra mcp
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

## License

MIT (see `LICENSE`). The bundled Xiaomi connector derives from an upstream MIT
project — see `THIRD_PARTY_LICENSES/`.
