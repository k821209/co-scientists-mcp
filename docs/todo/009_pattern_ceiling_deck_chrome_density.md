# 009 — Pattern ceiling, deck chrome, density: closing the gap to the original

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Claude / Yang Jae Kang, project `ai-breeding`, 2026-05-27.
**Status:** closed 2026-05-27 — A (SKILL nudge inverted) + B (h.deck_chrome) + C (h.table) + D (p.gantt_chart) + E (gantt corpus exemplar) all shipped.

## Resolution log

- **2026-05-27 A — SKILL nudge inverted.** Replaced "Don't reinvent — patterns cover ~90%" with "Patterns are a starting point, not a ceiling." New text spells out: real decks have 30–70 shapes per content slide, our patterns produce ~10–15, the cap is the agent's compose budget per slide not python-pptx's capability. Density (~25–60 shapes) is a *positive* signal when each shape carries info.
- **2026-05-27 B — h.deck_chrome.** One-call helper that adds eyebrow upper-left (semantic label like "HOW · 추진 방법") + footer bottom-left (project / deck name) + page-number bottom-right (e.g. "5 / 13"). Each argument is optional — skip what you don't need. Bound on `h` namespace.
- **2026-05-27 C — h.table.** Native `MSO_SHAPE_TYPE.TABLE` helper. Headers in display font + accent color; body cells in body font; `first_col_emphasis=True` styles col 0 in display (for personnel / timeline labels). Real editable PowerPoint table that nudges + resizes properly in the editor — replaces card_grid for tabular data.
- **2026-05-27 D — p.gantt_chart.** Activity-rows × period-columns timeline. Items = `[{label, start, span}]` (1-indexed). Period labels across the top, accent-colored rounded rectangle bars positioned per item, zebra-striped row backgrounds. Used together with `h.deck_chrome` reproduces the original's slide 9 visual quality.
- **2026-05-27 E — gantt corpus exemplar.** New `reference_corpus/gantt_chart.png` showing the pattern with realistic Korean activity labels + chrome (eyebrow, footer, page 9/13). The exemplar is what the agent pattern-matches against on first use — shipping a high-density example trains the agent toward that density.

3 new tests (deck_chrome 3 chrome pieces present; h.table emits a real `MSO_SHAPE_TYPE.TABLE`; p.gantt_chart produces ≥7 bars + activity labels). All 394 pass.

Visual verification: a Gantt slide + a dense bespoke proposal slide (3 platform cards + 5-stage pipeline + target metrics + deck_chrome) rendered and compared side-by-side with the original's slide 9 / slide 5. Capability gap closed; remaining quality differences are content-curation, not infrastructure.

