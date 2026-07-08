"""``mihome-ctl`` CLI entry point: wires each subcommand function into Tyro."""

from __future__ import annotations

import sys

import tyro

from .commands import (
    action,
    devices,
    extract,
    ir,
    ir_ac,
    ir_code,
    ir_send,
    miio,
    prop_get,
    prop_set,
    setup,
    show,
    spec,
    tui,
    verify,
)


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] in ("--version", "-V"):
        from . import __version__

        print(f"mihome-ctl {__version__}")
        return
    result = tyro.extras.subcommand_cli_from_dict(
        {
            "extract": extract.extract,
            "list": show.list_,
            "verify": verify.verify,
            "ir": ir.ir,
            "ir-send": ir_send.ir_send,
            "ir-ac": ir_ac.ir_ac,
            "ir-code": ir_code.ir_code,
            "devices": devices.devices,
            "prop-get": prop_get.prop_get,
            "prop-set": prop_set.prop_set,
            "action": action.action,
            "miio": miio.miio,
            "spec": spec.spec,
            "setup": setup.setup,
            "tui": tui.tui,
        },
        prog="mihome-ctl",
        description="Passwordless QR login to the official Xiaomi cloud: extract per-device tokens (tw/sg friendly) + cloud IR/device control. `mihome-ctl --version` prints the version.",
    )
    sys.exit(result if isinstance(result, int) else 0)


if __name__ == "__main__":
    main()
