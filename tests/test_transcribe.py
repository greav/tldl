"""`tldl transcribe`, driven from the outside with a stand-in Engine in place of the default Engine."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tldl import cli
from tldl.engines import Segment

INTERRUPTED_TRACK = Path(__file__).parent / "audio" / "interrupted-track.flac"
"""A system track left by a capture program that was killed after four seconds with nothing playing.

Its header gives no length; 3.744 s of it decode.
"""


def transcribe(*arguments: str) -> int:
    """Run `tldl transcribe` with the arguments that follow it on the command line."""
    return cli.main(["transcribe", *arguments])


def lines_of(transcript: Path) -> list[str]:
    """The lines of a Transcript that carry a timecode."""
    return [line for line in transcript.read_text().splitlines() if line.startswith("[")]


def test_transcribe_writes_a_transcript_with_a_timecode_and_a_speaker_on_each_line(make_recording, stand_in):
    recording = make_recording()
    stand_in(
        mic=[Segment(4.0, 5.5, "Hi, can you hear me?")],
        system=[Segment(1.0, 2.5, "Hello everyone."), Segment(3725.2, 3727.0, "Loud and clear.")],
    )

    exit_status = transcribe()

    assert exit_status == 0
    assert lines_of(recording / "transcript.whisper-large-v3.md") == [
        "[00:00:01] **Others:** Hello everyone.",
        "[00:00:04] **Me:** Hi, can you hear me?",
        "[01:02:05] **Others:** Loud and clear.",
    ]


def test_the_transcript_opens_with_a_header_giving_the_date_start_time_and_duration(make_recording, stand_in):
    # The system track begins 2 s after the mic track and runs for 64 s: the Recording is 66 s long.
    recording = make_recording(
        "2026-10-10_1946_sprint-planning",
        started="2026-10-10T19:46:05+02:00",
        track_starts=(100.0, 102.0),
        mic_seconds=3,
        system_seconds=64,
    )
    stand_in(system=[Segment(1.0, 2.5, "Hello everyone.")])

    transcribe()

    assert (recording / "transcript.whisper-large-v3.md").read_text() == (
        "# 2026-10-10_1946_sprint-planning\n"
        "\n"
        "- Date: 2026-10-10\n"
        "- Start time: 19:46\n"
        "- Duration: 00:01:06\n"
        "\n"
        "[00:00:03] **Others:** Hello everyone.\n"
    )


def test_lines_of_both_tracks_are_in_the_order_spoken_whichever_track_began_first(make_recording, stand_in):
    # The mic track begins 2.5 s after the system track, so its Segment at 1 s was spoken at 3.5 s.
    recording = make_recording(track_starts=(102.5, 100.0))
    stand_in(
        mic=[Segment(1.0, 2.0, "Second."), Segment(9.0, 10.0, "Fourth.")],
        system=[Segment(3.0, 3.4, "First."), Segment(4.0, 5.0, "Third.")],
    )

    transcribe()

    assert lines_of(recording / "transcript.whisper-large-v3.md") == [
        "[00:00:03] **Others:** First.",
        "[00:00:03] **Me:** Second.",
        "[00:00:04] **Others:** Third.",
        "[00:00:11] **Me:** Fourth.",
    ]


def test_consecutive_segments_of_one_speaker_are_joined_into_one_line(make_recording, stand_in):
    recording = make_recording()
    stand_in(
        mic=[Segment(20.0, 21.0, "Sounds good.")],
        system=[
            Segment(5.0, 7.0, "First we look at the numbers."),
            Segment(7.5, 9.0, "Then at the plan."),
            Segment(30.0, 31.0, "Great."),
            Segment(32.0, 33.0, "See you."),
        ],
    )

    transcribe()

    assert lines_of(recording / "transcript.whisper-large-v3.md") == [
        "[00:00:05] **Others:** First we look at the numbers. Then at the plan.",
        "[00:00:20] **Me:** Sounds good.",
        "[00:00:30] **Others:** Great. See you.",
    ]


def test_a_long_pause_in_one_speakers_speech_starts_a_new_line_with_its_own_timecode_and_speaker(
    make_recording, stand_in
):
    recording = make_recording()
    stand_in(
        system=[
            Segment(5.0, 7.0, "First we look at the numbers."),
            Segment(7.5, 9.0, "Then at the plan."),
            Segment(30.0, 31.0, "That is all from me."),
        ]
    )

    transcribe()

    assert (recording / "transcript.whisper-large-v3.md").read_text().endswith(
        "\n"
        "[00:00:05] **Others:** First we look at the numbers. Then at the plan.\n"
        "\n"
        "[00:00:30] **Others:** That is all from me.\n"
    )


def test_a_track_with_no_speech_contributes_no_lines(make_recording, stand_in):
    recording = make_recording()
    stand_in(mic=[], system=[Segment(1.0, 2.0, "Is anyone there?")])

    transcribe()

    assert lines_of(recording / "transcript.whisper-large-v3.md") == ["[00:00:01] **Others:** Is anyone there?"]


def test_the_segments_file_holds_every_segment_of_both_tracks_with_its_speaker(make_recording, stand_in):
    recording = make_recording(track_starts=(100.0, 100.5), mic_seconds=3, system_seconds=10)
    stand_in(
        mic=[Segment(4.0, 5.5, "Привет, слышно меня?")],
        system=[Segment(1.0, 2.5, "Hello everyone."), Segment(2.75, 3.0, "Shall we start?")],
    )

    transcribe()

    assert json.loads((recording / "segments.whisper-large-v3.json").read_text()) == {
        "engine": "whisper-large-v3",
        "language": None,
        "duration": 10.5,
        "segments": [
            {"speaker": "Others", "start": 1.5, "end": 3.0, "text": "Hello everyone.", "echo": False},
            {"speaker": "Others", "start": 3.25, "end": 3.5, "text": "Shall we start?", "echo": False},
            {"speaker": "Me", "start": 4.0, "end": 5.5, "text": "Привет, слышно меня?", "echo": False},
        ],
    }


def test_an_echo_is_left_out_of_the_transcript_and_marked_in_the_segments_file(make_recording, stand_in):
    # On loudspeakers the microphone heard the others: their words are on the mic track as well.
    recording = make_recording()
    stand_in(
        mic=[Segment(1.2, 2.6, "Hello everyone, shall we start?"), Segment(4.0, 5.5, "Yes, let's start.")],
        system=[Segment(1.0, 2.5, "Hello everyone, shall we start?")],
    )

    transcribe()

    assert lines_of(recording / "transcript.whisper-large-v3.md") == [
        "[00:00:01] **Others:** Hello everyone, shall we start?",
        "[00:00:04] **Me:** Yes, let's start.",
    ]
    assert json.loads((recording / "segments.whisper-large-v3.json").read_text())["segments"] == [
        {"speaker": "Others", "start": 1.0, "end": 2.5, "text": "Hello everyone, shall we start?", "echo": False},
        {"speaker": "Me", "start": 1.2, "end": 2.6, "text": "Hello everyone, shall we start?", "echo": True},
        {"speaker": "Me", "start": 4.0, "end": 5.5, "text": "Yes, let's start.", "echo": False},
    ]


def test_the_engine_is_given_the_two_tracks_of_the_recording(make_recording, stand_in):
    recording = make_recording()
    engine = stand_in()

    transcribe()

    assert engine.tracks == [recording / "mic.flac", recording / "system.flac"]


def test_the_header_gives_no_language_when_the_engine_detected_none(make_recording, stand_in):
    recording = make_recording()
    stand_in(mic=[Segment(1.0, 2.0, "Hello.")])

    transcribe()

    assert "Language" not in (recording / "transcript.whisper-large-v3.md").read_text()
    assert json.loads((recording / "segments.whisper-large-v3.json").read_text())["language"] is None


def test_the_header_gives_the_language_the_engine_detected(make_recording, stand_in):
    recording = make_recording()
    stand_in(mic=[Segment(1.0, 2.0, "Привет.")], language="ru")

    transcribe()

    assert "- Duration: 00:00:03\n- Language: ru\n" in (recording / "transcript.whisper-large-v3.md").read_text()
    assert json.loads((recording / "segments.whisper-large-v3.json").read_text())["language"] == "ru"


def test_the_language_is_detected_once_on_both_tracks_together_and_each_is_recognised_in_it(
    make_recording, stand_in
):
    recording = make_recording()
    engine = stand_in(mic=[Segment(1.0, 2.0, "Привет.")], language="ru")

    transcribe()

    assert engine.detected_on == [[recording / "mic.flac", recording / "system.flac"]]
    assert engine.languages_given == ["ru", "ru"]


def test_transcribe_with_no_argument_takes_the_recording_that_started_last(make_recording, stand_in):
    older = make_recording("2026-10-09_1000", started="2026-10-09T10:00:12+02:00")
    # Two Recordings of the same minute: their names order them by title, their start times do not.
    earlier = make_recording("2026-10-10_1946_zeta", started="2026-10-10T19:46:05+02:00")
    latest = make_recording("2026-10-10_1946_alpha", started="2026-10-10T19:46:40+02:00")
    (latest.parent / "not-a-recording").mkdir()
    (latest.parent / ".DS_Store").write_text("")
    stand_in(mic=[Segment(1.0, 2.0, "Hello.")])

    exit_status = transcribe()

    assert exit_status == 0
    assert (latest / "transcript.whisper-large-v3.md").exists()
    assert not (earlier / "transcript.whisper-large-v3.md").exists()
    assert not (older / "transcript.whisper-large-v3.md").exists()


@pytest.mark.parametrize("how_it_is_named", ["by its name", "by its folder"])
def test_transcribe_with_an_argument_takes_the_recording_named(make_recording, stand_in, how_it_is_named):
    named = make_recording("2026-10-09_1000_retro", started="2026-10-09T10:00:12+02:00")
    latest = make_recording("2026-10-10_1946", started="2026-10-10T19:46:05+02:00")
    stand_in(mic=[Segment(1.0, 2.0, "Hello.")])

    exit_status = transcribe(named.name if how_it_is_named == "by its name" else str(named))

    assert exit_status == 0
    assert (named / "transcript.whisper-large-v3.md").exists()
    assert (named / "segments.whisper-large-v3.json").exists()
    assert not (latest / "transcript.whisper-large-v3.md").exists()


@pytest.mark.parametrize(
    ("run_from", "argument"),
    [
        ("2026-10-09_1000_retro", "."),
        ("2026-10-10_1946", "../2026-10-09_1000_retro"),
        ("..", "tldl/2026-10-09_1000_retro"),
    ],
)
def test_transcribe_takes_a_relative_path_to_the_recordings_folder(
    make_recording, stand_in, monkeypatch, run_from, argument
):
    named = make_recording("2026-10-09_1000_retro", started="2026-10-09T10:00:12+02:00")
    latest = make_recording("2026-10-10_1946", started="2026-10-10T19:46:05+02:00")
    stand_in(mic=[Segment(1.0, 2.0, "Hello.")])
    monkeypatch.chdir(named.parent / run_from)

    exit_status = transcribe(argument)

    assert exit_status == 0
    assert (named / "transcript.whisper-large-v3.md").read_text().startswith("# 2026-10-09_1000_retro\n")
    assert not (latest / "transcript.whisper-large-v3.md").exists()


def test_transcribe_says_where_the_transcript_and_the_segments_file_are(make_recording, stand_in, capsys):
    recording = make_recording()
    stand_in()

    transcribe()

    output = capsys.readouterr().out
    assert f"Transcript: {recording / 'transcript.whisper-large-v3.md'}" in output
    assert f"Segments: {recording / 'segments.whisper-large-v3.json'}" in output


def test_transcribing_again_replaces_the_transcript_and_the_segments_file(make_recording, stand_in):
    recording = make_recording()
    stand_in(mic=[Segment(1.0, 2.0, "The first hearing."), Segment(50.0, 51.0, "Gone the second time.")])
    transcribe()
    stand_in(mic=[Segment(1.0, 2.0, "The second hearing.")])

    transcribe()

    assert lines_of(recording / "transcript.whisper-large-v3.md") == ["[00:00:01] **Me:** The second hearing."]
    [segment] = json.loads((recording / "segments.whisper-large-v3.json").read_text())["segments"]
    assert segment["text"] == "The second hearing."
    assert sorted(file.name for file in recording.iterdir()) == [
        "mic.flac",
        "recording.json",
        "segments.whisper-large-v3.json",
        "system.flac",
        "transcript.whisper-large-v3.md",
    ]


def test_an_interrupted_recording_can_be_transcribed(home, stand_in):
    # What a Recording is when it was killed, not stopped: nothing the capture program reports late
    # reached the metadata file, and the Tracks' headers give no length.
    recording = home / "tldl" / "2026-10-10_1946"
    recording.mkdir(parents=True)
    shutil.copy(INTERRUPTED_TRACK, recording / "mic.flac")
    shutil.copy(INTERRUPTED_TRACK, recording / "system.flac")
    metadata = {
        "started": "2026-10-10T19:46:05+02:00",
        "track_starts": {"mic": None, "system": None},
        "output_route": None,
        "output_transport": None,
    }
    (recording / "recording.json").write_text(json.dumps(metadata))
    stand_in(mic=[Segment(2.0, 3.0, "Can you hear me?")], system=[Segment(1.0, 2.0, "Hello.")])

    exit_status = transcribe()

    assert exit_status == 0
    transcript = recording / "transcript.whisper-large-v3.md"
    assert "- Duration: 00:00:03\n" in transcript.read_text()
    assert lines_of(transcript) == ["[00:00:01] **Others:** Hello.", "[00:00:02] **Me:** Can you hear me?"]
    assert json.loads((recording / "segments.whisper-large-v3.json").read_text())["duration"] == 3.744


def test_transcribe_fails_when_there_is_no_recording_of_that_name(make_recording, stand_in, capsys):
    make_recording("2026-10-10_1946")
    engine = stand_in()

    exit_status = transcribe("2026-10-11_0900")

    assert exit_status == 1
    assert "no Recording named 2026-10-11_0900" in capsys.readouterr().err
    assert engine.tracks == []


def test_transcribe_fails_when_there_are_no_recordings(home, stand_in, capsys):
    stand_in()

    exit_status = transcribe()

    assert exit_status == 1
    assert f"no Recordings under {home / 'tldl'}" in capsys.readouterr().err


@pytest.mark.parametrize(
    "what_the_track_holds, reason", [("not audio", "ffmpeg could not decode it"), ("", "the file is empty")]
)
def test_transcribe_fails_before_the_engine_runs_when_a_track_cannot_be_read(
    make_recording, stand_in, capsys, what_the_track_holds, reason
):
    recording = make_recording()
    (recording / "system.flac").write_text(what_the_track_holds)
    engine = stand_in()

    exit_status = transcribe()

    assert exit_status == 1
    assert capsys.readouterr().err == f"Cannot transcribe: could not read {recording / 'system.flac'}: {reason}.\n"
    assert engine.tracks == []
    assert not (recording / "transcript.whisper-large-v3.md").exists()


def test_transcribe_fails_before_the_engine_runs_when_a_track_is_missing(make_recording, stand_in, capsys):
    recording = make_recording()
    (recording / "mic.flac").unlink()
    engine = stand_in()

    exit_status = transcribe()

    assert exit_status == 1
    assert capsys.readouterr().err == (
        f"Cannot transcribe: could not read {recording / 'mic.flac'}: No such file or directory.\n"
    )
    assert engine.tracks == []


def test_transcribe_fails_before_the_engine_runs_when_a_track_start_in_the_metadata_file_is_not_a_number(
    make_recording, stand_in, capsys
):
    recording = make_recording(track_starts=(100.0, "soon"))
    engine = stand_in()

    exit_status = transcribe()

    assert exit_status == 1
    assert capsys.readouterr().err == (
        f"Cannot transcribe: the metadata file {recording / 'recording.json'}"
        ' gives the start of the system track as "soon", which is not a number.\n'
    )
    assert engine.tracks == []
    assert not (recording / "transcript.whisper-large-v3.md").exists()


def test_transcribe_fails_with_the_reason_when_ffmpeg_is_missing(make_recording, stand_in, monkeypatch, capsys):
    recording = make_recording()
    engine = stand_in()
    monkeypatch.setenv("PATH", str(recording))

    exit_status = transcribe()

    assert exit_status == 1
    assert "ffmpeg is needed to read the Tracks" in capsys.readouterr().err
    assert engine.tracks == []


def test_tldl_starts_without_loading_speech_recognition():
    # Every Engine is named when `tldl` starts; none may bring its speech recognition library along
    # until it runs. Both `parakeet-mlx` and `mlx-whisper` are built on `mlx`, and `whisper-large-v3`
    # finds the speech on a Track with `torch`.
    loaded = subprocess.run(
        [sys.executable, "-c", "import sys, tldl.cli; print('mlx' in sys.modules or 'torch' in sys.modules)"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert loaded.stdout.strip() == "False"
