"""Whole-slide design patterns for `code` slides (todo 004 §B).

A *pattern* is a complete slide layout — not a primitive — that encodes
a designer's compositional decisions (grid position, type hierarchy,
whitespace ratio, color use, visual storytelling device). The agent
picks a pattern that fits the slide's *intent* and passes content;
the pattern handles the design.

Patterns are bound as `p.*` in the `code` slide exec namespace. Each
function paints directly onto the slide and returns None (or a small
summary dict). All theme inputs (`palette`, `fonts`, `type_scale`,
`sw`, `sh`) follow the same calling convention as `h.*` helpers.

Pattern catalog (todo 004 §B):

  hero_with_trailing_evidence — thesis / takeaway slide
  chapter_divider             — section opener
  metric_tile_row             — KPI / quantitative summary
  evidence_stack              — claim + 2-3 supporting facts
  flow_pipeline               — workflow / process steps
  before_after_split          — risk-vs-mitigation, old-vs-new
  contrast_pair               — two competing options
  quadrant_map                — comparative landscape with axes
  numbered_milestone_arc      — progressive timeline (Era I/II/III)
  zoom_in_callout             — focus on a region of a complex figure
"""
from __future__ import annotations

from pptx.util import Inches, Pt          # type: ignore
from pptx.enum.shapes import MSO_SHAPE    # type: ignore
from pptx.enum.text import (              # type: ignore
    MSO_AUTO_SIZE, MSO_ANCHOR, PP_ALIGN,
)
from pptx.dml.color import RGBColor       # type: ignore

from . import slide_render_helpers as _h


# ─── shared internals ────────────────────────────────────────────────────


