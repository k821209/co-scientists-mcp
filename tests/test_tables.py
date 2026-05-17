"""Tables: pure-doc CRUD; supplementary offset; isolation."""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import papers, tables


def _setup(state):
    papers.create_paper(state, title="My paper")
    return "my-paper"


_MD_TABLE = "| Gene | log2FC | qvalue |\n|---|---|---|\n| A | 2.1 | 0.001 |\n"


def test_add_and_get_table(state):
    slug = _setup(state)
    t = tables.add_table(state, slug, table_number=1, title="DEGs", content=_MD_TABLE,
                        caption="Top hits")
    assert t["title"] == "DEGs"
    assert t["content"] == _MD_TABLE
    fetched = tables.get_table(state, slug, 1)
    assert fetched == t


def test_update_table_patches_only_provided(state):
    slug = _setup(state)
    tables.add_table(state, slug, table_number=1, title="DEGs", content=_MD_TABLE, caption="A")
    updated = tables.update_table(state, slug, 1, caption="B")
    assert updated["caption"] == "B"
    assert updated["content"] == _MD_TABLE  # unchanged


def test_supplementary_offset(state):
    slug = _setup(state)
    tables.add_table(state, slug, table_number=1, title="Main", content=_MD_TABLE)
    tables.add_table(state, slug, table_number=101, title="Supp", content=_MD_TABLE)
    assert [t["table_number"] for t in tables.list_tables(state, slug)] == [1]
    assert [t["table_number"] for t in tables.list_tables(state, slug, supplementary=True)] == [101]


def test_duplicate_table_rejected(state):
    slug = _setup(state)
    tables.add_table(state, slug, table_number=1, title="A", content=_MD_TABLE)
    with pytest.raises(ValueError, match="already exists"):
        tables.add_table(state, slug, table_number=1, title="B", content=_MD_TABLE)


def test_delete_table(state):
    slug = _setup(state)
    tables.add_table(state, slug, table_number=1, title="X", content=_MD_TABLE)
    assert tables.delete_table(state, slug, 1) is True
    assert tables.delete_table(state, slug, 1) is False  # idempotent


def test_get_missing_table_raises(state):
    slug = _setup(state)
    with pytest.raises(NotFound):
        tables.get_table(state, slug, 99)


def test_table_isolation_between_users(state, other_state):
    slug = _setup(state)
    tables.add_table(state, slug, table_number=1, title="X", content=_MD_TABLE)
    with pytest.raises(NotFound):
        tables.get_table(other_state, slug, 1)
