"""`tldl stereo`, driven from the outside on Recordings whose Tracks are short generated sounds."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy
import pytest

from tldl import cli
from tldl.engines import Segment
from tldl.stereo_file import PEAK_CEILING, RAISE_LIMIT, TARGET_LOUDNESS

RATE = 48_000
"""The stereo file's sample rate, in hertz."""

INTERRUPTED_TRACK = Path(__file__).parent / "audio" / "interrupted-track.flac"
"""A system track left by a capture program that was killed after four seconds with nothing playing.

Its header gives no length; 3.744 s of it decode.
"""


def stereo(*arguments: str) -> int:
    """Run `tldl stereo` with the arguments that follow it on the command line."""
    return cli.main(["stereo", *arguments])


def tone(seconds: float, *, hz: float = 1000, level: float = -20, rate: int = RATE) -> numpy.ndarray:
    """A steady tone. `level` is its RMS level in dBFS, which for a tone at 1 kHz is also its loudness
    in LUFS."""
    moments = numpy.arange(round(seconds * rate)) / rate
    return 10 ** (level / 20) * numpy.sqrt(2) * numpy.sin(2 * numpy.pi * hz * moments)


def write_track(track: Path, sound: numpy.ndarray, rate: int = RATE) -> None:
    """Write `sound` as a Track: mono FLAC at `rate`, 16 bits a sample, as the capture program leaves one."""
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "f32le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0"]
        + ["-c:a", "flac", "-sample_fmt", "s16", track],
        input=sound.astype("<f4").tobytes(),
        check=True,
    )


def format_of(audio_file: Path) -> dict:
    """What kind of audio file `audio_file` is, in ffprobe's words."""
    probed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,channels,sample_rate"]
        + ["-of", "json", audio_file],
        capture_output=True,
        text=True,
        check=True,
    )
    (stream,) = json.loads(probed.stdout)["streams"]
    return stream


def channels_of(stereo_file: Path) -> tuple[numpy.ndarray, numpy.ndarray]:
    """The left and the right channel of a stereo file, each as samples between -1 and 1."""
    decoded = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", stereo_file, "-f", "f32le", "pipe:1"],
        capture_output=True,
        check=True,
    )
    samples = numpy.frombuffer(decoded.stdout, "<f4").reshape(-1, 2)
    return samples[:, 0], samples[:, 1]


@pytest.fixture
def recording_of(make_recording):
    """Puts a Recording under `~/tldl/` whose mic track and system track hold the given sounds; returns
    its folder. A sound is samples at 48 kHz, or a pair of samples and their sample rate."""

    def make(mic, system, **how) -> Path:
        recording = make_recording(**how)
        for track, sound in (("mic.flac", mic), ("system.flac", system)):
            write_track(recording / track, *(sound if isinstance(sound, tuple) else (sound,)))
        return recording

    return make


def test_stereo_leaves_one_stereo_flac_at_48_khz_in_the_recording_folder(recording_of):
    recording = recording_of(mic=tone(1), system=tone(1))

    exit_status = stereo()

    assert exit_status == 0
    assert format_of(recording / "stereo.flac") == {"codec_name": "flac", "channels": 2, "sample_rate": "48000"}


def pitch_of(sound: numpy.ndarray) -> float:
    """The frequency that carries most of `sound`, in hertz."""
    spectrum = numpy.abs(numpy.fft.rfft(sound))
    return float(numpy.fft.rfftfreq(len(sound), 1 / RATE)[spectrum.argmax()])


def test_the_mic_track_is_the_left_channel_and_the_system_track_the_right(recording_of):
    recording = recording_of(mic=tone(1, hz=440), system=tone(1, hz=1000))

    stereo()

    left, right = channels_of(recording / "stereo.flac")
    assert pitch_of(left) == pytest.approx(440, abs=2)
    assert pitch_of(right) == pytest.approx(1000, abs=2)


def test_stereo_with_no_argument_takes_the_recording_that_started_last(make_recording):
    older = make_recording("2026-10-08_0900", started="2026-10-08T09:00:00+02:00")
    latest = make_recording("2026-10-09_1000", started="2026-10-09T10:00:00+02:00")

    exit_status = stereo()

    assert exit_status == 0
    assert (latest / "stereo.flac").exists()
    assert not (older / "stereo.flac").exists()


