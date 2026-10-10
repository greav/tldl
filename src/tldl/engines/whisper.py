"""The Whisper Engines, built on `mlx-whisper`: recognition on this Mac, through MLX.

Whisper hears half a minute at a time and writes text for whatever it is given: on silence it invents
words, and speech that follows a silence it places too early. So the speech on a Track is found first,
by the Silero speech detector, and Whisper is given nothing else. It gets the speech one passage at a
time: a stretch of the Track that begins and ends in silence and is no longer than Whisper hears at
once. A Segment's times are those Whisper gives within the passage, moved to where the passage lies on
the Track.

`mlx-whisper` reads the Track through `ffmpeg`, which has to be on the PATH.
"""

import math
import warnings
from collections.abc import Sequence
from pathlib import Path

from tldl.engines.seam import Segment
from tldl.engines.weights import weights_folder

SAMPLE_RATE = 16_000
"""How many samples a second Whisper and the speech detector take a Track in."""

PASSAGE_SECONDS = 30.0
"""The longest passage: what Whisper hears at once. Speech that runs on for longer is cut at its
longest pause."""

PAUSE_SECONDS = 2.0
"""A silence this long ends a passage. A shorter one stays inside the passage with the speech on both
sides of it, so that Whisper hears a sentence whole and with the ones around it."""

MARGIN_SECONDS = 0.2
"""How much of the silence before and after its speech a passage takes in, so that no word is cut at
its edge."""

LANGUAGE_EXCERPTS = 3
"""On how many excerpts of a Track's speech its language is judged. Whisper judges the language of
half a minute, and the first half minute of a call may hold little but greetings and names."""

WEIGHTS_FILES = ("config.json", "weights.npz")
"""The files of a speech model on Hugging Face that `mlx-whisper` loads."""

Passage = tuple[int, int]
"""Where a passage lies on a Track: its first sample and the one after its last."""


class Whisper:
    """A Whisper speech model as an Engine."""

    def __init__(self, weights: str) -> None:
        """`weights` names the speech model on Hugging Face."""
        self._weights = weights
        self._folder: str | None = None
        # Finding the speech on a two-hour Track takes half a minute, and a Track is asked about
        # twice: for the language and to be recognised.
        self._passages: dict[Path, list[Passage]] = {}

    def detect_language(self, tracks: Sequence[Path]) -> str | None:
        import numpy

        votes: dict[str, float] = {}
        for track in tracks:
            audio = _audio(track)
            for excerpt in _language_excerpts(self._passages_on(track, audio)):
                speech = numpy.concatenate([audio[start:end] for start, end in excerpt])
                # An excerpt counts for as much as the speech it holds, so a Track with a few words
                # on it does not outvote the Track that holds the conversation.
                for language, probability in self._language_probabilities(speech).items():
                    votes[language] = votes.get(language, 0.0) + probability * len(speech)
        return max(votes, key=votes.get) if votes else None

    def recognise(self, track: Path, language: str | None) -> list[Segment]:
        # Imported here and not at the top: loading speech recognition takes seconds, and only a run
        # of this Engine should pay for it.
        import mlx_whisper

        audio = _audio(track)
        passages = self._passages_on(track, audio)
        if not passages:
            return []
        language = language or self.detect_language([track])
        segments = []
        for start, end in passages:
            heard = mlx_whisper.transcribe(
                audio[start:end], path_or_hf_repo=self._weights_folder(), language=language
            )
            segments += [
                Segment(
                    start / SAMPLE_RATE + piece["start"],
                    min(start / SAMPLE_RATE + piece["end"], end / SAMPLE_RATE),
                    text,
                )
                for piece in heard["segments"]
                if (text := piece["text"].strip())
            ]
        return segments

    def _passages_on(self, track: Path, audio) -> list[Passage]:
        if track not in self._passages:
            self._passages[track] = _passages(audio)
        return self._passages[track]

    def _language_probabilities(self, speech) -> dict[str, float]:
        """How likely each language is to be the one spoken in `speech`, half a minute of audio at most."""
        import mlx.core as mx
        from mlx_whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim
        from mlx_whisper.transcribe import ModelHolder

        # The speech model `mlx_whisper.transcribe` loads and keeps, so that it is loaded once.
        model = ModelHolder.get_model(self._weights_folder(), mx.float16)
        spectrogram = log_mel_spectrogram(speech, n_mels=model.dims.n_mels, padding=N_SAMPLES)
        _, probabilities = model.detect_language(pad_or_trim(spectrogram, N_FRAMES, axis=-2).astype(mx.float16))
        return probabilities

    def _weights_folder(self) -> str:
        if self._folder is None:
            self._folder = str(weights_folder(self._weights, WEIGHTS_FILES))
        return self._folder


def _audio(track: Path):
    """The audio of `track` as an array of samples between -1 and 1, SAMPLE_RATE of them a second."""
    import numpy
    from mlx_whisper.audio import load_audio

    return numpy.array(load_audio(str(track), sr=SAMPLE_RATE))


def _passages(audio) -> list[Passage]:
    """The passages of speech in `audio`, in the order spoken. None when it holds no speech."""
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    with warnings.catch_warnings():
        # `torch` warns that the form the speech detector is shipped in is on its way out.
        warnings.simplefilter("ignore", FutureWarning)
        detector = load_silero_vad()
    found = get_speech_timestamps(
        torch.from_numpy(audio),
        detector,
        sampling_rate=SAMPLE_RATE,
        max_speech_duration_s=PASSAGE_SECONDS,
        min_silence_duration_ms=round(PAUSE_SECONDS * 1000),
        speech_pad_ms=round(MARGIN_SECONDS * 1000),
    )
    return [(passage["start"], passage["end"]) for passage in found]


def _language_excerpts(passages: Sequence[Passage]) -> list[list[Passage]]:
    """At most LANGUAGE_EXCERPTS excerpts of the speech in `passages`, spread evenly over it.

    An excerpt is a run of passages that hold half a minute of speech between them, or less.
    """
    excerpts: list[list[Passage]] = []
    length = 0
    for start, end in passages:
        if not excerpts or length + end - start > PASSAGE_SECONDS * SAMPLE_RATE:
            excerpts.append([])
            length = 0
        excerpts[-1].append((start, end))
        length += end - start
    return excerpts[:: max(1, math.ceil(len(excerpts) / LANGUAGE_EXCERPTS))]
