"""Stand-in Engine for the fast suite: returns prepared Segments and runs no speech recognition."""

from collections.abc import Sequence
from pathlib import Path

from tldl.engines import Segment


class StandInEngine:
    """An Engine that hears on each Track exactly the Segments it was prepared with.

    `mic` and `system` are the Segments of the mic track and of the system track. `language` is the
    language the Engine detects; None for an Engine that detects none. Afterwards `detected_on` holds
    the Tracks of each time it was asked for the language, `tracks` the Tracks it was given to
    recognise and `languages_given` the language it was given with each.
    """

    def __init__(
        self, mic: Sequence[Segment] = (), system: Sequence[Segment] = (), language: str | None = None
    ) -> None:
        self._segments = {"mic.flac": list(mic), "system.flac": list(system)}
        self._language = language
        self.detected_on: list[list[Path]] = []
        self.tracks: list[Path] = []
        self.languages_given: list[str | None] = []

    def detect_language(self, tracks: Sequence[Path]) -> str | None:
        self.detected_on.append(list(tracks))
        return self._language

    def recognise(self, track: Path, language: str | None) -> list[Segment]:
        self.tracks.append(track)
        self.languages_given.append(language)
        return self._segments[track.name]
