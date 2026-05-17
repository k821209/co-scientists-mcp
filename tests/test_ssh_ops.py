"""SSH-bound server tools, using FakeSSHExecutor.

We never actually shell out — the executor is the only seam where SSH would
happen. The tests verify the *logic* layered on top of the executor:
- parsing uptime/free/ps output
- politeness check gating
- pidfile idempotency in submit
- dead-PID reconciliation
- untracked-job detection
"""
from __future__ import annotations

import pytest

from co_scientist_local.tools import analyses, papers, runs, servers, ssh_ops


# ──────────────────────────────────────────────────────────────────────────────
# server_status
# ──────────────────────────────────────────────────────────────────────────────


_UPTIME_OK = "  10:23:45 up 12 days,  4:17,  3 users,  load average: 0.42, 0.51, 0.48"
_FREE_OK = (
    "              total        used        free      shared  buff/cache   available\n"
    "Mem:             64          12          30           0          22          50\n"
    "Swap:             8           0           8"
)


def _status_output(*, uptime=_UPTIME_OK, free=_FREE_OK, others=0, ours_lines=()):
    """Build the multi-section output that server_status expects."""
    parts = ["---uptime---", uptime, "---free---", free, "---others---", str(others), "---ours---"]
    parts.extend(ours_lines)
    return "\n".join(parts)


def test_server_status_parses_normal_output(state, ssh):
    servers.add_server(state, alias="nabis2", host="10.0.0.1", user="alice", cores=32)
    ssh.expect(stdout=_status_output())
    s = ssh_ops.server_status(state, "nabis2")
    assert s["online"] is True
    assert s["load"] == {"load_1": 0.42, "load_5": 0.51, "load_15": 0.48}
    assert s["memory"]["total_gb"] == 64
    assert s["memory"]["available_gb"] == 50
    assert s["other_users_heavy_count"] == 0
    assert s["warnings"] == []
    assert s["polite_max_workers"] == 16  # 32 * 50%


