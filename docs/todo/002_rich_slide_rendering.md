# 002 — Rich slide rendering beyond literal markdown

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Yang Jae Kang, project `ai-breeding`, 2026-05-25.
**Status:** closed · landed via `render_mode="code"`.
**Related:** [001 — Native-language prose in the harness](./001_native_language_prose_in_harness.md)

## Resolution log

- **2026-05-25** — first attempt landed (`commit 93ca849`): expanded the
  body-markdown renderer with pull-quote / tag-pill / code-panel block
  emitters in `deck_render._render_markdown_block`. This was a misstep
  — the user pointed out (2026-05-26) that markdown's grammar is too
  thin to drive slide design, and trying to do so produces mediocre
  slides regardless of how much sugar we layer on top.
- **2026-05-26** — reverted the markdown-rich layer. `body` is back to
  plain-text rendering (`deck_render._render_simple_body`). Visual
  richness is to be delivered via the slide's `code` field — a python-
  pptx snippet the agent writes per slide that composes the slide
  natively.
- **2026-05-26 (same day)** — Step 2 shipped. `render_mode="code"`
  added. At PPTX export time the slide's `code` snippet executes
  against a prepared namespace (slide, palette, fonts, type_scale,
  Pt/Inches/MSO_SHAPE, and an `h` helpers namespace). Helpers in
  `slide_render_helpers.py` cover the common boilerplate
  (`accent_stripe`, `title_block`, `bullet_list`, `card`, `card_grid`,
  `pull_quote`, `image_path`, `image_region`, `image_figure`). Snippet
  exceptions degrade the slide to plain text and surface in the export
  result's `code_errors[]`. paper-deck SKILL §5a rewritten with the
  helper catalog and two worked examples. Closing the todo.

---

## TL;DR

`export_deck_to_pptx` currently renders slide `body` markdown by mapping it 1:1 to PowerPoint primitives — `**bold**` becomes a bold text run, `- item` becomes a bulleted paragraph, blockquote becomes a regular paragraph. The result looks like *raw markdown rendered to PPTX*, not like *a designed slide*. The medium (PowerPoint) supports far richer visual vocabulary — colored callout cards, badges, quote blocks with side bars, two-column comparisons, KPI tiles, accent strips, icon glyphs — and none of that is being leveraged. The export should treat markdown as a *semantic specification* and render it through a richer translation layer (HTML/CSS via headless browser, or rich python-pptx shape composition, or a JSX-style component model).

---

## Concrete observation

For deck `multi-modal-agricultural-ai-...`, slide bodies are written in deliberately structured markdown — e.g. the harness slide (S16):

```markdown
**MCP**가 *어떤 도구가 있는가*를 정의한다면, **Harness**는 *그 도구를 어떻게 쓰는가*를 정의합니다 (LLM 런타임).

- **Memory**: 세션 사이에 결정과 교정이 쌓이고, 다음 대화는 그 위에서 시작
- **Hooks**: 특정 이벤트에 자동 실행 (교배 등록 직전 검증, 내보내기 전 DOI 확인 등)
- **Slash commands**: `/literature-review` 같은 재사용 가능한 작업
- **Context manager**: 매 순간 LLM이 주목하는 정보를 관리

> **대화하는 행위가 곧 다음 버전의 AI를 만드는 행위입니다.** 한 번 정교화한 교배 설계 휴리스틱은, 다음 세션부터 자동으로 적용됩니다.

*Era II = 데이터를 디지털로 / Era III = 실천을 디지털로*
```

In the current export, this becomes a slide with:
- A title bar
- A normal paragraph (the opening sentence with bold + italic spans)
- Four bullet points (bold prefix + colon + normal text)
- One blockquote (rendered as another normal paragraph with bold spans)
- One italic line

There is *no visual differentiation* of structure beyond the bullet symbol. A reader's eye does not naturally group "the four primitives," does not find the punchline blockquote, does not see the closing slogan as a separate emphasis. Yet a competent slide designer would render this content with:

- **Four colored callout cards** for the primitives (Memory / Hooks / Slash commands / Context manager), each a small panel with the bold label as a tag and the description below, two-per-row
- **A pull-quote block** for the blockquote — left accent bar, larger type, indented
- **A divider strip** for the closing italic line — accent-colored

That is the same content; only the rendering changes.

The pattern repeats across the whole deck. Every slide carries structural intent that the markdown captures but the PPTX renderer flattens.

---

## Why this belongs in the harness, not per slide

1. **Authoring efficiency.** The user writes markdown because it is fast and version-controllable. If the user has to escape into "now I will design this slide in PowerPoint by hand," the harness has failed to do its job.

2. **Consistency across slides.** A renderer that recognises `> ...` as "pull-quote callout" applies the same visual treatment everywhere — automatically. A user designing 23 slides by hand will not be consistent.

3. **Theme switchability.** A native text slide today already inherits accent / typography from the deck concept (commit `ad40f76` and follow-ups). The same channel should carry richer style decisions — callout-card color, quote-block styling, divider weight — so swapping themes propagates to all slides.

4. **Two ecosystems already solved this.** Reveal.js, Marp, and similar HTML-based slide tools accept markdown and produce richly styled slides routinely. The PPTX export is the laggard.

---

## Proposed approaches (dev team picks; ordered by effort)

### A. *Cheapest* — semantic shape vocabulary inside python-pptx

