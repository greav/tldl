"""The `tldl` command line."""

import argparse
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from tldl.capture import Capture, CaptureNotLaunched
from tldl.configuration import SYSTEM_DEFAULT_MICROPHONE, UnreadableConfiguration, read_configuration
from tldl.engines import ENGINES
from tldl.recording import NoRecording, Recording
from tldl.status_line import status_line
from tldl.stereo_file import StereoFileNotMade, make_stereo_file
from tldl.track import UnreadableTrack, track_length
from tldl.transcript import build_transcript, render_segments_file, render_transcript


def main(command_line: list[str] | None = None) -> int:
    """Run `tldl` with the arguments in `command_line`; without it, with the ones it was started with."""
    parser = argparse.ArgumentParser(prog="tldl")
    commands = parser.add_subparsers(dest="command", required=True)
    record_command = commands.add_parser(
        "record", help="capture the mic track and the system track until Ctrl+C"
    )
    record_command.add_argument("title", nargs="?", help="a name for the Recording, added to its folder's name")
    record_command.add_argument(
        "--microphone",
        metavar="NAME",
        help="the microphone to take the mic track from for this run, by the name the system gives it;"
        f" {SYSTEM_DEFAULT_MICROPHONE} is the system default microphone",
    )
    transcribe_command = commands.add_parser("transcribe", help="turn a Recording into a Transcript")
    transcribe_command.add_argument(
        "recording", nargs="?", help="the Recording's name or its folder; without it, the latest Recording"
    )
    transcribe_command.add_argument(
        "--engine", metavar="NAME", help=f"the Engine to use for this run: {', '.join(ENGINES)}"
    )
    transcribe_command.add_argument(
        "--lang", metavar="CODE", help="the language spoken, as a code such as en or ru, for this run"
    )
    stereo_command = commands.add_parser("stereo", help="put both Tracks of a Recording into one stereo file")
    stereo_command.add_argument(
        "recording", nargs="?", help="the Recording's name or its folder; without it, the latest Recording"
    )
    arguments = parser.parse_args(command_line)
    try:
        configuration = read_configuration()
    except UnreadableConfiguration as problem:
        print(f"{problem}.", file=sys.stderr)
        return 1
    if arguments.command == "transcribe":
        return transcribe(
            configuration.recordings_root,
            arguments.recording,
            arguments.engine or configuration.engine,
            arguments.lang or configuration.language,
        )
    if arguments.command == "stereo":
        return stereo(configuration.recordings_root, arguments.recording)
    # A flag that was given wins, an empty one too: that is a name no microphone has.
    microphone = configuration.microphone if arguments.microphone is None else arguments.microphone
    return record(
        configuration.recordings_root,
        arguments.title,
        None if microphone == SYSTEM_DEFAULT_MICROPHONE else microphone,
    )


def record(recordings_root: Path, title: str | None, microphone: str | None) -> int:
    """Make a Recording under `recordings_root` until the stop signal.

    `microphone` names the microphone the mic track is taken from; None is the system default microphone.
    """
    recording = Recording.begin(recordings_root, datetime.now().astimezone(), title)

    try:
        capture = Capture(recording.mic_track, recording.system_track, microphone)
    except CaptureNotLaunched as problem:
        print(f"Recording failed: {problem}.", file=sys.stderr)
        recording.discard()
        return 1
    signal.signal(signal.SIGINT, lambda signum, frame: capture.stop())

    started_at = None
    status_line_shown = False
    failure = None
    for event in capture.events():
        if event.name == "started":
            print("Recording. Press Ctrl+C to stop.", flush=True)
            started_at = time.monotonic()
        elif event.name == "track-started":
            recording.note_track_start(event.fields["track"], float(event.fields["host-time"]))
        elif event.name == "output-route":
            recording.note_output_route(event.fields["route"], event.fields.get("transport"))
        elif event.name == "microphone":
            sample_rate = event.fields.get("sample-rate")
            recording.note_microphone(
                unquote(event.fields["name"]),
                event.fields.get("transport"),
                int(sample_rate) if sample_rate else None,
            )
        elif event.name == "level" and started_at is not None:
            elapsed = time.monotonic() - started_at
            levels = (float(event.fields.get(track, 0)) for track in ("mic", "system"))
            # The carriage return writes each state of the status line over the one before it.
            print("\r" + status_line(elapsed, *levels), end="", flush=True)
            status_line_shown = True
        elif event.name == "failed":
            failure = event.text
    if status_line_shown:
        print()
    if capture.wait() != 0 and failure is None:
        failure = "the capture program stopped with an error"

    if failure is not None:
        outcome = "failed" if started_at is None else "stopped"
        print(f"Recording {outcome}: {failure}.", file=sys.stderr)
        if started_at is None:
            recording.discard()
            return 1

    print(f"Mic track: {recording.mic_track}")
    print(f"System track: {recording.system_track}")
    return 0 if failure is None else 1


