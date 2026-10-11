"""`tools/echo_level.py`: how much of the system track is on the mic track of a Recording."""

import importlib.util
import json
from pathlib import Path

import numpy
from test_stereo import write_track

TOOL = Path(__file__).parent.parent / "tools" / "echo_level.py"
RATE = 48_000


def echo_level(recording: Path):
    """Measure `recording` with the tool, loaded from its file as it is not part of the package."""
    described = importlib.util.spec_from_file_location("echo_level", TOOL)
    tool = importlib.util.module_from_spec(described)
    described.loader.exec_module(tool)
    return tool.measure(recording)


def recording_with(tmp_path: Path, mic: numpy.ndarray, system: numpy.ndarray, starts=(100.0, 100.0)) -> Path:
    recording = tmp_path / "2026-10-10_1946"
    recording.mkdir()
    write_track(recording / "mic.flac", mic)
    write_track(recording / "system.flac", system)
    metadata = {"started": "2026-10-10T19:46:05+02:00", "track_starts": dict(zip(("mic", "system"), starts))}
    (recording / "recording.json").write_text(json.dumps(metadata))
    return recording


def noise(seconds: float, level: float, seed: int) -> numpy.ndarray:
    """Noise at an RMS level of `level` dBFS."""
    return 10 ** (level / 20) * numpy.random.default_rng(seed).standard_normal(round(seconds * RATE))


def test_a_copy_of_the_system_track_on_the_mic_track_is_measured_by_its_level_and_its_lag(tmp_path):
    played = noise(10, -20, seed=1)
    late = round(0.025 * RATE)
    # The microphone hears the room, and what the computer played a quarter as loud and 25 ms later.
    heard = noise(10, -45, seed=2)
    heard[late:] += 0.25 * played[:-late]

    measured = echo_level(recording_with(tmp_path, mic=heard, system=played))

    assert abs(measured.below_system_track - -12.04) < 1  # a quarter of the amplitude is -12.04 dB
    assert abs(measured.lag - 0.025) < 0.001
    assert measured.share_of_mic_track > 0.75  # the room's own noise is the rest


def test_a_mic_track_that_holds_none_of_the_system_track_shows_next_to_none_of_its_energy_as_a_copy(tmp_path):
    measured = echo_level(recording_with(tmp_path, mic=noise(10, -30, seed=3), system=noise(10, -20, seed=4)))

    assert measured.share_of_mic_track < 0.05


def test_the_track_starts_in_the_metadata_are_taken_out_of_the_lag(tmp_path):
    played = noise(10, -20, seed=5)
    heard = 0.5 * played
    # The mic track began 50 ms before the system track, so the same moment sits 50 ms later in it.
    early = round(0.05 * RATE)
    heard = numpy.concatenate([numpy.zeros(early), heard])

    measured = echo_level(recording_with(tmp_path, mic=heard, system=played, starts=(100.0, 100.05)))

    assert abs(measured.lag) < 0.001
