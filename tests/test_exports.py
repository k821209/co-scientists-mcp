"""prepare_export + export_to_path + list_exports.

We never run real pandoc — the FakePandocExecutor records every invocation
and snapshots the temp directory at call time so we can verify that
manuscript.md, references.bib, and figure blobs were laid out correctly.
"""
from __future__ import annotations

import pathlib

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import (
    exports,
    figures,
    papers,
    references,
    sections,
)


def _setup(state):
    papers.create_paper(state, title="Rice TE evolution", journal="Nature")
    return "rice-te-evolution"


# ──────────────────────────────────────────────────────────────────────────────
# prepare_export
# ──────────────────────────────────────────────────────────────────────────────


def test_prepare_export_returns_full_bundle(state):
    slug = _setup(state)
    sections.update_section(state, slug, "introduction", body="The introduction.")
    references.add_reference(state, slug, citation_key="smith2024",
                             title="Plant evo", authors=["Smith"], year=2024,
                             doi="10.1/abc")
    figures.add_figure(state, slug, figure_number=1, title="Overview",
                       caption="Pipeline")

    b = exports.prepare_export(state, slug)
    assert b["slug"] == slug
    assert b["paper"]["title"] == "Rice TE evolution"
    assert "## Introduction" in b["manuscript"]
    assert "The introduction." in b["manuscript"]
    assert len(b["references"]) == 1
    assert len(b["figures"]) == 1
    assert "@article{smith2024" in b["bibtex"]
    assert "doi = {10.1/abc}" in b["bibtex"]


def test_prepare_export_uses_literal_bibtex_when_provided(state):
    slug = _setup(state)
    raw = "@misc{custom2024,\n  title = {Raw entry}\n}"
    references.add_reference(state, slug, citation_key="custom2024",
                             title="Raw", bibtex=raw)
    b = exports.prepare_export(state, slug)
    assert "Raw entry" in b["bibtex"]
    assert "@misc{custom2024" in b["bibtex"]


def test_prepare_export_detects_placeholders(state):
    slug = _setup(state)
    sections.update_section(state, slug, "methods",
                            body="We did TODO this and TBD that. Sample size: XXX.")
    b = exports.prepare_export(state, slug)
    markers = {p["marker"] for p in b["placeholders"]}
    assert {"TODO", "TBD", "XXX"} <= markers
    assert any("placeholder marker" in w for w in b["warnings"])


def test_prepare_export_detects_bracket_placeholders(state):
    slug = _setup(state)
    sections.update_section(state, slug, "results", body="Effect size was [...].")
    b = exports.prepare_export(state, slug)
    assert any(p["marker"].startswith("[") for p in b["placeholders"])


def test_prepare_export_flags_unresolved_doi_citations(state):
    slug = _setup(state)
    sections.update_section(state, slug, "introduction",
                            body="This was shown by {doi:10.1/found} and {doi:10.1/missing}.")
    references.add_reference(state, slug, citation_key="found", title="Found",
                             doi="10.1/found")
    b = exports.prepare_export(state, slug)
    assert b["unresolved_citations"] == ["10.1/missing"]
    assert any("unresolved" in w for w in b["warnings"])


def test_prepare_export_flags_empty_sections(state):
    slug = _setup(state)
    # Default sections start as pending + empty
    b = exports.prepare_export(state, slug)
    empty_warnings = [w for w in b["warnings"] if "is empty" in w]
    assert len(empty_warnings) >= 1  # all default sections are pending+empty


def test_prepare_export_suggests_csl_from_journal(state):
    slug = _setup(state)
    b = exports.prepare_export(state, slug)
    assert b["suggested_csl_filename"] == "nature.csl"


def test_prepare_export_missing_paper_raises(state):
    with pytest.raises(NotFound):
        exports.prepare_export(state, "ghost")


# ──────────────────────────────────────────────────────────────────────────────
# export_to_path
# ──────────────────────────────────────────────────────────────────────────────


def test_export_to_path_writes_manuscript_and_bib_into_tmpdir(state, pandoc, tmp_path):
    slug = _setup(state)
    sections.update_section(state, slug, "results", body="We found things.")
    references.add_reference(state, slug, citation_key="x2024", title="X", year=2024)
    out = tmp_path / "out.docx"

    res = exports.export_to_path(state, slug, output_path=str(out))
    assert res.get("error") is None
    assert pathlib.Path(res["local_path"]).is_file()

    # Pandoc was called once with the expected args
    assert len(pandoc.calls) == 1
    call = pandoc.calls[0]
    assert "manuscript.md" in call["args"]
    assert "-o" in call["args"]
    assert "--bibliography" in call["args"]
    assert "--citeproc" in call["args"]
    # Temp-dir layout had the manuscript + bib
    assert "manuscript.md" in call["files"]
    assert b"We found things." in call["files"]["manuscript.md"]
    assert "references.bib" in call["files"]
    assert b"@article{x2024" in call["files"]["references.bib"]