@pytest.mark.parametrize("how_it_is_named", ["by its name", "by its folder"])
def test_stereo_with_an_argument_takes_the_recording_named(make_recording, how_it_is_named):
    older = make_recording("2026-10-08_0900", started="2026-10-08T09:00:00+02:00")
    latest = make_recording("2026-10-09_1000", started="2026-10-09T10:00:00+02:00")

    exit_status = stereo(older.name if how_it_is_named == "by its name" else str(older))

    assert exit_status == 0
    assert (older / "stereo.flac").exists()
    assert not (latest / "stereo.flac").exists()


def level_of(sound: numpy.ndarray) -> float:
    """The RMS level of `sound` in dBFS; digital silence is minus infinity."""
    with numpy.errstate(divide="ignore"):
        return float(20 * numpy.log10(numpy.sqrt(numpy.mean(numpy.square(sound, dtype=numpy.float64)))))


def peak_of(sound: numpy.ndarray) -> float:
    """The level of the highest sample of `sound`, in dBFS."""
    return float(20 * numpy.log10(numpy.abs(sound).max()))


def seconds(sound: numpy.ndarray, start: float, end: float) -> numpy.ndarray:
    """The part of a channel of a stereo file from `start` to `end`, in seconds from its beginning."""
    return sound[round(start * RATE) : round(end * RATE)]


def test_tracks_at_different_sample_rates_each_come_out_as_long_as_they_were(recording_of):
    recording = recording_of(
        mic=(tone(1.5, hz=440, rate=24_000), 24_000),
        system=(tone(2.5, hz=1000, rate=48_000), 48_000),
    )

    stereo()

    left, right = channels_of(recording / "stereo.flac")
    assert len(left) == len(right) == 2.5 * RATE
    assert pitch_of(seconds(left, 0, 1.5)) == pytest.approx(440, abs=2)
    assert level_of(seconds(left, 1.4, 1.5)) == pytest.approx(level_of(seconds(left, 0, 0.1)), abs=0.5)
    assert not seconds(left, 1.5, 2.5).any()
    assert pitch_of(right) == pytest.approx(1000, abs=2)
    assert level_of(seconds(right, 2.4, 2.5)) == pytest.approx(level_of(seconds(right, 0, 0.1)), abs=0.5)


def beep_at(start: float, *, of: float, rate: int = RATE) -> numpy.ndarray:
    """`of` seconds of silence with a tone a tenth of a second long beginning `start` seconds in."""
    sound = numpy.zeros(round(of * rate))
    beep = tone(0.1, rate=rate)
    sound[round(start * rate) : round(start * rate) + len(beep)] = beep
    return sound


def onset_in(sound: numpy.ndarray) -> float:
    """When the loudest thing in a channel of a stereo file begins, in seconds from its beginning."""
    return float(numpy.flatnonzero(numpy.abs(sound) > numpy.abs(sound).max() / 2)[0]) / RATE


@pytest.mark.parametrize(
    "mic_start, system_start, mic_beep, system_beep, beep_in_the_stereo_file",
    [
        # The mic track began a quarter of a second after the system track, so what both captured
        # at one moment is a quarter of a second earlier on the mic track.
        (100.25, 100.0, 0.75, 1.0, 1.0),
        (100.0, 100.4, 1.0, 0.6, 1.0),
    ],
)
def test_a_sound_captured_at_one_moment_on_both_tracks_lands_at_one_moment_in_both_channels(
    recording_of, mic_start, system_start, mic_beep, system_beep, beep_in_the_stereo_file
):
    recording = recording_of(
        mic=(beep_at(mic_beep, of=2, rate=24_000), 24_000),
        system=beep_at(system_beep, of=2),
        track_starts=(mic_start, system_start),
    )

    stereo()

    left, right = channels_of(recording / "stereo.flac")
    assert onset_in(left) == pytest.approx(beep_in_the_stereo_file, abs=0.001)
    assert onset_in(right) == pytest.approx(beep_in_the_stereo_file, abs=0.001)


def test_with_no_track_starts_in_the_metadata_both_tracks_begin_at_the_same_moment(recording_of):
    recording = recording_of(
        mic=beep_at(0.5, of=1), system=beep_at(0.75, of=2), track_starts=(None, None)
    )

    exit_status = stereo()

    assert exit_status == 0
    left, right = channels_of(recording / "stereo.flac")
    assert onset_in(left) == pytest.approx(0.5, abs=0.001)
    assert onset_in(right) == pytest.approx(0.75, abs=0.001)


