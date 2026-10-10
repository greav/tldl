"""The capture program, as the CLI sees it.

This module is the one description of the capture program contract. The Swift capture program in
`capture/` and the stand-in in `tests/stand_in_capture.py` both implement it.

Capture program contract
------------------------

Arguments
    tldl-capture <mic-track-path> <system-track-path>

    Two file paths and nothing else. The capture program writes the mic track (the system default
    microphone at the moment of start) to the first and the system track (everything the computer plays)
    to the second, each as mono 16-bit FLAC at its device's sample rate. The folders must exist; the files
    are created or replaced.

Stop signal
    SIGINT. The capture program closes both files and exits with status 0. It treats SIGTERM and SIGHUP
    the same way, and a stop signal that arrives while it is already stopping changes nothing: Ctrl+C in
    a terminal reaches the capture program directly as well as through the CLI.

    The capture program stops in the same way when nobody reads its standard output any more: without
    the CLI there is nobody left to send the stop signal.

Standard output
    One event per line, UTF-8: the event's name, then zero or more `key=value` fields, all separated by
    single spaces. A value holds no spaces. A reader ignores events and fields it does not know, so new
    ones can be added without breaking it.

    started
        Both Tracks are being written.

    level mic=<level> system=<level>
        The loudest sample of each Track since the event before this one, as a fraction of full scale
        from 0.0000 to 1.0000. Reported about ten times a second from `started` until capture ends. A
        Track with no sound in it reports 0.0000.

    failed <reason>
        Capture could not start or could not go on. Everything after the name is the reason, in words
        fit for the user; unlike a field it may hold spaces. It is the last event.

Failure
    When capture cannot start or cannot go on, the capture program closes both files, so that what was
    captured is kept, reports `failed` and exits with a non-zero status. The microphone it started on
    disappearing is such a failure. A non-zero status with no `failed` event means the capture program
    itself broke.

Sleep
    From `started` until it exits, the capture program keeps the Mac from idle sleep.
"""

import os
import signal
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

PACKAGED_CAPTURE_PROGRAM = Path(__file__).parent / "bin" / "tldl-capture"
"""Where `make install` puts the capture binary inside the package."""

CAPTURE_PROGRAM_VARIABLE = "TLDL_CAPTURE_PROGRAM"
"""Environment variable naming a program to run in place of the packaged one, such as a stand-in."""

MIC_TRACK_FILE = "mic.flac"
SYSTEM_TRACK_FILE = "system.flac"


@dataclass(frozen=True)
class Event:
    """One line of the capture program's standard output."""

    name: str
    fields: dict[str, str]
    text: str = ""
    """Everything after the name, for an event that carries words and not fields."""


def parse_event(line: str) -> Event:
    name, _, text = line.strip().partition(" ")
    fields = dict(field.split("=", 1) for field in text.split() if "=" in field)
    return Event(name, fields, text)


class Capture:
    """A running capture program, writing the two Tracks to the given paths."""

    def __init__(self, mic_track: Path, system_track: Path) -> None:
        program = os.environ.get(CAPTURE_PROGRAM_VARIABLE) or PACKAGED_CAPTURE_PROGRAM
        self._process = subprocess.Popen(
            [program, mic_track, system_track], stdout=subprocess.PIPE, text=True
        )

    def events(self) -> Iterator[Event]:
        """The capture program's events as they arrive, until it closes its output."""
        for line in self._process.stdout:
            if line.strip():
                yield parse_event(line)

    def stop(self) -> None:
        """Send the stop signal."""
        self._process.send_signal(signal.SIGINT)

    def wait(self) -> int:
        """Wait for the capture program to exit and return its exit status."""
        return self._process.wait()