def test_server_status_warns_on_high_load(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u", cores=8)
    ssh.expect(stdout=_status_output(
        uptime="up 1 day, load average: 9.20, 8.10, 7.50",
    ))
    s = ssh_ops.server_status(state, "nabis2")
    assert any("load avg" in w for w in s["warnings"])


def test_server_status_warns_on_low_memory(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u", cores=8)
    ssh.expect(stdout=_status_output(
        free=(
            "              total        used        free      shared  buff/cache   available\n"
            "Mem:            100          95           2           0           3           3"
        ),
    ))
    s = ssh_ops.server_status(state, "nabis2")
    assert any("available memory" in w for w in s["warnings"])


def test_server_status_warns_on_other_user_heavy_procs(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u", cores=8)
    ssh.expect(stdout=_status_output(others=5))
    s = ssh_ops.server_status(state, "nabis2")
    assert any("other-user process" in w for w in s["warnings"])


def test_server_status_unreachable(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    ssh.expect(rc=255, stderr="ssh: connect to host h port 22: Connection refused")
    s = ssh_ops.server_status(state, "nabis2")
    assert s["online"] is False
    assert "unreachable" in s["warnings"][0].lower()


def test_server_status_reports_our_running_pids(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u", cores=8)
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")
    # Record a run with pid 12345 on nabis2 (unfinished)
    runs.record_analysis_run(state, "p", "pca", command="x", host="nabis2", pid=12345)

    # Status SSH returns one alive PID in ours section
    ssh.expect(stdout=_status_output(
        ours_lines=("12345 02:04:13 python build_pca.py",),
    ))
    s = ssh_ops.server_status(state, "nabis2")
    assert len(s["our_running"]) == 1
    assert s["our_running"][0]["pid"] == 12345
    assert s["dead_pids"] == []


def test_server_status_marks_missing_pids_as_dead(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u", cores=8)
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")
    runs.record_analysis_run(state, "p", "pca", command="a", host="nabis2", pid=1111)
    runs.record_analysis_run(state, "p", "pca", command="b", host="nabis2", pid=2222)

    # SSH returns only one of the two
    ssh.expect(stdout=_status_output(
        ours_lines=("1111 02:00:00 python a.py",),
    ))
    s = ssh_ops.server_status(state, "nabis2")
    assert 2222 in s["dead_pids"]
    assert 1111 not in s["dead_pids"]


# ──────────────────────────────────────────────────────────────────────────────
# submit_remote_job
# ──────────────────────────────────────────────────────────────────────────────


def _seed_for_submit(state):
    servers.add_server(state, alias="nabis2", host="10.0.0.1", user="u",
                       cores=32, default_workdir="/scratch/u", conda_root="/opt/conda")
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")


def _ok_status_response(ssh):
    ssh.expect(command_substring="---uptime---", stdout=_status_output())


def test_submit_remote_job_records_run_on_success(state, ssh, rsync, tmp_path):
    _seed_for_submit(state)
    local = tmp_path / "local"
    local.mkdir()

    # 1. server_status call returns healthy
    _ok_status_response(ssh)
    # 2. mkdir
    ssh.expect(command_substring="mkdir -p", stdout="")
    # 3. launch returns PID:99999
    ssh.expect(command_substring="nohup bash", stdout="PID:99999")

    res = ssh_ops.submit_remote_job(
        state, "p", "pca",
        command="python build.py", server_alias="nabis2",
        env_name="ami_n69", workers=8, local_dir=str(local),
    )
    assert res["pid"] == 99999
    assert res["existing"] is False
    assert res["run_key"] is not None
    # rsync was called with the right args
    assert len(rsync.calls) == 1
    assert rsync.calls[0][0] == "nabis2"
    # run row exists
    listed = runs.list_analysis_runs(state, "p", "pca")
    assert len(listed) == 1
    assert listed[0]["pid"] == 99999
    assert listed[0]["host"] == "nabis2"


def test_submit_remote_job_idempotent_on_existing_pidfile(state, ssh, rsync):
    _seed_for_submit(state)
    _ok_status_response(ssh)
    ssh.expect(command_substring="mkdir -p", stdout="")
    # Launcher reports the pidfile already has a live PID
    ssh.expect(command_substring="nohup bash", stdout="EXISTING:55555")

    res = ssh_ops.submit_remote_job(
        state, "p", "pca",
        command="python build.py", server_alias="nabis2",
        sync_files=False,
    )
    assert res["existing"] is True
    assert res["pid"] == 55555
    # No new run row created
    assert len(runs.list_analysis_runs(state, "p", "pca")) == 0
    assert any("Duplicate submit blocked" in w for w in res["warnings"])


def test_submit_remote_job_blocks_on_high_load(state, ssh, rsync):
    _seed_for_submit(state)
    ssh.expect(stdout=_status_output(
        uptime="up 5h, load average: 40.0, 35.0, 30.0",
    ))
    res = ssh_ops.submit_remote_job(
        state, "p", "pca",
        command="python build.py", server_alias="nabis2",
        sync_files=False,
    )
    assert "error" in res
    assert "load avg" in res["error"]


def test_submit_remote_job_blocks_on_worker_overcap(state, ssh, rsync):
    _seed_for_submit(state)
    _ok_status_response(ssh)
    res = ssh_ops.submit_remote_job(
        state, "p", "pca",
        command="python build.py", server_alias="nabis2",
        workers=20,  # cores=32 * 50% = 16 polite cap
        sync_files=False,
    )
    assert "error" in res
    assert "polite cap" in res["error"]


def test_submit_remote_job_force_bypasses_politeness(state, ssh, rsync):
    _seed_for_submit(state)
    # Use command_substring matcher so the high-load response is *only* served
    # for the server_status SSH call, not the subsequent mkdir / nohup calls.
    ssh.expect(command_substring="---uptime---", stdout=_status_output(
        uptime="up 5h, load average: 40.0, 35.0, 30.0",
    ))
    ssh.expect(command_substring="mkdir -p", stdout="")
    ssh.expect(command_substring="nohup bash", stdout="PID:12345")
    res = ssh_ops.submit_remote_job(
        state, "p", "pca", command="x",
        server_alias="nabis2", workers=999, sync_files=False, force=True,
    )
    assert res.get("error") is None
    assert res["pid"] == 12345


def test_submit_remote_job_requires_default_workdir(state, ssh, rsync):
    servers.add_server(state, alias="bare", host="h", user="u")  # no default_workdir
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")
    res = ssh_ops.submit_remote_job(
        state, "p", "pca", command="x", server_alias="bare", sync_files=False,
    )
    assert "default_workdir" in res["error"]


# ──────────────────────────────────────────────────────────────────────────────
# tail / kill / poll / scan
# ──────────────────────────────────────────────────────────────────────────────


def test_tail_remote_log_returns_output(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u",
                       default_workdir="/scratch/u")
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")
    run = runs.record_analysis_run(
        state, "p", "pca", command="x", host="nabis2",
        pid=99999, log_path="analysis/pca/run.log",
    )
    ssh.expect(command_substring="tail -n", stdout="line 1\nline 2\nline 3")
    res = ssh_ops.tail_remote_log(state, "p", "pca", run["run_key"], lines=10)
    assert res["tail"] == "line 1\nline 2\nline 3"


def test_tail_remote_log_local_reads_file(state, tmp_path):
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")
    log = tmp_path / "run.log"
    log.write_text("hello\nworld\n")
    r = runs.record_analysis_run(state, "p", "pca", command="x",
                                 host="local", pid=1, log_path=str(log))
    res = ssh_ops.tail_remote_log(state, "p", "pca", r["run_key"], lines=5)
    assert "hello" in res["tail"] and "world" in res["tail"]


def test_kill_remote_job_marks_finished(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")
    r = runs.record_analysis_run(state, "p", "pca", command="x", host="nabis2", pid=77777)
    ssh.expect(command_substring="kill -9", rc=0)
    res = ssh_ops.kill_remote_job(state, "p", "pca", r["run_key"])
    assert res["killed"] is True
    # Run is now marked finished with exit_code=-1
    final = runs.get_analysis_run(state, "p", "pca", r["run_key"])
    assert final["finished_at"] is not None
    assert final["exit_code"] == -1


def test_kill_remote_job_idempotent_when_already_finished(state):
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")
    r = runs.record_analysis_run(state, "p", "pca", command="x", host="local", pid=1)
    runs.mark_run_finished(state, "p", "pca", r["run_key"], exit_code=0)
    res = ssh_ops.kill_remote_job(state, "p", "pca", r["run_key"])
    assert "already finished" in res["error"]


def test_poll_remote_pids_closes_dead_rows(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")
    r_alive = runs.record_analysis_run(state, "p", "pca", command="a",
                                        host="nabis2", pid=1111)
    r_dead = runs.record_analysis_run(state, "p", "pca", command="b",
                                       host="nabis2", pid=2222)
    # SSH reports only the alive PID
    ssh.expect(command_substring="ps -p", stdout="1111\n")
    res = ssh_ops.poll_remote_pids(state, "nabis2")
    assert res["finished"] == 1
    assert res["still_running"] == 1
    # The dead row is now finished, the alive one is not
    assert runs.get_analysis_run(state, "p", "pca", r_dead["run_key"])["finished_at"] is not None
    assert runs.get_analysis_run(state, "p", "pca", r_alive["run_key"])["finished_at"] is None


def test_poll_remote_pids_noop_when_no_unfinished_rows(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    papers.create_paper(state, title="P")
    res = ssh_ops.poll_remote_pids(state, "nabis2")
    assert res == {"alias": "nabis2", "checked": 0, "finished": 0, "still_running": 0}


def test_scan_untracked_jobs_detects_orphan_python(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    # ppid==1 + python script + 120s etime → untracked
    ssh.expect(command_substring="--no-headers", stdout=(
        "12345 1 00:02:00 python /home/u/analysis/foo.py\n"      # untracked job-like
        "67890 1 00:00:30 python short.py\n"                      # etime < 60, skipped
        "111   1 12-00:00:00 sshd: u@pts/0\n"                     # excluded daemon
        "222   12345 00:01:30 bash -c something\n"                # ppid != 1
    ))
    res = ssh_ops.scan_untracked_jobs(state, "nabis2", min_etime_seconds=60)
    pids = [u["pid"] for u in res["untracked"]]
    assert pids == [12345]
    assert res["tracked"] == []


def test_scan_untracked_jobs_skips_known_tracked_pids(state, ssh):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")
    runs.record_analysis_run(state, "p", "pca", command="x", host="nabis2", pid=99999)
    ssh.expect(command_substring="--no-headers", stdout=(
        "99999 1 00:05:00 python analysis.py\n"  # is tracked
        "88888 1 00:05:00 Rscript model.R\n"     # not tracked
    ))
    res = ssh_ops.scan_untracked_jobs(state, "nabis2", min_etime_seconds=60)
    assert res["tracked"] == [99999]
    assert [u["pid"] for u in res["untracked"]] == [88888]


def test_auto_finish_stale_runs_local_dead_pid(state):
    papers.create_paper(state, title="P")
    analyses.create_analysis(state, "p", name="pca")
    # Pick a PID extremely unlikely to be alive
    r = runs.record_analysis_run(state, "p", "pca", command="x", host="local",
                                 pid=999999)
    res = ssh_ops.auto_finish_stale_runs(state)
    assert res["finished"] >= 1
    assert runs.get_analysis_run(state, "p", "pca", r["run_key"])["finished_at"] is not None
