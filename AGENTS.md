# tldl

A personal macOS command-line tool that records both sides of a call as two Tracks and turns the Recording
into a Transcript. One user, one Mac, run from Terminal.app.

## Structure

Two programs:

- **Capture program** (Swift) knows only audio and its devices: it is told where to write the mic track and
  the system track and which microphone to take, writes until told to stop, keeps the Mac awake meanwhile,
  and reports levels, each Track's start, the output route, the microphone and errors. It knows nothing
  about Recordings.
- **CLI** (Python) owns everything else: Recording folders, configuration, Engines, Transcripts. It reaches
  the capture program only through that contract.

Every Engine sits behind one seam: a Track goes in, Segments come out. Everything after the seam (merging
the two Tracks, the echo filter, rendering the Transcript) works on Segments alone, so adding an Engine is
one adapter and one name.

## Branches

Name a branch `<type>/<slug>`: type is `feat`, `fix`, `refactor`, `docs`, `test` or `chore`; the slug is a
few lowercase words joined by hyphens, in the glossary's terms. When the work has a folder in `.scratch/`,
the slug is that folder's name, and that branch is the one the work is reviewed and merged from. A ticket
of the work may be built on a short-lived branch named for the ticket, merged into that branch and then
deleted. Never commit feature work to the default branch.

## Configuration

One file, `~/.config/tldl/config.toml`. Every key is optional and the tool runs on defaults without the
file. A command-line flag overrides the file.

## Testing

- **Fast suite**, `uv run pytest`: everything on the Python side except the Engines, driven by ready-made
  Segments and a stand-in capture program, with no speech recognition. It needs `ffmpeg` and `ffprobe` on
  the PATH. Required before any change is done.
- **Engine tests**, `uv run pytest -m engine`: a few slow tests per Engine on short audio files. Required
  when the change touches an Engine.
- **Capture program**: checked by hand, because it needs macOS permissions and real devices. Required when
  the change touches it: make a short Recording and confirm both Tracks hold sound.

## Agent skills

### Issue tracker

Issues and specs live as local markdown files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
