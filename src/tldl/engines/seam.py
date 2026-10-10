"""The Engine seam: a Track goes in, Segments come out.

An Engine knows nothing about Speakers or the Transcript. Everything after the seam works on Segments
alone.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Segment:
    """A continuous stretch of speech on one Track."""

    start: float
    """Seconds from the start of the Track."""
    end: float
    """Seconds from the start of the Track."""
    text: str


class Engine(Protocol):
    def accepts_language(self, language: str) -> bool:
        """Whether `language` is one the Engine can be given to recognise a Track in.

        Asked before any Track is read, so the answer costs no speech recognition. An Engine that
        takes no language accepts every one, because it ignores it.
        """
        ...

    def detect_language(self, tracks: Sequence[Path]) -> str | None:
        """The language spoken on `tracks`, as a code such as `en` or `ru`.

        `tracks` are the audio files of the Tracks of one Recording. They are judged together, so that
        a Track with a few words on it does not decide for the Track that holds the conversation. None
        from an Engine that takes no language, and when no Track holds speech.
        """
        ...

    def recognise(self, track: Path, language: str | None) -> list[Segment]:
        """Turn the Track in the audio file `track` into Segments, in the order spoken.

        A Track with no speech gives none. `language` is the language to recognise the Track in; None
        leaves the choice to the Engine, which then judges this Track alone. An Engine that takes no
        language ignores it.
        """
        ...
