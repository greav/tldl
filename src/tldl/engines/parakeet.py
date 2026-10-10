"""The Parakeet Engines, built on `parakeet-mlx`: recognition on this Mac, through MLX.

`parakeet-mlx` reads the Track through `ffmpeg`, which has to be on the PATH.
"""

from collections.abc import Sequence
from pathlib import Path

from tldl.engines.seam import Segment
from tldl.engines.weights import weights_folder

CHUNK_SECONDS = 120.0
"""How much of a Track goes through the speech model at once. The model attends to all of what it is
given, so this is what keeps a two-hour Track within the memory a two-minute one needs."""

CHUNK_OVERLAP_SECONDS = 15.0
"""How much of each chunk repeats the end of the one before, so that words cut by a chunk's edge are
heard whole in one of the two."""

WEIGHTS_FILES = ("config.json", "model.safetensors")
"""The files of a speech model on Hugging Face that `parakeet-mlx` loads."""


class Parakeet:
    """A Parakeet speech model as an Engine. It neither detects a language nor takes one."""

    def __init__(self, weights: str) -> None:
        """`weights` names the speech model on Hugging Face."""
        self._weights = weights
        self._model = None

    def accepts_language(self, language: str) -> bool:
        return True

    def detect_language(self, tracks: Sequence[Path]) -> str | None:
        return None

    def recognise(self, track: Path, language: str | None) -> list[Segment]:
        if self._model is None:
            self._model = self._load()
        heard = self._model.transcribe(
            track, chunk_duration=CHUNK_SECONDS, overlap_duration=CHUNK_OVERLAP_SECONDS
        )
        # A Segment is a sentence as the speech model punctuated it.
        return [
            Segment(sentence.start, _end_of_speech(sentence), text)
            for sentence in heard.sentences
            if (text := sentence.text.strip())
        ]

    def _load(self):
        # Imported here and not at the top: loading speech recognition takes seconds, and only a run
        # of this Engine should pay for it.
        from parakeet_mlx import from_pretrained

        return from_pretrained(str(weights_folder(self._weights, WEIGHTS_FILES)))


def _end_of_speech(sentence) -> float:
    """When the last word of `sentence` ends.

    Not when the sentence does: the speech model writes a sentence's full stop only once it hears the
    next sentence begin, so the sentence's own end lies as far past its last word as the pause lasted.
    """
    words = [token.end for token in sentence.tokens if any(character.isalnum() for character in token.text)]
    return max(words, default=sentence.end)
