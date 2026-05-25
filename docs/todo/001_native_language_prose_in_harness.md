# 001 — Native-language prose in the harness (translation-ese problem)

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Yang Jae Kang, project `ai-breeding`, 2026-05-25.
**Status:** open · proposal.

---

## TL;DR

When the harness generates Korean (or any non-English) content for a user, it consistently produces *translation-ese* — text that reads as if mechanically translated from English, not written natively in the target language. The user has to spot it and ask for a rewrite pass every time. This is a harness-level concern that should be solved once, not re-solved per project / per session via project memory.

---

## Concrete observation

While building a 23-slide Korean presentation for a domestic plant-breeding society (project: `ai-breeding`, deck: `multi-modal-agricultural-ai-...`), the harness produced slide bodies like:

```
- **MCP 기반 워크플로** — 자연어 질문 한 번 → **약 30초** + 자동 provenance
- 손코딩 shortcut이 아니라 *재현 가능한 인프라*
- 모든 step이 plan에 *provenance trail*로 동봉됨
```

A Korean-native reader immediately recognises this as English-derived: em-dash chains, English nouns with Korean particles, English-style "X — Y → Z" parallel structure, mixed sentence endings. The user reported it with *"왜 슬라이드글이 전부 번역체 처럼 이상하냐 ㅋ"*. A manual rewrite pass produced a satisfactory native-Korean version.

The rewrite was not subtle — *every* text slide needed work, plus several titles and figure captions.

---

## Why this belongs in the harness, not per project

The user can — and did — record the natural-Korean rules into project memory (cloud) and local feedback memory. That works for *this* project. But:

1. **The pattern repeats across projects.** Any Korean (or Japanese, or French, …) audience will hit the same problem. Recording the rules N times for N projects is not scalable.

2. **The user shouldn't have to be the diagnostician.** They are paying for a system that produces presentation-grade prose; spotting translation-ese should not be their job. A breeder-PI is not a copy-editor.

3. **The rules are general, not project-specific.** "Avoid em-dash overuse," "don't directly translate English clause structures," "keep field-standard English abbreviations but translate everyday nouns" — these apply equally to a wheat-breeding talk, a soybean-genomics paper, or a chemistry lecture.

4. **Memory recall is post-hoc.** Project memory and local feedback memory are loaded at session start, but they don't stop the harness from drafting in English patterns first and having the rewrite be a *follow-up*. By then the user has already seen the bad draft.

---

## Proposed approaches (dev team picks 1+, not exclusive)

### A. Skill-level prompt injection — *cheapest, ship-this-week*

`/paper-deck`, `/paper-writing`, `/paper-revision`, `/paper-export`, and any other prose-generating skill should include, in their SKILL.md, a section like:

> ### Non-English audiences
> If `deck.audience`, `paper.audience`, or any explicit signal indicates a target audience whose primary language is not English:
> 1. **Default to native language flow** of that language. Do not write English first and translate.
> 2. **Keep English only for field-standard abbreviations** (e.g. GWAS, BLUP, MCP, API, F4, accession). Translate everyday English nouns to the target language.
> 3. **Use the target language's native punctuation conventions.** In Korean: prefer colons and natural sentence breaks over em-dashes.
> 4. **Run a final pass with this question**: "Could a native speaker mentally reverse-translate this to English word-for-word?" If yes, rewrite.

That single block, dropped into the relevant skills, would catch ~90% of the problem.

### B. Concept-level language hint

The deck concept (and analogous fields on paper / poster / report) already carries audience text in free form. Add an explicit `language` or `target_locale` field (or codify the convention that the concept block names the language). The export and slide-generation paths read it and condition their prose generation accordingly.

```yaml
concept:
  audience: 한국 육종학회 연구자
  language: ko          # NEW: explicit locale tag
  palette: …
  typography: …
```

This makes the language signal *programmatic* rather than buried in an audience description.

### C. Project-guide nudge

`mcp__co_scientist__project_guide()` (called on every session start) could include a short paragraph at the top:

> When generating prose for a non-English audience, default to native flow of the target language. Translation-ese (English patterns rendered with target-language morphology) is a recurring user complaint and should be self-checked before delivery.

This is the lowest-effort intervention and would reach every session.

### D. Memory-level pre-load of language rules

The harness already loads project memory at session start. Ship a small library of *language-specific writing-style memos* — Korean, Japanese, Chinese, Spanish, French — that get auto-included in the context when the project memory or deck concept signals that locale.

Effectively: "the harness ships with translation-ese-prevention rules for the top N languages."

### E. Lightweight post-generation lint

Run a cheap heuristic over generated Korean prose:
- count em-dashes per slide; flag > 1
- count English-word + Korean-particle pairs in body bullets; flag a threshold
- check sentence-ending consistency (한다 vs 합니다 mix)

Flag offenders before showing the slide to the user, ideally in the same turn as generation. This wouldn't catch nuance, but it would catch the worst cases.

---

## Acceptance criteria

When a future user runs `/paper-deck <slug> "Korean audience" 30` on a fresh project:

1. The *first* draft of every slide should pass a Korean native-speaker read without requiring a rewrite pass.
2. Em-dash count should be reasonable (≤ 1 per slide for Korean).
3. Korean sentence endings should be consistent within a single slide.
4. Common English words that have natural Korean equivalents (지름길, 과정, 공개, 대체, etc.) should be in Korean. Field-standard English abbreviations (GWAS, BLUP, …) should be in English.
5. The user should not have to memorise project memory rules to get this behaviour — it should be the default.

---

## References

- This project's `MEMORY` tab in dashboard — the per-project version of these rules was filed there 2026-05-25.
- Local feedback memory: `~/.claude/projects/-Users-yangjaekang-works-gnu-rnd-ai_breeding/memory/feedback_korean_writing_style.md`.
- The slide-by-slide rewrite that produced the natural-Korean version is preserved in the deck's session history.

---

## Suggested labels (for dev tracker)

`skill:paper-deck` · `skill:paper-writing` · `area:i18n` · `priority:medium` · `effort:S–M` (depending on which approach is picked)
