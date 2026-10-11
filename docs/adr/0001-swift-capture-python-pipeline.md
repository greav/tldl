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

## Considered options

- **Everything in Swift, one binary.** One toolchain and the Engine in-process, which suits a future live
  mode. Rejected for now because every Python-only Engine would have to be run as an external program anyway.
  Moving to a single binary later stays open; it would mean rewriting the Python side, not the capture side.
- **Everything in Python.** Rejected: the Python bindings for the capture API are flagged as unproven by their
  own author, and Python is a poor fit for a real-time audio callback.
- **Rust.** Rejected: its system-audio capture support is recent, it has the fewest ready Engines, and the
  toolchain is not installed.
