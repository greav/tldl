"""The status line `tldl record` shows while a Recording runs."""

import math

LEVEL_CELLS = 10
"""How many cells a level is drawn with."""

QUIETEST_SHOWN_DB = -60.0
"""Sound at or below this many decibels under full scale is drawn as no cells."""


def status_line(elapsed_seconds: float, mic_level: float, system_level: float) -> str:
    """The elapsed time and one level per Track. A level is a fraction of full scale, 0 to 1.

    The line is the same width whatever it shows, so writing one over another leaves nothing behind.
    """
    minutes, seconds = divmod(int(elapsed_seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return (
        f"{hours:02}:{minutes:02}:{seconds:02}"
        f"  mic {_level_cells(mic_level)}  system {_level_cells(system_level)}"
    )


def _level_cells(level: float) -> str:
    """A level drawn on a decibel scale, which is how loudness is heard."""
    if level <= 0:
        filled = 0
    else:
        decibels = 20 * math.log10(level)
        shown = min(max(1 - decibels / QUIETEST_SHOWN_DB, 0), 1)
        filled = round(shown * LEVEL_CELLS)
    return "█" * filled + "·" * (LEVEL_CELLS - filled)
