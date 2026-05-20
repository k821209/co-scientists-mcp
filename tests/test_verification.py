"""Verification findings: list filters, acknowledge verdict, clear,
doi-safe id, missing-paper guards."""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import papers, verification


def _setup(state):
    papers.create_paper(state, title="My paper")
    return "my-paper"


def _write_finding(state, slug, doi, kind, **extra):
    """Directly seed a finding doc (mimics what validate_references /
    the dashboard's Sync DOIs button persist)."""
    doc_id = verification._doi_safe_id(doi)
    payload = {
        "doi": doi.lower(),
        "kind": kind,
        "source": "registered_ref",
        "detected_at": "2026-05-20T00:00:00Z",
        "acknowledged": False,
        **extra,
    }
    state.backend.set_doc(
        verification._finding_doc_path(state, slug, doc_id), payload,
    )


def test_doi_safe_id_sanitizes():
    assert verification._doi_safe_id("10.1038/s41586-022-04618-z") == "10_1038_s41586_022_04618_z"
    assert verification._doi_safe_id("") == "_"
    # Same DOI always maps to the same id (overwrite, not append)
    a = verification._doi_safe_id("10.1/X")
    b = verification._doi_safe_id("10.1/x")
    assert a == b


def test_list_defaults_filter_resolved_and_acknowledged(state):
    slug = _setup(state)
    _write_finding(state, slug, "10.1/a", "unresolved")
    _write_finding(state, slug, "10.1/b", "resolved")
    _write_finding(state, slug, "10.1/c", "context_mismatch", acknowledged=True)
    # default: only_unacknowledged + only_problems
    out = verification.list_verification_findings(state, slug)
    dois = {f["doi"] for f in out}
    assert dois == {"10.1/a"}     # b is resolved, c is acknowledged


def test_list_full_audit_log(state):
    slug = _setup(state)
    _write_finding(state, slug, "10.1/a", "unresolved")
    _write_finding(state, slug, "10.1/b", "resolved")
    _write_finding(state, slug, "10.1/c", "context_mismatch", acknowledged=True)
    out = verification.list_verification_findings(
        state, slug, only_unacknowledged=False, only_problems=False,
    )
    assert len(out) == 3


def test_list_only_problems_keeps_acknowledged_when_asked(state):
    slug = _setup(state)
    _write_finding(state, slug, "10.1/c", "context_mismatch", acknowledged=True)
    out = verification.list_verification_findings(
        state, slug, only_unacknowledged=False, only_problems=True,
    )
    assert len(out) == 1   # acknowledged but still a problem


def test_acknowledge_with_approved_verdict(state):
    slug = _setup(state)
    _write_finding(state, slug, "10.1/x", "context_mismatch")
    doc = verification.acknowledge_finding(
        state, slug, "10.1/x", verdict="approved", note="checked abstract",
    )
    assert doc["acknowledged"] is True
    assert doc["context_verified"] is True
    assert doc["agent_verdict"] == "approved"
    assert doc["acknowledged_note"] == "checked abstract"


def test_acknowledge_with_rejected_verdict(state):
    slug = _setup(state)
    _write_finding(state, slug, "10.1/y", "context_mismatch")
    doc = verification.acknowledge_finding(state, slug, "10.1/y", verdict="rejected")
    assert doc["context_verified"] is False
    assert doc["agent_verdict"] == "rejected"


def test_acknowledge_no_verdict_just_marks(state):
    slug = _setup(state)
    _write_finding(state, slug, "10.1/z", "unresolved")
    doc = verification.acknowledge_finding(state, slug, "10.1/z", note="removed it")
    assert doc["acknowledged"] is True
    assert "context_verified" not in doc   # no verdict → axis untouched


def test_acknowledge_invalid_verdict_raises(state):
    slug = _setup(state)
    _write_finding(state, slug, "10.1/q", "unresolved")
    with pytest.raises(ValueError):
        verification.acknowledge_finding(state, slug, "10.1/q", verdict="maybe")


def test_acknowledge_missing_finding_raises(state):
    slug = _setup(state)
    with pytest.raises(NotFound):
        verification.acknowledge_finding(state, slug, "10.1/ghost")


def test_clear_findings_wipes_all(state):
    slug = _setup(state)
    _write_finding(state, slug, "10.1/a", "unresolved")
    _write_finding(state, slug, "10.1/b", "resolved")
    n = verification.clear_findings(state, slug)
    assert n == 2
    assert verification.list_verification_findings(
        state, slug, only_unacknowledged=False, only_problems=False,
    ) == []


def test_clear_findings_empty_returns_zero(state):
    slug = _setup(state)
    assert verification.clear_findings(state, slug) == 0


def test_list_missing_paper_raises(state):
    with pytest.raises(NotFound):
        verification.list_verification_findings(state, "ghost-paper")
