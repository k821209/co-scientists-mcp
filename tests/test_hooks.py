"""Hooks behave correctly when invoked as subprocesses with JSON on stdin.

This tests the *hook scripts* (packages/hooks/*.py) — independent from the
MCP tool functions tested elsewhere.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent / "packages" / "hooks"


def _run_hook(name: str, payload: dict, *, env: dict | None = None,
              cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / f"{name}.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env={**os.environ, **(env or {})},
        cwd=str(cwd) if cwd else None,
        timeout=10,
    )


# ──────────────────────────────────────────────────────────────────────────────
# session_start
# ──────────────────────────────────────────────────────────────────────────────


def test_session_start_with_manuscript_marker(tmp_path):
    paper_dir = tmp_path / "rice-evo"
    paper_dir.mkdir()
    (paper_dir / "manuscript.md").write_text("# Rice")
    res = _run_hook("session_start", {}, cwd=paper_dir)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert "rice-evo" in out["additionalContext"]
    assert "open" in out["additionalContext"].lower()  # mentions open comments


def test_session_start_with_explicit_marker_file(tmp_path):
    paper_dir = tmp_path / "weird-dir-name"
    paper_dir.mkdir()
    (paper_dir / ".co-scientist-paper").write_text("nice-slug")
    res = _run_hook("session_start", {}, cwd=paper_dir)
    out = json.loads(res.stdout)
    assert "nice-slug" in out["additionalContext"]


def test_session_start_with_no_paper(tmp_path):
    res = _run_hook("session_start", {}, cwd=tmp_path)
    out = json.loads(res.stdout)
    assert "no paper detected" in out["additionalContext"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# post_tool
# ──────────────────────────────────────────────────────────────────────────────


def test_post_tool_is_noop():
    res = _run_hook("post_tool", {"tool_name": "mcp__co_scientist__update_section"})
    assert res.returncode == 0
    assert res.stdout == ""


def test_post_tool_survives_garbage_input():
    res = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "post_tool.py")],
        input="this is not json",
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert res.returncode == 0


# ──────────────────────────────────────────────────────────────────────────────
# pretool_block_ssh_nohup
# ──────────────────────────────────────────────────────────────────────────────


def _seed_servers_cache(tmp_path: Path, aliases: list[dict]) -> Path:
    cache = tmp_path / "servers.json"
    cache.write_text(json.dumps({"servers": aliases}))
    return cache


def test_ssh_nohup_blocked_when_alias_matches(tmp_path):
    cache = _seed_servers_cache(tmp_path, [{"alias": "nabis2", "host": "h", "user": "u"}])
    res = _run_hook(
        "pretool_block_ssh_nohup",
        {"tool_name": "Bash",
         "tool_input": {"command": "ssh nabis2 'nohup python build.py > log 2>&1 &'"}},
        env={"CO_SCIENTIST_SERVERS_CACHE": str(cache)},
    )
    assert res.returncode == 2
    assert "submit_remote_job" in res.stderr


def test_ssh_nohup_allowed_with_setup_prefix(tmp_path):
    cache = _seed_servers_cache(tmp_path, [{"alias": "nabis2", "host": "h", "user": "u"}])
    res = _run_hook(
        "pretool_block_ssh_nohup",
        {"tool_name": "Bash",
         "tool_input": {"command": "# setup\nssh nabis2 'nohup conda env create &'"}},
        env={"CO_SCIENTIST_SERVERS_CACHE": str(cache)},
    )
    assert res.returncode == 0


def test_ssh_nohup_allowed_when_no_nohup_present(tmp_path):
    cache = _seed_servers_cache(tmp_path, [{"alias": "nabis2", "host": "h", "user": "u"}])
    res = _run_hook(
        "pretool_block_ssh_nohup",
        {"tool_name": "Bash", "tool_input": {"command": "ssh nabis2 ls -la"}},
        env={"CO_SCIENTIST_SERVERS_CACHE": str(cache)},
    )
    assert res.returncode == 0


def test_ssh_nohup_allowed_when_alias_unknown(tmp_path):
    cache = _seed_servers_cache(tmp_path, [{"alias": "nabis2", "host": "h", "user": "u"}])
    res = _run_hook(
        "pretool_block_ssh_nohup",
        {"tool_name": "Bash",
         "tool_input": {"command": "ssh random-host 'nohup foo &'"}},
        env={"CO_SCIENTIST_SERVERS_CACHE": str(cache)},
    )
    assert res.returncode == 0


def test_ssh_nohup_fails_open_when_cache_missing(tmp_path):
    # Point at a non-existent cache file
    res = _run_hook(
        "pretool_block_ssh_nohup",
        {"tool_name": "Bash",
         "tool_input": {"command": "ssh nabis2 'nohup foo &'"}},
        env={"CO_SCIENTIST_SERVERS_CACHE": str(tmp_path / "no-such.json")},
    )
    assert res.returncode == 0


def test_ssh_nohup_ignores_non_bash_tools(tmp_path):
    cache = _seed_servers_cache(tmp_path, [{"alias": "nabis2", "host": "h", "user": "u"}])
    res = _run_hook(
        "pretool_block_ssh_nohup",
        {"tool_name": "Read", "tool_input": {"file_path": "/etc/passwd"}},
        env={"CO_SCIENTIST_SERVERS_CACHE": str(cache)},
    )
    assert res.returncode == 0


# ──────────────────────────────────────────────────────────────────────────────
# pretool_cutadapt_lint
# ──────────────────────────────────────────────────────────────────────────────


def test_cutadapt_warns_on_loose_paired():
    res = _run_hook(
        "pretool_cutadapt_lint",
        {"tool_name": "Bash",
         "tool_input": {"command": "cutadapt -g CCAA -a GGTT --discard-untrimmed in.fq -o out.fq"}},
    )
    assert res.returncode == 0  # non-blocking
    assert "loose-vs-strict" in res.stderr


def test_cutadapt_quiet_for_linked_form():
    res = _run_hook(
        "pretool_cutadapt_lint",
        {"tool_name": "Bash",
         "tool_input": {"command": "cutadapt -g 'CCAA...GGTT' --discard-untrimmed in.fq -o out.fq"}},
    )
    assert res.returncode == 0
    assert res.stderr == ""


def test_cutadapt_quiet_without_discard_untrimmed():
    res = _run_hook(
        "pretool_cutadapt_lint",
        {"tool_name": "Bash",
         "tool_input": {"command": "cutadapt -g CCAA -a GGTT in.fq -o out.fq"}},
    )
    assert res.returncode == 0
    assert res.stderr == ""


def test_cutadapt_ignores_non_bash():
    res = _run_hook(
        "pretool_cutadapt_lint",
        {"tool_name": "Read", "tool_input": {"file_path": "foo"}},
    )
    assert res.returncode == 0
    assert res.stderr == ""
