"""Baseball innings notation.

5.2 means five innings and two outs = 17 outs = 17/3 innings, not 5.2 decimal.
"""

from __future__ import annotations


def parse_innings(value) -> float:
    """Convert baseball IP (X.Y with Y in 0..2) to decimal innings (outs/3)."""
    if value is None or value == "":
        raise ValueError("missing innings")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        s = f"{value}"
    else:
        s = str(value).strip()
    if not s:
        raise ValueError("missing innings")
    if "." in s:
        whole, frac = s.split(".", 1)
        outs_part = int(frac[0]) if frac else 0
        if outs_part not in (0, 1, 2):
            raise ValueError(f"invalid baseball innings fraction: {value!r}")
        innings_whole = int(whole or 0)
        return innings_whole + outs_part / 3.0
    return float(int(s))


def innings_to_outs(value) -> int:
    dec = parse_innings(value)
    return int(round(dec * 3))


def outs_to_innings(outs: int) -> float:
    return outs / 3.0


def format_baseball_ip(decimal_innings: float) -> str:
    outs = int(round(decimal_innings * 3))
    whole, rem = divmod(outs, 3)
    return f"{whole}.{rem}"
