# Architecture

## High-level

```
                      ┌─────────────────────────────────┐
                      │  Firebase project co-scientist- │
                      │             5af1a               │
                      ├─────────────────────────────────┤
                      │  Auth          (Google + email) │
                      │  Firestore     (per-project)    │
                      │  Storage       (manuscript blobs)
                      │  Hosting       (SPA at .web.app)│
                      │  Functions:                     │
                      │    /exchange_key                │
                      │    /generate_image  (Pro+ gate) │
                      │  Secret Manager:                │
                      │    OPENAI_API_KEY               │
                      └────────┬─────────────┬──────────┘
                               │             │
                       custom-token   ID-token (web SDK)
                               │             │
                ┌──────────────▼──┐     ┌────▼─────────────┐
                │  Local MCP      │     │  Browser dashboard│
                │  (python -m     │     │  (Vite SPA at    │
                │   co_scientist_ │     │   .web.app)      │
                │   local)        │     │                  │
                │  spawned by     │     │  - Paper view    │
                │  Claude Code    │     │  - Sync DOIs btn │
                │  via stdio MCP  │     │  - Admin panel   │
                │  protocol       │     │  - Setup tab     │
                └─────────────────┘     └──────────────────┘
                       ▲
                       │ stdin / stdout
                       │
                ┌──────┴──────┐
                │ Claude Code │ (user's machine)
                └─────────────┘
```

## Two clients, one Firestore

The same Firestore project is touched by two unrelated clients:

1. **Local MCP** — Python process spawned by Claude Code. Authenticates via
   a per-project API key (`csk_…`) that `/exchange_key` swaps for a Firebase
   custom token carrying `developer_claims.project_id`. Once signed in,
   the MCP holds an ID token (refreshed via `securetoken.googleapis.com`)
   and writes Firestore + Storage as that authenticated user.
2. **Browser dashboard** — Vite SPA. Standard Firebase Auth flow (Google
   popup or email/password). User's session ID token writes Firestore
   directly.

Both go through the same Firestore security rules. The rules grant access
either by `request.auth.token.project_id == pid` (the MCP path) **or** by
`request.auth.uid == project.owner_uid` looked up via Firestore `get()`
(the dashboard path). Either is sufficient — see
[002-per-project-api-key](decisions/002-per-project-api-key.md).

## Data shape

```
/users/{uid}                              ← profile + plan
/admins/{uid}                             ← mirror of custom-claim admins
/admin_audit_log/{id}                     ← admin actions

/projects/{pid}                           ← project doc (owner_uid, api_key, name)
  /api_keys/{hash}                        ← admin-only key index
  /papers/{slug}                          ← paper doc
    /sections/{key}                       ← section bodies
    /reviews/{id}                         ← inline comments
    /references/{citation_key}            ← bibliography
    /verification_findings/{doi_safe_id}  ← CrossRef verdicts (audit log)
    /figures/{n}                          ← figure metadata
    /tables/{n}
    /analyses/{name}                      ← analysis bundles
      /runs/{run_key}                     ← run execution records
    /assets/{filename}                    ← generic image assets
    /activity_log/{id}                    ← audit feed
    /exports/{id}
    manuscript.md                         ← blob (regenerated on every section update)
  /servers/{alias}                        ← HPC SSH targets

/plans/{plan_id}                          ← public plan catalog
```

The `manuscript.md` blob in Storage is regenerated on every `update_section`
call — it's a denormalized join of all section docs in canonical order.
The dashboard fetches the blob directly (no need to recompose client-side).

## CollectionGroup queries

The Runs tab issues `collectionGroup(db, "runs").where("project_id", "==", pid)`.
The default `/projects/{pid}/{document=**}` rule doesn't match collectionGroup
queries (they have no fixed parent path), so there's a separate
`/{path=**}/runs/{runId}` rule with the same project_id-claim check. Every
run doc is denormalized with `project_id`, `paper_slug`, `analysis_name`
at write time.

## Two compute boundaries

| Where                 | What it does                          |
| --------------------- | ------------------------------------- |
| User's machine        | LLM (Claude Code), MCP, pandoc export, image gen (free tier) |
| User's registered HPC | Long-running analyses (via SSH submit) |
| Firebase Cloud Function | API-key exchange, Pro-gated image gen with server's OpenAI key |
| Firebase Hosting      | Static SPA only                       |

No server-side LLM. No Cloud Run for the MCP itself.
See [001-no-cloud-mcp](decisions/001-no-cloud-mcp.md).

## Image generation routing

```
                          generate_image MCP tool
                                    │
                  ┌─────────────────┴─────────────────┐
              default                          opt-in via
                  │                      CO_SCIENTIST_USE_LOCAL_OPENAI=1
                  ▼                                   │
        CloudFunctionImageGenerator                   ▼
                  │                          LocalOpenAIImageGenerator
                  ▼                          (user's OPENAI_API_KEY,
        /generate_image Cloud Function        user's bill)
                  │
       ┌──────────┼───────────┐
   free → 403   pro → quota   enterprise → quota
                  │
                  ▼
            OpenAI gpt-image-2
            (Secret Manager key)
```

See [003-pro-only-image-gen](decisions/003-pro-only-image-gen.md).

## DOI hallucination check

Two entry points, one Firestore audit log.

```
        Browser "Sync DOIs"             MCP validate_references()
                │                                  │
                └────────┬────────┐    ┌───────────┘
                         ▼        ▼    ▼
                     CrossRef public API
                         │
                         ▼
   /papers/{slug}/verification_findings/{doi_safe_id}
                         │
                         ▼
              MCP list_verification_findings()
              (agent reads what user flagged)
```

See [doi-verification.md](doi-verification.md).
