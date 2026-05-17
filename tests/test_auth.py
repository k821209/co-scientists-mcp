"""Firebase Auth token caching, refresh, and rotation."""
from __future__ import annotations

import pytest

from co_scientist_local.auth import FakeTokenRefresher, FirebaseAuthClient


class _Clock:
    """Controllable monotonic clock for tests."""
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.t = start
    def __call__(self) -> float:
        return self.t
    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_get_id_token_calls_refresher_on_first_use():
    clock = _Clock()
    refresher = FakeTokenRefresher()
    client = FirebaseAuthClient(
        web_api_key="key", refresh_token="rt-1",
        refresher=refresher, now_fn=clock,
    )
    token = client.get_id_token()
    assert token == "fake-id-1"
    assert len(refresher.calls) == 1
    assert refresher.calls[0]["refresh_token"] == "rt-1"
    assert refresher.calls[0]["web_api_key"] == "key"


def test_get_id_token_caches_until_near_expiry():
    clock = _Clock()
    refresher = FakeTokenRefresher()
    refresher.set_expires_in(3600)
    client = FirebaseAuthClient(
        web_api_key="key", refresh_token="rt-1",
        refresher=refresher, now_fn=clock,
    )
    a = client.get_id_token()
    clock.advance(100)
    b = client.get_id_token()
    clock.advance(1000)
    c = client.get_id_token()
    # All three within the cache window → single refresh call
    assert a == b == c == "fake-id-1"
    assert len(refresher.calls) == 1


def test_refreshes_when_within_lead_window():
    clock = _Clock()
    refresher = FakeTokenRefresher()
    refresher.set_expires_in(3600)
    client = FirebaseAuthClient(
        web_api_key="key", refresh_token="rt-1",
        refresher=refresher, now_fn=clock,
    )
    client.get_id_token()  # first refresh (1)
    # Advance to 30s before expiry (within REFRESH_LEAD_SECONDS=60 window)
    clock.advance(3600 - 30)
    token = client.get_id_token()
    assert token == "fake-id-2"
    assert len(refresher.calls) == 2


def test_invalidate_forces_next_refresh():
    clock = _Clock()
    refresher = FakeTokenRefresher()
    client = FirebaseAuthClient(
        web_api_key="key", refresh_token="rt-1",
        refresher=refresher, now_fn=clock,
    )
    client.get_id_token()
    client.invalidate()
    client.get_id_token()
    assert len(refresher.calls) == 2


def test_refresh_token_rotation():
    clock = _Clock()
    refresher = FakeTokenRefresher()
    refresher.set_expires_in(60)  # short so we trigger another refresh
    refresher.rotate_refresh_token()
    client = FirebaseAuthClient(
        web_api_key="key", refresh_token="rt-original",
        refresher=refresher, now_fn=clock,
    )
    client.get_id_token()
    # The client should now be using the rotated refresh token
    assert client.refresh_token == "rotated-refresh-1"
    # Trigger another refresh → the rotated token is sent, not the original
    clock.advance(60)
    client.get_id_token()
    assert refresher.calls[1]["refresh_token"] == "rotated-refresh-1"


def test_constructor_rejects_empty_credentials():
    with pytest.raises(ValueError, match="web_api_key is required"):
        FirebaseAuthClient(web_api_key="", refresh_token="rt")
    with pytest.raises(ValueError, match="refresh_token is required"):
        FirebaseAuthClient(web_api_key="k", refresh_token="")


def test_refresh_failure_propagates():
    refresher = FakeTokenRefresher()
    refresher.fail_next()
    client = FirebaseAuthClient(
        web_api_key="k", refresh_token="rt", refresher=refresher,
    )
    with pytest.raises(RuntimeError, match="simulated token refresh"):
        client.get_id_token()
