"""Building a Transcript from the Segments of the two Tracks, and writing it down.

Everything here works on Segments alone: nothing knows which Engine they came from or reads audio.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from tldl.echo_filter import echoes
from tldl.engines import Segment

LINE_PAUSE = 2.0
"""How many seconds of silence in one Speaker's speech end a Line: a Segment that starts this long or
longer after the Line's last Segment ends starts a new Line."""

LINE_LENGTH = 30.0
"""How many seconds long a Line gets before it ends at the first end of a sentence."""

LINE_LIMIT = 60.0
"""How many seconds long a Line gets before it ends anyway, for speech with no end of a sentence in it."""


class Speaker(StrEnum):
    """Who a Line of a Transcript is attributed to. The labels stay in English in every Transcript."""

    ME = "Me"
    OTHERS = "Others"


@dataclass(frozen=True)
class SpokenSegment:
    """A Segment attributed to a Speaker and placed on the Recording's timeline."""

    speaker: Speaker
    start: float
    """Seconds from the start of the Recording."""
    end: float
    """Seconds from the start of the Recording."""
    text: str
    echo: bool = False
    """True for a Segment the echo filter removed: the microphone hearing what the others said."""


@dataclass(frozen=True)
class Line:
    """One paragraph of a Transcript: one or more consecutive Segments of one Speaker under one timecode."""

    start: float
    """When its first Segment starts, in seconds from the start of the Recording."""
    speaker: Speaker
    text: str


@dataclass(frozen=True)
class Transcript:
    segments: list[SpokenSegment]
    """Every Segment of both Tracks, in the order spoken, the ones the echo filter removed included."""
    lines: list[Line]
    """The speech as it reads: the Segments the echo filter left, consecutive ones of one Speaker
    joined into Lines."""


def build_transcript(
    mic_segments: Sequence[Segment],
    system_segments: Sequence[Segment],
    *,
    mic_offset: float = 0.0,
    system_offset: float = 0.0,
) -> Transcript:
    """Build the Transcript of a Recording from the Segments of its mic track and its system track.

    Mic-track Segments are attributed to Me and system-track Segments to Others. `mic_offset` and
    `system_offset` are how many seconds after the start of the Recording each Track begins; they put
    the Segments of both Tracks on the Recording's one timeline.

    The echo filter always runs: a mic-track Segment that is the microphone hearing the others is
    marked and left out of the Lines.
    """
    me = [_placed(segment, mic_offset) for segment in mic_segments]
    others = [_placed(segment, system_offset) for segment in system_segments]
    spoken = [
        SpokenSegment(Speaker.ME, segment.start, segment.end, segment.text, echo=echo)
        for segment, echo in zip(me, echoes(me, others))
    ] + [SpokenSegment(Speaker.OTHERS, segment.start, segment.end, segment.text) for segment in others]
    spoken.sort(key=lambda segment: segment.start)
    return Transcript(spoken, _lines([segment for segment in spoken if not segment.echo]))


def _placed(segment: Segment, offset: float) -> Segment:
    """`segment` on the Recording's timeline, given how long after its start the Segment's Track begins."""
    return Segment(offset + segment.start, offset + segment.end, segment.text)


def _lines(segments: Sequence[SpokenSegment]) -> list[Line]:
    """The Lines that `segments`, in the order spoken, read as.

    A Segment starts a new Line when its Speaker is not the Speaker of the Line before it, when it
    starts `LINE_PAUSE` or longer after that Line's last Segment ends, when that Line is `LINE_LENGTH`
    long or longer and its last Segment ends a sentence, or when that Line is `LINE_LIMIT` long or
    longer. Otherwise it joins that Line. A Line is as long as from the start of its first Segment to
    the end of its last, and no Segment is ever cut: one longer than `LINE_LIMIT` is a Line that long.

    An Engine can give a Segment that overlaps the one before it, or one whose end lies before its
    start. The times are taken as given: a pause below zero ends no Line.
    """
    runs: list[list[SpokenSegment]] = []
    for segment in segments:
        if runs and not _starts_a_line(segment, runs[-1]):
            runs[-1].append(segment)
        else:
            runs.append([segment])
    return [Line(run[0].start, run[0].speaker, " ".join(segment.text for segment in run)) for run in runs]


def _starts_a_line(segment: SpokenSegment, line: Sequence[SpokenSegment]) -> bool:
    """Whether `segment` starts a new Line, given the Segments of the Line before it."""
    last = line[-1]
    length = last.end - line[0].start
    return (
        segment.speaker != last.speaker
        or segment.start - last.end >= LINE_PAUSE
        or (length >= LINE_LENGTH and last.text.endswith((".", "?", "!", "…")))
        or length >= LINE_LIMIT
    )


def timecode(seconds: float) -> str:
    """Seconds as `HH:MM:SS`."""
    whole = int(seconds)
    return f"{whole // 3600:02}:{whole // 60 % 60:02}:{whole % 60:02}"


def render_transcript(
    transcript: Transcript, *, title: str, started: datetime, duration: float, language: str | None
) -> str:
    """The Transcript as Markdown: a header about the Recording, then one paragraph per Line.

    `started` is when the Recording started, `duration` its length in seconds. `language` is shown
    when there is one to show: the Engine reported it or the user gave it.
    """
    header = [
        f"# {title}",
        "",
        f"- Date: {started:%Y-%m-%d}",
        f"- Start time: {started:%H:%M}",
        f"- Duration: {timecode(duration)}",
    ]
    if language:
        header.append(f"- Language: {language}")
    paragraphs = ["\n".join(header)] + [
        f"[{timecode(line.start)}] **{line.speaker}:** {line.text}" for line in transcript.lines
    ]
    return "\n\n".join(paragraphs) + "\n"


def render_segments_file(
    transcript: Transcript, *, engine: str, duration: float, language: str | None
) -> str:
    """The Segments file: the Transcript's Segments as JSON, for rendering it again without the Engine.

    Its keys:

        engine    the name of the Engine that heard the Segments
        language  the language shown in the Transcript's header, or null
        duration  the length of the Recording in seconds
        segments  every Segment of both Tracks in the order spoken, each with its `speaker` (`Me` or
                  `Others`), its `start` and `end` in seconds from the start of the Recording, and
                  its `text`. `echo` is true for a Segment the echo filter removed: it is in this
                  file and not in the Transcript
    """
    content = {
        "engine": engine,
        "language": language,
        "duration": round(duration, 3),
        "segments": [
            {
                "speaker": segment.speaker,
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": segment.text,
                "echo": segment.echo,
            }
            for segment in transcript.segments
        ],
    }
    return json.dumps(content, ensure_ascii=False, indent=2) + "\n"
