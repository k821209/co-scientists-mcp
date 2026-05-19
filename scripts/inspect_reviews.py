"""Quick: dump every paper's reviews so we can see anchor_text contents
and figure out why a particular comment isn't getting an inline highlight.

Usage:
    export GOOGLE_APPLICATION_CREDENTIALS=~/.co-scientist/serviceAccount.json
    python scripts/inspect_reviews.py <pid> <paper_slug>
"""
from __future__ import annotations

import os
import sys

import firebase_admin
from firebase_admin import firestore


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: inspect_reviews.py <pid> <paper_slug>", file=sys.stderr)
        sys.exit(2)
    pid, slug = sys.argv[1], sys.argv[2]
    os.environ.setdefault(
        "GOOGLE_APPLICATION_CREDENTIALS",
        os.path.expanduser("~/.co-scientist/serviceAccount.json"),
    )
    firebase_admin.initialize_app()
    db = firestore.client()

    paper = db.document(f"projects/{pid}/papers/{slug}").get()
    if not paper.exists:
        print(f"paper not found: {pid}/{slug}", file=sys.stderr)
        sys.exit(1)

    # Pull all section bodies so we can search anchor_text against them.
    sections = {}
    for s in db.collection(f"projects/{pid}/papers/{slug}/sections").stream():
        sections[s.id] = (s.to_dict() or {}).get("body") or ""

    print(f"# paper: {pid}/{slug}")
    print(f"# sections: {sorted(sections.keys())}")
    print()

    reviews = list(db.collection(f"projects/{pid}/papers/{slug}/reviews").stream())
    print(f"# {len(reviews)} reviews total")
    print()

    for r in reviews:
        d = r.to_dict() or {}
        print(f"--- review {r.id} ---")
        print(f"  status          : {d.get('status')}")
        print(f"  source          : {d.get('source')}")
        print(f"  section         : {d.get('section')!r}")
        print(f"  manuscript_ref  : {d.get('manuscript_ref')!r}")
        anchor = d.get("anchor_text")
        if not anchor:
            print(f"  anchor_text     : (none)")
            print()
            continue
        print(f"  anchor_text     : {anchor[:120]!r}{'…' if len(anchor) > 120 else ''}")
        # Try matching against every section body
        hits: list[tuple[str, str]] = []
        for sk, body in sections.items():
            if anchor in body:
                hits.append((sk, "exact"))
                continue
            # Whitespace-tolerant match
            import re
            pattern = re.escape(anchor).replace(r"\ ", r"[\s*_~`]+")
            if re.search(pattern, body):
                hits.append((sk, "loose"))
        if hits:
            for sk, kind in hits:
                print(f"  matches         : {sk} ({kind})")
        else:
            print(f"  matches         : NONE — invisible inline")
            print(f"  comment         : {(d.get('comment') or '')[:200]!r}")
        print()


if __name__ == "__main__":
    main()