def test_an_interrupted_recording_gets_a_stereo_file(recording_of):
    # What a Recording is when it was killed, not stopped: the metadata file holds no Track starts, and
    # the Tracks' headers give no length.
    recording = recording_of(mic=tone(1, hz=440), system=tone(1), track_starts=(None, None))
    shutil.copy(INTERRUPTED_TRACK, recording / "system.flac")

    exit_status = stereo()

    assert exit_status == 0
    left, right = channels_of(recording / "stereo.flac")
    assert len(left) == len(right) == 3.744 * RATE
    assert pitch_of(seconds(left, 0, 1)) == pytest.approx(440, abs=2)


def test_nothing_of_either_track_is_cut_and_the_channel_that_ends_first_is_silent_to_the_end(recording_of):
    # The mic track begins a second and a half into the system track and outlasts it by half a second.
    recording = recording_of(mic=tone(1, hz=440), system=tone(2), track_starts=(101.5, 100.0))

    stereo()

    left, right = channels_of(recording / "stereo.flac")
    assert len(left) == len(right) == 2.5 * RATE
    assert not seconds(left, 0, 1.5).any()
    assert level_of(seconds(left, 2.4, 2.5)) == pytest.approx(level_of(seconds(left, 1.5, 1.6)), abs=0.5)
    assert level_of(seconds(right, 1.9, 2.0)) == pytest.approx(level_of(seconds(right, 0, 0.1)), abs=0.5)
    assert not seconds(right, 2.0, 2.5).any()


def test_a_quiet_track_and_a_loud_track_come_out_at_the_same_loudness(recording_of):
    recording = recording_of(mic=tone(2, level=-35), system=tone(2, level=-8))

    stereo()

    left, right = channels_of(recording / "stereo.flac")
    assert level_of(left) == pytest.approx(TARGET_LOUDNESS, abs=0.5)
    assert level_of(right) == pytest.approx(TARGET_LOUDNESS, abs=0.5)


def test_a_track_that_is_mostly_silence_is_made_as_loud_as_the_sound_in_it(recording_of):
    a_few_words = numpy.zeros(10 * RATE)
    a_few_words[4 * RATE : 6 * RATE] = tone(2, level=-35)
    recording = recording_of(mic=a_few_words, system=tone(10, level=-8))

    stereo()

    left, right = channels_of(recording / "stereo.flac")
    assert level_of(seconds(left, 4.5, 5.5)) == pytest.approx(TARGET_LOUDNESS, abs=1)
    assert level_of(right) == pytest.approx(TARGET_LOUDNESS, abs=0.5)


def noise(seconds: float, *, level: float) -> numpy.ndarray:
    """A steady hiss, the same every time. `level` is its RMS level in dBFS."""
    return numpy.random.default_rng(0).normal(0, 10 ** (level / 20), round(seconds * RATE))


def test_a_track_with_nothing_but_faint_noise_is_raised_by_no_more_than_the_limit(recording_of):
    recording = recording_of(mic=noise(2, level=-60), system=tone(2))

    stereo()

    left, _ = channels_of(recording / "stereo.flac")
    assert level_of(left) == pytest.approx(-60 + RAISE_LIMIT, abs=0.5)
    assert level_of(left) < TARGET_LOUDNESS - 10


def test_a_track_raised_past_full_scale_does_not_clip(recording_of):
    # A quiet tone with one loud moment in it: the tone needs raising by much more than the 3 dB the
    # loud moment has left under full scale.
    quiet_with_a_loud_moment = tone(3, level=-35)
    quiet_with_a_loud_moment[RATE : RATE + 96] = tone(0.002, level=-6)
    recording = recording_of(mic=quiet_with_a_loud_moment, system=tone(3))

    stereo()

    left, _ = channels_of(recording / "stereo.flac")
    assert level_of(seconds(left, 0, 0.9)) > -35 + 6
    assert level_of(seconds(left, 2, 3)) == pytest.approx(level_of(seconds(left, 0, 0.9)), abs=0.1)
    assert peak_of(left) <= PEAK_CEILING + 0.01


def test_the_two_tracks_are_unchanged_byte_for_byte(recording_of):
    recording = recording_of(mic=(tone(1, level=-35, rate=24_000), 24_000), system=tone(2, level=-8))
    mic_track = (recording / "mic.flac").read_bytes()
    system_track = (recording / "system.flac").read_bytes()

    stereo()

    assert (recording / "mic.flac").read_bytes() == mic_track
    assert (recording / "system.flac").read_bytes() == system_track


