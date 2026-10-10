"""The `tldl` command line."""

import argparse
import signal
import sys
import tempfile
import time
from pathlib import Path

from tldl.capture import MIC_TRACK_FILE, SYSTEM_TRACK_FILE, Capture
from tldl.status_line import status_line


def main() -> int:
    parser = argparse.ArgumentParser(prog="tldl")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("record", help="capture the mic track and the system track until Ctrl+C")
    parser.parse_args()
    return record()


def record() -> int:
    folder = Path(tempfile.mkdtemp(prefix="tldl-", dir=Path.cwd()))
    mic_track = folder / MIC_TRACK_FILE
    system_track = folder / SYSTEM_TRACK_FILE

    capture = Capture(mic_track, system_track)
    signal.signal(signal.SIGINT, lambda signum, frame: capture.stop())

    started_at = None
    status_line_shown = False
    failure = None
    for event in capture.events():
        if event.name == "started":
            print("Recording. Press Ctrl+C to stop.", flush=True)
            started_at = time.monotonic()
        elif event.name == "level" and started_at is not None:
            elapsed = time.monotonic() - started_at
            levels = (float(event.fields.get(track, 0)) for track in ("mic", "system"))
            # The carriage return writes each state of the status line over the one before it.
            print("\r" + status_line(elapsed, *levels), end="", flush=True)
            status_line_shown = True
        elif event.name == "failed":
            failure = event.text
    if status_line_shown:
        print()
    if capture.wait() != 0 and failure is None:
        failure = "the capture program stopped with an error"

    if failure is not None:
        outcome = "failed" if started_at is None else "stopped"
        print(f"Recording {outcome}: {failure}.", file=sys.stderr)
        if started_at is None:
            return 1

    print(f"Mic track: {mic_track}")
    print(f"System track: {system_track}")
    return 0 if failure is None else 1
