"""``mihome-ctl`` CLI 進入點：把各 subcommand 函式接上 Tyro。"""

from __future__ import annotations

import sys

import tyro

from .commands import extract, ir, ir_ac, ir_code, ir_send, show, verify


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
        },
        prog="mihome-ctl",
        description="免密碼 QR 登入官方小米雲：抽 per-device token（tw/sg 友善）＋雲端 IR 控制",
    )
    sys.exit(result if isinstance(result, int) else 0)


if __name__ == "__main__":
    main()
