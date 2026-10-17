# Coding standards

Read by the reviewer, not loaded into every session: the Standards axis of `/code-review` looks for this
file and checks the diff against everything it points to. The rules themselves live in one place each;
this file only says where.

## Where the rules are

- Structure, naming, branches: `AGENTS.md`
- Domain vocabulary and ADR conflicts: `docs/agents/domain.md`
- Trial runs on the user's machine: `docs/agents/trial-runs.md`

## Project-specific rules

- **A failure the user can cause ends in a message.** A wrong flag, a wrong value in the configuration file,
  a Recording or Track that is missing or unreadable: the command prints one line in its own form
  ("Cannot transcribe: …", "Recording failed: …", "Cannot make the stereo file of …: …") and exits with a
  failure status. A traceback that can reach the user is a defect.
- **The capture program contract is described once.** Its arguments, events and how values are encoded are
  described in the docstring of `src/tldl/capture.py`, and on the Python side only that module knows them.
  The Swift program, the stand-in in `tests/` and that description change in the same commit.
- **A number meant for tuning has one home.** Thresholds, targets and limits, such as the echo filter's or
  the stereo file's, are named constants at the top of their module, each said in words.
