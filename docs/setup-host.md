# Setup — self-host

For deploying co-scientist-cloud to your own Firebase project. Targets
someone who's done Firebase deploys before.

Steps that bit me at least once are flagged ⚠.

## 1. Firebase project

```bash
firebase login
firebase projects:create my-co-scientist
firebase use my-co-scientist
```

Enable in the Firebase console:
- Authentication → Sign-in providers → Google + Email/Password
- Firestore → Native mode → pick a region (us-central1 if unsure)
- Storage → ⚠ **click "Get started"** — Storage bucket isn't created
  until you do this manually, even though `firebase init storage` makes
  it look like it should be
- (Optional) Analytics

## 2. Clone + configure

```bash
git clone https://github.com/k821209/co-scientists-mcp.git
cd co-scientists-mcp
```

Patch the constants:

```python
# apps/local-mcp/co_scientist_local/constants.py
DEFAULT_FIREBASE_PROJECT_ID    = "my-co-scientist"
DEFAULT_FIREBASE_STORAGE_BUCKET = "my-co-scientist.firebasestorage.app"
DEFAULT_FIREBASE_WEB_API_KEY   = "AIzaSy…"  # Firebase Console → Project settings → Web API key
```

Frontend Firebase config: `apps/web/src/firebase.ts` — paste your project's
web SDK config (Firebase console → Project settings → Your apps).

`.firebaserc`:
```json
{ "projects": { "default": "my-co-scientist" } }
```

## 3. Deploy infra

```bash
firebase deploy --only firestore:rules,firestore:indexes,storage:rules
firebase deploy --only hosting           # after `cd apps/web && npm run build`
firebase deploy --only functions:exchange-key
firebase deploy --only functions:generate-image
```

## 4. Secrets (for generate_image)

```bash
printf '%s' 'sk-proj-…' \
  | gcloud secrets create OPENAI_API_KEY --data-file=- --project=my-co-scientist
# Optional: GEMINI_API_KEY for the gemini fallback provider
```

⚠ Use `printf '%s'` (no trailing newline). `echo` adds `\n` which breaks
the Authorization header — see the `.strip()` defensive fix in
`apps/cloud-functions/generate-image/main.py`, but better to not need it.

The function definition references the secret via `secrets=["OPENAI_API_KEY"]`;
the Cloud Functions runtime binds it on next deploy.

## 5. IAM grants ⚠

Two roles that aren't auto-granted:

```bash
PROJECT_ID=my-co-scientist
PROJECT_NUM=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"

# (a) Allow exchange_key to mint custom tokens
gcloud iam service-accounts add-iam-policy-binding $COMPUTE_SA \
  --member="serviceAccount:$COMPUTE_SA" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=$PROJECT_ID

# (b) Required API
gcloud services enable iamcredentials.googleapis.com --project=$PROJECT_ID

# (c) Let the public hit the function (Pro gating is inside the function)
gcloud run services add-iam-policy-binding generate-image \
  --member="allUsers" --role="roles/run.invoker" \
  --region=us-central1 --project=$PROJECT_ID
gcloud run services add-iam-policy-binding exchange-key \
  --member="allUsers" --role="roles/run.invoker" \
  --region=us-central1 --project=$PROJECT_ID

# (d) Cloud Run gen2 sometimes pre-validates the Bearer token as a GCP
#     OAuth token before the function sees it. Disable that:
gcloud run services update generate-image \
  --no-invoker-iam-check --region=us-central1 --project=$PROJECT_ID
gcloud run services update exchange-key \
  --no-invoker-iam-check --region=us-central1 --project=$PROJECT_ID
```

## 6. Bootstrap an admin

```bash
python3 scripts/grant_admin.py grant your@email.example
```

Sets the `admin: true` custom claim on the Firebase Auth user + mirrors
to `/admins/{uid}`. Verify with `whoami your@email.example`.

Now the Admin tab in the dashboard works — promote users to Pro, view
audit log, etc.

## 7. Smoke test

```bash
PYTHONPATH=apps/local-mcp python3 scripts/smoke.py
```

Creates `/projects/smoke-test-<hex>/...`, writes a paper + section + review,
verifies round-trip, leaves the data in place (don't bother cleaning unless
you want to). Should print `OK` at the end.

## What you can change vs not

| Thing                          | Safe to change?                             |
| ------------------------------ | ------------------------------------------- |
| Firebase project ID            | Yes — patch constants + firebase.ts        |
| Web API key                    | Yes — public, ships in every Firebase web SDK |
| Storage bucket name            | Yes — patch constants                       |
| Region (us-central1)           | Yes — but match in `firebase.json` for hosting cache |
| `DEFAULT_*_URL_TEMPLATE`       | Yes — but Cloud Functions gen2 URL aliases assume us-central1 |
| Firestore data model           | No — security rules + denormalized fields  |
| Tool names (`mcp__co_scientist__*`) | No — agent prompts hard-code them      |
