# 007 — Pattern + helper API consistency: agent burns turns re-discovering signatures

> Filed by user as "006"; renumbered to 007 in this repo because
> `006_slide_typology_and_layout_effects.md` was already taken.

**Audience:** co-scientist-local MCP / Claude Code harness dev team.
**Filed by:** Yang Jae Kang, project `ai-breeding`, 2026-05-27.
**Status:** Tier 1 + 2 + 3 all shipped 2026-05-27.

## Resolution log

- **2026-05-27** — Tier 1 shipped, covering 6 of the 10 concrete defects + 3 of the 4 axis-level issues:
  - **#1 / Axis-roles** — `_VALID_ROLES` extended with `hook`, `thesis`, `section`, `figure`, `image`, `content`. The 9 canonical roles still preferred; the extension just accepts common deck-vocabulary terms without error.
  - **#6 / Axis 4** — `_theme_colors` now exposes all 7 palette keys (`accent`, `background`, `foreground`, `surface`, `muted`, `secondary`, `highlight`). Concept's `Palette:` block can declare any; missing keys get computed defaults (`muted` = 45/55 fg-bg blend; `secondary` / `highlight` = accent shifted ±0.18 toward black/white). All 7 reach the snippet's `palette` dict as RGBColor.
  - **#7 / Axis 1** — `h.image_path` / `h.image_region` / `h.image_figure` accept `slide` as the first positional arg (consistent with every other helper / pattern). Back-compat: omit slide and the closure-bound slide is used, so existing snippets keep working.
  - **#10** — `before_after_split` title/body coordinate overlap fixed: body now starts at `top + Pt(20) + title_h + Pt(8)` (after the title box ends) instead of `top + Pt(title_pt * 1.7)` (which overlapped the bottom of the title by ~15pt).
  - **Axis 3** — `Grid.cell()` returns a `Cell` namedtuple with both tuple-unpacking AND `.left / .top / .width / .height` attribute access. Existing `left, top, w, h = g.cell(...)` callers unchanged.
  - **§D (h.text)** — new `h.text(slide, content, *, left, top, width, height, palette, size_pt=20, color=None, ...)` one-call textbox helper. Drops the `add_textbox + text_frame + paragraph + run + font` ceremony to one line; autofit-shrinks Korean-aware by default.
  - paper-deck SKILL §3 concept template gains `muted` / `secondary` / `highlight` rows; §5a helper catalog gains `h.text` row + slide-optional notes on image helpers + Cell namedtuple + 7-key palette explainer.
- **2026-05-27 (later that day)** — Tier 2 shipped. `_resolve_items(name, items, **legacy_aliases)` resolves the canonical `items=` kwarg against legacy names — raises `TypeError` loudly if both are passed (catches partial renames). `_item_get(item, *keys)` walks alias keys inside dict items so the canonical `{tag, body}` shape works alongside historical `{title, body}` / `{tag, note}` / `{value, label, unit}` forms.
  Updated patterns:
  - `hero_with_trailing_evidence(items=...)` — accepts `list[str]` OR `list[{body, ...}]`. Legacy alias: `evidence=`.
  - `evidence_stack(items=...)` — `list[{tag, body|note|text}]`. Legacy: `evidence=`.
  - `flow_pipeline(items=...)` — `list[{tag|title, body|note|text}]`. Legacy: `steps=`.
  - `metric_tile_row(items=...)` — `list[tuple OR {value|tag, label|body, unit?}]`. Legacy: `tiles=`.
  - `numbered_milestone_arc(items=...)` — `list[{tag, body|note}]`. Legacy: `milestones=`.
  - `card_grid` already used `items=`; now also accepts `{tag, body}` alongside `{title, body}`.
  4 new tests cover `items` canonical use, dict-shape detection on `metric_tile_row`, the both-passed `TypeError`, and `body`/`note` alias on `numbered_milestone_arc`. 387 total passing.

- **2026-05-27 (Tier 3)** — paper-deck SKILL §5a gains a single grep-able "Quick reference — every callable at a glance" code block listing every helper + pattern with their canonical signature + contract / item shape / legacy aliases in one place. The agent now greps SKILL for `h.image_figure` or `p.evidence_stack` instead of grepping the source on first use.

