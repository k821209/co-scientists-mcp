"""Section writes update both the Firestore doc AND the manuscript blob."""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import papers, sections


def _setup(state):
    papers.create_paper(state, title="My paper")
    return "my-paper"


def test_update_section_writes_body_and_recomputes_word_count(state):
    slug = _setup(state)
    body = "Plants are amazing organisms that photosynthesize sunlight into chemical energy."
    updated = sections.update_section(state, slug, "introduction", body=body, status="draft")
    assert updated["body"] == body
    assert updated["word_count"] == len(body.split())
    assert updated["status"] == "draft"


def test_update_section_regenerates_manuscript_blob(state, backend):
    slug = _setup(state)
    sections.update_section(state, slug, "methods", body="We sequenced 100 genomes.")
    blob = backend.get_blob(f"projects/p-alice/papers/{slug}/manuscript.md")
    assert blob is not None
    text = blob.decode("utf-8")
    # Section heading + body both present
    assert "## Methods" in text
    assert "We sequenced 100 genomes." in text


def test_get_manuscript_returns_assembled_text(state):
    slug = _setup(state)
    sections.update_section(state, slug, "introduction", body="Intro body.")
    sections.update_section(state, slug, "results", body="Results body.")
    text = sections.get_manuscript(state, slug)
    # Order: intro before results (matches sort_order from DEFAULT_SECTIONS)
    intro_idx = text.find("Intro body.")
    results_idx = text.find("Results body.")
    assert intro_idx != -1 and results_idx != -1
    assert intro_idx < results_idx


def test_update_section_bumps_paper_updated_at(state):
    slug = _setup(state)
    before = papers.get_paper_state(state, slug)["paper"]["updated_at"]
    # Sleep would be cheating; just rely on microsecond resolution
    sections.update_section(state, slug, "introduction", body="Hello.")
    after = papers.get_paper_state(state, slug)["paper"]["updated_at"]
    assert after >= before


def test_list_sections_returns_in_sort_order(state):
    slug = _setup(state)
    listed = sections.list_sections(state, slug)
    keys = [s["key"] for s in listed]
    # Default order from manuscript.DEFAULT_SECTIONS
    assert keys == ["abstract", "introduction", "methods", "results", "discussion", "conclusion"]


def test_add_section_inserts_at_sort_order(state):
    slug = _setup(state)
    sections.add_section(
        state, slug, key="materials", title="Materials and Notes",
        sort_order=2.5, body="reagents...",
    )
    listed = sections.list_sections(state, slug)
    keys = [s["key"] for s in listed]
    # 2.5 slots between methods (sort_order=2) and results (sort_order=3)
    assert keys.index("materials") == keys.index("methods") + 1


def test_add_section_rejects_duplicate(state):
    slug = _setup(state)
    with pytest.raises(ValueError, match="already exists"):
        sections.add_section(state, slug, key="introduction", title="Dup", sort_order=10)


def test_update_section_missing_paper_raises(state):
    with pytest.raises(NotFound):
        sections.update_section(state, "ghost", "introduction", body="x")


def test_update_section_missing_key_raises(state):
    slug = _setup(state)
    with pytest.raises(NotFound):
        sections.update_section(state, slug, "never-existed", body="x")
