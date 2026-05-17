"""Firebase Cloud Function (gen2) — POST /generate_image.

The ONLY server-side AI surface in the system. **Subscription Pro+ only.**

Flow:
  1. Validates the Firebase ID token (request.auth.uid).
  2. Looks up /users/{uid}.plan_id; if 'free' or 'disabled', returns 403.
  3. Looks up monthly usage at /usage/{uid}/monthly/{YYYYMM}; if at limit, 429.
  4. Calls the configured PROVIDER (default: openai/gpt-image-1; fallback: gemini)
     with the server's API key from Secret Manager.
  5. Uploads PNG bytes to Cloud Storage at users/{uid}/generated/{yyyymm}/{id}.png.
  6. Atomically increments the usage counter.
  7. Returns the PNG bytes (image/png) so the local MCP can store them wherever
     the caller wants (figure / asset).

Plan tiers (hardcoded for v0; future: /plans/{id} docs in Firestore):
    free         → 0 images/month   (blocked with 403)
    pro          → 200 images/month
    enterprise   → 2000 images/month

Provider selection:
    IMAGE_PROVIDER env var: "openai" (default) | "gemini"
    Body field `provider` overrides for a single call.

Deploy:
    firebase functions:secrets:set OPENAI_API_KEY    # paste the key when prompted
    firebase functions:secrets:set GEMINI_API_KEY    # optional, for gemini fallback
    firebase deploy --only functions:generate_image

Secrets bound to the function: OPENAI_API_KEY, GEMINI_API_KEY.
"""
from __future__ import annotations

import base64
import json as _json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

# Firebase Functions gen2 (Python) imports — only available at deploy time.
try:
    from firebase_functions import https_fn, options  # type: ignore
    from firebase_admin import auth, firestore, initialize_app, storage  # type: ignore
    from google.cloud.firestore import Increment  # type: ignore
    initialize_app()
except ImportError:  # pragma: no cover — only runs in Functions runtime
    https_fn = None
    options = None


# ──────────────────────────────────────────────────────────────────────────────
# Hardcoded plan quotas (v0). Move to /plans/{id} Firestore docs later.
# ──────────────────────────────────────────────────────────────────────────────

PLAN_QUOTAS: dict[str, dict[str, int]] = {
    "free":       {"images_per_month": 0},
    "pro":        {"images_per_month": 200},
    "enterprise": {"images_per_month": 2000},
}


