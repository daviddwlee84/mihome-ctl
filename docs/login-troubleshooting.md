# Login troubleshooting

Xiaomi login is the step in the whole flow most likely to get you stuck. This page lays out
the pitfalls observed in practice, their root causes, and the fixes all in one place, plus a
**security review** (which tools connect only to the official servers, and how passwords are
handled).

## `miiocli cloud` returns `Access denied` (`MiCloudAccessDenied`)

Under the hood `python-miio` uses [`micloud`](https://pypi.org/project/micloud/) (barely
updated since 2022), which does a username/password POST to
`account.xiaomi.com/pass/serviceLoginAuth2`. Xiaomi later added **captcha + email/phone 2FA**
to this endpoint for non-App clients, and an unattended credential POST can't get past it, so
it gets blocked as `Access denied`. Home Assistant's "Xiaomi Miio" cloud flow hits the same wall.

| Symptom | Root cause | Fix |
|---|---|---|
| `miiocli cloud` returns `Access denied` | Password flow blocked by captcha/2FA | Switch to QR (`mihome-ctl`) |
| HA Xiaomi Miio cloud login fails | Inherits the same wall | Same as above, or extract the token with `mihome-ctl` and fill it in manually |
| Correct credentials still blocked | **Network layer**: Cloudflare DNS, AdGuard/PiHole, router region restrictions | Switch to a non-Cloudflare DNS, disable ad filtering, don't block `api.io.mi.com` |
| Hitting the 2FA limit | About 3–5 verification emails per region per day (remember to check spam) | Wait, or switch to QR (not subject to this limit) |

!!! note "This isn't a backdoor — the flow just can't be automated headlessly"
    It has been verified that `micloud` and the extractor connect only to Xiaomi's official
    domains, and that the password is hashed with **unsalted MD5 (uppercase hex)** before being
    uploaded over TLS — **the plaintext password never leaves the network card**. A fresh login
    not being able to solve captcha/2FA is a structural limitation, not a tool hiding a backdoor.

## Region trap: `miiocli`'s locale list has no `tw`

A Taiwan account is **not** a China account, and `cn` will never find it. Xiaomi binds the
account + devices to the region chosen at the moment of pairing in the Xiaomi Home App, served
via `{region}.api.io.mi.com`.

!!! danger "python-miio's AVAILABLE_LOCALES has no tw"
    `python-miio`'s built-in locales are only `cn, de, i2, ru, sg, us` (plus `all`) — **no `tw`**.
    So `miiocli cloud`, `micloud`, and HA's Xiaomi Miio cloud flow will **silently miss** the
    devices on a Taiwan account, and the list looks empty.

| Tool | Supported regions | For a Taiwan account |
|---|---|---|
| python-miio / micloud | cn, de, i2, ru, sg, us | ❌ no tw |
| `mihome-ctl` / Xiaomi-cloud-tokens-extractor | cn, de, us, ru, **tw**, **sg**, in, i2 | ✅ |

In practice: `mihome-ctl` scans `tw sg cn` by default. Many Taiwan / Southeast Asia users
actually have their devices in **`sg`** (they set the App region to Singapore during pairing).
**The most common reason for "the device list is empty" is picking the wrong region, not wrong
credentials.**

## Security review: which tools connect only to the official servers, and how passwords are handled

| Tool | Official Xiaomi only? | Password handling | Provides token? |
|---|---|---|---|
| `mihome-ctl` / extractor | ✅ `account.xiaomi.com` + `{region}.api.io.mi.com` | QR, password-free | ✅ |
| `miiocli cloud` / micloud | ✅ official | ⚠️ prompt not masked (plaintext echo) + sent after MD5 | ✅ |
| **`mijiaAPI` / `miot-mcp`** | ❌ **device flow goes through the third-party `api.mijia.tech`** | QR, password-free (but the token goes through a third party) | ❌ |
| `miio-extract-tokens` | ✅ zero network (offline) | none | ✅ |

!!! danger "mijiaAPI / miot-mcp go through a third-party proxy"
    `mijiaAPI` (`apis.py` hardcodes `api_base_url = https://api.mijia.tech/app`) sends your
    `serviceToken`/`ssecurity` and every device command to **`api.mijia.tech` — not Xiaomi
    official (self-hosted by the author)**. That is effectively a trusted MITM: the proxy side can
    log, replay, and tamper with all your device data and control commands. Use it only for pure
    cloud control and only if you trust it; if you want privacy / want the token, use `mihome-ctl`
    (official-only).

## QR is password-free but not zero-interaction

QR login hands authorization to the phone App, bypassing the captcha + email-2FA of
`serviceLoginAuth2`, and is not subject to the daily 2FA quota. But the phone side may still
occasionally ask for an SMS/OTP confirmation — it's "you don't type a password in the script,"
not "you never touch anything."
