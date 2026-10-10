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

    The audio reaches the files while capture runs, and a file is valid FLAC at every moment: whatever
    ends the capture program, each Track can be decoded up to about the moment it ended.

Stop signal
    SIGINT. The capture program closes both files and exits with status 0. It treats SIGTERM and SIGHUP
    the same way, and a stop signal that arrives while it is already stopping changes nothing: Ctrl+C in
    a terminal reaches the capture program directly as well as through the CLI.

Standard output
    One event per line, UTF-8: the event's name, then zero or more `key=value` fields, all separated by
    single spaces. A value holds no spaces. A reader ignores events and fields it does not know, so new
    ones can be added without breaking it.

    started
        Both Tracks are being written.

    track-started track=<mic|system> host-time=<seconds>
        The named Track has received its first audio. `host-time` is the moment that audio was captured,
        in seconds on the host clock: the one clock both devices stamp their audio with, counting from an
        arbitrary moment. The difference between the two Tracks' values is how far apart they begin.

    output-route route=<speakers|headphones|unknown> transport=<word>
        What the computer was playing sound through when capture started, judged from the default output
        device. `transport` is how that device is connected, the fact the verdict rests on: `built-in`,
        `bluetooth`, `usb`, `hdmi`, `displayport`, `airplay`, `virtual` or `other`.

Failure
    When capture cannot start or cannot go on, the capture program writes the reason to standard error
    and exits with a non-zero status.
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


@dataclass(frozen=True)
class Event:
    """One line of the capture program's standard output."""

    name: str
    fields: dict[str, str]


def parse_event(line: str) -> Event:
    name, *fields = line.split()
    return Event(name, dict(field.split("=", 1) for field in fields if "=" in field))


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
