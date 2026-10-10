"""The `tldl` command line."""

import argparse
import signal
import sys
from datetime import datetime
from pathlib import Path

from tldl.capture import Capture
from tldl.recording import DEFAULT_RECORDINGS_ROOT, Recording


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

    started = False
    for event in capture.events():
        if event.name == "started":
            started = True
            print("Recording. Press Ctrl+C to stop.", flush=True)
        elif event.name == "track-started":
            recording.note_track_start(event.fields["track"], float(event.fields["host-time"]))
        elif event.name == "output-route":
            recording.note_output_route(event.fields["route"], event.fields.get("transport"))
    if capture.wait() != 0:
        if not started:
            recording.discard()
        print("Recording failed: the capture program stopped with an error.", file=sys.stderr)
        return 1

    print(f"Mic track: {recording.mic_track}")
    print(f"System track: {recording.system_track}")
    return 0
