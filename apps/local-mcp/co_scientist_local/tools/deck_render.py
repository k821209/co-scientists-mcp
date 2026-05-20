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

`export_deck_to_pptx` collects every rendered slide and emits a .pptx
via python-pptx — one slide per deck slide, embedded PNG + title + speaker
notes. Lazy-imports python-pptx so the optional dep stays optional.
"""
from __future__ import annotations

import os
import pathlib
import re
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
    # Mark deck rendered when every slide has an image_blob_path.
    refreshed = _decks.list_slides(state, slug, deck_id)
    all_rendered = all(s.get("image_blob_path") for s in refreshed)
    if all_rendered:
        _decks.update_deck(state, slug, deck_id, status="rendered")
    return results


# ─── PPTX export ─────────────────────────────────────────────────────────────


def export_deck_to_pptx(
    state: State,
    slug: str,
    deck_id: str,
    *,
    output_path: str,
) -> dict:
    """Build a .pptx from every slide that has a rendered image.

    Layout: one PPTX slide per deck slide, blank background with the
    image centered + the slide title in a top text box + speaker notes
    on the notes pane. python-pptx ships in the base install.
    """
    try:
        from pptx import Presentation         # type: ignore
        from pptx.util import Inches, Pt      # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "python-pptx not installed — reinstall the package: "
            "pip install -e ~/co-scientists-mcp/apps/local-mcp"
        ) from e

    deck = _decks.get_deck(state, slug, deck_id)
    slides = _decks.list_slides(state, slug, deck_id)
    if not slides:
        raise ValueError(f"deck {deck_id!r} has no slides")

    prs = Presentation()
    prs.slide_width = Inches(13.333)   # 16:9 widescreen
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    missing_renders: list[int] = []
    with tempfile.TemporaryDirectory() as tmpd:
        for s in slides:
            slide = prs.slides.add_slide(blank_layout)
            # Title box (top center)
            if s.get("title"):
                tx = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12.3), Inches(0.7))
                tx.text_frame.text = s["title"]
                for para in tx.text_frame.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(28)
                        run.font.bold = True
            # Image (centered, below title)
            blob = state.backend.get_blob(s["image_blob_path"]) if s.get("image_blob_path") else None
            if blob:
                tmp = pathlib.Path(tmpd) / f"slide_{s['id']}.png"
                tmp.write_bytes(blob)
                slide.shapes.add_picture(
                    str(tmp),
                    Inches(0.5), Inches(1.0),
                    width=Inches(12.3), height=Inches(6.0),
                )
            else:
                missing_renders.append(s.get("slide_number") or 0)
                placeholder = slide.shapes.add_textbox(
                    Inches(0.5), Inches(3.0), Inches(12.3), Inches(2.0)
                )
                placeholder.text_frame.text = (
                    f"[unrendered slide — body:]\n\n{s.get('body') or '(empty)'}"
                )
            # Speaker notes
            if s.get("notes"):
                slide.notes_slide.notes_text_frame.text = s["notes"]

    out = pathlib.Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))

    blob_path = state.project_path(
        "papers", slug, "decks", deck_id, "exports", out.name,
    )
    with open(out, "rb") as f:
        data = f.read()
    state.backend.put_blob(blob_path, data)

    # Index the export so the dashboard's Presentation tab can list it.
    export_doc_path = state.project_path(
        "papers", slug, "decks", deck_id, "exports", out.name,
    )
    now = now_iso()
    state.backend.set_doc(export_doc_path, {
        "filename": out.name,
        "blob_path": blob_path,
        "size_bytes": len(data),
        "slide_count": len(slides),
        "missing_renders": missing_renders,
        "created_at": now,
    })

    return {
        "deck_id": deck_id,
        "deck_title": deck.get("title"),
        "slide_count": len(slides),
        "missing_renders": missing_renders,
        "local_path": str(out),
        "blob_path": blob_path,
        "size_bytes": os.path.getsize(out),
    }
