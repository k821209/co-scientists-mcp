"""Section-level reads/writes.

The section doc holds the canonical body text plus metadata (word_count,
status). On every write we regenerate the manuscript.md blob so consumers
that want one file (export, dashboard download) get it for free.
"""
from __future__ import annotations

from ..backends.base import NotFound
from ..state import State
from ..util import now_iso, word_count
from .activity import log_event
from .papers import _paper_path, _regenerate_manuscript, _section_path


def get_section(state: State, slug: str, key: str) -> dict:
    """Return a section doc by key."""
    if state.backend.get_doc(_paper_path(state, slug)) is None:
        raise NotFound(f"paper not found: {slug!r} in project {state.project_id!r}")
    doc = state.backend.get_doc(_section_path(state, slug, key))
    if doc is None:
        raise NotFound(f"section not found: {slug!r}/{key!r}")
    return doc


def list_sections(state: State, slug: str) -> list[dict]:
    """List all sections for a paper, ordered by sort_order."""
    if state.backend.get_doc(_paper_path(state, slug)) is None:
        raise NotFound(f"paper not found: {slug!r} in project {state.project_id!r}")
    pairs = state.backend.list_collection(
        state.project_path("papers", slug, "sections")
    )
    sections = [data for _, data in pairs]
    sections.sort(key=lambda s: s.get("sort_order", 999))
    return sections


def update_section(
    state: State,
    slug: str,
    key: str,
    *,
    body: str | None = None,
    status: str | None = None,
    title: str | None = None,
) -> dict:
    """Update a section's body / status / title; regenerate manuscript blob.

    Returns the updated section doc.
    """
    if state.backend.get_doc(_paper_path(state, slug)) is None:
        raise NotFound(f"paper not found: {slug!r} in project {state.project_id!r}")
    path = _section_path(state, slug, key)
    existing = state.backend.get_doc(path)
    if existing is None:
        raise NotFound(f"section not found: {slug!r}/{key!r}")

    fields: dict = {"updated_at": now_iso()}
    if body is not None:
        fields["body"] = body
        fields["word_count"] = word_count(body)
    if status is not None:
        fields["status"] = status
    if title is not None:
        fields["title"] = title
    state.backend.update_doc(path, fields)

    # Bump paper's updated_at to feed list_papers ordering and dashboard "last activity"
    state.backend.update_doc(_paper_path(state, slug), {"updated_at": fields["updated_at"]})

    _regenerate_manuscript(state, slug)
    log_event(
        state, slug, action="section_updated",
        detail={
            "key": key,
            "word_count": fields.get("word_count"),
            "status": fields.get("status"),
        },
    )
    return state.backend.get_doc(path)


def add_section(
    state: State,
    slug: str,
    *,
    key: str,
    title: str,
    sort_order: float | int,
    body: str = "",
) -> dict:
    """Register a custom section (e.g. journal-specific) beyond the defaults."""
    if state.backend.get_doc(_paper_path(state, slug)) is None:
        raise NotFound(f"paper not found: {slug!r} in project {state.project_id!r}")
    path = _section_path(state, slug, key)
    if state.backend.get_doc(path) is not None:
        raise ValueError(f"section already exists: {slug!r}/{key!r}")
    now = now_iso()
    doc = {
        "key": key,
        "title": title,
        "body": body,
        "word_count": word_count(body),
        "status": "pending",
        "sort_order": sort_order,
        "updated_at": now,
    }
    state.backend.set_doc(path, doc)
    _regenerate_manuscript(state, slug)
    return doc


def get_manuscript(state: State, slug: str) -> str:
    """Return the assembled manuscript.md as a string."""
    if state.backend.get_doc(_paper_path(state, slug)) is None:
        raise NotFound(f"paper not found: {slug!r} in project {state.project_id!r}")
    blob = state.backend.get_blob(state.project_path("papers", slug, "manuscript.md"))
    return blob.decode("utf-8") if blob else ""
