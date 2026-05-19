---
name: paper-export
description: Export a paper to .docx / .tex / .pdf / .md via Pandoc. Use when the user says "export," "download as Word/PDF/LaTeX," "send to journal," or any phrasing that asks for a finished document file.
---

# /paper-export

**Triggers:** "export to docx," "give me a PDF," "download as LaTeX,"
"submit-ready file," "save the paper," "convert to Word."

## What this skill does (high level)

Calls the MCP's `prepare_export` to gather everything Pandoc needs
(assembled manuscript, BibTeX from registered references, figures /
tables / supplementary, placeholders + unresolved DOI warnings), then
`export_to_path` to actually run Pandoc and upload the resulting file
to Cloud Storage under `papers/{slug}/exports/`.

No re-implementation of the export pipeline in the skill — the MCP
tools encapsulate the whole flow. The skill's job is to ASK what
format/path, surface warnings, and call the right tool.

## Flow

### 1. Resolve the target paper

- If the user already named a slug, use it.
- Otherwise call `mcp__co_scientist__list_papers()` and ask which one.

### 2. Run `prepare_export(slug)` — pre-flight check

The tool returns a bundle with a `warnings` array plus dedicated lists:

- `placeholders[]` — TBD / TK / XXX / TODO / FIXME / `[...]` markers
- `unresolved_citations[]` — `{doi:…}` references not in `references/`
- `warnings[]` — short human-readable summary

If any of these are non-empty, **surface them to the user and ask
whether to proceed**:

> "Found 3 placeholders and 2 unresolved DOIs. Continue with export
> anyway, or fix first?"

Recommended fixes BEFORE export:

- Placeholders → grep the section bodies for `TODO`/etc. and either
  resolve them or strip the markers.
- Unresolved DOIs → call `add_reference_by_doi(slug, doi)` for each
  missing DOI (CrossRef-backed; refuses fakes).
- Empty sections → ask the user whether they're intentionally blank.

If the user wants to proceed despite warnings, continue.

### 3. Decide format + output path

- Default format: **docx** (most common journal submission target).
- Other accepted formats: `tex`, `pdf`, `md`.
- Default path: `./{slug}.{ext}` in the current working directory
  unless the user supplied one.

### 4. Run `export_to_path`

```
mcp__co_scientist__export_to_path(
  slug,
  output_path="<absolute path or ./{slug}.{ext}>",
  fmt="docx" | "tex" | "pdf" | "md",
)
```

The tool:
- Re-runs `prepare_export` (so warnings are fresh)
- Writes manuscript.md + references.bib + every figure file into a
  temp dir
- Invokes Pandoc with appropriate flags (citeproc when a bib exists,
  `-t latex` for tex, etc.)
- Uploads the output blob to Storage at
  `papers/{slug}/exports/{filename}` so it's downloadable from the
  dashboard.

Returns `{ local_path, blob_path, fmt, rc, stderr, warnings }`.

### 5. Confirm + tell the user where the file is

- Local path: `output_path` (the file on the user's machine).
- Cloud copy: dashboard's Paper → Manuscript card will list it under
  Exports.

If `rc != 0` or stderr mentions errors, surface them. Most failures are:
- Pandoc not installed → ask the user to `brew install pandoc` /
  `apt install pandoc`
- LaTeX engine missing (for PDF) → suggest `--pdf-engine=...` or
  fall back to DOCX
- Unicode math errors → tell user to check `prepare_export`'s
  warnings

## Safety rules

- **NEVER skip `prepare_export` warnings silently**. The dashboard's
  DOI-verification system depends on those warnings being surfaced to
  the user.
- **NEVER re-invent the export pipeline** in the skill (don't manually
  build BibTeX, don't manually run pandoc). The MCP tools already do
  it; deviating risks shipping stale figure data — the original
  co-scientist had a May 2026 incident where re-implemented assembly
  shipped an outdated figure caption.
- **NEVER hardcode a CSL path**. `prepare_export` returns
  `suggested_csl_filename` based on the paper's journal — pass it
  through verbatim. Future versions will resolve it against a CSL
  repo automatically.

## Common follow-ups

- "Make it ready for Nature" → set `paper.journal = "Nature"` via
  `update_paper`, then re-export so CSL gets the right hint.
- "Strip references" → call `delete_reference` for each; warnings will
  shift to "unresolved citations" instead. Decide with the user
  whether to leave inline DOI markers as plain text or remove them.
- "Add supplementary figures only" → there's no separate supplementary
  export yet; the main export already includes supplementary figures
  (`figure_number >= 101`) and tables at the end. Future iteration:
  a separate `--supplementary` flag.
