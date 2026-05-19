"""Deck rendering: placeholder resolution + slide rendering modes.

PPTX export is covered by a smoke test only — requires python-pptx
optional dep.
"""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import deck_render, decks, figures, papers


def _setup(state):
    papers.create_paper(state, title="My paper")
    decks.create_deck(state, "my-paper", title="d", deck_id="d")
    return "my-paper"


# ─── placeholder resolution ──────────────────────────────────────────────


def test_parse_concept_extracts_pairs():
    concept = """
    Palette:
      bg: #fafaf7  surface: #ffffff  text: #1a1a1a  accent: #b58900
    Typography:
      display: Inter Bold
      body: Inter Regular
    """
    kv = deck_render._parse_concept(concept)
    assert kv["accent"] == "#b58900"
    assert kv["bg"] == "#fafaf7"
    assert kv["display"] == "Inter Bold"
    assert kv["body"] == "Inter Regular"


def test_resolve_replaces_known_placeholders():
    concept = "accent: #b58900"
    text = "Use {accent} for the trend line"
    assert deck_render.resolve_placeholders(text, concept) == "Use #b58900 for the trend line"


def test_resolve_leaves_unknown_placeholders_visible():
    """Unknown placeholders stay literal so the bug is obvious."""
    out = deck_render.resolve_placeholders("Hello {unknown}", "accent: red")
    assert "{unknown}" in out


def test_resolve_none_concept_returns_text_unchanged():
    assert deck_render.resolve_placeholders("hi {x}", None) == "hi {x}"


def test_resolve_no_braces_returns_unchanged():
    assert deck_render.resolve_placeholders("no placeholders", "x: y") == "no placeholders"


# ─── render_slide modes ──────────────────────────────────────────────────


def test_render_paper_figure_copies_blob(state, tmp_path):
    slug = _setup(state)
    # Stage a figure with a real PNG blob
    png_bytes = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    p = tmp_path / "fig1.png"
    p.write_bytes(png_bytes)
    figures.add_figure(
        state, slug, figure_number=1, title="Figure 1",
        caption="x", local_path=str(p),
    )
    s = decks.add_slide(
        state, slug, "d", slide_number=1, role="result", title="Fig 1 slide",
        notes="my notes", render_mode="paper-figure", figure_number=1,
    )
    r = deck_render.render_slide(state, slug, "d", s["id"])
    assert r["size_bytes"] == len(png_bytes)
    assert r["mode"] == "paper-figure"
    # Verify slide doc was updated
    updated = decks.list_slides(state, slug, "d")[0]
    assert updated["image_blob_path"]
    assert updated["status"] == "rendered"


def test_render_ai_image_uses_image_gen(state, monkeypatch):
    slug = _setup(state)
    decks.update_deck(state, slug, "d", concept="accent: #f00")
    s = decks.add_slide(
        state, slug, "d", slide_number=1, role="background",
        title="cover", notes="hi",
        prompt="Use {accent} on the cover",
        render_mode="ai-image",
    )

    class FakeGen:
        captured: dict = {}
        def generate(self, *, prompt, aspect_ratio="1:1", model="gpt-image-2"):
            FakeGen.captured["prompt"] = prompt
            FakeGen.captured["aspect_ratio"] = aspect_ratio
            return b"fake-png-bytes"

    state.image_gen = FakeGen()
    r = deck_render.render_slide(state, slug, "d", s["id"])
    assert r["mode"] == "ai-image"
    assert FakeGen.captured["prompt"] == "Use #f00 on the cover"
    assert FakeGen.captured["aspect_ratio"] == "16:9"


def test_render_code_shape_requires_local_path(state, tmp_path):
    slug = _setup(state)
    s = decks.add_slide(
        state, slug, "d", slide_number=1, role="result", title="x",
        notes="hi", code="plt.savefig('out.png')",
        render_mode="code-shape",
    )
    with pytest.raises(ValueError):
        deck_render.render_slide(state, slug, "d", s["id"])


def test_render_code_shape_with_local_path(state, tmp_path):
    slug = _setup(state)
    s = decks.add_slide(
        state, slug, "d", slide_number=1, role="result", title="x",
        notes="hi", code="plt.savefig('out.png')",
        render_mode="code-shape",
    )
    p = tmp_path / "code-shape.png"
    p.write_bytes(b"local-png-bytes")
    r = deck_render.render_slide(state, slug, "d", s["id"], local_path=str(p))
    assert r["size_bytes"] == len(b"local-png-bytes")


def test_render_deck_marks_status_rendered_when_all_done(state, tmp_path):
    slug = _setup(state)
    decks.update_deck(state, slug, "d", concept="accent: red")
    # Two ai-image slides
    decks.add_slide(state, slug, "d", slide_number=1, role="title",
                    title="t1", notes="n", prompt="Hi", render_mode="ai-image")
    decks.add_slide(state, slug, "d", slide_number=2, role="conclusion",
                    title="t2", notes="n", prompt="Bye", render_mode="ai-image")

    class FakeGen:
        def generate(self, *, prompt, aspect_ratio="1:1", model="gpt-image-2"):
            return b"fake-png"
    state.image_gen = FakeGen()

    result = deck_render.render_deck(state, slug, "d")
    assert len(result["rendered"]) == 2
    assert result["errors"] == []
    deck = decks.get_deck(state, slug, "d")
    assert deck["status"] == "rendered"


def test_render_deck_skips_code_shape(state):
    slug = _setup(state)
    decks.add_slide(state, slug, "d", slide_number=1, role="title",
                    title="t1", notes="n", code="x",
                    render_mode="code-shape")
    result = deck_render.render_deck(state, slug, "d")
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["reason"] == "needs local PNG from agent"


def test_render_missing_slide_raises(state):
    slug = _setup(state)
    with pytest.raises(NotFound):
        deck_render.render_slide(state, slug, "d", "ghost-id")
