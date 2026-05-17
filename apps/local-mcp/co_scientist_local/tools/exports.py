"""Manuscript export: prepare bundle, run pandoc, upload result to Storage.

`prepare_export` is pure data — collects everything pandoc will need:
- assembled manuscript text (from compile_manuscript)
- references converted to BibTeX
- figures with their blob paths
- warnings: placeholder markers (TBD/TK/XXX/TODO) and unresolved `{doi:…}`
  citations not present in any reference's `doi` field.

`export_to_path` runs the full pipeline:
1. prepare_export
2. Lay out a temp dir: manuscript.md, references.bib, figure files
3. Invoke pandoc to produce the output file
4. Upload the output to Cloud Storage at
   `users/{uid}/papers/{slug}/exports/{filename}` so the dashboard can serve it.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import tempfile

from ..backends.base import NotFound
from ..state import State
from ..util import now_iso
from . import figures as _figures
from . import papers as _papers
from . import references as _references
from . import sections as _sections
from . import tables as _tables


_DOI_INLINE_RE = re.compile(r"\{doi:([^}]+)\}")
_PLACEHOLDER_RE = re.compile(r"\b(TBD|TK|XXX|TODO|FIXME)\b", re.IGNORECASE)
_BRACKET_PLACEHOLDER_RE = re.compile(r"\[(?:\.{3}|placeholder|tbd|tk|xxx|todo|fixme)\]", re.IGNORECASE)


def _scan_placeholders(text: str) -> list[dict]:
    """Find TODO-like markers per line. Returns [{line, snippet, marker}]."""
    out: list[dict] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for m in _PLACEHOLDER_RE.finditer(line):
            out.append({"line": i, "marker": m.group(0).upper(),
                        "snippet": line.strip()[:200]})
        for m in _BRACKET_PLACEHOLDER_RE.finditer(line):
            out.append({"line": i, "marker": m.group(0),
                        "snippet": line.strip()[:200]})
    return out


def _extract_cited_dois(text: str) -> list[str]:
    return _DOI_INLINE_RE.findall(text)


def _ref_to_bibtex(ref: dict) -> str:
    """Build a minimal @article BibTeX entry from a reference doc.

    If the ref carries a literal `bibtex` field, return that verbatim.
    """
    if ref.get("bibtex"):
        return ref["bibtex"].rstrip() + "\n"
    key = ref.get("citation_key") or "unknown"
    fields: list[str] = []
    if ref.get("title"):
        fields.append(f"  title = {{{ref['title']}}}")
    authors = ref.get("authors")
    if isinstance(authors, list):
        author_str = " and ".join(authors)
    else:
        author_str = authors
    if author_str:
        fields.append(f"  author = {{{author_str}}}")
    if ref.get("journal"):
        fields.append(f"  journal = {{{ref['journal']}}}")
    if ref.get("year"):
        fields.append(f"  year = {{{ref['year']}}}")
    if ref.get("doi"):
        fields.append(f"  doi = {{{ref['doi']}}}")
    body = ",\n".join(fields)
    return f"@article{{{key},\n{body}\n}}\n"


def prepare_export(state: State, slug: str) -> dict:
    """Collect everything needed to export `slug` to a finished document.

    Returns a dict with:
        slug, paper, sections, manuscript (str), figures, tables,
        references, bibtex (str), warnings, placeholders,
        unresolved_citations (list of DOIs), suggested_csl_filename.
    """
    bundle = _papers.get_paper_state(state, slug)
    figs = _figures.list_figures(state, slug)
    supp_figs = _figures.list_figures(state, slug, supplementary=True)
    tbls = _tables.list_tables(state, slug)
    supp_tbls = _tables.list_tables(state, slug, supplementary=True)
    refs = _references.list_references(state, slug)

    manuscript = bundle["manuscript"]
    placeholders = _scan_placeholders(manuscript)
    cited_dois = _extract_cited_dois(manuscript)
    known_dois = {r["doi"] for r in refs if r.get("doi")}
    unresolved = sorted(set(cited_dois) - known_dois)

    bibtex = "".join(_ref_to_bibtex(r) for r in refs)

    paper = bundle["paper"]
    journal = (paper.get("journal") or "").strip()
    csl_suggestion = None
    if journal:
        # Deterministic guess at the CSL filename based on journal.
        # Real CSL resolution (with Zotero repo download) is a v1.x refinement.
        csl_suggestion = re.sub(r"[^a-z0-9]+", "-", journal.lower()).strip("-") + ".csl"

    warnings: list[str] = []
    if placeholders:
        warnings.append(f"{len(placeholders)} placeholder marker(s) in manuscript")
    if unresolved:
        warnings.append(f"{len(unresolved)} unresolved {{doi:…}} citation(s)")
    for s in bundle["sections"]:
        if s.get("status") == "pending" and (s.get("word_count") or 0) == 0:
            warnings.append(f"section '{s['key']}' is empty")

    return {
        "slug": slug,
        "paper": paper,
        "sections": bundle["sections"],
        "manuscript": manuscript,
        "figures": figs,
        "supplementary_figures": supp_figs,
        "tables": tbls,
        "supplementary_tables": supp_tbls,
        "references": refs,
        "bibtex": bibtex,
        "placeholders": placeholders,
        "unresolved_citations": unresolved,
        "suggested_csl_filename": csl_suggestion,
        "warnings": warnings,
    }


_VALID_FORMATS = {"docx", "tex", "pdf", "md"}


def _format_pandoc_args(fmt: str, manuscript_filename: str, output_filename: str,
                       has_bib: bool, csl_path: str | None) -> list[str]:
    args: list[str] = [manuscript_filename, "-o", output_filename]
    if fmt == "tex":
        args.extend(["-t", "latex"])
    elif fmt == "pdf":
        # Use default pdf engine (xelatex/pdflatex if available)
        pass
    elif fmt == "md":
        args.extend(["-t", "markdown"])
    # docx is the implicit default when output ext is .docx
    if has_bib:
        args.extend(["--bibliography", "references.bib", "--citeproc"])
    if csl_path:
        args.extend(["--csl", csl_path])
    return args


def export_to_path(
    state: State,
    slug: str,
    *,
    output_path: str,
    fmt: str | None = None,
    csl_path: str | None = None,
    upload_to_storage: bool = True,
) -> dict:
    """Full export pipeline.

    `fmt` is inferred from output_path extension if None.
    Returns metadata: local path, blob path (if uploaded), pandoc rc/stderr,
    plus the prepare_export warnings so the caller can surface them.
    """
    bundle = prepare_export(state, slug)
    out = pathlib.Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    inferred = (out.suffix.lstrip(".") or "").lower()
    fmt = (fmt or inferred or "docx").lower()
    if fmt not in _VALID_FORMATS:
        raise ValueError(f"unsupported format {fmt!r}; choose from {_VALID_FORMATS}")

    with tempfile.TemporaryDirectory(prefix=f"export-{slug}-") as tmp:
        tmp_path = pathlib.Path(tmp)

        # Lay out manuscript + bib
        (tmp_path / "manuscript.md").write_text(bundle["manuscript"], encoding="utf-8")
        has_bib = bool(bundle["bibtex"].strip())
        if has_bib:
            (tmp_path / "references.bib").write_text(bundle["bibtex"], encoding="utf-8")

        # Download figure blobs into tmp dir (main + supplementary)
        for fig in (*bundle["figures"], *bundle["supplementary_figures"]):
            bp = fig.get("blob_path")
            if not bp:
                continue
            data = state.backend.get_blob(bp)
            if data is None:
                continue
            local_name = pathlib.Path(bp).name
            (tmp_path / local_name).write_bytes(data)

        # Run pandoc; it writes the output file inside tmp dir, we copy it out
        tmp_output = tmp_path / out.name
        args = _format_pandoc_args(
            fmt, "manuscript.md", out.name,
            has_bib=has_bib, csl_path=csl_path,
        )
        rc, stdout, stderr = state.require_pandoc().run(args, cwd=str(tmp_path))
        if rc != 0:
            return {
                "error": f"pandoc failed (rc={rc}): {stderr.strip()}",
                "warnings": bundle["warnings"],
            }
        if not tmp_output.is_file():
            return {
                "error": "pandoc reported success but produced no output file",
                "warnings": bundle["warnings"],
            }

        # Copy to the user-specified path
        shutil.copy2(tmp_output, out)
        output_bytes = tmp_output.read_bytes()

    blob_path: str | None = None
    if upload_to_storage:
        blob_path = state.project_path("papers", slug, "exports", out.name)
        state.backend.put_blob(blob_path, output_bytes)
        # Also record an exports doc so the dashboard can list past exports
        doc_path = state.project_path("papers", slug, "exports", out.name)
        # We're storing the export-doc at the same key as the blob — that's fine
        # because docs and blobs have separate stores. Add metadata fields.
        existing = state.backend.get_doc(doc_path)
        meta = {
            "filename": out.name,
            "format": fmt,
            "blob_path": blob_path,
            "size_bytes": len(output_bytes),
            "updated_at": now_iso(),
        }
        if existing is None:
            meta["created_at"] = meta["updated_at"]
            state.backend.set_doc(doc_path, meta)
        else:
            state.backend.update_doc(doc_path, meta)

    return {
        "slug": slug,
        "format": fmt,
        "local_path": str(out),
        "blob_path": blob_path,
        "size_bytes": len(output_bytes),
        "warnings": bundle["warnings"],
        "placeholders": bundle["placeholders"],
        "unresolved_citations": bundle["unresolved_citations"],
    }


def list_exports(state: State, slug: str) -> list[dict]:
    """List previously-exported files for a paper."""
    if state.backend.get_doc(state.project_path("papers", slug)) is None:
        raise NotFound(f"paper not found: {slug!r} in project {state.project_id!r}")
    pairs = state.backend.list_collection(state.project_path("papers", slug, "exports"))
    items = [data for _, data in pairs]
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return items