def _muted(fg) -> RGBColor:
    """A muted version of the foreground color for secondary labels.
    We can't mix RGB without knowing intent, so we approximate: pull
    luminance halfway toward gray. Falls back to #6c757d."""
    try:
        r, g, b = fg
        mid = (r + g + b) // 3
        return RGBColor(
            int((r + mid * 2) // 3),
            int((g + mid * 2) // 3),
            int((b + mid * 2) // 3),
        )
    except Exception:
        return RGBColor(0x6C, 0x75, 0x7D)


def _emit_text(slide, text, *, left, top, width, height,
               size_pt: int, color, font_name=None, bold: bool = False,
               italic: bool = False, align=None, anchor=None,
               line_spacing: float = 1.2):
    """Add a textbox with a single styled run. Returns the textbox."""
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    _h._autoshrink(tf)
    if anchor is not None:
        tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.line_spacing = line_spacing
    if align is not None:
        p.alignment = align
    run = p.add_run()
    run.text = text or ""
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    if font_name:
        run.font.name = font_name
    return tb


def _accent_rule(slide, *, left, top, width, height, color):
    rect = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top, width, height,
    )
    rect.line.fill.background()
    rect.fill.solid()
    rect.fill.fore_color.rgb = color
    rect.shadow.inherit = False
    return rect


# ─── 1. hero_with_trailing_evidence ───────────────────────────────────────


def hero_with_trailing_evidence(slide, *, headline: str,
                                 evidence: list[str],
                                 palette, fonts, type_scale, sw, sh):
    """Thesis / takeaway slide. Massive headline upper-left (display
    type, ~half slide width), evidence as a vertical column on the right
    in fine print. The asymmetry is intentional — left-aligned headline
    + right column creates tension that earns the contrast."""
    headline_pt = max(36, type_scale.get("cover_title", 40) - 4)
    body_pt = type_scale.get("body", 20) - 2
    label_pt = type_scale.get("caption", 12)

    _accent_rule(slide, left=Inches(0.7), top=Inches(0.8),
                 width=Inches(0.5), height=Pt(6),
                 color=palette["accent"])
    _emit_text(slide, headline,
               left=Inches(0.7), top=Inches(1.0),
               width=Inches(7.6), height=Inches(4.5),
               size_pt=headline_pt, color=palette["foreground"],
               font_name=fonts.get("display"), bold=True,
               line_spacing=1.05)

    # Evidence column on the right
    ev_left = Inches(8.6)
    ev_top = Inches(1.5)
    ev_w = sw - ev_left - Inches(0.6)
    ev_h_each = Pt(body_pt * 2.6)
    fg_muted = _muted(palette["foreground"])
    _emit_text(slide, "EVIDENCE",
               left=ev_left, top=ev_top,
               width=ev_w, height=Pt(label_pt * 2),
               size_pt=label_pt, color=palette["accent"],
               font_name=fonts.get("body"), bold=True)
    for i, line in enumerate(evidence):
        y = ev_top + Pt(label_pt * 2.8) + i * (ev_h_each + Pt(4))
        # Thin accent number
        _emit_text(slide, f"{i + 1:02d}",
                   left=ev_left, top=y,
                   width=Pt(36), height=ev_h_each,
                   size_pt=int(body_pt * 0.85), color=palette["accent"],
                   font_name=fonts.get("display"), bold=True)
        _emit_text(slide, line,
                   left=ev_left + Pt(36), top=y,
                   width=ev_w - Pt(36), height=ev_h_each,
                   size_pt=body_pt, color=fg_muted,
                   font_name=fonts.get("body"))


# ─── 2. chapter_divider ───────────────────────────────────────────────────


def chapter_divider(slide, *, chapter_label: str, summary: str = "",
                    palette, fonts, type_scale, sw, sh):
    """Section opener. Massive chapter number / name in the centre-left,
    optional one-line summary tagline below. Massive whitespace right —
    no body content. Distinct rhythm from interior slides so the
    audience feels the section break."""
    label_pt = type_scale.get("cover_title", 40)
    summary_pt = type_scale.get("head", 26) - 2

    _accent_rule(slide, left=Inches(0.9), top=Inches(2.8),
                 width=Inches(1.4), height=Pt(8),
                 color=palette["accent"])
    _emit_text(slide, chapter_label,
               left=Inches(0.9), top=Inches(3.0),
               width=Inches(9.0), height=Inches(2.0),
               size_pt=label_pt + 8, color=palette["foreground"],
               font_name=fonts.get("display"), bold=True,
               line_spacing=1.0)
    if summary:
        fg_muted = _muted(palette["foreground"])
        _emit_text(slide, summary,
                   left=Inches(0.9), top=Inches(4.5),
                   width=Inches(9.0), height=Inches(1.5),
                   size_pt=summary_pt, color=fg_muted,
                   font_name=fonts.get("body"),
                   italic=True, line_spacing=1.25)


# ─── 3. metric_tile_row ───────────────────────────────────────────────────


def metric_tile_row(slide, *, tiles: list[tuple],
                    palette, fonts, type_scale, sw, sh,
                    top=None, height=None):
    """KPI / quantitative summary. A row of large numbers with thin
    labels under each. `tiles` is a list of (value, label) or
    (value, label, unit) tuples — typically 3-5 items.

    Renders the value in display type (huge), unit in smaller accent
    type adjacent, label in caption type below. All tile widths are
    equal; the row centers within the available width.
    """
    if not tiles:
        return
    top = Inches(2.5) if top is None else top
    height = Inches(3.0) if height is None else height
    side_margin = Inches(0.7)
    usable = sw - 2 * side_margin
    gap = Pt(_h.SPACING_UNIT_PT * 3)
    tile_w = (usable - gap * (len(tiles) - 1)) // len(tiles)

    value_pt = max(48, type_scale.get("cover_title", 40) + 8)
    unit_pt = type_scale.get("head", 26)
    label_pt = type_scale.get("caption", 12)

    fg_muted = _muted(palette["foreground"])
    for i, tile in enumerate(tiles):
        if len(tile) == 3:
            value, label, unit = tile
        else:
            value, label = tile
            unit = ""
        left = side_margin + i * (tile_w + gap)
        # Value (huge number, accent color)
        _emit_text(slide, str(value),
                   left=left, top=top,
                   width=tile_w, height=Pt(value_pt * 1.2),
                   size_pt=value_pt, color=palette["accent"],
                   font_name=fonts.get("display"), bold=True,
                   align=PP_ALIGN.CENTER, line_spacing=1.0)
        if unit:
            _emit_text(slide, unit,
                       left=left, top=top + Pt(value_pt * 1.3),
                       width=tile_w, height=Pt(unit_pt * 1.5),
                       size_pt=unit_pt, color=palette["foreground"],
                       font_name=fonts.get("body"),
                       align=PP_ALIGN.CENTER)
        # Label (small, muted)
        label_top = top + height - Pt(label_pt * 2.5)
        _emit_text(slide, label,
                   left=left, top=label_top,
                   width=tile_w, height=Pt(label_pt * 2.5),
                   size_pt=label_pt, color=fg_muted,
                   font_name=fonts.get("body"),
                   align=PP_ALIGN.CENTER)


# ─── 4. evidence_stack ────────────────────────────────────────────────────


def evidence_stack(slide, *, claim: str, evidence: list[dict],
                   palette, fonts, type_scale, sw, sh):
    """Claim + 2-3 supporting facts. Top: claim in display type. Bottom:
    stacked evidence rows, each with a small accent tag-pill on the left
    + body text on the right.

    `evidence` items: {"tag": str, "body": str} (or just `body` and the
    pill is left blank).
    """
    claim_pt = max(28, type_scale.get("head", 26) + 4)
    tag_pt = type_scale.get("caption", 12)
    body_pt = type_scale.get("body", 20)

    _emit_text(slide, claim,
               left=Inches(0.7), top=Inches(1.0),
               width=sw - Inches(1.4), height=Inches(1.8),
               size_pt=claim_pt, color=palette["foreground"],
               font_name=fonts.get("display"), bold=True,
               line_spacing=1.15)
    _accent_rule(slide, left=Inches(0.7), top=Inches(2.85),
                 width=Inches(3.0), height=Pt(4),
                 color=palette["accent"])

    stack_top = Inches(3.2)
    row_h = (sh - stack_top - Inches(0.6)) // max(1, len(evidence))
    tag_w = Inches(1.6)
    fg_muted = _muted(palette["foreground"])
    for i, item in enumerate(evidence):
        y = stack_top + i * row_h
        tag = (item.get("tag") or "").upper()
        body = item.get("body") or ""
        if tag:
            pill = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(0.7), y + Pt(8),
                tag_w, Pt(tag_pt * 1.8),
            )
            pill.line.fill.background()
            pill.fill.solid()
            pill.fill.fore_color.rgb = palette["accent"]
            pill.shadow.inherit = False
            ptf = pill.text_frame
            ptf.margin_left = Pt(8)
            ptf.margin_right = Pt(8)
            pp = ptf.paragraphs[0]
            pp.alignment = PP_ALIGN.CENTER
            run = pp.add_run()
            run.text = tag
            run.font.size = Pt(tag_pt)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            if fonts.get("body"):
                run.font.name = fonts["body"]
        _emit_text(slide, body,
                   left=Inches(0.7) + tag_w + Pt(12), top=y + Pt(4),
                   width=sw - Inches(1.4) - tag_w - Pt(12),
                   height=row_h - Pt(8),
                   size_pt=body_pt, color=fg_muted,
                   font_name=fonts.get("body"),
                   anchor=MSO_ANCHOR.TOP)


# ─── 5. flow_pipeline ─────────────────────────────────────────────────────


def flow_pipeline(slide, *, steps: list[dict],
                  palette, fonts, type_scale, sw, sh):
    """Horizontal process flow. Each step is a small card with a tag
    label + body. Arrows (right-pointing) connect consecutive steps.
    `steps` items: {"tag": str, "body": str}.
    """
    if not steps:
        return
    side = Inches(0.7)
    top = Inches(2.2)
    height = Inches(3.4)
    n = len(steps)
    gap = Inches(0.3)
    arrow_w = Pt(_h.SPACING_UNIT_PT * 5)
    usable = sw - 2 * side - arrow_w * (n - 1) - gap * (n - 1)
    step_w = usable // n

    tag_pt = type_scale.get("head", 26) - 4
    body_pt = type_scale.get("body", 20) - 2
    fg_muted = _muted(palette["foreground"])

    for i, step in enumerate(steps):
        left = side + i * (step_w + arrow_w + gap)
        # Step card
        card = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top, step_w, height,
        )
        card.fill.solid()
        card.fill.fore_color.rgb = palette["background"]
        card.line.color.rgb = palette["accent"]
        card.line.width = Pt(0.75)
        card.shadow.inherit = False
        # Top accent stripe
        _accent_rule(slide, left=left, top=top,
                     width=step_w, height=Pt(4),
                     color=palette["accent"])
        # Step number
        _emit_text(slide, f"{i + 1:02d}",
                   left=left + Pt(12), top=top + Pt(12),
                   width=step_w - Pt(24), height=Pt(tag_pt * 1.2),
                   size_pt=int(tag_pt * 0.7),
                   color=palette["accent"],
                   font_name=fonts.get("display"), bold=True)
        # Tag
        _emit_text(slide, step.get("tag") or "",
                   left=left + Pt(12), top=top + Pt(tag_pt * 1.6),
                   width=step_w - Pt(24), height=Pt(tag_pt * 1.5),
                   size_pt=tag_pt, color=palette["foreground"],
                   font_name=fonts.get("display"), bold=True)
        # Body
        _emit_text(slide, step.get("body") or "",
                   left=left + Pt(12), top=top + Pt(tag_pt * 3.4),
                   width=step_w - Pt(24),
                   height=height - Pt(tag_pt * 3.6),
                   size_pt=body_pt, color=fg_muted,
                   font_name=fonts.get("body"))
        # Arrow to the next step
        if i < n - 1:
            ax = left + step_w + gap // 2
            ay = top + height // 2 - Pt(8)
            arrow = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW,
                ax, ay, arrow_w, Pt(16),
            )
            arrow.line.fill.background()
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = palette["accent"]
            arrow.shadow.inherit = False


