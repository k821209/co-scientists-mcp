# generate-image Cloud Function

Firebase Functions gen2 HTTP endpoint. Validates a Firebase ID token, checks
the user's plan + monthly image quota, calls Gemini with the server's API
key (from Secret Manager), uploads the result to Cloud Storage, and returns
the PNG bytes.

This is the **only** server-side AI surface. All text/LLM work stays in
Claude Code on the user's machine.

## Deploy

```bash
firebase functions:secrets:set GEMINI_API_KEY
firebase deploy --only functions:generate_image
```

## Request

```
POST https://<region>-<project>.cloudfunctions.net/generate_image
Authorization: Bearer <firebase-id-token>
Content-Type: application/json

{ "prompt": "...", "aspect_ratio": "1:1", "model": "imagen-3" }
```

## Response

- `200` — `image/png` bytes, headers `X-Asset-Id`, `X-Blob-Path`, `X-Plan-Id`
- `400` — missing prompt
- `401` — missing/invalid token
- `403` — account disabled
- `429` — `{ "message": "monthly image quota reached..." }`
- `502` — Gemini upstream error (quota refunded)
