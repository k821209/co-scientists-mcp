"""Firebase Cloud Function: POST /exchange_key

The auth broker for per-project MCP credentials. Validates a per-project
API key against /projects/{pid}.api_key, then mints a Firebase custom token
with developer_claims { project_id } so the local MCP can authenticate as
the project owner with security rules enforcing project scope.

Flow:
    Local MCP                  /exchange_key Cloud Function          Firestore
       │                              │                                  │
       │  POST /exchange_key          │                                  │
       │  Authorization: Bearer csk_… │                                  │
       │ ───────────────────────────► │                                  │
       │                              │  query projects where api_key == │
       │                              │ ────────────────────────────────►│
       │                              │  ◄───────────────── project doc  │
       │                              │  auth.create_custom_token(uid,   │
       │                              │      developer_claims={proj_id}) │
       │  { customToken, ... }        │                                  │
       │ ◄─────────────────────────── │                                  │
       │                              │                                  │
       │  exchange custom → ID token  │                                  │
       │  via Identity Toolkit REST   │                                  │
       │                              │                                  │
       │  use ID token for Firestore  │                                  │
       │  + Storage. Rules enforce    │                                  │
       │  request.auth.token.proj_id  │                                  │
       │  == pid.                     │                                  │
"""
from __future__ import annotations

import json
import time

try:
    from firebase_admin import auth, firestore, initialize_app
    from firebase_functions import https_fn, options
    initialize_app()
except ImportError:  # pragma: no cover — only runs in Functions runtime
    https_fn = None
    options = None


_KEY_PREFIX = "csk_"


def _validate_key(db, raw_key: str) -> dict | None:
    """Look up the project whose api_key matches `raw_key`.

    Returns the project doc dict (with `id`) or None if no match.

    NOTE on storage model: v0 stores `api_key` as a plaintext field on the
    project doc, owner-readable via security rules. Production hardening
    moves to /projects/{pid}/api_keys/{hash} with bcrypt-hashed keys.
    """
    if not raw_key or not raw_key.startswith(_KEY_PREFIX):
        return None
    # Equality query on api_key field. Firestore auto-indexes single fields
    # on top-level collections, so no composite index needed.
    snaps = list(db.collection("projects").where("api_key", "==", raw_key).limit(1).get())
    if not snaps:
        return None
    snap = snaps[0]
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    data["id"] = snap.id
    return data


def _json_response(payload: dict, status: int = 200):
    return https_fn.Response(
        json.dumps(payload),
        status=status,
        headers={"Content-Type": "application/json"},
    )


if https_fn is not None:  # pragma: no cover

    @https_fn.on_request(
        memory=options.MemoryOption.MB_256,
        timeout_sec=30,
        cors=options.CorsOptions(cors_origins=["*"], cors_methods=["post", "options"]),
    )
    def exchange_key(req: https_fn.Request) -> https_fn.Response:
        if req.method != "POST":
            return _json_response({"error": "POST required"}, status=405)

        auth_header = req.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _json_response({"error": "missing bearer token"}, status=401)

        raw_key = auth_header.split(" ", 1)[1].strip()
        db = firestore.client()
        project = _validate_key(db, raw_key)
        if project is None:
            # Small constant-time-ish delay to discourage brute-force scanning.
            time.sleep(0.4)
            return _json_response({"error": "invalid api key"}, status=401)

        if project.get("disabled") is True:
            return _json_response({"error": "project disabled"}, status=403)

        pid = project["id"]
        owner_uid = project.get("owner_uid")
        if not owner_uid:
            return _json_response({"error": "project has no owner_uid"}, status=500)

        try:
            custom_token = auth.create_custom_token(
                owner_uid,
                developer_claims={"project_id": pid},
            )
        except Exception as e:
            return _json_response({"error": f"token mint failed: {e!s}"}, status=500)
        if isinstance(custom_token, bytes):
            custom_token = custom_token.decode("utf-8")

        # Best-effort usage tracking. Failure is non-fatal.
        try:
            db.collection("projects").document(pid).update({
                "api_key_last_used_at": firestore.SERVER_TIMESTAMP,
            })
        except Exception:
            pass

        return _json_response({
            "customToken": custom_token,
            "projectId": pid,
            "ownerUid": owner_uid,
        })
