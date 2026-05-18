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
    def __init__(self, doi: str) -> None:
        self.doi = doi
        super().__init__(f"CrossRef returned 404 for {doi!r} — likely a hallucinated DOI")


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
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        raise RuntimeError(
            f"CrossRef HTTP {e.code} {e.reason or ''} for {doi!r}"
            + (f" — {body}" if body else "")
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"CrossRef network error for {doi!r}: {e.reason}") from e
    except TimeoutError as e:
        raise RuntimeError(f"CrossRef timeout ({timeout}s) for {doi!r}") from e
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


def _extract_doi_contexts(state: State, slug: str) -> dict[str, list[dict]]:
    """For each {doi:X} marker in this paper's section bodies, capture the
    surrounding sentence as the agent's "claim" about that DOI.

    Returns {doi_lower: [{"section": key, "sentence": "..."}]}.

    Used by validate_references to compare the manuscript's *intent* (the
    sentence the agent wrote around the citation) against the CrossRef
    title — catches the case where the DOI is real but the agent cited
    an unrelated paper (the most common hallucination once auto-fill has
    overwritten stored_title with CrossRef's truth).
    """
    from . import sections as _sections
    contexts: dict[str, list[dict]] = {}
    secs = _sections.list_sections(state, slug)
    pattern = re.compile(r"\{doi:([^}\s]+)\}", re.IGNORECASE)
    for sec in secs:
        body = sec.get("body") or ""
        if not body:
            continue
        for m in pattern.finditer(body):
            doi = m.group(1).lower()
            sentence = _sentence_around(body, m.start(), m.end())
            contexts.setdefault(doi, []).append({
                "section": sec.get("key", ""),
                "sentence": sentence,
            })
    return contexts


def _sentence_around(body: str, start: int, end: int) -> str:
    """Extract the sentence containing positions [start, end)."""
    # Walk backwards to sentence start
    s = start
    while s > 0 and body[s - 1] not in ".!?\n":
        s -= 1
    # Walk forwards to sentence end
    e = end
    while e < len(body) and body[e] not in ".!?\n":
        e += 1
    return body[s:e].strip()


def validate_references(state: State, slug: str) -> dict:
    """Run CrossRef against every reference in a paper and check citation
    context. Categorizes results and persists each verdict to
    /papers/{slug}/verification_findings/{doi_safe}.

    Three independent checks per DOI:

      1. **DOI resolves** — CrossRef returns the work. Failure → `unresolved`
         (almost certainly a hallucinated DOI).
      2. **Stored-title match** — `stored_title` (the reference doc's title
         field) shares ≥3 substantive words with CrossRef title. Mismatch →
         `title_mismatch`. NOTE: this check is useless after the dashboard
         "Sync DOIs" button or any auto-fill has overwritten stored_title
         with the CrossRef title (then they always match).
      3. **Context match** — for each {doi:X} marker in section text, the
         surrounding sentence shares ≥2 substantive words with CrossRef
         title. Mismatch → `context_mismatch`. This catches "real DOI,
         wrong paper for the context" hallucinations that survive (2).

    Returns dict with keys: total, resolved, unresolved, title_mismatch,
    context_mismatch, missing_doi, errors. A single DOI can appear in
    BOTH title_mismatch and context_mismatch (independent signals).
    """
    # Local import to avoid circular dep
    from . import verification as _verification

    contexts = _extract_doi_contexts(state, slug)
    refs = list_references(state, slug)
    resolved: list[dict] = []
    unresolved: list[dict] = []
    missing_doi: list[dict] = []
    title_mismatch: list[dict] = []
    context_mismatch: list[dict] = []
    errors: list[dict] = []
    now = now_iso()
    inline_only = set(contexts.keys())

    def _resolve(doi, *, registered, key=None, stored_title=None):
        """Verify one DOI (existence + context). Mutates the buckets above.
        Writes a SINGLE finding doc with both verification axes."""
        nonlocal resolved, unresolved, missing_doi, title_mismatch, context_mismatch, errors
        source = "registered_ref" if registered else "inline"
        try:
            meta = _fetch_crossref(doi)
        except DoiNotFound:
            unresolved.append({"citation_key": key, "doi": doi, "stored_title": stored_title})
            _write_finding(
                state, slug, doi=doi, kind="unresolved", source=source,
                ref_citation_key=key, stored_title=stored_title,
                doi_verified=False, now=now, verification=_verification,
            )
            return
        except Exception as e:
            errors.append({"citation_key": key, "doi": doi, "error": str(e)})
            _write_finding(
                state, slug, doi=doi, kind="error", source=source,
                ref_citation_key=key, message=str(e),
                now=now, verification=_verification,
            )
            return

        crossref_title = meta.get("title") or ""
        # Title check (only meaningful for registered refs where agent set a title)
        shared_title = _shared_words((stored_title or "").lower(), crossref_title.lower())
        title_problem = registered and bool(stored_title and stored_title.strip()) and shared_title < 3
        # Context check
        ctxs = contexts.get(doi, [])
        checkable = [c for c in ctxs if _substantive_word_count(c["sentence"]) >= 3]
        if checkable:
            best = max(
                _shared_words(c["sentence"].lower(), crossref_title.lower())
                for c in checkable
            )
            worst = min(
                checkable,
                key=lambda c: _shared_words(c["sentence"].lower(), crossref_title.lower()),
            )
            context_verified = best >= 2
        else:
            best = None
            worst = None
            context_verified = None  # can't check — leave for human review

        entry = {
            "citation_key": key, "doi": doi,
            "stored_title": stored_title,
            "crossref_title": crossref_title,
            "shared_title_words": shared_title if registered else None,
            "context_count": len(ctxs),
            "best_context_shared_words": best,
            "worst_context": worst,
            "doi_verified": True,
            "context_verified": context_verified,
        }
        # Bucket according to the dominant problem (context > title > resolved)
        if context_verified is False:
            context_mismatch.append(entry)
            kind = "context_mismatch"
        elif title_problem:
            title_mismatch.append(entry)
            kind = "title_mismatch"
        else:
            resolved.append(entry)
            kind = "resolved"
        _write_finding(
            state, slug, doi=doi, kind=kind, source=source,
            ref_citation_key=key, stored_title=stored_title,
            crossref_title=crossref_title, shared_words=best if best is not None else shared_title,
            context_sentence=(worst or {}).get("sentence") if worst else None,
            context_section=(worst or {}).get("section") if worst else None,
            doi_verified=True, context_verified=context_verified,
            now=now, verification=_verification,
        )

    for r in refs:
        key = r.get("citation_key", "")
        doi = (r.get("doi") or "").strip().lower()
        if not doi:
            missing_doi.append({"citation_key": key, "title": r.get("title")})
            continue
        inline_only.discard(doi)
        _resolve(doi, registered=True, key=key, stored_title=r.get("title"))

    for doi in inline_only:
        _resolve(doi, registered=False)

    return {
        "total": len(refs) + len(inline_only),
        "resolved": resolved,
        "unresolved": unresolved,
        "title_mismatch": title_mismatch,        # legacy axis — auto-fill kills it
        "context_mismatch": context_mismatch,    # the real hallucination catcher
        "missing_doi": missing_doi,
        "errors": errors,
    }


