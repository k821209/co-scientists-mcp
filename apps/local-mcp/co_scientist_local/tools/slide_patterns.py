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


# Where the body content starts for patterns that sit under an agent-
# drawn h.title_block (which spans ~Inches(0.45) .. Inches(1.5) plus a
# short accent rule below it). Inches(1.85) leaves a small clearance.
# Patterns that "own the whole slide" (e.g. chapter_divider) ignore this.
# (todo 005 Bug B / meta-issue: patterns need a contract about caller state.)
_BODY_TOP = Inches(1.85)
_SIDE_MARGIN = Inches(0.7)
_BOTTOM_MARGIN = Inches(0.6)


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
    """Thesis / takeaway slide. Asymmetric: large headline on the left
    (~⅔ width), small numbered evidence column on the right. Tension
    between the two earns the contrast.

    Contract: **Goes under a title_block.** Call h.accent_stripe(slide)
    and h.title_block(slide, ...) BEFORE this pattern. The pattern
    starts at y = `_BODY_TOP` (≈ 1.85"), below the title bar.

    Content limits:
        headline: max ~60 chars; wraps to 3 lines.
        evidence: 2–4 items, each max ~80 chars (wraps to 2 lines).
    """
    headline_pt = max(36, type_scale.get("cover_title", 40) - 4)
    body_pt = type_scale.get("body", 20) - 2
    label_pt = type_scale.get("caption", 12)

    body_top = _BODY_TOP
    body_h = sh - body_top - Inches(0.6)
    # Left column ~62% width, right column the rest
    margin = Inches(0.7)
    left_w = int((sw - 2 * margin) * 0.62)
    right_x = margin + left_w + Inches(0.3)
    right_w = sw - right_x - margin

    _emit_text(slide, headline,
               left=margin, top=body_top,
               width=left_w, height=body_h,
               size_pt=headline_pt, color=palette["foreground"],
               font_name=fonts.get("display"), bold=True,
               line_spacing=1.05)

    fg_muted = _muted(palette["foreground"])
    _emit_text(slide, "EVIDENCE",
               left=right_x, top=body_top,
               width=right_w, height=Pt(label_pt * 2),
               size_pt=label_pt, color=palette["accent"],
               font_name=fonts.get("body"), bold=True)

    ev_top = body_top + Pt(label_pt * 2.8)
    ev_h_each = (body_h - Pt(label_pt * 2.8)) // max(1, len(evidence))
    for i, line in enumerate(evidence):
        y = ev_top + i * ev_h_each
        # Thin accent number
        _emit_text(slide, f"{i + 1:02d}",
                   left=right_x, top=y,
                   width=Pt(36), height=ev_h_each,
                   size_pt=int(body_pt * 0.85), color=palette["accent"],
                   font_name=fonts.get("display"), bold=True)
        _emit_text(slide, line,
                   left=right_x + Pt(36), top=y,
                   width=right_w - Pt(36), height=ev_h_each,
                   size_pt=body_pt, color=fg_muted,
                   font_name=fonts.get("body"),
                   anchor=MSO_ANCHOR.TOP)


# ─── 2. chapter_divider ───────────────────────────────────────────────────


