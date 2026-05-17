"""Analyses (records only): name auto-slugifies; status filter; uniqueness."""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import analyses, papers


def _setup(state):
    papers.create_paper(state, title="My paper")
    return "my-paper"


def test_create_analysis_slugifies_name(state):
    slug = _setup(state)
    a = analyses.create_analysis(state, slug, name="PCA Analysis", description="dimensionality")
    assert a["name"] == "pca-analysis"
    assert a["status"] == "active"


def test_get_analysis_by_normalized_name(state):
    slug = _setup(state)
    analyses.create_analysis(state, slug, name="DEG Analysis")
    a = analyses.get_analysis(state, slug, "deg-analysis")
    assert a["name"] == "deg-analysis"


def test_list_analyses_filter_by_status(state):
    slug = _setup(state)
    analyses.create_analysis(state, slug, name="a")
    analyses.create_analysis(state, slug, name="b")
    analyses.update_analysis(state, slug, "b", status="archived")
    active = analyses.list_analyses(state, slug, status="active")
    archived = analyses.list_analyses(state, slug, status="archived")
    assert [x["name"] for x in active] == ["a"]
    assert [x["name"] for x in archived] == ["b"]


def test_create_analysis_requires_name(state):
    slug = _setup(state)
    with pytest.raises(ValueError, match="name is required"):
        analyses.create_analysis(state, slug, name="")


def test_create_analysis_rejects_duplicate(state):
    slug = _setup(state)
    analyses.create_analysis(state, slug, name="pca")
    with pytest.raises(ValueError, match="already exists"):
        analyses.create_analysis(state, slug, name="PCA")  # slugifies to same key


def test_update_analysis_patches(state):
    slug = _setup(state)
    analyses.create_analysis(state, slug, name="pca", description="initial")
    a = analyses.update_analysis(state, slug, "pca", description="updated", status="complete")
    assert a["description"] == "updated"
    assert a["status"] == "complete"


def test_delete_analysis(state):
    slug = _setup(state)
    analyses.create_analysis(state, slug, name="pca")
    assert analyses.delete_analysis(state, slug, "pca") is True
    assert analyses.delete_analysis(state, slug, "pca") is False  # idempotent


def test_analyses_isolation_between_users(state, other_state):
    slug = _setup(state)
    analyses.create_analysis(state, slug, name="alice-only")
    with pytest.raises(NotFound):
        analyses.list_analyses(other_state, slug)
