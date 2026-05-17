"""Figures: doc + blob round-trip, supplementary offset, isolation."""
from __future__ import annotations

import pathlib

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import figures, papers


def _setup(state):
    papers.create_paper(state, title="My paper")
    return "my-paper"


def _fake_png(tmp_path: pathlib.Path, name: str = "fig.png", payload: bytes = b"\x89PNG\r\n...") -> str:
    p = tmp_path / name
    p.write_bytes(payload)
    return str(p)


def test_add_figure_without_local_path(state):
    slug = _setup(state)
    f = figures.add_figure(state, slug, figure_number=1, title="Overview", caption="The pipeline")
    assert f["figure_number"] == 1
    assert f["title"] == "Overview"
    assert f["blob_path"] is None  # no upload happened
    assert f["status"] == "pending"


def test_add_figure_with_local_path_uploads_blob(state, backend, tmp_path):
    slug = _setup(state)
    local = _fake_png(tmp_path, "schematic.png", b"PNG_BYTES_HERE")
    f = figures.add_figure(state, slug, figure_number=2, title="Schematic", local_path=local)
    assert f["blob_path"] == f"projects/p-alice/papers/{slug}/figures/figure_2.png"
    blob = backend.get_blob(f["blob_path"])
    assert blob == b"PNG_BYTES_HERE"


def test_add_figure_missing_file_raises(state, tmp_path):
    slug = _setup(state)
    with pytest.raises(FileNotFoundError):
        figures.add_figure(state, slug, figure_number=1, title="X",
                           local_path=str(tmp_path / "nonexistent.png"))


def test_add_figure_duplicate_number_rejected(state):
    slug = _setup(state)
    figures.add_figure(state, slug, figure_number=1, title="A")
    with pytest.raises(ValueError, match="already exists"):
        figures.add_figure(state, slug, figure_number=1, title="B")


def test_update_figure_replaces_blob_when_extension_changes(state, backend, tmp_path):
    slug = _setup(state)
    png = _fake_png(tmp_path, "f.png", b"old-png")
    figures.add_figure(state, slug, figure_number=1, title="A", local_path=png)
    old_blob = f"projects/p-alice/papers/{slug}/figures/figure_1.png"
    assert backend.get_blob(old_blob) == b"old-png"

    jpg = tmp_path / "f.jpg"
    jpg.write_bytes(b"new-jpg")
    updated = figures.update_figure(state, slug, 1, local_path=str(jpg))
    new_blob = f"projects/p-alice/papers/{slug}/figures/figure_1.jpg"
    assert updated["blob_path"] == new_blob
    assert backend.get_blob(new_blob) == b"new-jpg"
    # Old blob cleaned up
    assert backend.get_blob(old_blob) is None


def test_list_figures_main_vs_supplementary(state):
    slug = _setup(state)
    figures.add_figure(state, slug, figure_number=1, title="Fig 1")
    figures.add_figure(state, slug, figure_number=2, title="Fig 2")
    # SFigure 1 → number 101 (offset)
    figures.add_figure(state, slug, figure_number=101, title="SFig 1")

    main = figures.list_figures(state, slug)
    assert [f["figure_number"] for f in main] == [1, 2]
    supp = figures.list_figures(state, slug, supplementary=True)
    assert [f["figure_number"] for f in supp] == [101]


def test_delete_figure_removes_blob(state, backend, tmp_path):
    slug = _setup(state)
    png = _fake_png(tmp_path)
    figures.add_figure(state, slug, figure_number=1, title="X", local_path=png)
    blob_path = f"projects/p-alice/papers/{slug}/figures/figure_1.png"
    assert backend.get_blob(blob_path) is not None
    assert figures.delete_figure(state, slug, 1) is True
    assert backend.get_blob(blob_path) is None


def test_figure_isolation_between_users(state, other_state):
    slug = _setup(state)
    figures.add_figure(state, slug, figure_number=1, title="alice's fig")
    with pytest.raises(NotFound):
        figures.get_figure(other_state, slug, 1)


def test_get_missing_figure_raises(state):
    slug = _setup(state)
    with pytest.raises(NotFound):
        figures.get_figure(state, slug, 99)
