"""`tldl record`, driven from the outside against a stand-in capture program."""

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

TLDL = Path(sys.executable).with_name("tldl")
STAND_IN_CAPTURE = Path(__file__).with_name("stand_in_capture.py")


def start_record(
    home: Path, capture_program: Path, *arguments: str, text: bool = True, **environment: str
) -> subprocess.Popen:
    """Start `tldl record` with `home` as the home folder and `capture_program` as the capture program.

    `arguments` follow `record` on the command line. `environment` is added to the environment of both
    programs. With `text=False` the output comes as bytes, exactly as written: reading it as text turns
    every carriage return into a new line.
    """
    return subprocess.Popen(
        [TLDL, "record", *arguments],
        cwd=home,
        env={
            **os.environ,
            # The user's own home is out of reach: for this run `~/tldl/` is `home / "tldl"`.
            "HOME": str(home),
            "TLDL_CAPTURE_PROGRAM": str(capture_program),
            **environment,
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        # A group of its own, so the stop signal reaches the capture program only if `record` passes it
        # on, and so a failing test can clear away both processes.
        start_new_session=True,
    )


def finish(record: subprocess.Popen) -> tuple[int, str, str]:
    """Wait for `record` to exit; return its exit status, standard output and standard error."""
    try:
        output, errors = record.communicate(timeout=10)
    finally:
        try:
            os.killpg(record.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            # Nobody is left to clear away. "Not permitted" is how macOS says so while a process of
            # the group is dead and not yet reaped: after a test killed the whole group, the capture
            # program is an orphan that the system reaps a moment later.
            pass
    return record.returncode, output, errors


def reported_path(output: str, label: str) -> Path:
    """The path `tldl record` printed after `label`."""
    for line in output.splitlines():
        if line.startswith(label):
            return Path(line.removeprefix(label).strip())
    raise AssertionError(f"no line starting with {label!r} in:\n{output}")


@pytest.fixture
def stopped_record(tmp_path):
    """A `tldl record` run that was stopped with the stop signal once capture had started."""
    record = start_record(tmp_path, STAND_IN_CAPTURE)
    started = record.stdout.readline()
    record.send_signal(signal.SIGINT)
    exit_status, output, _ = finish(record)
    assert "Recording" in started
    return exit_status, output


def test_record_runs_until_the_stop_signal_then_exits_cleanly(stopped_record):
    exit_status, _ = stopped_record

    assert exit_status == 0


def test_record_says_where_the_mic_track_and_the_system_track_are(stopped_record):
    _, output = stopped_record

    assert reported_path(output, "Mic track:").read_text() == "mic track"
    assert reported_path(output, "System track:").read_text() == "system track"


def test_record_exits_cleanly_when_ctrl_c_reaches_the_capture_program_as_well(tmp_path):
    # Ctrl+C in a terminal goes to every process in the foreground group, not to `record` alone.
    record = start_record(tmp_path, STAND_IN_CAPTURE)
    record.stdout.readline()
    os.killpg(record.pid, signal.SIGINT)
    exit_status, output, _ = finish(record)

    assert exit_status == 0
    assert reported_path(output, "Mic track:").exists()
    assert reported_path(output, "System track:").exists()


def test_record_fails_when_the_capture_program_fails(tmp_path):
    failing_capture = tmp_path / "failing-capture"
    failing_capture.write_text("#!/bin/sh\necho 'no microphone' >&2\nexit 1\n")
    failing_capture.chmod(0o755)

    exit_status, output, errors = finish(start_record(tmp_path, failing_capture))

    assert exit_status == 1
    assert "no microphone" in errors
    assert "track:" not in output
