# ADR 001 — No Cloud Run for the MCP

**Status**: accepted (2026-05)

## Context

Original plan: Cloud Run hosts the MCP server, Claude Code talks to it via
HTTP. User authenticates once in the browser → token → sent on every MCP
call → Cloud Run validates → does Firestore writes server-side.

This would mean operating an always-on container, scaling it under load,
maintaining a network protocol, and paying Cloud Run hours.

## Decision

Run the MCP locally on the user's machine. Communicate over stdio
(MCP protocol's default transport — what Claude Code expects anyway).

## Consequences

**Pros**:
- Zero Cloud Run cost.
- No container to keep healthy.
- Authentication uses the same Firebase ID-token plumbing as any other
  Firebase client — no custom server-side session layer.
- Heavy local operations (pandoc export, SSH submit to HPC, image generation
  via user's key) run on the user's machine where they belong.
- The MCP can read local files (`local_path=…` for figure uploads) without
  shipping them over the network first.
- Easier debugging — `python -m co_scientist_local` runs verbatim, no
  Docker rebuild loop.

**Cons**:
- Every user needs `pip install`. We add an installation step.
- Updates require `git pull` + Claude Code restart. Compared to a Cloud Run
  deploy which would be instant for everyone.
- We can't enforce server-side rate limits on MCP tool calls — Firestore
  security rules are the only enforcement boundary.
- Power features that need server-side compute (image gen with a server
  key) require carve-outs — see [003](003-pro-only-image-gen.md).

## What still lives in Cloud Functions

Only two functions, both narrowly scoped:

1. `/exchange_key` — mints custom tokens. Can't run client-side because
   it needs the Admin SDK to call `auth.create_custom_token()`.
2. `/generate_image` — wraps OpenAI gpt-image-2 with plan gating using
   the server's `OPENAI_API_KEY` from Secret Manager. Exists specifically
   because we don't want every Pro user to need their own OpenAI key.

Everything else is either Firestore (rules-enforced) or local.
