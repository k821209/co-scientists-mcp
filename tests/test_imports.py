"""Document import: format dispatch, pandoc/pdf paths, error handling.

pandoc + pypdf calls are stubbed so the suite runs without those
binaries/packages or network.
"""
from __future__ import annotations

import pathlib

import pytest

from co_scientist_local.tools import imports


def test_unsupported_format_raises(tmp_path):
    f = tmp_path / "manuscript.pages"
    f.write_text("x")
    with pytest.raises(ValueError, match="unsupported import format"):
        imports.import_document(None, local_path=str(f))


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        imports.import_document(None, local_path="/no/such/file.docx")


def test_docx_routes_through_pandoc(tmp_path, monkeypatch):
    f = tmp_path / "paper.docx"
    f.write_bytes(b"fake docx")
    captured = {}

    def fake_pandoc(src, fmt, media_to):
        captured["fmt"] = fmt
        return ("# Title\n\nbody text", ["/tmp/img1.png"])

    monkeypatch.setattr(imports, "_pandoc_to_markdown", fake_pandoc)
    out = imports.import_document(None, local_path=str(f))
    assert out["source_format"] == "docx"
    assert captured["fmt"] == "docx"
    assert out["markdown"].startswith("# Title")
    assert out["media"] == ["/tmp/img1.png"]
    assert out["char_count"] == len(out["markdown"])


def test_docx_no_media_warns(tmp_path, monkeypatch):
    f = tmp_path / "paper.docx"
    f.write_bytes(b"x")
    monkeypatch.setattr(
        imports, "_pandoc_to_markdown", lambda *a: ("text", []),
    )
    out = imports.import_document(None, local_path=str(f))
    assert any("No embedded images" in w for w in out["warnings"])


def test_pdf_routes_through_pypdf(tmp_path, monkeypatch):
    f = tmp_path / "paper.pdf"
    f.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(
        imports, "_pdf_to_text", lambda src: "page one\n\npage two",
    )
    out = imports.import_document(None, local_path=str(f))
    assert out["source_format"] == "pdf"
    assert out["markdown"] == "page one\n\npage two"
    assert out["media"] == []
    # PDF import always carries the lossy warning
    assert any("lossy" in w.lower() for w in out["warnings"])


def test_markdown_passthrough(tmp_path, monkeypatch):
    f = tmp_path / "draft.md"
    f.write_text("# already markdown")
    monkeypatch.setattr(
        imports, "_pandoc_to_markdown", lambda *a: ("# already markdown", []),
    )
    out = imports.import_document(None, local_path=str(f))
    assert out["source_format"] == "markdown"


def test_pandoc_missing_binary_message(tmp_path, monkeypatch):
    """A clear error when pandoc isn't installed."""
    f = tmp_path / "paper.docx"
    f.write_bytes(b"x")

    def boom(*a, **k):
        raise FileNotFoundError("pandoc")

    monkeypatch.setattr(imports.subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="pandoc not found"):
        imports.import_document(None, local_path=str(f))