# ─── 6. before_after_split ────────────────────────────────────────────────


def before_after_split(slide, *, before: dict, after: dict,
                       transition_label: str = "",
                       palette, fonts, type_scale, sw, sh):
    """Two-panel comparison. Left = muted/before, right = accent/after.
    A single arrow + optional label between them. Asymmetry on weight
    (after is visually heavier) earns the contrast.

    Each panel: {"title": str, "body": str}.
    """
    side = Inches(0.7)
    top = Inches(2.0)
    height = Inches(4.4)
    arrow_w = Inches(0.9)
    panel_w = (sw - 2 * side - arrow_w) // 2

    title_pt = type_scale.get("head", 26)
    body_pt = type_scale.get("body", 20) - 2
    fg = palette["foreground"]
    fg_muted = _muted(fg)

    # Before (muted)
    bcard = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, side, top, panel_w, height,
    )
    bcard.fill.solid()
    bcard.fill.fore_color.rgb = palette["background"]
    bcard.line.color.rgb = fg_muted
    bcard.line.width = Pt(0.5)
    bcard.shadow.inherit = False
    _emit_text(slide, before.get("title") or "BEFORE",
               left=side + Pt(20), top=top + Pt(20),
               width=panel_w - Pt(40), height=Pt(title_pt * 1.5),
               size_pt=title_pt, color=fg_muted,
               font_name=fonts.get("display"), bold=True)
    _emit_text(slide, before.get("body") or "",
               left=side + Pt(20), top=top + Pt(title_pt * 1.7),
               width=panel_w - Pt(40),
               height=height - Pt(title_pt * 2),
               size_pt=body_pt, color=fg_muted,
               font_name=fonts.get("body"))

    # Arrow + transition label
    arrow_left = side + panel_w
    arrow_top = top + height // 2 - Pt(12)
    arrow = slide.shapes.add_shape(
        MSO_SHAPE.RIGHT_ARROW, arrow_left, arrow_top,
        arrow_w, Pt(24),
    )
    arrow.line.fill.background()
    arrow.fill.solid()
    arrow.fill.fore_color.rgb = palette["accent"]
    arrow.shadow.inherit = False
    if transition_label:
        _emit_text(slide, transition_label,
                   left=arrow_left, top=arrow_top - Pt(28),
                   width=arrow_w, height=Pt(20),
                   size_pt=type_scale.get("caption", 12),
                   color=palette["accent"],
                   font_name=fonts.get("body"), bold=True,
                   align=PP_ALIGN.CENTER)

    # After (vibrant — accent border + accent stripe at top)
    aleft = arrow_left + arrow_w
    acard = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, aleft, top, panel_w, height,
    )
    acard.fill.solid()
    acard.fill.fore_color.rgb = palette["background"]
    acard.line.color.rgb = palette["accent"]
    acard.line.width = Pt(1.5)
    acard.shadow.inherit = False
    _accent_rule(slide, left=aleft, top=top,
                 width=panel_w, height=Pt(6),
                 color=palette["accent"])
    _emit_text(slide, after.get("title") or "AFTER",
               left=aleft + Pt(20), top=top + Pt(20),
               width=panel_w - Pt(40), height=Pt(title_pt * 1.5),
               size_pt=title_pt, color=palette["foreground"],
               font_name=fonts.get("display"), bold=True)
    _emit_text(slide, after.get("body") or "",
               left=aleft + Pt(20), top=top + Pt(title_pt * 1.7),
               width=panel_w - Pt(40),
               height=height - Pt(title_pt * 2),
               size_pt=body_pt, color=palette["foreground"],
               font_name=fonts.get("body"))


