"""Firebase Cloud Function: POST /exchange_share_token

Auth broker for anonymous paper-share links. The owner creates a share
doc at /projects/{pid}/papers/{slug}/shares/{shareId}; the shareId is an
unguessable secret embedded in the link. A visitor's browser posts
{pid, slug, shareId} here; if the share is valid (exists, not revoked,
not expired) the function mints a Firebase custom token carrying the
claim `share_paper = "{pid}/{slug}"`. Firestore + Storage rules grant
that claim read access to the one paper and create access to its
`reviews` (comment) subcollection — nothing else.

Flow mirrors /exchange_key (the per-project MCP key exchange).

    Visitor browser            /exchange_share_token            Firestore
        │                            │                              │
        │  POST {pid,slug,shareId}   │                              │
        │ ─────────────────────────► │                              │
        │                            │  get share doc               │
        │                            │ ────────────────────────────►│
        │                            │ ◄──────────────── share doc  │
        │                            │  auth.create_custom_token(    │
        │                            │    ephemeral_uid,             │
        │                            │    {share_paper: pid/slug})   │
        │  { customToken }           │                              │
        │ ◄───────────────────────── │                              │
        │  signInWithCustomToken →   │                              │
        │  read paper, post comments │                              │
"""
from __future__ import annotations

import json
import secrets
import time

try:
    from firebase_admin import auth, firestore, initialize_app
    from firebase_functions import https_fn, options
    initialize_app()
except ImportError:  # pragma: no cover — only runs in Functions runtime
    https_fn = None
    options = None


def _json_response(payload: dict, status: int = 200):
    return https_fn.Response(
        json.dumps(payload),
        status=status,
        headers={"Content-Type": "application/json"},
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


if https_fn is not None:  # pragma: no cover

    @https_fn.on_request(
        memory=options.MemoryOption.MB_256,
        timeout_sec=30,
        cors=options.CorsOptions(cors_origins=["*"], cors_methods=["post", "options"]),
    )
    def exchange_share_token(req: https_fn.Request) -> https_fn.Response:
        if req.method != "POST":
            return _json_response({"error": "POST required"}, status=405)

        try:
            body = req.get_json(silent=True) or {}
        except Exception:
            body = {}
        pid = (body.get("pid") or "").strip()
        slug = (body.get("slug") or "").strip()
        share_id = (body.get("shareId") or "").strip()
        if not (pid and slug and share_id):
            return _json_response(
                {"error": "pid, slug, shareId all required"}, status=400,
            )

        db = firestore.client()
        share_ref = (
            db.collection("projects").document(pid)
              .collection("papers").document(slug)
              .collection("shares").document(share_id)
        )
        snap = share_ref.get()
        if not snap.exists:
            # Constant-ish delay to discourage shareId scanning.
            time.sleep(0.4)
            return _json_response({"error": "invalid share link"}, status=404)

        share = snap.to_dict() or {}
        if share.get("revoked") is True:
            return _json_response({"error": "share link revoked"}, status=403)
        expires_at = share.get("expires_at_ms")
        if isinstance(expires_at, (int, float)) and _now_ms() > expires_at:
            return _json_response({"error": "share link expired"}, status=403)

        # Ephemeral identity — one per link-open. Comments are attributed by
        # the visitor-entered name (reviewer_name), not by uid.
        ephemeral_uid = f"share-{share_id[:8]}-{secrets.token_hex(6)}"
        try:
            custom_token = auth.create_custom_token(
                ephemeral_uid,
                developer_claims={
                    "share_paper": f"{pid}/{slug}",
                    "share_scope": share.get("scope") or "comment",
                },
            )
        except Exception as e:
            return _json_response({"error": f"token mint failed: {e!s}"}, status=500)
        if isinstance(custom_token, bytes):
            custom_token = custom_token.decode("utf-8")

        # Best-effort visit counter.
        try:
            share_ref.update({
                "last_opened_at": firestore.SERVER_TIMESTAMP,
                "open_count": firestore.Increment(1),
            })
        except Exception:
            pass

        return _json_response({
            "customToken": custom_token,
            "pid": pid,
            "slug": slug,
            "scope": share.get("scope") or "comment",
            "paperTitle": share.get("paper_title"),
        })
