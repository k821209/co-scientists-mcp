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

# Deck aspect ratio → (width_in, height_in) for the PPTX page.
_ASPECT_TO_SIZE = {
    "16:9": (13.333, 7.5),
    "16:10": (12.0, 7.5),
    "4:3": (10.0, 7.5),
}

# Standard aspect ratios an image generator accepts — used to match a
# region's box shape (the original co-scientist's todo 052: pass the
# region aspect to the generator, not the deck aspect).
_STD_ASPECTS = {"1:1": 1.0, "4:3": 4 / 3, "3:4": 3 / 4, "16:9": 16 / 9, "9:16": 9 / 16}


def _nearest_aspect(width: float, height: float) -> str:
    """Pick the standard aspect-ratio string closest to width:height."""
    if height <= 0:
        return "1:1"
    ratio = width / height
    return min(_STD_ASPECTS, key=lambda k: abs(_STD_ASPECTS[k] - ratio))


def _deck_aspect_size(deck: dict) -> tuple[float, float]:
    """The deck's slide dimensions in inches."""
    return _ASPECT_TO_SIZE.get(
        deck.get("aspect_ratio") or "16:9", _ASPECT_TO_SIZE["16:9"],
    )


def _slide_blob_path(state: State, slug: str, deck_id: str, slide_number: int) -> str:
    return state.project_path(
        "papers", slug, "decks", deck_id, "slides", f"{slide_number:04d}.png",
    )


def _region_blob_path(
    state: State, slug: str, deck_id: str, slide_number: int, region_id: str,
) -> str:
    return state.project_path(
        "papers", slug, "decks", deck_id, "slides",
        f"{slide_number:04d}", "regions", f"{region_id}.png",
    )


def _figure_png(state: State, slug: str, figure_number) -> bytes:
    """Fetch a paper figure's image bytes, or raise NotFound."""
    fig = _figures.get_figure(state, slug, int(figure_number))
    if not fig or not fig.get("blob_path"):
        raise NotFound(
            f"figure {figure_number!r} has no blob_path on paper {slug!r}"
        )
    blob = state.backend.get_blob(fig["blob_path"])
    if blob is None:
        raise NotFound(f"figure {figure_number!r} blob is empty")
    return blob


