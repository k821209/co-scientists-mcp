# 008 — Figure slides waste vertical space; Latin+Korean type pair limps; hero pattern blows out short content

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Yang Jae Kang, project `ai-breeding`, 2026-05-27.
**Status:** closed 2026-05-27 — §A (figure_full pattern), §B (Noto Sans KR doc), §C (hero adaptive spacing + use-when guidance) all shipped. See "Resolution log" at the bottom.

## Resolution log

- **2026-05-27 §A figure space** — new `p.figure_full(slide, *, image_path=None, image_callable=None, caption="", palette, fonts, type_scale, sw, sh)` pattern. Image fills the body area (rows 1–6 of the grid ≈ 85% slide height) with contain-fit; caption rides in the bottom-margin strip outside the grid in muted body italics. ~17% more figure area than the prior `row_span=4` + caption-in-row-6 convention. `image_path` for filesystem PNGs; `image_callable=lambda **kw: h.image_figure(slide, N, **kw)` for paper figures from inside a code slide. Bound to `p` namespace; added to SKILL §5a structural catalog + quick-ref block. New corpus exemplar `figure_full.png` + manifest entry.
- **2026-05-27 §B Latin+Hangul pairing** — paper-deck SKILL §3 concept template now ships a comment block recommending **Noto Sans KR / JP / SC** for Korean / Japanese / Chinese audiences (Google's pan-CJK families with Latin glyphs co-designed to share metrics with the matching CJK script). A new paragraph below the Type-scale block explains *why*: Pretendard / Inter Latin glyphs are taller + heavier than the Hangul they sit next to and create a visible seam in mixed-script body text. Default `Inter Bold / Regular` stays for English-only audiences.
- **2026-05-27 §C hero short content** — `hero_with_trailing_evidence` gains content-length-adaptive row spacing. When the average evidence item is < 50 chars, the pattern switches to a tight per-row height (`body_pt × 4.2pt` ≈ 2-line cap) so items huddle near the top of the right column instead of being launched apart across the full body height. Docstring rewritten with explicit **Use when** guidance (headline ≥ 3 lines AND items ≥ 50 chars); shorter content steers callers toward `evidence_stack`. Reference corpus manifest entry's `do` / `dont` rewritten to reflect the same guidance; exemplar content swapped to long-form that earns the asymmetric layout.

3 new tests: `figure_full` renders 1 PICTURE filling > 55% of slide height + caption; `figure_full` raises `TypeError` when both / neither image source passed; `hero_with_trailing_evidence` with 3 short items keeps the row-01-to-row-02 gap < Inches(1.4) EMU. 391 total passing.

Deferred:
- **§B2 locale-aware default fonts** — auto-set Noto Sans KR / JP / SC when concept's `audience:` field contains Korean / Japanese / Chinese signals. The SKILL note steers the agent for now; convert to programmatic default if a future session shows it's still missed.
- **§C2 UserWarning on short hero content** — §C3 adaptive spacing already rescues the layout, so a warning would be diagnostic-only; ship if a future session shows the pattern still mis-picked.
**Related:** [005 — Pattern library quality](./005_pattern_library_quality.md), [007 — API consistency](./007_pattern_library_api_consistency.md) (filed as 006 locally, renumbered 007 upstream).

---

## TL;DR

After todo 007 landed (API consistency, palette, `h.text`, Cell namedtuple), I rebuilt the deck and the structural / code-level issues were largely gone. But three design-level issues surfaced that the agent ends up patching by hand every session:

1. **Figure slides shrink the image** to ~67% of available vertical space because the canonical pattern reserves a full grid row for a blank gap *and* another for the caption — even when the figure is the only thing on the slide. Agent has to notice visually, switch `row_span` to 6, and tuck the caption into the bottom margin outside the grid.
2. **Latin + Korean type pair limps** when display / body are set to `Pretendard SemiBold / Pretendard Regular`. Pretendard's Latin glyphs are squarer and heavier than its Hangul; in a deck where every body sentence mixes both ("**GS·BLUP**이 정확도 천장까지 끌어올림") the Latin words sit visually higher and bolder than the surrounding 한글 — the reader feels the seam. Fix: switch to **Noto Sans KR** (Google's pan-CJK family with Latin co-designed to share Hangul metrics).
3. **`hero_with_trailing_evidence` blows out on short content.** When the headline is 2 short lines and the evidence is 3 two-line items, the pattern's asymmetric "huge headline left, narrow numbered evidence right" reserves ~⅓ of the slide as deadspace and stretches the evidence column with massive inter-item gaps, so the two halves read as disconnected pieces of content. The fix that landed on every affected slide (S3, S10, S18, S20) was the same: swap `hero_with_trailing_evidence` → `evidence_stack` (claim above, tagged rows tightly stacked below). The hero pattern should not be the agent's default for tagged 3-item content.

