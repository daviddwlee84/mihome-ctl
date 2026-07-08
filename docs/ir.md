# Local IR control (including pulling `miir.*` cloud codes back to local)

The Mi Home App has a "learn a remote → record a button → replay it later" feature. This can be
done **entirely locally** (`python-miio` talks miIO directly, without going through the cloud) —
provided the IR blaster's **model is the right one** and the code's **format matches**. This page
answers the core question: **can you extract the codes already recorded in the cloud `miir.*` and
replay them yourself?**

!!! info "The conclusion up front"
    - **Extractable**: the `miir.*` remotes on your account can be read out via the official cloud
      API (`{region}.api.io.mi.com/app/v2/irdevice/...`).
    - **DIY-learned keys**: the raw code is stored on the account → can be replayed directly.
      **Brand-paired remotes**: only a reference is stored; the real code lives in Xiaomi's code
      library and is **AES-ECB + gzip encrypted → microsecond timings → Pronto**, and only
      `chuangmi.ir.v2` can play it.
    - **Format is bound to the blaster**: chuangmi base64 ≠ acpartner `FE` ≠ pronto, not
      interchangeable. `lumi.acpartner.v2` can only replay codes "learned on the acpartner"; it
      can't send the extracted TV/chuangmi codes.

## Which devices can emit IR locally

| Model | `python-miio` class | Local learn/play? | Notes |
|---|---|---|---|
| `chuangmi.ir.v2` / `chuangmi.remote.v2` (universal remote) | `ChuangmiIr` | ✅ full `learn`/`read`/`play`/`play_pronto` | **cleanest for arbitrary codes** |
| `lumi.acpartner.v2` (AC companion) | `AirConditioningCompanion` | ✅ `learn`/`send_ir_code` (**FE format**) | best for AC; can learn TV/fan, but codes are acpartner-specific |
| `lumi.acpartner.mcn02` | `AirConditioningCompanionMcn02` | ❌ only on/off/status/send_command | **can't learn** IR locally |
| `xiaomi.wifispeaker.*` (Xiao AI speakers with IR) | `WifiSpeaker` | ❌ no local IR methods at all | has IR hardware but `WifiSpeaker` has no local IR API → **cloud only** |

!!! warning "'Have Xiao AI turn on the TV via IR' is a cloud skill, not local"
    Even a Xiao AI with IR — `python-miio`'s `WifiSpeaker` class **has no IR methods at all** — its
    IR is driven entirely by the Xiaomi cloud / voice scenes. **No Xiao AI speaker can act as a
    local IR emitter.** For local, use `chuangmi.ir.v2` or `acpartner.v2`.

## Path 1: extract the codes from the cloud `miir.*`

`miir.tv.ir01`, `miir.aircondition.ir02`, `miir.fan.ir01`… have no token and no `localip`,
because they aren't physical devices but "appliance definitions" that Mi Home overlays on a real
blaster. But **the recorded codes can be extracted via the official cloud API**, using the
`serviceToken`/`ssecurity` signing that `mihome-ctl` already has.

### Endpoints (POST, official `api.io.mi.com`, not third-party)

| Endpoint | Params | Purpose |
|---|---|---|
| `/v2/irdevice/controllers` | `{parent_id}` | list the virtual remotes under a physical blaster |
| `/v2/irdevice/controller/keys` | `{did}` | list a remote's **keys** (includes `code` for DIY) |
| `/v2/irdevice/controller/info` | `{did}` | remote info, including the `controller_id` (matchid) of a brand pairing |
| `/v2/irdevice/controller/key/click` | `{did, key_id}` | **cloud**-trigger a single key (works today) |

The key factor that decides "can it be replayed locally" is each `miir.*`'s **`parent_id`** (which
physical blaster produced it), which determines the code format:

| Case | Code format | Local replay |
|---|---|---|
| DIY-learned, parent = chuangmi blaster/Xiao AI | chuangmi base64 (magic `0xA567`) | ✅ `chuangmi.ir.v2` `play('raw:…')` |
| DIY-learned, parent = acpartner | `FE…` frame | ✅ replay on the same `acpartner.v2` with `send_ir_code` |
| **brand pairing** | code-library encrypted: base64 → AES-ECB(`fd7e915003168929c1a9b0ec32a60788`) → gzip → microsecond timings → **Pronto** | ✅ only `chuangmi.ir.v2` `play('pronto:…')` |

### Look up your remotes with `mihome-ctl ir`

```bash
mihome-ctl ir   # draws the login QR directly in the terminal (open :31415 if it can't be scanned); session-cached after one scan
```

