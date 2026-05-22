"""Per-project memory: get / update / append, per-project isolation."""
from __future__ import annotations

import pytest

from co_scientist_local.tools import memory


def test_get_empty_when_unset(state):
    assert memory.get_project_memory(state) == {
        "content": "", "updated_at": None, "updated_by": None,
    }


def test_update_then_get(state):
    memory.update_project_memory(state, "# Notes\n- prefers active voice")
    out = memory.get_project_memory(state)
    assert out["content"] == "# Notes\n- prefers active voice"
    assert out["updated_at"] is not None
    assert out["updated_by"] == "claude"


def test_update_preserves_created_at(state):
    memory.update_project_memory(state, "v1")
    created = state.backend.get_doc(
        state.project_path("memory", "main"))["created_at"]
    memory.update_project_memory(state, "v2")
    doc = state.backend.get_doc(state.project_path("memory", "main"))
    assert doc["content"] == "v2"
    assert doc["created_at"] == created


def test_append_to_empty(state):
    memory.append_project_memory(state, "first fact")
    assert memory.get_project_memory(state)["content"] == "first fact"


def test_append_adds_a_line(state):
    memory.update_project_memory(state, "line one")
    memory.append_project_memory(state, "line two")
    assert memory.get_project_memory(state)["content"] == "line one\nline two"


def test_append_rejects_empty(state):
    with pytest.raises(ValueError, match="empty"):
        memory.append_project_memory(state, "   ")


def test_memory_is_per_project(state, other_state):
    memory.update_project_memory(state, "alice's notes")
    assert memory.get_project_memory(other_state)["content"] == ""