def _month_key(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y%m")


def _load_user_plan(db, uid: str) -> tuple[str, dict]:
    """Return (plan_id, quotas dict). Falls back to 'free'."""
    user_snap = db.document(f"users/{uid}").get()
    if not user_snap.exists:
        return "free", PLAN_QUOTAS["free"]
    user = user_snap.to_dict() or {}
    if user.get("disabled"):
        return "disabled", PLAN_QUOTAS["free"]

    expires = user.get("plan_expires_at")
    if expires and expires < datetime.now(timezone.utc).isoformat():
        return "free", PLAN_QUOTAS["free"]

    plan_id = (user.get("plan_id") or "free").lower()
    return plan_id, PLAN_QUOTAS.get(plan_id, PLAN_QUOTAS["free"])


def _check_and_increment_quota(db, uid: str, quotas: dict) -> tuple[bool, str | None]:
    """Atomically check usage < limit and increment. Returns (ok, message)."""
    limit = int(quotas.get("images_per_month", 0))
    if limit <= 0:
        return False, "image generation requires a Pro subscription"

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


# ──────────────────────────────────────────────────────────────────────────────
# Image provider implementations
# ──────────────────────────────────────────────────────────────────────────────

_OPENAI_SIZE_MAP = {
    "1:1": "1024x1024", "square": "1024x1024",
    "16:9": "1536x1024", "3:2": "1536x1024", "landscape": "1536x1024",
    "9:16": "1024x1536", "2:3": "1024x1536", "portrait": "1024x1536",
}


def _call_openai(prompt: str, aspect_ratio: str, model: str | None) -> bytes:
    """Real OpenAI gpt-image-1 call. Returns PNG bytes.

    Uses urllib (no SDK) to keep the function's deploy package small.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in Secret Manager")
    size = _OPENAI_SIZE_MAP.get(aspect_ratio, "1024x1024")
    body = _json.dumps({
        "model": model or "gpt-image-1",
        "prompt": prompt,
        "size": size,
        "n": 1,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = _json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenAI HTTP {e.code}: {err_body}") from e

    item = (payload.get("data") or [{}])[0]
    if "b64_json" in item and item["b64_json"]:
        return base64.b64decode(item["b64_json"])
    if "url" in item and item["url"]:
        with urllib.request.urlopen(item["url"], timeout=120) as r:
            return r.read()
    raise RuntimeError(f"OpenAI response had no image data: {payload!r}")


def _call_gemini(prompt: str, aspect_ratio: str, model: str | None) -> bytes:
    """Optional fallback: Google Gemini image API. Requires GEMINI_API_KEY."""
    import google.generativeai as genai  # type: ignore
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set in Secret Manager")
    genai.configure(api_key=key)
    gen_model = genai.GenerativeModel(model or "imagen-3")
    response = gen_model.generate_content(prompt)
    for part in response.parts:
        if hasattr(part, "inline_data") and getattr(part.inline_data, "data", None):
            return part.inline_data.data
    raise RuntimeError("no image bytes in Gemini response")


def _dispatch_provider(provider: str, prompt: str, aspect_ratio: str, model: str | None) -> bytes:
    provider = (provider or "openai").lower()
    if provider == "openai":
        return _call_openai(prompt, aspect_ratio, model)
    if provider == "gemini":
        return _call_gemini(prompt, aspect_ratio, model)
    raise RuntimeError(f"unknown provider: {provider!r}")


# ──────────────────────────────────────────────────────────────────────────────
# HTTP entrypoint
# ──────────────────────────────────────────────────────────────────────────────

if https_fn is not None:  # pragma: no cover — only at deploy time

    @https_fn.on_request(
        # GEMINI_API_KEY is optional — bind it via deploy if you want the
        # gemini fallback (default provider is openai).
        secrets=["OPENAI_API_KEY"],
        memory=options.MemoryOption.MB_512,
        timeout_sec=120,
    )
    def generate_image(req: https_fn.Request) -> https_fn.Response:
        # 1. Auth
        auth_header = req.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return https_fn.Response(
                _json.dumps({"error": "missing bearer token"}),
                status=401, headers={"Content-Type": "application/json"},
            )
        id_token = auth_header.split(" ", 1)[1]
        try:
            decoded = auth.verify_id_token(id_token)
            uid = decoded["uid"]
        except Exception as e:
            return https_fn.Response(
                _json.dumps({"error": f"invalid token: {e!s}"}),
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
                _json.dumps({"error": "prompt is required"}),
                status=400, headers={"Content-Type": "application/json"},
            )
        aspect_ratio = body.get("aspect_ratio") or "1:1"
        model = body.get("model")
        provider = body.get("provider") or os.environ.get("IMAGE_PROVIDER", "openai")

        # 3. Plan check — Pro+ required
        db = firestore.client()
        plan_id, quotas = _load_user_plan(db, uid)
        if plan_id == "disabled":
            return https_fn.Response(
                _json.dumps({"error": "account disabled"}),
                status=403, headers={"Content-Type": "application/json"},
            )
        if plan_id == "free":
            return https_fn.Response(
                _json.dumps({
                    "error": "image generation requires Pro subscription",
                    "current_plan": plan_id,
                    "upgrade_url": "https://co-scientist-5af1a.web.app/account",
                }),
                status=403, headers={"Content-Type": "application/json"},
            )

        # 4. Quota check + atomic increment
        ok, msg = _check_and_increment_quota(db, uid, quotas)
        if not ok:
            return https_fn.Response(
                _json.dumps({"message": msg, "current_plan": plan_id}),
                status=429, headers={"Content-Type": "application/json"},
            )

        # 5. Provider call
        try:
            png = _dispatch_provider(provider, prompt, aspect_ratio, model)
        except Exception as e:
            # Refund the quota on upstream error (best effort).
            ym = _month_key()
            try:
                db.document(f"usage/{uid}/monthly/{ym}").update(
                    {"images_used": Increment(-1)},
                )
            except Exception:
                pass
            return https_fn.Response(
                _json.dumps({"error": f"image generation failed: {e!s}",
                             "provider": provider}),
                status=502, headers={"Content-Type": "application/json"},
            )

        # 6. Upload to Storage for audit / re-download
        ym = _month_key()
        asset_id = uuid.uuid4().hex[:12]
        blob_path = f"users/{uid}/generated/{ym}/{asset_id}.png"
        bucket = storage.bucket()
        bucket.blob(blob_path).upload_from_string(png, content_type="image/png")

        # 7. Return PNG bytes; local MCP stores them where the caller wants.
        return https_fn.Response(
            png,
            status=200,
            headers={
                "Content-Type": "image/png",
                "X-Asset-Id": asset_id,
                "X-Blob-Path": blob_path,
                "X-Plan-Id": plan_id,
                "X-Provider": provider,
            },
        )
