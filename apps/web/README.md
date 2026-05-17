# co-scientist-web

Vite + React + TypeScript + Tailwind + shadcn-style components.

## Quick start

```bash
cd apps/web
npm install
npm run dev          # http://localhost:5173
```

Make sure Firebase **Authentication** has at least one sign-in provider
enabled (Email/Password or Google) in the Firebase Console.

## Build

```bash
npm run build
# output → apps/web/dist
firebase deploy --only hosting
```

## Routes

| Path | Description | Auth |
|---|---|---|
| `/login` | Email + Google sign-in | public |
| `/papers` | Live paper list (Firestore listener on `/users/{uid}/papers`) | required |
| `/papers/:slug` | Manuscript + sections + comments | required |
| `/account` | Profile, plan, compute servers | required |
| `/admin` | Admin panel (placeholder) | requires `admin: true` custom claim |

## The comment loop

The dashboard writes to `/users/{uid}/papers/{slug}/reviews/{auto-id}` with
`source: "user"`. Claude Code's local MCP picks these up via
`mcp__co_scientist__list_reviews(slug, status="open", source="user")` and
resolves them with `update_review` — which fires the Firestore listener
back to this dashboard immediately.

## Stack notes

- **shadcn/ui** components are hand-rolled in `src/components/ui/` so the
  scaffold runs without the shadcn CLI. To replace a component with the
  official one later: `npx shadcn@latest add <component>`.
- **Responsive**: mobile-first. Sidebar collapses to hamburger below `md`.
- **No SSR**: static SPA, deployed to Firebase Hosting. Auth happens
  client-side via Firebase Auth.
