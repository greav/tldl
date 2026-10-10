"""The Recording that `tldl record` leaves behind: its folder, its Tracks and its metadata file."""

import json
import os
import signal
import time
from datetime import datetime
from pathlib import Path

import pytest
from test_record import STAND_IN_CAPTURE, finish, start_record

WHAT_THE_STAND_IN_REPORTS = {
    "track_starts": {"mic": 100.25, "system": 100.5},
    "output_route": "headphones",
    "output_transport": "bluetooth",
}
"""The metadata a Recording made with the stand-in capture program holds, apart from its start time."""


def make_recording(home: Path, *arguments: str) -> None:
    """Run `tldl record` and stop it with the stop signal once capture has started."""
    record = start_record(home, STAND_IN_CAPTURE, *arguments)
    record.stdout.readline()
    record.send_signal(signal.SIGINT)
    exit_status, _, errors = finish(record)
    assert exit_status == 0, errors


def recordings(home: Path) -> list[Path]:
    """The Recordings under `~/tldl/`, by name."""
    return sorted((home / "tldl").iterdir())


def names_by_date_and_time(before: datetime, after: datetime) -> set[str]:
    """What a Recording without a title is called when it started between the two moments."""
    return {moment.strftime("%Y-%m-%d_%H%M") for moment in (before, after)}


def test_a_recording_is_a_folder_under_the_recordings_root_named_by_date_and_time(tmp_path):
    before = datetime.now()
    make_recording(tmp_path)
    after = datetime.now()

    [recording] = recordings(tmp_path)
    assert recording.name in names_by_date_and_time(before, after)
    assert (recording / "mic.flac").read_text() == "mic track"
    assert (recording / "system.flac").read_text() == "system track"


@pytest.mark.parametrize(
    ("title", "ending"),
    [
        ("sprint planning", "_sprint-planning"),
        ("  Q3 Review: Budget & Hiring!  ", "_q3-review-budget-hiring"),
        ("Планёрка по релизу 2.1", "_планёрка-по-релизу-2-1"),
        # "й" typed as "и" and a combining breve, as file names copied from Finder have it.
        ("Чай", "_чай"),
        ("../../elsewhere", "_elsewhere"),
        ("?!", ""),
    ],
)
def test_a_title_is_appended_to_the_folder_name_as_a_slug(tmp_path, title, ending):
    before = datetime.now()
    make_recording(tmp_path, title)
    after = datetime.now()

    [recording] = recordings(tmp_path)
    assert recording.name in {name + ending for name in names_by_date_and_time(before, after)}
    assert (recording / "mic.flac").exists()


def test_a_second_recording_in_the_same_minute_leaves_the_first_untouched(tmp_path):
    seconds_left_in_the_minute = 60 - datetime.now().second
    if seconds_left_in_the_minute < 5:
        time.sleep(seconds_left_in_the_minute)

    make_recording(tmp_path)
    [first] = recordings(tmp_path)
    (first / "mic.flac").write_text("the first mic track")
    (first / "system.flac").write_text("the first system track")
    make_recording(tmp_path)
    make_recording(tmp_path)

    assert [recording.name for recording in recordings(tmp_path)] == [
        first.name,
        f"{first.name}-2",
        f"{first.name}-3",
    ]
    assert (first / "mic.flac").read_text() == "the first mic track"
    assert (first / "system.flac").read_text() == "the first system track"
    assert (first.with_name(f"{first.name}-2") / "mic.flac").read_text() == "mic track"


def test_the_metadata_file_holds_the_start_time_the_track_starts_and_the_output_route(tmp_path):
    before = datetime.now().astimezone().replace(microsecond=0)
    make_recording(tmp_path)
    after = datetime.now().astimezone()

    [recording] = recordings(tmp_path)
    metadata = json.loads((recording / "recording.json").read_text())
    assert before <= datetime.fromisoformat(metadata.pop("started")) <= after
    assert metadata == WHAT_THE_STAND_IN_REPORTS


def test_the_metadata_is_already_on_disk_when_a_recording_is_killed(tmp_path):
    record = start_record(tmp_path, STAND_IN_CAPTURE)
    record.stdout.readline()
    [recording] = recordings(tmp_path)
    metadata_file = recording / "recording.json"

    # The stand-in reports the system track's start last.
    give_up = time.monotonic() + 5
    while json.loads(metadata_file.read_text())["track_starts"]["system"] is None and time.monotonic() < give_up:
        time.sleep(0.01)
    os.killpg(record.pid, signal.SIGKILL)
    finish(record)

    metadata = json.loads(metadata_file.read_text())
    del metadata["started"]
    assert metadata == WHAT_THE_STAND_IN_REPORTS
    # The stand-in writes its Tracks on the stop signal, so their absence shows it never got one.
    assert not (recording / "mic.flac").exists()


def test_a_recording_that_never_started_leaves_no_folder(tmp_path):
    failing_capture = tmp_path / "failing-capture"
    failing_capture.write_text("#!/bin/sh\necho 'no microphone' >&2\nexit 1\n")
    failing_capture.chmod(0o755)

    exit_status, _, _ = finish(start_record(tmp_path, failing_capture))

    assert exit_status == 1
    assert recordings(tmp_path) == []
