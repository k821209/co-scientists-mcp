"""Firebase Auth token caching, refresh, and rotation."""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from co_scientist_local.auth import (
    FakeTokenRefresher, FirebaseAuthClient, HttpTokenRefresher,
)


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


# ─── HttpTokenRefresher transient-failure retry ──────────────────────────


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://securetoken", code, "err", {}, io.BytesIO(b'{"error":"x"}'),
    )


def _ok_response():
    class _R:
        def read(self): return json.dumps(
            {"id_token": "fresh", "expires_in": "3600"}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return _R()


def test_refresher_retries_transient_5xx(monkeypatch):
    """A 503 blip then success → refresh() succeeds after retry."""
    import co_scientist_local.auth as auth_mod
    calls = {"n": 0}

    def fake_urlopen(req, timeout=30):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error(503)
        return _ok_response()

    monkeypatch.setattr(auth_mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(auth_mod.time, "sleep", lambda s: None)  # no real waiting

    out = HttpTokenRefresher().refresh("rt", "wk")
    assert out["id_token"] == "fresh"
    assert calls["n"] == 3   # 2 failures + 1 success


def test_refresher_does_not_retry_4xx(monkeypatch):
    """A 400 (bad refresh token) is permanent — fail immediately, no retry."""
    import co_scientist_local.auth as auth_mod
    calls = {"n": 0}

    def fake_urlopen(req, timeout=30):
        calls["n"] += 1
        raise _http_error(400)

    monkeypatch.setattr(auth_mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(auth_mod.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError, match="token refresh failed"):
        HttpTokenRefresher().refresh("rt", "wk")
    assert calls["n"] == 1   # no retry on 4xx


def test_refresher_gives_up_after_max_attempts(monkeypatch):
    """Persistent 5xx → raises after MAX_ATTEMPTS tries."""
    import co_scientist_local.auth as auth_mod
    calls = {"n": 0}

    def fake_urlopen(req, timeout=30):
        calls["n"] += 1
        raise _http_error(500)

    monkeypatch.setattr(auth_mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(auth_mod.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError, match="after 3 attempts"):
        HttpTokenRefresher().refresh("rt", "wk")
    assert calls["n"] == 3
