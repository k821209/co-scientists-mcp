# 004 — Design methodology for code slides (raise the design ceiling)

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Yang Jae Kang, project `ai-breeding`, 2026-05-26.
**Status:** mostly shipped — §A (critique loop) + §B (pattern library) + §D (grid) + §G (design language doc) landed 2026-05-26; §C/E/F open.

## Resolution log

- **2026-05-26** — §D shipped. `h.grid(sw=, sh=, cols=, rows=, ...)`
  returns a `Grid` with `.cell(col, span, row, row_span)` →
  `(left, top, width, height)`. Default 12 cols × 6 rows, Pt(8) gutters
  + row gaps (the 8pt rhythm), Inches(0.6) side/bottom margins, Inches
  (1.8) top margin so `h.title_block` sits above it. Plus
  `h.SPACING_UNIT_PT = 8` for snippets that want to compute vertical
  gaps as integer multiples. (6 tests, all 330 pass.)
- **2026-05-26** — §G shipped (docs only). paper-deck SKILL adds a
  `Design language:` block to the concept template — a deck-level
  design constitution: grid rules, whitespace ratio, max type sizes
  per slide, color count, section-opener convention. Not parsed by
  the renderer; it's the contract every slide's `code` answers to.
- **Open:** §C (iconography — asset bundle decision),
  §E (semantic type roles — touches existing type_scale callers),
  §F (reference design corpus — curation work).
- **2026-05-26 (same day)** — §A shipped. PyMuPDF (>=1.24) added as a
  dep. `_render_pdf_to_pngs(pdf_path, out_dir, dpi=150)` renders each
  PDF page to `slide_NNN.png` via PyMuPDF; best-effort (returns []
  on missing dep / unreadable PDF). `export_deck_to_pptx` now emits
  per-slide PNGs into the deck's exports folder when the sibling PDF
  exists, and the result dict gains `slide_pngs: [{slide_number,
  local_path, blob_path}]` + `slide_pngs_skipped`. paper-deck SKILL
  §9 documents the critique pass: agent Reads each PNG, scores
  against a 6-category rubric (visual hierarchy / whitespace /
  alignment / type discipline / color discipline / visual
  storytelling), rewrites weak slides' `code` via `update_slide`,
  re-exports — loop max 3 rounds.
- **2026-05-26 (same day)** — §B shipped. New `slide_patterns.py`
  module ships 10 whole-slide patterns:
  `hero_with_trailing_evidence`, `chapter_divider`, `metric_tile_row`,
  `evidence_stack`, `flow_pipeline`, `before_after_split`,
  `contrast_pair`, `quadrant_map`, `numbered_milestone_arc`,
  `zoom_in_callout`. Each encodes designer-level compositional
  decisions (grid placement, type hierarchy, whitespace, color use,
  visual storytelling). Bound to the exec namespace as `p.*`
  (and `patterns`). SKILL §5a gains the pattern catalog table +
  role→pattern recommendations. (10 tests, all 342 pass.)