def test_making_the_stereo_file_again_replaces_it(recording_of):
    recording = recording_of(mic=tone(1, hz=440), system=tone(1))
    stereo()
    write_track(recording / "mic.flac", tone(2, hz=660))

    exit_status = stereo()

    assert exit_status == 0
    left, _ = channels_of(recording / "stereo.flac")
    assert len(left) == 2 * RATE
    assert pitch_of(left) == pytest.approx(660, abs=2)
    assert sorted(file.name for file in recording.iterdir()) == [
        "mic.flac",
        "recording.json",
        "stereo.flac",
        "system.flac",
    ]


def test_stereo_says_which_recording_it_took_and_where_the_stereo_file_is(recording_of, capsys):
    recording = recording_of(mic=tone(1), system=tone(1), name="2026-10-10_1946_sprint-planning")

    stereo()

    assert capsys.readouterr().out == (
        "Making the stereo file of 2026-10-10_1946_sprint-planning.\n"
        f"Stereo file: {recording / 'stereo.flac'}\n"
    )


@pytest.mark.parametrize("track", ["mic.flac", "system.flac"])
def test_stereo_fails_when_a_track_is_missing_naming_the_recording_and_the_problem(recording_of, capsys, track):
    recording = recording_of(mic=tone(1), system=tone(1), name="2026-10-10_1946_sprint-planning")
    (recording / track).unlink()

    exit_status = stereo()

    assert exit_status == 1
    assert capsys.readouterr().err == (
        "Cannot make the stereo file of 2026-10-10_1946_sprint-planning: "
        f"could not read {recording / track}: No such file or directory.\n"
    )
    assert not (recording / "stereo.flac").exists()


@pytest.mark.parametrize("track", ["mic.flac", "system.flac"])
@pytest.mark.parametrize(
    "what_the_track_holds, reason", [("not audio", "ffmpeg could not decode it"), ("", "the file is empty")]
)
def test_stereo_fails_when_a_track_cannot_be_read_naming_the_recording_and_the_problem(
    recording_of, capsys, track, what_the_track_holds, reason
):
    recording = recording_of(mic=tone(1), system=tone(1), name="2026-10-10_1946_sprint-planning")
    (recording / track).write_text(what_the_track_holds)

    exit_status = stereo()

    assert exit_status == 1
    assert capsys.readouterr().err == (
        "Cannot make the stereo file of 2026-10-10_1946_sprint-planning: "
        f"could not read {recording / track}: {reason}.\n"
    )
    assert sorted(file.name for file in recording.iterdir()) == ["mic.flac", "recording.json", "system.flac"]


@pytest.mark.parametrize(
    "track_starts, problem",
    [
        (("soon", 100.0), 'gives the start of the mic track as "soon", which is not a number'),
        ((100.0, [100.0]), "gives the start of the system track as [100.0], which is not a number"),
        ((float("nan"), 100.0), "gives the start of the mic track as NaN, which is not a number"),
    ],
)
def test_stereo_fails_when_a_track_start_in_the_metadata_file_is_not_a_number_naming_the_file_and_the_problem(
    recording_of, capsys, track_starts, problem
):
    recording = recording_of(
        mic=tone(1), system=tone(1), name="2026-10-10_1946_sprint-planning", track_starts=track_starts
    )

    exit_status = stereo()

    assert exit_status == 1
    assert capsys.readouterr().err == (
        "Cannot make the stereo file of 2026-10-10_1946_sprint-planning: "
        f"the metadata file {recording / 'recording.json'} {problem}.\n"
    )
    assert not (recording / "stereo.flac").exists()


def test_stereo_fails_when_the_track_starts_in_the_metadata_file_are_not_a_start_for_each_track(recording_of, capsys):
    recording = recording_of(mic=tone(1), system=tone(1), name="2026-10-10_1946_sprint-planning")
    metadata = json.loads((recording / "recording.json").read_text())
    (recording / "recording.json").write_text(json.dumps({**metadata, "track_starts": [100.0, 100.25]}))

    exit_status = stereo()

    assert exit_status == 1
    assert capsys.readouterr().err == (
        "Cannot make the stereo file of 2026-10-10_1946_sprint-planning: "
        f"the metadata file {recording / 'recording.json'} gives the Track starts as [100.0, 100.25],"
        " which is not a start for each Track.\n"
    )
    assert not (recording / "stereo.flac").exists()


def test_stereo_fails_when_there_is_no_recording_of_that_name(make_recording, capsys):
    recording = make_recording("2026-10-10_1946")

    exit_status = stereo("2026-10-11_0900")

    assert exit_status == 1
    assert "Cannot make the stereo file: there is no Recording named 2026-10-11_0900" in capsys.readouterr().err
    assert not (recording / "stereo.flac").exists()


