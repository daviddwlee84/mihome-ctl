# Auth & Token (prerequisite)

Whichever control method you choose, the first step is always to **obtain
authentication**. Mi Home has two kinds of authentication:

| Authentication | How to get it | Applicable control path | Region-dependent? |
|---|---|---|---|
| Device **token** | Pulled from the Xiaomi cloud, or extracted offline from an App backup | Local miIO/LAN direct control | ✅ must match region |
| Account **QR login** | Scan to log in to your Xiaomi account | Cloud API | ✅ log in to the matching region |

!!! danger "The token is a device secret"
    The device token is effectively the control key for that device — **do not** commit it
    into git or paste it anywhere public. The tokens extracted by `mihome-ctl` are written to
    the state dir (`0600`, see the state dir notes on the [Home](index.md) page) and are not
    version-controlled by default.

!!! warning "Read this first"
    - `miiocli cloud` (backed by `micloud`) now **fails to log in most of the time** — Xiaomi
      added captcha + 2FA to the password flow, and the locale list has **no `tw`**, so Taiwan
      accounts return nothing. See [Login troubleshooting](login-troubleshooting.md) for details.
    - QR tools that go through a third-party proxy (such as `mijiaAPI` / `miot-mcp`) will **send
      your session token to `api.mijia.tech`**, and can't obtain the local token — they only suit
      pure cloud control.
    - **If you need the token, use `mihome-ctl`** (a thin wrapper around
      [Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor):
      password-free QR, official-only, supports tw/sg).

## Recommended: `mihome-ctl` (official QR token extraction)

Password-free QR login to the **official** Xiaomi cloud, extracting each device's token +
local IP + BLE key:

```bash
mihome-ctl extract
#  → draws a QR in the terminal (or open http://127.0.0.1:31415); scan it with the "Mi Home App"
#  → after scanning, fetches all three regions tw sg cn, writes mi-tokens.json (chmod 600) + devices.md to the state dir
mihome-ctl list                # reprint offline (token masked by default, --show to reveal)
mihome-ctl verify --did <DID>  # locally verify a device token with python-miio (needs [verify])
```

- Connects only to `account.xiaomi.com` + `{region}.api.io.mi.com` (official), **never through a third party**.
- Scans `tw sg cn` by default; `--server tw sg` lets you specify (note: space-separated, not a repeated flag).
- Once you have the token you can control locally right away: `miiocli device --ip <IP> --token <TOKEN> info`.

## Other methods

| What you want | Use |
|---|---|
| **Local token for LAN direct control** (recommended) | `mihome-ctl` (official QR) |
| Pure cloud control, feeding Claude, willing to accept a third-party proxy | `mijiaAPI` / `miot-mcp` (QR, via `api.mijia.tech`) |
| Fully offline, an old Android that has already paired | `miio-extract-tokens` (app-backup) |
| (historical) `miiocli cloud` | Mostly broken, see [Login troubleshooting](login-troubleshooting.md) |

For an in-depth look at failure causes, security review, and tw-region traps → **[Login troubleshooting](login-troubleshooting.md)**.
