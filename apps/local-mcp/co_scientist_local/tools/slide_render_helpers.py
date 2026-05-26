"""Helpers exposed to a slide's `code` field at PPTX export time
(docs/todo/002).

A slide with `render_mode='code'` carries a `code` field that is a
python-pptx snippet. The exporter `exec`s that code in a namespace where
the slide object, theme primitives, python-pptx imports, and these
helpers are pre-bound — so the snippet can compose the slide natively
without dragging in boilerplate.

The static helpers in this module don't need the runtime state (Storage
/ Firestore). Image-loading helpers that DO need state are constructed
per-slide as closures in `deck_render._build_code_namespace` and added
to the same `h` namespace.

Design intent: keep these helpers thin. They cover the boilerplate the
agent would otherwise repeat per slide (accent stripe, themed title,
bullet column, card / card-grid), so per-slide code can focus on the
layout that distinguishes that slide.

Usage shape inside a slide's `code` field:

    h.accent_stripe(slide)
    h.title_block(slide, title)
    h.card_grid(slide, [
        {"title": "Memory", "body": "decisions stack across sessions"},
        {"title": "Hooks",  "body": "run on specific events"},
        {"title": "Slash",  "body": "reusable commands"},
        {"title": "Context","body": "what the LLM is looking at"},
    ], left=Inches(0.7), top=Inches(1.9),
       width=sw - Inches(1.4), height=sh - Inches(2.3),
       cols=2)
"""
from __future__ import annotations

from pptx.util import Inches, Pt  # type: ignore
from pptx.enum.shapes import MSO_SHAPE  # type: ignore
from pptx.enum.text import MSO_AUTO_SIZE, MSO_ANCHOR, PP_ALIGN  # type: ignore


def _autoshrink(tf) -> None:
    try:
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_SHAPE
    except Exception:
        pass


def accent_stripe(slide, *, palette, sw, height_in: float = 0.16):
    """Top accent stripe — the deck's signature horizontal bar."""
    stripe = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, sw, Inches(height_in),
    )
    stripe.line.fill.background()
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = palette["accent"]
    stripe.shadow.inherit = False
    return stripe


def title_block(slide, text: str, *, palette, fonts, type_scale, sw, sh,
                left=None, top=None, width=None, height=None,
                cover: bool = False, accent_rule: bool = True):
    """A themed title textbox.

    cover=False (default): top-anchored content-slide title at
    Inches(0.7), Inches(0.45). A short accent rule sits beneath when
    accent_rule=True.

    cover=True: vertically + horizontally centered, no rule, larger
    type. Use for `role='title'` slides.
    """
    if cover:
        left = Inches(1.0) if left is None else left
        top = Inches(0.5) if top is None else top
        width = sw - Inches(2.0) if width is None else width
        height = sh - Inches(1.0) if height is None else height
        box = slide.shapes.add_textbox(left, top, width, height)
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        _autoshrink(tf)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        p.line_spacing = 1.1
        run = p.add_run()
        run.text = text or ""
        run.font.size = Pt(type_scale.get("cover_title", 40))
        run.font.bold = True
        run.font.color.rgb = palette["foreground"]
        if fonts.get("display"):
            run.font.name = fonts["display"]
        return box

    left = Inches(0.7) if left is None else left
    top = Inches(0.45) if top is None else top
    width = sw - Inches(1.4) if width is None else width
    height = Inches(1.0) if height is None else height
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    _autoshrink(tf)
    p = tf.paragraphs[0]
    p.line_spacing = 1.05
    run = p.add_run()
    run.text = text or ""
    run.font.size = Pt(type_scale.get("title", 32))
    run.font.bold = True
    run.font.color.rgb = palette["foreground"]
    if fonts.get("display"):
        run.font.name = fonts["display"]
    if accent_rule:
        rule = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left + Inches(0.02),
            top + height + Pt(2), Inches(2.2), Pt(4),
        )
        rule.line.fill.background()
        rule.fill.solid()
        rule.fill.fore_color.rgb = palette["accent"]
        rule.shadow.inherit = False
    return box


def bullet_list(slide, items, *, palette, fonts, type_scale,
                left, top, width, height, bullet: str = "•"):
    """A vertical bulleted list. `items` is a list of strings; each
    becomes one paragraph at the deck's body type. Pass bullet="" for
    a plain paragraph list."""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    _autoshrink(tf)
    body_pt = type_scale.get("body", 20)
    line_spacing = type_scale.get("line_spacing", 1.22)
    first = True
    for item in items:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.line_spacing = line_spacing
        para.space_after = Pt(4)
        run = para.add_run()
        run.text = f"{bullet} {item}" if bullet else str(item)
        run.font.size = Pt(body_pt)
        run.font.color.rgb = palette["foreground"]
        if fonts.get("body"):
            run.font.name = fonts["body"]
    return box


