# tldl

Too long; didn't listen.

A personal macOS command-line tool that records both sides of a call and turns the Recording into a
Transcript, entirely on the Mac. It works with any app that plays sound: Teams, Zoom, Google Meet in a
browser.

A Recording holds two Tracks: the **mic track** is what the microphone heard, the **system track** is
everything the computer played.

## Requirements

- macOS 14.2 or later on Apple silicon. Built and used on macOS 26.
- Terminal.app. macOS grants audio access to the terminal, not to `tldl`; another terminal may record silence
  until it is given the same permissions.
- Swift (the Command Line Tools are enough), [`uv`](https://docs.astral.sh/uv/) and `ffmpeg`.

## Install

```
make install
```

This builds the capture program, installs the `tldl` command with `uv tool install`, and says so if `ffmpeg`
is missing. Run it again to update.

The first `tldl record` makes macOS ask Terminal for two permissions: the microphone, and System Audio
Recording. Allow both. The first `tldl transcribe` with an Engine downloads its speech model from Hugging
Face, once: about 2.4 GB for `parakeet-v3` and 2.9 GB for `whisper-large-v3`. After that nothing leaves the
machine.

## Use

### Record

```
tldl record "sprint planning"
```

Records until Ctrl+C. The title is optional. While it runs, one line shows the elapsed time and a level for
each Track; the Mac is kept awake. The Recording lands in `~/tldl/2026-10-11_1430_sprint-planning/`.

```
tldl record --microphone "MacBook Pro Microphone"
```

Takes the mic track from the named microphone instead of the system's default input, without changing that
default: the call can go on using a headset's microphone while the Recording is made with the built-in one.
A name that is not there stops the Recording before it starts and lists the microphones that are.

### Transcribe

```
tldl transcribe
tldl transcribe 2026-10-11_1430_sprint-planning --engine whisper-large-v3 --lang ru
```

With no argument it takes the latest Recording; otherwise a Recording's folder name or path. The result is
a Markdown file in the Recording folder:

```
[00:00:14] **Others:** Shall we start with the release?
[00:00:17] **Me:** Yes, two things from my side.
```

Each Engine writes its own Transcript, so one Recording can be transcribed by both and the results compared.
Running the same Engine again replaces its Transcript.

| Engine | Language | Notes |
| --- | --- | --- |
| `parakeet-v3` | Takes none; writes what it hears | Faster |
| `whisper-large-v3` (default) | Detected once per Recording, or given with `--lang` | Slower. Given one language, it tends to write words spoken in another in that language |

### Stereo file

```
tldl stereo
```

Puts both Tracks of a Recording into one file, `stereo.flac`: the mic track in the left channel, the system
track in the right, lined up in time and brought to a comparable loudness. It is for playing a Recording back
and for tools that take one file. The Tracks are not changed.

## What a Recording holds

```
~/tldl/2026-10-11_1430_sprint-planning/
  mic.flac                         the mic track
  system.flac                      the system track
  recording.json                   start time, each Track's start, output route, microphone
  transcript.whisper-large-v3.md   the Transcript, one per Engine
  segments.whisper-large-v3.json   what the Engine heard, including lines the echo filter removed
  stereo.flac                      the stereo file, if made
```

Audio reaches the disk while the Recording runs, so a crash or a closed terminal costs only the last moments,
and an interrupted Recording can still be transcribed. Recordings are kept until you delete them.

## Configuration

Optional, in `~/.config/tldl/config.toml`. Every key may be left out, and a flag wins over the file.

```toml
recordings_root = "~/tldl"
engine = "whisper-large-v3"
language = "ru"
microphone = "MacBook Pro Microphone"
```

`tldl record --microphone default` goes back to the system's default input for one run. A key the tool does
not know is refused with a message, so a misspelt key is never silently ignored.

## Headphones or loudspeakers

On loudspeakers the microphone hears the others too, so their words are recognised twice. An echo filter
leaves out the lines under **Me** that copy a line under **Others**, but it does not catch everything. The
cleanest Transcript comes from headphones with the Mac's built-in microphone.

## Good to know

- If a level stays at zero while there is sound, Terminal lacks a permission. Both are under System Settings,
  Privacy & Security: Microphone, and Screen & System Audio Recording (the "System Audio Recording Only"
  list). macOS gives silence, not an error, when one is missing.
- The system track holds everything the computer plays, not only the call, and it does not depend on the
  volume or on mute.
- The mic track records you even when you are muted in the call.
- The microphone and the output are fixed when a Recording starts. If the microphone disappears, the Recording
  stops with a message and keeps what it captured.

## Development

```
uv run pytest             # the fast suite; needs ffmpeg and ffprobe
uv run pytest -m engine   # slow tests that run the real Engines
```

The capture program has no automated tests: it needs macOS permissions and real devices, so it is checked by
making a short Recording and confirming both Tracks hold sound.
