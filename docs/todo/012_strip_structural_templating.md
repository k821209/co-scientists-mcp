# 012 — Strip structural templating: agent inherits same skeleton + eyebrows every deck

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Yang Jae Kang (chat), 2026-05-28.
**Status:** closed 2026-05-28 — §4 outline + §3 Arc reframed; corpus exemplars labeled as density references, not content templates.

---

## TL;DR

User reported: even after todo 011's follow-up (inverted SKILL order,
shape_count manifest, density-25 critique), a fresh-session deck
still came out with the **same structure and same content** as the
previous deck. Style varied, composition didn't.

Diagnosis: I'd been fixing per-slide design ceilings but the
*deck-level structure* was still being prescribed by SKILL:

1. **§4 had a "Standard role sequence" table** listing 8 roles with
   "always" / "always" / "always" markers and "Typical role count"
   columns. Every deck the agent built had the same 8-slide skeleton.
2. **§3 concept template hardcoded an Arc**: "problem → setup →
   result → implications → questions". The agent saw it and used it
   verbatim across decks.
3. **Corpus exemplars carry specific eyebrows** (HOW · 추진 방법 /
   WHO · 사업 수행 능력 / WHEN · 7개월 병렬 운영) which trained the
   agent to use WHO/WHY/HOW/WHEN vocabulary on every deck regardless
   of the talk type.
4. **Worked-example callout said "mirror the structure"** which
   meant "copy proposal_dense's 3-platform-card layout even if your
   paper has nothing to do with platforms".

Capability + per-slide density gains didn't matter — the *outline*
was being copied.

---

## What changed

1. **§4 rewritten as descriptive, not prescriptive.** Header now leads
   with: "Derive the outline from YOUR paper, not from a template."
   The "Standard role sequence" table is gone. Replaced with **five
   example deck shapes** (lab seminar / conference talk / grant
   pitch / departmental review / one-figure deep-dive) and a list
   of available roles to remix freely. Each example explicitly
   says "this is illustrative, not canonical".

2. **§3 Arc reframed.** The concept template's Arc line used to be a
   hardcoded recipe ("problem → setup → result → implications →
   questions"). Now shows three example arcs as comments and a
   placeholder `[the arc that fits THIS paper / talk]` for the agent
   to fill in based on the paper.

3. **Worked-examples callout rewritten.** Was "Mirror the structure;
   adapt the content." → now "Mirror the **technique**, NOT the
   **content**. The corpus is a *density gym*, not a content shopping
   mall." Plus explicit: "if your paper has no platform comparison,
   your slide has no platform comparison". Same for eyebrow
   vocabulary: WHO/WHY/HOW/WHEN was one team's convention, not the
   canonical eyebrow set.

---

## Why this should actually move the needle this time

Todo 009 / 010 / 011 fixed per-slide ceiling and per-slide design
defaults. But the deck-level skeleton was still pinned. The agent was
hitting "what slides should this deck have" → SKILL §4 → "title /
outline / background / method / result / discussion / conclusion /
qa, with these counts" → identical outline across decks.

This todo unpins the skeleton. The agent now hits §4 → "derive from
YOUR paper, here are 5 different shapes a deck could take" → outline
varies with paper.

---

## Acceptance criteria

A future deck on a wholly different paper should:
1. Have a different role sequence than previous decks (NOT the fixed
   8-slide skeleton).
2. Use eyebrows derived from the paper's actual sections, not the
   WHO/WHY/HOW/WHEN proposal-pitch vocabulary.
3. Skip irrelevant sections (a single-paper lab seminar shouldn't
   have a personnel page; a methodology talk doesn't need a Gantt).

If a future deck still mirrors the prior deck's outline, the
prescription must be coming from somewhere else (paper-deck SKILL's
hard-rules section? a memory entry? a Claude.md file?) — track it
down in the follow-up.

---

## Cross-reference

| Todo | Fixed | Didn't fix |
|---|---|---|
| 004–008 | Per-slide patterns, helpers, density math | Deck-level structure |
| 009 | Pattern ceiling, deck chrome, gantt | Deck-level structure |
| 010 | Defer mode decision | Deck-level structure |
| 011 (v1+v2) | Visual prior, "go bespoke" placement, density bar | Deck-level structure |
| **012** | **Deck-level structure prescription stripped from §4 + §3** | (deeper memory / Claude.md sources, if any) |
