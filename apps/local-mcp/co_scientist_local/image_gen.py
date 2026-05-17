"""Image-generation executor abstraction.

Two production backends:
- **LocalGeminiImageGenerator** — free tier; uses the user's own
  GEMINI_API_KEY via google-generativeai. No quota for us to enforce.
- **CloudFunctionImageGenerator** — subscribed tier; HTTPS POSTs to the
  Firebase Cloud Function at /generate_image, which validates the user's
  Firebase ID token, checks plan + monthly quota in Firestore, calls
  Gemini with the server's key, increments usage, returns PNG bytes.

Architecture note: this is the ONLY server-side AI surface in the system.
Text/LLM agent work stays in Claude Code on the user's machine. See
~/.claude/projects/.../memory/architecture_decisions.md.
"""
from __future__ import annotations

from typing import Callable, Protocol


class QuotaExceeded(Exception):
    """Raised when the Cloud Function returns 429 (monthly image quota hit)."""


class ImageGenerator(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        aspect_ratio: str = "1:1",
        model: str = "imagen-3",
    ) -> bytes:
        """Generate an image. Returns the PNG (or other format) bytes."""
        ...


class LocalGeminiImageGenerator:
    """Free-tier: caller-supplied GEMINI_API_KEY, direct Gemini call.

    Lazy-imports google-generativeai so the package stays optional.
    """

    def __init__(self, *, api_key: str) -> None:
        if not api_key:
            raise ValueError("api_key is required for LocalGeminiImageGenerator")
        self._api_key = api_key

    def generate(
        self,
        *,
        prompt: str,
        aspect_ratio: str = "1:1",
        model: str = "imagen-3",
    ) -> bytes:
        # Lazy import — pip extra `gemini` pulls google-generativeai
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "google-generativeai not installed. Install the [gemini] extra: "
                "pip install 'co-scientist-local[gemini]'"
            ) from e
        genai.configure(api_key=self._api_key)
        gen_model = genai.GenerativeModel(model)
        response = gen_model.generate_content(prompt)  # pragma: no cover
        # Extract PNG bytes from response. Shape varies by SDK version — the
        # caller should treat this as best-effort and fall back gracefully.
        for part in response.parts:
            if hasattr(part, "inline_data") and getattr(part.inline_data, "data", None):
                return part.inline_data.data
        raise RuntimeError("no image bytes in Gemini response")


class CloudFunctionImageGenerator:
    """Subscribed-tier: HTTPS POST to the Firebase Cloud Function."""

    def __init__(
        self,
        *,
        function_url: str,
        get_id_token: Callable[[], str],
    ) -> None:
        self._url = function_url
        self._get_id_token = get_id_token

    def generate(
        self,
        *,
        prompt: str,
        aspect_ratio: str = "1:1",
        model: str = "imagen-3",
    ) -> bytes:
        import requests  # type: ignore
        token = self._get_id_token()
        r = requests.post(
            self._url,
            json={"prompt": prompt, "aspect_ratio": aspect_ratio, "model": model},
            headers={"Authorization": f"Bearer {token}"},
            timeout=90,
        )
        if r.status_code == 429:
            try:
                detail = r.json()
                msg = detail.get("message") or detail.get("error") or "quota exceeded"
            except Exception:
                msg = "quota exceeded"
            raise QuotaExceeded(msg)
        r.raise_for_status()
        return r.content


class FakeImageGenerator:
    """Test image generator.

    Records every call and returns canned PNG bytes. Tests verify both that
    the right arguments were passed AND that the bytes end up in Storage.
    """

    def __init__(self, *, png_bytes: bytes = b"\x89PNG_FAKE") -> None:
        self.calls: list[dict] = []
        self._png = png_bytes
        self._quota_exceeded = False

    def trigger_quota_exceeded(self) -> None:
        """Make subsequent calls raise QuotaExceeded."""
        self._quota_exceeded = True

    def generate(
        self,
        *,
        prompt: str,
        aspect_ratio: str = "1:1",
        model: str = "imagen-3",
    ) -> bytes:
        if self._quota_exceeded:
            raise QuotaExceeded("test-quota-exceeded")
        self.calls.append({
            "prompt": prompt, "aspect_ratio": aspect_ratio, "model": model,
        })
        return self._png
