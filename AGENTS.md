# tldl

<One or two sentences: what this is and who uses it.>

## Structure

\<Project-specific: the project's layers, what may import what, and how things are named.>

## Branches

Name a branch `<type>/<slug>`: type is `feat`, `fix`, `refactor`, `docs`, `test` or `chore`; the slug is a
few lowercase words joined by hyphens, in the glossary's terms. When the work has a folder in `.scratch/`,
the slug is that folder's name. Never commit feature work to the default branch.

## Configuration

\<Project-specific: where configuration lives, how it reaches each class.>

## Testing

\<Project-specific: what runs, what is required before a change is considered done.>

## Agent skills

### Issue tracker

Issues and specs live as local markdown files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