def test_stereo_fails_when_there_are_no_recordings(home, capsys):
    exit_status = stereo()

    assert exit_status == 1
    assert f"Cannot make the stereo file: there are no Recordings under {home / 'tldl'}" in capsys.readouterr().err


def test_stereo_fails_with_the_reason_when_ffmpeg_is_missing(recording_of, monkeypatch, capsys):
    recording = recording_of(mic=tone(1), system=tone(1))
    monkeypatch.setenv("PATH", str(recording))

    exit_status = stereo()

    assert exit_status == 1
    assert "ffmpeg is needed to read the Tracks" in capsys.readouterr().err
    assert not (recording / "stereo.flac").exists()


FFMPEG_THAT_CANNOT_FINISH_A_FILE = '''#!{python}
"""Stands in for ffmpeg: reads as ffmpeg does, but a file it is told to write into the folder given
below, beside the Tracks, is left half-written, and the run fails as on a full disk."""
import subprocess
import sys
from pathlib import Path

arguments = sys.argv[1:]
run = subprocess.run(["{ffmpeg}", *arguments])
written = [
    Path(argument)
    for argument in arguments
    if Path(argument).parent == Path("{folder}") and Path(argument).name not in ("mic.flac", "system.flac")
]
if not written:
    sys.exit(run.returncode)
for file in written:
    file.write_bytes(file.read_bytes()[: file.stat().st_size // 2])
print("Error writing trailer: No space left on device", file=sys.stderr)
sys.exit(228)
'''


@pytest.fixture
def ffmpeg_cannot_finish_a_file_in(tmp_path, monkeypatch):
    """From now on, `ffmpeg` fails part-way through any file it writes into the given Recording folder."""

    def put(recording: Path) -> None:
        stand_in = tmp_path / "stand-in-ffmpeg" / "ffmpeg"
        stand_in.parent.mkdir()
        stand_in.write_text(
            FFMPEG_THAT_CANNOT_FINISH_A_FILE.format(python=sys.executable, ffmpeg=shutil.which("ffmpeg"), folder=recording)
        )
        stand_in.chmod(0o755)
        monkeypatch.setenv("PATH", str(stand_in.parent), prepend=":")

    return put


def test_a_failure_part_way_leaves_no_half_written_stereo_file(recording_of, ffmpeg_cannot_finish_a_file_in, capsys):
    recording = recording_of(mic=tone(1), system=tone(1))
    ffmpeg_cannot_finish_a_file_in(recording)

    exit_status = stereo()

    assert exit_status == 1
    assert (
        f"Cannot make the stereo file of {recording.name}: ffmpeg could not write it: "
        "Error writing trailer: No space left on device.\n"
    ) in capsys.readouterr().err
    assert sorted(file.name for file in recording.iterdir()) == ["mic.flac", "recording.json", "system.flac"]


def test_a_failure_part_way_leaves_the_stereo_file_made_before_as_it_was(recording_of, ffmpeg_cannot_finish_a_file_in):
    recording = recording_of(mic=tone(1), system=tone(1))
    stereo()
    made_before = (recording / "stereo.flac").read_bytes()
    ffmpeg_cannot_finish_a_file_in(recording)

    exit_status = stereo()

    assert exit_status == 1
    assert (recording / "stereo.flac").read_bytes() == made_before
    assert sorted(file.name for file in recording.iterdir()) == [
        "mic.flac",
        "recording.json",
        "stereo.flac",
        "system.flac",
    ]


def test_transcribe_gives_the_same_transcript_for_a_recording_with_a_stereo_file_as_for_one_without(
    recording_of, stand_in
):
    recording = recording_of(mic=tone(1), system=tone(4), track_starts=(100.5, 100.0))
    engine = stand_in(mic=[Segment(0.2, 0.8, "Hi.")], system=[Segment(1.5, 2.5, "Hello everyone.")])
    transcript, segments_file = recording / "transcript.parakeet-v3.md", recording / "segments.parakeet-v3.json"
    cli.main(["transcribe"])
    without_a_stereo_file = transcript.read_text(), segments_file.read_text()
    stereo()

    exit_status = cli.main(["transcribe"])

    assert exit_status == 0
    assert (transcript.read_text(), segments_file.read_text()) == without_a_stereo_file
    assert engine.detected_on[-1] == engine.tracks[-2:] == [recording / "mic.flac", recording / "system.flac"]
