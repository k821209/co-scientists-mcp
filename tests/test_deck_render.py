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


def test_export_hybrid_slide_with_body_renders_native_bullets(
        state, tmp_path, monkeypatch):
    """A hybrid slide with `body` renders the bullets as NATIVE editable
    text in the LEFT half, alongside an image region on the right — the
    'title + bullets + figure' layout."""
    pytest.importorskip("pptx")
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    slug = _setup(state)
    p = tmp_path / "fig.png"
    p.write_bytes(_PNG_1x1)
    figures.add_figure(state, slug, figure_number=1, title="F", local_path=str(p))
    s = decks.add_slide(
        state, slug, "d", slide_number=1, role="background",
        title="Pipeline vs MCP",
        body="- two-week bespoke pipeline\n- 30-second MCP query",
        notes="n",
    )
    decks.set_slide_regions(state, slug, "d", s["id"], regions=[
        {"render_mode": "paper-figure", "figure_number": 1,
         "x": 0.54, "y": 0.22, "w": 0.42, "h": 0.65},
    ])
    deck_render.render_slide(state, slug, "d", s["id"])
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)

    out = tmp_path / "deck.pptx"
    deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    prs = Presentation(str(out))
    slide = prs.slides[0]

    # one image region on the right
    pics = [sh for sh in slide.shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pics) == 1

    # native body text present and on the LEFT half of the slide. Each
    # bullet is its own textbox (block-based renderer — todo 002), so
    # collect them all and assert (a) both bullets exist as text frames
    # and (b) every body textbox sits in the left half.
    body_tbs = [
        sh for sh in slide.shapes
        if sh.has_text_frame and (
            "two-week bespoke pipeline" in sh.text_frame.text
            or "30-second MCP query" in sh.text_frame.text
        )
        and sh.left is not None
        and sh.left + sh.width <= prs.slide_width / 2 + 1
    ]
    body_text = "".join(b.text_frame.text for b in body_tbs)
    assert "two-week bespoke pipeline" in body_text
    assert "30-second MCP query" in body_text


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


# ─── export typography: title layout, markdown, fonts ────────


def test_font_family_strips_weight_words():
    assert deck_render._font_family("Inter Bold") == "Inter"
    assert deck_render._font_family("Source Serif Pro Regular") == "Source Serif Pro"
    assert deck_render._font_family("Inter") == "Inter"
    assert deck_render._font_family(None) is None
    assert deck_render._font_family("   ") is None


def test_theme_fonts_from_concept():
    concept = ("Typography:\n  display: Inter Bold   "
               "body: Source Serif Regular   mono: JetBrains Mono")
    f = deck_render._theme_fonts(concept)
    assert f["display"] == "Inter"
    assert f["body"] == "Source Serif"
    assert f["mono"] == "JetBrains Mono"


def test_theme_fonts_default_none():
    assert deck_render._theme_fonts(None) == {
        "display": None, "body": None, "mono": None,
    }


def test_export_title_slide_is_centered(state, tmp_path, monkeypatch):
    pytest.importorskip("pptx")
    from pptx import Presentation
    from pptx.enum.text import PP_ALIGN

    slug = _setup(state)
    decks.add_slide(state, slug, "d", slide_number=1, role="title",
                    title="My Big Talk", body="A subtitle line",
                    notes="n", render_mode="text")
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    prs = Presentation(str(out))
    tb = next(sh for sh in prs.slides[0].shapes if sh.has_text_frame)
    # cover layout: the title paragraph is centered, not top-anchored
    assert tb.text_frame.paragraphs[0].alignment == PP_ALIGN.CENTER
    assert "My Big Talk" in tb.text_frame.text


def test_export_body_is_plain_text_no_markdown_parsing(state, tmp_path, monkeypatch):
    """body markdown markers (** _ `) survive into the slide as literal
    text — the renderer is intentionally markdown-agnostic. Rich slide
    design is the job of the slide's `code` field, not the body parser
    (docs/todo/002)."""
    pytest.importorskip("pptx")
    from pptx import Presentation

    slug = _setup(state)
    decks.add_slide(state, slug, "d", slide_number=1, role="background",
                    title="Background", body="plain and **strong** words",
                    notes="n", render_mode="text")
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    prs = Presentation(str(out))
    flat = " ".join(
        sh.text_frame.text for sh in prs.slides[0].shapes if sh.has_text_frame
    )
    assert "plain and **strong** words" in flat
    runs = [r for sh in prs.slides[0].shapes if sh.has_text_frame
            for para in sh.text_frame.paragraphs for r in para.runs]
    body_runs = [r for r in runs if "strong" in (r.text or "")]
    assert body_runs and body_runs[0].font.bold is not True