Stay with python-pptx, but expand `_render_markdown_into` (in `tools/deck_render.py`) to map markdown constructs to *richer shape compositions*, not just text runs:

| Markdown construct | Current PPTX output | Proposed PPTX output |
|---|---|---|
| `> quote` | Normal paragraph | Side-bar callout: vertical accent rectangle on the left + indented paragraph + larger type |
| `- **Tag**: text` | Bullet, bold prefix | Two-column row: small bold tag pill on left, body text on right |
| `1. ...` ordered list of 4–6 items | Numbered paragraphs | Numbered cards in 2×2 / 3×2 grid (within the body box) |
| `*emphasis*` standalone line (not in paragraph) | Italic paragraph | Accent-colored divider line above + italic centred slogan |
| Triple-dash `---` | Hairline rule (current) | Keep as hairline rule |
| Code block (`\`\`\``) | Plain text | Mono font + tinted background panel + 1px border |

Effort: medium. All buildable with python-pptx primitives that already exist (`add_shape`, `add_textbox`, `MSO_SHAPE.ROUNDED_RECTANGLE`). The work is *layout logic* — measuring how many bullets there are, packing them into a grid, etc.

### B. *Best fidelity* — HTML/CSS renderer + headless browser → image slide

Render each slide as an HTML page (one CSS framework: Tailwind, vanilla, whatever) and use Playwright / Puppeteer / WeasyPrint to capture it as a high-res PNG. The PPTX then embeds the PNG as a full-bleed image slide.

Pros:
- Full visual fidelity. Any CSS layout becomes available — flexbox grids, gradient cards, shadowed quote boxes, icon glyphs from any web font, etc.
- Slide designs live as testable HTML templates the team can iterate on.
- The same renderer drives the dashboard preview and the export — no drift.

Cons:
- New runtime dependency (headless browser).
- The slide text is no longer editable in PowerPoint (it's a baked PNG). Mitigation: also write a parallel `text-frame-only` PPTX for downstream editing, or treat the HTML→PNG path as the *presentation* output and python-pptx as the *editable* output.
- Higher per-slide render time.

Effort: medium-large. But the dashboard preview path (`apps/web/src/pages/ProjectPresentations.tsx`) already does HTML/CSS rendering — that work can be lifted into the export.

### C. *Component model* — JSX-style slide components

Define a small library of slide-component types (`<TitleSlide/>`, `<TwoColumn/>`, `<CalloutGrid/>`, `<PullQuote/>`, `<TimelineBand/>`, `<MetricTiles/>`, `<HybridFigure/>`, ...). Slide markdown becomes a *spec* that compiles into one of these components, optionally with hints from the role / role-frontmatter.

A `discussion` slide with four bullets → `<CalloutGrid items=[…]/>` automatically.
A `conclusion` slide with a quote → `<PullQuote text=… subtitle=…/>` automatically.

Pros:
- Best long-term maintainability — each slide type is a single component the team can refine.
- The same components serve the dashboard preview and the PPTX export (render different backends from the same component tree).
- Allows the harness to do *layout substitution* without changing slide bodies: the user updates markdown; the renderer decides which component fits.

Cons:
- Largest engineering investment up front.
- Needs a small DSL for the markdown → component mapping.

Effort: large. Ship in phases — start with 3–5 components covering 80% of slide types.

### D. *Hybrid* — semantic CSS classes embedded in markdown

Allow the user to write `:::callout-grid` / `::: pull-quote` / `:::two-col` fenced sections in the markdown body, mapped by the renderer to richer shapes. Falls back to plain rendering when no marker is present.

```markdown
:::callout-grid
- **Memory**: 세션 사이에 결정과 교정이 쌓이고…
- **Hooks**: 특정 이벤트에 자동 실행…
- **Slash commands**: `/literature-review`…
- **Context manager**: 매 순간 LLM이 주목하는 정보…
:::
```

Pros:
- User retains control over which slides get the richer treatment.
- Incremental — add new fences over time.
- Backwards compatible with existing markdown bodies.

Cons:
- Pushes design decisions back onto the user. Defeats some of the "harness does the design for me" win.

Effort: small-medium.

---

## Acceptance criteria

A slide whose body contains the harness-S16 markdown above (one paragraph with mixed emphasis + four `**Tag**: text` bullets + one blockquote + one italic standalone line) should export to PPTX in a form where:

1. The four primitives are visually grouped (e.g. as a 2×2 card grid or a vertical column with tag pills), not just as four naked bullets.
2. The blockquote reads as a distinct emphasis block, not as another paragraph.
3. The closing italic line reads as a divider / slogan, not as just-another-paragraph.
4. The same content rendered in a different deck theme picks up that theme's accent, typography, and card style without the slide body changing.
5. A native PowerPoint user can still nudge / edit the layout (or accept that the slide is a baked image, with editable text shipped in a sibling file).

---

## Cross-reference

This is the visual-rendering twin of the prose problem filed in [001 — Native-language prose in the harness](./001_native_language_prose_in_harness.md). Together they describe the same shortfall: the harness currently outputs *the user's markdown*, where it should output *a designed slide that happens to share the markdown's semantic structure*.

---

## Suggested labels

`area:export-pptx` · `area:slide-design` · `skill:paper-deck` · `priority:medium-high` · `effort:M–L`