# ─── 7. contrast_pair ─────────────────────────────────────────────────────


def contrast_pair(slide, *, left_item: dict, right_item: dict,
                  axis_label: str = "",
                  palette, fonts, type_scale, sw, sh):
    """Two competing options framed by an axis. Mirrored boxes; an axis
    label sits above (e.g. 'cost', 'risk', 'expressivity'). Different
    from before_after_split — both sides are equally weighted; the
    question is which one *for your case*.

    Items: {"title": str, "pros": list[str], "cons": list[str]}.
    """
    side = Inches(0.7)
    top = Inches(1.9)
    panel_w = (sw - 2 * side - Inches(0.3)) // 2
    height = Inches(4.7)
    title_pt = type_scale.get("head", 26)
    body_pt = type_scale.get("body", 20) - 2
    fg_muted = _muted(palette["foreground"])

    if axis_label:
        _emit_text(slide, axis_label.upper(),
                   left=side, top=Inches(1.4),
                   width=sw - 2 * side, height=Pt(20),
                   size_pt=type_scale.get("caption", 12),
                   color=palette["accent"],
                   font_name=fonts.get("body"), bold=True,
                   align=PP_ALIGN.CENTER)

    for i, item in enumerate((left_item, right_item)):
        x = side + i * (panel_w + Inches(0.3))
        card = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, x, top, panel_w, height,
        )
        card.fill.solid()
        card.fill.fore_color.rgb = palette["background"]
        card.line.color.rgb = palette["accent"]
        card.line.width = Pt(0.75)
        card.shadow.inherit = False
        # Title
        _emit_text(slide, item.get("title") or "",
                   left=x + Pt(20), top=top + Pt(20),
                   width=panel_w - Pt(40),
                   height=Pt(title_pt * 1.6),
                   size_pt=title_pt, color=palette["foreground"],
                   font_name=fonts.get("display"), bold=True)
        # Pros
        pros = item.get("pros") or []
        cons = item.get("cons") or []
        y = top + Pt(title_pt * 1.9)
        if pros:
            _emit_text(slide, "PROS",
                       left=x + Pt(20), top=y,
                       width=panel_w - Pt(40), height=Pt(16),
                       size_pt=type_scale.get("caption", 12),
                       color=palette["accent"],
                       font_name=fonts.get("body"), bold=True)
            y = y + Pt(22)
            for ln in pros:
                _emit_text(slide, "+ " + ln,
                           left=x + Pt(20), top=y,
                           width=panel_w - Pt(40),
                           height=Pt(body_pt * 1.8),
                           size_pt=body_pt, color=palette["foreground"],
                           font_name=fonts.get("body"))
                y = y + Pt(body_pt * 1.8)
        if cons:
            y = y + Pt(8)
            _emit_text(slide, "CONS",
                       left=x + Pt(20), top=y,
                       width=panel_w - Pt(40), height=Pt(16),
                       size_pt=type_scale.get("caption", 12),
                       color=fg_muted,
                       font_name=fonts.get("body"), bold=True)
            y = y + Pt(22)
            for ln in cons:
                _emit_text(slide, "− " + ln,
                           left=x + Pt(20), top=y,
                           width=panel_w - Pt(40),
                           height=Pt(body_pt * 1.8),
                           size_pt=body_pt, color=fg_muted,
                           font_name=fonts.get("body"))
                y = y + Pt(body_pt * 1.8)


