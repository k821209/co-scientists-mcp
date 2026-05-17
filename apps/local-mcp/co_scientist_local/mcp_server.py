"""FastMCP server: registers tool functions for Claude Code over stdio."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .state import State
from .tools import analyses as _analyses
from .tools import exports as _exports
from .tools import figures as _figures
from .tools import images as _images
from .tools import papers as _papers
from .tools import references as _references
from .tools import reviews as _reviews
from .tools import runs as _runs
from .tools import sections as _sections
from .tools import servers as _servers
from .tools import ssh_ops as _ssh_ops
from .tools import tables as _tables


def build_mcp(state: State) -> FastMCP:
    """Construct the MCP server bound to a given State (uid + backend)."""
    mcp = FastMCP("co-scientist-local")

    # ─── papers ──────────────────────────────────────────────────────────────
    @mcp.tool()
    def create_paper(
        title: str,
        slug: str | None = None,
        authors: list[str] | None = None,
        journal: str | None = None,
        abstract: str | None = None,
    ) -> dict[str, Any]:
        """Create a new paper and seed canonical sections."""
        return _papers.create_paper(
            state, title=title, slug=slug, authors=authors,
            journal=journal, abstract=abstract,
        )

    @mcp.tool()
    def list_papers() -> list[dict[str, Any]]:
        """List all papers for the active user."""
        return _papers.list_papers(state)

    @mcp.tool()
    def get_paper_state(slug: str) -> dict[str, Any]:
        """Return paper + sections + assembled manuscript text."""
        return _papers.get_paper_state(state, slug)

    @mcp.tool()
    def update_paper(
        slug: str,
        title: str | None = None,
        journal: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Patch a paper's metadata."""
        return _papers.update_paper(state, slug, title=title, journal=journal, status=status)

    @mcp.tool()
    def delete_paper(slug: str) -> dict[str, Any]:
        """Delete a paper and all its sections/reviews/manuscript blob."""
        return {"deleted": _papers.delete_paper(state, slug)}

    # ─── sections ────────────────────────────────────────────────────────────
    @mcp.tool()
    def get_section(slug: str, key: str) -> dict[str, Any]:
        """Read one section's body + metadata."""
        return _sections.get_section(state, slug, key)

    @mcp.tool()
    def update_section(
        slug: str,
        key: str,
        body: str | None = None,
        status: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Update a section's body/status/title; regenerates the manuscript blob."""
        return _sections.update_section(state, slug, key, body=body, status=status, title=title)

    @mcp.tool()
    def list_sections(slug: str) -> list[dict[str, Any]]:
        """List all sections for a paper."""
        return _sections.list_sections(state, slug)

    @mcp.tool()
    def get_manuscript(slug: str) -> str:
        """Return the assembled manuscript.md as a string."""
        return _sections.get_manuscript(state, slug)

    # ─── reviews / comments ──────────────────────────────────────────────────
    @mcp.tool()
    def add_review(
        slug: str,
        comment: str,
        source: str = "user",
        reviewer_name: str = "User",
        section: str | None = None,
        severity: str = "minor",
        manuscript_ref: str | None = None,
        anchor_text: str | None = None,
        manuscript_snapshot: str | None = None,
    ) -> dict[str, Any]:
        """Create a new review/comment. Use source='user' for dashboard comments."""
        return _reviews.add_review(
            state, slug, comment=comment, source=source, reviewer_name=reviewer_name,
            section=section, severity=severity, manuscript_ref=manuscript_ref,
            anchor_text=anchor_text, manuscript_snapshot=manuscript_snapshot,
        )

    @mcp.tool()
    def list_reviews(
        slug: str,
        status: str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """List reviews for a paper, optionally filtered."""
        return _reviews.list_reviews(state, slug, status=status, source=source)

    @mcp.tool()
    def update_review(
        slug: str,
        review_id: str,
        status: str | None = None,
        response: str | None = None,
    ) -> dict[str, Any]:
        """Update a review's status / response text."""
        return _reviews.update_review(state, slug, review_id, status=status, response=response)

    @mcp.tool()
    def count_open_user_comments(slug: str) -> int:
        """How many unresolved user comments exist (for SessionStart banner)."""
        return _reviews.count_open_user_comments(state, slug)

    # ─── figures ─────────────────────────────────────────────────────────────
    @mcp.tool()
    def add_figure(
        slug: str,
        figure_number: int,
        title: str,
        caption: str | None = None,
        legend: str | None = None,
        local_path: str | None = None,
    ) -> dict[str, Any]:
        """Register a figure. If local_path provided, uploads image bytes to Storage."""
        return _figures.add_figure(
            state, slug, figure_number=figure_number, title=title,
            caption=caption, legend=legend, local_path=local_path,
        )

    @mcp.tool()
    def update_figure(
        slug: str,
        figure_number: int,
        title: str | None = None,
        caption: str | None = None,
        legend: str | None = None,
        local_path: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Patch a figure; optionally replace the image bytes."""
        return _figures.update_figure(
            state, slug, figure_number, title=title, caption=caption,
            legend=legend, local_path=local_path, status=status,
        )

    @mcp.tool()
    def get_figure(slug: str, figure_number: int) -> dict[str, Any]:
        return _figures.get_figure(state, slug, figure_number)

    @mcp.tool()
    def list_figures(slug: str, supplementary: bool = False) -> list[dict[str, Any]]:
        return _figures.list_figures(state, slug, supplementary=supplementary)

    @mcp.tool()
    def delete_figure(slug: str, figure_number: int) -> dict[str, Any]:
        return {"deleted": _figures.delete_figure(state, slug, figure_number)}

    # ─── tables ──────────────────────────────────────────────────────────────
    @mcp.tool()
    def add_table(
        slug: str,
        table_number: int,
        title: str,
        content: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        return _tables.add_table(
            state, slug, table_number=table_number, title=title,
            content=content, caption=caption,
        )

    @mcp.tool()
    def update_table(
        slug: str,
        table_number: int,
        title: str | None = None,
        content: str | None = None,
        caption: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        return _tables.update_table(
            state, slug, table_number, title=title, content=content,
            caption=caption, status=status,
        )

    @mcp.tool()
    def get_table(slug: str, table_number: int) -> dict[str, Any]:
        return _tables.get_table(state, slug, table_number)

    @mcp.tool()
    def list_tables(slug: str, supplementary: bool = False) -> list[dict[str, Any]]:
        return _tables.list_tables(state, slug, supplementary=supplementary)

    @mcp.tool()
    def delete_table(slug: str, table_number: int) -> dict[str, Any]:
        return {"deleted": _tables.delete_table(state, slug, table_number)}

    # ─── references ──────────────────────────────────────────────────────────
    @mcp.tool()
    def add_reference(
        slug: str,
        citation_key: str,
        title: str,
        authors: list[str] | None = None,
        journal: str | None = None,
        year: int | None = None,
        doi: str | None = None,
        pmid: str | None = None,
        bibtex: str | None = None,
    ) -> dict[str, Any]:
        return _references.add_reference(
            state, slug, citation_key=citation_key, title=title, authors=authors,
            journal=journal, year=year, doi=doi, pmid=pmid, bibtex=bibtex,
        )

    @mcp.tool()
    def update_reference(
        slug: str,
        citation_key: str,
        title: str | None = None,
        authors: list[str] | None = None,
        journal: str | None = None,
        year: int | None = None,
        doi: str | None = None,
        pmid: str | None = None,
        bibtex: str | None = None,
    ) -> dict[str, Any]:
        return _references.update_reference(
            state, slug, citation_key, title=title, authors=authors,
            journal=journal, year=year, doi=doi, pmid=pmid, bibtex=bibtex,
        )

    @mcp.tool()
    def get_reference(slug: str, citation_key: str) -> dict[str, Any]:
        return _references.get_reference(state, slug, citation_key)

    @mcp.tool()
    def list_references(slug: str) -> list[dict[str, Any]]:
        return _references.list_references(state, slug)

    @mcp.tool()
    def search_references(
        slug: str,
        doi: str | None = None,
        pmid: str | None = None,
        year: int | None = None,
        title_contains: str | None = None,
    ) -> list[dict[str, Any]]:
        return _references.search_references(
            state, slug, doi=doi, pmid=pmid, year=year, title_contains=title_contains,
        )

    @mcp.tool()
    def delete_reference(slug: str, citation_key: str) -> dict[str, Any]:
        return {"deleted": _references.delete_reference(state, slug, citation_key)}

    # ─── analyses ────────────────────────────────────────────────────────────
    @mcp.tool()
    def create_analysis(
        slug: str,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        return _analyses.create_analysis(state, slug, name=name, description=description)

    @mcp.tool()
    def update_analysis(
        slug: str,
        name: str,
        description: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        return _analyses.update_analysis(state, slug, name, description=description, status=status)

    @mcp.tool()
    def get_analysis(slug: str, name: str) -> dict[str, Any]:
        return _analyses.get_analysis(state, slug, name)

    @mcp.tool()
    def list_analyses(slug: str, status: str | None = None) -> list[dict[str, Any]]:
        return _analyses.list_analyses(state, slug, status=status)

    @mcp.tool()
    def delete_analysis(slug: str, name: str) -> dict[str, Any]:
        return {"deleted": _analyses.delete_analysis(state, slug, name)}

    # ─── compute-server registry ─────────────────────────────────────────────
    @mcp.tool()
    def add_server(
        alias: str,
        host: str,
        user: str,
        cores: int = 1,
        memory_gb: int | None = None,
        gpus: int = 0,
        ssh_key: str | None = None,
        conda_root: str | None = None,
        default_workdir: str | None = None,
        polite_max_cores_pct: int = 50,
        notes: str | None = None,
    ) -> dict[str, Any]:
        return _servers.add_server(
            state, alias=alias, host=host, user=user, cores=cores,
            memory_gb=memory_gb, gpus=gpus, ssh_key=ssh_key,
            conda_root=conda_root, default_workdir=default_workdir,
            polite_max_cores_pct=polite_max_cores_pct, notes=notes,
        )

    @mcp.tool()
    def list_servers(active_only: bool = True) -> list[dict[str, Any]]:
        return _servers.list_servers(state, active_only=active_only)

    @mcp.tool()
    def get_server(alias: str) -> dict[str, Any]:
        return _servers.get_server(state, alias)

    @mcp.tool()
    def update_server(
        alias: str,
        host: str | None = None,
        user: str | None = None,
        cores: int | None = None,
        polite_max_cores_pct: int | None = None,
        default_workdir: str | None = None,
        active: bool | None = None,
    ) -> dict[str, Any]:
        return _servers.update_server(
            state, alias, host=host, user=user, cores=cores,
            polite_max_cores_pct=polite_max_cores_pct,
            default_workdir=default_workdir, active=active,
        )

    @mcp.tool()
    def delete_server(alias: str) -> dict[str, Any]:
        return {"deleted": _servers.delete_server(state, alias)}

    @mcp.tool()
    def add_server_env(
        alias: str,
        env_name: str,
        env_type: str = "conda",
        python_version: str | None = None,
        key_packages: list[str] | None = None,
    ) -> dict[str, Any]:
        return _servers.add_server_env(
            state, alias, env_name=env_name, env_type=env_type,
            python_version=python_version, key_packages=key_packages,
        )

    @mcp.tool()
    def list_server_envs(alias: str) -> list[dict[str, Any]]:
        return _servers.list_server_envs(state, alias)

    @mcp.tool()
    def delete_server_env(alias: str, env_name: str) -> dict[str, Any]:
        return {"deleted": _servers.delete_server_env(state, alias, env_name)}

    # ─── analysis runs ───────────────────────────────────────────────────────
    @mcp.tool()
    def record_analysis_run(
        slug: str,
        analysis: str,
        command: str,
        host: str = "local",
        env_name: str | None = None,
        pid: int | None = None,
        log_path: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        return _runs.record_analysis_run(
            state, slug, analysis, command=command, host=host,
            env_name=env_name, pid=pid, log_path=log_path, notes=notes,
        )

    @mcp.tool()
    def list_analysis_runs(
        slug: str,
        analysis: str,
        unfinished_only: bool = False,
        host: str | None = None,
    ) -> list[dict[str, Any]]:
        return _runs.list_analysis_runs(
            state, slug, analysis, unfinished_only=unfinished_only, host=host,
        )

    @mcp.tool()
    def get_analysis_run(slug: str, analysis: str, run_key: str) -> dict[str, Any]:
        return _runs.get_analysis_run(state, slug, analysis, run_key)

    @mcp.tool()
    def mark_run_finished(
        slug: str,
        analysis: str,
        run_key: str,
        exit_code: int,
        notes: str | None = None,
    ) -> dict[str, Any]:
        return _runs.mark_run_finished(
            state, slug, analysis, run_key, exit_code=exit_code, notes=notes,
        )

    @mcp.tool()
    def launch_local_job(
        slug: str,
        analysis: str,
        command: str,
        workdir: str,
        env_name: str | None = None,
        conda_root: str | None = None,
    ) -> dict[str, Any]:
        """Spawn a long-running local job (detached). Returns run row with pid + log_path."""
        return _runs.launch_local_job(
            state, slug, analysis, command=command, workdir=workdir,
            env_name=env_name, conda_root=conda_root,
        )

    @mcp.tool()
    def reap_local_run(slug: str, analysis: str, run_key: str) -> dict[str, Any]:
        """Check if a local run's PID is gone; if so, mark it finished."""
        return _runs.reap_local_run(state, slug, analysis, run_key)

    # ─── SSH-bound server operations ─────────────────────────────────────────
    @mcp.tool()
    def server_status(alias: str) -> dict[str, Any]:
        """Live SSH check: load avg, memory, our running PIDs, warnings."""
        return _ssh_ops.server_status(state, alias)

    @mcp.tool()
    def submit_remote_job(
        slug: str,
        analysis: str,
        command: str,
        server_alias: str,
        env_name: str | None = None,
        workers: int | None = None,
        local_dir: str | None = None,
        sync_files: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        """Politeness-checked SSH job submission (rsync + nohup, pidfile-idempotent)."""
        return _ssh_ops.submit_remote_job(
            state, slug, analysis, command=command, server_alias=server_alias,
            env_name=env_name, workers=workers, local_dir=local_dir,
            sync_files=sync_files, force=force,
        )

    @mcp.tool()
    def tail_remote_log(
        slug: str,
        analysis: str,
        run_key: str,
        lines: int = 50,
    ) -> dict[str, Any]:
        """Last N lines of a run's log file (remote or local)."""
        return _ssh_ops.tail_remote_log(state, slug, analysis, run_key, lines=lines)

    @mcp.tool()
    def refresh_log_tail(
        slug: str,
        analysis: str,
        run_key: str,
        lines: int = 50,
    ) -> dict[str, Any]:
        """Like tail_remote_log, but persists the tail onto the run doc so the
        dashboard's Runs tab can render it via its Firestore listener."""
        return _ssh_ops.refresh_log_tail(state, slug, analysis, run_key, lines=lines)

    @mcp.tool()
    def kill_remote_job(slug: str, analysis: str, run_key: str) -> dict[str, Any]:
        """SIGKILL the recorded PID + mark run finished."""
        return _ssh_ops.kill_remote_job(state, slug, analysis, run_key)

    @mcp.tool()
    def poll_remote_pids(alias: str) -> dict[str, Any]:
        """One SSH round-trip: close phantom rows for `alias`."""
        return _ssh_ops.poll_remote_pids(state, alias)

    @mcp.tool()
    def auto_finish_stale_runs() -> dict[str, Any]:
        """Bulk cleanup across all hosts (local + remote)."""
        return _ssh_ops.auto_finish_stale_runs(state)

    @mcp.tool()
    def scan_untracked_jobs(alias: str, min_etime_seconds: int = 60) -> dict[str, Any]:
        """Find detached job-like processes on `alias` not in analysis_runs."""
        return _ssh_ops.scan_untracked_jobs(state, alias, min_etime_seconds=min_etime_seconds)

    # ─── export ──────────────────────────────────────────────────────────────
    @mcp.tool()
    def prepare_export(slug: str) -> dict[str, Any]:
        """Pre-export bundle: manuscript text, bibtex, figures, warnings."""
        return _exports.prepare_export(state, slug)

    @mcp.tool()
    def export_to_path(
        slug: str,
        output_path: str,
        fmt: str | None = None,
        csl_path: str | None = None,
        upload_to_storage: bool = True,
    ) -> dict[str, Any]:
        """Run pandoc to produce a document; upload result to Cloud Storage."""
        return _exports.export_to_path(
            state, slug, output_path=output_path, fmt=fmt,
            csl_path=csl_path, upload_to_storage=upload_to_storage,
        )

    @mcp.tool()
    def list_exports(slug: str) -> list[dict[str, Any]]:
        """List previously-exported files for a paper."""
        return _exports.list_exports(state, slug)

    # ─── image generation ────────────────────────────────────────────────────
    @mcp.tool()
    def generate_image(
        slug: str,
        prompt: str,
        figure_number: int | None = None,
        asset_filename: str | None = None,
        aspect_ratio: str = "1:1",
        model: str = "gpt-image-1",
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Generate an image via the configured ImageGenerator (local or cloud-fn).

        Default backend (hosted service) is OpenAI gpt-image-1. Requires a
        Pro+ subscription — the /generate_image Cloud Function refuses with
        403 for free-plan users.

        Supported aspect_ratio values: "1:1" (1024x1024), "16:9"/"3:2"/
        "landscape" (1536x1024), "9:16"/"2:3"/"portrait" (1024x1536).

        If `figure_number` is set, registers the result as a figure for the paper.
        Otherwise stores as an asset under papers/{slug}/assets/.
        """
        return _images.generate_image(
            state, slug, prompt=prompt, figure_number=figure_number,
            asset_filename=asset_filename, aspect_ratio=aspect_ratio,
            model=model, caption=caption,
        )

    @mcp.tool()
    def list_assets(slug: str) -> list[dict[str, Any]]:
        """List generated image assets (non-figure) for a paper."""
        return _images.list_assets(state, slug)

    @mcp.tool()
    def delete_asset(slug: str, asset_id_or_filename: str) -> dict[str, Any]:
        return {"deleted": _images.delete_asset(state, slug, asset_id_or_filename)}

    return mcp
