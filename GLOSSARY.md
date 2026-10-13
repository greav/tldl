# tldl

A personal command-line tool that records what is said on a call, on both sides, and turns it into text.

## Language

**Recording**:
One continuous capture of audio, from the moment the user starts it to the moment they stop it, together with
everything derived from it.
_Avoid_: Meeting, call, session

**Track**:
One of the two audio streams that make up a Recording: the mic track or the system track.
_Avoid_: Channel, stream

**Mic track**:
The Track holding what the user's microphone heard.
_Avoid_: Input, local audio

**System track**:
The Track holding what the computer played.
_Avoid_: Output, loopback, remote audio

**Speaker**:
Who a Line of a Transcript is attributed to: **Me** for speech from the mic track, **Others** for speech from
the system track.
_Avoid_: Participant, user, remote

**Segment**:
A continuous stretch of speech on one Track: when it starts, when it ends, and what was said.
_Avoid_: Utterance, line, chunk

**Engine**:
What turns a Track into Segments, identified by a name. The same software with a different speech model is a
different Engine.
_Avoid_: Backend, transcriber, provider, model

**Transcript**:
The text of a Recording as one Engine heard it: the Segments of both Tracks in chronological order, each
attributed to a Speaker. A Recording has at most one Transcript per Engine.
_Avoid_: Notes, minutes, summary

**Line**:
A stretch of one Speaker's speech in a Transcript under one timecode, made of one or more consecutive
Segments of that Speaker.
_Avoid_: Block, paragraph, turn

**Timecode**:
Where a Line begins in its Recording: the time from the start of the Recording to the start of the Line's
first Segment, written `[HH:MM:SS]`.
_Avoid_: Timestamp, time

**Stereo file**:
One audio file holding both Tracks of a Recording: the mic track in its left channel, the system track in its
right. It is derived from the Tracks and can be made again from them.
_Avoid_: Mix, mixdown, combined recording, merged audio

**Capture program**:
The program that captures the two Tracks of a Recording. It knows audio and its devices and nothing about
Recordings.
_Avoid_: Recorder, helper, daemon

**Recordings root**:
The folder under which every Recording has its own folder.
_Avoid_: Output directory, library

**Output route**:
What the computer was playing sound through when a Recording started: loudspeakers or headphones.
_Avoid_: Output device, audio route

**Echo filter**:
What keeps out of a Transcript the Segments on the mic track that are copies of what the Others said, picked
up by the microphone from the loudspeakers.
_Avoid_: Echo cancellation, deduplication

**Segments file**:
The machine-readable record of what one Engine heard in a Recording: every Segment of both Tracks with its
Speaker, kept beside that Engine's Transcript.
_Avoid_: JSON transcript, raw transcript