Deferred:
- A second dense bespoke exemplar in the corpus (e.g. the original's slide 10 personnel + equipment style). The capability is there; one exemplar suffices for now.
- `p.platform_comparison` or similar named pattern for "3 cards in a row with mode + spec + tag" — the dense bespoke approach (hand-rolling with h.text + h.card) is fine; pattern is convenience-only.
**Related:** 004, 005, 006, 007, 008 — every previous design todo. This
one explains *why our slides still look toy* and what to do.

---

## TL;DR

The user attached a `.pptx` produced by the original co-scientist repo
and asked why ours doesn't look as good. **The original uses the same
mechanism we do — fully editable python-pptx with native auto-shapes,
text-boxes, and tables.** No PIL bake, no different backend, no
font-rendering magic. Inspecting the original's slides:

| Original slide | shape count |
|---|---|
| Slide 5 — *HOW · 추진 방법* (3-platform cards + 5-stage pipeline) | ~46 |
| Slide 9 — *WHEN · 7개월 병렬 운영* (full Gantt chart, 12 rows × 8 months) | ~73 |
| Slide 10 — *WHO · 사업 수행 능력* (4-person table + multi-section equipment list) | ~65 |

Our patterns produce **10–15 shapes per slide**. The original's slides
have **30–70**. The gap is *what the agent codes per slide*, not what
python-pptx supports.

Three root causes:

1. **Our patterns became a ceiling.** SKILL says "use patterns, don't
   reinvent" — exactly the wrong nudge when the slide content needs a
   bespoke 30-shape layout. The agent reaches for `p.flow_pipeline` and
   stops there. Original's agent kept going.
2. **No deck-level chrome.** Original ships consistent eyebrow labels
   (WHO / WHY / HOW / WHAT / WHEN) + footer (deck title) + page number
   ("5 / 13") on every slide. We have none of that.
3. **No native table helper.** Original's slide 4 uses
   `MSO_SHAPE_TYPE.TABLE` — a real python-pptx table. We never emit one;
   our `card_grid` is a misfit substitute for tabular data.

The reference corpus we shipped doesn't help either — every exemplar is
a toy demo (3 cards, 2 columns). The agent pattern-matches against the
toys and ships toys.

---

## Concrete observation

The original's slide 5 in detail:

- Top-left eyebrow: `HOW · 추진 방법` (small caps, accent color)
- Slide title: `Part 1 — 참조 유전체 구축 (3중 플랫폼 전략)`
- 3 platform cards in a row: PacBio HiFi / ONT PromethION / DNBSEQ-G99,
  each with mode (외주/자체), throughput spec, and read-type
- 5-stage pipeline row below: 시료 QC → 라이브러리 → K-mer → de novo → Hybrid →
  Assembly QC
- Target metrics paragraph (Contig N50, BUSCO completeness)
- Footer left: project name (기러기류 종 특이적 마커 발굴…) + company
- Footer right: page number `5 / 13`

This is one slide. The agent decided the layout suited the content and
wrote it directly with `h.text` / `h.card` / arrow shapes — no pattern
covered it.

---

## Proposed fixes

### A — Invert the SKILL nudge (highest leverage)

§5a today says:

> Don't reinvent — the `h.*` helpers cover ~90% of the layouts you'll
> need. Drop to raw `slide.shapes.add_textbox(...)` only when no helper
> fits.

Rewrite to:

> **Patterns are a starting point, not a ceiling.** When the slide's
> content asks for a 30-shape bespoke layout (a proposal page, a Gantt
> chart, a side-by-side comparison with tagged differentiators), compose
> it directly with `h.*` primitives + raw `slide.shapes.add_shape()` —
> don't shoehorn into a generic pattern. Patterns are for fast common
> cases; *bespoke is the default* when content is dense.

The line that today nudges toward patterns is the line that ships toy
slides.

### B — Deck-level chrome helper

```python
h.deck_chrome(
    slide, *,
    eyebrow="HOW · 추진 방법",   # upper-left semantic label
    page_number=5, total=13,    # bottom-right "5 / 13"
    footer="기러기류 종 특이적 마커 발굴 · ㈜디보",  # bottom-left muted
    palette, fonts, type_scale, sw, sh,
)
```

One call per slide, after `h.accent_stripe + h.title_block`. Brands
the deck consistently and gives the audience a *where am I* signal at
every slide.

### C — Native table helper

```python
h.table(
    slide, *,
    headers=["주요 활동", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"],
    rows=[
        ["착수보고 및 계획 확정", "■", "", "", "", "", "", "", ""],
        ["시료 QC, HMW DNA 추출", "■", "■", "", "", "", "", "", ""],
        ...
    ],
    left=Inches(0.5), top=Inches(2), width=Inches(12), height=Inches(4.5),
    palette, fonts, type_scale,
    first_col_emphasis=True,
)
```

Real `MSO_SHAPE_TYPE.TABLE`. Headers in accent + bold; first column in
display font when `first_col_emphasis=True`. Native PowerPoint table that
nudges and resizes properly in the editor.

### D — Gantt pattern

`p.gantt_chart(slide, *, activities, periods, palette, fonts, type_scale, sw, sh)` —
activity rows with right-positioned bars across `periods` columns.
Subsumes the agent re-implementing the slide-9 layout every time.

### E — Dense bespoke exemplars in the reference corpus

Ship 1–2 corpus PNGs that show 40+ shape slides (e.g. a re-creation of
the original's slide 5 with anonymised content). The agent
pattern-matches against the corpus; show density, density propagates.

---

## Acceptance criteria

After fixes:

1. A future deck's average shape count per content slide ≥ 25 (vs ~12
   today).
2. Every slide carries eyebrow + footer + page number (via
   `h.deck_chrome`).
3. The agent emits at least one native `MSO_SHAPE_TYPE.TABLE` per deck
   when the content has tabular data (timeline, personnel, equipment).
4. The "don't reinvent" SKILL line is gone; the new nudge says
   "patterns are a starting point — go bespoke when content asks".

---

## Cross-reference

| Todo | Status | Insight |
|---|---|---|
| 001–008 | Closed | Mechanism + pattern QA + design discipline |
| **009** | **This todo** | **Pattern ceiling + chrome + native tables + density nudge** |

004–008 made the patterns *correct*. 009 makes the patterns *not the
limit*. Without 009, every deck stays at toy density even when the
content asks for proposal-grade layouts.

---

## Suggested labels

`area:slide-patterns` · `area:helpers` · `area:design-methodology` ·
`area:reference-corpus` · `priority:high` (visible quality ceiling) ·
`effort:M (SKILL rewrite + deck_chrome + h.table + 1 dense exemplar) + L (gantt pattern + 2nd dense exemplar)`
