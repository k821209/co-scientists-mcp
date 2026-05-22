"""Decks + slides: CRUD, idempotent create, slide validation, renumber."""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import decks, papers


def _setup(state):
    papers.create_paper(state, title="My paper")
    return "my-paper"


def test_create_deck_seeds_defaults(state):
    slug = _setup(state)
    d = decks.create_deck(state, slug, title="Lab seminar")
    assert d["id"] == "lab-seminar"
    assert d["status"] == "draft"
    assert d["slide_count"] == 0
    assert d["concept"] is None
    assert d["aspect_ratio"] == "16:9"   # default


def test_create_deck_with_aspect_ratio(state):
    slug = _setup(state)
    d = decks.create_deck(state, slug, title="Poster", aspect_ratio="4:3")
    assert d["aspect_ratio"] == "4:3"


def test_create_deck_rejects_bad_aspect_ratio(state):
    slug = _setup(state)
    with pytest.raises(ValueError, match="aspect_ratio"):
        decks.create_deck(state, slug, title="d", aspect_ratio="21:9")


def test_update_deck_aspect_ratio(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    upd = decks.update_deck(state, slug, "d", aspect_ratio="16:10")
    assert upd["aspect_ratio"] == "16:10"
    with pytest.raises(ValueError, match="aspect_ratio"):
        decks.update_deck(state, slug, "d", aspect_ratio="bogus")


def test_slide_accepts_text_render_mode(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    s = decks.add_slide(state, slug, "d", slide_number=1, role="outline",
                        title="Agenda", body="- one\n- two",
                        render_mode="text")
    assert s["render_mode"] == "text"


def test_create_deck_idempotent(state):
    slug = _setup(state)
    a = decks.create_deck(state, slug, title="Seminar", deck_id="d1")
    b = decks.create_deck(state, slug, title="Different title", deck_id="d1")
    assert a == b   # second call returns existing doc unchanged


def test_create_deck_requires_title(state):
    slug = _setup(state)
    with pytest.raises(ValueError):
        decks.create_deck(state, slug, title="")


def test_add_slide_then_list(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    decks.add_slide(state, slug, "d", slide_number=1, role="title", title="Cover")
    decks.add_slide(state, slug, "d", slide_number=2, role="result", title="Fig 1", notes="key result")
    listed = decks.list_slides(state, slug, "d")
    assert [s["slide_number"] for s in listed] == [1, 2]
    deck = decks.get_deck(state, slug, "d")
    assert deck["slide_count"] == 2


def test_add_slide_validates_role(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    with pytest.raises(ValueError):
        decks.add_slide(state, slug, "d", slide_number=1,
                        role="invalid", title="x")


def test_add_slide_rejects_zero_slide_number(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    with pytest.raises(ValueError):
        decks.add_slide(state, slug, "d", slide_number=0,
                        role="title", title="x")


def test_update_slide_patches_fields(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    s = decks.add_slide(state, slug, "d", slide_number=1, role="result", title="X")
    upd = decks.update_slide(state, slug, "d", s["id"], notes="speaker notes")
    assert upd["notes"] == "speaker notes"
    assert upd["title"] == "X"   # untouched


def test_update_slide_rejects_invalid_render_mode(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    s = decks.add_slide(state, slug, "d", slide_number=1, role="result", title="X")
    with pytest.raises(ValueError):
        decks.update_slide(state, slug, "d", s["id"], render_mode="hologram")


def test_delete_slide_decrements_count(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    a = decks.add_slide(state, slug, "d", slide_number=1, role="title", title="A")
    decks.add_slide(state, slug, "d", slide_number=2, role="result", title="B")
    assert decks.get_deck(state, slug, "d")["slide_count"] == 2
    assert decks.delete_slide(state, slug, "d", a["id"]) is True
    assert decks.get_deck(state, slug, "d")["slide_count"] == 1


def test_renumber_packs_after_delete(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    decks.add_slide(state, slug, "d", slide_number=1, role="title", title="A")
    b = decks.add_slide(state, slug, "d", slide_number=2, role="result", title="B")
    decks.add_slide(state, slug, "d", slide_number=5, role="conclusion", title="C")
    decks.delete_slide(state, slug, "d", b["id"])
    result = decks.renumber_deck(state, slug, "d")
    assert result["count"] == 2
    nums = [s["slide_number"] for s in decks.list_slides(state, slug, "d")]
    assert nums == [1, 2]


def test_delete_deck_cascades_slides(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    decks.add_slide(state, slug, "d", slide_number=1, role="title", title="A")
    decks.add_slide(state, slug, "d", slide_number=2, role="result", title="B")
    assert decks.delete_deck(state, slug, "d") is True
    with pytest.raises(NotFound):
        decks.get_deck(state, slug, "d")
    # slides also gone
    assert decks.list_slides(state, slug, "d") == []


def test_update_deck_concept(state):
    slug = _setup(state)
    decks.create_deck(state, slug, title="d", deck_id="d")
    upd = decks.update_deck(state, slug, "d",
                            concept="palette: navy/gold; typography: serif")
    assert "palette" in upd["concept"]


def test_get_missing_deck_raises(state):
    slug = _setup(state)
    with pytest.raises(NotFound):
        decks.get_deck(state, slug, "ghost")


def test_deck_isolation_per_paper(state):
    papers.create_paper(state, title="P1", slug="p1")
    papers.create_paper(state, title="P2", slug="p2")
    decks.create_deck(state, "p1", title="d", deck_id="d")
    assert decks.list_decks(state, "p1") != []
    assert decks.list_decks(state, "p2") == []