def card(slide, *, left, top, width, height, title: str, body: str,
         palette, fonts, type_scale,
         accent_top: bool = True, accent_height_pt: int = 4):
    """A single titled card: rectangle + optional top accent stripe +
    title (bold) + body. Returns dict(card, title_box, body_box)."""
    bg = palette.get("surface", palette["background"])
    border = palette["accent"]
    card_shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top, width, height,
    )
    card_shape.fill.solid()
    card_shape.fill.fore_color.rgb = bg
    card_shape.line.color.rgb = border
    card_shape.line.width = Pt(0.75)
    card_shape.shadow.inherit = False

    if accent_top:
        stripe = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top, width, Pt(accent_height_pt),
        )
        stripe.line.fill.background()
        stripe.fill.solid()
        stripe.fill.fore_color.rgb = palette["accent"]
        stripe.shadow.inherit = False

    title_pt = max(14, type_scale.get("head", 26) - 4)
    body_pt = max(12, type_scale.get("body", 20) - 4)
    pad = Pt(10)
    title_h = Pt(int(title_pt * 1.6))

    tb = slide.shapes.add_textbox(
        left + pad, top + pad, width - 2 * pad, title_h,
    )
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = title or ""
    run.font.size = Pt(title_pt)
    run.font.bold = True
    run.font.color.rgb = palette["foreground"]
    if fonts.get("display"):
        run.font.name = fonts["display"]

    bb = slide.shapes.add_textbox(
        left + pad, top + pad + title_h,
        width - 2 * pad, height - 2 * pad - title_h,
    )
    bf = bb.text_frame
    bf.word_wrap = True
    _autoshrink(bf)
    if body:
        p = bf.paragraphs[0]
        p.line_spacing = type_scale.get("line_spacing", 1.22)
        run = p.add_run()
        run.text = body
        run.font.size = Pt(body_pt)
        run.font.color.rgb = palette["foreground"]
        if fonts.get("body"):
            run.font.name = fonts["body"]
    return {"card": card_shape, "title_box": tb, "body_box": bb}


def card_grid(slide, items, *, left, top, width, height,
              palette, fonts, type_scale,
              cols: int = 2, gap_pt: int = 12):
    """Lay out `items` (list of dicts with `title` + `body`) as a grid
    of `card()`s with `cols` columns. Rows are derived from len(items).
    Returns the list of per-card dicts."""
    n = len(items)
    if n == 0:
        return []
    rows = (n + cols - 1) // cols
    gap = Pt(gap_pt)
    cell_w = (width - gap * (cols - 1)) // cols
    cell_h = (height - gap * (rows - 1)) // rows
    out = []
    for i, item in enumerate(items):
        r, c = i // cols, i % cols
        cl = left + c * (cell_w + gap)
        ct = top + r * (cell_h + gap)
        out.append(card(
            slide, left=cl, top=ct, width=cell_w, height=cell_h,
            title=item.get("title", ""), body=item.get("body", ""),
            palette=palette, fonts=fonts, type_scale=type_scale,
        ))
    return out


def pull_quote(slide, text: str, *, palette, fonts, type_scale,
               left, top, width, height,
               bar_pt: int = 4, gap_pt: int = 10):
    """An emphasis block: vertical accent bar + italic text. Use for a
    punchline / take-home line you want the audience to focus on."""
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top, Pt(bar_pt), height,
    )
    bar.line.fill.background()
    bar.fill.solid()
    bar.fill.fore_color.rgb = palette["accent"]
    bar.shadow.inherit = False
    body_pt = type_scale.get("body", 20)
    quote_pt = max(body_pt, int(body_pt * 1.1))
    tb = slide.shapes.add_textbox(
        left + Pt(bar_pt) + Pt(gap_pt), top,
        width - Pt(bar_pt) - Pt(gap_pt), height,
    )
    tf = tb.text_frame
    tf.word_wrap = True
    _autoshrink(tf)
    first = True
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.line_spacing = type_scale.get("line_spacing", 1.22)
        run = p.add_run()
        run.text = line.strip()
        run.font.size = Pt(quote_pt)
        run.font.italic = True
        run.font.color.rgb = palette["foreground"]
        if fonts.get("body"):
            run.font.name = fonts["body"]
    return {"bar": bar, "text_box": tb}
