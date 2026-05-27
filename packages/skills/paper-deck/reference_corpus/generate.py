"""Regenerate the reference corpus PNGs (todo 004 §F).

Each entry is one canonical pattern + a curated content example, exported
through the same `export_deck_to_pptx` → soffice → PyMuPDF pipeline an
agent uses, so the references are pixel-identical to what the agent will
produce. The manifest.json records the pattern, content, do, and dont
for each example so the agent can grep for "show me a good flow_pipeline"
and Read the matching PNG.

Run:

    PYTHONPATH=apps/local-mcp python \\
        packages/skills/paper-deck/reference_corpus/generate.py

Requires soffice + pymupdf in scope (same as the export pipeline).
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

# Allow running from the repo root: PYTHONPATH=apps/local-mcp
_THIS = pathlib.Path(__file__).resolve()
_REPO = _THIS.parents[4]
sys.path.insert(0, str(_REPO / "apps" / "local-mcp"))

from co_scientist_local.backends.memory import InMemoryBackend
from co_scientist_local.state import State
from co_scientist_local.tools import deck_render, decks, papers
from PIL import Image


PREAMBLE = (
    "h.accent_stripe(slide, palette=palette, sw=sw)\n"
    "h.title_block(slide, title, palette=palette, fonts=fonts,\n"
    "              type_scale=type_scale, sw=sw, sh=sh)\n"
)


# Each entry: (filename, pattern, title, code, owns_slide, do, dont)
REFERENCES = [
    (
        "title_slide.png", "title_slide",
        "Multi-modal AI for plant breeding",
        "p.title_slide(slide,\n"
        "  title='Multi-modal AI for plant breeding',\n"
        "  subtitle='Yang Jae Kang · Korean Breeding Society 2026',\n"
        "  eyebrow='Lab seminar · 30 min',\n"
        "  palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh)\n",
        True,
        "Eyebrow (kicker label) above the big title, accent rule under it, "
        "subtitle (author + venue + date) on a third line. All centered, "
        "all vertically balanced. Use for the *opening* slide of a deck.",
        "Don't add body bullets or a closing tagline here — keep the slide "
        "to four short text lines max. The title IS the slide; whitespace "
        "carries the rest. For a centered emphasis MID-deck, use "
        "`chapter_divider` instead.",
    ),
    (
        "chapter_divider.png", "chapter_divider",
        "Section opener",
        "p.chapter_divider(slide, chapter_label='Era II',\n"
        "  summary='Data goes digital — but the breeder still works on paper.',\n"
        "  palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh)\n",
        True,
        "Massive 56pt+ chapter label vertically-centered, short accent rule "
        "*under* the label (visual anchor), italic summary as a tagline. "
        "Use between sections of a long talk so the audience feels the break.",
        "Don't repeat the deck-level accent stripe at the top — this pattern "
        "owns the canvas. Don't make the summary a paragraph; one tight "
        "sentence (≤ 50 chars) carries the rhythm.",
    ),
    (
        "title_and_body.png", "title_and_body",
        "MCP is the new pipeline",
        PREAMBLE + (
            "h.image_path  # noop; just keep the namespace happy if unused\n"
        ) + "p.title_and_body(slide, title=title,\n"
        "  body=['Two-week bespoke pipeline collapses to 30 seconds',\n"
        "        '500 accessions × 4 modalities in a single query',\n"
        "        'Provenance trail attached to every step'],\n"
        "  lead='The breeder talks to the data.',\n"
        "  palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh)\n",
        False,
        "Lead sentence (display italic) sets the thesis; bullets carry "
        "the evidence. Body lives in the LEFT 60% of the slide — the "
        "right 40% is intentional whitespace. The audience focuses; "
        "you don't fill space for the sake of filling it.",
        "Don't stretch the body to the full slide width. Don't write "
        "5+ bullets — split into two slides. Don't put a lead sentence "
        "longer than two lines.",
    ),
    (
        "title_two_content.png", "title_two_content",
        "In-house vs cloud MCP",
        PREAMBLE + (
            "p.title_two_content(slide, title=title,\n"
            "  left={'heading': 'In-house servers',\n"
            "        'bullets': ['Full control of data + cost',\n"
            "                    'No per-query fee',\n"
            "                    'Ops burden + slow to scale']},\n"
            "  right={'heading': 'Cloud MCP',\n"
            "         'bullets': ['Minutes to scale up or down',\n"
            "                     'No ops overhead',\n"
            "                     'Per-query cost + vendor lock-in']},\n"
            "  palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh)\n"
        ),
        False,
        "Mirrored panels, equally weighted — both sides get a small accent "
        "rule under their heading. Use for *which one for your case* "
        "comparisons where the panels aren't ordered (old/new) or "
        "evaluated (pro/con).",
        "Don't use this if one side is clearly preferred; that's "
        "`before_after_split` (muted left, accent right). Don't use this "
        "for pros/cons of competing options; that's `contrast_pair`.",
    ),
    (
        "hero_with_trailing_evidence.png", "hero_with_trailing_evidence",
        "Thesis with supporting evidence",
        PREAMBLE + (
            "p.hero_with_trailing_evidence(slide,\n"
            "  headline='Two weeks of bespoke pipeline collapse to 30 seconds.',\n"
            "  items=['500 accessions integrated across geno / pheno / image / env',\n"
            "         'Four modalities trained into a single joint embedding',\n"
            "         'Provenance trail attached to every query — auditable end-to-end'],\n"
            "  palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh)\n"
        ),
        False,
        "Use when the headline is *long* (≥ 3 wrapped lines) AND each "
        "evidence item is ≥ 50 chars (todo 008 §C). The asymmetric "
        "left-headline / right-numbered-column layout needs long "
        "content on both sides to earn its weight — short items "
        "leave a visible deadspace gap in the right column.",
        "Don't pick this for short tagged 3-item content (headline ≤ 2 "
        "lines, items < 50 chars) — `evidence_stack` packs the same "
        "shape into ~⅔ the vertical space without the asymmetric "
        "whitespace reservation. The pattern auto-tightens row height "
        "for short content as a rescue, but the layout-fit answer is "
        "to pick the other pattern.",
    ),
    (
        "metric_tile_row.png", "metric_tile_row",
        "Quantitative summary",
        PREAMBLE + (
            "p.metric_tile_row(slide, items=[\n"
            "  ('30', 'seconds per query', 's'),\n"
            "  ('500', 'accessions', None),\n"
            "  ('4', 'modalities', None),\n"
            "  ('150', 'fold speedup', '×'),\n"
            "], palette=palette, fonts=fonts, type_scale=type_scale,\n"
            "   sw=sw, sh=sh)\n"
        ),
        False,
        "3–5 big numbers (display type, accent color) with thin labels "
        "and optional units. Numbers carry the headline emotion; labels "
        "carry the meaning. Use for KPI / result slides where the "
        "magnitudes themselves are the message.",
        "Don't put 6+ tiles — the row gets cramped and each number "
        "loses weight. Don't write a long label; ≤ ~24 chars per tile, "
        "one line only.",
    ),
    (
        "evidence_stack.png", "evidence_stack",
        "Claim + tagged evidence",
        PREAMBLE + (
            "p.evidence_stack(slide,\n"
            "  claim='MCP queries are the new pipeline.',\n"
            "  items=[\n"
            "    {'tag': 'speed',    'body': '30 seconds vs two-week bespoke pipeline'},\n"
            "    {'tag': 'breadth',  'body': '500 accessions × 4 modalities in one query'},\n"
            "    {'tag': 'provenance', 'body': 'Trail attached to every step'},\n"
            "  ],\n"
            "  palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh)\n"
        ),
        False,
        "Claim on top in display type, tagged evidence below as stacked "
        "rows — each row is `[ TAG ]  body text`. Tag pills give the "
        "audience a named axis to remember each evidence by.",
        "Don't make tag labels long (≤ ~10 chars); they're meant to read "
        "as section names. Don't use this for unstructured bullets — "
        "those go in `title_and_body`.",
    ),
    (
        "flow_pipeline.png", "flow_pipeline",
        "Process pipeline",
        PREAMBLE + (
            "p.flow_pipeline(slide, items=[\n"
            "  {'tag': 'Collect',  'body': 'multi-modal accession data'},\n"
            "  {'tag': 'Curate',   'body': 'tidy + DOI-stamp every field'},\n"
            "  {'tag': 'Embed',    'body': 'train a single embedding'},\n"
            "  {'tag': 'Deploy',   'body': 'natural-language query interface'},\n"
            "], palette=palette, fonts=fonts, type_scale=type_scale,\n"
            "   sw=sw, sh=sh)\n"
        ),
        False,
        "Numbered cards (01 / 02 / 03 / 04) connected by right-arrows. "
        "Use for *sequential* processes — method, workflow, lifecycle. "
        "3–5 steps is the readable range.",
        "Don't use this for non-sequential lists (peers without an order) "
        "— that's `title_and_image_grid` or `card_grid`. Don't write a "
        "long body per step; the readability comes from short headings "
        "and quick descriptions.",
    ),
    (
        "before_after_split.png", "before_after_split",
        "Before vs after",
        PREAMBLE + (
            "p.before_after_split(slide,\n"
            "  before={'title': 'Bespoke pipeline',\n"
            "          'body': 'Two weeks per query. Every column hand-joined; every plot hand-coded.'},\n"
            "  after={'title': 'MCP query',\n"
            "         'body': '30 seconds per query. Natural language in, provenance trail out.'},\n"
            "  transition_label='150× faster',\n"
            "  palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh)\n"
        ),
        False,
        "Muted left panel (history / problem), accent-bordered right "
        "panel (solution / future). A single right-arrow + short label "
        "between. The asymmetric weight (left muted, right vibrant) "
        "carries the *direction of improvement* visually.",
        "Don't use this for equal-weight comparisons (`title_two_content` "
        "or `contrast_pair`). Don't put long paragraphs on either side — "
        "≤ ~140 chars each, 4 lines max.",
    ),
    (
        "figure_full.png", "figure_full",
        "Reference architecture (figure-only slide)",
        PREAMBLE + (
            "p.figure_full(slide, image_path=REF_TILE_BLUE,\n"
            "  caption='Fig 3 · LLM (사고) ↔ MCP (도구) ↔ Harness (운영). 자연어가 결정, MCP가 다리, harness가 운영.',\n"
            "  palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh)\n"
        ),
        False,
        "Image owns the **full grid** (rows 1–6 ≈ 85% of slide height). "
        "Caption tucks into the 0.6\" bottom-margin strip OUTSIDE the "
        "grid, in muted body italics. Wins back ~17% of figure area "
        "vs the old row_span=4 + caption-in-row-6 layout (todo 008 §A).",
        "Don't waste a grid row as 'breathing space' between figure "
        "and caption — the bottom margin already does that job. Don't "
        "let the caption run > 120 chars; 1 line preferred, 2 max.",
    ),
    (
        "title_and_image_grid.png", "title_and_image_grid",
        "Multi-image overview",
        PREAMBLE + (
            "p.title_and_image_grid(slide, title=title,\n"
            "  images=[{'path': REF_TILE_RED, 'caption': 'Era I — paper records'},\n"
            "          {'path': REF_TILE_BLUE, 'caption': 'Era II — data digital'},\n"
            "          {'path': REF_TILE_GREEN, 'caption': 'Era III — practice digital'},\n"
            "          {'path': REF_TILE_PURPLE, 'caption': 'Now — natural-language interface'}],\n"
            "  cols=2,\n"
            "  palette=palette, fonts=fonts, type_scale=type_scale, sw=sw, sh=sh)\n"
        ),
        False,
        "N images in a `cols`-column grid with italic captions below each. "
        "2×2 = comparison (peers, no order). N×1 row = progression "
        "(left → right reads as sequence). Captions stay in body type, "
        "never display.",
        "Don't use a grid for one hero image (`h.image_*` full-bleed). "
        "Don't pile in 6+ tiles — they get small and lose weight. Don't "
        "skip captions; the grid needs labeling to land.",
    ),
]


def _stage_tiles(tmp_dir: pathlib.Path) -> dict:
    """Solid-color PNG tiles standing in for real figures in the image-
    grid example (so the example renders without external assets)."""
    tiles = {
        "REF_TILE_RED":    (200, 90, 90),
        "REF_TILE_BLUE":   (90, 130, 180),
        "REF_TILE_GREEN":  (130, 170, 90),
        "REF_TILE_PURPLE": (160, 100, 170),
    }
    out = {}
    for name, color in tiles.items():
        p = tmp_dir / f"{name.lower()}.png"
        Image.new("RGB", (640, 480), color).save(p)
        out[name] = p
    return out


def main() -> int:
    corpus_dir = _THIS.parent
    tmp_dir = corpus_dir / "_tmp"
    tmp_dir.mkdir(exist_ok=True)
    tiles = _stage_tiles(tmp_dir)

    state = State(project_id="reference-corpus", owner_uid="me",
                  backend=InMemoryBackend())
    paper = papers.create_paper(state, title="Reference corpus")
    slug = paper["slug"]
    decks.create_deck(state, slug, title="corpus", deck_id="d")
    decks.update_deck(state, slug, "d", concept=(
        "Palette:\n"
        "  bg: #fafaf7  surface: #ffffff  text: #1a1a1a  accent: #b58900\n"
        "  muted: #6c757d  secondary: #2e7d32  highlight: #c0392b\n"
        "Typography:\n"
        "  display: Inter Bold  body: Inter Regular  mono: JetBrains Mono\n"
    ))

    # Substitute tile paths into the image-grid code
    manifest = {
        "generated_at": "2026-05-27",
        "generator": "packages/skills/paper-deck/reference_corpus/generate.py",
        "note": (
            "Each entry shows one canonical pattern with curated content + "
            "do/dont notes. Agent grep flow: read manifest.json, pick the "
            "pattern that fits the current slide's intent, Read the PNG to "
            "see what a good rendering looks like."
        ),
        "patterns": {},
    }
    for i, (fname, pattern, title, code, owns_slide, do, dont) in enumerate(REFERENCES, start=1):
        # Inline tile paths if needed
        for name, p in tiles.items():
            code = code.replace(name, repr(str(p)))
        decks.add_slide(
            state, slug, "d", slide_number=i, role="background",
            title=title, body="", notes="n", render_mode="code",
            code=code,
        )
        manifest["patterns"][pattern] = {
            "file": fname,
            "title": title,
            "owns_slide": owns_slide,
            "do": do,
            "dont": dont,
        }

    pptx_out = tmp_dir / "corpus.pptx"
    res = deck_render.export_deck_to_pptx(
        state, slug, "d", output_path=str(pptx_out),
    )
    if res["code_errors"]:
        print("code_errors:", res["code_errors"])
        return 1
    if res["pdf_skipped"]:
        print("PDF was skipped — soffice missing. Cannot render PNGs.")
        return 1

    # Move + rename PNGs from slide_001.png etc. → pattern-name.png
    for i, (fname, *_rest) in enumerate(REFERENCES, start=1):
        src = pathlib.Path(res["slide_pngs"][i - 1]["local_path"])
        dst = corpus_dir / fname
        shutil.copy(src, dst)
    (corpus_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # Tidy temp
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"wrote {len(REFERENCES)} reference slides + manifest.json to "
          f"{corpus_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
