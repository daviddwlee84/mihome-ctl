"""``mihome-ctl`` CLI entry point: wires each subcommand function into Tyro."""

from __future__ import annotations

import sys

import tyro

from .commands import extract, ir, ir_ac, ir_code, ir_send, setup, show, verify


def main() -> None:
    result = tyro.extras.subcommand_cli_from_dict(
        {
            "extract": extract.extract,
            "list": show.list_,
            "verify": verify.verify,
            "ir": ir.ir,
            "ir-send": ir_send.ir_send,
            "ir-ac": ir_ac.ir_ac,
            "ir-code": ir_code.ir_code,
            "setup": setup.setup,
        },
        prog="mihome-ctl",
        description="Passwordless QR login to the official Xiaomi cloud: extract per-device tokens (tw/sg friendly) + cloud IR control",
    )
    sys.exit(result if isinstance(result, int) else 0)


if __name__ == "__main__":
    main()
