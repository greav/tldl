---
status: accepted
---

# The two Tracks are captured apart and joined only afterwards

The mic track and the system track come from two devices with two clocks and sometimes two sample rates, so
the capture program writes each to its own file as it arrives and does nothing to line them up. Whatever needs
both in one place, the Transcript's timeline or the stereo file, is derived after the Recording from the two
files and the Track starts noted in the metadata. A mistake in joining can then be made good from the Tracks;
made during capture, it would have damaged the Recording itself.

## Considered options

- **One two-channel file written during capture.** Rejected: both channels of a file share a sample rate and a
  sample count, so one of the two would have to be resampled and corrected for drift in real time.
- **One aggregate device holding the microphone and the tap, with Core Audio's drift correction.** It would
  deliver both in step. Not taken: it would replace a capture path proven on built-in, wired and Bluetooth
  microphones, and nothing has yet shown drift to be a problem. Drift over a long Recording has not been
  measured.
