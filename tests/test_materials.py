"""Reference materials: upload, list, download-to-disk, delete, isolation."""
from __future__ import annotations

import pathlib

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import materials, papers


def _setup(state):
    papers.create_paper(state, title="My paper")
    return "my-paper"


def _file(tmp_path: pathlib.Path, name: str, payload: bytes) -> str:
    p = tmp_path / name
    p.write_bytes(payload)
    return str(p)


def test_add_material_uploads_blob_and_doc(state, backend, tmp_path):
    slug = _setup(state)
    local = _file(tmp_path, "data.csv", b"a,b\n1,2\n")
    m = materials.add_material(state, slug, local_path=local, description="raw data")
    assert m["filename"] == "data.csv"
    assert m["content_type"] == "text/csv"
    assert m["size_bytes"] == 8
    assert m["description"] == "raw data"
    assert backend.get_blob(m["blob_path"]) == b"a,b\n1,2\n"


def test_add_material_missing_file_raises(state, tmp_path):
    slug = _setup(state)
    with pytest.raises(FileNotFoundError):
        materials.add_material(state, slug, local_path=str(tmp_path / "nope.pdf"))


def test_add_material_sanitizes_filename(state, tmp_path):
    slug = _setup(state)
    local = _file(tmp_path, "weird name (1).pdf", b"%PDF-1.4")
    m = materials.add_material(state, slug, local_path=local)
    assert m["filename"] == "weird_name_1_.pdf"
    assert m["content_type"] == "application/pdf"


def test_list_materials_newest_first(state):
    slug = _setup(state)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        a = _file(pathlib.Path(d), "a.txt", b"a")
        b = _file(pathlib.Path(d), "b.txt", b"b")
        m1 = materials.add_material(state, slug, local_path=a)
        m2 = materials.add_material(state, slug, local_path=b)
    # Force distinct ordering via created_at
    backend = state.backend
    backend.update_doc(
        f"projects/p-alice/papers/{slug}/materials/{m1['material_id']}",
        {"created_at": "2026-01-01T00:00:00.000000Z"},
    )
    backend.update_doc(
        f"projects/p-alice/papers/{slug}/materials/{m2['material_id']}",
        {"created_at": "2026-02-01T00:00:00.000000Z"},
    )
    out = materials.list_materials(state, slug)
    assert [m["filename"] for m in out] == ["b.txt", "a.txt"]


def test_get_material_writes_to_disk(state, tmp_path):
    slug = _setup(state)
    src = _file(tmp_path, "notes.md", b"# hello")
    m = materials.add_material(state, slug, local_path=src)
    dest = tmp_path / "out"
    res = materials.get_material(state, slug, m["material_id"], dest_dir=str(dest))
    written = pathlib.Path(res["path"])
    assert written.read_bytes() == b"# hello"
    assert written.name == "notes.md"
    assert res["size_bytes"] == 7


def test_get_material_respects_dest_path(state, tmp_path):
    slug = _setup(state)
    src = _file(tmp_path, "x.bin", b"\x00\x01\x02")
    m = materials.add_material(state, slug, local_path=src)
    target = tmp_path / "sub" / "renamed.bin"
    res = materials.get_material(state, slug, m["material_id"], dest_path=str(target))
    assert pathlib.Path(res["path"]) == target.resolve()
    assert target.read_bytes() == b"\x00\x01\x02"


def test_get_missing_material_raises(state):
    slug = _setup(state)
    with pytest.raises(NotFound):
        materials.get_material(state, slug, "deadbeef")


def test_delete_material_removes_blob(state, backend, tmp_path):
    slug = _setup(state)
    src = _file(tmp_path, "f.json", b"{}")
    m = materials.add_material(state, slug, local_path=src)
    assert backend.get_blob(m["blob_path"]) is not None
    assert materials.delete_material(state, slug, m["material_id"]) is True
    assert backend.get_blob(m["blob_path"]) is None
    assert materials.delete_material(state, slug, m["material_id"]) is False


def test_material_isolation_between_projects(state, other_state, tmp_path):
    slug = _setup(state)
    src = _file(tmp_path, "secret.txt", b"alice")
    m = materials.add_material(state, slug, local_path=src)
    # other_state's paper doesn't even exist → NotFound on the paper guard
    with pytest.raises(NotFound):
        materials.get_material(other_state, slug, m["material_id"])
