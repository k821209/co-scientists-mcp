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
from pptx.dml.color import RGBColor  # type: ignore


# Icon vocabulary (todo 004 §C). Each semantic name maps to either an
# MSO_SHAPE built-in (preferred — native PowerPoint shape, fully
# recolorable + editable + scalable) or a fallback Unicode glyph
# rendered in a textbox. The agent calls `h.icon(slide, name, ...)`
# with one of these names; unknown names raise.
_ICON_SHAPES = {
    # Direction / flow
    "arrow-right":   MSO_SHAPE.RIGHT_ARROW,
    "arrow-left":    MSO_SHAPE.LEFT_ARROW,
    "arrow-up":      MSO_SHAPE.UP_ARROW,
    "arrow-down":    MSO_SHAPE.DOWN_ARROW,
    "arrow-both":    MSO_SHAPE.LEFT_RIGHT_ARROW,
    "arrow-vert":    MSO_SHAPE.UP_DOWN_ARROW,
    "arrow-quad":    MSO_SHAPE.QUAD_ARROW,
    "arrow-curve":   MSO_SHAPE.CURVED_RIGHT_ARROW,
    "arrow-loop":    MSO_SHAPE.CIRCULAR_ARROW,
    "chevron":       MSO_SHAPE.CHEVRON,
    # Status / emphasis
    "lightning":     MSO_SHAPE.LIGHTNING_BOLT,
    "burst":         MSO_SHAPE.EXPLOSION1,
    "burst-big":     MSO_SHAPE.EXPLOSION2,
    "star":          MSO_SHAPE.STAR_5_POINT,
    "heart":         MSO_SHAPE.HEART,
    "plus":          MSO_SHAPE.MATH_PLUS,
    "minus":         MSO_SHAPE.MATH_MINUS,
    "warning":       MSO_SHAPE.ISOSCELES_TRIANGLE,
    # Data / storage
    "database":      MSO_SHAPE.CAN,
    "cloud":         MSO_SHAPE.CLOUD,
    "document":      MSO_SHAPE.FOLDED_CORNER,
    # Process / decision
    "decision":      MSO_SHAPE.DIAMOND,
    "molecule":      MSO_SHAPE.HEXAGON,
    "stop":          MSO_SHAPE.OCTAGON,
    "input":         MSO_SHAPE.PARALLELOGRAM,
    "gear":          MSO_SHAPE.GEAR_6,
    # Time / mode
    "sun":           MSO_SHAPE.SUN,
    "moon":          MSO_SHAPE.MOON,
    # Generic geometry
    "circle":        MSO_SHAPE.OVAL,
    "square":        MSO_SHAPE.RECTANGLE,
    "rounded":       MSO_SHAPE.ROUNDED_RECTANGLE,
    "ring":          MSO_SHAPE.DONUT,
    # Annotation / brackets
    "brace-left":    MSO_SHAPE.LEFT_BRACE,
    "brace-right":   MSO_SHAPE.RIGHT_BRACE,
    "brace-pair":    MSO_SHAPE.DOUBLE_BRACE,
}

# Unicode-glyph fallbacks for things python-pptx doesn't ship as a
# native shape (check, x, info, …). Rendered as text inside a textbox
# — still recolorable and scalable.
_ICON_GLYPHS = {
    "check":         "✓",   # ✓
    "x":             "✗",   # ✗
    "info":          "ⓘ",   # ⓘ
    "question":      "?",
    "exclaim":       "!",
    "dot":           "●",   # ●
    "open-dot":      "○",   # ○
    "diamond-glyph": "◆",   # ◆
    "asterisk":      "✱",   # ✱
    "skull":         "☠",   # ☠
    "atom":          "⚛",   # ⚛
    "leaf":          "⚘",   # ⚘
    "flask":         "⚚",   # ⚚
    "dna":           "\U0001F9EC",   # 🧬
    "microscope":    "\U0001F52C",   # 🔬
    "chart":         "\U0001F4C8",   # 📈
    "lock":          "\U0001F512",   # 🔒
}