6 new tests, 383 total — covers extended roles, Cell namedtuple unpacking + attribute access, `h.text` one-call shape, 7-key palette in exec namespace, image_figure slide-first / closure forms, theme_colors explicit override of optional keys.
**Related:** [005 — Pattern library quality](./005_pattern_library_quality.md) (this is the *next layer* of the same complaint — 005 catalogued visual defects, 006 catalogues API-shape defects).

---

## TL;DR

Building a 20-slide deck from scratch this session burned **8 export cycles on signature-discovery errors** before any visual critique could begin. The patterns/helpers each have *plausible but inconsistent* signatures: some take dicts, some take tuples; some take `items`, some take `evidence`, some take `tiles`, some take `steps`; some take `slide` first, some don't; `grid.cell()` returns a tuple while pull_quote / image_region read dict-style. The agent has no way to learn the conventions short of reading the source — and even after reading once, the next pattern surprises again. The library is *usable*, but the cost is paid in trial-and-error per pattern per session.

This is a **DX problem**, not a render-quality problem (005 covers that). The fix is a small consistency pass + a single living-reference doc the agent can grep.

---

## Concrete defects from this session (all in one 20-slide build)

Each row is one round-trip the agent had to spend on signature discovery:

| # | Symptom (export error) | What I had to learn |
|---|---|---|
| 1 | `invalid role: 'hook'` | Valid roles are: `title`, `outline`, `background`, `method`, `result`, `discussion`, `conclusion`, `qa`, `custom` (only documented in `_VALID_ROLES` in `decks.py`). No `hook`, `thesis`, `figure`, `section`, `image`, `content` — common deck vocabulary. |
| 2 | `title_slide() got an unexpected keyword argument 'presenter'` | `title_slide(title, subtitle, eyebrow)` only. No `presenter` slot — must pack author into `subtitle`. |
| 3 | `'dict' object has no attribute 'strip'` | `hero_with_trailing_evidence.evidence: list[str]` — strings, NOT `{tag, body}` dicts (contrast: `evidence_stack.evidence: list[dict]` uses dicts). |
| 4 | `title_block() missing 1 required keyword-only argument: 'sh'` | `title_block` needs both `sw` AND `sh`. (`accent_stripe` needs only `sw`.) |
| 5 | `col must be 1..12, got 0` | `g.cell()` is **1-indexed**, not 0-indexed. Standard CSS / numpy / pandas / D3 all use 0-indexed. |
| 6 | `KeyError: 'muted'` | `palette` exposes only `accent`, `background`, `foreground`. Concept's `muted: #64748B`, `secondary`, `highlight`, `text` keys are **silently dropped** at parse time. Agent has to hardcode `RGBColor(0x64, 0x74, 0x8B)` for a muted gray. |
| 7 | `_image_from_figure() got multiple values for argument 'figure_number'` | `h.image_figure(figure_number, *, left, top, width, height)` — call as `h.image_figure(1, ...)`. Do NOT pass `slide` (it's pre-bound in the namespace). Contrast: `h.image_path(path, left=, ...)` (no slide), `h.image_region("r1", left=, ...)` (no slide). But `h.pull_quote(slide, text, ...)`, `h.accent_stripe(slide, ...)`, `h.title_block(slide, text, ...)` DO take slide. **Inconsistent.** |
| 8 | `evidence_stack() got an unexpected keyword argument 'items'` | `evidence_stack(*, claim, evidence: list[dict])`. Same shape `[{"tag":, "body":}]` as flow_pipeline.steps but different parameter name. |
| 9 | `metric_tile_row` rendered LITERAL placeholders ("label", "value", "unit") | `tiles: list[tuple]` — pass `(value, label)` or `(value, label, unit)`. The only pattern that takes tuples; every neighbour takes dicts. |
| 10 | `before_after_split` rendered with title and body overlapping | Pattern positions title at `top=Pt(20), height=Pt(title_pt*1.5)` ≈ ends at 56pt, body at `top + Pt(title_pt*1.7)` ≈ starts at 41pt → 15pt overlap built into the math. Not a caller bug — pattern bug. |

Plus three "secondary surprises" that didn't error but cost time to figure out:

- `g.cell(...)` returns a **tuple** `(left, top, w, h)`, but my reflex was `cell["left"]` because the helpers I'd already used (`h.image_region(left=, top=, width=, height=)`) prefer keyword unpacking.
- `pull_quote` does NOT accept `attribution`. The pattern is "bar + text" only — attribution has to be a separate `add_textbox` call.
- No `h.emit_text(...)`. The patterns use a private `_emit_text` internally; the agent has to fall back to raw `slide.shapes.add_textbox(...)` boilerplate (5+ lines for one caption).

---

## Total cost in this session

- **20 slides shipped**
- **8 distinct API errors** caught at export time (above)
- **~12 export cycles** burned just to get all 20 slides to compile (before any visual critique)
- Every error cost 1 export round-trip + 1 source read + 1 patch attempt

In the ideal world, the first export of 20 slides would have ~0 signature errors and the agent could spend the cycles on *design critique*, which is what the deck actually needs.

---

## Pattern of the defects (the meta-issue)

The library evolved organically — each helper / pattern was added with the signature that felt natural at the time. The agent has no schema to learn from; it has to *read each function* on first use. Three concrete inconsistencies dominate:

### Axis 1 — `slide` is sometimes the first positional arg, sometimes pre-bound

| Function | Takes `slide` positional? |
|---|---|
| `h.accent_stripe(slide, *, palette, sw)` | yes |
| `h.title_block(slide, text, *, palette, ...)` | yes |
| `h.pull_quote(slide, text, *, palette, ...)` | yes |
| `h.bullet_list(slide, items, *, ...)` | yes |
| `h.card_grid(slide, items, *, ...)` | yes |
| `h.image_path(path, *, left, top, ...)` | **no** (slide bound at namespace build) |
| `h.image_region(region_id, *, left, top, ...)` | **no** |
| `h.image_figure(figure_number, *, left, top, ...)` | **no** |
| `p.<any_pattern>(slide, *, ...)` | yes |

The image helpers are the outlier. From the agent's perspective, this is the most disorienting because the obvious-feeling call `h.image_figure(slide, figure_number=1, ...)` parses but binds `slide` to `figure_number` and then `figure_number=1` collides — producing an opaque "got multiple values" error.

**Suggested fix:** make `slide` the first positional arg for *every* image helper too (it's already in scope; the binding is purely a closure detail). Or document this prominently in §5a of the SKILL.

### Axis 2 — list-of-items parameter name and item shape

| Function | Param name | Item shape |
|---|---|---|
| `h.bullet_list` | `items` | `list[str]` |
| `h.card_grid` | `items` | `list[{title, body}]` |
| `p.flow_pipeline` | `steps` | `list[{tag, body}]` |
| `p.evidence_stack` | `evidence` | `list[{tag, body}]` |
| `p.hero_with_trailing_evidence` | `evidence` | `list[str]` ← contradicts evidence_stack |
| `p.metric_tile_row` | `tiles` | `list[tuple]` ← contradicts everyone |
| `p.numbered_milestone_arc` | `milestones` | `list[{tag, note}]` ← yet another field-name pair |
| `p.contrast_pair` | `left_item` / `right_item` | `{title, pros, cons}` |
| `p.before_after_split` | `before` / `after` | `{title, body}` |

This is the spreadsheet that should not exist. Two patterns named `evidence` accept *different* shapes for `evidence`. `before_after_split.before` and `contrast_pair.left_item` are the same idea with different keys and different sub-shapes. `flow_pipeline.steps` and `evidence_stack.evidence` are nearly identical structurally but named differently.

**Suggested fix:** canonical parameter name `items` everywhere a list of dicts is expected. Canonical dict shape `{tag, body}` everywhere a tagged item is expected. Patterns that need pros/cons can use `{tag, body, pros, cons}` (extra fields ignored by patterns that don't need them).

### Axis 3 — return shapes for measurement helpers

`g.cell(col, span, row, row_span)` returns a 4-tuple. Most code-snippet authors will reach for `cell["left"]` or `cell.left` because that's the modern convention. The agent does too. Then it spends 1 round-trip learning to unpack.

**Suggested fix:** return a small `Cell` dataclass with `.left`, `.top`, `.width`, `.height` attributes that *also* iterates as a 4-tuple for tuple-unpacking. Both forms work; both are obvious.

### Axis 4 — palette key surface

The deck concept's `Palette:` block carries seven keys (`bg`, `surface`, `text`, `accent`, `secondary`, `highlight`, `muted`). The runtime exposes only three (`accent`, `background`, `foreground`). The other four silently disappear into `_parse_concept` and are unrecoverable from the snippet.

Two consequences:
1. The "max 3 colors per slide" design rule in the concept depends on `muted` and `highlight` being available. They're not.
2. The agent must hardcode hex literals (`RGBColor(0x64, 0x74, 0x8B)`) every time it needs a muted caption color, defeating the point of having a deck-wide palette.

**Suggested fix:** expose the full palette dict as the concept defines it (with sensible computed defaults for missing keys — `muted = 65% blend of foreground+background`, etc.). Same with typography — currently only `body`/`display`/`mono`; concept defines more.

---

## Proposed fixes (dev team picks)

### A. Consistency pass on patterns — *highest impact*

Single PR that:
1. Renames every list-of-dicts parameter to `items` (with backwards-compat alias for one release).
2. Settles `{tag, body}` as the canonical item shape; `metric_tile_row` accepts both tuple and dict.
3. Makes `h.image_*` accept `slide` as the first positional arg (closure still works; just unwrap from the namespace).
4. Adds an attribute view to `Grid.cell()` return so both unpacking and `.left` work.

Effort: small-medium. Most patterns are 30–80 lines each. The consistency change is mechanical.

### B. Single-page API reference in the SKILL — *cheapest, ship-this-week*

A short table in `paper-deck/SKILL.md §5a` listing every helper + pattern with:
- exact signature (name, required kwargs, return)
- one-line "what it does"
- one-line "do not call before/after X" contract

So the agent can grep the SKILL instead of grepping the source on every first call. Use the existing pattern docstrings as the source of truth — just collect them in one table.

Effort: small. The information already exists; it's just scattered across 14 docstrings.

### C. Expose the full palette + type_scale to snippets

Today the concept's `Palette:` block has 7 keys but only 3 reach the snippet. Pass them all through (with computed fallbacks for missing ones). Same for `Typography:`.

Effort: small. One change in `_theme_colors` / `_parse_concept`. Lets the deck's design language actually reach the snippet.

### D. A `h.text(...)` convenience helper

Wrap the 5-line `add_textbox` + `text_frame` + `paragraph` + `run` + `font` boilerplate into one call:

```python
h.text(slide, "caption text",
       left=cl, top=ct, width=cw, height=Pt(40),
       size_pt=12, color=palette.get("muted"), italic=True)
```

Every caption / footer / small label needs this; today the snippet repeats the boilerplate 3–5 times per deck.

Effort: trivial. Just expose `_emit_text` (or a sanitised wrapper) on the `h` namespace.

### E. Pattern unit-tests with `pytest.raises` on bad input

For each pattern, a one-liner test that calls it with the *natural-but-wrong* shape (the shape the agent's intuition would reach for) and asserts a *helpful* error message — not `TypeError: got multiple values for figure_number` but `ValueError: image_figure expects (figure_number, ...); slide is pre-bound — drop it from your call`.

Effort: medium. But catches the next 8 agents-from-the-future at zero round-trips each.

---

## Acceptance criteria

After fixes land, a future agent building a fresh 20-slide deck should:

1. **Get every pattern signature right on the first try**, having read only the SKILL §5a table — no source-diving needed.
2. **Use `palette["muted"]` without hardcoding hex** — every key the concept declares is available in the snippet.
3. **Spend < 2 export cycles on signature errors** for a 20-slide deck (vs ~8 today).
4. **Find a single text helper** for one-line captions instead of 5-line `add_textbox` ceremony.

A reviewer reading a snippet should not be able to tell from style alone which helpers take `slide` and which don't, which params want dicts vs tuples, which use `evidence` vs `items` — because they'll all be the same.

---

## Cross-reference

| Todo | Layer | Status |
|---|---|---|
| 001 | Prose (translation-ese) | Applied |
| 002 | Rich rendering (markdown → shape vocabulary) | Applied |
| 003 | Content-first design | Applied |
| 004 §A/B/D/G | Critique loop + grid + manifesto | Applied |
| 004 §C/E/F | Iconography, type roles, ref corpus | Pending |
| 005 | Pattern visual quality (overlap / wrap / contracts) | Open |
| **006** | **Pattern + helper API consistency** | **This todo** |

004 gave the agent design *intent*. 005 caught the patterns producing wrong *output*. 006 catches the patterns producing right output only *after* the agent has paid the discovery tax. Together they describe a library that works once you've been burned by it; the goal is a library that works the first time.

---

## Suggested labels

`area:slide-patterns` · `area:helpers` · `area:dx` · `priority:high` (every code-mode session pays this tax) · `effort:S (SKILL table + palette expose) + M (consistency pass + unit tests)`