# ─── 8. quadrant_map ──────────────────────────────────────────────────────


def quadrant_map(slide, *, items: list[dict], axes: dict,
                 palette, fonts, type_scale, sw, sh):
    """2×2 conceptual map. Items are positioned by their (x, y) in
    [0, 1] (origin bottom-left). Axes carry labels and an optional
    explanation. Useful for "is X high/low on cost AND high/low on
    impact" comparisons.

    items: [{"label": str, "x": float, "y": float}]
    axes: {"x": str, "y": str, "x_low": str?, "x_high": str?,
           "y_low": str?, "y_high": str?}
    """
    pad = Inches(1.2)
    map_left = Inches(1.6)
    map_top = Inches(1.5)
    map_w = sw - map_left - pad
    map_h = sh - map_top - Inches(1.0)

    # Axes — vertical (Y) on the left, horizontal (X) on the bottom
    accent = palette["accent"]
    fg = palette["foreground"]
    fg_muted = _muted(fg)
    cap_pt = type_scale.get("caption", 12)
    label_pt = type_scale.get("body", 20) - 4

    # Vertical axis line
    _accent_rule(slide, left=map_left, top=map_top,
                 width=Pt(2), height=map_h, color=fg_muted)
    # Horizontal axis line
    _accent_rule(slide, left=map_left, top=map_top + map_h - Pt(2),
                 width=map_w, height=Pt(2), color=fg_muted)
    # Cross at the center (so 4 quadrants are clear)
    cx = map_left + map_w // 2
    cy = map_top + map_h // 2
    _accent_rule(slide, left=cx, top=map_top,
                 width=Pt(1), height=map_h, color=fg_muted)
    _accent_rule(slide, left=map_left, top=cy,
                 width=map_w, height=Pt(1), color=fg_muted)

    # Axis labels
    _emit_text(slide, axes.get("x") or "",
               left=map_left, top=map_top + map_h + Pt(8),
               width=map_w, height=Pt(label_pt * 1.5),
               size_pt=label_pt, color=fg,
               font_name=fonts.get("body"), bold=True,
               align=PP_ALIGN.CENTER)
    if axes.get("x_low"):
        _emit_text(slide, axes["x_low"],
                   left=map_left, top=map_top + map_h - Pt(4),
                   width=map_w // 2, height=Pt(cap_pt * 1.5),
                   size_pt=cap_pt, color=fg_muted,
                   font_name=fonts.get("body"))
    if axes.get("x_high"):
        _emit_text(slide, axes["x_high"],
                   left=cx, top=map_top + map_h - Pt(4),
                   width=map_w // 2, height=Pt(cap_pt * 1.5),
                   size_pt=cap_pt, color=fg_muted,
                   font_name=fonts.get("body"),
                   align=PP_ALIGN.RIGHT)
    # Vertical axis label — rotated would be best, but python-pptx
    # rotation is finicky; place it above the line for legibility.
    _emit_text(slide, axes.get("y") or "",
               left=Inches(0.3), top=map_top - Pt(label_pt * 1.5) - 4,
               width=Inches(1.6), height=Pt(label_pt * 1.5),
               size_pt=label_pt, color=fg,
               font_name=fonts.get("body"), bold=True)

    # Items
    for item in items:
        x = max(0.0, min(1.0, item.get("x", 0.5)))
        y = max(0.0, min(1.0, item.get("y", 0.5)))
        # y is bottom-origin in spec; flip for PPTX (top-origin)
        px = map_left + int(map_w * x)
        py = map_top + int(map_h * (1.0 - y))
        dot_r = Pt(8)
        dot = slide.shapes.add_shape(
            MSO_SHAPE.OVAL, px - dot_r, py - dot_r, dot_r * 2, dot_r * 2,
        )
        dot.line.fill.background()
        dot.fill.solid()
        dot.fill.fore_color.rgb = accent
        dot.shadow.inherit = False
        _emit_text(slide, item.get("label") or "",
                   left=px + Pt(8), top=py - Pt(label_pt),
                   width=Inches(2.4), height=Pt(label_pt * 1.8),
                   size_pt=cap_pt, color=fg,
                   font_name=fonts.get("body"))


