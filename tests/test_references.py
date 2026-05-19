"""References: CRUD + simple search; citation_key uniqueness; isolation."""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import papers, references


def _setup(state):
    papers.create_paper(state, title="My paper")
    return "my-paper"


def test_add_and_get_reference(state):
    slug = _setup(state)
    r = references.add_reference(
        state, slug, citation_key="smith2024",
        title="Plant evolution review",
        authors=["Smith, J", "Lee, K"], journal="Cell", year=2024,
        doi="10.1234/example",
    )
    assert r["citation_key"] == "smith2024"
    assert r["authors"] == ["Smith, J", "Lee, K"]
    same = references.get_reference(state, slug, "smith2024")
    assert same == r


def test_duplicate_citation_key_rejected(state):
    slug = _setup(state)
    references.add_reference(state, slug, citation_key="a2024", title="A")
    with pytest.raises(ValueError, match="already exists"):
        references.add_reference(state, slug, citation_key="a2024", title="A2")


def test_search_by_doi(state):
    slug = _setup(state)
    references.add_reference(state, slug, citation_key="a", title="X", doi="10.1/a")
    references.add_reference(state, slug, citation_key="b", title="Y", doi="10.1/b")
    hits = references.search_references(state, slug, doi="10.1/b")
    assert len(hits) == 1
    assert hits[0]["citation_key"] == "b"


def test_search_by_title_substring_is_case_insensitive(state):
    slug = _setup(state)
    references.add_reference(state, slug, citation_key="a", title="Maize Genome Annotation")
    references.add_reference(state, slug, citation_key="b", title="Rice transcriptome study")
    hits = references.search_references(state, slug, title_contains="GENOME")
    assert [h["citation_key"] for h in hits] == ["a"]


def test_search_by_year(state):
    slug = _setup(state)
    references.add_reference(state, slug, citation_key="a", title="X", year=2023)
    references.add_reference(state, slug, citation_key="b", title="Y", year=2024)
    references.add_reference(state, slug, citation_key="c", title="Z", year=2024)
    hits = references.search_references(state, slug, year=2024)
    assert sorted(h["citation_key"] for h in hits) == ["b", "c"]


def test_list_references_sorted_by_citation_key(state):
    slug = _setup(state)
    for key in ["zhao2024", "abe2023", "li2024"]:
        references.add_reference(state, slug, citation_key=key, title=key)
    keys = [r["citation_key"] for r in references.list_references(state, slug)]
    assert keys == ["abe2023", "li2024", "zhao2024"]


def test_update_reference_patches_fields(state):
    slug = _setup(state)
    references.add_reference(state, slug, citation_key="a", title="Original")
    updated = references.update_reference(state, slug, "a", title="Revised", year=2025)
    assert updated["title"] == "Revised"
    assert updated["year"] == 2025


def test_delete_reference(state):
    slug = _setup(state)
    references.add_reference(state, slug, citation_key="a", title="X")
    assert references.delete_reference(state, slug, "a") is True
    assert references.delete_reference(state, slug, "a") is False  # idempotent


def test_reference_isolation_between_users(state, other_state):
    slug = _setup(state)
    references.add_reference(state, slug, citation_key="a", title="alice's ref")
    with pytest.raises(NotFound):
        references.list_references(other_state, slug)


def test_get_missing_reference_raises(state):
    slug = _setup(state)
    with pytest.raises(NotFound):
        references.get_reference(state, slug, "ghost")


def test_validate_references_emits_facts_pack(state, monkeypatch):
    """Server's job is to gather facts, not judge context. The result
    should include CrossRef metadata + manuscript contexts so the agent
    can make the call."""
    slug = _setup(state)
    references.add_reference(
        state, slug, citation_key="smith2024",
        title="Plant evolution review",
        doi="10.1234/example",
    )
    references.add_reference(
        state, slug, citation_key="nodoi",
        title="Untitled work without DOI",
    )

    def _fake_fetch(doi, *, timeout=15):
        if doi == "10.1234/example":
            return {
                "doi": doi, "title": "Plant evolution review",
                "abstract": "We review plant evolution.",
                "subjects": ["Plant Science"],
                "authors": ["J Smith"], "journal": "Cell",
                "year": 2024, "url": None, "type": "journal-article",
            }
        raise references.DoiNotFound(doi)
    monkeypatch.setattr(references, "_fetch_crossref", _fake_fetch)

    result = references.validate_references(state, slug)
    assert result["total"] == 2
    assert len(result["results"]) == 1
    assert len(result["missing_doi"]) == 1
    assert result["unresolved"] == []
    # Facts pack content
    entry = result["results"][0]
    assert entry["doi_verified"] is True
    assert entry["crossref"]["title"] == "Plant evolution review"
    assert "Plant Science" in entry["crossref"]["subjects"]
    assert entry["crossref"]["abstract"]


def test_validate_references_no_context_verdict(state, monkeypatch):
    """Even when shared-words is 0, the server doesn't say it's wrong —
    the agent decides. Server still records the signal."""
    slug = _setup(state)
    references.add_reference(
        state, slug, citation_key="bogus2024",
        title="Somatic mutation rates scale with lifespan across mammals",
        doi="10.1038/s41586-022-04618-z",
    )
    from co_scientist_local.tools import sections
    sections.update_section(
        state, slug, "introduction",
        body="T2T plant pangenome assemblies are now routine {doi:10.1038/s41586-022-04618-z}.",
    )

    def _fake_fetch(doi, *, timeout=15):
        return {
            "doi": doi,
            "title": "Somatic mutation rates scale with lifespan across mammals",
            "abstract": "", "subjects": [],
            "authors": ["G Kucsko"], "journal": "Nature",
            "year": 2022, "url": None, "type": "journal-article",
        }
    monkeypatch.setattr(references, "_fetch_crossref", _fake_fetch)

    result = references.validate_references(state, slug)
    # NO context_mismatch bucket — it's gone. Agent decides via the signal.
    assert "context_mismatch" not in result
    assert len(result["results"]) == 1
    entry = result["results"][0]
    assert entry["signals"]["best_context_overlap_words"] == 0
    assert entry["doi_verified"] is True
    # Context decision is NOT made by server
    # (no context_verified key on the result entry — that's agent territory)


