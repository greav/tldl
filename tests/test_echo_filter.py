"""The echo filter, from plain Segment lists: what the Transcript shows and what the Segments file marks.

On loudspeakers the microphone hears the others, so their words come back as Segments of the mic
track. Each case below gives the Segments of the two Tracks and reads the result as the user does.
"""

import json
from datetime import datetime

from tldl.engines import Segment
from tldl.transcript import build_transcript, render_segments_file, render_transcript


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


def removed_texts(mic: list[Segment], system: list[Segment], **track_offsets: float) -> list[str]:
    """The texts of the Segments that the Segments file marks as removed by the echo filter."""
    rendered = render_segments_file(
        build_transcript(mic, system, **track_offsets), engine="parakeet-v3", duration=60.0, language=None
    )
    return [segment["text"] for segment in json.loads(rendered)["segments"] if segment["echo"]]


def test_an_exact_echo_is_left_out_of_the_transcript():
    lines = rendered_lines(
        mic=[Segment(10.2, 12.6, "We ship the release on Friday."), Segment(14.0, 15.0, "Fine with me.")],
        system=[Segment(10.0, 12.5, "We ship the release on Friday.")],
    )

    assert lines == [
        "[00:00:10] **Others:** We ship the release on Friday.",
        "[00:00:14] **Me:** Fine with me.",
    ]


def test_an_echo_the_engine_heard_a_little_differently_is_removed():
    # The microphone's copy is noisier, so the Engine mishears a word and loses the last one:
    # nine of the copy's ten words are in the others' Segment, in the same order.
    mic = [Segment(10.3, 14.0, "So the plan is to sheep the release on Friday.")]
    system = [Segment(10.0, 14.2, "So, the plan is to ship the release on Friday morning.")]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Others:** So, the plan is to ship the release on Friday morning."
    ]
    assert removed_texts(mic, system) == ["So the plan is to sheep the release on Friday."]


def test_a_copy_with_seven_of_its_ten_words_in_the_others_segment_is_removed_and_one_with_six_is_kept():
    system = [Segment(10.0, 14.0, "The new build goes out to all the customers on Monday.")]
    seven_of_ten = [Segment(10.3, 14.1, "The new bill goes out to tall the customer Monday.")]
    six_of_ten = [Segment(10.3, 14.1, "The new bill goes out to tall a customer Monday.")]

    assert removed_texts(seven_of_ten, system) == ["The new bill goes out to tall the customer Monday."]
    assert removed_texts(six_of_ten, system) == []


def test_a_copy_the_engine_placed_a_moment_before_the_others_segment_is_removed():
    # An Engine does not place the start of the same speech at the same instant on both Tracks:
    # here the microphone's copy comes out 80 ms ahead of what it copies, as `parakeet-v3` did on a
    # loudspeaker Recording. Nobody repeats seven words that fast.
    mic = [Segment(11.76, 14.64, "Someone has to write the release notes.")]
    system = [Segment(11.84, 14.7, "Someone has to write the release notes.")]

    assert rendered_lines(mic, system) == ["[00:00:11] **Others:** Someone has to write the release notes."]
    assert removed_texts(mic, system) == ["Someone has to write the release notes."]


def test_the_users_line_is_kept_when_the_same_words_come_from_the_others_half_a_second_later():
    # The user's own words coming back from the far end of the call, half a second late.
    mic = [Segment(11.3, 14.2, "Someone has to write the release notes.")]
    system = [Segment(11.8, 14.7, "Someone has to write the release notes.")]

    assert removed_texts(mic, system) == []


def test_when_the_others_repeat_the_user_the_users_line_is_kept():
    # The user spoke first; the same words then come from the others. Nothing here is an echo.
    mic = [Segment(10.0, 11.5, "Let's ship it on Friday.")]
    system = [Segment(12.0, 13.5, "Let's ship it on Friday.")]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Me:** Let's ship it on Friday.",
        "[00:00:12] **Others:** Let's ship it on Friday.",
    ]
    assert removed_texts(mic, system) == []


def test_a_copy_that_starts_shortly_after_the_others_finished_is_removed():
    # The copy starts 1.5 s after the others' Segment ended.
    mic = [Segment(14.0, 16.0, "We ship the release on Friday.")]
    system = [Segment(10.0, 12.5, "We ship the release on Friday.")]

    assert removed_texts(mic, system) == ["We ship the release on Friday."]


def test_the_user_saying_the_others_words_back_later_is_kept():
    # The same words 2 s after the others finished them: the user reading the decision back.
    mic = [Segment(14.5, 16.5, "We ship the release on Friday.")]
    system = [Segment(10.0, 12.5, "We ship the release on Friday.")]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Others:** We ship the release on Friday.",
        "[00:00:14] **Me:** We ship the release on Friday.",
    ]
    assert removed_texts(mic, system) == []


