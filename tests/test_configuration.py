"""The configuration file and the flags that override it, driven from the outside: `tldl transcribe` with
stand-in Engines, `tldl record` against the stand-in capture program."""

import json
import signal
from pathlib import Path

import pytest
from test_record import STAND_IN_CAPTURE, finish, reported_path, start_record

from tldl import cli
from tldl.engines import Segment


@pytest.fixture
def configure(home):
    """Writes the given text as the configuration file, `~/.config/tldl/config.toml`; returns its path."""

    def write(text: str) -> Path:
        file = home / ".config" / "tldl" / "config.toml"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return file

    return write


def transcribe(*arguments: str) -> int:
    """Run `tldl transcribe` with the arguments that follow it on the command line."""
    return cli.main(["transcribe", *arguments])


def test_the_engine_flag_chooses_the_engine_for_one_run(make_recording, stand_in):
    recording = make_recording()
    default = stand_in("parakeet-v3")
    chosen = stand_in("stand-in-large", mic=[Segment(1.0, 2.0, "Hello.")])

    exit_status = transcribe("--engine", "stand-in-large")

    assert exit_status == 0
    assert chosen.tracks == [recording / "mic.flac", recording / "system.flac"]
    assert default.tracks == []
    assert "**Me:** Hello." in (recording / "transcript.stand-in-large.md").read_text()


def test_an_unknown_engine_name_fails_with_a_message_listing_the_known_engines(make_recording, stand_in, capsys):
    recording = make_recording()
    stand_in("parakeet-v3")
    stand_in("stand-in-large")

    exit_status = transcribe("--engine", "whisper")

    assert exit_status == 1
    assert "there is no Engine named whisper; the Engines are parakeet-v3, stand-in-large" in capsys.readouterr().err
    assert sorted(file.name for file in recording.iterdir()) == ["mic.flac", "recording.json", "system.flac"]


def test_transcribing_one_recording_with_two_engines_leaves_both_transcripts_side_by_side(make_recording, stand_in):
    recording = make_recording()
    stand_in("parakeet-v3", mic=[Segment(1.0, 2.0, "As the first Engine heard it.")])
    stand_in("stand-in-large", mic=[Segment(1.0, 2.0, "As the second Engine heard it.")])

    transcribe()
    transcribe("--engine", "stand-in-large")

    assert sorted(file.name for file in recording.iterdir()) == [
        "mic.flac",
        "recording.json",
        "segments.parakeet-v3.json",
        "segments.stand-in-large.json",
        "system.flac",
        "transcript.parakeet-v3.md",
        "transcript.stand-in-large.md",
    ]
    assert "As the first Engine heard it." in (recording / "transcript.parakeet-v3.md").read_text()
    assert "As the second Engine heard it." in (recording / "transcript.stand-in-large.md").read_text()
    assert json.loads((recording / "segments.parakeet-v3.json").read_text())["engine"] == "parakeet-v3"
    assert json.loads((recording / "segments.stand-in-large.json").read_text())["engine"] == "stand-in-large"


def test_the_lang_flag_gives_the_language_to_the_engine_and_to_the_transcript_header(make_recording, stand_in):
    recording = make_recording()
    engine = stand_in(mic=[Segment(1.0, 2.0, "Привет.")])

    exit_status = transcribe("--lang", "ru")

    assert exit_status == 0
    assert engine.languages_given == ["ru", "ru"]
    assert engine.detected_on == []
    assert "- Language: ru\n" in (recording / "transcript.parakeet-v3.md").read_text()
    assert json.loads((recording / "segments.parakeet-v3.json").read_text())["language"] == "ru"


def test_the_configuration_file_sets_the_default_engine(make_recording, stand_in, configure):
    recording = make_recording()
    default = stand_in("parakeet-v3")
    configured = stand_in("stand-in-large", mic=[Segment(1.0, 2.0, "Hello.")])
    configure('engine = "stand-in-large"\n')

    exit_status = transcribe()

    assert exit_status == 0
    assert configured.tracks == [recording / "mic.flac", recording / "system.flac"]
    assert default.tracks == []
    assert (recording / "transcript.stand-in-large.md").exists()


def test_the_engine_flag_wins_over_the_configuration_file(make_recording, stand_in, configure):
    recording = make_recording()
    stand_in("parakeet-v3")
    configured = stand_in("stand-in-large")
    flagged = stand_in("stand-in-turbo")
    configure('engine = "stand-in-large"\n')

    transcribe("--engine", "stand-in-turbo")

    assert flagged.tracks == [recording / "mic.flac", recording / "system.flac"]
    assert configured.tracks == []


def test_the_configuration_file_sets_the_default_language(make_recording, stand_in, configure):
    recording = make_recording()
    engine = stand_in(mic=[Segment(1.0, 2.0, "Привет.")])
    configure('language = "ru"\n')

    exit_status = transcribe()

    assert exit_status == 0
    assert engine.languages_given == ["ru", "ru"]
    assert engine.detected_on == []
    assert "- Language: ru\n" in (recording / "transcript.parakeet-v3.md").read_text()


def test_the_lang_flag_wins_over_the_configuration_file(make_recording, stand_in, configure):
    recording = make_recording()
    engine = stand_in(mic=[Segment(1.0, 2.0, "Hello.")])
    configure('language = "ru"\n')

    transcribe("--lang", "en")

    assert engine.languages_given == ["en", "en"]
    assert "- Language: en\n" in (recording / "transcript.parakeet-v3.md").read_text()


