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

For each slide, decide the **render_mode**. This decides whether the
slide's text stays editable in the exported .pptx — choose carefully:

- `text` — title + bullet body rendered as **NATIVE, editable
  PowerPoint text**, themed with the concept's fonts / colours /
  spacing. **This is the default for any slide that is mostly words** —
  background, methods narrative, takeaways, agenda, section dividers.
  The reviewer can edit it in PowerPoint and it inherits the deck design.
- `paper-figure` — re-use a manuscript figure full-bleed (set `figure_number`).
- `ai-image` — a generated image: an eyecatch (cover / closing) or an
  abstract concept slide that is image-led, not text-led.
- `code-shape` — a single PNG you draw with code, embedded **full-bleed**.
  ⚠ The WHOLE slide becomes a flat picture — any text in it is baked
  into the bitmap, NOT editable in the .pptx, and ignores the deck's
  fonts/theme. Use it **only** for a genuine code-drawn data visual
  (a real plot / chart). **Never** make a prose- or bullet-heavy slide
  `code-shape` — that is the #1 way to ship an ugly, unreadable,
  uneditable slide. Text-heavy slide → `text`.
- `hybrid` — **title + native body bullets (rendered in the LEFT half)
  + one or more image regions** (positioned by you, typically on the
  right). This is the right mode for "title + bullets + a figure /
  diagram" — the bullets stay editable native text, the figure is an
  image region. Also for multi-image slides. Set with
  `set_slide_regions` (see "Multi-image slides"). Don't set this in
  `add_slide`'s render_mode — let `set_slide_regions` flip it.

Rule of thumb: **if you'd write more than a few words of text on the
slide, it is a `text` slide.** `code-shape` / `ai-image` are for slides
that are fundamentally a picture.

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
  render_mode="text" | "code-shape" | "paper-figure" | "ai-image" | "hybrid",
  figure_number=<N>,   # if render_mode == paper-figure
)
```

**Prompt template rule**: every prompt MUST start with the unity
header using placeholders. Example:

> `"{accent} accent. {display_font} typography. Minimal modern academic
> theme. Body: …"`

Never hardcode `"navy blue"` or `"Inter"` — write `{accent}` /
`{display_font}` so theme switching is a no-op rebuild.

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
