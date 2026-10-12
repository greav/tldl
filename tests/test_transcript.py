"""Building and rendering a Transcript, from plain Segment lists."""

from datetime import datetime

import pytest

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


def test_a_pause_of_two_seconds_starts_a_new_line_and_a_shorter_one_does_not():
    lines = rendered_lines(
        mic=[],
        system=[
            Segment(1.0, 4.0, "First the numbers."),
            Segment(5.5, 8.0, "They are up."),
            Segment(10.0, 12.0, "Now the plan."),
        ],
    )

    # A second and a half of silence, then exactly two seconds of it.
    assert lines == [
        "[00:00:01] **Others:** First the numbers. They are up.",
        "[00:00:10] **Others:** Now the plan.",
    ]


def test_a_line_thirty_seconds_long_ends_at_the_first_end_of_a_sentence_and_not_before():
    lines = rendered_lines(
        mic=[],
        system=[
            Segment(100.0, 112.0, "We looked at the numbers,"),
            Segment(112.5, 125.0, "and they are up."),
            Segment(125.5, 133.0, "So we keep the plan and"),
            Segment(133.5, 140.0, "ship on Friday."),
            Segment(140.5, 145.0, "Any questions?"),
        ],
    )

    # The sentence that ends 25 s into the Line does not end it: the Line is not long enough yet.
    # 33 s into it the Line is long enough but in the middle of a sentence.
    assert lines == [
        "[00:01:40] **Others:** We looked at the numbers, and they are up. So we keep the plan and ship on Friday.",
        "[00:02:20] **Others:** Any questions?",
    ]


@pytest.mark.parametrize("mark", [".", "?", "!", "…"])
def test_a_segment_ends_a_sentence_with_a_full_stop_a_question_mark_an_exclamation_mark_or_an_ellipsis(mark):
    lines = rendered_lines(
        mic=[Segment(0.0, 30.0, f"Thirty seconds of talking{mark}"), Segment(30.5, 32.0, "And then more.")],
        system=[],
    )

    assert lines == [f"[00:00:00] **Me:** Thirty seconds of talking{mark}", "[00:00:30] **Me:** And then more."]


def test_a_line_sixty_seconds_long_ends_though_no_sentence_does():
    lines = rendered_lines(
        mic=[],
        system=[
            Segment(0.0, 20.0, "so first the numbers"),
            Segment(20.5, 40.0, "then the plan"),
            Segment(40.5, 60.0, "then the release"),
            Segment(60.5, 70.0, "and then the questions"),
        ],
    )

    assert lines == [
        "[00:00:00] **Others:** so first the numbers then the plan then the release",
        "[00:01:00] **Others:** and then the questions",
    ]


def test_a_segment_longer_than_a_minute_is_one_line_whole():
    lines = rendered_lines(
        mic=[Segment(0.0, 95.0, "A long story told in one breath"), Segment(95.5, 97.0, "and how it ended.")],
        system=[],
    )

    assert lines == ["[00:00:00] **Me:** A long story told in one breath", "[00:01:35] **Me:** and how it ended."]


def test_short_segments_spoken_close_together_make_one_line():
    lines = rendered_lines(
        mic=[],
        system=[
            Segment(1.0, 1.4, "Yes."),
            Segment(1.6, 2.0, "Right."),
            Segment(2.5, 3.5, "Go on."),
            Segment(5.0, 6.0, "I see!"),
        ],
    )

    assert lines == ["[00:00:01] **Others:** Yes. Right. Go on. I see!"]


def test_an_echo_is_in_no_line_and_ends_none():
    # The microphone's copy starts between the others' two Segments and is the user's only Segment.
    lines = rendered_lines(
        mic=[Segment(10.2, 12.6, "We ship the release on Friday.")],
        system=[
            Segment(10.0, 12.5, "We ship the release on Friday."),
            Segment(13.0, 15.0, "Then we write the notes."),
        ],
    )

    assert lines == ["[00:00:10] **Others:** We ship the release on Friday. Then we write the notes."]


def test_a_segment_that_overlaps_the_one_before_it_or_ends_before_it_starts_joins_the_line():
    lines = rendered_lines(
        mic=[],
        system=[
            Segment(1.0, 5.0, "One moment,"),
            Segment(4.0, 6.0, "let me share my screen."),
            Segment(6.5, 6.2, "There."),
            Segment(7.0, 8.0, "Can you see it?"),
        ],
    )

    assert lines == ["[00:00:01] **Others:** One moment, let me share my screen. There. Can you see it?"]


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

    assert lines == ["[00:00:59] **Me:** One.", "[02:03:04] **Me:** Two."]


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
