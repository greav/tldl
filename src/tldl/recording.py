"""A Recording on disk: a folder under the Recordings root holding the two Tracks and a metadata file,
and, once it has been transcribed, a Transcript and a Segments file for each Engine that heard it.

The folder is named `YYYY-MM-DD_HHMM` after the local time the Recording started, with `_<title-slug>`
appended when it was given a title.

The metadata file is JSON with these keys:

    started           when the Recording started: local time with its UTC offset, ISO 8601
    track_starts      for `mic` and for `system`, when the Track's first audio was captured, in seconds
                      on the clock the two Tracks share. Only the difference between the two means
                      anything: it is how far apart the Tracks begin.
    output_route      what the computer was playing sound through at the start: `speakers`,
                      `headphones` or `unknown`
    output_transport  how that output device was connected, the fact `output_route` was judged from

The file is written when the Recording starts and again each time the capture program reports one of
these, so it is there whatever ends the Recording. A value is null until it has been reported.
"""

import itertools
import json
import os
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

DEFAULT_RECORDINGS_ROOT = Path("~/tldl")
"""Where Recordings go unless the caller names another Recordings root."""

MIC_TRACK_FILE = "mic.flac"
SYSTEM_TRACK_FILE = "system.flac"
METADATA_FILE = "recording.json"


def title_slug(title: str) -> str:
    """A title as a folder name carries it: its words in lowercase, joined by hyphens.

    A word is a run of letters and digits of any alphabet; everything else separates words. The result
    is empty when the title holds no letter or digit.
    """
    return "-".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFC", title).lower()))


class NoRecording(Exception):
    """There is no Recording where one was asked for. The message says so in words fit for the user."""


class Recording:
    """A Recording on disk: its folder, and what its metadata file holds."""

    def __init__(self, folder: Path, metadata: dict) -> None:
        self.folder = folder
        self._metadata = metadata

    @classmethod
    def begin(cls, recordings_root: Path, started: datetime, title: str | None = None) -> "Recording":
        """Create the folder for a Recording that starts at `started`.

        The folder is always a new one: when the name is taken, as for a second Recording within the
        same minute, the name gets `-2`, `-3` and so on.
        """
        name = started.strftime("%Y-%m-%d_%H%M")
        if title and (slug := title_slug(title)):
            name += f"_{slug}"
        root = recordings_root.expanduser()
        root.mkdir(parents=True, exist_ok=True)
        for number in itertools.count(1):
            folder = root / (name if number == 1 else f"{name}-{number}")
            try:
                folder.mkdir()
            except FileExistsError:
                continue
            recording = cls(
                folder,
                {
                    "started": started.isoformat(timespec="seconds"),
                    "track_starts": {"mic": None, "system": None},
                    "output_route": None,
                    "output_transport": None,
                },
            )
            recording._write_metadata()
            return recording

    @classmethod
    def open(cls, folder: Path) -> "Recording":
        """The Recording in `folder`, however it ended: stopped, failed or interrupted."""
        try:
            metadata = json.loads((folder / METADATA_FILE).read_text())
            datetime.fromisoformat(metadata["started"])
        except (OSError, ValueError, KeyError, TypeError) as problem:
            raise NoRecording(f"{folder} is not a Recording: it has no readable {METADATA_FILE}") from problem
        return cls(folder, metadata)

    @classmethod
    def latest(cls, recordings_root: Path) -> "Recording":
        """The Recording under `recordings_root` that started last."""
        root = recordings_root.expanduser()
        recordings = []
        for folder in root.iterdir() if root.is_dir() else ():
            try:
                recordings.append(cls.open(folder))
            except NoRecording:
                continue
        if not recordings:
            raise NoRecording(f"there are no Recordings under {root}")
        # By the start time and not by the folder's name: the name is to the minute and ends with the
        # title, so it does not order two Recordings that started within one minute.
        return max(recordings, key=lambda recording: (recording.started, recording.folder.name))

    @classmethod
    def named(cls, recordings_root: Path, name: str) -> "Recording":
        """The Recording called `name` under `recordings_root`, or the one in the folder `name`."""
        root = recordings_root.expanduser()
        not_a_recording = None
        # The path is resolved, so that one such as `.` gives the folder under its own name.
        for folder in (root / name, Path(name).resolve()):
            if not folder.is_dir():
                continue
            try:
                return cls.open(folder)
            except NoRecording as problem:
                # `.` read as a name is the Recordings root itself: the path is still to be tried.
                not_a_recording = problem
        raise not_a_recording or NoRecording(f"there is no Recording named {name} under {root}")

    @property
    def started(self) -> datetime:
        """When the Recording started, in the local time of that moment."""
        return datetime.fromisoformat(self._metadata["started"])

    @property
    def track_offsets(self) -> tuple[float, float]:
        """How many seconds after the start of the Recording the mic track and the system track begin.

        The Recording starts with whichever Track began first. When a Track's start was never
        reported, as in a Recording interrupted in its first moments, both count as beginning together.
        """
        starts = self._metadata.get("track_starts") or {}
        mic, system = starts.get("mic"), starts.get("system")
        if mic is None or system is None:
            return 0.0, 0.0
        return mic - min(mic, system), system - min(mic, system)

    @property
    def mic_track(self) -> Path:
        return self.folder / MIC_TRACK_FILE

    @property
    def system_track(self) -> Path:
        return self.folder / SYSTEM_TRACK_FILE

    def transcript_file(self, engine: str) -> Path:
        """Where the Transcript made by the Engine named `engine` goes."""
        return self.folder / f"transcript.{engine}.md"

    def segments_file(self, engine: str) -> Path:
        """Where the Segments the Engine named `engine` heard go, beside its Transcript."""
        return self.folder / f"segments.{engine}.json"

    def note_track_start(self, track: str, host_time: float) -> None:
        """Record when `track` (`mic` or `system`) began, in seconds on the Tracks' shared clock."""
        self._metadata["track_starts"][track] = host_time
        self._write_metadata()

    def note_output_route(self, route: str, transport: str | None) -> None:
        """Record what the computer was playing sound through when the Recording started."""
        self._metadata["output_route"] = route
        self._metadata["output_transport"] = transport
        self._write_metadata()

    def discard(self) -> None:
        """Remove the folder. For a Recording that never started, whose folder holds no audio."""
        shutil.rmtree(self.folder)

    def _write_metadata(self) -> None:
        # Written aside and moved into place, so the file is whole at every moment.
        unfinished = self.folder / f"{METADATA_FILE}.unfinished"
        unfinished.write_text(json.dumps(self._metadata, indent=2) + "\n")
        os.replace(unfinished, self.folder / METADATA_FILE)
