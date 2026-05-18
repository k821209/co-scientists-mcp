# co-scientist-cloud

Firebase-based fork of [co-scientist](https://github.com/k821209/co-scientist).

Local MCP for Claude Code + Firestore/Storage + static SPA on Firebase Hosting.
No Cloud Run for the MCP itself, no server-side LLM. Heavy compute stays on
the user's machine or their registered HPC; only image generation (Pro+)
goes through a Cloud Function.

- **Dashboard**: https://co-scientist-5af1a.web.app
- **MCP package**: https://github.com/k821209/co-scientists-mcp (also this repo)

## Docs

See [`docs/`](docs/README.md) for the full map. Quick links:

- [Architecture](docs/architecture.md) — components, data flow, security model
- [Setup (user)](docs/setup-user.md) — sign up → first paper
- [Setup (self-host)](docs/setup-host.md) — deploy from scratch
- [MCP tools](docs/mcp-tools.md) — full ~70-tool catalog
- [DOI verification](docs/doi-verification.md) — CrossRef hallucination check
- [Decisions (ADRs)](docs/decisions/) — why things are the way they are
