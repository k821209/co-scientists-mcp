# Comments (selection-anchored)

The dashboard's primary commenting flow is drag-to-select inside the
manuscript view. Each comment lands as a Firestore `review` document
carrying the verbatim selected passage in `anchor_text` so the agent
can identify exactly where the human pointed.

## Data shape

```
/projects/{pid}/papers/{slug}/reviews/{review_id}
{
  source: "user",                    // "user" | "ai" | "external"
  reviewer_name: "User",
  section: "introduction",           // matches the section the selection lived in
  manuscript_ref: "section:introduction",
  severity: "minor",                 // "minor" | "major" | "suggestion"
  status: "open",                    // "open" | "resolved" | "rejected"
  comment: "...",                    // user-authored
  anchor_text: "T2T plant assemblies are now routine",
  response: null,
  created_at: ISO,
  resolved_at: null,
}
```

`anchor_text` is the rendered text the user selected — `selection.toString()`
captured from the browser. Render-only artifacts are stripped at save
time (`stripRenderArtifacts` in `apps/web/src/lib/anchorInjector.ts`):

- ✓ / ⚠ DOI status badges that our markdown renderer adds
- The visible `doi:NNN/PATH` text of an inline DOI link (where source
  has `{doi:NNN/PATH}`)
- Accidentally captured `{doi:…}` / `{fig:N}` / `{tab:N}` tokens
- Whitespace collapsed to single spaces

So `anchor_text` is clean rendered prose, not raw markdown.

## How the inline highlight is built

The Paper page passes every open user comment's `anchor_text` to the
`Markdown` component. Before react-markdown parses the body,
`injectAnchorMarks` wraps each occurrence in literal `<mark>` HTML:

```html
<mark class="cs-anchor-mark" data-review-ids="rev123,rev456">…</mark>
```

`rehype-raw` lets react-markdown render the raw HTML, and our
components.mark renderer paints the yellow background via inline style.

Matching is **tiered** because the markdown source has tokens
(`{doi:…}`, `**bold**`, etc.) that the rendered anchor doesn't:

1. Exact substring
2. Anchor with whitespace runs treated as `[\s*_~`]+` (markdown markers
   allowed between anchor words)
3. Same as (2) plus full `{x:y}` marker tokens allowed in the gap,
   capped at 80 chars to prevent cross-sentence false matches

Stops at the first tier that finds hits, so an exact match never gets
overridden by a permissive regex.

## Overlapping anchors

Two comments anchoring to overlapping passages merge into one `<mark>`
carrying both IDs in `data-review-ids="a,b"`. Visual cues:

- Slightly darker yellow background + amber underline shadow
- `×N` superscript at the end of the highlighted span

Clicking opens `CommentHoverPopover` which shows comment 1 / N with
prev/next chevrons. Resolve/Withdraw drops just that comment and
advances to the next; closes when the last is handled.

## Agent (Claude Code) integration

Each `review` doc's `anchor_text` is the user's exact pointer. When the
agent fetches `list_reviews(slug, status="open")` it gets:

```json
{
  "id": "...",
  "section": "introduction",
  "anchor_text": "T2T plant assemblies are now routine",
  "comment": "expand this claim — cite the actual reference",
  "severity": "minor",
  ...
}
```

The agent should use `anchor_text` to find the exact place in the
manuscript to edit (or add to). After addressing the comment:

```
mcp__co_scientist__update_review(
  slug, review_id,
  status="resolved",
  response="Expanded to include three T2T assemblies (Arabidopsis,
            Tomato, Rice) with DOIs..."
)
```

## Why we don't use the CSS Custom Highlight API

Tried it. Two problems:

1. CSS Custom Highlights aren't DOM elements, so click events can't be
   delegated normally — we'd have to point-in-rect every click against
   the highlight ranges.
2. Tailwind's Preflight reset strips the `<mark>` element's default
   yellow background. The CSS Custom Highlight approach didn't actually
   solve our React-reconciliation issue cleanly either — `Range`
   objects went stale when the underlying text nodes were replaced.

The remark-plugin-with-rehype-raw approach is the simplest robust path:
the `<mark>` is part of React's virtual DOM, survives reconciliation,
and click events work via standard delegation on `mark.cs-anchor-mark`.

## Diagnostic script

When a comment doesn't render an inline highlight:

```bash
GOOGLE_APPLICATION_CREDENTIALS=~/.co-scientist/serviceAccount.json \
  python scripts/inspect_reviews.py <pid> <paper_slug>
```

Prints each review's `anchor_text` and tells you which section body it
matches against (exact / loose / NONE). "NONE" is the failure mode that
indicates either a missing/changed body, a section field mismatch, or
render artifacts in `anchor_text` that the cleaner missed.
