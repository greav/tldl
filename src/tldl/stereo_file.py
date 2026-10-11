"""Making a Recording's stereo file from its two Tracks, with `ffmpeg`.

The stereo file is one stereo FLAC at 48 kHz in the Recording folder: the mic track is its left channel,
the system track its right. The Tracks are only read, so the stereo file can always be made again.

Each channel begins where its Track began on the clock the two Tracks share, and the one that ends first
is silent from there to the end, so nothing of either Track is cut.

Each Track is brought to the same loudness on its own, by one change of level for the whole Track: its
loudness is measured first, and the Track is raised or lowered by the difference from the target. It is
never raised by more than a fixed limit, so a Track that holds no speech stays quiet. The few moments
that would then pass full scale are turned down by a limiter; nothing clips.
"""

import os
import subprocess
from pathlib import Path

from tldl.recording import Recording
from tldl.track import UnreadableTrack, track_loudness

SAMPLE_RATE = 48_000
"""The stereo file's sample rate, in hertz. A Track at another rate is resampled to it."""

TARGET_LOUDNESS = -19.0
"""How loud each channel of the stereo file is made, in LUFS."""

RAISE_LIMIT = 20.0
"""The most a Track is raised to reach the target, in decibels. Lowering has no limit."""

PEAK_CEILING = -1.0
"""The level no sample of the stereo file rises above, in dBFS."""


class StereoFileNotMade(Exception):
    """A Recording's stereo file could not be made. The message says why in words fit for the user."""


def make_stereo_file(recording: Recording) -> Path:
    """Make the stereo file of `recording`, in the place of one made before; returns where it is."""
    stereo_file = recording.stereo_file
    mic_offset, system_offset = recording.track_offsets
    try:
        mic_loudness = track_loudness(recording.mic_track)
        system_loudness = track_loudness(recording.system_track)
    except UnreadableTrack as problem:
        raise StereoFileNotMade(str(problem)) from problem
    # Each Track becomes a stereo stream with sound in one channel only, and the two are added together
    # for as long as the longer one lasts.
    graph = (
        f"[0:a]{_channel(0, mic_offset, mic_loudness)}[left];"
        f"[1:a]{_channel(1, system_offset, system_loudness)}[right];"
        "[left][right]amix=inputs=2:duration=longest:normalize=0[stereo]"
    )
    # Written aside and moved into place, so a stereo file is never seen half-written and the one made
    # before stays until the new one is whole.
    unfinished = stereo_file.with_name(f"{stereo_file.name}.unfinished")
    try:
        making = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", recording.mic_track, "-i", recording.system_track]
            + ["-filter_complex", graph, "-map", "[stereo]"]
            + ["-c:a", "flac", "-sample_fmt", "s16", "-f", "flac", unfinished],
            capture_output=True,
            text=True,
        )
        if making.returncode != 0:
            reason = making.stderr.strip().splitlines()[-1:] or ["it stopped with an error"]
            raise StereoFileNotMade(f"ffmpeg could not write it: {reason[0]}")
        os.replace(unfinished, stereo_file)
    finally:
        unfinished.unlink(missing_ok=True)
    return stereo_file


def _channel(channel: int, offset: float, loudness: float) -> str:
    """The ffmpeg filters that turn a Track into channel number `channel` of the stereo file.

    `offset` is how many seconds after the start of the Recording the Track begins, and `loudness` how
    loud the Track is, in LUFS.
    """
    gain = min(TARGET_LOUDNESS - loudness, RAISE_LIMIT)
    filters = [
        f"aresample={SAMPLE_RATE}",
        f"volume={gain:.2f}dB",
        # A limiter: it turns the sound down for the moments that would pass the ceiling, and leaves
        # the rest as it is. `level=false` stops it making up for that by raising everything,
        # and `latency=true` keeps the sound where it was in time.
        f"alimiter=limit={PEAK_CEILING}dB:level=false:latency=true",
    ]
    if silence := round(offset * SAMPLE_RATE):
        # In samples, so that the two channels are lined up to the sample.
        filters.append(f"adelay={silence}S")
    filters.append(f"pan=stereo|c{channel}=c0")
    return ",".join(filters)
