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


# ─── text slides + theme ─────────────────────────────────────────────────


def test_theme_colors_from_concept():
    concept = "Palette:\n  bg: #101010  text: #fafafa  accent: #ff8800"
    c = deck_render._theme_colors(concept)
    assert c == {
        "accent": "#ff8800", "background": "#101010", "foreground": "#fafafa",
    }


def test_theme_colors_defaults_when_absent():
    c = deck_render._theme_colors(None)
    assert c["accent"] == "#2E7D32"
    assert c["background"] == "#FFFFFF"
    assert c["foreground"] == "#1A1A1A"


def test_render_slide_text_mode_raises(state):
    slug = _setup(state)
    s = decks.add_slide(state, slug, "d", slide_number=1, role="outline",
                        title="Agenda", body="- a\n- b", render_mode="text")
    with pytest.raises(ValueError, match="text slides"):
        deck_render.render_slide(state, slug, "d", s["id"])


def test_render_deck_skips_text_slides(state):
    slug = _setup(state)
    decks.add_slide(state, slug, "d", slide_number=1, role="outline",
                    title="Agenda", body="x", render_mode="text")
    result = deck_render.render_deck(state, slug, "d")
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["reason"] == \
        "text slide — native PPTX text on export"


def test_render_deck_all_text_marks_rendered(state):
    """A deck of only text slides is fully rendered — text slides never
    get an image_blob_path, so they must not block the status flip."""
    slug = _setup(state)
    decks.add_slide(state, slug, "d", slide_number=1, role="title",
                    title="t", body="x", render_mode="text")
    deck_render.render_deck(state, slug, "d")
    assert decks.get_deck(state, slug, "d")["status"] == "rendered"


def test_pdf_via_soffice_missing_returns_none(state, tmp_path, monkeypatch):
    def _no_soffice(*a, **k):
        raise FileNotFoundError("soffice")
    monkeypatch.setattr(deck_render.subprocess, "run", _no_soffice)
    assert deck_render._pdf_via_soffice(tmp_path / "deck.pptx") is None


# ─── PPTX export smoke test (needs the optional python-pptx dep) ─────────

# A valid 1×1 transparent PNG — python-pptx parses the header for sizing.
import base64 as _b64  # noqa: E402
_PNG_1x1 = _b64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk"
    "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def test_export_deck_to_pptx_smoke(state, tmp_path, monkeypatch):
    pytest.importorskip("pptx")
    slug = _setup(state)
    decks.update_deck(state, slug, "d", concept="accent: #b58900",
                      aspect_ratio="4:3")
    # one image slide (paper-figure, rendered)
    p = tmp_path / "fig.png"
    p.write_bytes(_PNG_1x1)
    figures.add_figure(state, slug, figure_number=1, title="F", local_path=str(p))
    img = decks.add_slide(state, slug, "d", slide_number=1, role="result",
                          title="Result", notes="n",
                          render_mode="paper-figure", figure_number=1)
    deck_render.render_slide(state, slug, "d", img["id"])
    # one native text slide
    decks.add_slide(state, slug, "d", slide_number=2, role="outline",
                    title="Agenda", body="- point one\n- point two",
                    notes="n2", render_mode="text")
    # keep the test offline + deterministic — skip the LibreOffice step
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)

    out = tmp_path / "deck.pptx"
    res = deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    assert out.is_file()
    assert res["slide_count"] == 2
    assert res["image_slides"] == 1
    assert res["text_slides"] == 1
    assert res["missing_renders"] == []     # the text slide is not "missing"
    assert res["aspect_ratio"] == "4:3"
    assert res["pdf_skipped"] is True


# ─── regions: hybrid multi-image slides ──────────────────────


