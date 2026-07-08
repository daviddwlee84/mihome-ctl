"""``spec`` — show a device's MIoT properties/actions by name (from miot-spec.org)."""

from __future__ import annotations

import json
import sys

from tabulate import tabulate

from ..config import StateDir
from ..core import miotspec
from ..core.operations import find_device


def spec(did: str | None = None, model: str | None = None) -> int:
    """Show named MIoT properties/actions for a device (--did) or a model (--model)."""
    state = StateDir.resolve()
    if not model:
        if not did:
            print("[mihome-ctl] pass --did <DID> or --model <MODEL>", file=sys.stderr)
            return 1
        if not state.tokens_json.exists():
            print(f"[mihome-ctl] {state.tokens_json} not found; run extract first", file=sys.stderr)
            return 1
        rows = json.loads(state.tokens_json.read_text(encoding="utf-8"))
        dev = find_device(rows, did)
        if not dev:
            print(f"[mihome-ctl] did={did} not found (run `mihome-ctl devices`)", file=sys.stderr)
            return 1
        model = dev.get("model", "")
    d = miotspec.describe(state, model)
    if d is None:
        print(f"[mihome-ctl] no public MIoT spec for model {model}", file=sys.stderr)
        return 1
    print(f"# {model}  ({d.urn})\n")
    ptab = [
        [
            p.siid,
            p.piid,
            f"{p.service} · {p.name}",
            p.format,
            miotspec.access_flags(p),
            miotspec.prop_constraint(p),
        ]
        for p in d.props
    ]
    print(
        tabulate(
            ptab,
            headers=["siid", "piid", "property", "format", "acc", "values"],
            tablefmt="rounded_outline",
        )
    )
    if d.actions:
        atab = [[a.siid, a.aiid, f"{a.service} · {a.name}", a.in_] for a in d.actions]
        print(
            "\n"
            + tabulate(atab, headers=["siid", "aiid", "action", "in"], tablefmt="rounded_outline")
        )
    print("\nUse with: mihome-ctl prop-get/prop-set --did <DID> --siid <s> --piid <p>  (or `tui`).")
    return 0
