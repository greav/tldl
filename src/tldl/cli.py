"""The `tldl` command line."""

import argparse
import signal
import sys
import tempfile
from pathlib import Path

from tldl.capture import MIC_TRACK_FILE, SYSTEM_TRACK_FILE, Capture


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

    for event in capture.events():
        if event.name == "started":
            print("Recording. Press Ctrl+C to stop.", flush=True)
    if capture.wait() != 0:
        print("Recording failed: the capture program stopped with an error.", file=sys.stderr)
        return 1

    print(f"Mic track: {mic_track}")
    print(f"System track: {system_track}")
    return 0
