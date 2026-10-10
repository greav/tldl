"""A Recording on disk: a folder under the Recordings root holding the two Tracks and a metadata file.

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


class Recording:
    """A Recording being made: its folder, and the metadata gathered so far."""

    def __init__(self, folder: Path, started: datetime) -> None:
        self.folder = folder
        self._metadata = {
            "started": started.isoformat(timespec="seconds"),
            "track_starts": {"mic": None, "system": None},
            "output_route": None,
            "output_transport": None,
        }
        self._write_metadata()

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
            return cls(folder, started)

    @property
    def mic_track(self) -> Path:
        return self.folder / MIC_TRACK_FILE

    @property
    def system_track(self) -> Path:
        return self.folder / SYSTEM_TRACK_FILE

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
