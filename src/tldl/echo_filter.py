"""The echo filter: which Segments of the mic track are copies of what the others said.

On loudspeakers the microphone hears the others, so the Engine recognises their words a second time
on the mic track. The filter finds those copies from the Segments alone and never reads a Track.

The four numbers below are starting values, to be tuned on real Recordings.
"""

import re
from collections.abc import Sequence

from tldl.engines import Segment

CONTAINMENT = 0.7
"""The share of a mic-track Segment's words that must appear, in the same order, in what the others
said for the Segment to be a copy of it."""

FOLLOWS_WITHIN = 1.75
"""How many seconds after the others finished a mic-track Segment may start and still be a copy."""

EXACT_UP_TO = 2
"""A mic-track Segment of this many words or fewer is a copy only when the others said exactly that:
"yes" and "right" are said by both sides."""

STARTS_TOGETHER = 0.25
"""How many seconds before the others' Segment a copy of it may seem to start. An Engine does not
place the start of the same speech at the same instant on both Tracks. A mic-track Segment further
ahead than this is the user's own, and the others are repeating it."""


def echoes(me: Sequence[Segment], others: Sequence[Segment]) -> list[bool]:
    """For each Segment of `me`, whether it is a copy of what `others` said.

    `me` holds the Segments of the mic track and `others` those of the system track, each in the
    order spoken, with times on one timeline.

    A Segment of `me` is a copy when it starts during a Segment of `others` or shortly after it, and
    most of its words appear in the same order in what the others said from that Segment until the
    copy ended. What the others began to say after the Segment of `me` began can complete that match
    and cannot make it: when most of the Segment's words are found in that later speech alone, the
    user said them first and the others are repeating them.
    """
    said_by_others = [_words(segment.text) for segment in others]

    def is_echo(mine: Segment) -> bool:
        my_words = _words(mine.text)
        if not my_words:
            return False

        def is_copy_of(said: Sequence[str]) -> bool:
            return _count_in_order(my_words, said) / len(my_words) >= CONTAINMENT

        for first, theirs in enumerate(others):
            if not theirs.start - STARTS_TOGETHER <= mine.start <= theirs.end + FOLLOWS_WITHIN:
                continue
            if len(my_words) <= EXACT_UP_TO:
                if my_words == said_by_others[first]:
                    return True
                continue
            # The Engine cuts the same speech into Segments differently on each Track, so the copy
            # is compared with everything the others said from this Segment until the copy ended.
            until_my_end = [
                (later, words)
                for later, words in zip(others[first + 1 :], said_by_others[first + 1 :])
                if later.start < mine.end
            ]
            said_until_my_end = said_by_others[first] + [word for _, words in until_my_end for word in words]
            said_after_my_start = [
                word
                for later, words in until_my_end
                if later.start > mine.start + STARTS_TOGETHER
                for word in words
            ]
            if is_copy_of(said_until_my_end) and not is_copy_of(said_after_my_start):
                return True
        return False

    return [is_echo(mine) for mine in me]


def _words(text: str) -> list[str]:
    """The words of `text` as they are compared: lower case and without punctuation, in any script.

    An Engine does not write one word one way every time, so an apostrophe inside a word is dropped
    and the Russian "ё" is read as "е".
    """
    return re.findall(r"\w+", re.sub("['’]", "", text.casefold()).replace("ё", "е"))


def _count_in_order(mine: Sequence[str], theirs: Sequence[str]) -> int:
    """How many words of `mine` appear in `theirs` in the same order: the longest common subsequence."""
    longest = [0] * (len(theirs) + 1)
    for word in mine:
        above_left = 0
        for index, their_word in enumerate(theirs, start=1):
            above = longest[index]
            longest[index] = above_left + 1 if word == their_word else max(above, longest[index - 1])
            above_left = above
    return longest[-1]
