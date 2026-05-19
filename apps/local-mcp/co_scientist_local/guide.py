"""Canonical agent-facing guide for the co-scientist MCP.

Returned by the `project_guide()` MCP tool. Update HERE (not in the
dashboard's CLAUDE.md template) so changes flow to all users on
`pip install --upgrade co-scientist-local` — even those whose CLAUDE.md
on disk was downloaded months ago.

CLAUDE.md on the user's project directory stays tiny (project identity
only) and refers the agent here on every session start.
"""
from __future__ import annotations

GUIDE_VERSION = "2026-05-19c"


def render_guide() -> str:
    """The canonical session-start guide, rendered as markdown."""
    return f"""# co-scientist MCP — session guide (v{GUIDE_VERSION})

## How this project works

A human collaborator views the dashboard and can leave inline comments on
specific passages by drag-selecting in the manuscript. Each comment lands
in Firestore as a `review` with `source='user'`, `status='open'`, plus an
`anchor_text` field containing the exact selected passage and a
`manuscript_ref` like `section:<key>`. The dashboard renders the anchor
as a yellow highlight in the rendered manuscript; clicking the highlight
opens a popover with the comment.

On every session start:

1. Call `mcp__co_scientist__whoami()` once — verifies the MCP is bound to
   the project_id your CLAUDE.md mentions. If they differ, STOP and tell
   the user — they likely mixed `.mcp.json` and `CLAUDE.md` from two
   different dashboard projects. (The MCP also prints a stderr warning
   banner on startup when this mismatch is detected.)
2. Call `mcp__co_scientist__list_papers()` then, for each paper,
   `mcp__co_scientist__count_open_user_comments(slug)`. If non-zero,
   call `mcp__co_scientist__list_reviews(slug, status="open")` to get
   the open comments with their `anchor_text` — use that quoted passage
   to locate the exact place in the manuscript the user is pointing at,
   then offer `/paper-revision`.

## Available skills

- `/paper-writing [title]` — create or update manuscript sections
- `/paper-revision` — address open user comments (anchor_text-anchored)
- `/paper-export [docx|tex|pdf|md]` — pandoc-based export with placeholder/
  unresolved-DOI pre-flight check; uploads result to Storage so the
  dashboard's Paper page lists it.
- `/literature-review [topic] [slug?]` — CrossRef keyword search via
  `search_works`, candidate-then-pick UX, registers selected via
  `add_reference_by_doi`, writes a structured synthesis.
- `/paper-review [slug] [mode?]` — three-persona AI review (methods /
  stats / domain) + consistency pass; each finding becomes one
  Firestore review row (`source="ai"`) anchored to the offending
  passage so the dashboard renders inline highlights.
- `/analysis-run [name]` — wrap a computation (local or registered HPC)
  in a tracked run, then `add_figure` / `add_table` selected outputs.
  Dashboard Runs tab streams logs in real time.
- `/scientific-image` — staged pipeline (classify → blueprint →
  generate → critique) around `generate_image` for schematics
  (pathway, network, workflow, comparison, architecture, tree).
  Real data plots go through `/analysis-run` instead.
- `/paper-deck [slug] [audience] [duration_min] [--theme slug]` —
  Phase 1 of the presentation pipeline: write deck-level concept
  (palette/typography/motif) + outline slides scaled to duration +
  per-slide content with MANDATORY speaker notes + prompt placeholders.
  Rendering and PPTX export are Phase 3.

## Tool surface (~60 tools under `mcp__co_scientist__*`)

papers · sections · reviews · figures · tables · references · analyses · runs
servers (HPC) · exports · image gen · whoami · project_guide

## Citation format + hallucination check

Inline DOI: `{{doi:10.1234/example}}`. References auto-managed via
`mcp__co_scientist__add_reference_by_doi(slug, doi)` — fetches title,
authors, journal, year from CrossRef so you never invent them. Refuses
DOIs CrossRef can't find (404 → almost always a hallucinated citation).

Two-axis verification model — and the MCP only owns one of them:

  - **DOI axis** (server-decidable): does CrossRef know this DOI?
    Browser Sync button and `validate_references` both write this.
    Deterministic — no LLM needed.
  - **Context axis** (YOU decide, not the server): does the cited
    paper's content actually fit the manuscript's claim around its
    `{{doi:X}}` marker? Word-overlap is too weak a proxy; only you
    have the manuscript intent loaded.

Workflow YOU follow per session:

1. Call `mcp__co_scientist__validate_references(slug)`. It returns a
   facts pack:
     - `unresolved[]` — CrossRef 404s. Almost always fake DOIs.
     - `missing_doi[]` — references with no DOI to check.
     - `results[]` — one entry per resolved DOI with:
         * `crossref`: title, abstract, subjects, authors, year, journal
         * `manuscript_contexts`: every `{{doi:X}}` occurrence with
           full sentence + ±240 char context + `stacked_with` peers
         * `signals`: raw overlap counts (HINTS, not verdicts)
2. For each `results[]` entry, READ the crossref abstract/title and
   compare against `manuscript_contexts`. Decide if the citation fits.
3. Record your decision:
     `acknowledge_finding(slug, doi, verdict="approved"|"rejected",
        note="<why>")`
   - approved → context_verified=true → dashboard ribbon turns green
   - rejected → context_verified=false → fix the citation (delete or
     replace via `add_reference_by_doi`) before next session

For unresolved DOIs, just delete the reference (or replace via
`add_reference_by_doi(slug, real_doi)`) and `acknowledge_finding(slug,
doi, note="hallucinated, removed")`.

The dashboard shows two ribbons per reference (`✓ DOI` / `✓ Context`).
`?` Context means you haven't judged it yet. Both green = trusted.

**On every session start, also call**
`mcp__co_scientist__list_verification_findings(slug)` for each paper.
Returns unacknowledged problem findings (unresolved hallucinations,
title mismatches, errors). If non-empty:
  1. Surface them to the user.
  2. Fix each (delete bad ref / replace with real citation / re-fetch
     via `add_reference_by_doi`).
  3. Call `acknowledge_finding(slug, doi, note="...")` once handled
     so it stops surfacing.

For single-citation spot checks: `verify_doi(doi)` returns metadata
without writing anything.

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
