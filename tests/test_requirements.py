"""Journal / paper-type submission requirements: set + deterministic check."""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import (
    figures,
    papers,
    references,
    requirements,
    sections,
    tables,
)


def _setup(state):
    papers.create_paper(state, title="Rice TE evolution", journal="Nature")
    return "rice-te-evolution"


# ── set_paper_requirements ───────────────────────────────────

def test_set_and_get_requirements(state):
    slug = _setup(state)
    out = requirements.set_paper_requirements(
        state, slug, paper_type="Short Communication",
        abstract_max_words=150, main_text_max_words=2000,
        max_figures=4, max_references=30,
        required_sections=["abstract", "results"],
        notes="Methods at the end.", source="https://example.org/guide",
    )
    assert out["paper_type"] == "Short Communication"
    assert out["abstract_max_words"] == 150
    assert out["max_tables"] is None       # unspecified → null, not invented
    assert "set_at" in out
    stored = requirements.get_paper_requirements(state, slug)
    assert stored["paper_type"] == "Short Communication"
    assert stored["notes"] == "Methods at the end."


def test_set_requires_paper_type(state):
    slug = _setup(state)
    with pytest.raises(ValueError, match="paper_type is required"):
        requirements.set_paper_requirements(state, slug, paper_type="  ")


def test_set_rejects_unknown_required_section(state):
    slug = _setup(state)
    with pytest.raises(ValueError, match="unknown section keys"):
        requirements.set_paper_requirements(
            state, slug, paper_type="Article",
            required_sections=["abstract", "intro"],  # 'intro' is not canonical
        )


def test_set_rejects_non_positive_limit(state):
    slug = _setup(state)
    with pytest.raises(ValueError, match="positive integer"):
        requirements.set_paper_requirements(
            state, slug, paper_type="Article", max_figures=0,
        )


def test_set_missing_paper_raises(state):
    with pytest.raises(NotFound):
        requirements.set_paper_requirements(state, "ghost", paper_type="Article")


# ── check_requirements ───────────────────────────────────────

def test_check_unconfigured(state):
    slug = _setup(state)
    out = requirements.check_requirements(state, slug)
    assert out["configured"] is False
    assert out["requirements"] is None


def test_check_counts_abstract_vs_main_text(state):
    slug = _setup(state)
    sections.update_section(state, slug, "abstract", body="one two three")
    sections.update_section(state, slug, "introduction", body="alpha beta")
    sections.update_section(state, slug, "results", body="x y z w")
    requirements.set_paper_requirements(
        state, slug, paper_type="Article",
        abstract_max_words=2, main_text_max_words=10,
    )
    out = requirements.check_requirements(state, slug)
    assert out["metrics"]["abstract_words"] == 3
    assert out["metrics"]["main_text_words"] == 6  # 2 intro + 4 results
    abstract_check = next(c for c in out["checks"] if c["name"] == "abstract_words")
    assert abstract_check["actual"] == 3 and abstract_check["ok"] is False
    main_check = next(c for c in out["checks"] if c["name"] == "main_text_words")
    assert main_check["ok"] is True


def test_check_figure_table_display_limits(state):
    slug = _setup(state)
    figures.add_figure(state, slug, figure_number=1, title="F1")
    figures.add_figure(state, slug, figure_number=2, title="F2")
    tables.add_table(state, slug, table_number=1, title="T1", content="| a |\n|---|")
    requirements.set_paper_requirements(
        state, slug, paper_type="Letter",
        max_figures=1, max_tables=2, max_display_items=2,
    )
    out = requirements.check_requirements(state, slug)
    assert out["metrics"] == {
        **out["metrics"],
        "figures": 2, "tables": 1, "display_items": 3,
    }
    by_name = {c["name"]: c for c in out["checks"]}
    assert by_name["figures"]["ok"] is False        # 2 > 1
    assert by_name["tables"]["ok"] is True           # 1 <= 2
    assert by_name["display_items"]["ok"] is False   # 3 > 2
    assert by_name["figures"] in out["violations"]


def test_check_reference_limit(state):
    slug = _setup(state)
    references.add_reference(state, slug, citation_key="a", title="A", year=2024)
    references.add_reference(state, slug, citation_key="b", title="B", year=2024)
    requirements.set_paper_requirements(
        state, slug, paper_type="Article", max_references=1,
    )
    out = requirements.check_requirements(state, slug)
    ref_check = next(c for c in out["checks"] if c["name"] == "references")
    assert ref_check["actual"] == 2 and ref_check["ok"] is False


def test_check_required_sections_missing(state):
    slug = _setup(state)
    sections.update_section(state, slug, "abstract", body="filled in")
    requirements.set_paper_requirements(
        state, slug, paper_type="Article",
        required_sections=["abstract", "methods", "results"],
    )
    out = requirements.check_requirements(state, slug)
    sec_check = next(c for c in out["checks"] if c["name"] == "required_sections")
    assert set(sec_check["missing"]) == {"methods", "results"}
    assert sec_check["ok"] is False


def test_check_all_within_limits_is_ok(state):
    slug = _setup(state)
    sections.update_section(state, slug, "abstract", body="short")
    requirements.set_paper_requirements(
        state, slug, paper_type="Article",
        abstract_max_words=10, max_figures=5,
    )
    out = requirements.check_requirements(state, slug)
    assert out["ok"] is True
    assert out["violations"] == []


def test_check_only_emits_checks_for_set_limits(state):
    slug = _setup(state)
    requirements.set_paper_requirements(
        state, slug, paper_type="Article", max_figures=3,
    )
    out = requirements.check_requirements(state, slug)
    # Only max_figures was set → exactly one check, no abstract/ref checks.
    assert [c["name"] for c in out["checks"]] == ["figures"]
