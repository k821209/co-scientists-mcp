# ADR 003 — Pro+ only image gen, server-side key

**Status**: accepted (2026-05)

## Context

Two product constraints, from the user:

1. **"the LLM is only done with claude code like harness"** — no
   server-side LLM. Claude Code stays on the user's machine.
2. **"subscription 이 pro 이상만 이미지 생성 쓸수 있게"** — image
   generation is the exception. Server side OK. Pro+ only.
3. **"사용자 자기키를 따로 웹에서 등록하는건 아니지?"** — no
   user-key-management UI on the web side.

Image generation has high inference cost (OpenAI's gpt-image-2 = $0.04-0.16
per image depending on size/quality). Without server-side enforcement,
free-tier abuse would be unbounded.

## Decision

- One Cloud Function `/generate_image` holds the only OpenAI key (Secret
  Manager). Free → 403. Pro/Enterprise → quota check → call OpenAI.
- The MCP's default `image_gen` in API-key mode is
  `CloudFunctionImageGenerator` — calls the function with the user's
  Firebase ID token in the Authorization header.
- Power users can opt out with `CO_SCIENTIST_USE_LOCAL_OPENAI=1` +
  `OPENAI_API_KEY` env var, which switches to `LocalOpenAIImageGenerator`
  (direct OpenAI call, user's bill, no plan check).

## What we explicitly do NOT do

- ❌ Free-tier image gen on the server. They'd need to use their own
  Gemini key via the `image_gen_mode="local"` TOML path.
- ❌ Web UI for users to register an OpenAI key. Constraint 3.
- ❌ Auto-detect `OPENAI_API_KEY` env var → take that path. We had
  this and it bit a user — a stray stale OpenAI key in their shell
  hijacked the cloud route. Now it requires explicit
  `CO_SCIENTIST_USE_LOCAL_OPENAI=1`.

## How gating works

```
generate_image MCP tool
    │
    ▼  CloudFunctionImageGenerator
POST /generate_image
   Authorization: Bearer <user's Firebase ID token>
    │
    ▼  Cloud Function
1. Verify ID token via Admin SDK
2. Lookup /users/{uid}
3. plan_id == 'free' or disabled → 403 {"error": "image_gen_requires_pro"}
4. plan_id == 'pro' → quota = 200/mo;  enterprise → 2000/mo
5. Lookup /users/{uid}/usage/{YYYY-MM}
6. count >= quota → 429 {"error": "monthly_quota_exceeded"}
7. Increment usage atomically (Firestore transaction)
8. Call OpenAI gpt-image-2
9. Return PNG bytes
```

The MCP-side `CloudFunctionImageGenerator` raises:
- 403 → `PermissionError("image_gen_requires_pro")`
- 429 → `QuotaExceeded(...)`
- Other → `RuntimeError`

The agent surfaces these distinctly so the user knows whether to upgrade
or wait until next month.

## Why gpt-image-2 vs imagen-3

- gpt-image-2 has better instruction following for scientific figures
  (charts, labeled diagrams, schematic illustrations).
- imagen-3 is fine for photorealistic content but worse at text rendering.
- Default kept at gpt-image-2. Users can override per-call with `model=`
  argument; LocalGeminiImageGenerator keeps `imagen-3` as its default
  since that's Gemini's correct model id.

## Timeout

OpenAI gpt-image-2 can take 2–4 min for complex prompts. Cloud Run default
was 120s — we hit a 504. Bumped to 300s. MCP client urlopen timeout is
310s so the client receives the Cloud Function's structured 504 rather
than its own timeout.

## Secret hygiene

`OPENAI_API_KEY` in Secret Manager often arrives with a trailing newline
(`gcloud secrets create --data-file` reads the file verbatim, and shell
operations often leave a `\n`). The Cloud Function `.strip()`s the value
before constructing the Bearer header — see the inline comment in
`generate-image/main.py:_call_openai`.

To upload a key without a newline:

```bash
printf '%s' 'sk-proj-…' | gcloud secrets versions add OPENAI_API_KEY --data-file=-
```
