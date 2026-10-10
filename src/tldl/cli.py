"""The `tldl` command line."""

import argparse
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from tldl.capture import Capture
from tldl.recording import DEFAULT_RECORDINGS_ROOT, Recording
from tldl.status_line import status_line


def main() -> int:
    parser = argparse.ArgumentParser(prog="tldl")
    commands = parser.add_subparsers(dest="command", required=True)
    record_command = commands.add_parser(
        "record", help="capture the mic track and the system track until Ctrl+C"
    )
    record_command.add_argument("title", nargs="?", help="a name for the Recording, added to its folder's name")
    arguments = parser.parse_args()
    return record(DEFAULT_RECORDINGS_ROOT, arguments.title)


def record(recordings_root: Path, title: str | None) -> int:
    recording = Recording.begin(recordings_root, datetime.now().astimezone(), title)

    capture = Capture(recording.mic_track, recording.system_track)
    signal.signal(signal.SIGINT, lambda signum, frame: capture.stop())

    started_at = None
    status_line_shown = False
    failure = None
    for event in capture.events():
        if event.name == "started":
            print("Recording. Press Ctrl+C to stop.", flush=True)
            started_at = time.monotonic()
        elif event.name == "track-started":
            recording.note_track_start(event.fields["track"], float(event.fields["host-time"]))
        elif event.name == "output-route":
            recording.note_output_route(event.fields["route"], event.fields.get("transport"))
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
            recording.discard()
            return 1

    print(f"Mic track: {recording.mic_track}")
    print(f"System track: {recording.system_track}")
    return 0 if failure is None else 1
