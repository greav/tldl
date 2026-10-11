---
status: accepted
---

# Swift captures audio, Python does everything else

tldl is two programs: a small Swift program that only captures the two Tracks, and a Python CLI that owns
everything else (Recording folders, configuration, Engines, building the Transcript). Capture is in Swift
because the macOS system-audio API exists only as Objective-C headers and delivers audio on a real-time
callback. The rest is in Python because that is where the local speech Engines live, and trying several
Engines is a goal of the project.

The Swift program knows nothing about Recordings: it is told where to write the two Tracks and which
microphone to take, writes audio until told to stop, and reports what it captures (levels, when each Track
started, the output route, the microphone) and errors. It also keeps the Mac awake while it writes, because
that hold then ends with the process however the process ends. That keeps it small and rarely changed.

The system track is captured with a Core Audio process tap of everything the computer plays, read through an
aggregate device. It is the one first-party way to get that sound that is audio only: it asks for the narrow
"System Audio Recording Only" permission and needs no extra software and no video pipeline. The price is a
floor of macOS 14.2, and silence instead of an error when the permission is missing.

The mic track and the system track come from two devices with two clocks and sometimes two sample rates, so
the Swift program writes each to its own file as it arrives and does nothing to line them up. Whatever needs
both in one place, the Transcript's timeline or the stereo file, is derived after the Recording from the two
files and the Track starts noted in the metadata. A mistake in joining can then be made good from the Tracks;
made during capture, it would have damaged the Recording itself.

## Considered options

For the two programs:

- **Everything in Swift, one binary.** One toolchain and the Engine in-process, which suits a future live
  mode. Rejected for now because every Python-only Engine would have to be run as an external program anyway.
  Moving to a single binary later stays open; it would mean rewriting the Python side, not the capture side.
- **Everything in Python.** Rejected: the Python bindings for the capture API are flagged as unproven by their
  own author, and Python is a poor fit for a real-time audio callback.
- **Rust.** Rejected: its system-audio capture support is recent, it has the fewest ready Engines, and the
  toolchain is not installed.

For the system track:

- **ScreenCaptureKit.** It delivers system audio and, from macOS 15, the microphone in one stream. Rejected:
  it is a screen-capture API, so it needs the broader Screen Recording permission and a display or window to
  capture, and on macOS 15 and later the system shows a recurring alert that a command-line tool has no way
  to avoid.
- **A virtual loopback driver**, such as BlackHole. It works on any macOS and from any language. Rejected: the
  user has to install a driver and send their output through a Multi-Output Device for every call.

For the two Tracks:

- **One two-channel file written during capture.** Rejected: both channels of a file share a sample rate and a
  sample count, so one of the two would have to be resampled and corrected for drift in real time.
- **One aggregate device holding the microphone and the tap, with Core Audio's drift correction.** It would
  deliver both in step. Not taken: it would replace a capture path proven on built-in, wired and Bluetooth
  microphones, and nothing has yet shown drift to be a problem. Drift over a long Recording has not been
  measured.
