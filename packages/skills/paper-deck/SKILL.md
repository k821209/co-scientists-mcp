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
5. **Native-language flow when the audience is non-English** (todo 001).
   Detect the audience language from `audience`, the user's prompt, or
   the deck concept. When it's Korean / Japanese / Chinese / etc.:
   - Draft *natively* in that language. Do **not** write English first
     and translate — that produces translation-ese a native reader
     spots immediately.
   - Keep English **only** for field-standard abbreviations (GWAS,
     BLUP, MCP, F4, GO, etc.). Translate everyday English nouns to the
     target language (shortcut → 지름길, process → 과정, …).
   - Use the target language's own punctuation conventions. In Korean,
     prefer colons and natural sentence breaks over em-dash chains
     (`X — Y → Z` reads as machine-translated English).
   - Keep sentence endings **consistent** within a slide (Korean: all
     `~합니다` or all `~한다`, not mixed).
   - Self-check: "Could a native speaker mentally reverse-translate
     this to English word-for-word?" If yes, rewrite before delivery.

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
  aspect_ratio="16:9",   # "16:9" (default) | "16:10" | "4:3"
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
    Type scale:
      title: 32  head: 26  body: 20  line_spacing: 1.22
      hybrid_body: 18  hybrid_head: 22  cover_title: 40  caption: 12
    Motif:
      a single thin horizontal rule under each title;
      a recurring small icon (#b58900) marking the figure-of-merit line
    Design language:
      Grid: 12 columns, 8pt vertical rhythm, Inches(0.6) side margins.
      Whitespace: >= 25% of each slide reads as empty — leave breathing room.
      Max 4 distinct type sizes per slide; type sizes only from `type_scale`.
      Max 3 colors per slide: accent + foreground + one neutral.
      Visual storytelling: every section opener (Era I/II/III) uses a
        chapter-divider pattern distinct from interior slides.
      Iconography: leave room for accent icons (filed for follow-up,
        todo 004 §C); for now use accent-colored shapes as visual anchors.
    Arc:
      problem → setup → result → implications → questions
  """,
)
```

The `Type scale:` block is **optional** — unspecified keys fall back to
defaults (title 32 / head 26 / body 20 / line_spacing 1.22 / cover 40).
Override any of them per deck:
- **Smaller body** (16–18pt) when slides are dense and projected close.
- **Larger title** (36–40pt) when the audience is at the back of a room.
- **Tighter line_spacing** (1.1–1.15) for code-heavy slides.

Avoid going below 14pt — the export's auto-shrink (TEXT_TO_SHAPE) will
already step down when individual slides overrun.

The `Design language:` block is the deck's **design constitution** —
free-text rules every slide answers to (todo 004 §G). Not parsed by
the renderer; it's a contract you write to yourself as the slide
author. When you draft each slide's `code`, check it against this
block. Defaults to use if you don't write one:
- 12-column grid, 8pt vertical rhythm
- ≥ 25% whitespace per slide
- ≤ 4 type sizes, ≤ 3 colors per slide
- Section openers use a distinct (chapter-divider) layout from
  interior slides

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

For each slide, decide the **render_mode**. This decides whether the
slide's text stays editable in the exported .pptx — choose carefully:

- `text` — title + plain bullet body rendered as **NATIVE, editable
  PowerPoint text** (each `body` line → one paragraph, no markdown
  parsing). Use for any slide that is genuinely just title + a list
  with no design treatment needed. The reviewer can edit it in
  PowerPoint and it inherits the deck's fonts / colors.
- `code` — **YOU author the slide via python-pptx code in `code`**.
  At export, the snippet runs against a namespace where `slide`,
  `palette`, `fonts`, `type_scale`, `Pt`, `Inches`, `MSO_SHAPE`, and
  a `h` helpers namespace are pre-bound. The slide ends up as
  NATIVE editable shapes — title, accent stripe, cards, bullets,
  figures — composed exactly the way you wrote them. **This is how
  you ship designed text slides** (card grids, two-column compares,
  pull-quote callouts, banner-and-bullets) without baking the slide
  into a PNG. Examples + the `h.*` catalog: §5a.
- `paper-figure` — re-use a manuscript figure full-bleed (set `figure_number`).
- `ai-image` — a generated image: an eyecatch (cover / closing) or an
  abstract concept slide that is image-led, not text-led.
- `code-shape` — a single PNG you draw with code, embedded **full-bleed**.
  ⚠ The WHOLE slide becomes a flat picture — any text in it is baked
  into the bitmap, NOT editable in the .pptx, and ignores the deck's
  fonts/theme. Use it **only** for a genuine code-drawn data visual
  (a real plot / chart). **Never** make a prose- or bullet-heavy slide
  `code-shape` — for those, the right answer is `code` (native editable
  shapes), not `code-shape` (baked image).
- `hybrid` — **title + native body bullets (rendered in the LEFT half)
  + one or more image regions** (positioned by you, typically on the
  right). This is the right mode for "title + bullets + a figure /
  diagram" — the bullets stay editable native text, the figure is an
  image region. Also for multi-image slides. Set with
  `set_slide_regions` (see "Multi-image slides"). Don't set this in
  `add_slide`'s render_mode — let `set_slide_regions` flip it.

Rule of thumb: **if the slide is mostly words AND needs any visual
treatment beyond a flat bullet list, it is a `code` slide.** Use `text`
only when "title + plain bullets, no design" is exactly what you want.
`code-shape` / `ai-image` are for slides that are fundamentally a picture.

**Role → recommended render_mode** (start here; adapt only with a reason):

| Role         | Default mode    | When to deviate                                 |
| ------------ | --------------- | ----------------------------------------------- |
| `title`      | `code` (cover layout) or `ai-image` | `text` for a stripped-down opener |
| `outline`    | `code` (card grid) or `hybrid` | `text` only for a bare bullet outline |
| `background` | `code` or `text` | `hybrid` when there's a prior-state schematic |
| `question`   | `code` (centered big-display) | `text` for a plainer treatment |
| `method`     | `hybrid`        | Workflow / pipeline diagram on the right        |
| `result`     | `paper-figure` (full bleed) **or** `hybrid` | `code` for KPI tiles around a figure |
| `discussion` | `code` (comparative grid) or `hybrid` | `text` if 3 bullets fit |
| `conclusion` | `code` (take-home card grid) | `text` for plain 3 take-home bullets |
| `qa`         | `text`          | Acknowledgments + contact, plain                |

**Dense-slide layout patterns** — when the content is heavy, pick the
layout up-front rather than letting auto-shrink rescue an over-stuffed
slide (it will, but readability suffers):

| Pattern             | When                                            | How                                          |
| ------------------- | ----------------------------------------------- | -------------------------------------------- |
| Hero (full-bleed)   | A single decisive figure or eyecatch            | `paper-figure` or `ai-image`, no body        |
| Banner + bullets    | A take-home one-liner above structured points   | `text` with the H1 used as banner            |
| 50-50 hybrid        | Title + bullets + one figure on the right       | `hybrid`, one region at `x:0.54 y:0.22 w:0.42 h:0.65` |
| Quadrant collage    | Two-to-four comparable images, no body          | `hybrid`, regions on a 2×2 grid              |
| Compact text + caption strip | Lots of small-print explainer + figure | `hybrid`, large image region + thin caption  |

If your `text` slide overflows even at default 20pt body, your first
move is **drop content** (split into two slides, demote one bullet to
the speaker notes), not lower the type — going below 16pt is a smell.

### 5. Add slides one by one

```
mcp__co_scientist__add_slide(
  slug, deck_id,
  slide_number=N,
  role="<role>",
  title="<slide title>",
  body="<plain-text body — lines become bullets; not markdown-parsed (§5a)>",
  prompt="""
    {accent} accent on the trend line. Display font: {display_font}.
    Body: clean grid showing X vs Y across 4 conditions.
  """,
  notes="<MANDATORY speaker notes — what you'll say>",
  code="<python-pptx snippet (render_mode='code') OR a code-shape author note>",
  render_mode="code" | "text" | "code-shape" | "paper-figure" | "ai-image" | "hybrid",
  figure_number=<N>,   # if render_mode == paper-figure
)
```

**Prompt template rule**: every prompt MUST start with the unity
header using placeholders. Example:

> `"{accent} accent. {display_font} typography. Minimal modern academic
> theme. Body: …"`

Never hardcode `"navy blue"` or `"Inter"` — write `{accent}` /
`{display_font}` so theme switching is a no-op rebuild.

### 5a. `code` slides — author the slide in python-pptx (todo 002)

A slide with `render_mode="code"` carries a python-pptx **snippet** in
its `code` field. The exporter `exec`s that snippet with a prepared
namespace, and the snippet adds shapes/textboxes/images to the slide
natively. Result: editable PPTX, visually-rich layout, your design
choices.

Why not just render the markdown `body`? Because markdown's grammar
is too thin to capture slide *design* — punchline placement, figure
position, "is this a list or a card grid", colored callouts, KPI
tiles. Trying to derive visual treatment from `>` quote vs `-` bullet
markers produces mediocre slides. You decide the design; code it.

**The namespace bound at exec time** (use these freely in `code`):

| Name | What it is |
|---|---|
| `slide` | The python-pptx `Slide` object you append shapes to |
| `title`, `body`, `notes`, `row` | The slide's stored fields (read-only inputs) |
| `palette` | `{"accent": RGBColor, "background": RGBColor, "foreground": RGBColor, "surface": RGBColor}` |
| `fonts` | `{"display": str|None, "body": str|None, "mono": str|None}` |
| `type_scale` | `{"title": 32, "head": 26, "body": 20, "line_spacing": 1.22, "cover_title": 40, "caption": 12, ...}` |
| `aspect` | `"16:9"` / `"16:10"` / `"4:3"` |
| `sw`, `sh` | Slide width / height in EMU (use with `Inches(...)` math) |
| `Pt`, `Inches`, `Emu` | python-pptx units |
| `MSO_SHAPE`, `PP_ALIGN`, `MSO_ANCHOR`, `RGBColor` | python-pptx primitives |
| `h` (alias `helpers`) | Helper namespace (see catalog below) |

**`h.*` helper catalog** — covers the boilerplate so the snippet can
focus on actual layout:

| Helper | Signature (sw/sh/palette/fonts/type_scale are kwargs) | Purpose |
|---|---|---|
| `h.accent_stripe(slide, *, palette, sw)` | — | Top accent stripe, deck signature |
| `h.title_block(slide, text, *, palette, fonts, type_scale, sw, sh, cover=False, accent_rule=True)` | — | Themed title + short accent rule (or centered cover layout if `cover=True`) |
| `h.bullet_list(slide, items, *, palette, fonts, type_scale, left, top, width, height, bullet="•")` | items=list[str] | Vertical bulleted list inside a box |
| `h.card(slide, *, left, top, width, height, title, body, palette, fonts, type_scale, accent_top=True)` | — | One titled card: bg + accent stripe + title + body |
| `h.card_grid(slide, items, *, left, top, width, height, palette, fonts, type_scale, cols=2, gap_pt=12)` | items=list[{title, body}] | N cards in a `cols`-column grid filling a box |
| `h.pull_quote(slide, text, *, palette, fonts, type_scale, left, top, width, height)` | — | Vertical accent bar + italic body — for a punchline |
| `h.image_path(path, *, left, top, width, height, fit="contain")` | — | Embed an image from a filesystem path |
| `h.image_region(region_id, *, left, top, width, height, fit="contain")` | — | Resolve `row.regions[id]` → embed that image |
| `h.image_figure(figure_number, *, left, top, width, height, fit="contain")` | — | Resolve a paper figure → embed |
| `h.grid(*, sw, sh, cols=12, rows=6, gutter=Pt(8), margin_x=Inches(0.6), margin_top=Inches(1.8), margin_bot=Inches(0.6), row_gap=Pt(8), row_h=None)` | — | Build a 12-col × 6-row design grid. Returns a `Grid` with `.cell(col, span, row, row_span)` → `(left, top, width, height)`. (todo 004 §D) |
| `h.SPACING_UNIT_PT` | constant `8` | 8pt vertical rhythm. Vertical gaps should be `Pt(SPACING_UNIT_PT * N)`. |

All Keynote-safe (RGBA → RGB JPEG ≤ 1920px normalization happens inside
the image helpers).

**Use the grid** — don't scatter ad-hoc `Inches(0.7)` constants. Once
the title's placed, `g = h.grid(sw=sw, sh=sh)` gives you a uniform 12-
column geometry that auto-aligns everything. The default leaves
Inches(1.8) at the top for `h.title_block` and Inches(0.6) margins on
the sides + bottom. Override only when a layout genuinely needs less
margin (a hero cover slide, for instance).

```python
g = h.grid(sw=sw, sh=sh)            # 12 cols × 6 rows by default
left, top, w_, h_ = g.cell(col=1, span=7, row=1, row_span=4)
h.bullet_list(slide, items, palette=palette, fonts=fonts,
              type_scale=type_scale,
              left=left, top=top, width=w_, height=h_)
left, top, w_, h_ = g.cell(col=8, span=5, row=1, row_span=4)
h.image_figure(1, left=left, top=top, width=w_, height=h_)
# Full-width footer band on the last row
left, top, w_, h_ = g.row(row=6)
h.pull_quote(slide, "Take-home line",
             palette=palette, fonts=fonts, type_scale=type_scale,
             left=left, top=top, width=w_, height=h_)
```

**Example 1 — title + 4-card grid + take-home quote**:

```python
mcp__co_scientist__add_slide(
  slug, deck_id, slide_number=N, role="discussion",
  title="The four harness primitives",
  body="Memory keeps decisions. Hooks fire on events. Slash commands "
       "are reusable. The context manager is the LLM's attention.",
  notes="Spend ~30 seconds on each primitive then land the take-home.",
  render_mode="code",
  code="""
h.accent_stripe(slide, palette=palette, sw=sw)
h.title_block(slide, title, palette=palette, fonts=fonts,
              type_scale=type_scale, sw=sw, sh=sh)
h.card_grid(slide, [
    {"title": "Memory",
     "body": "decisions and corrections stack across sessions"},
    {"title": "Hooks",
     "body": "auto-run on events (export validation, DOI check, …)"},
    {"title": "Slash commands",
     "body": "reusable workflows like /literature-review"},
    {"title": "Context manager",
     "body": "what the LLM is looking at right now"},
], left=Inches(0.7), top=Inches(1.9),
   width=sw - Inches(1.4), height=Inches(3.6),
   palette=palette, fonts=fonts, type_scale=type_scale, cols=2)
h.pull_quote(slide,
    "Each conversation builds the next version of the AI.",
    palette=palette, fonts=fonts, type_scale=type_scale,
    left=Inches(0.7), top=Inches(5.7),
    width=sw - Inches(1.4), height=Inches(1.0))
""",
)
```

**Example 2 — title + bullets on the left + figure on the right**:

```python
code="""
h.accent_stripe(slide, palette=palette, sw=sw)
h.title_block(slide, title, palette=palette, fonts=fonts,
              type_scale=type_scale, sw=sw, sh=sh)
h.bullet_list(slide, [
    "Two-week bespoke pipeline (before)",
    "30-second MCP query (after)",
    "Automatic provenance trail on every step",
], palette=palette, fonts=fonts, type_scale=type_scale,
   left=Inches(0.7), top=Inches(2.0),
   width=Inches(6.0), height=Inches(4.5))
h.image_figure(1, left=Inches(7.0), top=Inches(2.0),
               width=Inches(5.8), height=Inches(4.5))
"""
```

**Failure handling** — if the snippet raises, the exporter degrades
that slide to plain text (title + body) and records the error in
the export result's `code_errors[]`. The deck still exports. After
seeing an error, fix the snippet and re-export.

**Don't reinvent** — the `h.*` helpers cover ~90% of the layouts you'll
need. Drop to raw `slide.shapes.add_textbox(...)` only when no helper
fits. Keep snippets **declarative** (helper calls + a few coordinates),
not procedural (don't write loops that compute positions when
`card_grid(cols=N)` already does).

### 5b. Hybrid slides — bullets + figure, or several images (regions)

Two distinct uses of `set_slide_regions` / hybrid:

**(a) Title + bullets + one figure** — the most common mixed slide.
Put the bullets in `body` (markdown) on `add_slide`, then set ONE
image region for the figure on the right:

```
mcp__co_scientist__set_slide_regions(
  slug, deck_id, slide_id,
  regions=[
    { "render_mode": "ai-image",
      "prompt": "{accent} schematic of 2-week pipeline vs 30-sec MCP query",
      "x": 0.54, "y": 0.22, "w": 0.42, "h": 0.65,
      "fit": "contain" },
  ],
)
```

The slide's `body` renders as native bullets in the LEFT half; the
image region renders in its box on the right. The bullets stay
editable text in the .pptx; only the figure is an image.

**Keep the body tight on hybrid slides.** The body box is half-width,
so each bullet wraps onto more lines than on a full-width `text`
slide. As a rule, aim for ≤ 4 bullets, each ≤ 2 wrapped lines (i.e.
~80 Korean characters / 120 English characters). Dense bullets will
overflow the box even at the reduced 20pt body type.

**(b) Several images on one slide** — a generated schematic next to a
data plot next to a manuscript figure:

```
mcp__co_scientist__set_slide_regions(
  slug, deck_id, slide_id,
  regions=[
    { "render_mode": "paper-figure", "figure_number": 2,
      "x": 0.05, "y": 0.22, "w": 0.42, "h": 0.62, "fit": "contain",
      "caption": "Fig 2 — measured response" },
    { "render_mode": "ai-image", "prompt": "{accent} pathway schematic …",
      "x": 0.52, "y": 0.22, "w": 0.43, "h": 0.62, "fit": "contain",
      "caption": "Proposed mechanism" },
  ],
)
```

- This forces the slide to `render_mode="hybrid"`. Regions get ids
  `r1..rN` in order.
- `x/y/w/h` are **fractions of the slide** (0–1) — keep `y ≥ ~0.2` so
  regions clear the title. Useful layouts:
  - **2-up**: `r1` x=0.05 w=0.42, `r2` x=0.52 w=0.43 (both y=0.22 h=0.62)
  - **big-left + 2 stacked right**: `r1` x=0.05 y=0.22 w=0.55 h=0.62;
    `r2` x=0.64 y=0.22 w=0.31 h=0.29; `r3` x=0.64 y=0.55 w=0.31 h=0.29
  - **2×2**: four 0.42×0.34 boxes at x∈{0.05,0.52}, y∈{0.22,0.60}
- Each region has its own `render_mode` (`ai-image` / `code-shape` /
  `paper-figure`) and source. A region can't itself be `hybrid`/`text`.
- **`fit`** decides how the image fills its box:
  - `contain` (default) — letterbox, never crop. Use for figures,
    charts, tables, schematics — anything where cropping loses data.
  - `cover` — fill the box, crop the overflow. Use for an eyecatch /
    decorative / photo region where edge loss is fine.
- `render_region` records the rendered image's real pixel size
  (`image_width` / `image_height`) on the region — handy if you want
  to nudge a box to match the image's true aspect on a second pass.
- At export each region becomes a **separate, individually editable
  PPTX picture** — the user can nudge them in PowerPoint.

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
- `text`         → nothing to render; it becomes native PPTX text at
                   export. Returned in `skipped[]` with that reason.
- `paper-figure` → copies the existing figure blob into a slide image
- `ai-image`     → substitutes `{accent}` etc. from `deck.concept`,
                   calls `generate_image`
- `hybrid`       → renders every region it can (`paper-figure` /
                   `ai-image` regions); `code-shape` regions land in
                   `skipped[]` for you to do via `render_region`.
- `code-shape`   → returned in `skipped[]` because the MCP can't safely
                   exec arbitrary Python. Run the slide's `code` block
                   yourself locally (matplotlib/seaborn/etc. into a
                   PNG), then pass that path back:

```
mcp__co_scientist__render_slide(
  slug, deck_id, slide_id,
  local_path="/abs/path/to/slide-3.png",
)
```

For a **hybrid** slide's `code-shape` region, render that one region:

```
mcp__co_scientist__render_region(
  slug, deck_id, slide_id, region_id,   # e.g. region_id="r2"
  local_path="/abs/path/to/region.png",
)
```

`paper-figure` / `ai-image` regions need no `local_path` — the MCP
renders them (an ai-image region's aspect ratio is matched to its
box). A hybrid slide is "done" when every region has an image.

Once every non-`text` slide has an `image_blob_path`, the deck's
`status` flips to `"rendered"`. To export from Claude Code:

```
mcp__co_scientist__export_deck_to_pptx(
  slug, deck_id,
  output_path="~/decks/my-talk.pptx",
)
```

Export behavior:
- **Image slides** embed the rendered PNG, aspect-fitted and centered.
- **`hybrid` slides** get a themed title frame plus each region placed
  as its own separately-editable PPTX picture at its `x/y/w/h` box,
  with an optional caption.
- **`text` slides** (and any slide still missing a render) become
  NATIVE editable text — title + bullets — themed from the concept's
  `accent` / `bg` / `text` colors. Not a picture: the user can edit
  the words in PowerPoint.
- Page size follows the deck's `aspect_ratio`.
- A sibling **`.pdf`** is produced when LibreOffice (`soffice`) is
  installed — the portable fallback, since Keynote sometimes rejects
  python-pptx's PPTX.

Returns `{ local_path, blob_path, pdf_local_path, pdf_blob_path,
pdf_skipped, aspect_ratio, slide_count, image_slides, text_slides,
hybrid_slides, missing_renders }`. `missing_renders[]` is the non-text slides that
came out as text fallbacks because they weren't rendered yet — render
those and re-export. If `pdf_skipped` is true, tell the user to
install LibreOffice if they want the PDF.

python-pptx ships with the base install. LibreOffice is the only
optional extra (PDF sibling only).

## Addressing slide comments

Reviewers leave comments on individual slides from the dashboard's
Presentations tab — the deck analogue of manuscript review comments.

- `list_deck_comments(slug, deck_id)` — open slide comments, each tagged
  with `slide_number` / `slide_id` / `slide_title` (and an optional
  `region_id` pointing at one region of a hybrid slide). This is the
  deck's revision to-do list; check it at session start.
- For each comment: read it, revise that slide (`update_slide` /
  `set_slide_regions`), re-render if needed, then
  `resolve_deck_comment(slug, deck_id, slide_id, comment_id)` —
  `status="resolved"` if addressed, `"rejected"` if you and the user
  decide not to act on it.
- Re-export the deck once the slides are revised.
