#!/usr/bin/env python3
"""Stand-in capture program for the fast suite.

Speaks the capture program contract described in `src/tldl/capture.py`, without touching audio devices:
each Track file is written only when the stop signal arrives, and holds the name of the Track the contract
assigns to that argument.
"""

import signal
import sys


def main() -> int:
    mic_track, system_track = sys.argv[1:]

    stop_signals = {signal.SIGINT, signal.SIGTERM}
    signal.pthread_sigmask(signal.SIG_BLOCK, stop_signals)

    print("started", flush=True)
    signal.sigwait(stop_signals)

    with open(mic_track, "w") as track:
        track.write("mic track")
    with open(system_track, "w") as track:
        track.write("system track")
    return 0


if __name__ == "__main__":
    sys.exit(main())
