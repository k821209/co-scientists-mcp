# 010 — Defer slide-mode decision from outline to authoring time

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Yang Jae Kang (via chat), 2026-05-27.
**Status:** closed 2026-05-28 — `render_mode` is now optional + inferred from populated fields; SKILL flow rewritten so the agent designs per slide instead of pre-committing at outline time.

---

## TL;DR

The user pushed back on the outline-time `render_mode` decision: when
the agent is still writing the deck's content brief, they can't honestly
say "slide 7 is a code slide, slide 8 is paper-figure." That decision
*depends on the content* — text content might want a designed code
slide, a figure might want hybrid, etc. Forcing the decision upfront
locks in the wrong design.

The fix is to defer the render_mode decision to **authoring time** —
after the agent has read the brief and decided how this specific
slide's content lands best.

---

## What changed

1. **`render_mode` is optional on `add_slide`.** Default is `None`
   (instead of the silent `"code-shape"` it used to silently fall
   back to). Outline-time `add_slide` is now a pure content brief:
   `role / title / body / notes`. No mode.

2. **`_infer_render_mode(slide)` in `deck_render.py`.** Picks a mode
   from which fields the agent populated. Priority:
   - `regions[]`                       → `hybrid`
   - `code` with python-pptx signals   → `code`
   - `figure_number`                    → `paper-figure`
   - `image_blob_path`                  → `ai-image` (already rendered)
   - `prompt`                           → `ai-image` (needs generation)
   - `code` without python-pptx signals → `code-shape`
   - otherwise                          → `text`

3. **`_resolve_mode(slide)`** wraps that: explicit `render_mode`
   always wins; falls back to inference when `None`. Every dispatch
   point (render_slide / render_deck / _slide_is_rendered /
   export_deck_to_pptx) uses this resolver instead of reading
   `render_mode` directly.

4. **paper-deck SKILL flow rewritten.** Step 4 (Outline slides) drops
   the render_mode discussion entirely — just roles + content briefs.
   Step 5 (was "Add slides one by one") renamed to "**Design + author
   each slide**" and walks through: read brief → decide design →
   author by populating the right fields → mode is inferred. Includes
   a fields-to-mode mapping table so the agent always knows what the
   inference picks.

---

## Why this matters

Pre-deciding mode at outline time pushed the agent toward shallow
defaults (every slide a `code` slide because that's the "rich" mode,
or every slide `text` because it's safe). Deferring the decision lets
the slide's *content* drive the design:

- Result slide whose paper figure carries the message → `figure_number`
  set, mode inferred as `paper-figure`. Full-bleed figure, no body.
- Result slide that needs KPI tiles + a caption strip + a figure →
  `code` field with `p.metric_tile_row` + `h.image_figure`, mode
  inferred as `code`.
- Method slide whose 4 workflow steps fit `flow_pipeline` → `code`
  field with `p.flow_pipeline(items=...)`, mode inferred as `code`.

The agent never wrote "render_mode='code'" — it just authored the
slide. Same for the other modes.

---

## Tests

10 new tests covering inference of every mode + explicit-override
precedence + `add_slide` without `render_mode` storing None + an end-
to-end export where mode flows from a populated `code` field. 404
total passing.

---

## Cross-reference

Closes one of the few remaining DX taxes the agent paid every deck —
the outline-time mode commitment. Combined with 009 (patterns aren't a
ceiling) and 008 (figure_full / Noto Sans KR / hero adaptive), the
agent now has a clean path from "I have a paper" to "I have a
proposal-grade deck" without pre-committing to shapes that don't fit
the content.
