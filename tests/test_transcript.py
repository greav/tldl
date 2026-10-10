"""Building and rendering a Transcript, from plain Segment lists."""

from datetime import datetime

from tldl.engines import Segment
from tldl.transcript import build_transcript, render_transcript


def rendered_lines(mic: list[Segment], system: list[Segment], **track_offsets: float) -> list[str]:
    """The lines of the Transcript built from the Segments of the mic track and of the system track."""
    rendered = render_transcript(
        build_transcript(mic, system, **track_offsets),
        title="2026-10-10_1946",
        started=datetime.fromisoformat("2026-10-10T19:46:05+02:00"),
        duration=60.0,
        language=None,
    )
    return [line for line in rendered.splitlines() if line.startswith("[")]


def test_mic_track_segments_are_me_and_system_track_segments_are_others():
    lines = rendered_lines(mic=[Segment(2.0, 3.0, "Mine.")], system=[Segment(0.5, 1.0, "Theirs.")])

    assert lines == ["[00:00:00] **Others:** Theirs.", "[00:00:02] **Me:** Mine."]


def test_the_speaker_labels_stay_in_english_whatever_the_language_spoken():
    lines = rendered_lines(
        mic=[Segment(3.0, 4.0, "Да, слышно хорошо.")], system=[Segment(1.0, 2.0, "Добрый день, меня слышно?")]
    )

    assert lines == [
        "[00:00:01] **Others:** Добрый день, меня слышно?",
        "[00:00:03] **Me:** Да, слышно хорошо.",
    ]


def test_someone_speaking_over_the_other_splits_the_others_line_in_two():
    lines = rendered_lines(
        mic=[Segment(4.0, 4.5, "Right.")],
        system=[Segment(1.0, 6.0, "So the plan is this."), Segment(6.5, 8.0, "We ship on Friday.")],
    )

    assert lines == [
        "[00:00:01] **Others:** So the plan is this.",
        "[00:00:04] **Me:** Right.",
        "[00:00:06] **Others:** We ship on Friday.",
    ]


def test_each_track_is_placed_on_the_timeline_by_how_long_after_the_start_it_begins():
    lines = rendered_lines(
        mic=[Segment(10.0, 11.0, "Asked at ten seconds into the mic track.")],
        system=[Segment(8.0, 9.0, "Answered at eight seconds into the system track.")],
        mic_offset=0.0,
        system_offset=3.5,
    )

    assert lines == [
        "[00:00:10] **Me:** Asked at ten seconds into the mic track.",
        "[00:00:11] **Others:** Answered at eight seconds into the system track.",
    ]


def test_a_timecode_counts_hours_minutes_and_whole_seconds_from_the_start():
    lines = rendered_lines(mic=[Segment(59.99, 61.0, "One."), Segment(7384.2, 7385.0, "Two.")], system=[])

    # Joined into one line, which carries the first Segment's timecode.
    assert lines == ["[00:00:59] **Me:** One. Two."]
    assert rendered_lines(mic=[], system=[Segment(7384.2, 7385.0, "Two.")]) == ["[02:03:04] **Others:** Two."]


def test_a_recording_with_no_speech_renders_as_its_header_alone():
    rendered = render_transcript(
        build_transcript([], []),
        title="2026-10-10_1946_standup",
        started=datetime.fromisoformat("2026-10-10T19:46:05+02:00"),
        duration=7265.9,
        language="ru",
    )

    assert rendered == (
        "# 2026-10-10_1946_standup\n"
        "\n"
        "- Date: 2026-10-10\n"
        "- Start time: 19:46\n"
        "- Duration: 02:01:05\n"
        "- Language: ru\n"
    )
