"""The Engine seam: a Track goes in, Segments come out.

An Engine knows nothing about Speakers, the other Track or the Transcript. Everything after the seam
works on Segments alone.
"""

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


@dataclass(frozen=True)
class Recognition:
    """What an Engine heard on one Track."""

    segments: list[Segment]
    """In the order spoken. Empty for a Track with no speech."""
    language: str | None = None
    """The language the Engine recognised the Track in, as a code such as `en` or `ru`. None from an
    Engine that neither detects a language nor takes one."""


class Engine(Protocol):
    def recognise(self, track: Path, language: str | None) -> Recognition:
        """Turn the Track in the audio file `track` into Segments.

        `language` is the language to recognise it in; None leaves the choice to the Engine. An Engine
        that takes no language ignores it.
        """
        ...
