# 011 — Shift the agent's visual prior to dense / chrome'd slides

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Claude / Yang Jae Kang (chat diagnosis), 2026-05-28.
**Status:** closed 2026-05-28 — corpus chrome'd + 2 dense exemplars + SKILL "Go bespoke when…" triggers + §9 critique density+chrome categories.

---

## TL;DR

After todo 004 – 010 the *capability* is there (deck_chrome / table /
gantt / dense bespoke is all possible), but the user reports the next
deck still comes out toy-density. Diagnosis: **the agent's visual
prior comes from the corpus exemplars, and 11 of the 12 exemplars
were single-pattern toy slides (~10 shapes, no chrome)**. The new
"patterns aren't a ceiling" line in SKILL is one paragraph; the
visual prior won.

Fix the visual prior, not the docs.

---

## What changed

1. **Every corpus exemplar carries chrome.** PREAMBLE in
   `reference_corpus/generate.py` now wraps every entry with
   `h.deck_chrome(eyebrow, footer, page_number, total)` via try/except
   var defaults; per-entry overrides set EYE / FOOTER / PAGE / TOTAL
   to whatever fits the exemplar.

2. **Two new dense bespoke exemplars** (~50 and ~60 shapes each):
   - `proposal_dense.png` — Part 1 / 3 platform comparison cards
     (top half) + 5-stage assembly pipeline row + target metrics
     line. Single content slide, *no pattern call*, hand-composed
     with `h.text` / `slide.shapes.add_shape` from h.* primitives.
   - `personnel_equipment.png` — LEFT half: 4-row personnel table
     (name / role / pct / expertise per row). RIGHT half:
     multi-section equipment list (sequencing / HPC / storage).
     Two independent dense compositions side-by-side.

3. **SKILL "Go bespoke when…" trigger table** — explicit content
   signals that say STOP reaching for a pattern: 3+ structured
   comparison sections, personnel pages, equipment lists with
   sections, two independent compositions side-by-side, KPI + figure
   combos, custom architecture diagrams. Links to the two new
   bespoke exemplars + their source in generate.py.

4. **§9 critique rubric** gains two categories:
   - **Density**: content slide < 20 shapes on a non-trivial brief =
     automatic FAIL, rewrite bespoke.
   - **Chrome**: content slide without `h.deck_chrome` = FAIL.

---

## Why this should actually move the needle

The agent's behaviour at compose time is driven by:
1. What it grep-reads from SKILL §5a
2. What it Read-views from the corpus on first pattern use

Pre-011, both surfaces showed toy patterns. Post-011, both show:
- Chrome on every slide (it's part of the preamble)
- Two dense bespoke slides where pattern density tops out
- Trigger table that names the exact content signals for bespoke
- Critique rubric that flags toy density as a failure

If the agent now produces a toy-density slide, the critique loop
catches it; the agent reads the rewrite hint that points at the
bespoke exemplar; the rewrite happens. The capability was there;
this todo aligns the *defaults* with that capability.

---

## Cross-reference

| Todo | What it shipped | What it didn't |
|---|---|---|
| 004 §A–G | Patterns, grid, chrome-less primitives, corpus mechanism | Density nudge |
| 009 | Inverted "don't reinvent" nudge + deck_chrome + table + gantt | Default visual prior |
| 010 | Render-mode deferred to authoring time | Density defaults |
| **011** | **Visual prior shift: chrome'd corpus + 2 dense exemplars + critique density/chrome** | (see acceptance below) |

---

## Acceptance criteria

A future deck export should show:

1. Every content slide with eyebrow + footer + page number.
2. At least 30% of content slides with ≥ 25 shapes.
3. Tabular content (timelines / personnel / equipment) goes through
   `h.table` or bespoke composition — not `card_grid`.
4. The §9 critique loop flags toy-density slides and rewrites them
   to bespoke before declaring the deck done.

If point #2 still holds in a future deck (toy density dominates), the
agent isn't reading the corpus before composing — that's a SKILL §5
flow issue, not a corpus issue. File a follow-up.

## Follow-up (later same day 2026-05-28)

User reported: even on a fresh session the next deck looked toy
again. **The patterns' existence is the force.** Capability didn't
change; the agent's default behaviour didn't either, because:

- §5a's pattern catalog (14 patterns, two big tables, ~150 lines of
  visual footprint) is what the agent grep's first.
- "Go bespoke when…" was AFTER the catalog in the file. The agent
  read the menu before reading the warning.
- Pattern entries have "When to use" lines that read as broad
  recommendations ("use for thesis / takeaway") rather than narrow
  exact-fit conditions.

So this todo gets a second-pass fix:

1. **§5 opener now explicitly states the default**: "Content slides
   are BESPOKE by default — target ≥ 25 shapes per slide. Patterns
   are narrow shortcuts."
2. **§5a reorganised**: "Go bespoke when…" trigger table + worked-
   example pointers MOVED to the top of §5a, BEFORE the pattern
   catalog. The catalog now lives under "## Pattern shortcuts —
   narrow use only" with a banner saying "When in doubt: bespoke."
3. **Manifest gains `shape_count` per entry.** The agent reads
   `proposal_dense = 42 shapes` next to `evidence_stack = 13 shapes`
   and sees density as a measurable property they consciously
   target.
4. **§9 critique density bar raised** from 20 → 25 shapes for
   content slides. Pattern + chrome ≈ 15 shapes → automatic FAIL.

The capability is still the same. The visible defaults are
materially different.
