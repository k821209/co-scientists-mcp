# 013 — Strip slide-level pattern prescription: §5a was still forcing "1 pattern per slide"

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Yang Jae Kang (chat), 2026-05-28.
**Status:** closed 2026-05-28 — §5a role→pattern table removed, Two-step selection → Three-step (trigger-table Step 0 added), bespoke proposal_dense source inlined as Example 0.

---

## TL;DR

After 012 stripped deck-level structural templating (§4 outline +
§3 Arc), the user reported the next deck *still* came out with
each slide locked to a single pattern call — just rotated across
the catalog. Inspected the user's exported deck
(`fieldnotebookbreedingmcp.pptx`, 21 slides):

| Slide | Role | Pattern that ran |
|---|---|---|
| s5 GWAS→GS→DL→LM | method | `flow_pipeline` (4 numbered cards + arrows) |
| s6 ERA I 한계 | question | `hero_with_trailing_evidence` |
| s8 ERA II 모달리티 | result | `metric_tile_row` |
| s10 ERA II 한계 | (claim) | `evidence_stack` |
| s14 Schema vs Tool | discussion | `title_two_content` |
| s16 HARNESS 4 | discussion | `card_grid` 2×2 |
| s19 OUTLOOK 6 숙제 | (summary) | `card_grid` 2×3 |

Every content slide = one pattern call. The rotation across the
catalog gave each slide a different *style*, but the *composition*
(1 pattern × 1 slide) was identical and the agent never composed
bespoke despite todos 009 / 011 / 012's nudges.

---

## Diagnosis — three prescriptors still in §5a after 012

12 cleaned §4 / §3 but left §5a alone. Three §5a artifacts kept
prescribing "1 pattern per slide":

1. **`role → recommended pattern` table** (the smoking gun):

   ```
   | Role | First-pick pattern | Backup |
   | method | flow_pipeline | before_after_split |
   | result | metric_tile_row / evidence_stack | zoom_in_callout |
   | discussion | contrast_pair / before_after_split | quadrant_map |
   | conclusion | hero_with_trailing_evidence | metric_tile_row |
   ```

   The agent reads outline → has a `role` per slide → consults
   this 1:1 table → emits a pattern call. Even after 011 v2 moved
   "Go bespoke when…" *above* the catalog, this table sits
   *below* the catalog — i.e. the LAST thing the agent reads
   before composing.

2. **"Pick a different pattern per consecutive slides"** — one
   line that bakes in "1 slide = 1 pattern" as the default. The
   "rotation" advice is only well-defined under that assumption.

3. **Both worked examples in §5a were pattern-driven.** Example 1
   = `card_grid` + `pull_quote`. Example 2 = `bullet_list` +
   `image_figure`. Neither showed a multi-region bespoke
   composition; the `proposal_dense` exemplar existed only as a
   PNG outside §5a, so an agent grep-reading §5a never sees what
   bespoke code looks like in practice.

The combined effect: §5a's flow read as "decide role → look up
pattern → write 5 lines → next slide", with the "Go bespoke" table
treated as an exception note. Exactly what the deck shows.

---

## What changed

1. **`role → recommended pattern` table deleted** from §5a. The
   slot now carries an explicit anti-mapping note:

   > There is intentionally **no "role → pattern" mapping table**
   > here. Mapping `method → flow_pipeline` / `result → metric_tile_row`
   > / `discussion → contrast_pair` produces decks where every
   > slide is one pattern call and the composition repeats no
   > matter how the content varies. `role` is a slide *label*,
   > not a design recipe.

2. **"Pick a different pattern per consecutive slides" rewritten**:

   > **Rotation is not a goal.** You do NOT need a "different
   > pattern per consecutive slide" — most consecutive slides
   > should both be bespoke, with different *compositions* (not
   > different patterns) appropriate to their content. If three
   > slides in a row each call a different pattern, you've
   > turned the deck into a pattern menu demo.

3. **"Two-step selection" → "Three-step selection".** Added Step
   0: re-run the trigger-table check; if anything matches, skip
   pattern selection entirely. Step 1 and Step 2 now both lead
   with "Only if no trigger matched".

4. **"Example 0 — bespoke composition" inlined in §5a body**
   *before* Examples 1 & 2. The full `proposal_dense` source
   (~80 lines of `h.text` + `slide.shapes.add_shape`, ~50 final
   shapes, NO pattern call) lives in §5a body now. An agent
   reading §5a top-to-bottom sees the bespoke shape *first*,
   then the two pattern examples as narrow shortcuts.

---

## Why this should actually move the needle

The agent's compose-time behaviour is whatever §5a says at the
point of "now write the code". After 013:

- The trigger table is at the *top* of §5a (from 011 v2).
- The Three-step selection's Step 0 says "trigger-table check FIRST".
- The role→pattern table is gone — there's no recipe to fall back on.
- The first worked example in §5a is bespoke, not a pattern call.
- The rotation advice no longer assumes 1-pattern-per-slide.

If the next deck still produces a pattern call per slide, the
prescription is coming from somewhere outside SKILL.md (a memory
entry, CLAUDE.md, agent training prior) — track it in a follow-up.

---

## Acceptance criteria

A future deck on a substantial paper should:

1. Have **at most 30%** of content slides driven by a single
   `p.*` pattern call. The rest compose multi-region bespoke
   (or are intentional pattern fits — figure_full, gantt_chart,
   chapter_divider).
2. NOT show role→pattern 1:1 mapping in the export — i.e. two
   `method` slides shouldn't both be `flow_pipeline`; two
   `result` slides shouldn't both be `metric_tile_row`.
3. Have ≥ 1 slide that composes multiple regions (e.g. card row
   + pipeline row + metric line in one slide), not stacked
   pattern calls.

---

## Cross-reference

| Todo | Fixed | Didn't fix |
|---|---|---|
| 009 | Pattern ceiling (capability) | Default reach-for-pattern |
| 011 v1 | Visual prior + critique density bar | Slide-level prescription |
| 011 v2 | "Go bespoke when…" moved above catalog | role→pattern still below catalog |
| 012 | Deck-level structure (§4 + §3) | Slide-level pattern selection (§5a) |
| **013** | **§5a role→pattern table + rotation framing + inline bespoke example** | (external priors if any) |
