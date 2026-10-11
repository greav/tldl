"""Making a Recording's stereo file from its two Tracks, with `ffmpeg`.

The stereo file is one stereo FLAC at 48 kHz in the Recording folder: the mic track is its left channel,
the system track its right. The Tracks are only read, so the stereo file can always be made again.

Each channel begins where its Track began on the clock the two Tracks share, and the one that ends first
is silent from there to the end, so nothing of either Track is cut.

Each Track is brought to the same loudness on its own, by one change of level for the whole Track: it is
raised or lowered by the difference between the loudness of its loud part and the target.

The loud part is what the Track is listened to for, which on a call is the speech. It is found in the
Track's loudness from moment to moment. The loudest second is set aside, because a knock on the microphone
is louder than the speech and is not what the level should follow; the loud part is every moment of the
rest that lies within a fixed span below the loudest of them. What is quieter does not count, however long
it lasts: a mic track with a few words in an hour of the room's noise is raised as far as the words need,
and the noise with them by no more than that.

A Track is never raised by more than a fixed limit, so one that holds no speech stays quiet. The few
moments that would then pass full scale are turned down by a limiter; nothing clips.
"""

import math
import os
import subprocess
from pathlib import Path

from tldl.recording import Recording, UnreadableMetadata
from tldl.track import (
    LOUDNESS_MOMENTS_A_SECOND,
    UnreadableTrack,
    track_holds_audio,
    track_momentary_loudness,
)

SAMPLE_RATE = 48_000
"""The stereo file's sample rate, in hertz. A Track at another rate is resampled to it."""

TARGET_LOUDNESS = -19.0
"""How loud the loud part of each channel of the stereo file is made, in LUFS."""

LOUD_PART_SPAN = 16.0
"""How far below its loudest moment a Track still counts as loud, in decibels. Speech stays within this
span of itself; the noise of a room lies further below it."""

KNOCK_LENGTH = 1.0
"""How much of a Track, counted from its loudest moment down, is set aside before its loud part is looked
for, in seconds. A knock on the microphone or a cough is that short."""

KNOCK_SHARE = 0.25
"""The most of a Track's sound that is set aside in that way, as a part of the whole: a Track with less
than four seconds of sound in it gives up less than a second."""

SILENCE = -70.0
"""The loudness below which a moment of a Track counts as silent and has no part in the measure, in LUFS."""

RAISE_LIMIT = 20.0
"""The most a Track is raised to reach the target, in decibels. Lowering has no limit."""

PEAK_CEILING = -1.0
"""The level no sample of the stereo file rises above, in dBFS."""


class StereoFileNotMade(Exception):
    """A Recording's stereo file could not be made. The message says why in words fit for the user."""


def make_stereo_file(recording: Recording) -> Path:
    """Make the stereo file of `recording`, in the place of one made before; returns where it is."""
    stereo_file = recording.stereo_file
    try:
        mic_offset, system_offset = recording.track_offsets
        mic_moments = track_momentary_loudness(recording.mic_track)
        system_moments = track_momentary_loudness(recording.system_track)
        # One Track with nothing in it is a silent channel; two are a stereo file with nothing to play.
        # A Track that lasts long enough to have a loudness holds audio, so only shorter ones are asked.
        if not (
            mic_moments
            or system_moments
            or track_holds_audio(recording.mic_track)
            or track_holds_audio(recording.system_track)
        ):
            raise StereoFileNotMade("the Recording holds no audio: both of its Tracks are empty")
    except (UnreadableMetadata, UnreadableTrack) as problem:
        raise StereoFileNotMade(str(problem)) from problem
    mic_loudness = _loudness_of_the_loud_part(mic_moments)
    system_loudness = _loudness_of_the_loud_part(system_moments)
    # Each Track is put into one channel of a stereo sound whose other channel is silent, and the two
    # are added together for as long as the longer one lasts.
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


def _loudness_of_the_loud_part(moments: list[float]) -> float:
    """How loud the loud part of a Track is, in LUFS, given its loudness from moment to moment.

    A Track with no moment above `SILENCE` is that quiet.
    """
    heard = sorted((moment for moment in moments if moment > SILENCE), reverse=True)
    if not heard:
        return SILENCE
    knock = min(round(KNOCK_LENGTH * LOUDNESS_MOMENTS_A_SECOND), int(KNOCK_SHARE * len(heard)))
    lasting = heard[knock:]
    loud = [moment for moment in lasting if moment >= lasting[0] - LOUD_PART_SPAN]
    # Loudness is the logarithm of power, and it is the power that is averaged.
    return 10 * math.log10(sum(10 ** (moment / 10) for moment in loud) / len(loud))


def _channel(channel: int, offset: float, loudness: float) -> str:
    """The ffmpeg filters that turn a Track into channel number `channel` of the stereo file.

    `offset` is how many seconds after the start of the Recording the Track begins, and `loudness` how
    loud its loud part is, in LUFS.
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
