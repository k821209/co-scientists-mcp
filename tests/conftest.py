"""Shared fixtures.

Each test gets a fresh InMemoryBackend wrapped in a State scoped to a
project. The default project id is 'p-alice' owned by uid 'alice'; isolation
tests build a second State with a different project_id against the same
backend.
"""
from __future__ import annotations

import pytest

from co_scientist_local.backends import InMemoryBackend
from co_scientist_local.exporters import FakePandocExecutor
from co_scientist_local.image_gen import FakeImageGenerator
from co_scientist_local.ssh import FakeRsyncExecutor, FakeSSHExecutor
from co_scientist_local.state import State


# Sentinel project id used across tests — must NOT start/end with __ (Firestore reserved)
TEST_PROJECT_ID = "p-alice"
OTHER_PROJECT_ID = "p-bob"


@pytest.fixture
def backend() -> InMemoryBackend:
    return InMemoryBackend()


@pytest.fixture
def ssh() -> FakeSSHExecutor:
    return FakeSSHExecutor()


@pytest.fixture
def rsync() -> FakeRsyncExecutor:
    return FakeRsyncExecutor()


@pytest.fixture
def pandoc() -> FakePandocExecutor:
    return FakePandocExecutor()


@pytest.fixture
def image_gen() -> FakeImageGenerator:
    return FakeImageGenerator()


@pytest.fixture
def state(
    backend: InMemoryBackend,
    ssh: FakeSSHExecutor,
    rsync: FakeRsyncExecutor,
    pandoc: FakePandocExecutor,
    image_gen: FakeImageGenerator,
) -> State:
    return State(
        project_id=TEST_PROJECT_ID, owner_uid="alice",
        backend=backend, ssh=ssh, rsync=rsync,
        pandoc=pandoc, image_gen=image_gen,
    )


@pytest.fixture
def other_state(
    backend: InMemoryBackend,
    ssh: FakeSSHExecutor,
    rsync: FakeRsyncExecutor,
    pandoc: FakePandocExecutor,
    image_gen: FakeImageGenerator,
) -> State:
    """Second project against the same backend — used to test isolation."""
    return State(
        project_id=OTHER_PROJECT_ID, owner_uid="bob",
        backend=backend, ssh=ssh, rsync=rsync,
        pandoc=pandoc, image_gen=image_gen,
    )
