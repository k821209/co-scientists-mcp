# 005 — Pattern library quality: shipped patterns fail on real use

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Yang Jae Kang, project `ai-breeding`, 2026-05-26.
**Status:** closed — bugs A/B/C fixed + contracts in every pattern + integration tests landed 2026-05-26.

## Resolution log

- **2026-05-26** — All three bugs (A/B/C) fixed and visually verified
  against rendered PNGs of worst-case Korean content. Module-level
  constants `_BODY_TOP = Inches(1.85)` / `_SIDE_MARGIN = Inches(0.7)` /
  `_BOTTOM_MARGIN = Inches(0.6)` introduced so every under-title
  pattern starts beneath the agent's preamble. Per-pattern fixes:
  - **Bug A `numbered_milestone_arc`** — rewritten on equal-width
    slot layout: each milestone gets `slot_w = (sw - 2*margin) / n`
    of horizontal real estate; marker centered in slot, tag + note
    stacked **below the line** (no more alternating chaos). Timeline
    runs only between the first and last slot centres so it never
    extends past slide edges. Tag box now reserves space for 2
    wrapped lines so notes can't overlap.
  - **Bug B `hero_with_trailing_evidence`** — moved headline +
    evidence column from y=Inches(1.0) down to `_BODY_TOP`, leaving
    the title-bar zone for the agent-drawn `h.title_block`. Right
    column reflowed onto computed coordinates (no hardcoded
    Inches(8.6)).
  - **Bug C `chapter_divider`** — vertical-centered the chapter
    label (block_top = (sh - block_h) // 2), bumped label type to
    `max(56, cover_title + 16)`, and moved the accent rule **under**
    the label as a visual anchor instead of orphaned above it.
    Summary follows below the rule, all centered horizontally.
  - Other under-title patterns had their top-y bumped to
    `_BODY_TOP`-based coordinates to enforce the same contract.
- **Contracts in docstrings** — every pattern declares either "Owns
  the whole slide" (chapter_divider only) or "Goes under a
  title_block" (other 9), plus content limits (max chars, item
  counts). paper-deck SKILL §5a catalog gains a Contract column.
- **Integration tests** — 17 new (todo 005 §D + partial §B):
  parametrized over 8 under-title patterns, two checks each — (1)
  only the 3 preamble chrome shapes sit in the title zone (catches
  Bug-B-class collisions), (2) every shape stays within slide bounds
  (catches Bug-A-class edge overflow). Plus an own-slide test for
  chapter_divider (no preamble; label centered within Inches(1.0) of
  slide vertical centre; zero shapes in title zone). All 359 tests
  pass.
- **Visual verification** — a 10-slide deck (one per pattern with
  Korean content + plain-text baseline) was rendered through
  export_deck_to_pptx to PNGs and inspected; all three concrete
  bugs from this report are gone in the rendered output.
- **Open from this todo:** golden-image regression tests (PNG diff
  infra) — deferred; integration tests + visual review serve as the
  interim QA discipline. Stop-the-line on new patterns implicitly
  applied — no new patterns until existing 10 stay clean.
**Related:** [004 — Design methodology for code slides](./004_design_methodology_for_code_slides.md) (§B shipped this library).

---

## TL;DR

Todo 004 §B shipped a `slide_patterns.py` module with 10 whole-slide patterns (`hero_with_trailing_evidence`, `chapter_divider`, `numbered_milestone_arc`, …). Promising in concept. In practice, **every pattern tested so far has at least one visual defect** when called with realistic content (Korean text, a 4-marker timeline, an agent that has already called `h.title_block`). The critique loop (§A) catches them immediately — exactly what it's for — but the cost is that no pattern can be used as-shipped. Each one needs a fix or workaround before it's ready for production decks.

This todo documents three concrete defects found in the first session of use, proposes the QA discipline the library needs to land in good shape, and suggests a stop-the-line policy until existing patterns pass.

---

## Bugs reproduced (3 patterns tested, 3 with defects)

### Bug A — `numbered_milestone_arc` overlaps tag with note and overflows slide edges

**Repro**: 4 milestones, each `{tag, note}` with Korean text ~20 chars.