def test_export_to_path_writes_figure_blobs_into_tmpdir(state, pandoc, tmp_path):
    slug = _setup(state)
    # Use a fake local PNG to seed the blob
    src = tmp_path / "src.png"
    src.write_bytes(b"PNG_DATA")
    figures.add_figure(state, slug, figure_number=1, title="Fig 1", local_path=str(src))

    out = tmp_path / "out.docx"
    exports.export_to_path(state, slug, output_path=str(out))

    snapshot = pandoc.calls[0]["files"]
    assert "figure_1.png" in snapshot
    assert snapshot["figure_1.png"] == b"PNG_DATA"


def test_export_to_path_uploads_to_storage_and_records_doc(state, backend, tmp_path):
    slug = _setup(state)
    out = tmp_path / "out.docx"
    res = exports.export_to_path(state, slug, output_path=str(out))
    blob_path = res["blob_path"]
    assert blob_path == f"projects/p-alice/papers/{slug}/exports/out.docx"
    assert backend.get_blob(blob_path) == b"FAKE_PANDOC_OUTPUT"
    # Export doc record exists
    doc = backend.get_doc(blob_path)
    assert doc is not None
    assert doc["filename"] == "out.docx"
    assert doc["format"] == "docx"


def test_export_to_path_skips_upload_when_disabled(state, backend, tmp_path):
    slug = _setup(state)
    out = tmp_path / "out.docx"
    res = exports.export_to_path(state, slug, output_path=str(out),
                                  upload_to_storage=False)
    assert res["blob_path"] is None
    # No blob written
    assert backend.get_blob(f"projects/p-alice/papers/{slug}/exports/out.docx") is None


def test_export_to_path_format_inferred_from_extension(state, pandoc, tmp_path):
    slug = _setup(state)
    out_tex = tmp_path / "paper.tex"
    exports.export_to_path(state, slug, output_path=str(out_tex))
    args = pandoc.calls[0]["args"]
    assert "-t" in args and "latex" in args


def test_export_to_path_omits_bib_args_when_no_refs(state, pandoc, tmp_path):
    slug = _setup(state)
    out = tmp_path / "out.docx"
    exports.export_to_path(state, slug, output_path=str(out))
    args = pandoc.calls[0]["args"]
    assert "--bibliography" not in args
    assert "--citeproc" not in args
    # And no references.bib in the temp dir
    assert "references.bib" not in pandoc.calls[0]["files"]


def test_export_to_path_passes_csl_when_provided(state, pandoc, tmp_path):
    slug = _setup(state)
    references.add_reference(state, slug, citation_key="a", title="A", year=2024)
    out = tmp_path / "out.docx"
    csl = str(tmp_path / "nature.csl")
    exports.export_to_path(state, slug, output_path=str(out), csl_path=csl)
    args = pandoc.calls[0]["args"]
    assert "--csl" in args
    assert csl in args


def test_export_to_path_rejects_unsupported_format(state, tmp_path):
    slug = _setup(state)
    out = tmp_path / "out.weird"
    with pytest.raises(ValueError, match="unsupported format"):
        exports.export_to_path(state, slug, output_path=str(out), fmt="weird")


def test_export_to_path_propagates_pandoc_failure(state, pandoc, tmp_path):
    slug = _setup(state)
    # Make pandoc "fail"
    pandoc._rc = 99
    out = tmp_path / "out.docx"
    res = exports.export_to_path(state, slug, output_path=str(out))
    assert "error" in res
    assert "rc=99" in res["error"]


# ──────────────────────────────────────────────────────────────────────────────
# list_exports
# ──────────────────────────────────────────────────────────────────────────────


def test_list_exports_returns_recent_first(state, tmp_path):
    slug = _setup(state)
    exports.export_to_path(state, slug, output_path=str(tmp_path / "v1.docx"))
    exports.export_to_path(state, slug, output_path=str(tmp_path / "v2.docx"))
    listed = exports.list_exports(state, slug)
    assert [e["filename"] for e in listed][0] == "v2.docx"


def test_list_exports_isolation_between_users(state, other_state, tmp_path):
    slug = _setup(state)
    exports.export_to_path(state, slug, output_path=str(tmp_path / "v1.docx"))
    with pytest.raises(NotFound):
        exports.list_exports(other_state, slug)


def test_list_exports_missing_paper_raises(state):
    with pytest.raises(NotFound):
        exports.list_exports(state, "ghost")