def _hybrid_setup(state, tmp_path):
    """paper + deck "d" + figure 1 + a hybrid slide with two regions
    (one paper-figure, one ai-image)."""
    slug = _setup(state)
    p = tmp_path / "fig.png"
    p.write_bytes(_PNG_1x1)
    figures.add_figure(state, slug, figure_number=1, title="F", local_path=str(p))
    s = decks.add_slide(state, slug, "d", slide_number=1, role="result", title="R")
    decks.set_slide_regions(state, slug, "d", s["id"], regions=[
        {"render_mode": "paper-figure", "figure_number": 1,
         "x": 0.05, "y": 0.25, "w": 0.42, "h": 0.6},
        {"render_mode": "ai-image", "prompt": "{accent} schematic",
         "x": 0.52, "y": 0.25, "w": 0.42, "h": 0.6},
    ])
    return slug, s["id"]


def test_nearest_aspect():
    assert deck_render._nearest_aspect(1920, 1080) == "16:9"
    assert deck_render._nearest_aspect(100, 100) == "1:1"
    assert deck_render._nearest_aspect(1080, 1920) == "9:16"
    assert deck_render._nearest_aspect(400, 300) == "4:3"


def test_render_region_paper_figure(state, tmp_path):
    slug, sid = _hybrid_setup(state, tmp_path)
    r = deck_render.render_region(state, slug, "d", sid, "r1")
    assert r["region_id"] == "r1" and r["mode"] == "paper-figure"
    slide = decks.list_slides(state, slug, "d")[0]
    assert slide["regions"][0]["image_blob_path"]


def test_render_region_ai_image_matches_box_aspect(state, tmp_path):
    slug, sid = _hybrid_setup(state, tmp_path)
    captured: dict = {}

    class FakeGen:
        def generate(self, *, prompt, aspect_ratio="1:1", model="gpt-image-2"):
            captured["prompt"] = prompt
            captured["aspect"] = aspect_ratio
            return b"ai-png"

    state.image_gen = FakeGen()
    decks.update_deck(state, slug, "d", concept="accent: #abc")
    r = deck_render.render_region(state, slug, "d", sid, "r2")
    assert r["mode"] == "ai-image"
    assert captured["prompt"] == "#abc schematic"   # placeholder resolved
    # region box 0.42w × 0.6h on a 16:9 deck is portrait-ish → "4:3",
    # NOT the deck's 16:9 (the original's todo 052).
    assert captured["aspect"] == "4:3"


def test_render_region_code_shape_needs_local_path(state, tmp_path):
    slug = _setup(state)
    s = decks.add_slide(state, slug, "d", slide_number=1, role="result", title="R")
    decks.set_slide_regions(state, slug, "d", s["id"], regions=[
        {"render_mode": "code-shape", "code": "plt...",
         "x": 0.1, "y": 0.2, "w": 0.8, "h": 0.6},
    ])
    with pytest.raises(ValueError, match="local_path"):
        deck_render.render_region(state, slug, "d", s["id"], "r1")
    p = tmp_path / "r.png"
    p.write_bytes(b"region-png")
    out = deck_render.render_region(state, slug, "d", s["id"], "r1",
                                   local_path=str(p))
    assert out["size_bytes"] == len(b"region-png")


def test_render_region_missing_raises(state, tmp_path):
    slug, sid = _hybrid_setup(state, tmp_path)
    with pytest.raises(NotFound):
        deck_render.render_region(state, slug, "d", sid, "r99")


def test_render_slide_hybrid_renders_all_regions(state, tmp_path):
    slug, sid = _hybrid_setup(state, tmp_path)

    class FakeGen:
        def generate(self, *, prompt, aspect_ratio="1:1", model="gpt-image-2"):
            return b"ai-png"

    state.image_gen = FakeGen()
    res = deck_render.render_slide(state, slug, "d", sid)
    assert res["mode"] == "hybrid"
    assert len(res["rendered"]) == 2
    assert res["skipped"] == [] and res["errors"] == []
    slide = decks.list_slides(state, slug, "d")[0]
    assert all(r["image_blob_path"] for r in slide["regions"])


