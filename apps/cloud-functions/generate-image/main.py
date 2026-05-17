"""Firebase Cloud Function (gen2) — POST /generate_image.

The ONLY server-side AI surface in the system. Subscribed users' local MCP
calls this with a Firebase ID token; the function:
  1. Validates the token (Firebase Auth)
  2. Looks up /users/{uid}.plan_id + plan quotas in Firestore
  3. Looks up /usage/{uid}/monthly/{YYYYMM}.images_used
  4. Refuses with 429 if over quota or plan inactive
  5. Calls Gemini with the server's GEMINI_API_KEY (from Secret Manager)
  6. Uploads PNG bytes to Cloud Storage at
     users/{uid}/generated/{yyyy-mm}/{auto_id}.png
  7. Atomically increments usage counter
  8. Returns the PNG bytes (image/png) so the local MCP can store them
     wherever the user wants (figure / asset).

Deploy:
    firebase deploy --only functions:generate_image

Environment variables / secrets:
    GEMINI_API_KEY (Secret Manager binding)
    GCP_PROJECT, STORAGE_BUCKET (auto-injected by Functions)
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

# Firebase Functions gen2 (Python) imports — only available at deploy time.
# These imports will fail in local CI; that's expected, the file is a
# deployment artifact.
try:
    from firebase_functions import https_fn, options  # type: ignore
    from firebase_admin import auth, firestore, initialize_app, storage  # type: ignore
    from google.cloud.firestore import Increment  # type: ignore
    initialize_app()
except ImportError:  # pragma: no cover — only runs in Functions runtime
    https_fn = None
    options = None


_DEFAULT_MODEL = "imagen-3"


def _month_key(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y%m")


def _load_user_plan(db, uid: str) -> tuple[str, dict]:
    """Return (plan_id, quotas dict). Falls back to 'free' / 0 quotas."""
    user_snap = db.document(f"users/{uid}").get()
    if not user_snap.exists:
        return "free", {"images_per_month": 0}
    user = user_snap.to_dict() or {}
    if user.get("disabled"):
        return "disabled", {"images_per_month": 0}

    # plan_expires_at check
    expires = user.get("plan_expires_at")
    if expires and expires < datetime.now(timezone.utc).isoformat():
        return "free", {"images_per_month": 0}

    plan_id = user.get("plan_id") or "free"
    plan_snap = db.document(f"plans/{plan_id}").get()
    if not plan_snap.exists:
        return plan_id, {"images_per_month": 0}
    plan = plan_snap.to_dict() or {}
    return plan_id, plan.get("quotas") or {"images_per_month": 0}


def _check_and_increment_quota(db, uid: str, quotas: dict) -> tuple[bool, str | None]:
    """Atomically check usage < limit and increment. Returns (ok, message)."""
    limit = int(quotas.get("images_per_month", 0))
    if limit <= 0:
        return False, "image generation is not included in your current plan"

    ym = _month_key()
    usage_ref = db.document(f"usage/{uid}/monthly/{ym}")

    @firestore.transactional
    def txn(transaction):
        snap = usage_ref.get(transaction=transaction)
        used = (snap.to_dict() or {}).get("images_used", 0) if snap.exists else 0
        if used >= limit:
            return False, f"monthly image quota reached ({limit}); resets next month"
        if snap.exists:
            transaction.update(usage_ref, {"images_used": Increment(1)})
        else:
            transaction.set(usage_ref, {
                "images_used": 1,
                "exports_used": 0,
                "deck_compiles_used": 0,
                "reset_at": datetime.now(timezone.utc).isoformat(),
            })
        return True, None

    return txn(db.transaction())


def _call_gemini(prompt: str, aspect_ratio: str, model: str) -> bytes:
    """Real Gemini call. Returns PNG bytes."""
    import google.generativeai as genai  # type: ignore
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    gen_model = genai.GenerativeModel(model)
    response = gen_model.generate_content(prompt)
    for part in response.parts:
        if hasattr(part, "inline_data") and getattr(part.inline_data, "data", None):
            return part.inline_data.data
    raise RuntimeError("no image bytes in Gemini response")


if https_fn is not None:  # pragma: no cover — only at deploy time

    @https_fn.on_request(
        secrets=["GEMINI_API_KEY"],
        memory=options.MemoryOption.MB_512,
        timeout_sec=120,
    )
    def generate_image(req: https_fn.Request) -> https_fn.Response:
        # 1. Auth
        auth_header = req.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return https_fn.Response(
                '{"error": "missing bearer token"}',
                status=401, headers={"Content-Type": "application/json"},
            )
        id_token = auth_header.split(" ", 1)[1]
        try:
            decoded = auth.verify_id_token(id_token)
            uid = decoded["uid"]
        except Exception as e:
            return https_fn.Response(
                f'{{"error": "invalid token: {e!s}"}}',
                status=401, headers={"Content-Type": "application/json"},
            )

        # 2. Body
        try:
            body: dict[str, Any] = req.get_json(silent=True) or {}
        except Exception:
            body = {}
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            return https_fn.Response(
                '{"error": "prompt is required"}',
                status=400, headers={"Content-Type": "application/json"},
            )
        aspect_ratio = body.get("aspect_ratio") or "1:1"
        model = body.get("model") or _DEFAULT_MODEL

        # 3. Plan + quota
        db = firestore.client()
        plan_id, quotas = _load_user_plan(db, uid)
        if plan_id == "disabled":
            return https_fn.Response(
                '{"error": "account disabled"}',
                status=403, headers={"Content-Type": "application/json"},
            )
        ok, msg = _check_and_increment_quota(db, uid, quotas)
        if not ok:
            return https_fn.Response(
                f'{{"message": "{msg}"}}',
                status=429, headers={"Content-Type": "application/json"},
            )

        # 4. Gemini
        try:
            png = _call_gemini(prompt, aspect_ratio, model)
        except Exception as e:
            # Refund the quota on upstream error (best effort)
            ym = _month_key()
            db.document(f"usage/{uid}/monthly/{ym}").update(
                {"images_used": Increment(-1)},
            )
            return https_fn.Response(
                f'{{"error": "image generation failed: {e!s}"}}',
                status=502, headers={"Content-Type": "application/json"},
            )

        # 5. Upload to Storage for audit / re-download
        ym = _month_key()
        asset_id = uuid.uuid4().hex[:12]
        blob_path = f"users/{uid}/generated/{ym}/{asset_id}.png"
        bucket = storage.bucket()
        bucket.blob(blob_path).upload_from_string(png, content_type="image/png")

        # 6. Return PNG bytes (local MCP stores them where the caller wants).
        return https_fn.Response(
            png,
            status=200,
            headers={
                "Content-Type": "image/png",
                "X-Asset-Id": asset_id,
                "X-Blob-Path": blob_path,
                "X-Plan-Id": plan_id,
            },
        )