def test_transcribe_takes_the_latest_recording_under_the_configured_recordings_root(
    home, make_recording, stand_in, configure
):
    elsewhere = make_recording("2026-10-10_2000", started="2026-10-10T20:00:00+02:00")
    older = make_recording("2026-10-08_0900", root=home / "calls", started="2026-10-08T09:00:00+02:00")
    latest = make_recording("2026-10-09_1000", root=home / "calls", started="2026-10-09T10:00:00+02:00")
    stand_in(mic=[Segment(1.0, 2.0, "Hello.")])
    configure(f'recordings_root = "{home / "calls"}"\n')

    exit_status = transcribe()

    assert exit_status == 0
    assert (latest / "transcript.parakeet-v3.md").exists()
    assert not (older / "transcript.parakeet-v3.md").exists()
    assert not (elsewhere / "transcript.parakeet-v3.md").exists()


def test_record_writes_to_the_configured_recordings_root(home, configure):
    configure('recordings_root = "~/calls"\n')

    record = start_record(home, STAND_IN_CAPTURE, "Sprint planning")
    record.stdout.readline()
    record.send_signal(signal.SIGINT)
    exit_status, output, _ = finish(record)

    assert exit_status == 0
    [recording] = (home / "calls").iterdir()
    assert recording.name.endswith("_sprint-planning")
    assert reported_path(output, "Mic track:") == recording / "mic.flac"
    assert reported_path(output, "System track:") == recording / "system.flac"
    assert not (home / "tldl").exists()


def test_a_configuration_file_that_is_not_toml_fails_with_the_file_and_the_problem(
    make_recording, stand_in, configure, capsys
):
    recording = make_recording()
    engine = stand_in()
    file = configure('language = "ru"\nengine = parakeet-v3\n')

    exit_status = transcribe()

    assert exit_status == 1
    errors = capsys.readouterr().err
    assert f"Cannot read the configuration file {file}: " in errors
    assert "line 2" in errors
    assert engine.tracks == []
    assert not (recording / "transcript.parakeet-v3.md").exists()


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("engine = 3\n", "engine must be text in quotes"),
        ("language = true\n", "language must be text in quotes"),
        ('recordings_root = ["~/calls"]\n', "recordings_root must be text in quotes"),
        (
            'recording_root = "~/calls"\n',
            "there is no key named recording_root; the keys are recordings_root, engine, language",
        ),
        ('[transcribe]\nengine = "parakeet-v3"\n', "there is no key named transcribe"),
    ],
)
def test_a_configuration_file_with_a_key_it_cannot_use_fails_with_the_file_and_the_problem(
    make_recording, stand_in, configure, capsys, text, problem
):
    make_recording()
    engine = stand_in()
    file = configure(text)

    exit_status = transcribe()

    assert exit_status == 1
    assert f"Cannot read the configuration file {file}: {problem}" in capsys.readouterr().err
    assert engine.tracks == []


def test_a_configuration_file_that_cannot_be_opened_fails_with_the_file_and_the_problem(
    home, make_recording, stand_in, capsys
):
    make_recording()
    engine = stand_in()
    file = home / ".config" / "tldl" / "config.toml"
    file.mkdir(parents=True)

    exit_status = transcribe()

    assert exit_status == 1
    assert f"Cannot read the configuration file {file}: Is a directory." in capsys.readouterr().err
    assert engine.tracks == []


def test_a_configuration_file_that_is_not_text_fails_with_the_file_and_the_problem(
    make_recording, stand_in, configure, capsys
):
    make_recording()
    engine = stand_in()
    file = configure("")
    file.write_bytes('language = "ru"\n'.encode("utf-16"))

    exit_status = transcribe()

    assert exit_status == 1
    assert f"Cannot read the configuration file {file}: it is not UTF-8 text." in capsys.readouterr().err
    assert engine.tracks == []


def test_record_fails_before_it_starts_when_the_configuration_file_cannot_be_read(home, configure):
    file = configure("recordings_root = ~/calls\n")

    exit_status, output, errors = finish(start_record(home, STAND_IN_CAPTURE))

    assert exit_status == 1
    assert f"Cannot read the configuration file {file}: " in errors
    assert "Recording" not in output
    assert not (home / "tldl").exists()


def test_with_no_configuration_file_the_built_in_defaults_apply(home, make_recording, stand_in):
    make_recording("2026-10-10_1946")
    engine = stand_in("parakeet-v3", mic=[Segment(1.0, 2.0, "Hello.")])
    stand_in("stand-in-large")

    exit_status = transcribe()

    assert exit_status == 0
    assert not (home / ".config").exists()
    assert (home / "tldl" / "2026-10-10_1946" / "transcript.parakeet-v3.md").exists()
    assert engine.languages_given == [None, None]


def test_an_unknown_engine_name_in_the_configuration_file_fails_with_a_message_listing_the_known_engines(
    make_recording, stand_in, configure, capsys
):
    make_recording()
    engine = stand_in("parakeet-v3")
    configure('engine = "whisper"\n')

    exit_status = transcribe()

    assert exit_status == 1
    assert "there is no Engine named whisper; the Engines are parakeet-v3" in capsys.readouterr().err
    assert engine.tracks == []
