"""Compute-server registry CRUD + envs subcollection + isolation.

No SSH calls in v0 — server_status etc. arrive next session.
"""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.tools import servers


def test_add_and_list_server(state):
    servers.add_server(state, alias="nabis2", host="10.1.2.3", user="alice", cores=32)
    listed = servers.list_servers(state)
    assert [s["alias"] for s in listed] == ["nabis2"]
    assert listed[0]["active"] is True


def test_add_server_validates_inputs(state):
    with pytest.raises(ValueError, match="alias is required"):
        servers.add_server(state, alias="", host="h", user="u")
    with pytest.raises(ValueError, match="host is required"):
        servers.add_server(state, alias="a", host="", user="u")
    with pytest.raises(ValueError, match="polite_max_cores_pct"):
        servers.add_server(state, alias="a", host="h", user="u", polite_max_cores_pct=150)


def test_duplicate_alias_rejected(state):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    with pytest.raises(ValueError, match="already exists"):
        servers.add_server(state, alias="nabis2", host="other", user="u")


def test_active_only_filter(state):
    servers.add_server(state, alias="a", host="h", user="u")
    servers.add_server(state, alias="b", host="h", user="u")
    servers.update_server(state, "b", active=False)
    assert [s["alias"] for s in servers.list_servers(state)] == ["a"]
    assert [s["alias"] for s in servers.list_servers(state, active_only=False)] == ["a", "b"]


def test_update_server_patches(state):
    servers.add_server(state, alias="a", host="h1", user="u", cores=8)
    updated = servers.update_server(state, "a", host="h2", cores=16)
    assert updated["host"] == "h2"
    assert updated["cores"] == 16
    assert updated["user"] == "u"  # unchanged


def test_delete_server_cascades_envs(state, backend):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    servers.add_server_env(state, "nabis2", env_name="ami_n69", env_type="conda")
    servers.add_server_env(state, "nabis2", env_name="bio311", env_type="conda")
    assert len(servers.list_server_envs(state, "nabis2")) == 2

    assert servers.delete_server(state, "nabis2") is True
    # Both env docs gone
    assert backend.get_doc("projects/p-alice/servers/nabis2/envs/ami_n69") is None
    assert backend.get_doc("projects/p-alice/servers/nabis2/envs/bio311") is None


def test_server_envs_idempotent_add_replaces(state):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    servers.add_server_env(state, "nabis2", env_name="env1", env_type="conda",
                           python_version="3.10")
    # Re-adding with different python_version should replace, not error
    e = servers.add_server_env(state, "nabis2", env_name="env1", env_type="venv",
                                python_version="3.12")
    assert e["env_type"] == "venv"
    assert e["python_version"] == "3.12"
    envs = servers.list_server_envs(state, "nabis2")
    assert len(envs) == 1


def test_add_env_validates_type(state):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    with pytest.raises(ValueError, match="env_type must be one of"):
        servers.add_server_env(state, "nabis2", env_name="x", env_type="docker")


def test_envs_on_missing_server_raises(state):
    with pytest.raises(NotFound):
        servers.add_server_env(state, "ghost", env_name="x")
    with pytest.raises(NotFound):
        servers.list_server_envs(state, "ghost")


def test_delete_server_env(state):
    servers.add_server(state, alias="nabis2", host="h", user="u")
    servers.add_server_env(state, "nabis2", env_name="x")
    assert servers.delete_server_env(state, "nabis2", "x") is True
    assert servers.delete_server_env(state, "nabis2", "x") is False  # idempotent


def test_server_isolation_between_users(state, other_state):
    servers.add_server(state, alias="alice-hpc", host="h", user="alice")
    assert len(servers.list_servers(state)) == 1
    assert len(servers.list_servers(other_state)) == 0
    with pytest.raises(NotFound):
        servers.get_server(other_state, "alice-hpc")


def test_get_missing_server_raises(state):
    with pytest.raises(NotFound):
        servers.get_server(state, "ghost")
