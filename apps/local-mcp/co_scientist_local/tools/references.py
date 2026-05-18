"""References: bibliographic records + CrossRef DOI verification.

Paths:
    doc: projects/{pid}/papers/{slug}/references/{citation_key}

`citation_key` is the natural key (e.g. "smith2024"). DOI resolution uses
CrossRef's public API (no auth, generous rate limit). Calls are made from
the local MCP — the cloud has nothing to do with them.

Two purposes for the CrossRef integration:
1. **Auto-populate** (`add_reference_by_doi`): pull title/authors/journal/
   year from CrossRef so the agent doesn't have to invent them.
2. **Hallucination check** (`verify_doi`, `validate_references`): catch
   fake DOIs the LLM made up. If CrossRef returns 404, the citation is
   suspect.
"""
from __future__ import annotations

import json as _json
import re
import urllib.error
import urllib.parse
import urllib.request

from ..backends.base import NotFound
from ..state import State
from ..util import now_iso
from .papers import _paper_path

_CROSSREF_BASE = "https://api.crossref.org/works/"
_CROSSREF_UA = "co-scientist-local/0.1 (mailto:dev@co-scientist.example)"


class DoiNotFound(Exception):
    """Raised when CrossRef cannot resolve a DOI (likely hallucinated)."""


def _fetch_crossref(doi: str, *, timeout: int = 15) -> dict:
    """Fetch CrossRef metadata for a DOI. Raises DoiNotFound on 404."""
    doi = (doi or "").strip().lstrip("/")
    # Strip a leading https://doi.org/ if the agent passes a URL.
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    if not doi:
        raise ValueError("doi is required")
    url = _CROSSREF_BASE + urllib.parse.quote(doi, safe="/")
    req = urllib.request.Request(url, headers={"User-Agent": _CROSSREF_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = _json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise DoiNotFound(doi) from None
        raise RuntimeError(f"CrossRef HTTP {e.code} for {doi!r}") from e
    msg = payload.get("message", {})
    return _normalize_crossref(msg, doi)


def _normalize_crossref(msg: dict, doi: str) -> dict:
    """Flatten CrossRef's response into the fields add_reference expects."""
    title_list = msg.get("title") or []
    title = title_list[0] if title_list else ""
    container = msg.get("container-title") or []
    journal = container[0] if container else None
    issued = (msg.get("issued") or {}).get("date-parts") or [[]]
    year = issued[0][0] if issued and issued[0] else None
    authors = []
    for a in msg.get("author") or []:
        given = a.get("given") or ""
        family = a.get("family") or ""
        full = (given + " " + family).strip() or a.get("name") or ""
        if full:
            authors.append(full)
    return {
        "doi": (msg.get("DOI") or doi).lower(),
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": year,
        "url": msg.get("URL"),
        "type": msg.get("type"),
        "crossref_raw": msg,
    }


def _derive_citation_key(meta: dict) -> str:
    """smith2024 from first-author surname + year. Fallback to last DOI segment."""
    authors = meta.get("authors") or []
    year = meta.get("year")
    if authors and year:
        surname = authors[0].split()[-1].lower()
        # Keep only letters (handle Korean/Cyrillic by falling back to ascii subset)
        surname_ascii = re.sub(r"[^a-z]", "", surname)
        if surname_ascii:
            return f"{surname_ascii}{year}"
    # Fallback: last DOI segment with non-alnum stripped
    doi = (meta.get("doi") or "").rsplit("/", 1)[-1]
    return re.sub(r"[^a-z0-9]", "", doi.lower()) or "ref"


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


# ─── CrossRef-backed DOI tools ───────────────────────────────────────────────


def verify_doi(state: State, doi: str) -> dict:
    """Resolve a DOI against CrossRef. Returns metadata if real, raises
    DoiNotFound if CrossRef has no record of it (likely hallucinated).

    No Firestore writes. Use this to spot-check a single citation before
    inserting it into a manuscript.
    """
    return _fetch_crossref(doi)


def add_reference_by_doi(
    state: State,
    slug: str,
    *,
    doi: str,
    citation_key: str | None = None,
    cited_in: list[str] | None = None,
) -> dict:
    """Fetch CrossRef metadata for `doi` and add the reference. Auto-derives
    citation_key from first-author surname + year if not given. Raises
    DoiNotFound if CrossRef returns 404 — refuse to store hallucinated DOIs.
    """
    _ensure_paper(state, slug)
    meta = _fetch_crossref(doi)
    key = citation_key or _derive_citation_key(meta)
    # If the derived key collides, append a letter (smith2024 → smith2024a, b, …).
    if state.backend.get_doc(_ref_path(state, slug, key)) is not None:
        for suffix in "abcdefghijklmnopqrstuvwxyz":
            cand = f"{key}{suffix}"
            if state.backend.get_doc(_ref_path(state, slug, cand)) is None:
                key = cand
                break
        else:
            raise ValueError(f"citation_key {key!r} exhausted (a–z all taken)")
    return add_reference(
        state, slug,
        citation_key=key,
        title=meta["title"],
        authors=meta["authors"],
        journal=meta["journal"],
        year=meta["year"],
        doi=meta["doi"],
        cited_in=cited_in,
    )


def enrich_reference_from_doi(state: State, slug: str, citation_key: str) -> dict:
    """For an existing reference that has a DOI but lacks metadata, fetch
    CrossRef and fill in missing fields (title, authors, journal, year).
    Does not overwrite existing non-empty fields.
    """
    _ensure_paper(state, slug)
    path = _ref_path(state, slug, citation_key)
    cur = state.backend.get_doc(path)
    if cur is None:
        raise NotFound(f"reference {citation_key!r} not found for {slug!r}")
    doi = cur.get("doi")
    if not doi:
        raise ValueError(f"reference {citation_key!r} has no DOI to enrich from")
    meta = _fetch_crossref(doi)
    fields: dict = {"updated_at": now_iso()}
    # Fill only blanks — never overwrite user-edited values.
    if not cur.get("title") and meta.get("title"):
        fields["title"] = meta["title"]
    if not cur.get("authors") and meta.get("authors"):
        fields["authors"] = meta["authors"]
    if not cur.get("journal") and meta.get("journal"):
        fields["journal"] = meta["journal"]
    if not cur.get("year") and meta.get("year"):
        fields["year"] = meta["year"]
    if len(fields) == 1:
        return cur  # nothing to add
    state.backend.update_doc(path, fields)
    return state.backend.get_doc(path)


def validate_references(state: State, slug: str) -> dict:
    """Run CrossRef against every reference in a paper. Categorizes:

      - `resolved`: DOI exists on CrossRef and metadata matches loosely
      - `unresolved`: DOI returned 404 — almost certainly hallucinated
      - `missing_doi`: reference has no DOI field at all
      - `errors`: transient network/CrossRef failures (retry later)

    Title-mismatch heuristic: if the stored title and CrossRef title share
    fewer than 3 substantive words, flag for review (CrossRef title is
    authoritative). This catches "right DOI, wrong title" hallucinations.
    """
    refs = list_references(state, slug)
    resolved: list[dict] = []
    unresolved: list[dict] = []
    missing_doi: list[dict] = []
    title_mismatch: list[dict] = []
    errors: list[dict] = []
    for r in refs:
        key = r.get("citation_key", "")
        doi = (r.get("doi") or "").strip()
        if not doi:
            missing_doi.append({"citation_key": key, "title": r.get("title")})
            continue
        try:
            meta = _fetch_crossref(doi)
        except DoiNotFound:
            unresolved.append({
                "citation_key": key, "doi": doi, "stored_title": r.get("title"),
            })
            continue
        except Exception as e:
            errors.append({"citation_key": key, "doi": doi, "error": str(e)})
            continue
        # Loose title comparison — 3+ shared substantive words
        stored_title = (r.get("title") or "").lower()
        crossref_title = (meta.get("title") or "").lower()
        shared = _shared_words(stored_title, crossref_title)
        entry = {
            "citation_key": key, "doi": doi,
            "stored_title": r.get("title"),
            "crossref_title": meta.get("title"),
            "shared_title_words": shared,
        }
        if shared < 3 and stored_title:
            title_mismatch.append(entry)
        else:
            resolved.append(entry)
    return {
        "total": len(refs),
        "resolved": resolved,
        "unresolved": unresolved,           # hallucination suspects
        "title_mismatch": title_mismatch,   # wrong-paper-for-DOI suspects
        "missing_doi": missing_doi,
        "errors": errors,
    }


_STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "in", "on", "for", "to", "from",
    "with", "by", "is", "are", "was", "were", "be", "been", "as", "at",
    "this", "that", "these", "those", "we", "our", "their", "its",
}


def _shared_words(a: str, b: str) -> int:
    """Count substantive words shared between two titles (lowercased)."""
    def words(s: str) -> set[str]:
        return {w for w in re.findall(r"[a-z]+", s) if w not in _STOPWORDS and len(w) > 2}
    return len(words(a) & words(b))