**Defect 1 — Edge clip:**
```python
side = Inches(0.8)
x = side + int(line_w * (i / (n - 1)))   # i=0  → x = 0.8"
block_w = Inches(2.0)                    # ←  block centred on x
# block left edge = 0.8 - 1.0 = -0.2 inches → OFF SLIDE
```
First milestone's tag box extends past the slide's left edge; last milestone's past the right edge. Tags clip.

**Defect 2 — Wrap-overlap:**
```python
_emit_text(slide, m["tag"], height=Pt(tag_pt * 1.5), ...)
_emit_text(slide, m["note"], top=block_top + Pt(tag_pt * 1.6), ...)
```
Tag's height is computed as one line (`tag_pt * 1.5`), but tags like *"2018 · DL-on-SNP"* or *"2024 · Genomic LMs"* wrap to two lines. Note then starts at `block_top + tag_pt * 1.6` ≈ one-line-down and **overlaps the second wrapped line of the tag**.

**Defect 3 — Alternating + wrap = chaos:**
`above = (i % 2 == 0)` toggles each milestone above/below the line. With wrapped tags, the "above" milestones bleed downward into the line area and the "below" ones bleed upward — overall reading order breaks.

**Observed slide**: tags clipped on left/right edges, year + label + note overlapping in vertical stacks; "1, 2, 3, 4" circles correct but supporting text unreadable.

### Bug B — `hero_with_trailing_evidence` collides with caller's title_block

**Repro**:
```python
h.accent_stripe(slide, palette=palette, sw=sw)
h.title_block(slide, "오늘의 한 줄", ...)        # ← agent draws slide title here
p.hero_with_trailing_evidence(slide,
    headline="앞으로 10년의 농업 AI는, …",
    evidence=[…],
    ...)                                          # ← pattern then draws its own headline
```

**Defect**: The pattern draws its own large headline at the top of the slide body, **right on top of the agent-drawn title** ("오늘의 한 줄"). The accent rule from `h.title_block` cuts horizontally through the headline. Two title-magnitude texts stack in the same Y range with no clearance.

**Root cause**: The pattern *assumes the slide is bare* (no title yet). The SKILL §5a tells the agent to call `h.accent_stripe` + `h.title_block` first; the pattern docstring doesn't say "skip title_block — the pattern owns the top of the slide". One of the two has to give.

### Bug C — `chapter_divider` produces a thin / unanchored result

**Repro**:
```python
p.chapter_divider(slide,
    chapter_label="Era I",
    summary="시퀀스 예측 (2010–). 유전체 안에서만 본 15년. 병목: data scope.",
    palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh)
```

**Defects**:
1. Vertical placement of "Era I" sits at roughly y = ¾ slide height — not visually centred (which is what a chapter divider should feel like).
2. The pattern's own short accent rule appears *above* "Era I" in a spot where there's no title — it looks like an orphaned tick mark hovering in white space.
3. The chapter label uses default body type sizes — not the *display.chapter* magnitude (52–60pt) that gives a chapter opener its weight. "Era I" reads at title-bar size, not chapter-divider size.

**Observed slide**: lots of whitespace at the top, small "Era I" in the middle-left, isolated accent stripe with nothing to anchor, summary in plain italic body type. None of the *"new section starts here"* visual weight that a chapter divider exists for.

---

## Pattern of the bugs (the meta-issue)

Three patterns, three failure modes, one shared root cause: **the patterns were written without contracts about what state the slide is in when they're called**.

| Bug | Caller's state assumed by pattern | What actually happens |
|---|---|---|
| A (numbered_milestone_arc) | "block_w fits inside slide regardless of where x is" | First/last x are at `side`, which is *inside* the slide; the block then extends OUT |
| B (hero_with_trailing_evidence) | "Slide is empty — pattern owns the whole canvas" | Agent has already drawn `h.title_block` per SKILL §5a |
| C (chapter_divider) | Unclear — vertical centring math + accent placement seem inconsistent with each other | Result lands neither full-bleed nor under a title |

The patterns need explicit contracts:

