"""微秒 IR 時序 → Pronto hex（可餵給 chuangmi.ir.v2 的 play_pronto / HA remote）。

Pronto（"learned", type 0x0000）格式：4 個 header word（0000、載波除數、
一次序列的 burst-pair 數、重複序列的 burst-pair 數）後接成對的 on/off cycle 數。
這裡只輸出「一次序列」（第 3 個 header word），重複段留 0。
"""

from __future__ import annotations

# Pronto 時基常數：一個 Pronto cycle-unit = 0.241246 µs（≈ 1 / 4.145MHz 參考時鐘）。
_PRONTO_UNIT_US = 0.241246


def timings_to_pronto(timings: list[int], freq: int) -> str:
    """把微秒 ON/OFF 時序 + 載波頻率(Hz)轉成 Pronto hex 字串。"""
    fw = round(1_000_000 / (freq * _PRONTO_UNIT_US))
    cycles = [max(1, round(t * freq / 1_000_000)) for t in timings]
    if len(cycles) % 2:  # burst 必須成對；補一個最小 off
        cycles.append(1)
    words = [0x0000, fw, len(cycles) // 2, 0x0000] + cycles
    return " ".join(f"{w:04X}" for w in words)
