---
status: accepted
---

# The system track comes from a Core Audio process tap

The system track is captured with a Core Audio process tap of everything the computer plays, read through an
aggregate device. It is the one first-party way to get that sound that is audio only: it asks for the narrow
"System Audio Recording Only" permission and needs no extra software and no video pipeline. The price is a
floor of macOS 14.2, and silence instead of an error when the permission is missing.

## Considered options

- **ScreenCaptureKit.** It delivers system audio and, from macOS 15, the microphone in one stream. Rejected:
  it is a screen-capture API, so it needs the broader Screen Recording permission and a display or window to
  capture, and on macOS 15 and later the system shows a recurring alert that a command-line tool has no way
  to avoid.
- **A virtual loopback driver**, such as BlackHole. It works on any macOS and from any language. Rejected: the
  user has to install a driver and send their output through a Multi-Output Device for every call.