def icon(slide, name: str, *, left, top, size, palette,
         color=None, fonts=None):
    """Place a named icon at `(left, top)` with `size × size` bounding
    box (todo 004 §C). The vocabulary maps semantic names to MSO_SHAPE
    built-ins (preferred — native, recolorable, editable, scalable) or
    a Unicode-glyph fallback rendered in a textbox.

    color: defaults to `palette["accent"]`. Pass an RGBColor to override.

    Available shape names: see _ICON_SHAPES keys (`arrow-*`, `chevron`,
    `lightning`, `burst`, `star`, `heart`, `plus`, `minus`, `warning`,
    `database`, `cloud`, `document`, `decision`, `molecule`, `stop`,
    `input`, `gear`, `sun`, `moon`, `circle`, `square`, `rounded`,
    `ring`, `brace-*`).

    Glyph fallback names (textbox-rendered): `check`, `x`, `info`,
    `question`, `exclaim`, `dot`, `open-dot`, `diamond-glyph`,
    `asterisk`, `skull`, `atom`, `leaf`, `flask`, `dna`, `microscope`,
    `chart`, `lock`.

    Raises ValueError for unknown names.
    """
    fill = color if color is not None else palette["accent"]
    shape_const = _ICON_SHAPES.get(name)
    if shape_const is not None:
        sh = slide.shapes.add_shape(shape_const, left, top, size, size)
        sh.line.fill.background()
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
        sh.shadow.inherit = False
        return sh
    glyph = _ICON_GLYPHS.get(name)
    if glyph is None:
        raise ValueError(
            f"unknown icon name: {name!r}. "
            f"See _ICON_SHAPES / _ICON_GLYPHS in slide_render_helpers.py "
            "for the full vocabulary."
        )
    tb = slide.shapes.add_textbox(left, top, size, size)
    tf = tb.text_frame
    tf.margin_left = Pt(2); tf.margin_right = Pt(2)
    tf.margin_top = Pt(2); tf.margin_bottom = Pt(2)
    tf.word_wrap = False
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    p.line_spacing = 1.0
    run = p.add_run()
    run.text = glyph
    # Size text to ~75% of the box (Pt is 1/72 inch; EMU = 12700 Pt)
    pt_size = max(8, int(size / 12700 * 0.75))
    run.font.size = Pt(pt_size)
    run.font.color.rgb = fill
    if fonts and fonts.get("display"):
        run.font.name = fonts["display"]
    return tb


def icon_names() -> list[str]:
    """Sorted list of all icon names `h.icon()` accepts. Useful for the
    agent to consult before picking one."""
    return sorted(list(_ICON_SHAPES) + list(_ICON_GLYPHS))


# ─── text autofit (todo follow-up — box overlap fix) ─────────────────────


def _char_width_factor(cp: int) -> float:
    """Approximate width of a glyph at font_pt = 1.0, by codepoint
    range. Hangul / CJK / Kana count as ~1.0 × font_pt (wide); ASCII
    counts as ~0.55 × font_pt; punctuation / spaces around 0.3–0.4.
    LibreOffice / PowerPoint render at slightly different widths, so
    this is a conservative estimate used for autofit only."""
    if (0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F
            or 0xAC00 <= cp <= 0xD7AF):
        return 1.0   # Hangul Jamo / Compatibility Jamo / Syllables
    if (0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x309F
            or 0x30A0 <= cp <= 0x30FF):
        return 1.0   # CJK Unified / Hiragana / Katakana
    if cp >= 0x2000 and cp < 0x3000:
        return 0.4   # general punctuation block
    if cp < 128:
        if cp == 32:
            return 0.3
        ch = chr(cp)
        if ch.isalnum() or ch in "._/-+":
            return 0.55
        return 0.4
    return 0.6


def estimate_text_width_pt(text: str, font_pt: int) -> float:
    """Rough width-in-pt for `text` rendered at `font_pt`. Sums per-
    character width factors; Korean-aware so Korean-heavy text doesn't
    fool the autofit into thinking it'll fit."""
    return sum(_char_width_factor(ord(c)) * font_pt for c in text)


