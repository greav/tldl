#!/usr/bin/env python3
"""Stand-in capture program for the fast suite.

Speaks the capture program contract described in `src/tldl/capture.py`, without touching audio devices:
each Track file is written only when the stop signal arrives, and holds the name of the Track the contract
assigns to that argument. The Track starts and the output route it reports are always the same.
"""

import signal
import sys


def main() -> int:
    mic_track, system_track = sys.argv[1:]

    stop_signals = {signal.SIGINT, signal.SIGTERM}
    signal.pthread_sigmask(signal.SIG_BLOCK, stop_signals)

    print("started", flush=True)
    print("output-route route=headphones transport=bluetooth", flush=True)
    print("track-started track=mic host-time=100.250000", flush=True)
    print("track-started track=system host-time=100.500000", flush=True)
    signal.sigwait(stop_signals)

    with open(mic_track, "w") as track:
        track.write("mic track")
    with open(system_track, "w") as track:
        track.write("system track")
    return 0


if __name__ == "__main__":
    sys.exit(main())
