# mihome-ctl

Password-free QR login to the **official** Xiaomi cloud, extract each device's miIO
**token** / local IP / BLE key, and **control cloud IR remotes** (TV / air-conditioner /
fan / DIY on-off) — emitted through the parent blaster at home (e.g. a Xiao AI speaker),
**no local hardware and no Home Assistant required**.

- Connects only to official domains: `account.xiaomi.com` + `{region}.api.io.mi.com`
- Supports `tw` / `sg` (the locale list in `python-miio`/`micloud` has no `tw`)
- Produces per-device token + local IP + BLE key
- Password-free (uses QR); secret output is chmod 600

## Install and quick start

```bash
uv tool install mihome-ctl          # or pipx install mihome-ctl
mihome-ctl extract                  # QR login to extract tokens (scan tw sg cn)
mihome-ctl ir                       # list cloud IR remotes
mihome-ctl ir-send --remote <name> --key MUTE
mihome-ctl ir-ac --temp 26 --mode cool
```

## Contents

- [Auth & Token](auth-token.md): how to get a token / QR login, comparison of the methods.
- [Login troubleshooting](login-troubleshooting.md): `Access denied`, locale missing `tw`, third-party proxy security review.
- [Local IR control](ir.md): how to extract `miir.*` cloud codes, DIY vs brand pairing, Pronto, whether local replay is possible.

Source code and issues: <https://github.com/daviddwlee84/mihome-ctl>
