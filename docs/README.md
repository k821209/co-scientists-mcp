# co-scientist-cloud docs

Notes for future-me. Optimized for quick re-orientation, not for newcomers.

## Map

- [architecture.md](architecture.md) — components, data flow, security model
- [setup-user.md](setup-user.md) — sign up → first paper
- [setup-host.md](setup-host.md) — self-host from scratch
- [mcp-tools.md](mcp-tools.md) — full MCP tool catalog
- [doi-verification.md](doi-verification.md) — CrossRef hallucination check
- [comments.md](comments.md) — selection-anchored comment flow + inline highlight pipeline
- [plans.md](plans.md) — free / pro / enterprise gating

### Open work items

User-filed todos go in [todo/](todo/). Numbered sequentially; each is a
self-contained proposal with TL;DR + concrete observation + approaches +
acceptance criteria. Closing a todo: move the file to `todo/closed/` and
reference the commit that shipped it. Currently open:
- [001 — Native-language prose in the harness](todo/001_native_language_prose_in_harness.md)
- [002 — Rich slide rendering beyond literal markdown](todo/002_rich_slide_rendering.md) (closed 2026-05-26 — `render_mode="code"`)
- [004 — Design methodology for code slides](todo/004_design_methodology_for_code_slides.md) (partial 2026-05-26 — §D grid + §G design-language doc; §A/B/C/E/F open)

### Architecture decisions (ADRs)

- [001-no-cloud-mcp](decisions/001-no-cloud-mcp.md)
- [002-per-project-api-key](decisions/002-per-project-api-key.md)
- [003-pro-only-image-gen](decisions/003-pro-only-image-gen.md)
- [004-firestore-storage-rest](decisions/004-firestore-storage-rest.md)

## Quick repo map

```
apps/
├── web/                       # Vite + React + TS + Tailwind + shadcn dashboard
├── local-mcp/                 # The MCP — pip-installable, lives at github.com/k821209/co-scientists-mcp
│   └── co_scientist_local/
│       ├── __main__.py        # 3 startup modes (memory / api-key / service-account)
│       ├── mcp_server.py      # FastMCP tool registry (~70 tools)
│       ├── auth.py            # /exchange_key client + ID-token refresh
│       ├── backends/firestore.py  # Dual mode: Admin SDK vs user-token + Storage REST
│       ├── tools/             # one module per resource type
│       └── guide.py           # canonical session guide returned by project_guide()
└── cloud-functions/
    ├── exchange-key/          # csk_… → custom token w/ developer_claims.project_id
    └── generate-image/        # Pro-gated image gen, OpenAI gpt-image-2 default

firestore/
├── rules.firestore            # per-project access via custom claim OR owner_uid
├── rules.storage              # same model for blobs
└── indexes.json               # composite indexes (runs, reviews)

scripts/                       # smoke.py, grant_admin.py
tests/                         # 171 pytests (run with PYTHONPATH=apps/local-mcp)
```

## When something breaks

- "paper not found" → likely the user mixed `.mcp.json` and `CLAUDE.md` from
  two different projects. Have them call `whoami()` to check active pid.
- "no image generator configured" → `_build_api_key_state()` didn't wire
  `state.image_gen`. Should always default to CloudFunctionImageGenerator
  in API-key mode (see [003](decisions/003-pro-only-image-gen.md)).
- "Invalid header value … \\n" → secret has trailing newline. Cloud
  Function already `.strip()`s but re-upload secret without newline:
  `printf '%s' 'sk-…' | gcloud secrets versions add … --data-file=-`.
- 504 on `generate_image` → Cloud Function `timeout_sec` (currently 300).
  Image gen can run 2–4 min on complex prompts.
