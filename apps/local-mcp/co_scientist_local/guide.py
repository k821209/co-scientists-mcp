"""Canonical agent-facing guide for the co-scientist MCP.

Returned by the `project_guide()` MCP tool. Update HERE (not in the
dashboard's CLAUDE.md template) so changes flow to all users on
`pip install --upgrade co-scientist-local` — even those whose CLAUDE.md
on disk was downloaded months ago.

CLAUDE.md on the user's project directory stays tiny (project identity
only) and refers the agent here on every session start.
"""
from __future__ import annotations

GUIDE_VERSION = "2026-05-18"


def render_guide() -> str:
    """The canonical session-start guide, rendered as markdown."""
    return f"""# co-scientist MCP — session guide (v{GUIDE_VERSION})

## How this project works

A human collaborator views the dashboard and can leave inline comments on
paragraphs, figures, and claims. Those comments land in Firestore as
`reviews` with `source='user'`.

On every session start:

1. Call `mcp__co_scientist__whoami()` once — verifies the MCP is bound to
   the project_id your CLAUDE.md mentions. If they differ, STOP and tell
   the user — they likely mixed `.mcp.json` and `CLAUDE.md` from two
   different dashboard projects.
2. Call `mcp__co_scientist__list_papers()` then, for each paper,
   `mcp__co_scientist__count_open_user_comments(slug)`. If non-zero,
   surface them and offer `/paper-revision`.

## Available skills

- `/paper-writing [title]` — create or update manuscript sections
- `/paper-revision` — address open user comments (the bidirectional loop)
- `/paper-review` — run AI reviewers
- `/paper-export [docx|tex|pdf]` — pandoc-based export
- `/literature-review [topic]` — search + add references
- `/analysis-run [name] [command]` — local or registered-HPC

## Tool surface (~60 tools under `mcp__co_scientist__*`)

papers · sections · reviews · figures · tables · references · analyses · runs
servers (HPC) · exports · image gen · whoami · project_guide

## Citation format

Inline DOI: `{{doi:10.1234/example}}`. References auto-managed via
`mcp__co_scientist__add_reference_by_doi`, assembled into BibTeX on export.

## Math mode (Pandoc)

Use `$...$` (inline) or `$$...$$` (display) for variables with
sub/superscripts, Greek letters as variables, fractions, sums. Leave
`n = 69` / `q < 0.005` / `α-helix` as plain text. `prepare_export` returns
`math_warnings` flagging violations.

## Remote job rule

**Never** launch a long-running remote job via raw `ssh <alias> "nohup ..."`.
Use `mcp__co_scientist__submit_remote_job` so the run is tracked in
`analysis_runs` and visible in the dashboard.

## Image generation

`mcp__co_scientist__generate_image` routes through a Firebase Cloud Function
(Pro+ subscription required for the hosted OpenAI gpt-image-2 backend).
Free-tier users with their own `GEMINI_API_KEY` can still generate images
locally via the Gemini backend (imagen-3).
"""
