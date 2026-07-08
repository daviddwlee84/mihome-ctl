---
name: mihome-ir
description: Control cloud Xiaomi Mijia IR remotes (TV, air-conditioner, fan, DIY on/off) via the mihome-ctl CLI — no local hardware or Home Assistant. Use when the user asks to control a TV (volume / mute / power / input / channel), set an air-conditioner (temperature / mode / on / off / status), or send any IR remote key. Runs cloud IR through the user's parent blaster (e.g. a Xiao AI speaker).
---

# Mijia IR control (mihome-ctl)

Control cloud IR remotes (`miir.*`) with the **`mihome-ctl`** CLI. A QR-login session
is cached (`mi-session.json` in the state dir); if a command prints `❌` with a non-zero
`code`, the session likely expired — rerun the failing command with `--relogin` and tell
the user to scan the QR with the **Mi Home app**.

> This skill ships as a **generic example**. It does **not** hardcode any specific remote
> names — always **discover the user's own remotes first** (`mihome-ctl ir`), then match
> what the user says (e.g. 「電視」, 「客廳冷氣」, 「風扇」) to a remote from that list.

## 0. Discover the user's remotes/keys first

```bash
mihome-ctl ir                                  # list all remotes + parent blaster + type
mihome-ctl ir-send --remote <name-or-model>    # omit --key → list that remote's keys
```

`ir` writes `mi-ir.json` to the state dir. Map the user's words to a remote's **name or
model substring**; if unsure, show them the `ir` table and ask.

## 1. Send a TV / generic remote key

```bash
mihome-ctl ir-send --remote <remote> --key <KEY> [--repeat N]
```
Common TV keys: `POWER`, `MUTE`, `VOL+`, `VOL-`, `INPUT`, `HOME`, digits.

- 「靜音」→ `ir-send --remote <tv> --key MUTE`
- 「大聲一點」→ `ir-send --remote <tv> --key VOL+ --repeat 3`
- 「關電視」→ `ir-send --remote <tv> --key POWER`
- 「開/關風扇」→ `ir-send --remote <fan> --key POWER`

## 2. Air-conditioner — absolute state

```bash
mihome-ctl ir-ac [--temp 16-30] [--mode auto|cool|dry|heat|fan] [--on|--off|--status]
```
- 「開冷氣 26 度制冷」→ `ir-ac --temp 26 --mode cool`
- 「冷氣關掉」→ `ir-ac --off`
- 「冷氣現在幾度」→ `ir-ac --status`

`ir-ac` defaults to the sole `miir.aircondition.*` remote; if there are several, add
`--remote <name>`. Note: physical `lumi.acpartner` companions are **not** IR remotes and
`ir-ac` does not control them.

## Guardrails

- This is **cloud** IR (through Xiaomi + the parent blaster) — needs internet and the
  blaster in IR range of the appliance. On success the CLI prints `✅`.
- IR is one-way: **no absolute TV volume** (only `VOL+`/`VOL-`); the AC is state-based so
  absolute temp/mode works.
- Just run explicit requests. For a disruptive power action the user did **not** ask for
  (e.g. turning the AC on unprompted), confirm first.

## State dir

`mihome-ctl` resolves its state dir from `MIHOME_CTL_HOME` → nearest `./.secrets/` →
platformdirs. When running inside a repo that already holds `.secrets/`, run from that
repo root (or set `MIHOME_CTL_HOME`) so the cached session is reused.
