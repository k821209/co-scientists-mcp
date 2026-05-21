"""Journal → CSL resolution + the per-project registry.

`download_csl` (network) is stubbed; the registry uses the in-memory backend.
"""
from __future__ import annotations

import urllib.error

import pytest

from co_scientist_local.tools import csl


# ── normalization + slug ─────────────────────────────────────

def test_normalize_strips_the_and_punctuation():
    assert csl._normalize_journal("The Plant Cell") == "plant cell"
    assert csl._normalize_journal("PLOS  One!") == "plos one"
    assert csl._normalize_journal("") == ""


# ── resolve_csl_filename (offline) ───────────────────────────

def test_resolve_no_journal(state):
    out = csl.resolve_csl_filename(state, None)
    assert out["csl_status"] == "no_journal"
    assert out["csl_filename"] is None


def test_resolve_from_map(state):
    out = csl.resolve_csl_filename(state, "Nature")
    assert out == {"csl_filename": "nature.csl", "csl_slug": "nature",
                   "csl_source": "map", "csl_status": "resolved"}


def test_resolve_guess(state):
    out = csl.resolve_csl_filename(state, "Journal of Obscure Things")
    assert out["csl_filename"] == "journal-of-obscure-things.csl"
    assert out["csl_source"] == "guess"


def test_resolve_registry_wins_over_map(state):
    csl.register_journal_csl(state, "Nature", "nature-override.csl")
    out = csl.resolve_csl_filename(state, "Nature")
    assert out["csl_filename"] == "nature-override.csl"
    assert out["csl_source"] == "registry"


# ── registry CRUD ────────────────────────────────────────────

def test_register_and_lookup(state):
    csl.register_journal_csl(state, "J. Exp. Bot.",
                             "journal-of-experimental-botany.csl")
    assert csl.lookup_journal_csl(state, "J. Exp. Bot.") == \
        "journal-of-experimental-botany.csl"
    # normalization makes lookup tolerant of formatting differences
    assert csl.lookup_journal_csl(state, "j exp bot") == \
        "journal-of-experimental-botany.csl"


def test_register_rejects_non_csl_filename(state):
    with pytest.raises(ValueError, match="must end with .csl"):
        csl.register_journal_csl(state, "Nature", "nature.xml")


def test_register_rejects_empty_journal(state):
    with pytest.raises(ValueError, match="empty after normalization"):
        csl.register_journal_csl(state, "!!!", "x.csl")


def test_register_is_idempotent_and_keeps_created_at(state):
    first = csl.register_journal_csl(state, "Nature", "a.csl")
    second = csl.register_journal_csl(state, "Nature", "b.csl")
    assert second["csl_filename"] == "b.csl"
    assert second["created_at"] == first["created_at"]


def test_list_journal_csls_sorted(state):
    csl.register_journal_csl(state, "Nature", "nature.csl")
    csl.register_journal_csl(state, "Cell", "cell.csl")
    listed = csl.list_journal_csls(state)
    assert [r["name"] for r in listed] == ["cell", "nature"]


def test_delete_journal_csl(state):
    csl.register_journal_csl(state, "Nature", "nature.csl")
    assert csl.delete_journal_csl(state, "Nature") is True
    assert csl.delete_journal_csl(state, "Nature") is False
    assert csl.lookup_journal_csl(state, "Nature") is None


def test_registry_is_per_project(state, other_state):
    csl.register_journal_csl(state, "Nature", "nature.csl")
    assert csl.lookup_journal_csl(other_state, "Nature") is None


# ── download_csl ─────────────────────────────────────────────

class _Resp:
    def __init__(self, data):
        self._d = data

    def read(self):
        return self._d

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_download_csl_returns_bytes(monkeypatch):
    monkeypatch.setattr(
        csl.urllib.request, "urlopen",
        lambda url, timeout=0: _Resp(b'<?xml version="1.0"?><style>x</style>'),
    )
    data = csl.download_csl("nature.csl")
    assert b"<style>" in data


def test_download_csl_404_raises_cslnotfound(monkeypatch):
    def _boom(url, timeout=0):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(csl.urllib.request, "urlopen", _boom)
    with pytest.raises(csl.CslNotFound):
        csl.download_csl("frobnicate.csl")


def test_download_csl_rejects_non_csl_content(monkeypatch):
    monkeypatch.setattr(
        csl.urllib.request, "urlopen",
        lambda url, timeout=0: _Resp(b"<html>not a style</html>"),
    )
    with pytest.raises(csl.CslNotFound):
        csl.download_csl("nature.csl")
