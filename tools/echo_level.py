"""How much of the system track is on the mic track of a Recording.

    uv run python tools/echo_level.py <recording-folder> [<recording-folder> ...]

On loudspeakers the microphone hears what the computer plays, so the mic track holds a copy of the system
track; a headset can leak one through its cable. For each Recording this prints how far below the system
track that copy is, how much of the mic track's energy it makes up, how late it arrives, and its level in
four frequency bands. A copy that came through the air is coloured, band to band; one that came through a
cable is even.

Two limits of the estimate. With no copy at all the level does not fall to nothing: it settles on a floor
that is lower the longer the Recording and the quieter the mic track, so judge "no copy" by the share of the
mic track's energy, which is then a percent or two. And a copy that arrives late reads a little low, about
half a dB at 25 ms.

The Recordings are only read. `ffmpeg` and `numpy` are needed.
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy

RATE = 16_000
"""The rate both Tracks are compared at, in hertz: speech lies under half of it."""

WINDOW = 4096
STEP = 1024
SPEECH = (100, 7000)
BANDS = ((100, 300), (300, 1000), (1000, 3000), (3000, 7000))


@dataclass(frozen=True)
class EchoLevel:
    """What of the system track is on the mic track of one Recording."""

    below_system_track: float
    """The copy's level against the system track's own, in dB; negative when the copy is quieter."""
    share_of_mic_track: float
    """The part of the mic track's energy that is the copy, from 0 to 1."""
    lag: float
    """How long after the system track the copy arrives, in seconds, with the Tracks' starts allowed for."""
    bands: dict[tuple[int, int], float]
    """`below_system_track` for each frequency band, keyed by the band's edges in hertz."""


def measure(recording: Path) -> EchoLevel:
    """Measure the copy of the system track on the mic track of the Recording in `recording`."""
    mic, system = _decoded(recording / "mic.flac"), _decoded(recording / "system.flac")
    later = round(_system_track_starts_later_by(recording) * RATE)
    if later > 0:
        mic = mic[later:]
    else:
        system = system[-later:]
    length = min(len(mic), len(system))
    mic, system = mic[:length], system[:length]

    # One filter that turns the system track into its copy on the mic track, estimated band by band.
    shape = numpy.hanning(WINDOW)
    system_power = mic_power = cross = 0
    for start in range(0, length - WINDOW, STEP):
        played = numpy.fft.rfft(system[start : start + WINDOW] * shape)
        heard = numpy.fft.rfft(mic[start : start + WINDOW] * shape)
        system_power = system_power + numpy.abs(played) ** 2
        mic_power = mic_power + numpy.abs(heard) ** 2
        cross = cross + numpy.conj(played) * heard
    filter_ = cross / (system_power + 1e-12)
    copy_power = numpy.abs(filter_) ** 2 * system_power
    hertz = numpy.fft.rfftfreq(WINDOW, 1 / RATE)

    def within(low: int, high: int) -> numpy.ndarray:
        return (hertz >= low) & (hertz < high)

    def below(band: numpy.ndarray) -> float:
        return 10 * numpy.log10(max(copy_power[band].sum() / system_power[band].sum(), 1e-20))

    speech = within(*SPEECH)
    response = numpy.fft.irfft(filter_)
    peak = int(numpy.argmax(numpy.abs(response)))
    return EchoLevel(
        below_system_track=below(speech),
        share_of_mic_track=float(copy_power[speech].sum() / mic_power[speech].sum()),
        lag=(peak if peak < WINDOW // 2 else peak - WINDOW) / RATE,
        bands={band: below(within(*band)) for band in BANDS},
    )


def _decoded(track: Path) -> numpy.ndarray:
    decoding = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", track, "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    )
    return numpy.frombuffer(decoding.stdout, dtype="<f4").astype(numpy.float64)


def _system_track_starts_later_by(recording: Path) -> float:
    """Seconds between the two Tracks' starts; zero when the metadata does not give both."""
    starts = json.loads((recording / "recording.json").read_text()).get("track_starts") or {}
    mic, system = starts.get("mic"), starts.get("system")
    return system - mic if mic is not None and system is not None else 0.0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    for folder in map(Path, sys.argv[1:]):
        level = measure(folder)
        print(folder.name)
        print(f"  the system track on the mic track: {level.below_system_track:6.1f} dB against the system track")
        print(f"  share of the mic track's energy:   {100 * level.share_of_mic_track:6.1f} %")
        print(f"  arrives later by:                  {1000 * level.lag:6.1f} ms")
        for (low, high), below in level.bands.items():
            print(f"    {low:>4}-{high:<4} Hz: {below:6.1f} dB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
