"""Stand-in Engine for the fast suite: returns prepared Segments and runs no speech recognition."""

from collections.abc import Sequence
from pathlib import Path

from tldl.engines import Recognition, Segment


class StandInEngine:
    """An Engine that hears on each Track exactly the Segments it was prepared with.

    `mic` and `system` are the Segments of the mic track and of the system track. `language` is the
    language the Engine reports; None for an Engine that reports none. Afterwards `tracks` holds the
    Tracks it was given and `languages_given` the language it was given with each.
    """

    def __init__(
        self, mic: Sequence[Segment] = (), system: Sequence[Segment] = (), language: str | None = None
    ) -> None:
        self._segments = {"mic.flac": list(mic), "system.flac": list(system)}
        self._language = language
        self.tracks: list[Path] = []
        self.languages_given: list[str | None] = []

    def recognise(self, track: Path, language: str | None) -> Recognition:
        self.tracks.append(track)
        self.languages_given.append(language)
        return Recognition(self._segments[track.name], self._language)
