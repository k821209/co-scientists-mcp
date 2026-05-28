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
      muted: #6c757d  secondary: #2e7d32  highlight: #ee5500
    Typography:
      # English-only audience: Inter is fine. For ANY deck whose audience
      # is Korean / Japanese / Chinese (or whose body text mixes scripts),
      # use the matching Noto Sans CJK family — its Latin glyphs are co-
      # designed to share metrics with the CJK script. Pretendard's Latin
      # is taller / heavier than its Hangul and creates a visible seam in
      # mixed-script body text (todo 008 §B).
      #   Korean   audience: display: Noto Sans KR  body: Noto Sans KR
      #   Japanese audience: display: Noto Sans JP  body: Noto Sans JP
      #   Chinese  audience: display: Noto Sans SC  body: Noto Sans SC
      display: Inter Bold     body: Inter Regular     mono: JetBrains Mono
    Type scale:
      # legacy keys (still honored)
      title: 32  head: 26  body: 20  line_spacing: 1.22
      hybrid_body: 18  hybrid_head: 22  cover_title: 40  caption: 12
      # semantic role keys (canonical — prefer these in new code; todo 004 §E)
      display_chapter: 56  display_cover: 48  display_hero: 44
      headline_section: 28  title_slide: 32
      body_large: 22  body_standard: 20  body_small: 16
      label_tag: 12  label_caption: 12  scale_ratio: 1.25
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

**Mixed-script typography** (todo 008 §B). When the deck's body text
mixes Latin and CJK in the same paragraph (typical for Korean academic
talks that use English jargon like "BLUP", "GWAS", "MCP"), the
**Latin glyphs need to share metrics with the CJK script** or the two
read as collaged from different fonts. Google's **Noto Sans** pan-CJK
families do this by design — Noto Sans KR / JP / SC ship Latin
glyphs co-designed with the matching Hangul / Kana / Hanzi. Pretendard
and Inter look great in isolation but their Latin glyphs are taller
and heavier than the Hangul they sit next to, so "MCP가 다리" reads
with a visible seam between "MCP" and "가". The default for any non-
English audience should be the matching Noto Sans family.

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

**Don't commit to render_mode here (todo 010).** Outline is the
*content-brief* step — each slide gets `role + title + body intent +
speaker notes`. The design decision (will this be a code snippet?
a full-bleed figure? a 2-column compare? a Gantt?) is made in **§5
per slide**, when you've actually thought about the slide's content
and decided what layout serves it. `render_mode` defaults to None at
this stage; the exporter / renderer infers it from whichever fields
end up populated in §5 (regions → hybrid, code with python-pptx
signals → code, figure_number → paper-figure, prompt → ai-image,
otherwise → text). Pass an explicit `render_mode` only when you want
to lock the strategy at outline time (rare).

### 5. Design + author each slide

> **Content slides are BESPOKE by default — target ≥ 25 shapes per
> slide, composed from `h.*` primitives.** Patterns (`p.*`) are
> narrow shortcuts for *exact-fit* cases only (a 3-step workflow with
> nothing else on the slide; a single chapter divider). When the
> content has any of the §5a "Go bespoke when…" signals — proposal-
> grade density, multi-section structure, two compositions side-by-
> side, etc. — **do NOT call a single pattern**. Compose directly
> from `h.text` + `slide.shapes.add_shape` + `h.deck_chrome` like
> `reference_corpus/proposal_dense.png` and `personnel_equipment.png`.
> Pattern-fits-everything is the toy-density failure mode (todo 011).

Now you go slide-by-slide. For each slide:

