"""Entry point: `python -m co_scientist_local`.

Startup modes, in priority order:

  1. **Memory** (CO_SCIENTIST_USE_MEMORY=1) — InMemoryBackend, no network.
  2. **API-key mode** (CO_SCIENTIST_API_KEY set) — preferred multi-user path.
     Exchanges the key via /exchange_key Cloud Function, signs in with the
     resulting custom token, uses the ID token for all Firestore + Storage
     writes. Security rules enforce per-project scope.
  3. **Service-account mode** (GOOGLE_APPLICATION_CREDENTIALS + CO_SCIENTIST_PROJECT_ID)
     — developer / smoke fallback. Bypasses rules. End users never need this.

Env vars per mode:

    API-key mode:
        CO_SCIENTIST_API_KEY          per-project API key from the dashboard
        FIREBASE_PROJECT_ID           the Firebase project (e.g. co-scientist-5af1a)
        FIREBASE_STORAGE_BUCKET       the bucket
        FIREBASE_WEB_API_KEY          public web SDK API key (Identity Toolkit)
        CO_SCIENTIST_EXCHANGE_URL     [optional] override the default Cloud Function URL

    Service-account mode (developer):
        CO_SCIENTIST_PROJECT_ID, FIREBASE_PROJECT_ID, FIREBASE_STORAGE_BUCKET,
        GOOGLE_APPLICATION_CREDENTIALS
"""
from __future__ import annotations

import os
import sys

from .backends import InMemoryBackend
from .mcp_server import build_mcp
from .state import State


def _build_dev_state() -> State:
    pid = os.environ.get("CO_SCIENTIST_PROJECT_ID", "dev-project")
    uid = os.environ.get("CO_SCIENTIST_UID", "local-dev")
    return State(project_id=pid, owner_uid=uid, backend=InMemoryBackend())


def _build_api_key_state() -> State:
    """Preferred multi-user path: API key → custom token → ID token → Firestore."""
    from .auth import (
        FirebaseAuthClient,
        HttpCustomTokenSignIn,
        exchange_api_key,
    )
    from .backends.firestore import FirestoreBackend

    from .constants import (
        DEFAULT_EXCHANGE_URL_TEMPLATE,
        DEFAULT_FIREBASE_PROJECT_ID,
        DEFAULT_FIREBASE_STORAGE_BUCKET,
        DEFAULT_FIREBASE_WEB_API_KEY,
    )

    api_key = os.environ["CO_SCIENTIST_API_KEY"]
    # Only the API key is user-specific. The Firebase project/bucket/web-key are
    # constants of the hosted service; defaults are baked into constants.py and
    # can be overridden via env (for self-hosted forks).
    fb_project = os.environ.get("FIREBASE_PROJECT_ID", DEFAULT_FIREBASE_PROJECT_ID)
    bucket = os.environ.get("FIREBASE_STORAGE_BUCKET", DEFAULT_FIREBASE_STORAGE_BUCKET)
    web_api_key = os.environ.get("FIREBASE_WEB_API_KEY", DEFAULT_FIREBASE_WEB_API_KEY)
    exchange_url = os.environ.get(
        "CO_SCIENTIST_EXCHANGE_URL",
        DEFAULT_EXCHANGE_URL_TEMPLATE.format(project_id=fb_project),
    )

    # 1. Exchange API key for custom token + project/owner ids
    exch = exchange_api_key(api_key=api_key, exchange_url=exchange_url)
    project_id = exch["projectId"]
    owner_uid = exch["ownerUid"]

    # 2. Custom token → ID token + refresh token
    signin = HttpCustomTokenSignIn().sign_in(exch["customToken"], web_api_key)

    # 3. Auth client seeded with the initial token
    auth_client = FirebaseAuthClient(
        web_api_key=web_api_key,
        refresh_token=signin["refreshToken"],
        initial_id_token=signin["idToken"],
        initial_expires_in=int(signin.get("expiresIn", 3600)),
    )

    # 4. FirestoreBackend authenticated as the user
    backend = FirestoreBackend(
        project_id=fb_project,
        bucket_name=bucket,
        user_token_provider=auth_client.get_id_token,
    )
    return State(project_id=project_id, owner_uid=owner_uid, backend=backend)


def _build_service_account_state() -> State:
    """Developer fallback: service-account JSON, bypasses rules."""
    from .backends.firestore import FirestoreBackend

    pid = os.environ["CO_SCIENTIST_PROJECT_ID"]
    fb_project = os.environ["FIREBASE_PROJECT_ID"]
    bucket = os.environ["FIREBASE_STORAGE_BUCKET"]
    backend = FirestoreBackend(project_id=fb_project, bucket_name=bucket)

    project_doc = backend.get_doc(f"projects/{pid}")
    if project_doc is None:
        raise RuntimeError(
            f"project {pid!r} not found in Firestore. Create it via the dashboard first."
        )
    owner_uid = project_doc.get("owner_uid")
    if not owner_uid:
        raise RuntimeError(f"project {pid!r} has no owner_uid set")
    return State(project_id=pid, owner_uid=owner_uid, backend=backend)


def main() -> None:
    if os.environ.get("CO_SCIENTIST_USE_MEMORY") == "1":
        state = _build_dev_state()
        print("co-scientist-local: in-memory (dev mode)", file=sys.stderr)
    elif os.environ.get("CO_SCIENTIST_API_KEY"):
        try:
            state = _build_api_key_state()
        except (KeyError, RuntimeError) as e:
            print(f"co-scientist-local: {e}", file=sys.stderr)
            sys.exit(2)
        print(
            f"co-scientist-local: token-auth, "
            f"project={state.project_id}, owner={state.owner_uid}",
            file=sys.stderr,
        )
    elif os.environ.get("CO_SCIENTIST_PROJECT_ID") and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            state = _build_service_account_state()
        except (KeyError, RuntimeError) as e:
            print(f"co-scientist-local: {e}", file=sys.stderr)
            sys.exit(2)
        print(
            f"co-scientist-local: service-account (developer fallback), "
            f"project={state.project_id}, owner={state.owner_uid}",
            file=sys.stderr,
        )
    else:
        print(
            "co-scientist-local: no credentials.\n"
            "Set CO_SCIENTIST_API_KEY (preferred) and FIREBASE_* env vars,\n"
            "or CO_SCIENTIST_USE_MEMORY=1 for dev mode.",
            file=sys.stderr,
        )
        sys.exit(2)

    mcp = build_mcp(state)
    mcp.run()


if __name__ == "__main__":
    main()
