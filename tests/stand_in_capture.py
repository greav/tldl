#!/usr/bin/env python3
"""Stand-in capture program for the fast suite.

Speaks the capture program contract described in `src/tldl/capture.py`, without touching audio devices:
each Track file is written only when capture ends, and holds the name of the Track the contract assigns
to that argument.

What it reports after `started` comes from the environment:

STAND_IN_EVENTS
    Events to report, one per line, exactly as written. Without a `failed` event among them the stand-in
    then waits for the stop signal. On a `failed` event it ends capture as the contract says a failure
    does: it writes the Tracks, reports the event and exits with status 1.

STAND_IN_EVENT_INTERVAL
    Seconds to wait before each of those events. Default 0.
"""

import os
import signal
import sys
import time


def main() -> int:
    mic_track, system_track = sys.argv[1:]
    events = os.environ.get("STAND_IN_EVENTS", "").splitlines()
    interval = float(os.environ.get("STAND_IN_EVENT_INTERVAL", "0"))

    def write_tracks() -> None:
        with open(mic_track, "w") as track:
            track.write("mic track")
        with open(system_track, "w") as track:
            track.write("system track")

    stop_signals = {signal.SIGINT, signal.SIGTERM}
    signal.pthread_sigmask(signal.SIG_BLOCK, stop_signals)

    print("started", flush=True)
    for event in events:
        time.sleep(interval)
        if event.split()[0] == "failed":
            write_tracks()
            print(event, flush=True)
            return 1
        print(event, flush=True)
    signal.sigwait(stop_signals)

    write_tracks()
    return 0


if __name__ == "__main__":
    sys.exit(main())