def render_slide(
    state: State,
    slug: str,
    deck_id: str,
    slide_id: str,
    *,
    local_path: str | None = None,
) -> dict:
    """Materialize a slide's image(s) and upload to Storage.

    paper-figure / ai-image : the MCP renders it.
    code-shape              : the agent supplies `local_path` (a PNG it
                              produced locally — the MCP won't exec code).
    hybrid                  : renders every region it can; returns a
                              per-region summary (see render_region).
    text                    : nothing to render — native text at export.
    """
    deck = _decks.get_deck(state, slug, deck_id)
    slide = state.backend.get_doc(_decks._slide_path(state, slug, deck_id, slide_id))
    if slide is None:
        raise NotFound(f"slide not found: {slide_id!r}")
    mode = slide.get("render_mode", "code-shape")
    slide_number = slide.get("slide_number") or 0

    if mode == "text":
        raise ValueError(
            "text slides carry no image — they render as native PPTX "
            "text on export; nothing to render here"
        )
    if mode == "hybrid":
        return _render_hybrid_slide(state, slug, deck_id, slide, deck)

    png: bytes
    if mode == "paper-figure":
        fig_num = slide.get("figure_number")
        if fig_num is None:
            raise ValueError("paper-figure slide has no figure_number")
        png = _figure_png(state, slug, fig_num)
    elif mode == "ai-image":
        prompt = resolve_placeholders(slide.get("prompt") or "", deck.get("concept"))
        if not prompt.strip():
            raise ValueError("ai-image slide has no prompt")
        png = state.require_image_gen().generate(prompt=prompt, aspect_ratio="16:9")
    elif mode == "code-shape":
        if not local_path:
            raise ValueError(
                "code-shape slide requires local_path — produce the PNG "
                "yourself (matplotlib, python-pptx shapes, etc.) and pass it in."
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


# ─── hybrid (multi-region) slides ───────────────────────────────────────────


def _update_region(
    state: State, slug: str, deck_id: str, slide_id: str,
    region_id: str, fields: dict,
) -> None:
    """Patch one region (matched by id) inside a slide's `regions` array."""
    path = _decks._slide_path(state, slug, deck_id, slide_id)
    slide = state.backend.get_doc(path)
    regions = list(slide.get("regions") or [])
    for r in regions:
        if r.get("id") == region_id:
            r.update(fields)
            break
    state.backend.update_doc(path, {"regions": regions, "updated_at": now_iso()})


def _render_one_region(
    state: State, slug: str, deck_id: str, slide: dict, deck: dict,
    region: dict, *, local_path: str | None = None,
) -> dict:
    """Render a single region's image, store it, stamp the region doc."""
    rmode = region.get("render_mode")
    region_id = region.get("id")
    slide_number = slide.get("slide_number") or 0

    if rmode == "paper-figure":
        if region.get("figure_number") is None:
            raise ValueError(f"region {region_id}: paper-figure needs figure_number")
        png = _figure_png(state, slug, region["figure_number"])
    elif rmode == "ai-image":
        prompt = resolve_placeholders(region.get("prompt") or "", deck.get("concept"))
        if not prompt.strip():
            raise ValueError(f"region {region_id}: ai-image needs a prompt")
        w_in, h_in = _deck_aspect_size(deck)
        aspect = _nearest_aspect(
            (region.get("w") or 1.0) * w_in, (region.get("h") or 1.0) * h_in,
        )
        png = state.require_image_gen().generate(prompt=prompt, aspect_ratio=aspect)
    elif rmode == "code-shape":
        if not local_path:
            raise ValueError(
                f"region {region_id}: code-shape needs local_path — render the "
                "PNG yourself and pass it to render_region."
            )
        png = pathlib.Path(local_path).expanduser().read_bytes()
    else:
        raise ValueError(f"region {region_id}: unknown render_mode {rmode!r}")

    blob_path = _region_blob_path(state, slug, deck_id, slide_number, region_id)
    state.backend.put_blob(blob_path, png)
    _update_region(state, slug, deck_id, slide["id"], region_id, {
        "image_blob_path": blob_path,
        "rendered_at": now_iso(),
    })
    return {
        "region_id": region_id,
        "mode": rmode,
        "blob_path": blob_path,
        "size_bytes": len(png),
    }


def _render_hybrid_slide(
    state: State, slug: str, deck_id: str, slide: dict, deck: dict,
) -> dict:
    """Render every auto-renderable region of a hybrid slide. code-shape
    regions land in `skipped[]` for the agent to do via render_region."""
    regions = slide.get("regions") or []
    if not regions:
        raise ValueError(
            "hybrid slide has no regions — call set_slide_regions first"
        )
    rendered: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []
    for r in regions:
        tag = {
            "slide_id": slide["id"], "slide_number": slide.get("slide_number"),
            "region_id": r.get("id"),
        }
        if r.get("render_mode") == "code-shape":
            skipped.append({
                **tag,
                "reason": "code-shape region — render_region with local_path",
            })
            continue
        try:
            rendered.append({**tag, **_render_one_region(
                state, slug, deck_id, slide, deck, r,
            )})
        except Exception as e:
            errors.append({**tag, "error": str(e)})
    return {
        "slide_id": slide["id"],
        "slide_number": slide.get("slide_number"),
        "mode": "hybrid",
        "rendered": rendered,
        "skipped": skipped,
        "errors": errors,
    }


def render_region(
    state: State,
    slug: str,
    deck_id: str,
    slide_id: str,
    region_id: str,
    *,
    local_path: str | None = None,
) -> dict:
    """Render one region of a hybrid slide. paper-figure / ai-image are
    done by the MCP; a code-shape region needs `local_path` — a PNG you
    produced locally."""
    slide = state.backend.get_doc(_decks._slide_path(state, slug, deck_id, slide_id))
    if slide is None:
        raise NotFound(f"slide not found: {slide_id!r}")
    deck = _decks.get_deck(state, slug, deck_id)
    region = next(
        (r for r in (slide.get("regions") or []) if r.get("id") == region_id),
        None,
    )
    if region is None:
        raise NotFound(f"region not found: {region_id!r} on slide {slide_id!r}")
    return _render_one_region(
        state, slug, deck_id, slide, deck, region, local_path=local_path,
    )


def _slide_is_rendered(s: dict) -> bool:
    """A slide is 'done' when its image(s) exist: text → always; hybrid →
    every region has an image; else → has image_blob_path."""
    mode = s.get("render_mode") or "code-shape"
    if mode == "text":
        return True
    if mode == "hybrid":
        regions = s.get("regions") or []
        return bool(regions) and all(r.get("image_blob_path") for r in regions)
    return bool(s.get("image_blob_path"))


def render_deck(state: State, slug: str, deck_id: str) -> dict:
    """Render every slide we can do automatically. code-shape slides and
    code-shape regions land in `skipped[]` for agent follow-up. When every
    non-text slide (and every region) is rendered, deck.status → 'rendered'."""
    slides = _decks.list_slides(state, slug, deck_id)
    results: dict[str, list] = {"rendered": [], "skipped": [], "errors": []}
    for s in slides:
        mode = s.get("render_mode") or "code-shape"
        tag = {"slide_id": s["id"], "slide_number": s.get("slide_number")}
        if mode == "text":
            results["skipped"].append({
                **tag, "reason": "text slide — native PPTX text on export",
            })
            continue
        if mode == "code-shape":
            results["skipped"].append({
                **tag, "reason": "needs local PNG from agent",
            })
            continue
        if mode == "hybrid":
            try:
                hr = render_slide(state, slug, deck_id, s["id"])
                results["rendered"].extend(hr["rendered"])
                results["skipped"].extend(hr["skipped"])
                results["errors"].extend(hr["errors"])
            except Exception as e:
                results["errors"].append({**tag, "error": str(e)})
            continue
        try:
            results["rendered"].append(render_slide(state, slug, deck_id, s["id"]))
        except Exception as e:
            results["errors"].append({**tag, "error": str(e)})

    refreshed = _decks.list_slides(state, slug, deck_id)
    if all(_slide_is_rendered(s) for s in refreshed):
        _decks.update_deck(state, slug, deck_id, status="rendered")
    return results


# ─── PPTX export ─────────────────────────────────────────────────────────────


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


def _add_fitted_picture(slide, img_path: str, *, left, top, box_w, box_h) -> None:
    """Place an image scaled to fit within (box_w × box_h), centered in the
    box at (left, top). Aspect ratio preserved."""
    pic = slide.shapes.add_picture(img_path, left, top)
    scale = min(box_w / pic.width, box_h / pic.height)
    pic.width = int(pic.width * scale)
    pic.height = int(pic.height * scale)
    pic.left = int(left + (box_w - pic.width) / 2)
    pic.top = int(top + (box_h - pic.height) / 2)


def _add_slide_frame(slide, row, *, sw, sh, accent, fg, bg,
                     Inches, Pt, MSO_SHAPE) -> None:
    """Themed background + accent stripe + native title — the shared shell
    of native text slides and hybrid (multi-region) slides."""
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
        Inches(0.6), Inches(0.4), sw - Inches(1.2), Inches(0.95),
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    tf.text = row.get("title") or ""
    for run in tf.paragraphs[0].runs:
        run.font.size = Pt(32)
        run.font.bold = True
        run.font.color.rgb = fg


def _add_text_slide(slide, row, *, sw, sh, accent, fg, bg,
                    Inches, Pt, MSO_SHAPE) -> None:
    """A native (editable) title + bullet layout, palette-themed."""
    _add_slide_frame(slide, row, sw=sw, sh=sh, accent=accent, fg=fg, bg=bg,
                     Inches=Inches, Pt=Pt, MSO_SHAPE=MSO_SHAPE)
    body = (row.get("body") or "").strip()
    if body:
        body_box = slide.shapes.add_textbox(
            Inches(0.6), Inches(1.7), sw - Inches(1.2), sh - Inches(2.3),
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


def _add_hybrid_slide(slide, row, state, tmpd, *, sw, sh, accent, fg, bg,
                      Inches, Pt, MSO_SHAPE) -> int:
    """A themed title frame + each region placed as its own picture (or a
    placeholder box if unrendered). Returns the count of unrendered regions.
    Region x/y/w/h are fractions of the slide."""
    _add_slide_frame(slide, row, sw=sw, sh=sh, accent=accent, fg=fg, bg=bg,
                     Inches=Inches, Pt=Pt, MSO_SHAPE=MSO_SHAPE)
    unrendered = 0
    for r in row.get("regions") or []:
        left = int(r["x"] * sw)
        top = int(r["y"] * sh)
        box_w = int(r["w"] * sw)
        box_h = int(r["h"] * sh)
        caption = r.get("caption")
        cap_h = Inches(0.34) if caption else 0
        img_h = box_h - cap_h
        blob = (
            state.backend.get_blob(r["image_blob_path"])
            if r.get("image_blob_path") else None
        )
        if blob:
            tmp = pathlib.Path(tmpd) / f"region_{row['id']}_{r['id']}.png"
            tmp.write_bytes(blob)
            _add_fitted_picture(slide, str(tmp),
                                left=left, top=top, box_w=box_w, box_h=img_h)
        else:
            unrendered += 1
            box = slide.shapes.add_textbox(left, top, box_w, img_h)
            box.text_frame.word_wrap = True
            box.text_frame.text = (
                f"[region {r.get('id')}: {r.get('render_mode')} — not rendered]"
            )
        if caption:
            cap = slide.shapes.add_textbox(left, top + img_h, box_w, cap_h)
            cf = cap.text_frame
            cf.word_wrap = True
            cf.text = caption
            for run in cf.paragraphs[0].runs:
                run.font.size = Pt(12)
                run.font.color.rgb = fg
    return unrendered


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

    Per slide render_mode:
      - image slides (paper-figure / ai-image / code-shape) embed the
        rendered PNG, aspect-fitted and centered.
      - `hybrid` slides get a themed title frame plus each region placed
        as its own picture at its x/y/w/h box.
      - `text` slides — and any slide still missing a render — become
        NATIVE editable text (title + bullets) themed from the deck
        concept's palette.
    The slide size follows the deck's `aspect_ratio`.
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
    hybrid_slides = 0
    with tempfile.TemporaryDirectory() as tmpd:
        for s in slides:
            slide = prs.slides.add_slide(blank_layout)
            mode = s.get("render_mode") or "code-shape"
            if mode == "hybrid":
                n_missing = _add_hybrid_slide(
                    slide, s, state, tmpd, sw=sw, sh=sh,
                    accent=accent, fg=fg, bg=bg,
                    Inches=Inches, Pt=Pt, MSO_SHAPE=MSO_SHAPE,
                )
                hybrid_slides += 1
                if n_missing:
                    missing_renders.append(s.get("slide_number") or 0)
            else:
                blob = (
                    state.backend.get_blob(s["image_blob_path"])
                    if s.get("image_blob_path") else None
                )
                if blob:
                    tmp = pathlib.Path(tmpd) / f"slide_{s['id']}.png"
                    tmp.write_bytes(blob)
                    _add_fitted_picture(slide, str(tmp),
                                        left=0, top=0, box_w=sw, box_h=sh)
                    image_slides += 1
                else:
                    # Native editable text slide — a `text` slide by design,
                    # or a not-yet-rendered slide degraded gracefully.
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
        "hybrid_slides": hybrid_slides,
        "missing_renders": missing_renders,
        "local_path": str(out),
        "blob_path": pptx_blob,
        "pdf_local_path": str(pdf_path) if pdf_path else None,
        "pdf_blob_path": pdf_blob,
        "pdf_skipped": pdf_path is None,
        "size_bytes": os.path.getsize(out),
    }
