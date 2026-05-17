"""References: bibliographic records.

Paths:
    doc: users/{uid}/papers/{slug}/references/{citation_key}

`citation_key` is the natural key (e.g. "smith2024"). DOI/PMID resolution
(crossref/pubmed lookup) is a future tool that calls add_reference under
the hood — those go through the local MCP, not the cloud, because they're
just HTTP requests the local machine can make freely.

For v0 we only support manual `add_reference`. Searching/filtering is by
field-equality.
"""
from __future__ import annotations

from ..backends.base import NotFound
from ..state import State
from ..util import now_iso
from .papers import _paper_path


def _ref_path(state: State, slug: str, citation_key: str) -> str:
    return state.project_path("papers", slug, "references", citation_key)


def _ensure_paper(state: State, slug: str) -> None:
    if state.backend.get_doc(_paper_path(state, slug)) is None:
        raise NotFound(f"paper not found: {slug!r} in project {state.project_id!r}")


def add_reference(
    state: State,
    slug: str,
    *,
    citation_key: str,
    title: str,
    authors: list[str] | str | None = None,
    journal: str | None = None,
    year: int | None = None,
    doi: str | None = None,
    pmid: str | None = None,
    bibtex: str | None = None,
    cited_in: list[str] | None = None,
) -> dict:
    _ensure_paper(state, slug)
    if not citation_key or not citation_key.strip():
        raise ValueError("citation_key is required")
    path = _ref_path(state, slug, citation_key)
    if state.backend.get_doc(path) is not None:
        raise ValueError(f"reference {citation_key!r} already exists for {slug!r}")
    now = now_iso()
    doc = {
        "citation_key": citation_key,
        "title": title,
        "authors": list(authors) if isinstance(authors, list) else authors,
        "journal": journal,
        "year": year,
        "doi": doi,
        "pmid": pmid,
        "bibtex": bibtex,
        "cited_in": list(cited_in or []),
        "created_at": now,
        "updated_at": now,
    }
    state.backend.set_doc(path, doc)
    return doc


def update_reference(
    state: State,
    slug: str,
    citation_key: str,
    *,
    title: str | None = None,
    authors: list[str] | str | None = None,
    journal: str | None = None,
    year: int | None = None,
    doi: str | None = None,
    pmid: str | None = None,
    bibtex: str | None = None,
    cited_in: list[str] | None = None,
) -> dict:
    _ensure_paper(state, slug)
    path = _ref_path(state, slug, citation_key)
    if state.backend.get_doc(path) is None:
        raise NotFound(f"reference {citation_key!r} not found for {slug!r}")
    fields: dict = {"updated_at": now_iso()}
    if title is not None: fields["title"] = title
    if authors is not None: fields["authors"] = list(authors) if isinstance(authors, list) else authors
    if journal is not None: fields["journal"] = journal
    if year is not None: fields["year"] = year
    if doi is not None: fields["doi"] = doi
    if pmid is not None: fields["pmid"] = pmid
    if bibtex is not None: fields["bibtex"] = bibtex
    if cited_in is not None: fields["cited_in"] = list(cited_in)
    state.backend.update_doc(path, fields)
    return state.backend.get_doc(path)


def get_reference(state: State, slug: str, citation_key: str) -> dict:
    _ensure_paper(state, slug)
    doc = state.backend.get_doc(_ref_path(state, slug, citation_key))
    if doc is None:
        raise NotFound(f"reference {citation_key!r} not found for {slug!r}")
    return doc


def list_references(state: State, slug: str) -> list[dict]:
    """List references ordered by citation_key (lexicographic — natural for bib lists)."""
    _ensure_paper(state, slug)
    pairs = state.backend.list_collection(state.project_path("papers", slug, "references"))
    refs = [data for _, data in pairs]
    refs.sort(key=lambda r: r.get("citation_key", ""))
    return refs


def search_references(
    state: State,
    slug: str,
    *,
    doi: str | None = None,
    pmid: str | None = None,
    year: int | None = None,
    title_contains: str | None = None,
) -> list[dict]:
    """Field-equality + substring search. v0 scans all references (small N)."""
    refs = list_references(state, slug)
    if doi is not None:
        refs = [r for r in refs if r.get("doi") == doi]
    if pmid is not None:
        refs = [r for r in refs if r.get("pmid") == pmid]
    if year is not None:
        refs = [r for r in refs if r.get("year") == year]
    if title_contains:
        needle = title_contains.lower()
        refs = [r for r in refs if needle in (r.get("title", "") or "").lower()]
    return refs


def delete_reference(state: State, slug: str, citation_key: str) -> bool:
    _ensure_paper(state, slug)
    path = _ref_path(state, slug, citation_key)
    if state.backend.get_doc(path) is None:
        return False
    state.backend.delete_doc(path)
    return True