def test_render_deck_hybrid_code_shape_region_skipped(state, tmp_path):
    slug = _setup(state)
    p = tmp_path / "fig.png"
    p.write_bytes(_PNG_1x1)
    figures.add_figure(state, slug, figure_number=1, title="F", local_path=str(p))
    s = decks.add_slide(state, slug, "d", slide_number=1, role="result", title="R")
    decks.set_slide_regions(state, slug, "d", s["id"], regions=[
        {"render_mode": "paper-figure", "figure_number": 1,
         "x": 0.05, "y": 0.2, "w": 0.4, "h": 0.6},
        {"render_mode": "code-shape", "code": "x",
         "x": 0.5, "y": 0.2, "w": 0.4, "h": 0.6},
    ])
    result = deck_render.render_deck(state, slug, "d")
    assert len(result["rendered"]) == 1                 # paper-figure region
    assert len(result["skipped"]) == 1                  # code-shape region
    assert "code-shape region" in result["skipped"][0]["reason"]
    # one region still unrendered → deck not flipped to 'rendered'
    assert decks.get_deck(state, slug, "d")["status"] != "rendered"


def test_export_hybrid_slide_smoke(state, tmp_path, monkeypatch):
    pytest.importorskip("pptx")
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    slug, sid = _hybrid_setup(state, tmp_path)

    class FakeGen:
        def generate(self, *, prompt, aspect_ratio="1:1", model="gpt-image-2"):
            return _PNG_1x1

    state.image_gen = FakeGen()
    deck_render.render_slide(state, slug, "d", sid)      # render both regions
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)

    out = tmp_path / "deck.pptx"
    res = deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    assert out.is_file()
    assert res["hybrid_slides"] == 1
    assert res["missing_renders"] == []
    prs = Presentation(str(out))
    pics = [sh for sh in prs.slides[0].shapes
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pics) == 2   # two region images placed as separate shapes


# ─── placeholder metadata: fit mode + captured image size ────


def test_png_size_parses_dimensions():
    assert deck_render._png_size(_PNG_1x1) == (1, 1)
    assert deck_render._png_size(b"not a png at all") is None
    assert deck_render._image_dims(_PNG_1x1) == {
        "image_width": 1, "image_height": 1,
    }
    assert deck_render._image_dims(b"junk") == {}


def test_render_region_records_image_dimensions(state, tmp_path):
    slug, sid = _hybrid_setup(state, tmp_path)
    deck_render.render_region(state, slug, "d", sid, "r1")
    region = decks.list_slides(state, slug, "d")[0]["regions"][0]
    assert region["image_width"] == 1 and region["image_height"] == 1


def test_render_slide_records_image_dimensions(state, tmp_path):
    slug = _setup(state)
    p = tmp_path / "fig.png"
    p.write_bytes(_PNG_1x1)
    figures.add_figure(state, slug, figure_number=1, title="F", local_path=str(p))
    s = decks.add_slide(state, slug, "d", slide_number=1, role="result",
                        title="R", render_mode="paper-figure", figure_number=1)
    deck_render.render_slide(state, slug, "d", s["id"])
    slide = decks.list_slides(state, slug, "d")[0]
    assert slide["image_width"] == 1 and slide["image_height"] == 1


def test_export_cover_region_crops(state, tmp_path, monkeypatch):
    pytest.importorskip("pptx")
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    slug = _setup(state)
    p = tmp_path / "fig.png"
    p.write_bytes(_PNG_1x1)
    figures.add_figure(state, slug, figure_number=1, title="F", local_path=str(p))
    s = decks.add_slide(state, slug, "d", slide_number=1, role="result", title="R")
    # square image (1×1) into a portrait box with fit=cover → crop sides
    decks.set_slide_regions(state, slug, "d", s["id"], regions=[
        {"render_mode": "paper-figure", "figure_number": 1, "fit": "cover",
         "x": 0.1, "y": 0.25, "w": 0.3, "h": 0.6},
    ])
    deck_render.render_region(state, slug, "d", s["id"], "r1")
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    prs = Presentation(str(out))
    pic = next(sh for sh in prs.slides[0].shapes
               if sh.shape_type == MSO_SHAPE_TYPE.PICTURE)
    assert pic.crop_left > 0   # cover cropped the overflowing edges