1. **"Does this pattern own the whole slide, or does it sit under a `h.title_block`?"** Every pattern must declare one or the other in its docstring AND enforce it in code.
2. **"What body-area bounds is the pattern allowed to draw in?"** Patterns should use the grid (`h.grid()`) internally, not raw `Inches()` constants, so their bounds scale and they obey the same margins as agent-authored layouts.
3. **"How does the pattern behave when its content wraps?"** Every text-containing pattern must measure or estimate wrap, not assume single-line content. Korean glyph density makes this non-optional.

---

## Proposed QA discipline (before more patterns ship)

### A. Contract section in every pattern docstring

```python
def chapter_divider(slide, *, chapter_label, summary, ...):
    """Section opener. Massive chapter number / name in the centre-left,
    optional one-line summary tagline below.

    Owns the whole slide:
        Do NOT call `h.accent_stripe()` or `h.title_block()` before this
        pattern. This pattern draws its own accent treatment and chapter
        label as the slide's only top-level elements.

    Content limits:
        chapter_label: max ~12 chars at display.chapter size (52pt).
        summary:       max ~50 chars; wraps to 2 lines max.
    """
```

vs

```python
def hero_with_trailing_evidence(slide, *, headline, evidence, ...):
    """Thesis / takeaway slide. Massive headline upper-left ...

    Goes under a title_block:
        Call h.accent_stripe(slide, ...) and h.title_block(slide, ...)
        BEFORE this pattern. This pattern starts at y ≈ 1.8" (below the
        title bar).

    Content limits:
        headline: max ~60 chars; wraps to 3 lines.
        evidence: 2–4 items, each max ~80 chars (wraps to 2 lines).
    """
```

Without these contracts, the agent is guessing at every call.

### B. Per-pattern golden-image tests

For each pattern, the test suite renders a *worst-case content* example (Korean, max-length strings, edge counts) and saves the PNG. CI compares against a hand-approved golden image; any pixel-level regression fails the build.

The "worst cases" should include:
- Korean text at the upper length bound (twice the width of equivalent English chars)
- Edge counts (1, 2, max items)
- Slide-edge alignment (first/last marker, first/last grid cell)

Without golden images, defects ship silently — exactly what happened here.

### C. Stop-the-line on new patterns until the existing 10 pass

Don't add more patterns to the library until **the 10 already shipped pass their golden-image tests in worst-case Korean content**. The library's value depends on patterns being *usable as documented*; one bad pattern is worse than no pattern, because the agent burns time discovering and working around the bug.

### D. Pattern + caller integration tests

The export test suite should run a synthetic deck that uses each pattern once, on a single slide, with the agent's standard preamble (`h.accent_stripe` + `h.title_block`). Patterns that conflict with that preamble (Bug B) fail the test.

---

## Acceptance criteria

A future agent calling `p.<pattern_name>` with reasonable Korean content and the standard slide preamble should produce a slide that:

1. **Has no text overlap.** No two pieces of text occupy overlapping pixel regions.
2. **Stays within slide bounds.** No shape extends past the slide's left/right/top/bottom edges.
3. **Honours the visual contract in its own docstring.** A "chapter divider" feels like one; a "hero with trailing evidence" feels like one.
4. **Renders at the type sizes the type_scale defines** — no patterns silently using ad-hoc font sizes that override the deck concept.

---

## Cross-reference

| Todo | Status | What it does |
|---|---|---|
| 001 | Applied | Native-language prose nudges in SKILL |
| 002 | Applied | `render_mode="code"` + python-pptx authoring |
| 003 | Applied | Body-as-content-brief mindset |
| 004 §D, §G | Applied | Grid + design language manifesto |
| 004 §A | Applied | Per-slide PNG export + critique loop substrate |
| 004 §B | Applied (broken) | Pattern library — **THIS TODO documents its defects** |
| 004 §C, §E, §F | Pending | Iconography, type roles, reference corpus |

The progression now: 001–004 climbed the stack; 005 is *holding the library accountable* for the quality that 004 §B was supposed to deliver. Without 005, 004 §B is shipped-but-unusable, and the agent ends up hand-coding around the patterns every time.

---

## Suggested labels

`area:slide-patterns` · `area:qa` · `bug` · `priority:high` (blocks 004 §B's intended use) · `effort:S (fix bugs) + M (golden tests + contracts)`
