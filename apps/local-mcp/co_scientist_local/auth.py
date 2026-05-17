"""Firebase Auth client for the local MCP.

The local MCP runs on the user's machine and talks to Firebase. It uses a
**refresh token** (long-lived, revocable from the Firebase Console / web
dashboard) which it exchanges on demand for short-lived **ID tokens** that
the Cloud Function /generate_image accepts in `Authorization: Bearer …`.

Token exchange uses the Firebase Auth REST endpoint:
    POST https://securetoken.googleapis.com/v1/token?key=<WEB_API_KEY>
        grant_type=refresh_token&refresh_token=<refresh_token>
Returns: { id_token, expires_in, refresh_token, user_id, ... }

The web_api_key is *not a secret* — it identifies the Firebase project and
ships in every frontend bundle. Security comes from Firebase Auth rules +
the refresh_token itself.

This module is also useful for FirestoreBackend (future): writing as the
authenticated user with security rules enforced. For v0 the FirestoreBackend
uses Admin SDK (service account) and path discipline; that gets tightened
up later. See architecture_decisions.md.
"""
from __future__ import annotations

import time
from typing import Protocol


class TokenRefresher(Protocol):
    def refresh(self, refresh_token: str, web_api_key: str) -> dict:
        """Exchange a refresh_token for an id_token.

        Returns a dict with keys at least: id_token, expires_in (str/int).
        May also rotate the refresh_token (returned key 'refresh_token').
        """
        ...


class HttpTokenRefresher:
    """Real refresher: POSTs to Google's securetoken endpoint."""

    BASE_URL = "https://securetoken.googleapis.com/v1/token"

    def refresh(self, refresh_token: str, web_api_key: str) -> dict:
        import requests  # type: ignore
        r = requests.post(
            f"{self.BASE_URL}?key={web_api_key}",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


class FakeTokenRefresher:
    """Test refresher: records calls, returns canned tokens.

    Use `set_response(id_token=..., expires_in=...)` to control the next
    response; defaults to 'fake-id-1' and 1 hour.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._counter = 0
        self._expires_in = 3600
        self._fail_next = False
        self._rotate_refresh = False

    def set_expires_in(self, seconds: int) -> None:
        self._expires_in = seconds

    def fail_next(self) -> None:
        self._fail_next = True

    def rotate_refresh_token(self) -> None:
        """Next response will include a new refresh_token (rotation)."""
        self._rotate_refresh = True

    def refresh(self, refresh_token: str, web_api_key: str) -> dict:
        if self._fail_next:
            self._fail_next = False
            raise RuntimeError("simulated token refresh failure")
        self._counter += 1
        self.calls.append({
            "refresh_token": refresh_token,
            "web_api_key": web_api_key,
        })
        out = {
            "id_token": f"fake-id-{self._counter}",
            "expires_in": str(self._expires_in),
        }
        if self._rotate_refresh:
            out["refresh_token"] = f"rotated-refresh-{self._counter}"
            self._rotate_refresh = False
        return out


class FirebaseAuthClient:
    """Caches an ID token until it's near expiry, then refreshes."""

    REFRESH_LEAD_SECONDS = 60  # refresh this long before expiry

    def __init__(
        self,
        *,
        web_api_key: str,
        refresh_token: str,
        refresher: TokenRefresher | None = None,
        now_fn=None,  # injectable for tests; defaults to time.time
    ) -> None:
        if not web_api_key:
            raise ValueError("web_api_key is required")
        if not refresh_token:
            raise ValueError("refresh_token is required")
        self._web_api_key = web_api_key
        self._refresh_token = refresh_token
        self._refresher = refresher or HttpTokenRefresher()
        self._now = now_fn or time.time
        self._id_token: str | None = None
        self._expiry_epoch: float = 0.0

    @property
    def refresh_token(self) -> str:
        """Current refresh token (may have rotated from the original)."""
        return self._refresh_token

    def get_id_token(self) -> str:
        """Return a valid ID token, refreshing if needed."""
        now = self._now()
        if self._id_token is None or now >= self._expiry_epoch - self.REFRESH_LEAD_SECONDS:
            resp = self._refresher.refresh(self._refresh_token, self._web_api_key)
            self._id_token = resp["id_token"]
            try:
                ttl = int(resp.get("expires_in", 3600))
            except (TypeError, ValueError):
                ttl = 3600
            self._expiry_epoch = now + ttl
            new_refresh = resp.get("refresh_token")
            if new_refresh:
                self._refresh_token = new_refresh
        return self._id_token

    def invalidate(self) -> None:
        """Force the next get_id_token() to refresh (e.g. on 401 response)."""
        self._id_token = None
        self._expiry_epoch = 0.0