1. **Read the brief** (role + title + body intent + notes from §4).
2. **Decide the design** based on the content. Default to bespoke
   composition; only fall back to a single pattern when the content
   is a clean exact-fit case (see §5a's "Use only when…" criteria).
   `reference_corpus/proposal_dense.png` and `personnel_equipment.png`
   are the canonical density references — Read them before authoring
   any non-trivial content slide.
   (`chapter_divider` / `metric_tile_row` / `flow_pipeline` /
   `figure_full` / `gantt_chart` / …). If no pattern fits, **go
   bespoke** — compose with `h.text` / `h.card` / `h.icon` /
   `h.table` / `slide.shapes.add_shape` (§5a's "patterns are a
   starting point, not a ceiling" rule).
3. **Author the slide** by setting the field(s) that fit your design.
   The render_mode is **inferred** from which fields you populate —
   don't pass `render_mode` unless you want to lock it explicitly.

| What you authored                              | Mode inferred at export |
| ---------------------------------------------- | ----------------------- |
| `code` with `h.*` / `p.*` / `slide.shapes` etc. | `code`                  |
| `figure_number`                                | `paper-figure`          |
| `prompt` (no image yet)                        | `ai-image`              |
| `regions[]` (via `set_slide_regions`)          | `hybrid`                |
| `code` looking like an external PNG script     | `code-shape`            |
| Just `title + body`                            | `text`                  |

So the simplest add+design loop is:

```python
# Step 4 produced the brief; Step 5 designs + authors:
mcp__co_scientist__update_slide(
  slug, deck_id, slide_id=...,
  code="""
    h.accent_stripe(slide, palette=palette, sw=sw)
    h.title_block(slide, title, palette=palette, fonts=fonts,
                  type_scale=type_scale, sw=sw, sh=sh)
    h.deck_chrome(slide, palette=palette, fonts=fonts,
                  type_scale=type_scale, sw=sw, sh=sh,
                  eyebrow='HOW · 추진 방법', page_number=5, total=13,
                  footer='기러기류 마커 발굴 · ㈜디보')
    p.flow_pipeline(slide, items=[...],
                    palette=palette, fonts=fonts,
                    type_scale=type_scale, sw=sw, sh=sh)
  """,
)
# render_mode auto-inferred to "code" — no commitment made at outline time.
```

`add_slide` itself stays simple:

```
mcp__co_scientist__add_slide(
  slug, deck_id,
  slide_number=N,
  role="<role>",
  title="<slide title>",
  body="<content-brief lines — what the slide should say>",
  notes="<MANDATORY speaker notes — what you'll say>",
  # render_mode / code / prompt / figure_number all OPTIONAL —
  # populate via update_slide once you've decided the design (§5).
)
```

**Prompt template rule**: when you do set `prompt` (for ai-image), it
MUST start with the unity header using placeholders. Example:

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

**Quick reference — every callable at a glance** (todo 007 Tier 3).
Grep this block to find the right helper / pattern without reading
source. All signatures are *current* — legacy parameter names noted
where they still work.

```text
NAMESPACE (always bound in code snippets)
  slide, title, body, notes, row
  palette = {accent, background, foreground, surface, muted,
             secondary, highlight}    # 7 RGBColor keys, todo 007
  fonts   = {display, body, mono}
  type_scale = {legacy: title/head/body/cover_title/caption/...
                 canonical roles: display_chapter/cover/hero,
                                  headline_section, title_slide,
                                  body_large/standard/small,
                                  label_tag/caption, scale_ratio}
  aspect, sw, sh, Pt, Inches, Emu, MSO_SHAPE, PP_ALIGN, MSO_ANCHOR,
  RGBColor

HELPERS  (h.* — primitives)
  h.accent_stripe(slide, *, palette, sw)                 # top stripe
  h.title_block(slide, text, *, palette, fonts,           # themed title
                type_scale, sw, sh, cover=False,
                accent_rule=True)
  h.bullet_list(slide, items, *, palette, fonts,          # bulleted column
                type_scale, left, top, width, height,
                bullet="•")
  h.card(slide, *, left, top, width, height, title, body, # single card
         palette, fonts, type_scale, accent_top=True)
  h.card_grid(slide, items, *, left, top, width, height,  # N-card grid
              palette, fonts, type_scale, cols=2, gap_pt=12)
            # items: list[{title|tag, body|note}]
  h.pull_quote(slide, text, *, palette, fonts, type_scale, # accent bar + italic
               left, top, width, height)
  h.text(slide, content, *, left, top, width, height,    # one-call textbox
         palette, size_pt=20, color=None, bold=False,
         italic=False, align=None, anchor=None,
         line_spacing=1.22, autofit=True, min_pt=10,
         fonts=None)                                      # todo 007 §D
  h.icon(slide, name, *, left, top, size, palette,        # MSO_SHAPE or glyph
         color=None, fonts=None)
  h.icon_names() -> list[str]                             # vocabulary
  h.deck_chrome(slide, *, palette, fonts, type_scale,     # eyebrow + footer
                sw, sh, eyebrow="", page_number=None,     # + page number
                total=None, footer="")                    # (todo 009 B)
  h.table(slide, *, headers, rows, left, top, width,      # native pptx TABLE
          height, palette, fonts, type_scale,             # (todo 009 C)
          first_col_emphasis=False)
  h.image_path([slide,] path, *, left, top, width,        # embed local PNG
               height, fit="contain")
  h.image_region([slide,] region_id, *, left, top, width, # row.regions[id]
                 height, fit="contain")
  h.image_figure([slide,] figure_number, *, left, top,    # paper figure
                 width, height, fit="contain")
  h.grid(*, sw, sh, cols=12, rows=6, ...) -> Grid         # design grid
       grid.cell(col, span=1, row=1, row_span=1) -> Cell  # (left,top,w,h)
                                                           # OR .left/.top/...
  h.SPACING_UNIT_PT = 8                                   # 8pt rhythm
  h.autofit_pt(text, *, max_width_emu, max_height_emu,    # Korean-aware
               start_pt, line_spacing=1.22, min_pt=10)
  h.estimate_text_width_pt(text, font_pt)

STRUCTURAL PATTERNS  (p.* — content shape, PowerPoint master layouts)
  p.title_slide(slide, *, title, subtitle="", eyebrow="", # OWNS SLIDE
                palette, fonts, type_scale, sw, sh)
  p.title_and_body(slide, *, title, body, lead="",        # under title
                   palette, fonts, type_scale, sw, sh)
  p.title_two_content(slide, *, title, left, right,       # under title
                      palette, fonts, type_scale, sw, sh)
  p.title_and_image_grid(slide, *, title, images, cols=2, # under title
                         palette, fonts, type_scale, sw, sh)
  p.figure_full(slide, *, image_path=None,                # under title
                image_callable=None, caption="",
                palette, fonts, type_scale, sw, sh)
                       # Pass ONE of image_path / image_callable.
                       # Full-grid figure + caption in bottom margin.

INTENT PATTERNS  (p.* — design treatment)
  p.chapter_divider(slide, *, chapter_label, summary="",  # OWNS SLIDE
                    palette, fonts, type_scale, sw, sh)
  p.hero_with_trailing_evidence(slide, *, headline,       # under title
      items=..., palette, fonts, type_scale, sw, sh)
                       # items: list[str | {body}]
                       # legacy alias: evidence=
  p.metric_tile_row(slide, *, items=..., palette, fonts,  # under title
      type_scale, sw, sh, top=None, height=None)
                       # items: list[tuple | {value/tag, label/body, unit?}]
                       # legacy alias: tiles=
  p.evidence_stack(slide, *, claim, items=..., palette,   # under title
      fonts, type_scale, sw, sh)
                       # items: list[{tag, body}]
                       # legacy alias: evidence=
  p.flow_pipeline(slide, *, items=..., palette, fonts,    # under title
      type_scale, sw, sh)
                       # items: list[{tag, body}]
                       # legacy alias: steps=
  p.before_after_split(slide, *, before, after,           # under title
      transition_label="", palette, fonts, type_scale,
      sw, sh)
                       # before / after: {title, body}
  p.contrast_pair(slide, *, left_item, right_item,        # under title
      axis_label="", palette, fonts, type_scale, sw, sh)
                       # *_item: {title, pros: list[str], cons: list[str]}
  p.quadrant_map(slide, *, items, axes,                   # under title
      palette, fonts, type_scale, sw, sh)
                       # items: list[{label, x, y}]
                       # axes:  {x, y, x_low?, x_high?}
  p.numbered_milestone_arc(slide, *, items=..., palette,  # under title
      fonts, type_scale, sw, sh)
                       # items: list[{tag, body | note}]
                       # legacy alias: milestones=
  p.zoom_in_callout(slide, *, context_image_path,         # under title
      callout, note="", palette, fonts, type_scale,
      sw, sh)
                       # callout: {x, y, w, h}, all in [0,1]
  p.gantt_chart(slide, *, items=..., periods=None,        # under title
                period_count=None, palette, fonts,         # todo 009 D
                type_scale, sw, sh)
                       # items: list[{label, start, span}]
                       # legacy alias: activities=
```

Contract rules:
- **owns slide** patterns: do NOT call `h.accent_stripe` / `h.title_
  block` before — the pattern is the slide.
- **under title** patterns: DO call the preamble first; pattern
  content starts at `_BODY_TOP` ≈ Inches(1.85).
- Every text-emitting helper autofits Korean-aware (`h.autofit_pt`)
  so dense body content can't overflow its box (todo 005 + autofit
  follow-up).
- Every list-of-items parameter is canonically `items=`. Legacy
  names (`evidence` / `tiles` / `steps` / `milestones`) still work
  as aliases. Passing both raises `TypeError`.
- Image helpers (`h.image_*`) accept slide as the first positional
  arg OR rely on the closure-bound `slide`. Both forms work.

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
| `h.image_path([slide,] path, *, left, top, width, height, fit="contain")` | slide optional | Embed an image from a filesystem path. `slide` is optional (falls back to the snippet's bound slide); pass it explicitly for consistency with other helpers. |
| `h.image_region([slide,] region_id, *, left, top, width, height, fit="contain")` | slide optional | Resolve `row.regions[id]` → embed that image. |
| `h.image_figure([slide,] figure_number, *, left, top, width, height, fit="contain")` | slide optional | Resolve a paper figure → embed. |
| `h.text(slide, content, *, left, top, width, height, palette, size_pt=20, color=None, font_name=None, bold=False, italic=False, align=None, anchor=None, line_spacing=1.22, autofit=True, min_pt=10, fonts=None)` | one-call textbox | DX helper: drops the 5-line `add_textbox + text_frame + paragraph + run + font` ceremony to a single call. `color` defaults to `palette["foreground"]`; pass `palette["muted"]` for captions, `palette["accent"]` for emphasis. Autofit-shrinks Korean-aware. (todo 007 §D) |
| `h.grid(*, sw, sh, cols=12, rows=6, gutter=Pt(8), margin_x=Inches(0.6), margin_top=Inches(1.8), margin_bot=Inches(0.6), row_gap=Pt(8), row_h=None)` | — | Build a 12-col × 6-row design grid. Returns a `Grid` with `.cell(col, span, row, row_span)` → `(left, top, width, height)`. (todo 004 §D) |
| `h.SPACING_UNIT_PT` | constant `8` | 8pt vertical rhythm. Vertical gaps should be `Pt(SPACING_UNIT_PT * N)`. |
| `h.icon(slide, name, *, left, top, size, palette, color=None, fonts=None)` | name = semantic key | Place a named icon at `(left, top)` with `size×size` bounding box. Native MSO_SHAPE auto-shape when available (`arrow-right`, `lightning`, `database`, `warning`, `decision`, `molecule`, `sun`, `moon`, `gear`, `star`, `heart`, `cloud`, `document`, `brace-*`, …) — recolorable + scalable + editable in PowerPoint. Unicode-glyph fallback for `check`, `x`, `info`, `dna`, `microscope`, `flask`, `chart`, `lock`, etc. Color defaults to `palette["accent"]`. (todo 004 §C) |
| `h.icon_names()` | — | Sorted list of every icon name `h.icon()` accepts. Call at runtime when the agent needs to pick one. |
| `h.autofit_pt(text, *, max_width_emu, max_height_emu, start_pt, line_spacing=1.22, min_pt=10)` | Korean-aware | Largest pt in `[min_pt, start_pt]` at which `text` fits inside an EMU-sized box. Used internally by `_emit_text` / `bullet_list` / `_render_simple_body` so every text region auto-shrinks pre-export (soffice doesn't fully honor PowerPoint's TEXT_TO_SHAPE autoshrink — without this, dense Korean text overflowed into adjacent boxes). Call directly if you build a custom textbox. |
| `h.estimate_text_width_pt(text, font_pt)` | — | Rough pt-width estimate, summed per-char (Korean / CJK ≈ 1.0 × font_pt, ASCII alnum ≈ 0.55, space ≈ 0.3). |

All Keynote-safe (RGBA → RGB JPEG ≤ 1920px normalization happens inside
the image helpers).

**Use the grid** — don't scatter ad-hoc `Inches(0.7)` constants. Once
the title's placed, `g = h.grid(sw=sw, sh=sh)` gives you a uniform 12-
column geometry that auto-aligns everything. The default leaves
Inches(1.8) at the top for `h.title_block` and Inches(0.6) margins on
the sides + bottom. Override only when a layout genuinely needs less
margin (a hero cover slide, for instance).

`g.cell(col=, span=, row=, row_span=)` returns a **Cell** namedtuple —
unpack as `(left, top, w, h)` OR address as `cell.left / cell.top /
cell.width / cell.height` (todo 007 axis 3).

**Palette has 7 keys** (todo 007 axis 4) — `accent`, `background`,
`foreground`, `surface`, `muted`, `secondary`, `highlight`. The
concept's `Palette:` block can declare any of them; missing keys get
computed (muted = 45/55 blend of fg+bg; secondary = accent shifted
toward black; highlight = accent shifted toward white). Use
`palette["muted"]` for captions instead of hardcoding hex literals.

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

## ⚠️  Bespoke is the default — go bespoke when… (todo 011)

> Most content slides are NOT a single-pattern fit. Default to
> bespoke composition with `h.*` primitives + `slide.shapes.add_shape`.
> The pattern catalog comes AFTER this section as narrow shortcuts.

**Trigger table** — any of these signals in the slide brief means
**do NOT call a pattern**; compose directly:

| Signal in content brief | Why no pattern fits |
|---|---|
| 3+ structured comparison sections (e.g. "3 platforms × {mode, spec, tag}") | `card_grid` tops out at title+body; can't hold mode/spec/tag layered per card |
| Personnel page (N people × {role, percentage, expertise}) | Need 3-field row × N — no pattern; compose with rectangles + h.text |
| Equipment list with sections (sequencing / HPC / storage / …) | Multi-section nested-bullet structure; patterns are flat |
| Gantt or roadmap with parallel workstreams | Use `p.gantt_chart` BUT pair with chrome + extra annotation rows hand-added |
| Slide carries TWO independent dense compositions side-by-side (e.g. personnel + equipment) | Patterns assume ONE composition per slide |
| KPI tiles + supporting figure on the same slide | `p.metric_tile_row` doesn't take a figure; compose tiles + figure side-by-side |
| Architecture / system diagram with custom topology | No pattern covers arbitrary node-edge structures |

**Worked examples — Read these before authoring**:
- `reference_corpus/proposal_dense.png` (~50 shapes; source in
  `reference_corpus/generate.py` under `"proposal_dense"`)
- `reference_corpus/personnel_equipment.png` (~60 shapes; source ditto)

The canonical density vocabulary lives in those two snippets. Mirror
the structure; adapt the content. **Chrome (`h.deck_chrome`) is part
of every content slide** — never skip it.

If the brief has none of the trigger signals AND fits one of the
patterns below cleanly, you can use a single pattern call. But check
the pattern's "Use ONLY when…" line — most are tighter than they
look.

## Pattern shortcuts — narrow use only

> Each pattern below now lists an explicit "Use ONLY when…" condition.
> The condition is tight on purpose. When in doubt: bespoke.

**`p.*` whole-slide pattern catalog** (todo 004 §B + 005) — these are
*designed compositions*, not primitives. Each pattern bundles a
designer's compositional decisions (grid placement, type hierarchy,
whitespace ratios, color use, visual storytelling devices). Pick a
pattern that fits the slide's *intent*; don't reinvent the layout
with raw helpers.

**Contract: every pattern is one of two kinds.** Get this wrong and
the pattern collides with your `h.title_block` (or vice versa).
Patterns marked **under title** assume you've already called
`h.accent_stripe(slide, ...)` + `h.title_block(slide, ...)`; they
draw their content starting at `y ≈ 1.85"`. The one **owns slide**
pattern (`chapter_divider`) replaces the entire chrome — don't call
the preamble before it.

| Pattern | Contract | Intent / when to use | Content shape |
|---|---|---|---|
| `p.chapter_divider(slide, *, chapter_label, summary="")` | **owns slide** | Section opener (Era I/II/III). Big centered label + accent rule + summary. | `chapter_label` (≤ 12 chars), `summary` (≤ 50 chars) |
| `p.hero_with_trailing_evidence(slide, *, headline, evidence)` | under title | Thesis / takeaway. Big headline on the left + numbered evidence column on the right. | `headline` (≤ 60 chars), `evidence` (2–4 items, ≤ 80 chars) |
| `p.metric_tile_row(slide, *, tiles)` | under title | KPI / quantitative summary. Big numbers in a row. | `tiles: 3–5 of (value, label)` or `(value, label, unit)` |
| `p.evidence_stack(slide, *, claim, evidence)` | under title | A claim backed by 2-4 stacked tag-pill rows. | `claim` (≤ 80 chars), `evidence` (2–4 items, `{tag, body}`) |
| `p.flow_pipeline(slide, *, steps)` | under title | Process / workflow. Numbered cards with right-arrows between. | `steps: 3–5 of {tag, body}` |
| `p.before_after_split(slide, *, before, after, transition_label="")` | under title | Risk vs mitigation, old vs new. Muted left + accent right + arrow. | `before / after: {title, body}`, `transition_label` (≤ 16 chars) |
| `p.contrast_pair(slide, *, left_item, right_item, axis_label="")` | under title | Two competing options framed by an axis. Mirrored panels with pros/cons. | `*_item: {title, pros, cons}`, `axis_label` (≤ 40 chars) |
| `p.quadrant_map(slide, *, items, axes)` | under title | Comparative landscape. Items at (x, y) ∈ [0,1]² on labeled axes. | `items: [{label, x, y}]`, `axes: {x, y, x_low?, x_high?}` |
| `p.numbered_milestone_arc(slide, *, milestones)` | under title | Progressive timeline. Equal slots; tag + note **below** the line; weight saturates left→right. | `milestones: 3–6 of {tag, note}` |
| `p.zoom_in_callout(slide, *, context_image_path, callout, note="")` | under title | Focus on a region of a complex figure. Context + outlined ROI + zoomed inset. | `context_image_path` (real path), `callout: {x, y, w, h}` ∈ [0,1] |

All under-title patterns take the same theme kwargs (`palette`,
`fonts`, `type_scale`, `sw`, `sh`) as `h.*` helpers; `chapter_divider`
likewise.

**Structural patterns** (todo 006) — pick these *first* by content
shape (the PowerPoint master-layout taxonomy), then optionally swap to
an intent pattern above if a more loaded design fits:

| Pattern | Contract | PowerPoint base | Use for |
|---|---|---|---|
| `p.title_slide(slide, *, title, subtitle="", eyebrow="")` | **owns slide** | (1) Title Slide | Deck opener / cover at slide 1. Centered eyebrow + title + accent rule + subtitle. Distinct from `chapter_divider` (mid-deck). |
| `p.title_and_body(slide, *, title, body, lead="")` | under title | (2) Title and Content (plain) | The most common slide: title + bulleted body. Body sits in a 60% left column with 40% intentional whitespace on the right (focus discipline). Optional `lead` sentence in display type. |
| `p.title_two_content(slide, *, title, left, right)` | under title | (4) Two Content | Generic 2-column body, each `{heading?, body?, bullets?}`. Mirrored — for emphasized comparison use `before_after_split`; for pros/cons use `contrast_pair`. |
| `p.title_and_image_grid(slide, *, title, images, cols=2)` | under title | (4) Two Content extended / (9) Picture with Caption | N images in a `cols`-column grid (1 = half-bleed, 2 = side-by-side, 4 = 2×2). Optional per-image captions. |
| `p.figure_full(slide, *, image_path=None, image_callable=None, caption="")` | under title | (9) Picture with Caption (figure-only) | Single figure that owns the FULL grid (~85% slide height); caption rides in the bottom-margin strip outside the grid. ~17% more figure area vs `row_span=4` + caption-in-row-6 layouts. Pass `image_path` for filesystem PNGs or `image_callable=lambda **kw: h.image_figure(slide, N, **kw)` for paper figures. (todo 008 §A) |
| `p.gantt_chart(slide, *, items, periods=None, period_count=None)` | under title | Timeline matrix | Activity rows × period columns with accent-colored bars at each row's `{start, span}`. Zebra-striped rows + period labels + left-aligned activity labels. Pair with `h.deck_chrome` for proposal rhythm. items: `[{label, start, span}]` (1-indexed). (todo 009 D) |

**Two-step selection** (todo 006 — the 2D matrix):

1. **Structural type first** — pick by content *shape*. What do you
   have to put on this slide?
   - Just a centered title → `p.title_slide` (slide 1) or
     `p.chapter_divider` (mid-deck) or `h.title_block` alone.
   - Title + a list / paragraphs → `p.title_and_body`.
   - Title + 2 paired panels → `p.title_two_content` (generic) or
     `p.contrast_pair` (pros/cons) or `p.before_after_split` (old/new).
   - Title + a single figure → `h.image_figure` (full-bleed) or
     `p.zoom_in_callout` (with ROI).
   - Title + multiple images → `p.title_and_image_grid`.
2. **Intent treatment second** — if a more loaded design fits the
   *message*, swap to one of the intent patterns
   (`hero_with_trailing_evidence`, `metric_tile_row`, `evidence_stack`,
   `flow_pipeline`, `quadrant_map`, `numbered_milestone_arc`).

**Pattern selection — role → recommended pattern**:

| Role | First-pick pattern | Backup |
|---|---|---|
| `title` (deck opener) | `title_slide` | `chapter_divider` (mid-deck) |
| `outline` | `flow_pipeline` (steps) | `numbered_milestone_arc` |
| `background` | `evidence_stack` (claim + 2-3 facts) | `metric_tile_row` |
| `question` | `hero_with_trailing_evidence` (single line + supporting evidence) | `chapter_divider` |
| `method` | `flow_pipeline` (most natural) | `before_after_split` |
| `result` | `metric_tile_row` or `evidence_stack` | `zoom_in_callout` (focus on a figure region) |
| `discussion` | `contrast_pair` or `before_after_split` | `quadrant_map` |
| `conclusion` | `hero_with_trailing_evidence` (one big take-home + 3 supporting) | `metric_tile_row` |
| `qa` | `text` mode (acknowledgments) | — |

Pick a different pattern per consecutive slides — visual rhythm
across the deck matters as much as quality of any single slide.

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

**Patterns are a starting point, not a ceiling.** (todo 009.) The 14
patterns above cover the *common* shapes of a slide; they don't cover
proposal pages, Gantt charts, personnel tables, or any other layout
where the content asks for 30+ shapes hand-composed. Real decks
(e.g., a 13-page funded-grant proposal) have **30–70 shapes per
content slide**. Our toy patterns produce ~10–15. The gap is the
agent's compose budget per slide, not python-pptx's capability.

So:
- **Default to bespoke** — see the "Go bespoke when…" trigger table
  near the top of §5a (right before the pattern catalog).
- **Use a pattern only when the content is an exact fit** — each
  pattern's "Use ONLY when…" line in the catalog is intentionally
  tight. If your brief overflows that condition, you're in bespoke
  territory.
- **Density signals you're on the right track.** When a content slide
  ends up at ~25–60 shapes, that's *good* — every inch carries info.
  The bad case is 60 shapes with no hierarchy; not 60 shapes by
  themselves.
- **Chrome is part of every content slide.** `h.deck_chrome(eyebrow,
  footer, page_number, total)` after `h.title_block`. Pair the
  eyebrow with the slide's role (`role="method"` → `eyebrow="HOW ·
  …"`, `role="result"` → `eyebrow="WHAT · …"`).

**Image placeholder workflow for code slides.** When a `code` slide
needs images (a paper figure, an AI-generated diagram, a code-shape
PNG), **declare them as regions[] up front** instead of hardcoding
paths. The agent's workflow:

1. `add_slide(..., render_mode="code", code="""…h.image_region('r1', left=…, top=…, width=…, height=…)…""")`
2. `set_slide_regions(slug, deck_id, slide_id, regions=[{"render_mode": "ai-image", "prompt": "…", "x": 0.54, "y": 0.30, "w": 0.42, "h": 0.55}, …])`
3. `render_deck(slug, deck_id)` — `render_mode="code"` slides with regions are now rendered the same way as hybrid (each region's image is materialized).
4. `export_deck_to_pptx(slug, deck_id)` — the snippet's `h.image_region(id, …)` call resolves to the rendered blob and embeds it.

This separates **layout decision** (in the code) from **image
generation** (in regions[]). Theme / palette changes don't trigger
re-generation; re-positioning a region doesn't either. Set
`render_mode="code"` BEFORE calling `set_slide_regions` to keep the
mode (otherwise it snaps to `hybrid` for backwards compatibility).

**Box overlap won't happen** — every text emitter in `h.*` and every
`_emit_text` inside `p.*` calls `h.autofit_pt` to shrink the font
before rendering when content would overflow. PowerPoint's
TEXT_TO_SHAPE autoshrink kicks in on top of this; soffice (our
preview pipeline) doesn't fully honor that, so the autofit ensures
the PNG matches the slide. The minimum fall-back is ~12pt for body,
~16pt for headings — if you see autofit hitting min, the right fix
is to **drop content**, not to expand the box.

### 5c. Compositional effects — why arrangement matters (todo 006)

Same content lands differently depending on arrangement. The patterns
encode these rules; when you build a custom layout, mirror them.

**Left vs right placement.** Western reading is L→R; the right side is
where the audience arrives — the natural "this is the conclusion"
position. Place the **subject** on the right when it's the destination;
on the left when it's the starting fact.
- `p.before_after_split` deliberately puts BEFORE on the left
  (history) and AFTER on the right (where you arrive).

**Image emphasis — full-bleed vs caption strip.**
- Full-bleed image, no caption = "the image **IS** the message". Use
  when the image self-explains and you want emotional weight.
- Image + caption strip = "the image is supporting **evidence**".
  Caption stays in body type, never display.

**Multi-image arrangement — grid vs row.**
- 2×2 grid = COMPARISON (items are peers; no order).
- 3- or 4-image single row = PROGRESSION (left→right reads as sequence).
- 1 hero + N small supporting = FOCUS + context.

**Title position — hierarchy.**
- Title at top (default): content-first. The audience reads the title
  briefly and dwells on the body. Most slides.
- Title centered, no body (`title_slide` / `chapter_divider`): the
  title **is** the content. Use for openers and section breaks.

**Whitespace as design.**
- Filled body box = density. Defensible for dense reference data.
- 60% column with 40% whitespace = focus. Use for theses, hero
  statements, KPI tiles. `p.title_and_body` does this by default.

**The 4-color / 4-type-size discipline** (from the deck concept's
`Design language` block, todo 004 §G). Per slide:
- ≤ 3 colors (accent + foreground + one neutral).
- ≤ 4 distinct type sizes (read from `type_scale`, never ad-hoc).

When you author a layout that breaks one of these, ask whether the
break earns its keep — and if not, fall back to the rule.

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

### 5d. Reference corpus — what good renderings look like (todo 004 §F)

The skill ships with a curated corpus of exemplar slides at
`reference_corpus/` (one PNG per canonical pattern + `manifest.json`).
Each entry records the pattern name, the content the example uses, and
a do / don't pair the agent should mirror in its own slides.

**Recommended flow when authoring a `code` slide**:

1. Decide the structural type + intent treatment (§5a quick-ref table).
2. Read `packages/skills/paper-deck/reference_corpus/manifest.json` to
   confirm the canonical example exists for your chosen pattern.
3. Read the matching PNG (`Read("packages/skills/paper-deck/reference_corpus/<pattern>.png")`)
   — Claude is multimodal, so the agent SEES what a good rendering of
   that pattern looks like before authoring its own.
4. Follow the manifest entry's **do**; avoid its **dont**.
5. Author the `code` snippet against your own content. Run the
   critique loop (§9) against the result and the reference side-by-
   side; rewrite if your rendering diverges visually from the
   exemplar's discipline.

The corpus currently covers 10 patterns: `title_slide`,
`chapter_divider`, `title_and_body`, `title_two_content`,
`title_and_image_grid`, `hero_with_trailing_evidence`,
`metric_tile_row`, `evidence_stack`, `flow_pipeline`, and
`before_after_split`. Regenerate with:

```bash
PYTHONPATH=apps/local-mcp python \
  packages/skills/paper-deck/reference_corpus/generate.py
```

The corpus is checked in (small PNGs), so the agent has it locally
without a network round-trip. Each PNG is < 100 KB.

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

### 9. Critique pass — vision review of the exported deck (todo 004 §A)

After `export_deck_to_pptx` the result includes a `slide_pngs[]` list:
one PNG per slide rendered from the sibling PDF (so what the agent
sees is exactly what an opener of the .pptx / .pdf will see). Use them
to **score and rewrite weak slides** before declaring the deck done.

```
res = mcp__co_scientist__export_deck_to_pptx(slug, deck_id)
for png in res["slide_pngs"]:
    # Read the PNG via the Read tool — Claude is multimodal and will
    # see the actual slide rendering.
    Read(png["local_path"])
    # Score it (in your head / scratchpad) against the rubric.
    # If any category < 4, rewrite the slide's `code` and update_slide.
```

**Rubric** (each scored 1–5; a slide passes when all ≥ 4):

| Category | Question |
|---|---|
| Visual hierarchy | Is the focal point obvious within 1 second? |
| Whitespace | Does the slide breathe, or is it crowded? |
| Alignment | Are elements on an implicit grid? (no rogue offsets) |
| Typographic discipline | Type hierarchy clear; ≤ 4 sizes; consistent? |
| Color discipline | ≤ 3 colors, used semantically? |
| Visual storytelling | Is there a story device (contrast, progression, arrow), or is it a static composition? |
| **Density** (todo 011) | If this is a *content* slide (not title / chapter divider / qa), does it have ≥ **25** shapes? Toy density (single pattern call ≈ 10 shapes; pattern + chrome ≈ 15) on a slide with proposal-grade content = automatic FAIL. Rewrite **bespoke** referencing `reference_corpus/proposal_dense.png` (~50 shapes) or `personnel_equipment.png` (~60 shapes) — Read those PNGs + their source in `reference_corpus/generate.py` before the rewrite. |
| **Chrome** (todo 011) | Does the slide carry `h.deck_chrome` (eyebrow + footer + page number)? Content slides without chrome look orphaned in the deck. Title slide / chapter divider are exempt. |

For each category that scores < 4: write one specific complaint
("S3's headline is centered, killing the asymmetric tension a thesis
slide needs") + the fix ("left-align the headline at col=1 span=8,
leave col=9-12 empty for breathing room"). Then call
`update_slide(slug, deck_id, slide_id, code=<rewritten snippet>)`.

**Loop**: re-export, re-score, max 3 rounds. After round 3, accept
the deck as-is and surface the remaining weak categories in the user
summary so they know what to ask for next.

**When `slide_pngs_skipped` is True**: the export couldn't produce
PNGs (no LibreOffice / no PyMuPDF on this machine). Skip the critique
loop and tell the user — they can install soffice + pymupdf to enable
it.

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
