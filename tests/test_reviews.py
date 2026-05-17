"""The bidirectional comment loop: user adds review → Claude addresses it.

User adds comment via the (future) web dashboard, which writes a review row
with source='user'. The SessionStart hook surfaces the count to Claude, who
then runs /paper-revision and resolves each one.
"""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import papers, reviews


def _setup(state):
    papers.create_paper(state, title="My paper")
    return "my-paper"


def test_add_user_review_starts_open(state):
    slug = _setup(state)
    r = reviews.add_review(
        state, slug,
        comment="Methods section needs n= for each experiment.",
        section="methods", severity="major",
    )
    assert r["status"] == "open"
    assert r["source"] == "user"
    assert r["resolved_at"] is None
    assert r["section"] == "methods"
    assert r["severity"] == "major"


def test_add_review_requires_comment(state):
    slug = _setup(state)
    with pytest.raises(ValueError, match="comment is required"):
        reviews.add_review(state, slug, comment="")


def test_add_review_rejects_unknown_source(state):
    slug = _setup(state)
    with pytest.raises(ValueError, match="invalid source"):
        reviews.add_review(state, slug, comment="x", source="random")


def test_list_reviews_filter_by_status_and_source(state):
    slug = _setup(state)
    reviews.add_review(state, slug, comment="user one", source="user")
    reviews.add_review(state, slug, comment="user two", source="user")
    reviews.add_review(state, slug, comment="ai one", source="ai", reviewer_name="AI Methods")

    assert len(reviews.list_reviews(state, slug)) == 3
    assert len(reviews.list_reviews(state, slug, source="user")) == 2
    assert len(reviews.list_reviews(state, slug, source="ai")) == 1
    assert len(reviews.list_reviews(state, slug, status="open")) == 3


def test_resolution_stamps_resolved_at(state):
    slug = _setup(state)
    r = reviews.add_review(state, slug, comment="please clarify line 12.")
    updated = reviews.update_review(
        state, slug, r["id"],
        status="accepted", response="Clarified — added power-analysis details.",
    )
    assert updated["status"] == "accepted"
    assert updated["resolved_at"] is not None
    assert updated["response"].startswith("Clarified")


def test_session_start_banner_count(state):
    """count_open_user_comments is what the SessionStart hook will surface."""
    slug = _setup(state)
    assert reviews.count_open_user_comments(state, slug) == 0

    reviews.add_review(state, slug, comment="A", source="user")
    reviews.add_review(state, slug, comment="B", source="user")
    reviews.add_review(state, slug, comment="C", source="ai")  # AI doesn't count
    assert reviews.count_open_user_comments(state, slug) == 2

    # Resolving one drops the count
    bs = reviews.list_reviews(state, slug, source="user", status="open")
    reviews.update_review(state, slug, bs[0]["id"], status="accepted", response="fixed")
    assert reviews.count_open_user_comments(state, slug) == 1


def test_status_must_be_valid(state):
    slug = _setup(state)
    r = reviews.add_review(state, slug, comment="x")
    with pytest.raises(ValueError, match="invalid status"):
        reviews.update_review(state, slug, r["id"], status="wat")


def test_update_review_returns_existing_when_no_fields(state):
    slug = _setup(state)
    r = reviews.add_review(state, slug, comment="x")
    same = reviews.update_review(state, slug, r["id"])
    assert same["comment"] == "x"


def test_review_missing_raises(state):
    slug = _setup(state)
    with pytest.raises(NotFound):
        reviews.update_review(state, slug, "noexist", status="accepted")


def test_review_isolation_between_users(state, other_state):
    slug = _setup(state)
    reviews.add_review(state, slug, comment="alice comment")
    # bob can't even see alice's paper, much less her comments
    with pytest.raises(NotFound):
        reviews.list_reviews(other_state, slug)
