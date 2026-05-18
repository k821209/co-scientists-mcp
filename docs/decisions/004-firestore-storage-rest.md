# ADR 004 — Firebase Storage via REST, not GCS SDK

**Status**: accepted (2026-05)

## Context

The local MCP writes blobs (manuscript.md, figure PNGs, export artifacts)
to Cloud Storage. Initial attempt used `google-cloud-storage`:

```python
from google.cloud.storage import Client
client = Client(credentials=Credentials(token=id_token, ...))
client.bucket(bucket_name).blob(path).upload_from_string(data)
```

This 401'd with "Invalid Credentials". The reason: GCS REST API
(`storage.googleapis.com`) only accepts **GCP OAuth tokens**, not
**Firebase Auth ID tokens**. The MCP is signed in as a Firebase user
with a Firebase ID token — totally different audience.

## Decision

Use the **Firebase Storage REST API** (`firebasestorage.googleapis.com`)
directly via stdlib `urllib`. This endpoint *does* accept Firebase Auth
ID tokens — that's its whole job.

Implementation in `backends/firestore.py` → `_FirebaseStorageBucket`:

```python
class _FirebaseStorageBucket:
    BASE = "https://firebasestorage.googleapis.com/v0/b/"

    def upload(self, path, data, content_type):
        url = f"{self.BASE}{bucket}/o?uploadType=media&name={quote(path, safe='')}"
        req = urllib.request.Request(
            url, data=data,
            headers={
                "Authorization": f"Bearer {self._token_provider()}",
                "Content-Type": content_type,
            },
        )
        urllib.request.urlopen(req).read()
```

Plus matching `download`, `delete`, `get_download_url` methods.

## Consequences

**Pros**:
- Works with Firebase Auth ID tokens directly. No service-account JSON
  needed in production for blob ops.
- Same security model: Firebase Storage rules (`rules.storage`) gate
  access by `request.auth.token.project_id == pid` — same pattern as
  Firestore rules.
- No `google-cloud-storage` dep in the MCP package — smaller install.

**Cons**:
- We re-implement upload/download/delete by hand.
- No multipart upload (we use simple `uploadType=media` only).
  Acceptable: PNG / PDF / .docx are all single-shot.
- Error handling is hand-rolled.

## Service-account mode unchanged

The developer fallback (`GOOGLE_APPLICATION_CREDENTIALS` + Admin SDK
mode) still uses `firebase_admin.storage` which uses the standard
`google-cloud-storage` plumbing under a service-account credential
that *does* speak GCP OAuth. That path is only for smoke tests and
local development.

## Bonus: download URL pattern

Firebase Storage's REST API returns a `downloadTokens` field on upload
which can be inlined into a public-ish URL:

```
https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{path}?alt=media&token={downloadToken}
```

This is the same URL format the Firebase Web SDK's `getDownloadURL()`
returns. We construct it server-side after upload so the Firestore doc
can store the URL and the dashboard can `<img src=…>` directly without
calling Storage SDK from the browser.

`projectAuth.ts` in the web app exchanges the project's API key for a
project-scoped Firebase user inside a *secondary* Firebase app instance
(`inMemoryPersistence` — doesn't touch the dashboard's main session)
and uses that secondary app's Storage SDK to issue authenticated
`getDownloadURL` calls. The session-scoped secondary app means a logged-in
admin user doesn't get cross-project Storage access through some shared
context.
