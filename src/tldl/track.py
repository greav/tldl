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
    # `-progress` reports how far decoding has got as `key=value` lines; the last `out_time_us` is the
    # length of what was decoded, in microseconds.
    microseconds = [value for value in _decoded(track, ["-progress", "pipe:1"], "out_time_us") if value.isdigit()]
    if not microseconds:
        raise UnreadableTrack(f"could not read {track}: ffmpeg could not decode it")
    return int(microseconds[-1]) / 1_000_000


def track_holds_audio(track: Path) -> bool:
    """Whether `track` holds any audio at all. The Track of a Recording killed in its first moments is a
    header with nothing after it: a file that can be read, and holds none."""
    lengths = _decoded(track, ["-progress", "pipe:1"], "out_time_us")
    return any(length.isdigit() and int(length) > 0 for length in lengths)


LOUDNESS_MOMENTS_A_SECOND = 10
"""How many values `track_momentary_loudness` gives for each second of a Track."""


def track_momentary_loudness(track: Path) -> list[float]:
    """How loud `track` is from moment to moment, in LUFS: its momentary loudness by EBU R 128.

    There is one value for each tenth of a second of the Track, in order: the loudness of the 0.4
    seconds that end there. Before 0.4 seconds have passed, and where the Track holds digital silence,
    the value is far below that of any sound, under -120. A Track shorter than a tenth of a second has
    none.
    """
    return [
        float(loudness)
        for loudness in _decoded(
            track, ["-af", "ebur128=metadata=1,ametadata=mode=print:key=lavfi.r128.M:file=-"], "lavfi.r128.M"
        )
    ]


def _decoded(track: Path, reporting: list[str], key: str) -> list[str]:
    """Decode `track` to its end with ffmpeg, which is given the arguments `reporting` to make it report
    `key=value` lines on its output; returns the values reported for `key`, in order."""
    if shutil.which("ffmpeg") is None:
        raise UnreadableTrack("ffmpeg is needed to read the Tracks and was not found on the PATH")
    # The file is looked at here, because ffmpeg's own words are no reason to give: for a file with
    # nothing in it, and for one that is not audio, the last thing it writes is about the output it
    # could not make and says nothing of the Track.
    try:
        with open(track, "rb") as content:
            empty = not content.read(1)
    except OSError as problem:
        raise UnreadableTrack(f"could not read {track}: {problem.strerror}") from problem
    if empty:
        raise UnreadableTrack(f"could not read {track}: the file is empty")
    decoding = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", track, *reporting, "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    if decoding.returncode != 0:
        raise UnreadableTrack(f"could not read {track}: ffmpeg could not decode it")
    return [
        value for name, _, value in (line.partition("=") for line in decoding.stdout.splitlines()) if name == key
    ]
