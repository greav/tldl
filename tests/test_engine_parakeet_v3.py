"""The `parakeet-v3` Engine on a short audio file. Slow: run with `uv run pytest -m engine`."""

import re
from pathlib import Path

import pytest

from tldl.engines import ENGINES

SPEECH = Path(__file__).parent / "audio" / "speech.flac"
"""Two sentences in a synthetic voice, 8.73 s long: silence until 1.91 s, the first sentence until
4.37 s, silence until 6.07 s, then the second sentence to the end."""


def words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


@pytest.mark.engine
def test_parakeet_v3_hears_each_sentence_as_a_segment_where_it_was_spoken():
    first, second = ENGINES["parakeet-v3"].recognise(SPEECH, None)

    assert words(first.text) == "the quick brown fox jumps over the lazy dog".split()
    assert words(second.text) == "recordings become transcripts on this machine".split()
    # The speech model places a word to within a few tenths of a second.
    assert first.start == pytest.approx(1.91, abs=0.5)
    assert first.end == pytest.approx(4.37, abs=0.5)
    assert second.start == pytest.approx(6.07, abs=0.5)
    assert second.end == pytest.approx(8.73, abs=0.5)
    assert ENGINES["parakeet-v3"].detect_language([SPEECH]) is None


@pytest.mark.engine
def test_parakeet_v3_accepts_any_language_because_it_ignores_it():
    assert ENGINES["parakeet-v3"].accepts_language("xx")
