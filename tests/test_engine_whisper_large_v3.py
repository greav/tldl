"""The `whisper-large-v3` Engine on short audio files. Slow: run with `uv run pytest -m engine`."""

import re
from pathlib import Path

import pytest

from tldl.engines import ENGINES

SPEECH_AROUND_A_LONG_SILENCE = Path(__file__).parent / "audio" / "speech-around-a-long-silence.flac"
"""Two sentences in a synthetic voice, 47.64 s long: silence until 2.41 s, the first sentence until
4.87 s, silence until 44.98 s, then the second sentence to the end.

The silence is longer than the 30 s Whisper hears at once. Given the whole file, Whisper places the
first sentence at 0 s and the second at 30 s.
"""

NO_SPEECH = Path(__file__).parent / "audio" / "interrupted-track.flac"
"""3.744 s of digital silence. Given the whole file, Whisper hears "Thank you." in it."""


def words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


@pytest.mark.engine
def test_whisper_large_v3_hears_the_speech_where_it_was_spoken_and_nothing_in_the_silence():
    engine = ENGINES["whisper-large-v3"]

    first, second = engine.recognise(SPEECH_AROUND_A_LONG_SILENCE, None)

    assert words(first.text) == "the quick brown fox jumps over the lazy dog".split()
    assert words(second.text) == "recordings become transcripts on this machine".split()
    assert first.start == pytest.approx(2.41, abs=0.5)
    assert first.end == pytest.approx(4.87, abs=0.5)
    assert second.start == pytest.approx(44.98, abs=0.5)
    assert second.end == pytest.approx(47.64, abs=0.5)
    # The language is that of the Tracks taken together: the one without speech has no say in it.
    assert engine.detect_language([NO_SPEECH, SPEECH_AROUND_A_LONG_SILENCE]) == "en"


@pytest.mark.engine
def test_whisper_large_v3_hears_nothing_on_a_track_with_no_speech():
    engine = ENGINES["whisper-large-v3"]

    assert engine.recognise(NO_SPEECH, None) == []
    assert engine.detect_language([NO_SPEECH]) is None
