"""Reading a Track's audio, through `ffmpeg`.

`ffmpeg` is the decoder because it reads a Track whose Recording was interrupted: such a file is valid
FLAC without a length in its header, and may end in the middle of a block.
"""

import shutil
import subprocess
from pathlib import Path


class UnreadableTrack(Exception):
    """A Track's audio could not be read. The message says why in words fit for the user."""


def track_length(track: Path) -> float:
    """How many seconds of audio `track` holds, found by decoding it to its end.

    The file's header is not trusted with this: an interrupted Track's header gives no length.
    """
    if shutil.which("ffmpeg") is None:
        raise UnreadableTrack("ffmpeg is needed to read the Tracks and was not found on the PATH")
    # `-progress` reports how far decoding has got as `key=value` lines; the last `out_time_us` is the
    # length of what was decoded, in microseconds.
    decoding = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", track, "-f", "null", "-", "-progress", "pipe:1"],
        capture_output=True,
        text=True,
    )
    microseconds = [
        value
        for key, _, value in (line.partition("=") for line in decoding.stdout.splitlines())
        if key == "out_time_us" and value.isdigit()
    ]
    if decoding.returncode != 0 or not microseconds:
        reason = decoding.stderr.strip().splitlines()[-1:] or ["ffmpeg could not decode it"]
        raise UnreadableTrack(f"could not read {track}: {reason[0]}")
    return int(microseconds[-1]) / 1_000_000