def chapter_divider(slide, *, chapter_label: str, summary: str = "",
                    palette, fonts, type_scale, sw, sh):
    """Section opener — Era I/II/III. Massive chapter label vertically
    centered + a short accent rule UNDER the label + optional summary
    tagline below. Distinct rhythm from interior slides — the audience
    feels the section break.

    Contract: **Owns the whole slide.** Do NOT call h.accent_stripe()
    or h.title_block() before this pattern. This pattern is the slide;
    the centred label is the only top-level element.

    Content limits:
        chapter_label: ≤ ~12 chars at chapter size (>= 56pt). Korean
            counts as 2× width per char.
        summary: ≤ ~50 chars; wraps to 2 lines max.
    """
    # Use a clearly chapter-sized type (>= 56pt) so the label reads as a
    # section break, not a slide title (todo 005 Bug C).
    label_pt = max(56, type_scale.get("cover_title", 40) + 16)
    summary_pt = type_scale.get("head", 26)

    fg = palette["foreground"]
    fg_muted = _muted(fg)
    accent = palette["accent"]
    margin_x = sw // 14
    box_w = sw - 2 * margin_x

    # Build a centred vertical block: label + rule + summary.
    label_h = Pt(label_pt * 1.25)
    rule_gap = Pt(_h.SPACING_UNIT_PT * 2)   # 16pt above + below the rule
    rule_h = Pt(8)
    summary_h = Pt(summary_pt * 2.4) if summary else 0
    block_h = label_h + rule_gap + rule_h + (rule_gap + summary_h if summary else 0)
    block_top = (sh - block_h) // 2

    _emit_text(slide, chapter_label,
               left=margin_x, top=block_top,
               width=box_w, height=label_h,
               size_pt=label_pt, color=fg,
               font_name=fonts.get("display"), bold=True,
               align=PP_ALIGN.CENTER, line_spacing=1.05)
    # Accent rule UNDER the chapter label — anchors the title visually.
    rule_w = max(Inches(1.2), sw // 8)
    _accent_rule(slide,
                 left=(sw - rule_w) // 2,
                 top=block_top + label_h + rule_gap,
                 width=rule_w, height=rule_h, color=accent)
    if summary:
        _emit_text(slide, summary,
                   left=margin_x,
                   top=block_top + label_h + rule_gap + rule_h + rule_gap,
                   width=box_w, height=summary_h,
                   size_pt=summary_pt, color=fg_muted,
                   font_name=fonts.get("body"),
                   italic=True, align=PP_ALIGN.CENTER,
                   line_spacing=1.25)


# ─── 3. metric_tile_row ───────────────────────────────────────────────────


def metric_tile_row(slide, *, tiles: list[tuple],
                    palette, fonts, type_scale, sw, sh,
                    top=None, height=None):
    """KPI / quantitative summary — a row of large numbers with thin
    labels (and optional units) under each.

    Contract: **Goes under a title_block.** Call h.accent_stripe + h.
    title_block BEFORE. Pattern starts at y ≈ `_BODY_TOP + Inches(0.5)`
    by default (use `top=` to override).

    Content limits:
        tiles: 3–5 items. Each label ≤ ~24 chars (1 line).
            Tuple shape: (value, label) or (value, label, unit).
    """
    if not tiles:
        return
    top = _BODY_TOP + Inches(0.5) if top is None else top
    height = Inches(3.0) if height is None else height
    side_margin = _SIDE_MARGIN
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
    """Claim + 2-3 supporting facts. Top: the claim in display type.
    Bottom: stacked evidence rows, each with a small accent tag-pill
    on the left + body text on the right.

    Contract: **Goes under a title_block.** Call h.accent_stripe + h.
    title_block BEFORE. Claim starts at `_BODY_TOP`.

    Content limits:
        claim: ≤ ~80 chars; wraps to 2 lines max at claim_pt size.
        evidence: 2–4 items, each {tag (≤ ~10 chars), body (≤ ~120
            chars; wraps to 2 lines)}.
    """
    claim_pt = max(28, type_scale.get("head", 26) + 4)
    tag_pt = type_scale.get("caption", 12)
    body_pt = type_scale.get("body", 20)

    claim_top = _BODY_TOP
    claim_h = Inches(1.6)
    _emit_text(slide, claim,
               left=_SIDE_MARGIN, top=claim_top,
               width=sw - 2 * _SIDE_MARGIN, height=claim_h,
               size_pt=claim_pt, color=palette["foreground"],
               font_name=fonts.get("display"), bold=True,
               line_spacing=1.15)
    rule_top = claim_top + claim_h + Pt(4)
    _accent_rule(slide, left=_SIDE_MARGIN, top=rule_top,
                 width=Inches(3.0), height=Pt(4),
                 color=palette["accent"])

    stack_top = rule_top + Pt(16)
    row_h = (sh - stack_top - _BOTTOM_MARGIN) // max(1, len(evidence))
    tag_w = Inches(1.6)
    fg_muted = _muted(palette["foreground"])
    for i, item in enumerate(evidence):
        y = stack_top + i * row_h
        tag = (item.get("tag") or "").upper()
        body = item.get("body") or ""
        if tag:
            pill = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                _SIDE_MARGIN, y + Pt(8),
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
                   left=_SIDE_MARGIN + tag_w + Pt(12), top=y + Pt(4),
                   width=sw - 2 * _SIDE_MARGIN - tag_w - Pt(12),
                   height=row_h - Pt(8),
                   size_pt=body_pt, color=fg_muted,
                   font_name=fonts.get("body"),
                   anchor=MSO_ANCHOR.TOP)


