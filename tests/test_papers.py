"""CRUD round-trip + per-user isolation."""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import papers


def test_create_paper_seeds_canonical_sections(state):
    paper = papers.create_paper(state, title="Rice TE evolution", journal="Nature")
    assert paper["slug"] == "rice-te-evolution"
    assert paper["title"] == "Rice TE evolution"
    assert paper["journal"] == "Nature"
    assert paper["status"] == "draft"
    assert paper["owner_uid"] == "alice"

    bundle = papers.get_paper_state(state, "rice-te-evolution")
    section_keys = {s["key"] for s in bundle["sections"]}
    assert {"abstract", "introduction", "methods", "results", "discussion", "conclusion"} <= section_keys
    # Manuscript blob is generated immediately with section headers visible
    assert "## Introduction" in bundle["manuscript"]
    assert "## Methods" in bundle["manuscript"]


def test_create_paper_with_explicit_slug(state):
    p = papers.create_paper(state, title="A long title that would slugify weirdly", slug="my-paper")
    assert p["slug"] == "my-paper"


def test_create_paper_rejects_duplicate_slug(state):
    papers.create_paper(state, title="Paper one")
    with pytest.raises(ValueError, match="already exists"):
        papers.create_paper(state, title="Paper one")


def test_list_papers_ordered_by_updated_at_desc(state):
    papers.create_paper(state, title="First paper")
    papers.create_paper(state, title="Second paper")
    listed = papers.list_papers(state)
    assert len(listed) == 2
    # Second paper was created last → appears first
    assert listed[0]["slug"] == "second-paper"


def test_update_paper_patches_only_provided_fields(state):
    papers.create_paper(state, title="Original", journal="Nature")
    updated = papers.update_paper(state, "original", status="in_progress")
    assert updated["status"] == "in_progress"
    assert updated["journal"] == "Nature"  # unchanged
    assert updated["title"] == "Original"  # unchanged


def test_update_paper_title_regenerates_manuscript_blob(state):
    papers.create_paper(state, title="Old title")
    papers.update_paper(state, "old-title", title="New title")
    bundle = papers.get_paper_state(state, "old-title")
    assert bundle["manuscript"].startswith("# New title")


def test_delete_paper_removes_doc_subcollections_and_blob(state, backend):
    papers.create_paper(state, title="To delete")
    assert papers.delete_paper(state, "to-delete") is True

    with pytest.raises(NotFound):
        papers.get_paper_state(state, "to-delete")
    # No leftover docs or blobs at this path
    assert backend.get_doc("projects/p-alice/papers/to-delete") is None
    assert backend.get_doc("projects/p-alice/papers/to-delete/sections/introduction") is None
    assert backend.get_blob("projects/p-alice/papers/to-delete/manuscript.md") is None


def test_delete_paper_returns_false_when_missing(state):
    assert papers.delete_paper(state, "ghost") is False


def test_users_cannot_see_each_others_papers(state, other_state):
    papers.create_paper(state, title="Alice's secret paper")
    assert len(papers.list_papers(state)) == 1
    assert len(papers.list_papers(other_state)) == 0
    with pytest.raises(NotFound):
        papers.get_paper_state(other_state, "alice-s-secret-paper")


def test_get_missing_paper_raises_not_found(state):
    with pytest.raises(NotFound):
        papers.get_paper_state(state, "never-existed")