def autofit_pt(text: str, *, max_width_emu, max_height_emu, start_pt: int,
                line_spacing: float = 1.22, min_pt: int = 10) -> int:
    """Largest pt in [min_pt, start_pt] at which `text` fits inside an
    EMU-sized box, conservatively wrapping per estimated character
    width. Falls back to `min_pt` if even that doesn't fit (caller's
    job to handle over-min overflow).

    The autofit happens BEFORE python-pptx runs, so the rendered PNG
    (via soffice — which doesn't fully honor TEXT_TO_SHAPE auto-shrink)
    matches what the user will see. PowerPoint's own renderer will
    still auto-shrink further if needed.
    """
    if not text or not text.strip():
        return start_pt
    width_pt = max(1, max_width_emu / 12700)
    height_pt = max(1, max_height_emu / 12700)
    lines_raw = [ln for ln in text.splitlines() if ln.strip()]
    if not lines_raw:
        return start_pt

    def line_count_at(pt: int) -> int:
        total = 0
        for ln in lines_raw:
            w = estimate_text_width_pt(ln, pt)
            # Ceiling of w / width_pt, min 1 line
            wraps = max(1, int((w + width_pt - 1) // width_pt))
            total += wraps
        return total

    pt = start_pt
    while pt > min_pt:
        if line_count_at(pt) * pt * line_spacing <= height_pt:
            return pt
        pt -= 1
    return min_pt





# 8pt vertical rhythm — every vertical gap a snippet places should be an
# integer multiple of this (todo 004 §D). Pulled out as a constant so
# snippets can write `Pt(8 * 2)` rather than magic numbers.
SPACING_UNIT_PT = 8


class Grid:
    """12-column / N-row design grid for `code` slides (todo 004 §D).

    A `Grid` is pure coordinate math — it does NOT add any shapes. Use
    `grid.cell(col=, span=, row=, row_span=)` to get a `(left, top,
    width, height)` EMU tuple you can pass to the layout helpers
    (`h.card`, `h.bullet_list`, `h.image_*`, etc.).

    The grid leaves room at the top for `h.title_block` (default
    margin_top=Inches(1.8)) so titles and grid content don't fight.
    The 8pt vertical rhythm is enforced as the row gap.

    Replaces ad-hoc `Inches(0.7)` constants scattered across snippets
    with a single shared geometry — alignment becomes default, not
    something the agent has to think about.
    """

    def __init__(self, *, sw, sh, cols: int = 12, rows: int = 6,
                 gutter=None, margin_x=None, margin_top=None,
                 margin_bot=None, row_gap=None, row_h=None):
        if cols < 1:
            raise ValueError(f"cols must be >= 1, got {cols}")
        if rows < 1:
            raise ValueError(f"rows must be >= 1, got {rows}")
        self.sw = sw
        self.sh = sh
        self.cols = cols
        self.rows = rows
        self.gutter = gutter if gutter is not None else Pt(SPACING_UNIT_PT)
        self.margin_x = margin_x if margin_x is not None else Inches(0.6)
        self.margin_top = margin_top if margin_top is not None else Inches(1.8)
        self.margin_bot = margin_bot if margin_bot is not None else Inches(0.6)
        self.row_gap = row_gap if row_gap is not None else Pt(SPACING_UNIT_PT)
        # Column width: usable width minus gutters, split N ways
        usable_w = sw - 2 * self.margin_x - self.gutter * (cols - 1)
        self.col_w = int(usable_w // cols)
        # Row height: usable height minus row gaps, split N ways
        usable_h = sh - self.margin_top - self.margin_bot
        if row_h is not None:
            self.row_h = row_h
        else:
            self.row_h = int(
                (usable_h - self.row_gap * (rows - 1)) // rows
            )

    def cell(self, col: int, span: int = 1, row: int = 1,
             row_span: int = 1):
        """Return `(left, top, width, height)` in EMU for a grid cell.

        col / row are 1-indexed (1..cols, 1..rows). `span` extends the
        cell rightward; `row_span` extends it downward. Spanning
        absorbs the gutters / row gaps between covered cells (so a
        col_span=3 block is *wider* than 3 stand-alone cells).
        """
        if not 1 <= col <= self.cols:
            raise ValueError(f"col must be 1..{self.cols}, got {col}")
        if span < 1 or col + span - 1 > self.cols:
            raise ValueError(
                f"span {span} from col {col} exceeds {self.cols} cols",
            )
        if not 1 <= row <= self.rows:
            raise ValueError(f"row must be 1..{self.rows}, got {row}")
        if row_span < 1 or row + row_span - 1 > self.rows:
            raise ValueError(
                f"row_span {row_span} from row {row} exceeds {self.rows} rows",
            )
        left = self.margin_x + (col - 1) * (self.col_w + self.gutter)
        width = self.col_w * span + self.gutter * (span - 1)
        top = self.margin_top + (row - 1) * (self.row_h + self.row_gap)
        height = self.row_h * row_span + self.row_gap * (row_span - 1)
        return (left, top, width, height)

    def row(self, row: int = 1, row_span: int = 1):
        """Shorthand for `cell(1, span=cols, row=row, row_span=row_span)`
        — the whole row, useful for headlines or pull-quotes that span
        all columns."""
        return self.cell(1, span=self.cols, row=row, row_span=row_span)


def grid(*, sw, sh, **kwargs) -> Grid:
    """Build a `Grid` sized to the current slide. The `slide` argument
    isn't needed — the grid is pure coordinate math. Pass `cols`,
    `rows`, `gutter`, `margin_x`, `margin_top`, `margin_bot`,
    `row_gap`, `row_h` to override defaults (12 / 6 / Pt(8) / Inches
    (0.6) / Inches(1.8) / Inches(0.6) / Pt(8) / computed).

    Typical usage in a `code` snippet:

        g = h.grid(sw=sw, sh=sh)
        left, top, w_, h_ = g.cell(col=1, span=6, row=1, row_span=3)
        h.bullet_list(slide, items, left=left, top=top,
                      width=w_, height=h_, ...)
    """
    return Grid(sw=sw, sh=sh, **kwargs)


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
    becomes one paragraph at the deck's body type (autofit-shrunk if
    the items don't fit at the start size). Pass bullet="" for a
    plain paragraph list."""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    _autoshrink(tf)
    body_pt = type_scale.get("body", 20)
    line_spacing = type_scale.get("line_spacing", 1.22)
    rendered = [(f"{bullet} {it}" if bullet else str(it)) for it in items]
    actual_pt = autofit_pt(
        "\n".join(rendered),
        max_width_emu=width, max_height_emu=height,
        start_pt=body_pt, line_spacing=line_spacing,
        min_pt=max(10, body_pt - 8),
    )
    first = True
    for line in rendered:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.line_spacing = line_spacing
        para.space_after = Pt(4)
        run = para.add_run()
        run.text = line
        run.font.size = Pt(actual_pt)
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
