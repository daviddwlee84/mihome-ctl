"""Microsecond IR timings → Pronto hex (feedable to chuangmi.ir.v2's play_pronto / HA remote).

Pronto ("learned", type 0x0000) format: 4 header words (0000, the carrier
divisor, the burst-pair count of the once-sequence, the burst-pair count of the
repeat-sequence) followed by paired on/off cycle counts. Here we emit only the
"once-sequence" (the 3rd header word) and leave the repeat section at 0.
"""

from __future__ import annotations

# Pronto time-base constant: one Pronto cycle-unit = 0.241246 µs (≈ 1 / 4.145MHz reference clock).
_PRONTO_UNIT_US = 0.241246


def timings_to_pronto(timings: list[int], freq: int) -> str:
    """Convert microsecond ON/OFF timings + carrier frequency (Hz) into a Pronto hex string."""
    fw = round(1_000_000 / (freq * _PRONTO_UNIT_US))
    cycles = [max(1, round(t * freq / 1_000_000)) for t in timings]
    if len(cycles) % 2:  # bursts must be paired; append a minimal off
        cycles.append(1)
    words = [0x0000, fw, len(cycles) // 2, 0x0000] + cycles
    return " ".join(f"{w:04X}" for w in words)