def transcribe(recordings_root: Path, name: str | None, engine_name: str, language: str | None) -> int:
    """Turn a Recording into a Transcript and a Segments file, both written into its folder.

    `name` chooses the Recording; None is the latest one under `recordings_root`. `language` is the
    language the user gave; None leaves it to the Engine.
    """
    if engine_name not in ENGINES:
        known = ", ".join(ENGINES)
        print(f"Cannot transcribe: there is no Engine named {engine_name}; the Engines are {known}.", file=sys.stderr)
        return 1
    try:
        recording = Recording.latest(recordings_root) if name is None else Recording.named(recordings_root, name)
        mic_offset, system_offset = recording.track_offsets
        # Before the Engine runs: recognition takes minutes, and a Track that cannot be read should
        # stop the command at once.
        duration = max(
            mic_offset + track_length(recording.mic_track),
            system_offset + track_length(recording.system_track),
        )
    except (NoRecording, UnreadableTrack) as problem:
        print(f"Cannot transcribe: {problem}.", file=sys.stderr)
        return 1

    engine = ENGINES[engine_name]
    if language is not None and not engine.accepts_language(language):
        print(
            f"Cannot transcribe: the Engine {engine_name} knows no language {language};"
            " a language is given as a code such as en or ru.",
            file=sys.stderr,
        )
        return 1
    print(f"Transcribing {recording.folder.name} with {engine_name}.", flush=True)
    # A language is settled once for the Recording: what the user gave, or else what the Engine hears
    # on the two Tracks taken together.
    language = language or engine.detect_language([recording.mic_track, recording.system_track])
    mic_segments = engine.recognise(recording.mic_track, language)
    system_segments = engine.recognise(recording.system_track, language)

    transcript = build_transcript(
        mic_segments, system_segments, mic_offset=mic_offset, system_offset=system_offset
    )
    transcript_file = recording.transcript_file(engine_name)
    segments_file = recording.segments_file(engine_name)
    _replace(
        transcript_file,
        render_transcript(
            transcript,
            title=recording.folder.name,
            started=recording.started,
            duration=duration,
            language=language,
        ),
    )
    _replace(
        segments_file,
        render_segments_file(transcript, engine=engine_name, duration=duration, language=language),
    )
    print(f"Transcript: {transcript_file}")
    print(f"Segments: {segments_file}")
    return 0


def stereo(recordings_root: Path, name: str | None) -> int:
    """Make the stereo file of a Recording, in its folder.

    `name` chooses the Recording; None is the latest one under `recordings_root`.
    """
    try:
        recording = Recording.latest(recordings_root) if name is None else Recording.named(recordings_root, name)
    except NoRecording as problem:
        print(f"Cannot make the stereo file: {problem}.", file=sys.stderr)
        return 1
    print(f"Making the stereo file of {recording.folder.name}.", flush=True)
    try:
        stereo_file = make_stereo_file(recording)
    except StereoFileNotMade as problem:
        print(f"Cannot make the stereo file of {recording.folder.name}: {problem}.", file=sys.stderr)
        return 1
    print(f"Stereo file: {stereo_file}")
    return 0


def _replace(file: Path, text: str) -> None:
    """Write `text` as the whole content of `file`, which is never seen half-written."""
    unfinished = file.with_name(f"{file.name}.unfinished")
    unfinished.write_text(text)
    os.replace(unfinished, file)