# ─── 9. numbered_milestone_arc ────────────────────────────────────────────


def numbered_milestone_arc(slide, *, milestones: list[dict],
                            palette, fonts, type_scale, sw, sh):
    """Progressive timeline. Numbered markers (1, 2, 3, …) along a
    horizontal line; each marker has a brief tag + note above/below
    alternating. Visual weight progresses from light (early) to
    accent-saturated (late) so the audience sees direction.

    milestones: [{"tag": str, "note": str}].
    """
    if not milestones:
        return
    n = len(milestones)
    side = Inches(0.8)
    line_y = sh // 2 + Inches(0.3)
    line_w = sw - 2 * side
    # Base timeline
    _accent_rule(slide, left=side, top=line_y,
                 width=line_w, height=Pt(3),
                 color=_muted(palette["foreground"]))

    fg = palette["foreground"]
    fg_muted = _muted(fg)
    tag_pt = type_scale.get("head", 26) - 4
    note_pt = type_scale.get("body", 20) - 4
    accent = palette["accent"]

    for i, m in enumerate(milestones):
        # Position along the line
        x = side + int(line_w * (i / max(1, n - 1))) if n > 1 else side + line_w // 2
        # Marker color saturates over time (interpolate accent vs muted)
        try:
            ar, ag, ab = accent
            mr, mg, mb = fg_muted
            t = i / max(1, n - 1) if n > 1 else 1.0
            marker_color = RGBColor(
                int(mr * (1 - t) + ar * t),
                int(mg * (1 - t) + ag * t),
                int(mb * (1 - t) + ab * t),
            )
        except Exception:
            marker_color = accent
        # Numbered marker (circle)
        dot_r = Pt(20)
        dot = slide.shapes.add_shape(
            MSO_SHAPE.OVAL, x - dot_r, line_y - dot_r + Pt(1),
            dot_r * 2, dot_r * 2,
        )
        dot.line.fill.background()
        dot.fill.solid()
        dot.fill.fore_color.rgb = marker_color
        dot.shadow.inherit = False
        # Number inside the marker
        dtf = dot.text_frame
        dtf.margin_left = Pt(2)
        dtf.margin_right = Pt(2)
        dtf.margin_top = Pt(2)
        dtf.margin_bottom = Pt(2)
        dp = dtf.paragraphs[0]
        dp.alignment = PP_ALIGN.CENTER
        drun = dp.add_run()
        drun.text = str(i + 1)
        drun.font.size = Pt(tag_pt - 6)
        drun.font.bold = True
        drun.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        if fonts.get("display"):
            drun.font.name = fonts["display"]

        # Tag + note alternating above / below the line
        block_w = Inches(2.0)
        above = (i % 2 == 0)
        if above:
            block_top = line_y - dot_r - Inches(1.6)
            block_h = Inches(1.4)
        else:
            block_top = line_y + dot_r + Pt(8)
            block_h = Inches(1.4)
        _emit_text(slide, m.get("tag") or "",
                   left=x - block_w // 2, top=block_top,
                   width=block_w, height=Pt(tag_pt * 1.5),
                   size_pt=tag_pt, color=fg,
                   font_name=fonts.get("display"), bold=True,
                   align=PP_ALIGN.CENTER)
        _emit_text(slide, m.get("note") or "",
                   left=x - block_w // 2,
                   top=block_top + Pt(tag_pt * 1.6),
                   width=block_w, height=block_h - Pt(tag_pt * 1.6),
                   size_pt=note_pt, color=fg_muted,
                   font_name=fonts.get("body"),
                   align=PP_ALIGN.CENTER, line_spacing=1.2)