def test_export_applies_concept_fonts(state, tmp_path, monkeypatch):
    pytest.importorskip("pptx")
    from pptx import Presentation

    slug = _setup(state)
    decks.update_deck(
        state, slug, "d",
        concept="Typography:\n  display: Inter Bold   body: Lora Regular",
    )
    decks.add_slide(state, slug, "d", slide_number=1, role="background",
                    title="Heading", body="some body text",
                    notes="n", render_mode="text")
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    prs = Presentation(str(out))
    names = {r.font.name for sh in prs.slides[0].shapes if sh.has_text_frame
             for para in sh.text_frame.paragraphs for r in para.runs}
    assert "Inter" in names   # display font on the title
    assert "Lora" in names    # body font on the body text


# ─── Keynote-safe image normalization (todo 032) ────────────────────────


def test_normalize_image_rgba_becomes_rgb_jpeg(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    src = tmp_path / "rgba.png"
    Image.new("RGBA", (32, 32), (255, 0, 0, 128)).save(src)
    out = deck_render._normalize_image_for_pptx(str(src))
    # Returned as BytesIO; first bytes are the JPEG SOI marker (FFD8).
    assert hasattr(out, "read")
    head = out.read(3)
    assert head[:2] == b"\xff\xd8"
    out.seek(0)
    img = Image.open(out)
    assert img.mode == "RGB"   # alpha flattened against white background


def test_normalize_image_downsamples_oversized(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    src = tmp_path / "huge.png"
    Image.new("RGB", (4000, 2000), (200, 100, 50)).save(src)
    out = deck_render._normalize_image_for_pptx(str(src), target_width=1920)
    img = Image.open(out)
    assert img.width == 1920
    assert img.height == 960   # proportional


def test_normalize_image_keeps_smaller_rgb_at_size(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    src = tmp_path / "small.png"
    Image.new("RGB", (800, 600), (10, 20, 30)).save(src)
    out = deck_render._normalize_image_for_pptx(str(src), target_width=1920)
    img = Image.open(out)
    assert (img.width, img.height) == (800, 600)


def test_normalize_image_falls_back_on_unreadable_input(tmp_path):
    src = tmp_path / "garbage.png"
    src.write_bytes(b"not actually an image")
    # Must not raise — degraded gracefully so the export still produces a PPTX.
    out = deck_render._normalize_image_for_pptx(str(src))
    assert out == str(src)   # original path returned as last-ditch fallback


# ─── Theme-driven type scale (todo 035) ─────────────────────────────────


def test_type_scale_defaults_when_concept_absent():
    ts = deck_render._theme_type_scale(None)
    assert ts["title"] == 32
    assert ts["body"] == 20
    assert ts["head"] == 26
    assert ts["cover_title"] == 40
    assert ts["caption"] == 12
    assert ts["line_spacing"] == pytest.approx(1.22)


def test_type_scale_overrides_from_concept():
    concept = (
        "Type scale:\n"
        "  title: 30  head: 24  body: 18  line_spacing: 1.15\n"
        "  cover_title: 36"
    )
    ts = deck_render._theme_type_scale(concept)
    assert ts["title"] == 30
    assert ts["head"] == 24
    assert ts["body"] == 18
    assert ts["cover_title"] == 36
    assert ts["line_spacing"] == pytest.approx(1.15)
    # Unspecified keys keep defaults.
    assert ts["caption"] == 12


def test_type_scale_ignores_malformed_values():
    concept = "Type scale:\n  title: huge  body: 22"
    ts = deck_render._theme_type_scale(concept)
    assert ts["title"] == 32   # malformed → default
    assert ts["body"] == 22    # well-formed override applied


def test_export_applies_type_scale_to_title(state, tmp_path, monkeypatch):
    """A concept with `Type scale: title: 30` produces a 30pt title run
    instead of the default 32pt."""
    pytest.importorskip("pptx")
    from pptx import Presentation

    slug = _setup(state)
    decks.update_deck(
        state, slug, "d",
        concept="Type scale:\n  title: 30  body: 18",
    )
    decks.add_slide(state, slug, "d", slide_number=1, role="background",
                    title="Heading", body="some body text",
                    notes="n", render_mode="text")
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    prs = Presentation(str(out))
    title_runs = [
        r for sh in prs.slides[0].shapes if sh.has_text_frame
        for para in sh.text_frame.paragraphs for r in para.runs
        if r.text == "Heading"
    ]
    assert title_runs
    # python-pptx font.size is an Emu/Pt object; check via .pt
    assert title_runs[0].font.size.pt == 30


# ─── code slides: agent-authored python-pptx snippets (todo 002) ────────


def test_render_deck_skips_code_slides(state):
    """A code slide's `code` runs at PPTX export time; render_deck has
    nothing to do for it."""
    slug = _setup(state)
    decks.add_slide(state, slug, "d", slide_number=1, role="background",
                    title="t", code="pass", render_mode="code")
    result = deck_render.render_deck(state, slug, "d")
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["reason"] == \
        "code slide — runs at PPTX export time"


def test_render_slide_code_mode_raises(state):
    slug = _setup(state)
    s = decks.add_slide(state, slug, "d", slide_number=1, role="discussion",
                        title="t", code="pass", render_mode="code")
    with pytest.raises(ValueError, match="code slides"):
        deck_render.render_slide(state, slug, "d", s["id"])


def test_render_deck_all_code_marks_rendered(state):
    """A deck of only code slides is fully 'rendered' — they materialize
    natively at export time, so they must not block the status flip."""
    slug = _setup(state)
    decks.add_slide(state, slug, "d", slide_number=1, role="discussion",
                    title="t", code="pass", render_mode="code")
    deck_render.render_deck(state, slug, "d")
    assert decks.get_deck(state, slug, "d")["status"] == "rendered"


def test_export_code_slide_executes_snippet(state, tmp_path, monkeypatch):
    """A `code` slide's snippet runs at export, populating the slide
    with whatever shapes the agent's code adds."""
    pytest.importorskip("pptx")
    from pptx import Presentation

    slug = _setup(state)
    decks.update_deck(state, slug, "d", concept="accent: #b58900")
    decks.add_slide(
        state, slug, "d", slide_number=1, role="discussion",
        title="My Title", notes="n", render_mode="code",
        code=(
            "h.accent_stripe(slide, palette=palette, sw=sw)\n"
            "h.title_block(slide, title, palette=palette, fonts=fonts,\n"
            "              type_scale=type_scale, sw=sw, sh=sh)\n"
            "h.bullet_list(slide, ['alpha', 'beta', 'gamma'],\n"
            "              palette=palette, fonts=fonts, type_scale=type_scale,\n"
            "              left=Inches(0.7), top=Inches(2.0),\n"
            "              width=sw - Inches(1.4), height=Inches(4.0))\n"
        ),
    )
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    res = deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    assert res["code_slides"] == 1
    assert res["code_errors"] == []
    assert res["text_slides"] == 0
    flat = " ".join(
        sh.text_frame.text for sh in Presentation(str(out)).slides[0].shapes
        if sh.has_text_frame
    )
    assert "My Title" in flat
    for token in ("alpha", "beta", "gamma"):
        assert token in flat


def test_export_code_slide_card_grid(state, tmp_path, monkeypatch):
    """The card_grid helper produces N cards arranged in `cols` columns."""
    pytest.importorskip("pptx")
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    slug = _setup(state)
    decks.update_deck(state, slug, "d", concept="accent: #b58900")
    decks.add_slide(
        state, slug, "d", slide_number=1, role="background",
        title="Spec", notes="n", render_mode="code",
        code=(
            "h.accent_stripe(slide, palette=palette, sw=sw)\n"
            "h.title_block(slide, title, palette=palette, fonts=fonts,\n"
            "              type_scale=type_scale, sw=sw, sh=sh)\n"
            "h.card_grid(slide, [\n"
            "    {'title': 'Memory', 'body': 'persists across sessions'},\n"
            "    {'title': 'Hooks', 'body': 'fire on events'},\n"
            "    {'title': 'Slash', 'body': 'reusable commands'},\n"
            "    {'title': 'Context', 'body': 'attention manager'},\n"
            "], left=Inches(0.7), top=Inches(2.0),\n"
            "   width=sw - Inches(1.4), height=Inches(4.0),\n"
            "   palette=palette, fonts=fonts, type_scale=type_scale, cols=2)\n"
        ),
    )
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    slide = Presentation(str(out)).slides[0]
    # Each card adds: a card body rect (RECTANGLE), an accent stripe
    # (RECTANGLE), a title textbox, a body textbox. We expect 4 cards.
    flat = " ".join(
        sh.text_frame.text for sh in slide.shapes if sh.has_text_frame
    )
    for tag in ("Memory", "Hooks", "Slash", "Context"):
        assert tag in flat
    for body in ("persists across sessions", "fire on events",
                 "reusable commands", "attention manager"):
        assert body in flat
    # 4 cards × (card rect + accent stripe) = 8 RECTANGLE auto-shapes,
    # plus the top accent stripe and the title accent rule = at least 10.
    auto_shapes = [
        sh for sh in slide.shapes
        if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE
    ]
    assert len(auto_shapes) >= 10


def test_export_code_slide_error_degrades_to_text(state, tmp_path, monkeypatch):
    """A broken `code` slide's exception is captured in `code_errors`
    and the slide degrades to plain text — the whole export still
    succeeds."""
    pytest.importorskip("pptx")

    slug = _setup(state)
    decks.add_slide(
        state, slug, "d", slide_number=1, role="background",
        title="Broken", body="fallback text", notes="n",
        render_mode="code",
        code="raise RuntimeError('intentional test failure')",
    )
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    res = deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    assert out.is_file()
    assert res["code_slides"] == 0
    assert len(res["code_errors"]) == 1
    err = res["code_errors"][0]
    assert err["slide_number"] == 1
    assert "RuntimeError" in err["error"]
    assert "intentional test failure" in err["error"]
    # Slide degraded to text — body content survives.
    from pptx import Presentation
    flat = " ".join(
        sh.text_frame.text for sh in Presentation(str(out)).slides[0].shapes
        if sh.has_text_frame
    )
    assert "fallback text" in flat
    assert res["text_slides"] == 1


# ─── Design grid (todo 004 §D) ──────────────────────────────────────────


def test_grid_cell_basic_geometry():
    """First cell sits at (margin_x, margin_top); column widths divide
    the usable width evenly; horizontal gutters separate columns."""
    from pptx.util import Inches, Pt
    from co_scientist_local.tools import slide_render_helpers as srh

    sw = Inches(13.333)  # 16:9 deck slide width
    sh = Inches(7.5)
    g = srh.grid(sw=sw, sh=sh, cols=12, rows=6)
    left, top, w, h = g.cell(col=1, span=1, row=1, row_span=1)
    assert left == g.margin_x
    assert top == g.margin_top
    assert w == g.col_w
    assert h == g.row_h


def test_grid_span_absorbs_gutters():
    """A span-3 cell is wider than 3 separate col-1 cells by 2 gutters
    — the cell straddles the gutters between covered columns."""
    from pptx.util import Inches, Pt
    from co_scientist_local.tools import slide_render_helpers as srh

    g = srh.grid(sw=Inches(13.333), sh=Inches(7.5), cols=12, rows=6)
    _, _, w_single, _ = g.cell(col=1, span=1, row=1)
    _, _, w_three, _ = g.cell(col=1, span=3, row=1)
    assert w_three == 3 * w_single + 2 * g.gutter


def test_grid_row_helper_spans_all_columns():
    """`g.row(...)` is full-width across `cols` columns."""
    from pptx.util import Inches
    from co_scientist_local.tools import slide_render_helpers as srh

    g = srh.grid(sw=Inches(13.333), sh=Inches(7.5))
    full = g.row(row=2)
    same = g.cell(col=1, span=g.cols, row=2)
    assert full == same


def test_grid_rejects_out_of_range():
    """Cells outside the grid raise ValueError, not silently clip."""
    from pptx.util import Inches
    from co_scientist_local.tools import slide_render_helpers as srh

    g = srh.grid(sw=Inches(13.333), sh=Inches(7.5), cols=12, rows=6)
    with pytest.raises(ValueError, match="col must be 1..12"):
        g.cell(col=0, row=1)
    with pytest.raises(ValueError, match="exceeds 12 cols"):
        g.cell(col=10, span=5, row=1)
    with pytest.raises(ValueError, match="row must be 1..6"):
        g.cell(col=1, row=7)
    with pytest.raises(ValueError, match="exceeds 6 rows"):
        g.cell(col=1, row=5, row_span=3)


def test_export_code_slide_uses_grid(state, tmp_path, monkeypatch):
    """End-to-end: a `code` snippet builds a grid + a card grid in it,
    everything renders, the cards land at the grid coordinates."""
    pytest.importorskip("pptx")
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    slug = _setup(state)
    decks.update_deck(state, slug, "d", concept="accent: #b58900")
    decks.add_slide(
        state, slug, "d", slide_number=1, role="background",
        title="Grid demo", notes="n", render_mode="code",
        code=(
            "g = h.grid(sw=sw, sh=sh, cols=12, rows=4)\n"
            "h.accent_stripe(slide, palette=palette, sw=sw)\n"
            "h.title_block(slide, title, palette=palette, fonts=fonts,\n"
            "              type_scale=type_scale, sw=sw, sh=sh)\n"
            "left, top, w, ht = g.cell(col=1, span=6, row=1, row_span=4)\n"
            "h.bullet_list(slide, ['left half'],\n"
            "              palette=palette, fonts=fonts, type_scale=type_scale,\n"
            "              left=left, top=top, width=w, height=ht)\n"
            "left, top, w, ht = g.cell(col=7, span=6, row=1, row_span=4)\n"
            "h.bullet_list(slide, ['right half'],\n"
            "              palette=palette, fonts=fonts, type_scale=type_scale,\n"
            "              left=left, top=top, width=w, height=ht)\n"
        ),
    )
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    res = deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    assert res["code_slides"] == 1
    assert res["code_errors"] == []
    flat = " ".join(
        sh.text_frame.text for sh in Presentation(str(out)).slides[0].shapes
        if sh.has_text_frame
    )
    assert "left half" in flat
    assert "right half" in flat


def test_spacing_unit_exposed_to_snippets(state, tmp_path, monkeypatch):
    """A snippet can read `h.SPACING_UNIT_PT` for 8pt-rhythm math."""
    pytest.importorskip("pptx")
    from pptx import Presentation

    slug = _setup(state)
    decks.add_slide(
        state, slug, "d", slide_number=1, role="background",
        title="Rhythm", notes="n", render_mode="code",
        code=(
            "assert h.SPACING_UNIT_PT == 8\n"
            "h.accent_stripe(slide, palette=palette, sw=sw)\n"
            "h.title_block(slide, title, palette=palette, fonts=fonts,\n"
            "              type_scale=type_scale, sw=sw, sh=sh)\n"
        ),
    )
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    res = deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    assert res["code_slides"] == 1
    assert res["code_errors"] == []


def test_export_code_slide_image_from_figure(state, tmp_path, monkeypatch):
    """`h.image_figure(N, ...)` resolves a paper figure and embeds it."""
    pytest.importorskip("pptx")
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    slug = _setup(state)
    p = tmp_path / "fig.png"
    p.write_bytes(_PNG_1x1)
    figures.add_figure(state, slug, figure_number=1, title="F", local_path=str(p))
    decks.add_slide(
        state, slug, "d", slide_number=1, role="result",
        title="With figure", notes="n", render_mode="code",
        code=(
            "h.accent_stripe(slide, palette=palette, sw=sw)\n"
            "h.title_block(slide, title, palette=palette, fonts=fonts,\n"
            "              type_scale=type_scale, sw=sw, sh=sh)\n"
            "h.image_figure(1, left=Inches(0.7), top=Inches(2.0),\n"
            "               width=sw - Inches(1.4), height=Inches(4.0))\n"
        ),
    )
    monkeypatch.setattr(deck_render, "_pdf_via_soffice", lambda _p: None)
    out = tmp_path / "deck.pptx"
    res = deck_render.export_deck_to_pptx(state, slug, "d", output_path=str(out))
    assert res["code_slides"] == 1
    assert res["code_errors"] == []
    pics = [
        sh for sh in Presentation(str(out)).slides[0].shapes
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    assert len(pics) == 1   # one image embedded via image_figure

