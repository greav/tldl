# Trial runs on this machine

For an agent that goes beyond the test suites on the user's Mac: a real capture, `make install`, a real
Engine, one of the user's Recordings. The fast suite needs none of this; it gives every test a home folder
of its own.

## The user's files

- `~/tldl/` and `~/.config/tldl/` are the user's. Work in a temporary folder. `tldl transcribe <folder>` and
  `tldl stereo <folder>` take a Recording by its path, so nothing under the home folder is written.
  `tldl record` writes under the user's Recordings root: for a trial capture, run the capture program itself
  with two paths in the temporary folder.
- A Recording of the user's is private speech. Read one only when the user has said so, on a copy in a
  temporary folder, and delete the copy afterwards. Its audio and its text stay out of the repo, the tests
  and commit messages.

## A real capture

- At most five seconds, into a temporary folder; delete the audio afterwards. It records the room and
  whatever the computer is playing.
- macOS may ask for a permission with nobody there to answer. If capture hangs or records silence, stop,
  note what you saw and go on. Whether both Tracks hold real sound is the user's check.
- The system's volume, mute and default devices change only when the task is about them, and are put back
  as found.

## `make install`

It replaces the user's installed `tldl`. To try it without that, point `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR`
at temporary folders.

## A real Engine

The speech models are in `~/.cache/huggingface`, a few gigabytes each. A run under another home folder keeps
`HF_HOME` on that cache, or it downloads them again.

## In a git worktree

Files git ignores are not there: the story's folder under `.scratch/` and the skills under `.claude/skills`.
Read them from the main checkout by absolute path, and write nothing there.

## Criteria only the user can check

A criterion that begins "By hand, by the user" stays unticked. Build what it depends on and report what a
trial showed.
