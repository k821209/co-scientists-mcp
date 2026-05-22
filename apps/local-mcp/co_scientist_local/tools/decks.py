"""Decks: presentations built from a paper.

A deck attaches to a paper and holds:
  - `concept`     — palette / typography / motif strings the slides
                    inherit (the "single source of visual unity"). The
                    PPTX export harvests `accent` / `bg` / `text` colors
                    from here to theme native text slides.
  - `theme`       — optional theme slug (e.g. "minimal-modern-academic")
  - `aspect_ratio` — "16:9" (default) | "16:10" | "4:3"; sets PPTX size
  - `audience`    — free text ("lab seminar", "Nature poster", …)
  - `duration_min` — target talk length in minutes
  - slides as a subcollection

Each slide doc carries:
  - `slide_number`  (1-based, sparse during edits, normalized by renumber_deck)
  - `role`          (title | outline | background | method | result |
                     discussion | conclusion | qa | custom)
  - `title`         short slide heading
  - `body`          markdown content for the body text
  - `prompt`        full-image prompt if the slide will be rendered via
                    generate_image (starts with the deck's unity header)
  - `notes`         MANDATORY speaker notes
  - `code`          optional code block (for shape-code render mode)
  - `render_mode`   "code-shape" | "paper-figure" | "ai-image" |
                    "hybrid" | "text". A `text` slide carries no image —
                    it becomes a native (editable) PPTX text slide at
                    export, styled from the deck concept's palette.
  - `figure_number` if render_mode == paper-figure
  - `status`        "draft" | "rendered"

Render + PPTX export are Phase 3 — not implemented here. This module
ships the data layer + CRUD so /paper-deck can build the structure
incrementally.
"""
from __future__ import annotations

from ..backends.base import NotFound
from ..state import State
from ..util import new_id, now_iso, slugify
from .activity import log_event
from .papers import _paper_path

_VALID_ROLES = {
    "title", "outline", "background", "method", "result",
    "discussion", "conclusion", "qa", "custom",
}
_VALID_RENDER_MODES = {"code-shape", "paper-figure", "ai-image", "hybrid", "text"}
_VALID_DECK_STATUS = {"draft", "drafted", "rendered"}
_VALID_SLIDE_STATUS = {"draft", "rendered"}
_VALID_ASPECT = {"16:9", "16:10", "4:3"}


def _ensure_paper(state: State, slug: str) -> None:
    if state.backend.get_doc(_paper_path(state, slug)) is None:
        raise NotFound(f"paper not found: {slug!r} in project {state.project_id!r}")


def _deck_path(state: State, slug: str, deck_id: str) -> str:
    return state.project_path("papers", slug, "decks", deck_id)


def _slides_path(state: State, slug: str, deck_id: str) -> str:
    return state.project_path("papers", slug, "decks", deck_id, "slides")


def _slide_path(state: State, slug: str, deck_id: str, slide_id: str) -> str:
    return state.project_path("papers", slug, "decks", deck_id, "slides", slide_id)


# ─── deck-level CRUD ────────────────────────────────────────────────────────


