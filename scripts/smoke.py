#!/usr/bin/env python3
"""End-to-end smoke test for the co-scientist stack (project-scoped).

Walks through the bidirectional comment loop using real tool calls under
a sentinel project. The project doc is created up-front (simulating what
the /create_project Cloud Function would do in production) and cascade-
deleted at the end so nothing persists in Firestore.

By default uses InMemoryBackend so the script runs without network.

To verify against real Firestore/Storage:
    export GOOGLE_APPLICATION_CREDENTIALS=~/.co-scientist/serviceAccount.json
    export FIREBASE_PROJECT_ID=co-scientist-5af1a
    export FIREBASE_STORAGE_BUCKET=co-scientist-5af1a.firebasestorage.app
    .venv/bin/python scripts/smoke.py

The sentinel project id is `p-smoke-<short-hex>` so it never collides with
real user projects.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "local-mcp"))

from co_scientist_local.backends import InMemoryBackend
from co_scientist_local.state import State
from co_scientist_local.tools import (
    figures, papers, reviews, sections,
)
from co_scientist_local.util import now_iso


_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(text: str, color: str) -> str:
    if not _USE_COLOR:
        return text
    codes = {"green": "32", "red": "31", "yellow": "33", "cyan": "36", "dim": "2"}
    return f"\033[{codes.get(color, '0')}m{text}\033[0m"


def step(n: int, label: str) -> None:
    print(f"  {_c(f'[{n:2d}]', 'cyan')} {label} … ", end="", flush=True)


def ok(detail: str = "") -> None:
    print(_c("OK", "green") + (f"  {_c(detail, 'dim')}" if detail else ""))


def fail(detail: str) -> None:
    print(_c("FAIL", "red") + f"  {detail}")
    raise SystemExit(1)


def build_state() -> tuple[State, str]:
    """Return (state, backend_label).

    Switches to real Firestore + Storage when both FIREBASE_PROJECT_ID and
    FIREBASE_STORAGE_BUCKET are set. Credentials are resolved by firebase-admin
    in this order: GOOGLE_APPLICATION_CREDENTIALS env var; then ADC at
    ~/.config/gcloud/application_default_credentials.json.
    """
    pid = f"p-smoke-{uuid.uuid4().hex[:8]}"
    owner_uid = "smoke-test-user"
    project = os.environ.get("FIREBASE_PROJECT_ID")
    bucket = os.environ.get("FIREBASE_STORAGE_BUCKET")

    if project and bucket:
        from co_scientist_local.backends.firestore import FirestoreBackend
        backend = FirestoreBackend(project_id=project, bucket_name=bucket)
        return State(project_id=pid, owner_uid=owner_uid, backend=backend), f"Firestore[{project}]"

    return State(project_id=pid, owner_uid=owner_uid, backend=InMemoryBackend()), "InMemory"


def create_project_doc(state: State) -> None:
    """Bootstrap the /projects/{pid} doc.

    In production this is done by the /create_project Cloud Function. For the
    smoke we write it directly via the Admin SDK / InMemoryBackend.
    """
    state.backend.set_doc(f"projects/{state.project_id}", {
        "owner_uid": state.owner_uid,
        "name": "smoke test",
        "plan_id": "free",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })


def teardown_project(state: State) -> None:
    """Cascade-delete the project doc and any leftover subcollection docs."""
    # Best-effort: walk known subcollections and delete everything we can find.
    # The papers tools own their cleanup via delete_paper; this catches stray docs.
    try:
        for slug, _ in state.backend.list_collection(state.project_path("papers")):
            papers.delete_paper(state, slug)
    except Exception:
        pass
    state.backend.delete_doc(f"projects/{state.project_id}")


def run() -> None:
    state, label = build_state()
    print(_c("co-scientist smoke test", "cyan"))
    print(f"  backend:    {label}")
    print(f"  project_id: {state.project_id}")
    print(f"  owner_uid:  {state.owner_uid}")
    print()
    t0 = time.time()

    slug = None
    try:
        # 0. Bootstrap project doc
        step(0, "create /projects/{pid} doc")
        create_project_doc(state)
        ok()

        # 1. Create paper
        step(1, "create_paper")
        p = papers.create_paper(
            state, title="Smoke Test Paper", journal="Smoke Journal",
        )
        slug = p["slug"]
        if p["status"] != "draft" or p["owner_uid"] != state.owner_uid:
            fail(f"unexpected paper doc: {p!r}")
        if p.get("project_id") != state.project_id:
            fail(f"paper missing project_id: {p!r}")
        ok(slug)

        # 2. Update introduction
        step(2, "update_section(introduction)")
        s = sections.update_section(
            state, slug, "introduction",
            body="Plants are remarkable photosynthesizers.",
            status="draft",
        )
        if s["word_count"] != 4:
            fail(f"word_count expected 4, got {s['word_count']}")
        ok(f"word_count={s['word_count']}")

        # 3. Add user review
        step(3, "add_review(source='user')")
        r = reviews.add_review(
            state, slug,
            comment="Methods section needs n= for each experiment.",
            section="methods", severity="major",
        )
        review_id = r["id"]
        if r["status"] != "open" or r["source"] != "user":
            fail(f"unexpected review shape: {r!r}")
        ok(f"review {review_id}")

        # 4. List open user reviews
        step(4, "list_reviews(status='open', source='user')")
        listing = reviews.list_reviews(state, slug, status="open", source="user")
        if len(listing) != 1 or listing[0]["id"] != review_id:
            fail(f"expected 1 open user review, got {len(listing)}")
        ok("1 open user review found")

        # 5. Count == 1
        step(5, "count_open_user_comments == 1")
        n = reviews.count_open_user_comments(state, slug)
        if n != 1:
            fail(f"expected 1, got {n}")
        ok()

        # 6. Resolve review
        step(6, "update_review(status='accepted')")
        u = reviews.update_review(
            state, slug, review_id,
            status="accepted",
            response="Added power-analysis details to methods.",
        )
        if u["status"] != "accepted" or u["resolved_at"] is None:
            fail(f"unexpected: {u!r}")
        ok(f"resolved_at={u['resolved_at']}")

        # 7. Count == 0
        step(7, "count_open_user_comments == 0")
        n = reviews.count_open_user_comments(state, slug)
        if n != 0:
            fail(f"expected 0, got {n}")
        ok()

        # 8. Manuscript blob contains section body
        step(8, "get_manuscript blob contains section body")
        text = sections.get_manuscript(state, slug)
        if "Plants are remarkable photosynthesizers." not in text:
            fail("manuscript blob missing section body")
        if "## Introduction" not in text:
            fail("manuscript blob missing section heading")
        ok(f"{len(text)} bytes")

        # 9. Add figure metadata
        step(9, "add_figure metadata-only")
        f = figures.add_figure(
            state, slug,
            figure_number=1, title="Schematic",
            caption="The pipeline at a glance",
        )
        if f["blob_path"] is not None:
            fail(f"blob_path should be None without local_path, got {f['blob_path']!r}")
        lst = figures.list_figures(state, slug)
        if len(lst) != 1:
            fail(f"expected 1 figure, got {len(lst)}")
        ok("figure_number=1")

        # 10. Cleanup paper (subcollections + manuscript blob)
        step(10, "delete_paper cleanup")
        if not papers.delete_paper(state, slug):
            fail("delete_paper returned False on existing paper")
        if papers.list_papers(state):
            fail("papers list non-empty after delete")
        ok("paper gone")
        slug = None

        # 11. Cleanup project doc itself
        step(11, "delete /projects/{pid} doc")
        teardown_project(state)
        if state.backend.get_doc(f"projects/{state.project_id}") is not None:
            fail("project doc still present after teardown")
        ok("project gone")

        dt = (time.time() - t0) * 1000
        print()
        print(_c(f"  All 11 steps passed in {dt:.0f}ms.", "green"))

    finally:
        if slug is not None:
            try:
                papers.delete_paper(state, slug)
            except Exception:
                pass
        try:
            state.backend.delete_doc(f"projects/{state.project_id}")
        except Exception:
            pass


if __name__ == "__main__":
    run()