**Related:** [002](./002_rich_slide_rendering.md), [003 — not filed in this repo; referenced as "solved by paper-deck SKILL §5a rewrite" per 004's cross-reference table]

---

## TL;DR

Todos 002 + 003 took us from *"markdown rendered to PPTX"* to *"agent designs the slide in python-pptx from a content brief"*. That fixed the wrong-paradigm problem. The remaining problem is that the agent's *designs themselves are mediocre* — they're not "markdown-derived" anymore, but they're also not actually good. The agent is placing rectangles and text by intuition with no internalised design principles, no visual vocabulary beyond a few primitive helpers, no reference library, and no critic to push it. Markdown's been beaten; *design* hasn't.

This todo proposes methodology — not more primitives — to raise the ceiling.

---

## Concrete observation

User feedback on the deck `multi-modal-agricultural-ai-…`, 2026-05-26:

> *"일단 마크다운은 넘어선거 같은데, 디자인이 구린데? 디자인 측면을 강조할 수 있도록 방법론을 가져와야할것 같은데?"*

(Roughly: "OK we're past markdown, but the design itself is poor. We need to bring in a methodology that lets the design side shine.")

The user is correct. Looking at the rebuilt batch 1 (S1–S5):

| Slide | What I emitted | Why it's still mediocre |
|---|---|---|
| S1 cover | Title centered + subtitle + venue | Generic centered text. Could be by any tool. No typographic personality, no compositional point of view. |
| S2 eyecatch | pull-quote left + image right | Functional split, but the rhythm is flat — no leading line, no asymmetry that earns the contrast. |
| S3 thesis | Hero centered text + caption strip | Clean but template. The thesis sits in dead center with no surrounding tension. |
| S4 figure | Full-bleed figure + caption | Minimal — the slide is the figure, no design value added. |
| S5 Era I timeline | "Era I" label + horizontal timeline | The most genuinely *designed* of the batch, but raw — markers placed by linear interpolation, no negative space discipline, no visual storytelling devices (arrows of progress, weight changes, color encoding across the row). |

The agent (me) has no internalised design principles to fall back on. It's making coordinate decisions by intuition and the result is what *intuition-driven design* always looks like: cleanly-laid-out mediocrity.

---

## What's missing — the 8 gaps

The agent is composing slides without these:

1. **Grid system.** Every layout uses ad-hoc `Inches(0.7)`. There's no shared 12-column / 8pt-grid discipline forcing alignment.
2. **Pattern library (whole-slide compositions).** The `h.*` helpers are *primitive* (`card`, `bullet_list`, `pull_quote`). Real designers think in *patterns* (`hero-with-trailing-evidence`, `before-after-split`, `metric-tile-row-with-punchline`, `quadrant-map-with-winner-highlighted`, `chapter-divider-with-arc`). The agent has no pattern catalog.
3. **Iconography.** No icons in the entire stack. Slides look like Word docs with rectangles.
4. **Typographic system.** Two sizes, one weight, one accent color. No type-pair theory (display vs body vs label vs caption), no scale rhythm (e.g. perfect-fourth ratios).
5. **Whitespace as a design element.** The agent fills available space; it doesn't strategically *leave* space to create focal weight.
6. **Visual storytelling devices.** Arrows of motion, before/after staging, weight progression, color encoding of progress — none of these are in the helper vocabulary.
7. **Design critic.** Slides are rendered and shipped; there's no automated judge of *"is this actually good"*. The export-time check only verifies that the code didn't crash.
8. **Reference corpus.** The agent has no library of well-designed slides to pattern-match against — it's designing in a vacuum.

---

## Proposed methodology (dev team picks a stack)

These are not mutually exclusive. The highest-leverage combination is **A + D + F** — a critic loop, a pattern library, and a grid system. Effort estimates assume the existing `code` mode infrastructure.

### A. Vision-LLM critic loop (highest leverage, medium effort)

After `_add_code_slide` runs, the export converts the slide to a PNG, hands it to a vision-capable LLM (e.g., Claude with image input), and asks against a rubric:

```
Score 1–5 on:
- Visual hierarchy: is the focal point obvious in 1 second?
- Whitespace: does the slide breathe, or does it feel crowded?
- Alignment: are all elements on an implicit grid?
- Typographic discipline: is the type hierarchy clear and consistent?
- Color discipline: ≤3 colors used semantically?
- Visual storytelling: is there a story device (arrow, contrast, progression),
  or is it just a static composition?

For each <4 score, write one sentence of specific complaint.
```

The agent reads the critic's scores + complaints and rewrites the `code` field. Loop until all categories ≥4 or 3 rounds elapsed.

This is the same pattern as the existing `scientific-image` skill (classify → blueprint → generate → critique). Slides need the same loop.

**Why this matters most:** without a critic, the agent has no signal that its design is mediocre. With a critic, every slide that ships has cleared a bar.

Effort: M — wrap the existing slide render path with a critic pass, pass a vision model the PNG, parse JSON response, regenerate `code` on rounds 2–3.

### B. Pattern library — whole-slide design patterns (high leverage, medium-large effort)

Today's `h.*` is a **primitive** library. Ship a parallel `p.*` (or `patterns.*`) of *whole-slide patterns*, each implementing one or more of these well-known compositions:

| Pattern | When it applies | What it does |
|---|---|---|
| `p.hero_with_trailing_evidence(headline, evidence=[...])` | Thesis / takeaway slides | Massive headline top-left, evidence stack in a vertical column on the right |
| `p.before_after_split(before, after, *, transition_label)` | Risk vs mitigation, slow vs fast, old vs new | Two panels with intentional asymmetry — "before" muted, "after" accent, arrow between |
| `p.metric_tile_row(tiles=[(value, label, unit), ...])` | KPI / quantitative summary | 3–5 large numbers across the top with thin labels under each |
| `p.numbered_milestone_arc(milestones=[...])` | Progressive timeline (Era I) | Numbered markers along a curved or progressive line, each with a brief note. Visual weight changes across the row. |
| `p.quadrant_map(items, axes={x, y})` | Comparative landscape | 2×2 with labeled axes and items placed by their position on each axis |
| `p.evidence_stack(claim, evidence=[...])` | A thesis backed by 2–3 supporting facts | Top: claim in display type. Bottom: stacked evidence rows with citation tags |
| `p.flow_pipeline(steps=[...])` | Process / workflow | Horizontal flow with arrows; each step has a tag + body |
| `p.zoom_in_callout(context_image, callout_region, note)` | Focus on a region of a complex figure | Embeds figure on left, zoomed inset + annotation on right |
| `p.chapter_divider(chapter_label, summary)` | Era I/II/III opener | Massive chapter number + name, summary tagline, no body content. Section break rhythm. |
| `p.contrast_pair(left, right, *, axis_label)` | Two competing options | Mirrored boxes with a header axis defining the contrast |

Each pattern bundles a real designer's compositional decisions — coordinates, type hierarchy, color use, whitespace ratios. The agent picks *a pattern that fits the intent*, not coordinates.

This is **the single highest-leverage change to slide quality**. Patterns encode design knowledge that the agent doesn't have to invent.

Effort: M–L — implement ~10 patterns; each is ~50–150 lines.

### C. Iconography helper (medium leverage, small effort)

`h.icon(name, *, at, size, color=palette["accent"])` that pulls from a vetted icon set (Lucide / Phosphor / Heroicons). Built-in mapping table: `"warning" → triangle`, `"lightning" → bolt`, `"db" → cylinder`, etc.

A slide with even one well-placed icon already feels designed. The current decks have zero.

Effort: S — bundle an icon font or SVG set, write a `_place_icon` helper that mirrors `_place_picture` for SVG.

### D. Grid + spacing system (high leverage, small effort)

Replace ad-hoc `Inches(0.7)` with grid-aware helpers:

```python
g = h.grid(slide, cols=12, gutter=Inches(0.2),
           margin=Inches(0.6), top=Inches(1.8), bottom=Inches(0.6))

g.cell(col_start=1, col_span=7, row_start=1, row_span=3)
   # returns (left, top, width, height) on the canonical grid
```

Every layout snaps to the grid; mis-alignment becomes impossible. The agent doesn't have to think about 0.7 vs 0.5 vs 1.0 — it thinks about "5 cols of 12".

Pair with an explicit 8pt vertical rhythm: `h.spacing.unit = Pt(8)`; all vertical gaps are integer multiples of 8.

Effort: S — implement `grid()` class with `cell()` method, document in §5a.

### E. Typographic scale with type roles (medium leverage, small effort)

Replace the current type_scale's flat numeric overrides with semantic roles:

```python
type_scale = {
  "display.cover": 56,    # cover slide title
  "display.hero": 44,     # hero thesis line
  "display.chapter": 40,  # chapter divider
  "headline.section": 28, # in-slide section header
  "title.slide": 30,      # standard slide title
  "body.large": 22,       # generous body
  "body.standard": 18,    # standard body
  "body.small": 14,       # captions, labels
  "label.tag": 12,        # pills, tags
  "label.caption": 11,    # figure captions
  "scale_ratio": 1.25,    # perfect fourth — relationships derive from this
}
```

The agent picks a *role* ("this text is `label.caption`"), not a *number*. Roles enforce typographic consistency across the deck.

Effort: S — extend `_DEFAULT_TYPE_SCALE`, update helpers to accept role names.

### F. Reference design corpus (medium leverage, medium effort)

Ship a directory of ~30 well-designed slide PNGs with metadata:

```yaml
- file: slides/hero_thesis_with_accent_rule.png
  pattern: hero_with_trailing_evidence
  source: "Stripe annual letter"
  do: "Headline >40pt, evidence in fine print"
  dont: "Don't centre the headline — left-align with intentional whitespace right"
- file: slides/before_after_pipeline.png
  pattern: before_after_split
  source: "Apple keynote 2024"
  do: "Muted left, vibrant right, single arrow between"
```

The agent retrieves the 3 closest examples for its current pattern and follows them.

Effort: M — curate corpus, build retrieval helper.

### G. Per-deck design language manifesto (small leverage, small effort)

`update_deck(concept=...)` already takes free-text concept. Add to the SKILL template an explicit "Design language" block:

```
Design language:
  Grid: 12 cols, 8pt vertical rhythm
  Typography: perfect-fourth scale, max 4 sizes per slide
  Iconography: Lucide line icons, single-weight
  Whitespace: ≥25% per slide should be empty
  Color: accent + 2 grays max; warm amber reserved for hazard
  Motion: implicit only — composition implies direction, no animations
```

This is the *constitution* every slide answers to. The critic (A) judges against it.

Effort: S — SKILL doc update only.

---

## Recommended initial cut

If shipping one thing this week:

→ **D (grid system)**. Largest visible improvement per line of code. Slides instantly look intentional.

If shipping two:

→ **D + C**. Grid + icons. Now slides feel designed.

If shipping three:

→ **D + C + A**. Grid + icons + critic loop. Now slides are critiqued before they ship; the agent gets the feedback it currently lacks.

The full stack (A + B + C + D + E + F + G) is ~the design system a serious slide-tool product would build.

---

## Acceptance criteria

A future agent given the same prompt (*"build a 30-min deck for Korean breeders on multi-modal agricultural AI"*) on a fresh project should produce a first-pass deck where:

1. **A reviewer skimming any single slide cannot tell it was AI-generated** (currently very obvious).
2. **No two consecutive slides use the same layout pattern** — visual rhythm across the deck.
3. **Every slide passes the vision critic on hierarchy + whitespace + alignment** ≥4/5.
4. **Type sizes form a clean scale** — every text element is at a role-defined size, not an ad-hoc number.
5. **Each section opener (Era I/II/III) uses a chapter-divider pattern** distinct from interior slides.

---

## Cross-reference

| Todo | What it solves | What's left |
|---|---|---|
| 001 | Translation-ese in Korean prose | Solved at SKILL level |
| 002 | Markdown rendering ceiling | Solved by `render_mode="code"` |
| 003 | Body-as-structure mindset | Solved by SKILL prose rewrite |
| **004** | **Design ceiling — methodology gap** | **This document.** Methodology > more primitives. |

The progression: 001 (style of prose) → 002 (mechanism of rendering) → 003 (mindset of authoring) → 004 (discipline of designing). Each step climbs one layer; this is the last one.

---

## Suggested labels

`area:skill-paper-deck` · `area:design-methodology` · `priority:high` (largest remaining quality ceiling) · `effort:M (initial), L (full stack)`