This lists each `miir.*`'s **parent blaster**, key count, and **DIY (self-learned) vs brand
pairing (matchid)**, writing the raw keys/info to `mi-ir.json` in the state dir.

!!! note "The usual conclusion"
    A Xiao AI speaker with IR often has a batch of `miir.*` under it (TV / AC / fan + a few DIY
    self-learned), but **the Xiao AI speaker has no local IR API**, so **none of these can be
    replayed locally through the speaker**. For local TV control, the most practical option is to
    add a `chuangmi.ir.v2` and then either pick codes from a code library with SmartIR or re-learn.

### Usable right now: cloud-triggered `ir-send` (no hardware)

You don't have to wait to buy a blaster — `/v2/irdevice/controller/key/click` lets the cloud tell
the parent blaster to emit, and **both DIY and brand pairing work**:

```bash
mihome-ctl ir-send --remote <TV name> --key VOL+
mihome-ctl ir-send --remote <fan name> --key POWER --repeat 2
mihome-ctl ir-send --remote <TV name>          # omit --key → list all keys
```

Downsides: it goes through the cloud (depends on the network + Xiaomi), and the speaker must be
within IR range of the appliance. But it's **zero hardware, scriptable, and feedable to Claude**.

!!! note "'Set volume to 30' — a TV can't, an AC can"
    IR TVs are **stateless, one-way, no feedback** — you only get `VOL+`/`VOL-`, there's no
    absolute "set to 30". But **an AC is stateful** (`ac_state`) and can be set absolutely.

### Absolute AC control `ir-ac` (via MIoT-spec)

```bash
mihome-ctl ir-ac --status                # read the current ac_state
mihome-ctl ir-ac --temp 26 --mode cool   # set 26°C cooling and power on
mihome-ctl ir-ac --off                   # power off
```

Uses `/miotspec/prop/set` (ir-mode `siid2/piid1`: auto/cool/dry/heat/fan = 0–4; ir-temperature
`siid2/piid2`: 16–30) + `/miotspec/action` (power on aiid6 / off aiid5).

### `ir-code`: decode an IRDB matchid into Pronto (for local replay)

```bash
mihome-ctl ir-code --matchid xm_1_199
```

Fetches from the code library → AES-ECB/gzip decode → outputs **Pronto** for each key (feedable to
`chuangmi.ir.v2`'s `play_pronto`). The decoding is a native clean-room implementation (no AGPL
dependency).

!!! warning "Fetching codes online currently needs an app signature"
    The public `{region}-urc.io.mi.com/controller/code/1` endpoint currently returns `status:19`
    for anonymous requests (a Mi Home app signature is required), so "fetch codes online by
    matchid" is marked experimental; the decoding itself is validated with a homemade round-trip
    test. Also, the account's `controller_id` (the ID of a brand-paired remote) is **not** the
    matchid of the public IRDB and can't be used to look it up directly — for local TV codes, the
    most practical option is SmartIR or re-learning on a `chuangmi.ir.v2`.

> References: `remote.py` in [`al-one/hass-xiaomi-miot`](https://github.com/al-one/hass-xiaomi-miot),
> and `ircontroller.js` (official API) in [`MiEcosystem/miot-plugin-sdk`](https://github.com/MiEcosystem/miot-plugin-sdk).

## Path 2: just re-learn locally (no extraction, simplest)

Point the original remote at a locally-controllable blaster and learn it once:

```python
from miio import ChuangmiIr
d = ChuangmiIr("<BLASTER_IP>", "<TOKEN>")
d.learn(1); print(d.read(1))    # arm slot 1 → press the remote at it → get the base64 code
d.play("<BASE64_CODE>")         # replay (also accepts 'pronto:HEX')
```

First use [`mihome-ctl verify`](auth-token.md) to confirm the blaster's token + current IP (the
cloud's `localip` often expires; the tool auto-resolves via ARP-by-MAC).

## Path 3: Home Assistant `remote` + SmartIR (best UX)

Add the universal remote to HA via `xiaomi_miio`'s `remote` platform (host+token talking directly
to the LAN), which supports `chuangmi.ir.v2`/`chuangmi.remote.v2`; then use
[SmartIR](https://github.com/litinoveweedle/SmartIR) to grow a full `media_player` based on your
TV model.

!!! warning "SmartIR's Xiaomi = the universal remote's remote entity"
    SmartIR's Xiaomi controller **specifically means** `xiaomi_miio`'s **ChuangmiIr `remote`
    entity** — it **cannot** drive `lumi.acpartner`, nor drive a speaker.
