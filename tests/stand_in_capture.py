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

The microphones it plays come from the environment too:

STAND_IN_MICROPHONES
    The names of the microphones that are there, one per line, the system default microphone first. The
    stand-in takes the mic track from the one named in its arguments, or else from the first, and reports
    it in a `microphone` event right after `started`. A name that is not among them fails as the contract
    says a microphone that is not there does. Without the variable there are none: the stand-in reports no
    `microphone` event, and any name it is given is not there.
"""

import os
import signal
import sys
import time
from urllib.parse import quote


def main() -> int:
    mic_track, system_track, *named = sys.argv[1:]
    microphones = os.environ.get("STAND_IN_MICROPHONES", "").splitlines()
    microphone = named[0] if named else microphones[0] if microphones else None
    if microphone is not None and microphone not in microphones:
        there = f"the microphones are {', '.join(microphones)}" if microphones else "there are no microphones"
        print(f"failed there is no microphone named {microphone}; {there}", flush=True)
        return 1
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
    if microphone is not None:
        print(f"microphone name={quote(microphone, safe='')} transport=built-in sample-rate=48000", flush=True)
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