# ─── 10. zoom_in_callout ──────────────────────────────────────────────────


def zoom_in_callout(slide, *, context_image_path: str,
                    callout: dict, note: str = "",
                    palette, fonts, type_scale, sw, sh):
    """Focus on a region of a complex figure: full image on the left,
    a labeled rectangle marking the region of interest, then a zoomed
    inset on the right with a connector line and an explanatory note
    below the inset.

    context_image_path: filesystem path to the source PNG.
    callout: {"x": 0..1, "y": 0..1, "w": 0..1, "h": 0..1} — region of
             interest as fractions of the source image's bounding box.
    """
    # Left half — the context image
    left_x = Inches(0.6)
    left_y = Inches(1.6)
    left_w = (sw - Inches(1.2)) // 2 - Inches(0.3)
    left_h = sh - left_y - Inches(1.4)

    _h._autoshrink  # ensure import is touched (silence linters)
    # Place the context image (contain)
    img_buf = _normalize_for_helper(context_image_path)
    pic = slide.shapes.add_picture(img_buf, left_x, left_y,
                                   width=left_w, height=left_h)

    # Compute placement of the callout rectangle on top of the image
    cx_pct = max(0.0, min(1.0, callout.get("x", 0.4)))
    cy_pct = max(0.0, min(1.0, callout.get("y", 0.4)))
    cw_pct = max(0.05, min(1.0, callout.get("w", 0.2)))
    ch_pct = max(0.05, min(1.0, callout.get("h", 0.2)))
    # Use the picture's actual placement bounds (set above)
    box_left = pic.left + int(pic.width * cx_pct)
    box_top = pic.top + int(pic.height * cy_pct)
    box_w = int(pic.width * cw_pct)
    box_h = int(pic.height * ch_pct)
    rect = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, box_left, box_top, box_w, box_h,
    )
    rect.fill.background()
    rect.line.color.rgb = palette["accent"]
    rect.line.width = Pt(2)
    rect.shadow.inherit = False

    # Right half — the zoomed inset (place the same image cropped to
    # the callout via python-pptx crop_* properties)
    right_x = left_x + left_w + Inches(0.6)
    right_y = left_y
    right_w = sw - right_x - Inches(0.6)
    right_h = left_h * 2 // 3

    img_buf2 = _normalize_for_helper(context_image_path)
    inset = slide.shapes.add_picture(img_buf2, right_x, right_y,
                                     width=right_w, height=right_h)
    # Crop to the callout fractions
    inset.crop_left = cx_pct
    inset.crop_top = cy_pct
    inset.crop_right = 1.0 - (cx_pct + cw_pct)
    inset.crop_bottom = 1.0 - (cy_pct + ch_pct)

    # Connector — diagonal line from rect's right edge to inset's left
    conn = slide.shapes.add_connector(
        1, box_left + box_w, box_top + box_h // 2,
        right_x, right_y + right_h // 2,
    )
    conn.line.color.rgb = palette["accent"]
    conn.line.width = Pt(1.25)

    # Note below the inset
    if note:
        _emit_text(slide, note,
                   left=right_x, top=right_y + right_h + Pt(8),
                   width=right_w,
                   height=sh - (right_y + right_h) - Inches(0.6),
                   size_pt=type_scale.get("caption", 12),
                   color=_muted(palette["foreground"]),
                   font_name=fonts.get("body"),
                   italic=True, line_spacing=1.3)


def _normalize_for_helper(path: str):
    """Local thin wrapper around deck_render._normalize_image_for_pptx
    — kept here to break a circular import (deck_render imports this
    module, and slide_patterns.zoom_in_callout needs the
    normalization)."""
    from . import deck_render
    return deck_render._normalize_image_for_pptx(path)