def test_a_one_word_reply_that_happens_to_match_is_kept():
    # "Friday" is in the others' Segment, and so is every word of "On Friday", but a reply this
    # short is the user's own unless it is the whole of what the others said.
    mic = [Segment(13.0, 13.5, "Friday."), Segment(20.0, 20.8, "On Friday?")]
    system = [Segment(10.0, 12.5, "Shall we ship on Thursday or on Friday?"), Segment(18.0, 19.5, "So on Friday then.")]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Others:** Shall we ship on Thursday or on Friday?",
        "[00:00:13] **Me:** Friday.",
        "[00:00:18] **Others:** So on Friday then.",
        "[00:00:20] **Me:** On Friday?",
    ]
    assert removed_texts(mic, system) == []


def test_a_one_or_two_word_copy_is_removed_when_it_is_all_the_others_said():
    mic = [Segment(10.1, 10.6, "okay"), Segment(11.2, 12.0, "Thank you.")]
    system = [Segment(10.0, 10.5, "Okay."), Segment(11.0, 11.9, "Thank you!")]

    assert rendered_lines(mic, system) == ["[00:00:10] **Others:** Okay. Thank you!"]
    assert removed_texts(mic, system) == ["okay", "Thank you."]


def test_an_empty_segment_is_never_an_echo():
    # An Engine can return a Segment with no words in it. It is the copy of nothing.
    mic = [Segment(10.1, 10.6, "..."), Segment(12.0, 12.4, "")]
    system = [Segment(10.0, 10.5, "..."), Segment(11.0, 11.9, "Thank you!")]

    assert removed_texts(mic, system) == []


def test_both_talking_at_once_keeps_the_users_line():
    # The microphone heard the user and the loudspeakers together, so the Engine wrote down a mix of
    # the two: 6 of its 11 words are the others'. It is kept, garbled as it is, because the user's
    # words are in it.
    mic = [Segment(10.4, 14.0, "So the no wait plan is that cannot ship work Friday.")]
    system = [Segment(10.0, 13.5, "So the plan is to ship on Friday.")]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Others:** So the plan is to ship on Friday.",
        "[00:00:10] **Me:** So the no wait plan is that cannot ship work Friday.",
    ]
    assert removed_texts(mic, system) == []


def test_one_copy_that_runs_across_two_of_the_others_segments_is_removed():
    # The Engine cut the others' speech in two and the microphone's copy of it not at all. Neither
    # of the others' Segments holds most of the copy's words; the two together hold all of them.
    mic = [Segment(10.2, 15.1, "First we look at the numbers then at the plan for next week.")]
    system = [
        Segment(10.0, 12.4, "First we look at the numbers."),
        Segment(12.9, 15.0, "Then at the plan for next week."),
    ]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Others:** First we look at the numbers. Then at the plan for next week."
    ]
    assert removed_texts(mic, system) == ["First we look at the numbers then at the plan for next week."]


def test_two_copies_that_fall_inside_one_of_the_others_segments_are_removed():
    # The other way round: the Engine cut the microphone's copy in two and the others' speech not at all.
    mic = [Segment(10.2, 12.5, "First we look at the numbers."), Segment(12.9, 15.1, "Then at the plan for next week.")]
    system = [Segment(10.0, 15.0, "First we look at the numbers, then at the plan for next week.")]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Others:** First we look at the numbers, then at the plan for next week."
    ]
    assert removed_texts(mic, system) == ["First we look at the numbers.", "Then at the plan for next week."]


def test_the_users_line_is_kept_when_the_others_start_repeating_it_before_it_ends():
    # The others asked, the user answered, and the others began saying the answer back while the
    # user was still finishing it. The user's words match only speech that started after them.
    mic = [Segment(12.5, 15.0, "We ship it on Friday morning.")]
    system = [Segment(10.0, 11.5, "When do we ship it?"), Segment(13.4, 15.5, "We ship it on Friday morning, okay.")]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Others:** When do we ship it?",
        "[00:00:12] **Me:** We ship it on Friday morning.",
        "[00:00:13] **Others:** We ship it on Friday morning, okay.",
    ]
    assert removed_texts(mic, system) == []


def test_russian_words_are_compared_without_case_punctuation_or_the_dots_on_yo():
    # The Engine writes "ё" in one place and "е" in another for the same word.
    mic = [Segment(10.2, 13.0, "давайте ещё раз посмотрим на пул реквест"), Segment(14.1, 14.8, "Все понятно")]
    system = [Segment(10.0, 12.9, "Давайте, ещё раз посмотрим на пул-реквест."), Segment(14.0, 14.7, "Всё понятно?")]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Others:** Давайте, ещё раз посмотрим на пул-реквест. Всё понятно?"
    ]
    assert removed_texts(mic, system) == ["давайте ещё раз посмотрим на пул реквест", "Все понятно"]


