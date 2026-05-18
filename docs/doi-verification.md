# DOI verification (hallucination check)

Two entry points, one Firestore audit log. Either client (agent in Claude
Code, or human in the dashboard) can run a check; both see the same record.

## Why

LLMs invent DOIs. The model writes "the Smith 2024 paper on rice domestication
(doi:10.1234/nature.55555)" and the DOI doesn't exist. Spot-checking every
citation manually is the bottleneck this feature removes.

## Source of truth: CrossRef

Public REST API, no auth, generous rate limits:

- `GET https://api.crossref.org/works/{doi}` → 200 with metadata, or 404.

Both implementations send `User-Agent: co-scientist-…` per CrossRef etiquette
and use 150ms inter-request pacing.

## Verdict categories

| Kind | Meaning | Action |
| ---- | ------- | ------ |
| `resolved`        | DOI exists, stored title shares ≥3 substantive words with CrossRef's title | None — citation is fine |
| `unresolved`      | CrossRef returns 404                           | **HALLUCINATION** — delete or replace |
| `title_mismatch`  | DOI exists but stored title doesn't match CrossRef's (likely wrong paper cited for the DOI) | Accept CrossRef title or delete |
| `missing_doi`     | Reference has no DOI field                     | Add a DOI, then re-verify       |
| `error`           | Transient (network, 5xx)                       | Retry later                     |

Title comparison: lowercases, strips stopwords, counts shared substantive
words ≥3 char. ≥3 shared = match. The `_shared_words()` helper lives in
both `tools/references.py` (Python) and `lib/crossref.ts` (TypeScript).

## Persistence: `verification_findings/`

```
/projects/{pid}/papers/{slug}/verification_findings/{doi_safe_id}
```

`doi_safe_id` is `re.sub(r"[^a-z0-9]+", "_", doi.lower())` — same DOI hashes
to the same doc on every check, so re-running a sync overwrites rather than
appending.

Schema:
```python
{
  "doi": "10.1234/example",
  "kind": "unresolved" | "title_mismatch" | "missing_doi" | "error" | "resolved",
  "source": "registered_ref" | "inline",
  "ref_citation_key": "smith2024",        # if source == registered_ref
  "stored_title": "...",
  "crossref_title": "...",
  "shared_words": 4,
  "message": "...",                       # if kind == error
  "detected_at": "2026-05-18T12:34:56Z",
  "acknowledged": False,
  "acknowledged_at": "2026-05-18T13:00:00Z",
  "acknowledged_by": "agent" | "user-uid",
  "acknowledged_note": "...",
}
```

## Workflow A — agent self-validates

```
# After writing/revising a paper
validate_references(slug)
   ├─ runs CrossRef on every registered reference
   ├─ writes a finding doc per ref (resolved + problems)
   └─ returns {resolved, unresolved, title_mismatch, missing_doi, errors}

# Agent fixes each problem
for each unresolved DOI:
    delete_reference(slug, citation_key) OR
    add_reference_by_doi(slug, real_doi)   # refuses fake DOIs
    acknowledge_finding(slug, doi, note="replaced with real citation")
```

## Workflow B — human in the dashboard

The Paper page's References card has a `[Sync DOIs]` button.

1. Scans:
   - All registered references' DOIs
   - Inline `{doi:…}` patterns in section bodies that aren't yet registered
2. Verifies each against CrossRef (sequential, 150ms pacing).
3. Writes the same finding docs.
4. Per-row actions:
   - Resolved inline → **Register as reference** (auto-derives citation_key,
     upgrades the finding's `source` to `registered_ref`).
   - Title mismatch on registered → **Use CrossRef title** (overwrites
     stored title, deletes the finding).
   - Unresolved or mismatch → **Delete reference** (removes the ref doc
     and its finding).
5. Auto-fills missing fields (title/authors/journal/year) from CrossRef
   for resolved registered references — toggle in modal footer.

## Workflow C — handoff between A and B

The point of persisting findings:

- User clicks Sync DOIs in dashboard → 3 hallucinations flagged → user
  closes browser without fixing.
- Next time the agent runs (potentially days later), `list_verification_findings(slug)`
  returns those 3. Agent surfaces them to the user, fixes them, calls
  `acknowledge_finding` on each.

Guide v2026-05-18c instructs every session to call
`list_verification_findings(slug)` at start for each paper.

## Inline DOI scanning

A `{doi:10.1234/example}` pattern in section text isn't a registered
reference — there's no `references/{key}` doc — but it's still subject
to hallucination. The dashboard scans section bodies for the pattern,
subtracts already-registered DOIs, and queues the remainder for
verification with `source: "inline"`.

The MCP's `validate_references()` doesn't currently scan inline DOIs (it
only iterates `references/` collection). Adding this is a one-line change
in `references.py` if needed — for now the workflow is: agent inserts
inline DOIs while writing, then later registers them via
`add_reference_by_doi` (which automatically verifies) before the manuscript
is considered done.