All three are recurring DX taxes that should be paid once at the library level, not per deck.

---

## Bug A — figure slides waste a grid row

### Concrete observation

The agent's canonical figure-slide snippet (matching the reference corpus exemplar):

```python
g = h.grid(sw=sw, sh=sh)                       # 12 cols × 6 rows
f = g.cell(col=1, span=12, row=1, row_span=4)  # ← image gets rows 1–4
h.image_figure(slide, N, left=f.left, top=f.top, width=f.width, height=f.height)

c = g.cell(col=1, span=12, row=6, row_span=1)  # ← caption gets row 6
h.text(slide, "Fig N · …", ...)
```

Row 5 is empty by construction. On a 16:9 slide (7.5" tall) the grid's usable height is roughly `7.5 - 1.8 (top margin) - 0.6 (bottom margin) = 5.1"`. Of that, row 5 absorbs ~14% (~0.7") as a transparent gap with no visual purpose. The figure occupies rows 1–4 = ~3.4" tall but the slide could comfortably give it ~4.1" (rows 1–5).

User feedback verbatim: *"슬라이드 15번 같은걸 보면, 이미지가 잘 안보일 정도로 줄어들어 있지. 공간을 많이 버릴 이유가 있나?"*

The fix the agent has to apply by hand every time — and even `row_span=5` still wastes the bottom row to the caption strip when the figure could absorb that space too. The full fix is:

```diff
- f = g.cell(col=1, span=12, row=1, row_span=4)
- c = g.cell(col=1, span=12, row=6, row_span=1)
- h.text(slide, "Fig N · …", left=c.left, top=c.top, …)
+ f = g.cell(col=1, span=12, row=1, row_span=6)            # image owns the full grid
+ h.text(                                                    # caption drops into the bottom margin,
+     slide, "Fig N · …",                                     # outside the grid, in the 0.6" gutter
+     left=Inches(0.6), top=sh - Inches(0.45),
+     width=sw - Inches(1.2), height=Pt(28),
+     palette=palette, color=palette["muted"], fonts=fonts,
+     size_pt=type_scale["caption"], italic=True,
+ )
```

So the figure consumes the full grid height (rows 1–6 = ~5.1″) and the caption rides in the 0.6″ bottom-margin strip *outside* the grid. The reader gains another ~17% of figure area vs `row_span=5`, and the caption still has its own breathing room because it isn't competing with the figure for grid real estate.

User feedback after seeing `row_span=5`: *"row span 한칸 더 쓰는걸로"* — i.e., go all the way to `row_span=6` and pull the caption out of the grid. Confirmed.

That's a small but meaningful edit. It has to happen on every figure slide in every deck, after the agent visually notices the shrinkage. **The library shipped the wasted-row layout as the canonical example**, so the agent reproduces it unless told otherwise.

### Why this belongs in the harness

1. **The reference corpus exemplar uses `row_span=4`** (cf. `paper-deck/reference_corpus/*.py` for the canonical figure exemplar). That is the source of truth the agent pattern-matches against. Fixing it once propagates to every future deck.
2. **No worked example warns the agent** that row 5 is a deliberate breathing gap (it isn't — it's an accident of the 6-row grid + bottom caption convention).
3. The fix is one-line; the cost of not landing it is one round-trip of visual critique on *every* figure-bearing deck. Across a project's history that adds up.

### Proposed fixes

**A1 (cheapest).** Update the reference corpus's "figure slide" exemplar + the SKILL §5a worked example to use `row_span=6` for the image and a caption placed in the bottom margin via direct positioning (`top=sh - Inches(0.45)`). Adjust the docstring guidance accordingly: *"On figure-only slides, the image cell spans the FULL grid (rows 1–6); the caption is tucked into the bottom-margin strip outside the grid, not into a grid row."*

**A2 (better).** Add a `p.figure_full(slide, *, figure_number, caption, ...)` pattern that bakes the right proportions in: full-grid image (rows 1–6), caption in bottom margin, `fit="contain"`, with a sensible upper bound on caption length. Then a figure slide collapses to a single call, and the proportions can never drift.

```python
p.figure_full(
    slide,
    figure_number=3,
    title="육종 MCP — 레퍼런스 아키텍처",
    caption="Fig 3 · LLM (사고) ↔ MCP (도구) ↔ Harness (운영). …",
    palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh,
)
```

This is the "intent-axis" answer to the structural problem and fits the todo 006 §B catalog.

---

## Bug B — Pretendard's Latin glyphs don't sit with its Hangul

### Concrete observation

User feedback verbatim: *"글씨체가 여전히 이상하다. Noto 글씨체로 가자 그냥. 영문글씨체랑 한글글씨체랑 어울리지가 않은것도 문제임."*

In a deck where 8 out of 20 slides mix English and Korean inside the same paragraph (and even the same word — "**Era I·II — 데이터·모델은 충분, 다만 한 방향이었습니다.**"), the typeface choice for "display" and "body" has to *visually unify* the two scripts. Pretendard does this beautifully for Hangul but its Latin glyphs are derived from Inter — they read taller, squarer, and a hair bolder than the Pretendard Hangul they sit next to. In a side-by-side test on the take-home slide:

- *Pretendard:* the word "MCP" in "MCP가 다리" sits noticeably proud of "다리". The English looks like it was pasted in from a different deck.
- *Noto Sans KR:* the word "MCP" in "MCP가 다리" sits at the same baseline, same x-height, same weight register as "다리". The Latin reads as part of the Korean sentence.

Noto Sans KR ships with Latin glyphs explicitly designed to harmonise with the Hangul (Google's pan-CJK directive). It is the *correct* default for Korean academic decks that mix English jargon — which most of them do.

### Why this belongs in the harness

1. **Pretendard is the SKILL's recommended Korean font today.** That's the wrong default for mixed scripts.
2. The agent has no diagnostic vocabulary for "Latin and Hangul don't pair" — it sees the rendered slide and reads it as "ugly" without knowing to inspect *which* metric is off.
3. Every Korean-audience deck the harness ships will hit this. The cost is paid one user-frustration at a time.

### Proposed fixes

**B1 (cheapest).** Update the `paper-deck` SKILL §3 concept template to recommend Noto Sans KR as the default for `audience` containing 한국 / Korean / ko signals. Pretendard remains *available* but is no longer the first suggestion for mixed Latin+Korean prose.

**B2 (better).** Detect the locale of the audience field at concept time. If Korean, set `Typography: display: Noto Sans KR; body: Noto Sans KR;`. If Japanese, set `Noto Sans JP`. The agent doesn't have to know the typographic theory — the harness picks the pan-CJK family for the right locale.

**B3 (best).** Document the *why* in the SKILL ("Noto Sans KR is a pan-CJK family with Latin glyphs designed to share metrics with Hangul. Pretendard's Latin is taller and bolder than its Hangul, which creates a visible seam in mixed-script body text.") so future agents can diagnose the problem on their own.

---

---

## Bug C — `hero_with_trailing_evidence` wastes space on short tagged content

### Concrete observation

User feedback verbatim on S18 (위험과 검증): *"18번 슬라이드 스타일 이상한듯, 가설과 evidence 같은데, 시인성도 안좋고 이상한 느낌임. 이런건 거의 여백이 이상해서 그런거 같음."* Then on the other three slides using the same pattern: *"앞에서 했던 같은 스타일의 슬라이드도 바꿔야지."*

The pattern's docstring is right for *its intended use case*: a thesis statement so important it deserves ⅔ of the slide width as one massive headline, with a narrow "footnote" column of supporting items shrunk down at right.

But in practice, the agent picks this pattern for any "headline + 3 evidence" content. When the content is:

- **Headline**: 2 short lines (e.g., *"잘못된 교배 추천은 / 한 시즌을 잃습니다."*)
- **Evidence**: 3 short tagged items (e.g., *"Grounding — 모든 추천은 명시적 MCP 호출에서만 합성."*)

…the rendered slide has **~⅓ of the left half empty** below the headline (the hero reserves vertical room for up to 4 wrapped lines) AND **~⅓ of the right column empty between evidence items** (the pattern distributes 3 items across the full slide height with `(sh - top) / 3` row gaps, which becomes ~1.7" of empty white between two-line items).

Across the 4 hero-pattern slides in this deck (S3 thesis, S10 bottleneck, S18 risk+verification, S20 take-home), every single one suffered the same problem and needed the same fix.

### What worked: swap to `evidence_stack`

`evidence_stack` packs the same semantic content much more tightly:
- The *claim* sits at top in display type (replaces the hero headline)
- The *items* are tagged rows stacked tight below, each row sized to its content
- No reserved blank space; the pattern flows to its natural height

After conversion, all 4 slides read at a glance with no "where am I supposed to look next" gap.

### Why this belongs in the harness

1. **The reference corpus exemplar for `hero_with_trailing_evidence` uses long content** — a 3-line dense headline + 3 long-paragraph evidence items. The agent pattern-matches against this exemplar and copies the structure. But the *typical* slide content (short Korean tagged points) is short, not long.
2. **No content-length guidance in the docstring.** It says *"headline: max ~60 chars; wraps to 3 lines. evidence: 2–4 items, each max ~80 chars."* — the MAXIMUMS, not the *minimums-where-this-pattern-still-works*. A headline of 30 chars and evidence of 40 chars each will render with massive whitespace.
3. **The agent has no diagnostic vocabulary** to spot "this is the wrong pattern for this content length." It sees the rendered slide as "ugly" and stares.

### Proposed fixes

**C1 (cheapest).** Update the docstring + reference corpus caption for `hero_with_trailing_evidence`:

> **Use when:** headline ≥ 3 lines AND evidence items are ≥ 50 chars each. The pattern's asymmetry needs *long* content on both sides to earn its weight. For short tagged content (headline ≤ 2 lines, items ≤ 40 chars), prefer `evidence_stack` — it packs the same semantic shape into ~⅔ the vertical space without the asymmetric reservation.

**C2 (better).** At pattern entry, *measure* the content. If the headline wraps to < 3 lines OR the average evidence item is < 50 chars, emit a `UserWarning` ("hero_with_trailing_evidence has short content; consider evidence_stack — see todo 008 §C") and proceed with tighter spacing. The warning trains the agent over time; the tighter spacing rescues the current slide.

**C3 (best).** Adapt the pattern's inter-item gap to content height: `gap_pt = max(SPACING_UNIT_PT * 2, (available_h - sum(item_h)) // max(1, n_items - 1) // 2)` rather than spreading items uniformly to fill the slide. Short items huddle naturally near the top of the column instead of being launched apart.

---

## Acceptance criteria

A future agent building a 20-slide Korean-audience deck on a fresh project should:

1. **Produce figure slides where the image fills the full grid (~100% of grid height, ~80% of slide height)** without manual `row_span` adjustment.
2. **See harmonised Latin + Hangul** in body text on first export — no manual font swap, no "글씨체가 이상하다" feedback round-trip.
3. **Pick `evidence_stack` over `hero_with_trailing_evidence`** for short-tagged-3-item content by default, OR have the hero pattern render acceptable tight spacing when handed short content.
4. **Be told *why*** in the SKILL — not just *what* — so the next typography, layout, or pattern-selection question is solved on first principles.

---

## Cross-reference

| Todo | Layer | Status |
|---|---|---|
| 001 | Prose (translation-ese) | Applied |
| 002 | Rich rendering | Applied |
| 003 | Content-first design | Applied |
| 004 | Design methodology (grid + manifesto + critique + patterns + iconography + type roles + corpus) | Closed |
| 005 | Pattern visual quality | Closed (007 absorbed) |
| 007 | API consistency + palette + `h.text` + Cell + slide-first images | Closed |
| **008** | **Figure space + Latin/Hangul pair** | **This todo** |

004 fixed *what to design*. 005/007 fixed *how to call the patterns*. 008 catches the next layer down: *what the patterns ship as the canonical example, what default fonts they suggest, and which pattern fits short Korean tagged content*. The agent inherits these defaults; if they're slightly wrong, every deck pays the same tax.

---

## Suggested labels

`area:slide-patterns` · `area:typography` · `area:reference-corpus` · `area:hero_pattern` · `priority:medium` (visual quality, not blocking) · `effort:S (corpus + SKILL edits + docstring content-length guidance) + M (figure_full pattern + locale-aware fonts + hero adaptive spacing)`
