# 006 — Slide typology + layout effects (the 2nd axis of design)

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Yang Jae Kang, project `ai-breeding`, 2026-05-26 (drafted from
direction given in chat; user asked for the structural axis the design
methodology was missing).
**Status:** open · proposal + first cut.
**Related:** [004 §B](./004_design_methodology_for_code_slides.md) (pattern
library — design-intent axis), [005](./005_pattern_library_quality.md)
(pattern QA + contracts).

---

## TL;DR

Todo 004 §B shipped 10 patterns organized by **design intent** (thesis,
comparison, timeline, KPI, …). What's missing is the orthogonal **structural
axis** — *what shape of content this slide carries* (title only, title +
body, title + 1 image, title + N images, title + chart, …). Real slides
sit at the intersection of the two axes; design choices (whitespace,
left/right placement, full-bleed vs caption, grid vs row) flow from the
structural axis, not the intent axis.

This todo fills in the structural axis with 4 new patterns named after
the industry-standard PowerPoint master layouts ([MS support](
https://support.microsoft.com/en-us/office/apply-a-slide-layout-158e6dba-e53e-479b-a6fc-caab72609689))
and documents the compositional rules that govern how content lands
inside them.

---

## Why this axis was missing

The current 10 patterns answer "what is this slide *for*" (a hero, a
comparison, a timeline). They don't answer "what is this slide *made of*"
(title + body, title + 1 image, title + 4 image grid). Without the
structural axis:

- The agent has no canonical pattern for the most common slide kind —
  *title + body* — beyond `text` mode (no design) or hand-building with
  `h.title_block` + `h.bullet_list` (no compositional guidance).
- Multi-image slides have no pattern at all. The agent has to compose
  3+ `h.image_*` calls with hand-rolled coordinates each time.
- Cover slides are buried inside `_add_title_slide` (a private renderer
  for `role='title'` text-mode slides) — not exposed as a callable
  pattern the agent can pick.

PowerPoint's 9 master layouts ([SlideModel](
https://slidemodel.com/how-to-change-slide-layout-in-powerpoint/))
are the established taxonomy every other tool (Canva, Google Slides,
Keynote) descends from. Adopt them as the canonical names so our
patterns slot into a vocabulary the agent already knows.

---

## Canonical structural taxonomy (PowerPoint 9, mapped)

| # | PowerPoint name | Our coverage |
|---|---|---|
| 1 | Title Slide | **missing as pattern** (only `_add_title_slide` for text mode) |
| 2 | Title and Content | **partial** — 8 of our 10 patterns are sub-cases |
| 3 | Section Header | covered by `p.chapter_divider` |
| 4 | Two Content | **missing** as a generic pattern |
| 5 | Comparison | covered by `p.before_after_split`, `p.contrast_pair` |
| 6 | Title Only | covered by calling `h.title_block` alone |
| 7 | Blank | trivially covered (no preamble + free `code`) |
| 8 | Content with Caption | covered by `p.zoom_in_callout` |
| 9 | Picture with Caption | **missing as pattern** |

## Proposed: 4 new structural patterns

| Pattern | Contract | PowerPoint base | When to use |
|---|---|---|---|
| `p.title_slide(slide, *, title, subtitle="", eyebrow="")` | owns slide | 1 (Title Slide) | Deck opener / cover. Centered eyebrow + title + accent rule + subtitle. |
| `p.title_and_body(slide, *, title, body, lead="")` | under title | 2 (Title and Content, plain) | Title + bulleted body in a 60% left column with intentional 40% whitespace on the right. Optional `lead` sentence in display type above the bullets. |
| `p.title_two_content(slide, *, title, left, right)` | under title | 4 (Two Content) | Generic 2-column body. Each side `{heading?, body?, bullets?}`. |
| `p.title_and_image_grid(slide, *, title, images, cols=2, captions=None)` | under title | extension of 4 | N images in a `cols`-column grid (1 = full-bleed; 2 = side-by-side; 4 = 2×2 collage). Optional per-image captions. |

Title Only (6) doesn't need a pattern — calling `h.title_block(slide,
title)` alone is the whole layout.

---

## The 2-axis design matrix

Picking a slide design is a 2-step decision now:

1. **Pick the structural type** (which PowerPoint base?) — driven by the
   content shape (do you have body? images? how many?).
2. **Pick the intent treatment** (which `p.*` design pattern?) — driven
   by the message (thesis? comparison? timeline?).

For example:
- Result slide with 1 figure → structural = (9) Picture with Caption →
  intent = `p.zoom_in_callout` (if there's a callout region) or
  `h.image_figure` (full-bleed).
- Method slide with 4 steps → structural = (2) Title and Content →
  intent = `p.flow_pipeline`.
- Discussion slide with 4 named comparisons → structural = (4) Two
  Content × 2 rows OR a 2×2 → intent = `p.contrast_pair` (pair) or
  `p.title_and_image_grid` (visual quadrant).

---

## Compositional effects (the rules the patterns encode)

These are the design rules the new patterns answer to. Documented in
paper-deck SKILL §5c so the agent has a reference even when building
custom layouts.

### Horizontal placement (left vs right)

- Western reading flows left → right. The *right side* is where the
  audience arrives — the natural "this is the conclusion" position.
- Place the **subject** on the right when you want it to feel like the
  destination. Place it on the left when it's the starting fact.
- `p.before_after_split` deliberately puts BEFORE on the left (history)
  and AFTER on the right (where you arrive).

### Image emphasis (full-bleed vs caption strip)

- **Full-bleed image, no caption** = "the image IS the message". Use when
  the image self-explains and you want emotional weight.
- **Image + caption strip below** = "the image is supporting evidence".
  Use when the image needs a context line; caption stays in body type,
  never display.

### Multi-image arrangement (grid vs row)

- **2×2 grid** = COMPARISON. Items are peers; no order implied.
- **3- or 4-image single row** = PROGRESSION. Left → right reads as
  sequence.
- 1 hero image + N small supporting = FOCUS + context.

### Hierarchy (title position)

- **Title at top** (default): content-first. Audience reads the title,
  then dwells on the body. Most slides.
- **Title centered, no body** (cover / section header / chapter divider):
  the title IS the content. Use for openers and section breaks.

### Whitespace as a design choice

- **Filled body box** = density. Defensible for dense reference data
  (parameter table, dense list).
- **60% column with 40% whitespace** = focus. Use for theses, hero
  statements, KPI tiles — anywhere the audience should land on one
  thing.
- `p.title_and_body` reserves the right 40% as whitespace by default.

---

## Acceptance criteria

A future agent given a slide with content like *"title: '4 primitives of
the harness', body: 4 bullet points"* should:

1. Pick the structural type first (here: Title and Content → 4 items →
   a card grid or a body list).
2. Pick the intent treatment second (here: `evidence_stack` if there's
   a top-level claim, `card_grid` if the 4 items are peer named
   primitives).
3. Both pickings are documented in SKILL §5b table — agent reads role
   + content shape → pattern in two steps.

Bounds + title-collision tests (per todo 005 §D) cover the 4 new
patterns with realistic Korean content.

---

## Cross-reference

| Todo | What it brings |
|---|---|
| 001 | Native-language prose nudges (SKILL doc) |
| 002 | `render_mode="code"` substrate |
| 003 | Body-as-content-brief mindset (SKILL doc) |
| 004 §D, §G | Grid + design language manifesto |
| 004 §A | Per-slide PNG export + critique loop substrate |
| 004 §B | 10 intent-axis patterns |
| 005 | Pattern bug fixes + caller-state contracts |
| **006** | **2nd axis (structural) + 4 missing patterns + layout-effects doc** |

The progression so far: 001–005 climbed *intent* + quality; 006 adds the
orthogonal *structure* axis the agent was missing.

---

## Suggested labels

`area:slide-patterns` · `area:design-methodology` · `priority:medium` ·
`effort:M (4 patterns + doc + tests)`
