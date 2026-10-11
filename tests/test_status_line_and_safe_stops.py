"""The status line of `tldl record` and the stops it makes by itself, against a stand-in capture program."""

import signal
from pathlib import Path

from test_record import STAND_IN_CAPTURE, finish, reported_path, start_record


def record_reporting(folder: Path, *events: str, interval: float = 0) -> tuple[int, str, str]:
    """Run `tldl record` while the capture program reports `events`, then send the stop signal.

    Returns the exit status, standard output and standard error of `record`.
    """
    record = start_record(
        folder,
        STAND_IN_CAPTURE,
        text=False,  # the status line is made of carriage returns
        STAND_IN_EVENTS="\n".join(events),
        STAND_IN_EVENT_INTERVAL=str(interval),
    )
    first_line = record.stdout.readline()
    record.send_signal(signal.SIGINT)
    exit_status, output, errors = finish(record)
    return exit_status, (first_line + output).decode(), errors.decode()


def status_line_row(output: str) -> str:
    """The one row of the terminal the status line lives in, with everything written to it.

    Each update returns to the start of the row and writes over the state before it.
    """
    (row,) = (row for row in output.split("\n") if "\r" in row)
    return row


def status_line_states(output: str) -> list[str]:
    """Every state the status line went through, in order."""
    return status_line_row(output).split("\r")[1:]


def test_status_line_shows_the_elapsed_time_and_a_level_for_each_track(tmp_path):
    _, output, _ = record_reporting(tmp_path, "level mic=1.0000 system=0.0000")

    assert status_line_states(output) == ["00:00:00  mic ██████████  system ··········"]


def test_status_line_is_one_line_updated_in_place(tmp_path):
    _, output, _ = record_reporting(
        tmp_path,
        "level mic=0.0316 system=0.1000",  # 30 dB and 20 dB under full scale, of the 60 dB shown
        "level mic=0.0000 system=1.0000",
    )

    assert status_line_row(output) == (
        "\r00:00:00  mic █████·····  system ███████···"
        "\r00:00:00  mic ··········  system ██████████"
    )


def test_status_line_shows_a_silent_track_as_a_level_at_zero_and_nothing_else(tmp_path):
    _, output, errors = record_reporting(tmp_path, "level mic=0.0000 system=0.0000")

    assert status_line_states(output) == ["00:00:00  mic ··········  system ··········"]
    assert errors == ""


def test_status_line_counts_the_elapsed_time_from_the_start_of_capture(tmp_path):
    _, output, _ = record_reporting(tmp_path, "level mic=0.5000 system=0.5000", interval=1.1)

    assert status_line_states(output)[-1].startswith("00:00:01  ")


def test_record_stops_with_the_reason_when_the_microphone_disappears(tmp_path):
    record = start_record(
        tmp_path,
        STAND_IN_CAPTURE,
        STAND_IN_EVENTS="level mic=0.2000 system=0.2000\nfailed the microphone disappeared",
    )

    # No stop signal is sent: the Recording ends by itself.
    exit_status, _, errors = finish(record)

    assert exit_status == 1
    assert "Recording stopped: the microphone disappeared." in errors


def test_record_keeps_what_was_captured_before_the_microphone_disappeared(tmp_path):
    record = start_record(
        tmp_path, STAND_IN_CAPTURE, STAND_IN_EVENTS="failed the microphone disappeared"
    )

    _, output, _ = finish(record)

    assert reported_path(output, "Mic track:").read_text() == "mic track"
    assert reported_path(output, "System track:").read_text() == "system track"


def test_record_fails_with_the_reason_when_capture_cannot_start(tmp_path):
    no_microphone = tmp_path / "no-microphone"
    no_microphone.write_text("#!/bin/sh\necho 'failed there is no default microphone'\nexit 1\n")
    no_microphone.chmod(0o755)

    exit_status, output, errors = finish(start_record(tmp_path, no_microphone))

    assert exit_status == 1
    assert errors == "Recording failed: there is no default microphone.\n"
    assert output == ""