# ─── 5. flow_pipeline ─────────────────────────────────────────────────────


def flow_pipeline(slide, *, steps: list[dict],
                  palette, fonts, type_scale, sw, sh):
    """Horizontal process flow. Each step is a small card with a
    numbered tag + body; right-pointing arrows connect consecutive
    steps.

    Contract: **Goes under a title_block.** Call h.accent_stripe + h.
    title_block BEFORE. Pattern starts at `_BODY_TOP + 0.4"`.

    Content limits:
        steps: 3–5 items. tag ≤ ~12 chars, body ≤ ~80 chars (wraps to
            3 lines).
    """
    if not steps:
        return
    side = _SIDE_MARGIN
    top = _BODY_TOP + Inches(0.4)
    height = sh - top - _BOTTOM_MARGIN
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
    A single right-arrow + optional label between them. Asymmetry on
    weight (after is visually heavier) earns the contrast.

    Contract: **Goes under a title_block.** Call h.accent_stripe + h.
    title_block BEFORE. Pattern starts at `_BODY_TOP + 0.2"`.

    Content limits:
        before / after: {title (≤ ~16 chars), body (≤ ~140 chars,
            wraps to 4 lines)}.
        transition_label: ≤ ~16 chars.
    """
    side = _SIDE_MARGIN
    top = _BODY_TOP + Inches(0.2)
    height = sh - top - _BOTTOM_MARGIN
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
    """Two competing options framed by an axis (e.g. cost / risk /
    speed). Mirrored panels — both equally weighted. The question is
    which one *for your case*. Distinct from `before_after_split`,
    where the after-panel is intentionally heavier.

    Contract: **Goes under a title_block.** Call h.accent_stripe + h.
    title_block BEFORE. Axis label (if any) sits at `_BODY_TOP`; panels
    start just below it.

    Content limits:
        left_item / right_item: {title (≤ ~16 chars), pros (≤ 4 items
            of ≤ ~40 chars), cons (≤ 4 items of ≤ ~40 chars)}.
        axis_label: ≤ ~40 chars.
    """
    side = _SIDE_MARGIN
    panel_w = (sw - 2 * side - Inches(0.3)) // 2
    title_pt = type_scale.get("head", 26)
    body_pt = type_scale.get("body", 20) - 2
    fg_muted = _muted(palette["foreground"])

    axis_h = Pt(20) if axis_label else 0
    if axis_label:
        _emit_text(slide, axis_label.upper(),
                   left=side, top=_BODY_TOP,
                   width=sw - 2 * side, height=axis_h,
                   size_pt=type_scale.get("caption", 12),
                   color=palette["accent"],
                   font_name=fonts.get("body"), bold=True,
                   align=PP_ALIGN.CENTER)
    top = _BODY_TOP + axis_h + (Pt(8) if axis_label else 0)
    height = sh - top - _BOTTOM_MARGIN

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
    """2×2 conceptual map. Items positioned by their (x, y) in [0, 1]
    (origin bottom-left). Axes carry labels + optional low/high
    descriptors. Useful for "X is high/low on cost AND high/low on
    impact" comparisons.

    Contract: **Goes under a title_block.** Call h.accent_stripe + h.
    title_block BEFORE. The y-axis label sits at `_BODY_TOP`; the map
    starts just below.

    Content limits:
        items: 2–8. Each label ≤ ~16 chars.
        axes: {x, y} required (≤ ~30 chars each); optional x_low,
            x_high (≤ ~16 chars each) anchor the horizontal axis.
    """
    map_left = Inches(1.6)
    pad = Inches(0.6)
    # y-axis label sits in the top strip (height ≈ Pt(label_pt * 1.5))
    label_pt = type_scale.get("body", 20) - 4
    y_label_h = Pt(label_pt * 1.7)
    map_top = _BODY_TOP + y_label_h + Pt(4)
    map_w = sw - map_left - pad
    map_h = sh - map_top - _BOTTOM_MARGIN - Pt(label_pt * 2)

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
    # rotation is finicky; place it horizontally above the map and
    # within slide bounds (todo 005 — keep all shapes inside the slide).
    _emit_text(slide, "↑ " + (axes.get("y") or ""),
               left=Inches(0.6), top=_BODY_TOP,
               width=sw - Inches(1.2), height=y_label_h,
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
    """Progressive timeline. Equal-width slots across the body area;
    each slot has a numbered circle on a horizontal baseline + a tag +
    a note **all below the line**. Marker color saturates left → right
    (muted → accent) so the audience sees direction. Slot-based layout
    (no alternating above/below) keeps the design robust to Korean
    text wrapping and edge milestones (todo 005 Bug A).

    Contract: **Goes under a title_block.** Call h.accent_stripe + h.
    title_block BEFORE. Pattern starts at y = `_BODY_TOP`.

    Content limits:
        milestones: 3–6 items. Each tag ≤ ~14 chars at tag size
            (wraps to 2 lines max); note ≤ ~60 chars (3 lines max).
    """
    if not milestones:
        return
    n = len(milestones)

    fg = palette["foreground"]
    fg_muted = _muted(fg)
    accent = palette["accent"]
    tag_pt = max(14, type_scale.get("head", 26) - 6)
    note_pt = type_scale.get("body", 20) - 4

    # Body area
    body_top = _BODY_TOP
    body_bottom = sh - _BOTTOM_MARGIN
    body_h = body_bottom - body_top

    # Line sits at the top quarter of the body (markers below it)
    line_y = body_top + body_h // 4

    # Equal slots across usable width
    margin = _SIDE_MARGIN
    usable_w = sw - 2 * margin
    slot_w = usable_w // n

    # Marker dot radius
    dot_r = Pt(20)

    # Baseline timeline runs between the first and last slot CENTRES, so
    # the line doesn't extend past the markers and into empty margins.
    first_cx = margin + slot_w // 2
    last_cx = margin + (n - 1) * slot_w + slot_w // 2
    if last_cx > first_cx:
        _accent_rule(slide,
                     left=first_cx,
                     top=line_y - Pt(1),
                     width=last_cx - first_cx, height=Pt(3),
                     color=fg_muted)

    # Per-milestone slot
    for i, m in enumerate(milestones):
        slot_left = margin + i * slot_w
        slot_cx = slot_left + slot_w // 2

        # Marker color: interpolate muted → accent across the row
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

        # Numbered circle, centered on the slot at the timeline
        dot = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            slot_cx - dot_r, line_y - dot_r,
            dot_r * 2, dot_r * 2,
        )
        dot.line.fill.background()
        dot.fill.solid()
        dot.fill.fore_color.rgb = marker_color
        dot.shadow.inherit = False
        dtf = dot.text_frame
        dtf.margin_left = Pt(2); dtf.margin_right = Pt(2)
        dtf.margin_top = Pt(2); dtf.margin_bottom = Pt(2)
        dp = dtf.paragraphs[0]
        dp.alignment = PP_ALIGN.CENTER
        drun = dp.add_run()
        drun.text = str(i + 1)
        drun.font.size = Pt(tag_pt - 4)
        drun.font.bold = True
        drun.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        if fonts.get("display"):
            drun.font.name = fonts["display"]

        # Tag + note stacked BELOW the line within the slot
        text_top = line_y + dot_r + Pt(8)
        text_left = slot_left + Pt(4)
        text_w = slot_w - Pt(8)
        # Tag: room for up to 2 wrapped lines
        tag_h = Pt(tag_pt * 1.5 * 2)
        _emit_text(slide, m.get("tag") or "",
                   left=text_left, top=text_top,
                   width=text_w, height=tag_h,
                   size_pt=tag_pt, color=fg,
                   font_name=fonts.get("display"), bold=True,
                   align=PP_ALIGN.CENTER, line_spacing=1.15,
                   anchor=MSO_ANCHOR.TOP)
        # Note: the rest of the slot
        note_top = text_top + tag_h + Pt(4)
        _emit_text(slide, m.get("note") or "",
                   left=text_left, top=note_top,
                   width=text_w,
                   height=body_bottom - note_top,
                   size_pt=note_pt, color=fg_muted,
                   font_name=fonts.get("body"),
                   align=PP_ALIGN.CENTER, line_spacing=1.2,
                   anchor=MSO_ANCHOR.TOP)


# ─── 10. zoom_in_callout ──────────────────────────────────────────────────


def zoom_in_callout(slide, *, context_image_path: str,
                    callout: dict, note: str = "",
                    palette, fonts, type_scale, sw, sh):
    """Focus on a region of a complex figure: full image on the left,
    a marked rectangle on the region of interest, zoomed inset on the
    right with an optional note below it.

    Contract: **Goes under a title_block.** Call h.accent_stripe + h.
    title_block BEFORE. Content starts at `_BODY_TOP`.

    Content limits:
        context_image_path: a real filesystem path (the helper Keynote-
            normalizes the image into RGB JPEG ≤ 1920px).
        callout: {x, y, w, h} fractions of the image (0..1).
        note: ≤ ~120 chars, wraps to 3 lines.
    """
    left_x = _SIDE_MARGIN
    left_y = _BODY_TOP
    left_w = (sw - 2 * _SIDE_MARGIN) // 2 - Inches(0.3)
    left_h = sh - left_y - _BOTTOM_MARGIN - Inches(0.4)

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


# ─── Structural patterns (todo 006) ──────────────────────────────────────
#
# Where the 10 patterns above are organized by design *intent* (thesis,
# comparison, timeline, …), these are organized by content *shape* —
# the PowerPoint master-layout taxonomy. The agent picks the structural
# pattern first (do I have a body? images? how many?) and may then opt
# into a more design-loaded intent pattern instead.


def title_slide(slide, *, title: str, subtitle: str = "",
                eyebrow: str = "",
                palette, fonts, type_scale, sw, sh):
    """Deck opener / cover (PowerPoint base 1 — Title Slide). Centered
    eyebrow + large title + short accent rule + subtitle.

    Distinct from `chapter_divider` (a *mid-deck* section break) — this
    is the *opener* at slide 1 with author / venue / date metadata.

    Contract: **Owns the whole slide.** Do NOT call h.accent_stripe or
    h.title_block before; this pattern is the slide.

    Content limits:
        title:    ≤ ~50 chars at display size (wraps to 2 lines).
        subtitle: ≤ ~80 chars (1 line; e.g. "Author — Venue 2026").
        eyebrow:  ≤ ~30 chars; rendered upper-case in accent color.
    """
    title_pt = max(48, type_scale.get("cover_title", 40) + 8)
    sub_pt = type_scale.get("head", 26)
    eyebrow_pt = type_scale.get("caption", 12)

    fg = palette["foreground"]
    fg_muted = _muted(fg)
    accent = palette["accent"]
    margin_x = sw // 12
    box_w = sw - 2 * margin_x

    title_h = Pt(title_pt * 1.25)
    rule_gap = Pt(_h.SPACING_UNIT_PT * 2)
    rule_h = Pt(6)
    eyebrow_h = Pt(eyebrow_pt * 1.8) if eyebrow else 0
    sub_h = Pt(sub_pt * 1.8) if subtitle else 0
    block_h = (eyebrow_h + (Pt(4) if eyebrow else 0)
               + title_h
               + (rule_gap + rule_h if subtitle else 0)
               + (rule_gap + sub_h if subtitle else 0))
    block_top = (sh - block_h) // 2

    cursor = block_top
    if eyebrow:
        _emit_text(slide, eyebrow.upper(),
                   left=margin_x, top=cursor,
                   width=box_w, height=eyebrow_h,
                   size_pt=eyebrow_pt, color=accent,
                   font_name=fonts.get("body"), bold=True,
                   align=PP_ALIGN.CENTER)
        cursor += eyebrow_h + Pt(4)
    _emit_text(slide, title,
               left=margin_x, top=cursor,
               width=box_w, height=title_h,
               size_pt=title_pt, color=fg,
               font_name=fonts.get("display"), bold=True,
               align=PP_ALIGN.CENTER, line_spacing=1.05)
    cursor += title_h
    if subtitle:
        rule_w = max(Inches(1.2), sw // 8)
        _accent_rule(slide, left=(sw - rule_w) // 2,
                     top=cursor + rule_gap,
                     width=rule_w, height=rule_h, color=accent)
        _emit_text(slide, subtitle,
                   left=margin_x, top=cursor + rule_gap + rule_h + rule_gap,
                   width=box_w, height=sub_h,
                   size_pt=sub_pt, color=fg_muted,
                   font_name=fonts.get("body"),
                   align=PP_ALIGN.CENTER)


def title_and_body(slide, *, title: str, body, lead: str = "",
                   palette, fonts, type_scale, sw, sh):
    """Standard title + bullet body (PowerPoint base 2 — Title and
    Content, plain). Body sits in a left ~60% column with the right
    ~40% intentionally left as whitespace (focus discipline — see
    SKILL §5c).

    Contract: **Goes under a title_block.** Call h.accent_stripe + h.
    title_block BEFORE. Optional `lead` sentence renders in display
    type above the bullets.

    Content limits:
        body: list of strings (bullets) OR a string (one bullet per
            non-empty line; leading bullet marker stripped).
        lead: ≤ ~120 chars (wraps to 2 lines max).
    """
    if isinstance(body, str):
        items = [ln.strip().lstrip("-*•").lstrip()
                 for ln in body.splitlines() if ln.strip()]
    else:
        items = list(body or [])

    fg = palette["foreground"]
    fg_muted = _muted(fg)
    body_pt = type_scale.get("body", 20)
    lead_pt = max(body_pt + 4, type_scale.get("head", 26) - 4)
    body_top = _BODY_TOP
    body_left = _SIDE_MARGIN
    # ~60% width left column, 40% whitespace on the right
    body_w = int((sw - 2 * _SIDE_MARGIN) * 0.6)

    cursor = body_top
    if lead:
        lead_h = Pt(lead_pt * 2.2)
        _emit_text(slide, lead,
                   left=body_left, top=cursor,
                   width=body_w, height=lead_h,
                   size_pt=lead_pt, color=fg,
                   font_name=fonts.get("display"), bold=False,
                   line_spacing=1.2, italic=True)
        cursor += lead_h + Pt(_h.SPACING_UNIT_PT * 2)

    # Body bullets
    bullets_h = sh - cursor - _BOTTOM_MARGIN
    tb = slide.shapes.add_textbox(body_left, cursor, body_w, bullets_h)
    tf = tb.text_frame
    tf.word_wrap = True
    _h._autoshrink(tf)
    line_spacing = type_scale.get("line_spacing", 1.22)
    first = True
    for item in items:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.line_spacing = line_spacing
        para.space_after = Pt(_h.SPACING_UNIT_PT)
        run = para.add_run()
        run.text = f"•  {item}"
        run.font.size = Pt(body_pt)
        run.font.color.rgb = fg_muted
        if fonts.get("body"):
            run.font.name = fonts["body"]


def title_two_content(slide, *, title: str, left: dict, right: dict,
                       palette, fonts, type_scale, sw, sh):
    """Generic 2-column body (PowerPoint base 4 — Two Content). Each
    side is `{heading?, body?, bullets?}`. Mirrored panels — both
    equally weighted. Use for "X vs Y" structures where neither side
    dominates (for emphasized comparison, prefer
    `p.before_after_split`; for pros/cons, prefer `p.contrast_pair`).

    Contract: **Goes under a title_block.** Pattern starts at _BODY_TOP.

    Content limits:
        left / right: each {heading (≤ ~24 chars), body (≤ ~280 chars,
            wraps to 6 lines), bullets (≤ 5 of ≤ ~60 chars)}.
    """
    fg = palette["foreground"]
    fg_muted = _muted(fg)
    accent = palette["accent"]
    head_pt = type_scale.get("head", 26)
    body_pt = type_scale.get("body", 20)

    side = _SIDE_MARGIN
    top = _BODY_TOP
    gap = Inches(0.4)
    col_w = (sw - 2 * side - gap) // 2
    height = sh - top - _BOTTOM_MARGIN

    for i, item in enumerate((left, right)):
        x = side + i * (col_w + gap)
        heading = item.get("heading") or ""
        body = item.get("body") or ""
        bullets = item.get("bullets") or []

        cursor = top
        if heading:
            head_h = Pt(head_pt * 1.6)
            _emit_text(slide, heading,
                       left=x, top=cursor,
                       width=col_w, height=head_h,
                       size_pt=head_pt, color=fg,
                       font_name=fonts.get("display"), bold=True)
            # Small accent rule under the column heading
            _accent_rule(slide, left=x, top=cursor + head_h + Pt(2),
                         width=Inches(1.0), height=Pt(3), color=accent)
            cursor += head_h + Pt(_h.SPACING_UNIT_PT * 2)

        remaining = top + height - cursor
        tb = slide.shapes.add_textbox(x, cursor, col_w, remaining)
        tf = tb.text_frame
        tf.word_wrap = True
        _h._autoshrink(tf)
        first = True
        line_spacing = type_scale.get("line_spacing", 1.22)
        if body:
            p = tf.paragraphs[0]
            first = False
            p.line_spacing = line_spacing
            p.space_after = Pt(_h.SPACING_UNIT_PT)
            run = p.add_run()
            run.text = body
            run.font.size = Pt(body_pt)
            run.font.color.rgb = fg_muted
            if fonts.get("body"):
                run.font.name = fonts["body"]
        for b in bullets:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.line_spacing = line_spacing
            p.space_after = Pt(_h.SPACING_UNIT_PT // 2)
            run = p.add_run()
            run.text = f"•  {b}"
            run.font.size = Pt(body_pt)
            run.font.color.rgb = fg_muted
            if fonts.get("body"):
                run.font.name = fonts["body"]


def title_and_image_grid(slide, *, title: str,
                          images: list[dict], cols: int = 2,
                          palette, fonts, type_scale, sw, sh):
    """N images in a `cols`-column grid (PowerPoint base 4 extended).
    1 image = full-half; 2 = side-by-side; 4 = 2×2; etc. Optional per-
    image caption strip below each tile. Layout effect (SKILL §5c):
    grid implies COMPARISON; for PROGRESSION use cols=N rows=1.

    Contract: **Goes under a title_block.** Pattern starts at _BODY_TOP.

    Content limits:
        images: 1–6 items, each {path (real filesystem path), caption?
            (≤ ~60 chars; 1 line)}.
        cols: 1, 2, 3, or 4 (default 2).
    """
    if not images:
        return
    cols = max(1, min(4, int(cols)))
    n = len(images)
    rows = (n + cols - 1) // cols

    side = _SIDE_MARGIN
    top = _BODY_TOP
    gap = Pt(_h.SPACING_UNIT_PT * 2)
    grid_w = sw - 2 * side - gap * (cols - 1)
    grid_h = sh - top - _BOTTOM_MARGIN - gap * (rows - 1)
    cell_w = grid_w // cols
    cell_h = grid_h // rows

    cap_pt = type_scale.get("caption", 12)
    fg_muted = _muted(palette["foreground"])

    for i, img in enumerate(images):
        r, c = i // cols, i % cols
        x = side + c * (cell_w + gap)
        y = top + r * (cell_h + gap)
        path = img.get("path")
        caption = (img.get("caption") or "").strip()
        cap_h = Pt(cap_pt * 1.8) if caption else 0
        img_h = cell_h - cap_h - (Pt(4) if caption else 0)
        # Embed image with Keynote-safe normalization
        if path:
            img_buf = _normalize_for_helper(path)
            pic = slide.shapes.add_picture(img_buf, x, y, width=cell_w, height=img_h)
            # Letterbox-fit (contain) — never crop a tile image.
            if pic.width != cell_w or pic.height != img_h:
                # contain math
                pic_ar = pic.width / pic.height if pic.height else 1
                box_ar = cell_w / img_h if img_h else 1
                if pic_ar > box_ar:
                    new_w = cell_w
                    new_h = int(cell_w / pic_ar)
                else:
                    new_h = img_h
                    new_w = int(img_h * pic_ar)
                pic.width = new_w
                pic.height = new_h
                pic.left = x + (cell_w - new_w) // 2
                pic.top = y + (img_h - new_h) // 2
        if caption:
            _emit_text(slide, caption,
                       left=x, top=y + img_h + Pt(4),
                       width=cell_w, height=cap_h,
                       size_pt=cap_pt, color=fg_muted,
                       font_name=fonts.get("body"),
                       italic=True, align=PP_ALIGN.CENTER)
