"""Analysis runs CRUD + launch_local_job (real subprocess).

`launch_local_job` actually spawns a child process; we use `sleep 0.05`
which finishes fast enough that the tests stay snappy. The detached child
writes its exit code to `.exitcode_<run_key>` so `reap_local_run` can
recover it after the PID is gone.
"""
from __future__ import annotations

import os
import pathlib
import time

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import analyses, papers, runs


def _setup(state):
    papers.create_paper(state, title="My paper")
    analyses.create_analysis(state, "my-paper", name="pca")
    return "my-paper", "pca"


def test_record_and_list_run(state):
    slug, an = _setup(state)
    r = runs.record_analysis_run(state, slug, an, command="python build.py",
                                  host="nabis2", env_name="ami_n69", pid=12345)
    assert r["run_key"].startswith("run_")
    assert r["finished_at"] is None
    listed = runs.list_analysis_runs(state, slug, an)
    assert len(listed) == 1
    assert listed[0]["pid"] == 12345


def test_list_runs_filter_unfinished(state):
    slug, an = _setup(state)
    r1 = runs.record_analysis_run(state, slug, an, command="a")
    runs.record_analysis_run(state, slug, an, command="b")
    runs.mark_run_finished(state, slug, an, r1["run_key"], exit_code=0)

    all_runs = runs.list_analysis_runs(state, slug, an)
    unfinished = runs.list_analysis_runs(state, slug, an, unfinished_only=True)
    assert len(all_runs) == 2
    assert len(unfinished) == 1
    assert unfinished[0]["run_key"] != r1["run_key"]


def test_list_runs_filter_host(state):
    slug, an = _setup(state)
    runs.record_analysis_run(state, slug, an, command="a", host="local")
    runs.record_analysis_run(state, slug, an, command="b", host="nabis2")
    runs.record_analysis_run(state, slug, an, command="c", host="nabis2")
    assert len(runs.list_analysis_runs(state, slug, an, host="local")) == 1
    assert len(runs.list_analysis_runs(state, slug, an, host="nabis2")) == 2


def test_mark_run_finished_stamps_fields(state):
    slug, an = _setup(state)
    r = runs.record_analysis_run(state, slug, an, command="a", pid=999)
    fin = runs.mark_run_finished(state, slug, an, r["run_key"], exit_code=0,
                                  notes="completed normally")
    assert fin["finished_at"] is not None
    assert fin["exit_code"] == 0
    assert "completed normally" in fin["notes"]


def test_mark_run_finished_missing_raises(state):
    slug, an = _setup(state)
    with pytest.raises(NotFound):
        runs.mark_run_finished(state, slug, an, "ghost", exit_code=0)


def test_record_run_missing_analysis_raises(state):
    papers.create_paper(state, title="P")
    with pytest.raises(NotFound):
        runs.record_analysis_run(state, "p", "ghost", command="x")


def test_launch_local_job_actually_runs(state, tmp_path):
    """End-to-end: spawn a real subprocess, wait for it, reap, verify."""
    slug, an = _setup(state)
    workdir = tmp_path / "work"
    workdir.mkdir()

    # Sleep briefly then exit successfully
    r = runs.launch_local_job(
        state, slug, an,
        command="sleep 0.05 && echo done > out.txt",
        workdir=str(workdir),
    )
    assert r["pid"] is not None
    assert r["host"] == "local"
    log_path = pathlib.Path(r["log_path"])
    assert log_path.parent == workdir
    assert log_path.exists()

    # Wait for the child to finish (with a safety timeout)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            os.kill(r["pid"], 0)
            time.sleep(0.05)
        except ProcessLookupError:
            break
    else:
        raise AssertionError("subprocess did not exit in time")

    # Side effect of the command landed in workdir
    assert (workdir / "out.txt").read_text().strip() == "done"

    # Reap should mark it finished with exit_code=0 (from .exitcode_<key> sidecar)
    reaped = runs.reap_local_run(state, slug, an, r["run_key"])
    assert reaped["finished_at"] is not None
    assert reaped["exit_code"] == 0


def test_launch_local_job_failing_command_records_exit_code(state, tmp_path):
    slug, an = _setup(state)
    workdir = tmp_path / "work"
    workdir.mkdir()
    r = runs.launch_local_job(
        state, slug, an, command="false", workdir=str(workdir),
    )
    # Wait for exit
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            os.kill(r["pid"], 0)
            time.sleep(0.05)
        except ProcessLookupError:
            break
    reaped = runs.reap_local_run(state, slug, an, r["run_key"])
    assert reaped["exit_code"] == 1  # `false` exits with 1


def test_launch_local_job_missing_workdir_raises(state, tmp_path):
    slug, an = _setup(state)
    with pytest.raises(FileNotFoundError):
        runs.launch_local_job(state, slug, an, command="echo x",
                               workdir=str(tmp_path / "nope"))


def test_reap_skips_already_finished(state):
    slug, an = _setup(state)
    r = runs.record_analysis_run(state, slug, an, command="x", pid=1)
    runs.mark_run_finished(state, slug, an, r["run_key"], exit_code=0)
    # Calling reap on a finished run is a no-op
    after = runs.reap_local_run(state, slug, an, r["run_key"])
    assert after["finished_at"] is not None


def test_runs_isolation_between_users(state, other_state):
    slug, an = _setup(state)
    runs.record_analysis_run(state, slug, an, command="alice's run")
    with pytest.raises(NotFound):
        runs.list_analysis_runs(other_state, slug, an)
