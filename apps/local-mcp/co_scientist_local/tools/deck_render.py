"""Deck rendering + PPTX export (Phase 3).

`render_slide` materializes a slide's image based on its render_mode:
  - paper-figure : copies the existing figure blob from the paper
  - ai-image     : substitutes concept placeholders in prompt, calls
                   the configured ImageGenerator
  - code-shape   : agent supplies a local PNG path (the MCP can't safely
                   sandbox arbitrary Python execution); we just register
                   the path
  - hybrid       : treated as code-shape for now

The rendered PNG is uploaded to Storage at
  papers/{slug}/decks/{deck_id}/slides/{slide_number}.png
and the slide doc's `image_blob_path` field is updated.

`export_deck_to_pptx` emits a .pptx via python-pptx:
  - image slides   : the rendered PNG, aspect-fitted and centered
  - `text` slides  : a NATIVE (editable) title + bullet layout, themed
                     from the deck concept's palette — not a picture
The slide size follows the deck's `aspect_ratio`. A sibling .pdf is
produced via LibreOffice (`soffice`) when available — python-pptx's
PPTX is occasionally rejected by Keynote, so the PDF is the portable
fallback. python-pptx ships in the base install.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import tempfile

from ..backends.base import NotFound
from ..state import State
from ..util import now_iso
from . import decks as _decks
from . import figures as _figures


# ─── placeholder resolution ─────────────────────────────────────────────────


_KV_RE = re.compile(r"^\s*([a-zA-Z_]\w*)\s*:\s*(.+?)\s*$")


def _parse_concept(concept: str | None) -> dict[str, str]:
    """Extract {key: value} pairs from a freeform concept string.

    The skill writes the concept like:
        Palette:
          bg: #fafaf7  surface: #ffffff  text: #1a1a1a  accent: #b58900
        Typography:
          display: Inter Bold     body: Inter Regular

    We tokenize on whitespace+colon to harvest any `name: value` pairs the
    skill drops in. Best-effort; placeholders that don't resolve stay as
    `{name}` in the output prompt for visibility.
    """
    if not concept:
        return {}
    pairs: dict[str, str] = {}
    # Split on whitespace tokens like "accent: #b58900" — also handle
    # multi-word values when the line is one-per-key.
    for raw in concept.splitlines():
        line = raw.strip()
        if not line or line.endswith(":"):
            continue
        # Multiple pairs on a single line ("bg: #fff surface: #f00 text: #000")
        chunks = re.findall(r"([a-zA-Z_]\w*)\s*:\s*([^\s][^,\n]*?)(?=\s+[a-zA-Z_]\w*\s*:|$)", line)
        if chunks:
            for k, v in chunks:
                pairs[k.lower()] = v.strip()
            continue
        m = _KV_RE.match(line)
        if m:
            pairs[m.group(1).lower()] = m.group(2).strip()
    return pairs


def resolve_placeholders(text: str, concept: str | None) -> str:
    """Replace `{name}` tokens with values harvested from the concept.

    Unknown placeholders stay literal so the issue is visible (a slide
    with `{accent}` in its final prompt is a bug the user can see).
    """
    if not text:
        return text
    if "{" not in text:
        return text
    kv = _parse_concept(concept)

    def _sub(m: re.Match) -> str:
        key = m.group(1).lower()
        return kv.get(key, m.group(0))
    return re.sub(r"\{([a-zA-Z_][\w-]*)\}", _sub, text)


# ─── slide rendering ────────────────────────────────────────────────────────


def _slide_blob_path(state: State, slug: str, deck_id: str, slide_number: int) -> str:
    return state.project_path(
        "papers", slug, "decks", deck_id, "slides", f"{slide_number:04d}.png",
    )


def render_slide(
    state: State,
    slug: str,
    deck_id: str,
    slide_id: str,
    *,
    local_path: str | None = None,
) -> dict:
    """Materialize a slide's image and upload to Storage.

    For paper-figure / ai-image modes, the MCP does the work. For
    code-shape / hybrid, the caller (agent) must supply `local_path`
    pointing at a PNG produced locally — running arbitrary Python in
    the MCP would be unsafe.
    """
    deck = _decks.get_deck(state, slug, deck_id)
    slide = state.backend.get_doc(_decks._slide_path(state, slug, deck_id, slide_id))
    if slide is None:
        raise NotFound(f"slide not found: {slide_id!r}")
    mode = slide.get("render_mode", "code-shape")
    slide_number = slide.get("slide_number") or 0

    png: bytes
    if mode == "text":
        raise ValueError(
            "text slides carry no image — they render as native PPTX "
            "text on export; nothing to render here"
        )
    if mode == "paper-figure":
        fig_num = slide.get("figure_number")
        if fig_num is None:
            raise ValueError("paper-figure slide has no figure_number")
        fig = _figures.get_figure(state, slug, int(fig_num))
        if not fig or not fig.get("blob_path"):
            raise NotFound(f"figure {fig_num!r} has no blob_path on paper {slug!r}")
        blob = state.backend.get_blob(fig["blob_path"])
        if blob is None:
            raise NotFound(f"figure {fig_num!r} blob is empty at {fig['blob_path']!r}")
        png = blob
    elif mode == "ai-image":
        prompt = resolve_placeholders(slide.get("prompt") or "", deck.get("concept"))
        if not prompt.strip():
            raise ValueError("ai-image slide has no prompt")
        gen = state.require_image_gen()
        png = gen.generate(prompt=prompt, aspect_ratio="16:9")
    elif mode in ("code-shape", "hybrid"):
        if not local_path:
            raise ValueError(
                f"{mode} slide requires local_path — produce the PNG yourself "
                "(matplotlib, python-pptx shapes, etc.) and pass it in."
            )
        png = pathlib.Path(local_path).expanduser().read_bytes()
    else:
        raise ValueError(f"unknown render_mode: {mode!r}")

    blob_path = _slide_blob_path(state, slug, deck_id, slide_number)
    state.backend.put_blob(blob_path, png)
    now = now_iso()
    state.backend.update_doc(
        _decks._slide_path(state, slug, deck_id, slide_id),
        {
            "image_blob_path": blob_path,
            "rendered_at": now,
            "status": "rendered",
            "updated_at": now,
        },
    )
    return {
        "slide_id": slide_id,
        "slide_number": slide_number,
        "blob_path": blob_path,
        "size_bytes": len(png),
        "mode": mode,
    }


def render_deck(state: State, slug: str, deck_id: str) -> dict:
    """Render every slide that has enough info. Skips code-shape/hybrid
    slides without a `local_path` queued — those are agent-side work."""
    slides = _decks.list_slides(state, slug, deck_id)
    results = {"rendered": [], "skipped": [], "errors": []}
    for s in slides:
        mode = s.get("render_mode") or "code-shape"
        if mode == "text":
            results["skipped"].append({
                "slide_id": s["id"], "slide_number": s.get("slide_number"),
                "reason": "text slide — native PPTX text on export",
            })
            continue
        if mode in ("code-shape", "hybrid"):
            results["skipped"].append({
                "slide_id": s["id"], "slide_number": s.get("slide_number"),
                "reason": "needs local PNG from agent",
            })
            continue
        try:
            r = render_slide(state, slug, deck_id, s["id"])
            results["rendered"].append(r)
        except Exception as e:
            results["errors"].append({
                "slide_id": s["id"], "slide_number": s.get("slide_number"),
                "error": str(e),
            })
    # Deck is "rendered" once every non-text slide has an image_blob_path —
    # text slides never get one (they're native text at export time).
    refreshed = _decks.list_slides(state, slug, deck_id)
    all_rendered = all(
        s.get("image_blob_path")
        for s in refreshed
        if (s.get("render_mode") or "code-shape") != "text"
    )
    if all_rendered:
        _decks.update_deck(state, slug, deck_id, status="rendered")
    return results


# ─── PPTX export ─────────────────────────────────────────────────────────────

# Deck aspect ratio → (width_in, height_in) for the PPTX page.
_ASPECT_TO_SIZE = {
    "16:9": (13.333, 7.5),
    "16:10": (12.0, 7.5),
    "4:3": (10.0, 7.5),
}


def _theme_colors(concept: str | None) -> dict[str, str]:
    """Harvest accent / background / foreground hex colors from the deck
    concept — the skill writes a `Palette:` block with bg / text / accent."""
    kv = _parse_concept(concept)
    return {
        "accent": kv.get("accent") or "#2E7D32",
        "background": kv.get("bg") or kv.get("background") or "#FFFFFF",
        "foreground": kv.get("text") or kv.get("foreground") or "#1A1A1A",
    }


def _hex_to_rgb(value: str, fallback: str):
    """Parse '#rrggbb' into a python-pptx RGBColor, tolerating junk."""
    from pptx.dml.color import RGBColor  # type: ignore
    raw = (value or "").lstrip("#")
    if len(raw) != 6:
        raw = fallback.lstrip("#")
    try:
        return RGBColor(int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        fb = fallback.lstrip("#")
        return RGBColor(int(fb[0:2], 16), int(fb[2:4], 16), int(fb[4:6], 16))


def _add_fitted_picture(slide, img_path: str, sw, sh) -> None:
    """Place an image scaled to fit the slide (aspect preserved), centered."""
    pic = slide.shapes.add_picture(img_path, 0, 0)
    scale = min(sw / pic.width, sh / pic.height)
    pic.width = int(pic.width * scale)
    pic.height = int(pic.height * scale)
    pic.left = int((sw - pic.width) / 2)
    pic.top = int((sh - pic.height) / 2)


def _add_text_slide(slide, row, *, sw, sh, accent, fg, bg,
                    Inches, Pt, MSO_SHAPE) -> None:
    """Draw a native (editable) title + bullet layout, palette-themed."""
    try:
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = bg
    except Exception:
        pass  # leave the default background if this build won't set it
    stripe = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, sw, Inches(0.14))
    stripe.line.fill.background()
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = accent
    stripe.shadow.inherit = False

    title_box = slide.shapes.add_textbox(
        Inches(0.6), Inches(0.55), sw - Inches(1.2), Inches(1.1),
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    tf.text = row.get("title") or ""
    for run in tf.paragraphs[0].runs:
        run.font.size = Pt(34)
        run.font.bold = True
        run.font.color.rgb = fg

    body = (row.get("body") or "").strip()
    if body:
        body_box = slide.shapes.add_textbox(
            Inches(0.6), Inches(1.9), sw - Inches(1.2), sh - Inches(2.5),
        )
        bf = body_box.text_frame
        bf.word_wrap = True
        first = True
        for raw in body.splitlines():
            line = raw.strip().lstrip("-*•#> ").strip()
            if not line:
                continue
            para = bf.paragraphs[0] if first else bf.add_paragraph()
            first = False
            para.text = "•  " + line
            for run in para.runs:
                run.font.size = Pt(20)
                run.font.color.rgb = fg


def _pdf_via_soffice(pptx_path: pathlib.Path) -> pathlib.Path | None:
    """Convert the .pptx to a sibling .pdf via LibreOffice. Returns the PDF
    path, or None if soffice/libreoffice is missing or the conversion fails.
    python-pptx output is occasionally rejected by Keynote — the PDF is the
    portable fallback."""
    for binary in ("soffice", "libreoffice"):
        try:
            proc = subprocess.run(
                [binary, "--headless", "--convert-to", "pdf",
                 "--outdir", str(pptx_path.parent), str(pptx_path)],
                capture_output=True, text=True, timeout=180,
            )
        except FileNotFoundError:
            continue  # try the next binary name
        except subprocess.TimeoutExpired:
            return None
        pdf = pptx_path.with_suffix(".pdf")
        return pdf if (proc.returncode == 0 and pdf.is_file()) else None
    return None


def export_deck_to_pptx(
    state: State,
    slug: str,
    deck_id: str,
    *,
    output_path: str,
) -> dict:
    """Build a .pptx — and, when LibreOffice is available, a sibling .pdf.

    Image slides embed the rendered PNG, aspect-fitted and centered.
    `text` slides — and any slide still missing a render — become NATIVE
    editable text (title + bullets) themed from the deck concept's
    palette. The slide size follows the deck's `aspect_ratio`.
    """
    try:
        from pptx import Presentation              # type: ignore
        from pptx.util import Inches, Pt           # type: ignore
        from pptx.enum.shapes import MSO_SHAPE     # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "python-pptx not installed — reinstall the package: "
            "pip install -e ~/co-scientists-mcp/apps/local-mcp"
        ) from e

    deck = _decks.get_deck(state, slug, deck_id)
    slides = _decks.list_slides(state, slug, deck_id)
    if not slides:
        raise ValueError(f"deck {deck_id!r} has no slides")

    aspect = deck.get("aspect_ratio") or "16:9"
    w_in, h_in = _ASPECT_TO_SIZE.get(aspect, _ASPECT_TO_SIZE["16:9"])
    colors = _theme_colors(deck.get("concept"))
    accent = _hex_to_rgb(colors["accent"], "#2E7D32")
    fg = _hex_to_rgb(colors["foreground"], "#1A1A1A")
    bg = _hex_to_rgb(colors["background"], "#FFFFFF")

    prs = Presentation()
    sw, sh = Inches(w_in), Inches(h_in)
    prs.slide_width, prs.slide_height = sw, sh
    blank_layout = prs.slide_layouts[6]

    missing_renders: list[int] = []
    image_slides = 0
    text_slides = 0
    with tempfile.TemporaryDirectory() as tmpd:
        for s in slides:
            slide = prs.slides.add_slide(blank_layout)
            mode = s.get("render_mode") or "code-shape"
            blob = (
                state.backend.get_blob(s["image_blob_path"])
                if s.get("image_blob_path") else None
            )
            if blob:
                tmp = pathlib.Path(tmpd) / f"slide_{s['id']}.png"
                tmp.write_bytes(blob)
                _add_fitted_picture(slide, str(tmp), sw, sh)
                image_slides += 1
            else:
                # Native editable text slide — either a `text` slide by
                # design, or a not-yet-rendered slide degraded gracefully.
                _add_text_slide(
                    slide, s, sw=sw, sh=sh, accent=accent, fg=fg, bg=bg,
                    Inches=Inches, Pt=Pt, MSO_SHAPE=MSO_SHAPE,
                )
                text_slides += 1
                if mode != "text":
                    missing_renders.append(s.get("slide_number") or 0)
            if s.get("notes"):
                slide.notes_slide.notes_text_frame.text = s["notes"]

    out = pathlib.Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    pdf_path = _pdf_via_soffice(out)

    # Upload + index each artifact so the dashboard's Presentation tab
    # lists them.
    now = now_iso()

    def _publish(path: pathlib.Path, fmt: str) -> str:
        blob_path = state.project_path(
            "papers", slug, "decks", deck_id, "exports", path.name,
        )
        data = path.read_bytes()
        state.backend.put_blob(blob_path, data)
        state.backend.set_doc(blob_path, {
            "filename": path.name,
            "format": fmt,
            "blob_path": blob_path,
            "size_bytes": len(data),
            "slide_count": len(slides),
            "missing_renders": missing_renders,
            "created_at": now,
        })
        return blob_path

    pptx_blob = _publish(out, "pptx")
    pdf_blob = _publish(pdf_path, "pdf") if pdf_path else None

    return {
        "deck_id": deck_id,
        "deck_title": deck.get("title"),
        "aspect_ratio": aspect,
        "slide_count": len(slides),
        "image_slides": image_slides,
        "text_slides": text_slides,
        "missing_renders": missing_renders,
        "local_path": str(out),
        "blob_path": pptx_blob,
        "pdf_local_path": str(pdf_path) if pdf_path else None,
        "pdf_blob_path": pdf_blob,
        "pdf_skipped": pdf_path is None,
        "size_bytes": os.path.getsize(out),
    }