def _write_finding(
    state: State, slug: str, *,
    doi: str, kind: str, source: str,
    ref_citation_key: str | None = None,
    stored_title: str | None = None,
    crossref_title: str | None = None,
    shared_words: int | None = None,
    message: str | None = None,
    context_sentence: str | None = None,
    context_section: str | None = None,
    doi_verified: bool | None = None,
    context_verified: bool | None = None,
    now: str,
    verification,
) -> None:
    """Persist one verification verdict as a Firestore doc.

    Two independent axes (`doi_verified`, `context_verified`) get set in the
    same doc but tagged with who set them and when. set_doc uses merge=True
    so the browser's DOI-only sync and the MCP's context check coexist.
    """
    doc_id = verification._doi_safe_id(doi)
    payload = {
        "doi": doi.lower(),
        "kind": kind,
        "source": source,
        "detected_at": now,
        "acknowledged": False,
    }
    if ref_citation_key is not None:
        payload["ref_citation_key"] = ref_citation_key
    if stored_title is not None:
        payload["stored_title"] = stored_title
    if crossref_title is not None:
        payload["crossref_title"] = crossref_title
    if shared_words is not None:
        payload["shared_words"] = shared_words
    if message is not None:
        payload["message"] = message
    if context_sentence is not None:
        payload["context_sentence"] = context_sentence
    if context_section is not None:
        payload["context_section"] = context_section
    if doi_verified is not None:
        payload["doi_verified"] = doi_verified
        payload["doi_checked_at"] = now
        payload["doi_checked_by"] = "agent"
    if context_verified is not None:
        payload["context_verified"] = context_verified
        payload["context_checked_at"] = now
        payload["context_checked_by"] = "agent"
    state.backend.set_doc_merge(
        verification._finding_doc_path(state, slug, doc_id),
        payload,
    )


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


def _substantive_word_count(s: str) -> int:
    """How many substantive (non-stopword, ≥3-char) ASCII words a string has.
    Used as a 'is this context even checkable?' gate."""
    return len({
        w for w in re.findall(r"[a-z]+", s.lower())
        if w not in _STOPWORDS and len(w) > 2
    })
