#!/usr/bin/env python3
"""Grant or revoke the `admin: true` Firebase Auth custom claim.

Custom claims are set via the Admin SDK (service-account auth) — there's no
client-side way to bootstrap the first admin. Run this script once with the
project owner's service-account JSON to grant yourself admin; from there
you can manage further admins via the dashboard's Admin panel.

Usage:
    export GOOGLE_APPLICATION_CREDENTIALS=~/.co-scientist/serviceAccount.json
    python scripts/grant_admin.py grant <email>
    python scripts/grant_admin.py revoke <email>
    python scripts/grant_admin.py list
    python scripts/grant_admin.py whoami <email>     # show their current claims

The user must sign out + sign back in to the dashboard after a claim change
(Firebase ID tokens have a 1-hour TTL; new claims appear after refresh).
"""
from __future__ import annotations

import os
import sys

try:
    import firebase_admin
    from firebase_admin import auth, credentials, firestore
except ImportError:
    sys.stderr.write(
        "firebase-admin not installed. Activate the repo venv:\n"
        "  source .venv/bin/activate\n"
    )
    sys.exit(2)


def _init() -> None:
    if firebase_admin._apps:
        return
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if sa_path:
        cred = credentials.Certificate(sa_path)
    else:
        cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)


def _mirror_to_firestore(uid: str, is_admin: bool, added_by: str | None) -> None:
    """Mirror the admin allowlist to /admins/{uid} so security rules and
    audit queries can use Firestore-side checks too."""
    db = firestore.client()
    if is_admin:
        db.collection("admins").document(uid).set({
            "role": "superadmin",
            "added_by": added_by or "bootstrap-script",
            "added_at": firestore.SERVER_TIMESTAMP,
        })
    else:
        db.collection("admins").document(uid).delete()


def grant(email: str) -> None:
    _init()
    user = auth.get_user_by_email(email)
    claims = dict(user.custom_claims or {})
    claims["admin"] = True
    auth.set_custom_user_claims(user.uid, claims)
    _mirror_to_firestore(user.uid, True, added_by=user.email or "bootstrap")
    print(f"✓ Granted admin to {email}")
    print(f"  uid: {user.uid}")
    print(f"  claims: {claims}")
    print("  → User must sign out + sign back in for the new token to carry the claim.")


def revoke(email: str) -> None:
    _init()
    user = auth.get_user_by_email(email)
    claims = dict(user.custom_claims or {})
    claims.pop("admin", None)
    auth.set_custom_user_claims(user.uid, claims)
    _mirror_to_firestore(user.uid, False, added_by=None)
    print(f"✓ Revoked admin from {email}")
    print(f"  remaining claims: {claims}")


def list_admins() -> None:
    _init()
    page = auth.list_users()
    admins = []
    while page:
        for u in page.users:
            if u.custom_claims and u.custom_claims.get("admin") is True:
                admins.append(u)
        page = page.get_next_page()
    if not admins:
        print("(no admins yet — run `grant_admin.py grant <email>` to bootstrap)")
        return
    print(f"Admins ({len(admins)}):")
    for u in admins:
        print(f"  - {u.email}  uid={u.uid}")


def whoami(email: str) -> None:
    _init()
    user = auth.get_user_by_email(email)
    print(f"uid:           {user.uid}")
    print(f"email:         {user.email}")
    print(f"display_name:  {user.display_name}")
    print(f"disabled:      {user.disabled}")
    print(f"custom_claims: {user.custom_claims or {}}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "grant" and len(sys.argv) >= 3:
        grant(sys.argv[2])
    elif cmd == "revoke" and len(sys.argv) >= 3:
        revoke(sys.argv[2])
    elif cmd == "list":
        list_admins()
    elif cmd == "whoami" and len(sys.argv) >= 3:
        whoami(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
