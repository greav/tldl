"""Choosing the microphone the mic track is taken from, in the configuration file or with a flag of
`tldl record`, against a stand-in capture program that plays the microphones that are there."""

import json
import signal
from pathlib import Path

from test_record import STAND_IN_CAPTURE, finish, start_record

HEADSET_CONNECTED = "Headset Microphone\nMacBook Pro Microphone"
"""The microphones the stand-in plays: a headset the system moved its input to, and the built-in one."""


def record_and_stop(home: Path, *arguments: str) -> None:
    """Run `tldl record` with a headset connected and stop it once capture has started."""
    record = start_record(home, STAND_IN_CAPTURE, *arguments, STAND_IN_MICROPHONES=HEADSET_CONNECTED)
    record.stdout.readline()
    record.send_signal(signal.SIGINT)
    exit_status, _, errors = finish(record)
    assert exit_status == 0, errors


def microphone_in_the_metadata(home: Path) -> dict:
    """What the metadata file of the one Recording under `~/tldl/` says about the microphone."""
    [recording] = (home / "tldl").iterdir()
    return json.loads((recording / "recording.json").read_text())["microphone"]


def test_the_microphone_flag_chooses_the_microphone_the_recording_is_made_with(home):
    record_and_stop(home, "--microphone", "MacBook Pro Microphone")

    assert microphone_in_the_metadata(home)["name"] == "MacBook Pro Microphone"


def test_with_no_microphone_named_the_recording_is_made_with_the_system_default_microphone(home):
    record_and_stop(home)

    assert microphone_in_the_metadata(home)["name"] == "Headset Microphone"


def test_the_configuration_file_names_the_microphone_whatever_the_system_default_is(home, configure):
    configure('microphone = "MacBook Pro Microphone"\n')

    record_and_stop(home)

    assert microphone_in_the_metadata(home)["name"] == "MacBook Pro Microphone"


def test_the_microphone_flag_wins_over_the_configuration_file(home, configure):
    configure('microphone = "Headset Microphone"\n')

    record_and_stop(home, "--microphone", "MacBook Pro Microphone")

    assert microphone_in_the_metadata(home)["name"] == "MacBook Pro Microphone"


def test_the_word_default_goes_back_to_the_system_default_microphone_for_one_run(home, configure):
    configure('microphone = "MacBook Pro Microphone"\n')

    record_and_stop(home, "--microphone", "default")

    assert microphone_in_the_metadata(home)["name"] == "Headset Microphone"


def test_a_microphone_that_is_not_there_fails_with_its_name_and_the_microphones_that_are(home, configure):
    configure('microphone = "AirPods Pro"\n')

    record = start_record(home, STAND_IN_CAPTURE, STAND_IN_MICROPHONES=HEADSET_CONNECTED)
    exit_status, output, errors = finish(record)

    assert exit_status == 1
    assert errors == (
        "Recording failed: there is no microphone named AirPods Pro;"
        " the microphones are Headset Microphone, MacBook Pro Microphone.\n"
    )
    assert output == ""
    assert list((home / "tldl").iterdir()) == []


def test_a_named_microphone_that_disappears_stops_the_recording_and_keeps_what_was_captured(home):
    record = start_record(
        home,
        STAND_IN_CAPTURE,
        "--microphone",
        "MacBook Pro Microphone",
        STAND_IN_MICROPHONES=HEADSET_CONNECTED,
        STAND_IN_EVENTS="failed the microphone disappeared",
    )

    # No stop signal is sent: the Recording ends by itself.
    exit_status, _, errors = finish(record)

    assert exit_status == 1
    assert errors == "Recording stopped: the microphone disappeared.\n"
    [recording] = (home / "tldl").iterdir()
    assert (recording / "mic.flac").read_text() == "mic track"
    assert (recording / "system.flac").read_text() == "system track"
    assert microphone_in_the_metadata(home)["name"] == "MacBook Pro Microphone"
