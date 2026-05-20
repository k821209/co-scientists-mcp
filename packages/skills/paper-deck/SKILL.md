---
name: paper-deck
description: Build a presentation deck from a paper. Pick a theme or invent one; outline slides to match audience + duration; draft per-slide content + speaker notes; register every slide in Firestore so the dashboard's Presentation tab can pick it up. Use when the user says "make a deck," "presentation," "lab seminar slides," "talk slides," "poster outline."
---

# /paper-deck

**Triggers:** "build slides from this paper," "make a 20-minute lab
talk," "deck for the Nature poster," "slides for the conference,"
"presentation outline."

## What it does

Turns a manuscript into a structured deck:
- One `decks/{deck_id}` doc holding the **concept** (palette,
  typography, motif) — the single source of visual unity.
- N `decks/{deck_id}/slides/{slide_id}` docs, each with role, title,
  body, prompt, MANDATORY speaker notes, optional code, and a
  `render_mode` declaring how it'll be visualized.

Rendering (slide PNGs, PPTX export) is a separate later step (Phase
3). This skill produces the **drafted** deck — content + structure +
unity header — ready for rendering.

## Hard rules

1. **Speaker notes are MANDATORY** on every non-title slide. Empty
   notes mean the presenter wings the take-home → defeats the purpose.
2. **Concept first, slides second.** The deck's `concept` field
   (palette + typography + motif) is the unity header that every
   slide's `prompt` field inherits. Never write a slide whose prompt
   has bare color names — use placeholders like `{accent}` /
   `{display_font}` that materialize at render time against the
   concept.
3. **Don't fabricate figure references.** If the paper has 2 figures,
   you can't have 5 paper-figure slides. Cap result slides at
   `len(list_figures(slug))`.
4. **`add_slide` then `renumber_deck` once.** Don't renumber by hand —
   the doc IDs encode the original number; renumber updates the
   `slide_number` field, the IDs stay.

## Flow

### 1. Pull paper context

```
paper = mcp__co_scientist__get_paper_state(slug)
figs = mcp__co_scientist__list_figures(slug)
tabs = mcp__co_scientist__list_tables(slug)
prep = mcp__co_scientist__prepare_export(slug)   # for warnings
```

If `prep["warnings"]` shows placeholders or unresolved DOIs, ask the
user whether to proceed or fix first.

### 2. Initialize the deck (idempotent)

```
deck = mcp__co_scientist__create_deck(
  slug,
  title="<presentation title>",
  audience="<lab seminar | Nature poster | conference plenary | …>",
  duration_min=<minutes>,
  theme="<theme_slug>" or None,
  deck_id="<short-slug>" or None,   # auto-derived from title if omitted
)
```

`create_deck` is idempotent — calling with the same `deck_id` returns
the existing doc unchanged. Safe to re-run.

### 3. Draft the concept

Two modes:

**A. With theme**: pick from preset slugs:
- `classical-academic` — serif body, navy + gold accents, dense data
- `minimal-modern-academic` — sans body, cool grey + one accent, lots of whitespace
- `mono-chrome-scholarly` — black/white/grey, hairline rules, prose-heavy
- `data-botanical` — earth tones, organic shapes (plant biology talks)
- `tricolor-brief` — red/yellow/black, 3-min lightning talks

Write a SHORT narrative-arc concept and call:

```
mcp__co_scientist__update_deck(
  slug, deck_id,
  concept="""
    Theme: minimal-modern-academic
    Arc: question → data → answer → caveat → what's next
    Motif: one accent color used only for the figure of merit on every slide
  """,
)
```

**B. Without theme**: invent your own concept. Spell out:

```
mcp__co_scientist__update_deck(
  slug, deck_id,
  concept="""
    Palette:
      bg: #fafaf7  surface: #ffffff  text: #1a1a1a  accent: #b58900
    Typography:
      display: Inter Bold     body: Inter Regular     mono: JetBrains Mono
    Motif:
      a single thin horizontal rule under each title;
      a recurring small icon (#b58900) marking the figure-of-merit line
    Arc:
      problem → setup → result → implications → questions
  """,
)
```

### 4. Outline slides

Standard role sequence, scaled to duration:

| Role         | When | Typical role count for 20-min talk |
| ------------ | ---- | ----------------------------------- |
| `title`      | always | 1 |
| `outline`    | optional, ≥15 min | 0–1 |
| `background` | always | 1–2 |
| `method`     | always | 1–2 |
| `result`     | one per main figure | clamp to `len(figs)` |
| `discussion` | optional | 1 |
| `conclusion` | always | 1 |
| `qa`         | optional | 1 |