def test_a_russian_reply_of_one_word_that_happens_to_match_is_kept():
    mic = [Segment(13.0, 13.6, "В пятницу."), Segment(13.9, 14.5, "Хорошо.")]
    system = [Segment(10.0, 12.5, "Хорошо, тогда выкатываем в пятницу или в понедельник?")]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Others:** Хорошо, тогда выкатываем в пятницу или в понедельник?",
        "[00:00:13] **Me:** В пятницу. Хорошо.",
    ]


def test_a_word_with_an_apostrophe_is_one_word():
    # "That's right" is a two-word reply, kept unless it is all the others said; the apostrophe the
    # Engine writes may be either of the two.
    mic = [Segment(13.0, 13.8, "That's right."), Segment(16.1, 16.9, "That's right.")]
    system = [Segment(10.0, 12.5, "I think that's right for now."), Segment(16.0, 16.8, "That’s right.")]

    assert rendered_lines(mic, system) == [
        "[00:00:10] **Others:** I think that's right for now.",
        "[00:00:13] **Me:** That's right.",
        "[00:00:16] **Others:** That’s right.",
    ]
    assert removed_texts(mic, system) == ["That's right."]


def test_a_copy_is_looked_for_where_the_tracks_lie_on_the_recordings_timeline():
    # The mic track began 5 s after the system track. Counted from the start of each Track the
    # first pair looks like the others repeating the user and the second like an echo; on the
    # Recording's timeline it is the other way round.
    mic = [
        Segment(5.3, 7.6, "We ship the release on Friday."),
        Segment(20.3, 22.6, "I will write the release notes."),
    ]
    system = [
        Segment(10.0, 12.5, "We ship the release on Friday."),
        Segment(20.0, 22.5, "I will write the release notes."),
    ]

    assert rendered_lines(mic, system, mic_offset=5.0, system_offset=0.0) == [
        "[00:00:10] **Others:** We ship the release on Friday. I will write the release notes.",
        "[00:00:25] **Me:** I will write the release notes.",
    ]
    assert removed_texts(mic, system, mic_offset=5.0, system_offset=0.0) == ["We ship the release on Friday."]


def test_a_conversation_with_no_echo_is_left_as_it_was():
    # On headphones the microphone hears only the user, who agrees, asks back and talks over the others.
    mic = [
        Segment(3.0, 3.4, "Hello."),
        Segment(9.0, 9.5, "Okay."),
        Segment(15.5, 17.0, "On Friday, are you sure?"),
        Segment(22.0, 25.0, "Then I will write the release notes on Thursday."),
    ]
    system = [
        Segment(1.0, 2.5, "Hello everyone."),
        Segment(5.0, 8.8, "The plan is to ship the release on Friday."),
        Segment(10.0, 15.0, "Someone has to write the release notes before that."),
        Segment(17.5, 18.0, "Yes."),
        Segment(24.0, 26.0, "Thursday works, thank you."),
    ]

    assert rendered_lines(mic, system) == [
        "[00:00:01] **Others:** Hello everyone.",
        "[00:00:03] **Me:** Hello.",
        "[00:00:05] **Others:** The plan is to ship the release on Friday.",
        "[00:00:09] **Me:** Okay.",
        "[00:00:10] **Others:** Someone has to write the release notes before that.",
        "[00:00:15] **Me:** On Friday, are you sure?",
        "[00:00:17] **Others:** Yes.",
        "[00:00:22] **Me:** Then I will write the release notes on Thursday.",
        "[00:00:24] **Others:** Thursday works, thank you.",
    ]
    assert removed_texts(mic, system) == []


def test_the_segments_file_keeps_an_echo_and_marks_it_as_removed():
    transcript = build_transcript(
        [Segment(10.2, 12.6, "We ship the release on Friday."), Segment(14.0, 15.0, "Fine with me.")],
        [Segment(10.0, 12.5, "We ship the release on Friday.")],
    )

    segments_file = json.loads(render_segments_file(transcript, engine="parakeet-v3", duration=60.0, language=None))

    assert segments_file["segments"] == [
        {"speaker": "Others", "start": 10.0, "end": 12.5, "text": "We ship the release on Friday.", "echo": False},
        {"speaker": "Me", "start": 10.2, "end": 12.6, "text": "We ship the release on Friday.", "echo": True},
        {"speaker": "Me", "start": 14.0, "end": 15.0, "text": "Fine with me.", "echo": False},
    ]
