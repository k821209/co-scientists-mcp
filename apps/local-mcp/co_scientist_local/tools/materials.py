"""Reference materials: user-uploaded source files attached to a paper.

These are the files a user drops into the dashboard for the agent to consult
while writing — PDFs to read, datasets to analyze, prior drafts, notes, images.
Distinct from `references` (the bibliography of cited works): a material is a
*file*, a reference is a *citation*.

Paths:
    doc:  projects/{pid}/papers/{slug}/materials/{material_id}
    blob: projects/{pid}/papers/{slug}/materials/{material_id}__{filename}

The doc carries metadata (filename, content_type, size_bytes, description) and
a `blob_path`; the bytes live in Storage. `get_material` streams the bytes back
to the local disk so Claude Code can open the file directly.
"""
from __future__ import annotations

import pathlib
import re

from ..backends.base import NotFound
from ..state import State
from ..util import new_id, now_iso
from .papers import _paper_path

# Filenames are user-supplied; keep only a safe basename for the blob key.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str) -> str:
    base = pathlib.PurePosixPath(name).name or "file"
    cleaned = _UNSAFE.sub("_", base).strip("._") or "file"
    return cleaned[:120]


def _materials_collection(state: State, slug: str) -> str:
    return state.project_path("papers", slug, "materials")


def _material_path(state: State, slug: str, material_id: str) -> str:
    return state.project_path("papers", slug, "materials", material_id)


def _ensure_paper(state: State, slug: str) -> None:
    if state.backend.get_doc(_paper_path(state, slug)) is None:
        raise NotFound(f"paper not found: {slug!r} in project {state.project_id!r}")


def add_material(
    state: State,
    slug: str,
    *,
    local_path: str,
    description: str | None = None,
) -> dict:
    """Upload a local file as a reference material for `slug`."""
    _ensure_paper(state, slug)
    p = pathlib.Path(local_path)
    if not p.is_file():
        raise FileNotFoundError(f"material file not found: {local_path}")

    data = p.read_bytes()
    material_id = new_id()
    filename = _safe_filename(p.name)
    blob_path = _material_path(state, slug, f"{material_id}__{filename}")
    state.backend.put_blob(blob_path, data)

    now = now_iso()
    doc = {
        "material_id": material_id,
        "filename": filename,
        "content_type": _guess_content_type(filename),
        "size_bytes": len(data),
        "blob_path": blob_path,
        "description": description,
        "uploaded_by": "agent",
        "created_at": now,
        "updated_at": now,
    }
    state.backend.set_doc(_material_path(state, slug, material_id), doc)
    return doc


def list_materials(state: State, slug: str) -> list[dict]:
    """List reference materials attached to a paper, newest first."""
    _ensure_paper(state, slug)
    pairs = state.backend.list_collection(_materials_collection(state, slug))
    mats = [data for _, data in pairs]
    mats.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return mats


def get_material(
    state: State,
    slug: str,
    material_id: str,
    *,
    dest_dir: str = ".",
    dest_path: str | None = None,
) -> dict:
    """Download a material's bytes to local disk.

    Writes to `dest_path` if given, else `dest_dir`/<original-filename>.
    Returns {path, filename, size_bytes, content_type}.
    """
    _ensure_paper(state, slug)
    doc = state.backend.get_doc(_material_path(state, slug, material_id))
    if doc is None:
        raise NotFound(f"material {material_id!r} not found for {slug!r}")
    blob_path = doc.get("blob_path")
    if not blob_path:
        raise NotFound(f"material {material_id!r} has no stored file")
    data = state.backend.get_blob(blob_path)
    if data is None:
        raise NotFound(f"material {material_id!r} blob missing at {blob_path}")

    if dest_path:
        out = pathlib.Path(dest_path).expanduser()
    else:
        out = pathlib.Path(dest_dir).expanduser() / doc.get("filename", material_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return {
        "path": str(out.resolve()),
        "filename": doc.get("filename"),
        "size_bytes": len(data),
        "content_type": doc.get("content_type"),
    }


def delete_material(state: State, slug: str, material_id: str) -> bool:
    """Delete a material's doc + blob. Returns True if it existed."""
    _ensure_paper(state, slug)
    path = _material_path(state, slug, material_id)
    doc = state.backend.get_doc(path)
    if doc is None:
        return False
    if doc.get("blob_path"):
        state.backend.delete_blob(doc["blob_path"])
    state.backend.delete_doc(path)
    return True


_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "json": "application/json",
    "xml": "application/xml",
    "html": "text/html",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "svg": "image/svg+xml",
    "zip": "application/zip",
}


def _guess_content_type(filename: str) -> str:
    ext = pathlib.PurePosixPath(filename).suffix.lstrip(".").lower()
    return _CONTENT_TYPES.get(ext, "application/octet-stream")