Adjust to duration: each slide ≈ 1–2 minutes; 20 min ≈ 12–15 slides.

For each slide, decide the **render_mode**:
- `code-shape` — KPI table, Gantt, org chart, schematic with structured data
- `paper-figure` — re-use a figure from the manuscript (set `figure_number`)
- `ai-image` — eyecatch (cover, closing), abstract concept
- `hybrid` — diagram + numeric table overlay

### 5. Add slides one by one

```
mcp__co_scientist__add_slide(
  slug, deck_id,
  slide_number=N,
  role="<role>",
  title="<slide title>",
  body="<markdown body>",
  prompt="""
    {accent} accent on the trend line. Display font: {display_font}.
    Body: clean grid showing X vs Y across 4 conditions.
  """,
  notes="<MANDATORY speaker notes — what you'll say>",
  code="""```python
    # if render_mode == code-shape, the code that defines the slide
  ```""",
  render_mode="code-shape" | "paper-figure" | "ai-image" | "hybrid",
  figure_number=<N>,   # if render_mode == paper-figure
)
```

**Prompt template rule**: every prompt MUST start with the unity
header using placeholders. Example:

> `"{accent} accent. {display_font} typography. Minimal modern academic
> theme. Body: …"`

Never hardcode `"navy blue"` or `"Inter"` — write `{accent}` /
`{display_font}` so theme switching is a no-op rebuild.

### 6. Renumber once at the end

After adding all slides:

```
mcp__co_scientist__renumber_deck(slug, deck_id)
```

Packs `slide_number`s tightly starting at 1, even if you added them
out of order.

### 7. Mark drafted

```
mcp__co_scientist__update_deck(slug, deck_id, status="drafted")
```

Status flow: `draft` (initial) → `drafted` (slides + notes + prompts
done, ready for rendering) → `rendered` (Phase 3, slide PNGs + PPTX
exist).

### 8. Tell the user

Summary: "Deck `{deck_id}` drafted with N slides at status='drafted'.
Run /paper-deck again to iterate, or wait for Phase 3 rendering to
turn this into slide images + .pptx."

## Acceptance test

`/paper-deck <slug> "lab seminar" 20` should produce:
- One deck doc with concept + theme + audience + duration_min
- 9 default-role slides (title, outline, background ×2, method,
  result × `min(figs, 4)`, discussion, conclusion, qa) — adjusted to
  not exceed the paper's figure count
- Every slide has `notes` non-empty
- Every slide's `prompt` starts with the unity header placeholders
- `status == "drafted"` on the deck

## Common follow-ups

- "Change the theme to data-botanical" → `update_deck(theme=...,
  concept=...)`. Slides don't need to change — their prompts use
  placeholders that re-materialize against the new theme.
- "Cut to 10 minutes" → drop discussion + outline; verify with the
  user before deleting any slide that has good `notes`.
- "Reorder so methods come after background" → `update_slide` each
  affected one with new `slide_number`, then `renumber_deck`.

## Rendering + export (Phase 3 — shipped)

After every slide has its body / prompt / notes filled:

```
mcp__co_scientist__render_deck(slug, deck_id)
```

This walks every slide and:
- `paper-figure` → copies the existing figure blob into a slide image
- `ai-image`     → substitutes `{accent}` etc. from `deck.concept`,
                   calls `generate_image`
- `code-shape` / `hybrid` → returned in `skipped[]` because the MCP
                   can't safely exec arbitrary Python. You're expected
                   to run the slide's `code` block yourself locally
                   (matplotlib/seaborn/etc. into a PNG), then pass
                   that path back:

```
mcp__co_scientist__render_slide(
  slug, deck_id, slide_id,
  local_path="/abs/path/to/slide-3.png",
)
```

Once every slide has an `image_blob_path`, the deck's `status` flips
to `"rendered"` and the dashboard's Presentation tab will offer the
PPTX export. To trigger from Claude Code directly:

```
mcp__co_scientist__export_deck_to_pptx(
  slug, deck_id,
  output_path="~/decks/my-talk.pptx",
)
```

Returns `{ local_path, blob_path, slide_count, missing_renders }`.
`missing_renders[]` is the slide numbers that came out as text-only
placeholders because they hadn't been rendered yet — those should
go back through `render_slide` and the PPTX re-exported.

PPTX layout: 16:9, one slide per deck slide, title at top, image
centered (12.3" × 6"), speaker notes on the notes pane.

python-pptx ships with the base install — nothing extra to install.
