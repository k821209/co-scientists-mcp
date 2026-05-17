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