def create_deck(
    state: State,
    slug: str,
    *,
    title: str,
    audience: str | None = None,
    duration_min: int | None = None,
    theme: str | None = None,
    aspect_ratio: str = "16:9",
    deck_id: str | None = None,
) -> dict:
    """Create a deck attached to `slug`. Idempotent on (slug, deck_id) — if
    deck_id is supplied and exists, returns the existing doc unchanged.
    Without deck_id, deck slug is derived from `title`.
    """
    _ensure_paper(state, slug)
    if not title or not title.strip():
        raise ValueError("title is required")
    if aspect_ratio not in _VALID_ASPECT:
        raise ValueError(
            f"invalid aspect_ratio: {aspect_ratio!r}; "
            f"choose from {sorted(_VALID_ASPECT)}"
        )
    deck_id = deck_id or slugify(title)
    path = _deck_path(state, slug, deck_id)
    existing = state.backend.get_doc(path)
    if existing is not None:
        return existing
    now = now_iso()
    doc = {
        "id": deck_id,
        "title": title,
        "audience": audience,
        "duration_min": duration_min,
        "theme": theme,
        "aspect_ratio": aspect_ratio,
        "concept": None,            # set later via update_deck
        "status": "draft",
        "slide_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    state.backend.set_doc(path, doc)
    log_event(
        state, slug, action="deck_created",
        detail={"deck_id": deck_id, "title": title},
        actor="claude",
    )
    return doc


def get_deck(state: State, slug: str, deck_id: str) -> dict:
    _ensure_paper(state, slug)
    doc = state.backend.get_doc(_deck_path(state, slug, deck_id))
    if doc is None:
        raise NotFound(f"deck not found: {deck_id!r} on paper {slug!r}")
    return doc


def list_decks(state: State, slug: str) -> list[dict]:
    _ensure_paper(state, slug)
    pairs = state.backend.list_collection(state.project_path("papers", slug, "decks"))
    decks = [data for _, data in pairs]
    decks.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return decks


def update_deck(
    state: State,
    slug: str,
    deck_id: str,
    *,
    title: str | None = None,
    audience: str | None = None,
    duration_min: int | None = None,
    theme: str | None = None,
    aspect_ratio: str | None = None,
    concept: str | None = None,
    status: str | None = None,
) -> dict:
    _ensure_paper(state, slug)
    path = _deck_path(state, slug, deck_id)
    cur = state.backend.get_doc(path)
    if cur is None:
        raise NotFound(f"deck not found: {deck_id!r} on paper {slug!r}")
    fields: dict = {"updated_at": now_iso()}
    if title is not None: fields["title"] = title
    if audience is not None: fields["audience"] = audience
    if duration_min is not None: fields["duration_min"] = duration_min
    if theme is not None: fields["theme"] = theme
    if aspect_ratio is not None:
        if aspect_ratio not in _VALID_ASPECT:
            raise ValueError(
                f"invalid aspect_ratio: {aspect_ratio!r}; "
                f"choose from {sorted(_VALID_ASPECT)}"
            )
        fields["aspect_ratio"] = aspect_ratio
    if concept is not None: fields["concept"] = concept
    if status is not None:
        if status not in _VALID_DECK_STATUS:
            raise ValueError(f"invalid deck status: {status!r}")
        fields["status"] = status
    state.backend.update_doc(path, fields)
    return state.backend.get_doc(path)


def delete_deck(state: State, slug: str, deck_id: str) -> bool:
    """Delete deck doc + cascade all slide docs."""
    _ensure_paper(state, slug)
    path = _deck_path(state, slug, deck_id)
    if state.backend.get_doc(path) is None:
        return False
    # cascade slides
    for slide_id, _ in state.backend.list_collection(_slides_path(state, slug, deck_id)):
        state.backend.delete_doc(_slide_path(state, slug, deck_id, slide_id))
    state.backend.delete_doc(path)
    log_event(
        state, slug, action="deck_deleted",
        detail={"deck_id": deck_id}, actor="claude",
    )
    return True


# ─── slide CRUD ─────────────────────────────────────────────────────────────


def _validate_slide_fields(
    role: str | None,
    render_mode: str | None,
    status: str | None,
) -> None:
    if role is not None and role not in _VALID_ROLES:
        raise ValueError(f"invalid role: {role!r}")
    if render_mode is not None and render_mode not in _VALID_RENDER_MODES:
        raise ValueError(f"invalid render_mode: {render_mode!r}")
    if status is not None and status not in _VALID_SLIDE_STATUS:
        raise ValueError(f"invalid slide status: {status!r}")


def add_slide(
    state: State,
    slug: str,
    deck_id: str,
    *,
    slide_number: int,
    role: str,
    title: str,
    body: str = "",
    prompt: str = "",
    notes: str = "",
    code: str = "",
    render_mode: str = "code-shape",
    figure_number: int | None = None,
) -> dict:
    """Append a slide. `slide_number` is the 1-based order. Use
    `renumber_deck` after bulk add/delete to normalize gaps."""
    _ensure_paper(state, slug)
    if state.backend.get_doc(_deck_path(state, slug, deck_id)) is None:
        raise NotFound(f"deck not found: {deck_id!r} on paper {slug!r}")
    _validate_slide_fields(role, render_mode, None)
    if slide_number < 1:
        raise ValueError("slide_number must be >= 1")
    # Doc id is the slide_number zero-padded so list ordering by id matches.
    slide_id = f"s{slide_number:04d}_{new_id()[:6]}"
    now = now_iso()
    doc = {
        "id": slide_id,
        "slide_number": slide_number,
        "role": role,
        "title": title,
        "body": body,
        "prompt": prompt,
        "notes": notes,
        "code": code,
        "render_mode": render_mode,
        "figure_number": figure_number,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    state.backend.set_doc(_slide_path(state, slug, deck_id, slide_id), doc)
    # bump deck.slide_count + updated_at
    deck_path = _deck_path(state, slug, deck_id)
    deck = state.backend.get_doc(deck_path) or {}
    state.backend.update_doc(deck_path, {
        "slide_count": (deck.get("slide_count") or 0) + 1,
        "updated_at": now,
    })
    return doc


def update_slide(
    state: State,
    slug: str,
    deck_id: str,
    slide_id: str,
    *,
    slide_number: int | None = None,
    role: str | None = None,
    title: str | None = None,
    body: str | None = None,
    prompt: str | None = None,
    notes: str | None = None,
    code: str | None = None,
    render_mode: str | None = None,
    figure_number: int | None = None,
    status: str | None = None,
) -> dict:
    _ensure_paper(state, slug)
    path = _slide_path(state, slug, deck_id, slide_id)
    if state.backend.get_doc(path) is None:
        raise NotFound(f"slide not found: {slide_id!r}")
    _validate_slide_fields(role, render_mode, status)
    fields: dict = {"updated_at": now_iso()}
    if slide_number is not None: fields["slide_number"] = slide_number
    if role is not None: fields["role"] = role
    if title is not None: fields["title"] = title
    if body is not None: fields["body"] = body
    if prompt is not None: fields["prompt"] = prompt
    if notes is not None: fields["notes"] = notes
    if code is not None: fields["code"] = code
    if render_mode is not None: fields["render_mode"] = render_mode
    if figure_number is not None: fields["figure_number"] = figure_number
    if status is not None: fields["status"] = status
    state.backend.update_doc(path, fields)
    return state.backend.get_doc(path)


def delete_slide(state: State, slug: str, deck_id: str, slide_id: str) -> bool:
    _ensure_paper(state, slug)
    path = _slide_path(state, slug, deck_id, slide_id)
    if state.backend.get_doc(path) is None:
        return False
    state.backend.delete_doc(path)
    deck_path = _deck_path(state, slug, deck_id)
    deck = state.backend.get_doc(deck_path) or {}
    state.backend.update_doc(deck_path, {
        "slide_count": max(0, (deck.get("slide_count") or 1) - 1),
        "updated_at": now_iso(),
    })
    return True


def list_slides(state: State, slug: str, deck_id: str) -> list[dict]:
    _ensure_paper(state, slug)
    pairs = state.backend.list_collection(_slides_path(state, slug, deck_id))
    slides = [data for _, data in pairs]
    slides.sort(key=lambda s: s.get("slide_number") or 0)
    return slides


def renumber_deck(state: State, slug: str, deck_id: str) -> dict:
    """Pack slide_numbers tightly starting at 1, preserving order.
    Call after bulk add/delete. Returns {old_to_new: {old: new}, count}."""
    _ensure_paper(state, slug)
    slides = list_slides(state, slug, deck_id)
    old_to_new: dict[int, int] = {}
    now = now_iso()
    for i, s in enumerate(slides, start=1):
        old = s.get("slide_number")
        if old != i:
            state.backend.update_doc(
                _slide_path(state, slug, deck_id, s["id"]),
                {"slide_number": i, "updated_at": now},
            )
            if old is not None:
                old_to_new[old] = i
    return {"count": len(slides), "old_to_new": old_to_new}
