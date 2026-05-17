"""The MCP server wiring layer.

We don't spin up stdio transport in tests — that would require subprocess +
JSON-RPC plumbing. Instead we verify that build_mcp registers the expected
tool surface and that the tools are callable through the FastMCP registry.
"""
from __future__ import annotations

from co_scientist_local.backends import InMemoryBackend
from co_scientist_local.mcp_server import build_mcp
from co_scientist_local.state import State


def test_build_mcp_registers_expected_tools():
    state = State(project_id="p-alice", owner_uid="alice", backend=InMemoryBackend())
    mcp = build_mcp(state)

    # FastMCP exposes its registered tools via list_tools() (async). Use the
    # internal _tool_manager registry directly to avoid awaiting in this test.
    registered = set(mcp._tool_manager._tools.keys())
    expected = {
        # papers
        "create_paper", "list_papers", "get_paper_state", "update_paper", "delete_paper",
        # sections
        "get_section", "update_section", "list_sections", "get_manuscript",
        # reviews
        "add_review", "list_reviews", "update_review", "count_open_user_comments",
        # figures
        "add_figure", "update_figure", "get_figure", "list_figures", "delete_figure",
        # tables
        "add_table", "update_table", "get_table", "list_tables", "delete_table",
        # references
        "add_reference", "update_reference", "get_reference", "list_references",
        "search_references", "delete_reference",
        # analyses
        "create_analysis", "update_analysis", "get_analysis", "list_analyses", "delete_analysis",
        # compute-server registry
        "add_server", "list_servers", "get_server", "update_server", "delete_server",
        "add_server_env", "list_server_envs", "delete_server_env",
        # analysis runs
        "record_analysis_run", "list_analysis_runs", "get_analysis_run",
        "mark_run_finished", "launch_local_job", "reap_local_run",
        # SSH-bound server operations
        "server_status", "submit_remote_job", "tail_remote_log", "kill_remote_job",
        "poll_remote_pids", "auto_finish_stale_runs", "scan_untracked_jobs",
        # exports
        "prepare_export", "export_to_path", "list_exports",
        # image generation
        "generate_image", "list_assets", "delete_asset",
    }
    missing = expected - registered
    assert not missing, f"missing tools: {missing}"