def test_extract_doi_contexts_stacked_citation(state):
    """Stacked citations get stacked_with peers so the agent knows the
    DOI was part of a multi-citation chunk."""
    slug = _setup(state)
    from co_scientist_local.tools import sections
    sections.update_section(
        state, slug, "introduction",
        body="Pangenome studies in humans {doi:10.1/a}, maize {doi:10.1/b}, and rice {doi:10.1/c} revealed variation.",
    )
    contexts = references._extract_doi_contexts(state, slug)
    assert set(contexts.keys()) == {"10.1/a", "10.1/b", "10.1/c"}
    # Each DOI knows about its siblings
    assert set(contexts["10.1/a"][0]["stacked_with"]) == {"10.1/b", "10.1/c"}
    assert set(contexts["10.1/b"][0]["stacked_with"]) == {"10.1/a", "10.1/c"}


def test_search_works_normalizes_each_hit(monkeypatch):
    """search_works returns normalized CrossRef metadata per hit."""
    import urllib.request as ur

    fake_payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1/foo",
                    "title": ["A study"],
                    "author": [{"given": "Jane", "family": "Smith"}],
                    "container-title": ["Cell"],
                    "issued": {"date-parts": [[2024]]},
                    "subject": ["Plant Sci"],
                    "abstract": "<jats>concise</jats>",
                    "URL": "https://doi.org/10.1/foo",
                    "type": "journal-article",
                },
                {
                    "DOI": "10.2/bar",
                    "title": ["Another"],
                    "issued": {"date-parts": [[2025]]},
                },
            ],
        },
    }

    class FakeResp:
        def __init__(self, b): self.b = b
        def read(self): return self.b
        def __enter__(self): return self
        def __exit__(self, *a): return False

    captured: dict = {}
    def fake_urlopen(req, timeout=20):
        captured["url"] = req.full_url
        import json
        return FakeResp(json.dumps(fake_payload).encode())
    monkeypatch.setattr(ur, "urlopen", fake_urlopen)

    hits = references.search_works(
        None, query="plant pangenome", limit=2, year_from=2022,
    )
    assert len(hits) == 2
    assert hits[0]["doi"] == "10.1/foo"
    assert hits[0]["title"] == "A study"
    assert hits[0]["authors"] == ["Jane Smith"]
    assert hits[0]["journal"] == "Cell"
    assert hits[0]["year"] == 2024
    assert hits[0]["abstract"] == "concise"
    assert "Plant Sci" in hits[0]["subjects"]
    # Year filter actually went into the URL
    assert "from-pub-date%3A2022" in captured["url"]


def test_search_works_empty_query_raises():
    import pytest
    with pytest.raises(ValueError):
        references.search_works(None, query="")
    with pytest.raises(ValueError):
        references.search_works(None, query="   ")


def test_delete_reference_cascades_finding(state, monkeypatch):
    """Deleting a reference should remove the doi-keyed finding doc too,
    so the dashboard doesn't show a zombie ⚠ for a citation that's gone."""
    slug = _setup(state)
    references.add_reference(
        state, slug, citation_key="x", title="X", doi="10.1/x",
    )

    def _fake_fetch(doi, *, timeout=15):
        return {
            "doi": doi, "title": "X", "abstract": "", "subjects": [],
            "authors": [], "journal": None, "year": None,
            "url": None, "type": "journal-article",
        }
    monkeypatch.setattr(references, "_fetch_crossref", _fake_fetch)

    references.validate_references(state, slug)
    from co_scientist_local.tools import verification as _v
    # Finding exists before deletion
    findings_before = _v.list_verification_findings(
        state, slug, only_unacknowledged=False, only_problems=False,
    )
    assert any(f.get("doi") == "10.1/x" for f in findings_before)

    references.delete_reference(state, slug, "x")

    findings_after = _v.list_verification_findings(
        state, slug, only_unacknowledged=False, only_problems=False,
    )
    assert not any(f.get("doi") == "10.1/x" for f in findings_after)


def test_acknowledge_finding_records_agent_verdict(state, monkeypatch):
    """The agent's verdict (approved/rejected) is recorded on the finding,
    setting context_verified accordingly."""
    slug = _setup(state)
    references.add_reference(
        state, slug, citation_key="x", title="X", doi="10.1/x",
    )

    def _fake_fetch(doi, *, timeout=15):
        return {
            "doi": doi, "title": "X", "abstract": "", "subjects": [],
            "authors": [], "journal": None, "year": None,
            "url": None, "type": "journal-article",
        }
    monkeypatch.setattr(references, "_fetch_crossref", _fake_fetch)

    references.validate_references(state, slug)
    from co_scientist_local.tools import verification as _v
    doc = _v.acknowledge_finding(
        state, slug, "10.1/x", verdict="approved", note="checked abstract"
    )
    assert doc["context_verified"] is True
    assert doc["agent_verdict"] == "approved"
    assert doc["acknowledged_note"] == "checked abstract"

    # Re-call with rejected on a fresh finding
    references.add_reference(
        state, slug, citation_key="y", title="Y", doi="10.1/y",
    )
    references.validate_references(state, slug)
    doc2 = _v.acknowledge_finding(state, slug, "10.1/y", verdict="rejected")
    assert doc2["context_verified"] is False
