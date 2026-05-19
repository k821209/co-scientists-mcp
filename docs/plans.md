# Plans

## Tiers

| Plan | Projects | Image gen quota / month | Notes |
| ---- | -------- | ------------------------ | ----- |
| free        | 3       | 0 (403 from Cloud Function) | Default on sign-up. |
| pro         | unlimited (current honor) | 200 | Promoted by admin (or future: Stripe webhook). |
| enterprise  | unlimited | 2000 | Hand-set by admin. |

Quotas: hardcoded in `apps/cloud-functions/generate-image/main.py:PLAN_QUOTAS`.

## How `plan_id` is read

The Cloud Function (`generate_image`) inspects the caller's `/users/{uid}`
doc with the Firebase Admin SDK and reads `plan_id`. The web dashboard
never gates anything based on plan — only the Cloud Function does. So:

- A free-plan user *can* call `generate_image` from their MCP. The Cloud
  Function returns **403** with a structured body, which the MCP's
  `CloudFunctionImageGenerator` raises as `PermissionError`. The agent
  surfaces this to the user.
- A pro/enterprise user exceeding their monthly quota hits **429**,
  raised as `QuotaExceeded`. Monthly usage is tracked under
  `/users/{uid}/usage/{YYYY-MM}` and incremented atomically.

## Project cap (free tier)

3 projects max. v0 is honor-system on the client (browser checks the count
before letting the user click "Create"). Production hardening would move
this check into a `/create_project` Cloud Function — not done yet.

## Promotion / demotion

Admin tab in the dashboard lets an admin set `plan_id` on any user. Writes
land in `/users/{uid}` and an audit entry appears in `/admin_audit_log/`.
No emails fire on plan changes; the next `generate_image` call from the
user just succeeds (or fails) with the new state.

CLI alternative for bootstrapping:

```bash
python3 scripts/grant_admin.py grant your@email.example
# then go through the dashboard, OR use the Admin SDK manually:
python3 -c "
import firebase_admin; from firebase_admin import auth, firestore
firebase_admin.initialize_app()
db = firestore.client()
db.collection('users').document('<uid>').update({'plan_id': 'pro'})
"
```

## Stripe integration — not done

The plan was a `/stripe_webhook` Cloud Function that listens for
`checkout.session.completed` + `customer.subscription.deleted` and updates
`plan_id` accordingly. Currently a manual admin step.

## Free-tier image generation policy

**Free tier cannot use `generate_image`** through the built-in MCP. The
Cloud Function returns 403 for `plan_id="free"`, and the MCP no longer
provides any in-process fallback (the `CO_SCIENTIST_USE_LOCAL_OPENAI`
backdoor was removed for clarity — a stray `OPENAI_API_KEY` in the
shell shouldn't accidentally enable a paid feature).

Free users who want image generation should wire their own provider
through Claude Code directly (other image-gen MCPs, or Claude Code's
built-in image tools where available). Since Claude Code is what
calls the image generator anyway, the user controls that part — no
work for us. We just don't ship a free-tier path through our service.
