# ADR 002 — Per-project API key, not per-user

**Status**: accepted (2026-05)

## Context

The MCP needs to authenticate to Firebase. Two shapes considered:

A. **One user, many projects** — user signs in once, MCP holds a refresh
   token, all of the user's projects are accessible. Switch projects by
   passing a `project_id` argument to every MCP tool call.

B. **One MCP instance per project** — `csk_…` API key stored in
   `.mcp.json`. Key resolves to exactly one project. Switching projects
   means a different MCP child process spawned by Claude Code with a
   different `.mcp.json`.

## Decision

B — per-project API key.

## Why

- Claude Code's `.mcp.json` is per-directory anyway. Users typically
  open Claude Code in a specific project directory; that's already the
  natural scope boundary.
- Single-project state simplifies every tool — `state.project_id` is
  fixed at startup, every path is `projects/{state.project_id}/…`,
  every Firestore write is scoped without parameter passing.
- Security rules can express the per-project boundary cleanly:
  `request.auth.token.project_id == pid`. The key carries that claim,
  granted at exchange time. Stolen keys can only touch their one project.
- The API key is a single short string the user copies once. They never
  see a service-account JSON. They don't manage refresh tokens.

## How the exchange works

```
1. csk_abc123 (in .mcp.json) ──> /exchange_key Cloud Function (Admin SDK)
2. Validate against /projects/{pid}.api_key
3. auth.create_custom_token(owner_uid, developer_claims={"project_id": pid})
4. Return {customToken, projectId, ownerUid} to MCP
5. MCP: signInWithCustomToken via Identity Toolkit → idToken + refreshToken
6. Use idToken for Firestore + Storage REST writes
7. Refresh via securetoken.googleapis.com when within 60s of expiry
```

The custom token carries the `project_id` developer_claim — this becomes
`request.auth.token.project_id` for Firestore rules.

## Free-tier cap (3 projects)

Each new project = one new API key issued. The free-tier 3-project cap
is currently honor-system (client-side check before letting the user
create). Production hardening: `/create_project` Cloud Function that
checks `plan_id` + existing project count before issuing.

## Trade-offs

- **One Claude Code session = one project.** If a user wants to work on
  two projects in parallel, they need two terminal windows with two
  different `.mcp.json` files. This matches actual workflow (one paper
  per terminal tab).
- **Project deletion ≠ key revocation.** Currently nothing rotates keys.
  Project owner can manually `Rotate` from the Setup tab. Adding
  per-key revoked-state checking would be a Cloud Function check on
  every `/exchange_key` call.
- **No "I lost my key" recovery.** Owner can `Rotate` and get a new key;
  old key permanently dead.

## What about per-user refresh tokens?

`developer_claims` from `create_custom_token` only persist into the **first**
ID token issued after sign-in. Subsequent refreshes via the standard refresh
endpoint don't carry developer_claims forward — they'd be dropped. So a
long-lived refresh-token loop loses the `project_id` claim on first refresh.

Workarounds:
1. Re-call `/exchange_key` (which re-mints a fresh custom token) instead
   of using the refresh endpoint. Currently the MCP does standard refresh
   — needs to be patched if sessions ever exceed ~1hr.
2. Use `setCustomUserClaims` to persist `project_id` on the user record.
   But then a user can only ever be one project_id — breaks multi-project.

For now, MCP sessions are short-lived enough that this hasn't bitten.
Logged as a known risk; future fix: re-exchange on near-expiry instead
of refresh.
