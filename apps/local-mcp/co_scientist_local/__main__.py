"""Entry point: `python -m co_scientist_local` or via the console script.

Three startup modes, in priority order:

  1. **Memory** (CO_SCIENTIST_USE_MEMORY=1) — InMemoryBackend, no network.
  2. **Env-var Firestore** (CO_SCIENTIST_PROJECT_ID + GOOGLE_APPLICATION_CREDENTIALS
     set, no ~/.co-scientist/config.toml). v0 demo path: dashboard creates a
     project, user copies its ID into `.mcp.json`'s env. owner_uid is read
     from `/projects/{pid}.owner_uid`.
  3. **Config-file** — full bundle from a downloaded MCP config (refresh_token,
     api key, function URLs). Not yet shipped in v0; falls back to env-var
     Firestore if the file isn't present.
"""
from __future__ import annotations

import os
import sys

from .backends import InMemoryBackend
from .mcp_server import build_mcp
from .state import State


def _build_dev_state() -> State:
    """Lightweight in-memory state for smoke tests / mcp inspector."""
    pid = os.environ.get("CO_SCIENTIST_PROJECT_ID", "dev-project")
    uid = os.environ.get("CO_SCIENTIST_UID", "local-dev")
    return State(project_id=pid, owner_uid=uid, backend=InMemoryBackend())


def _build_env_firestore_state() -> State:
    """v0 demo path: env-var-only Firestore.

    Requires:
        CO_SCIENTIST_PROJECT_ID — the project doc id from the dashboard
        FIREBASE_PROJECT_ID     — the Firebase project (e.g. co-scientist-5af1a)
        FIREBASE_STORAGE_BUCKET — the bucket (e.g. co-scientist-5af1a.firebasestorage.app)
        GOOGLE_APPLICATION_CREDENTIALS — path to a service-account JSON

    Owner uid is fetched from /projects/{pid}.owner_uid at startup so the
    paper docs get the right owner stamp.
    """
    from .backends.firestore import FirestoreBackend

    pid = os.environ["CO_SCIENTIST_PROJECT_ID"]
    fb_project = os.environ["FIREBASE_PROJECT_ID"]
    bucket = os.environ["FIREBASE_STORAGE_BUCKET"]
    backend = FirestoreBackend(project_id=fb_project, bucket_name=bucket)

    project_doc = backend.get_doc(f"projects/{pid}")
    if project_doc is None:
        raise RuntimeError(
            f"project {pid!r} not found in Firestore. Create it via the dashboard first."
        )
    owner_uid = project_doc.get("owner_uid")
    if not owner_uid:
        raise RuntimeError(f"project {pid!r} has no owner_uid set")

    return State(project_id=pid, owner_uid=owner_uid, backend=backend)


def _build_prod_state() -> State:
    """Read full bundle config.toml, wire Firestore + Auth + image gen."""
    from .auth import FirebaseAuthClient
    from .backends.firestore import FirestoreBackend
    from .config import load_and_validate
    from .image_gen import (
        CloudFunctionImageGenerator,
        LocalGeminiImageGenerator,
    )

    cfg = load_and_validate()
    backend = FirestoreBackend(
        project_id=cfg["project_id"],
        bucket_name=cfg["storage_bucket"],
        credentials_path=cfg.get("credentials_path"),
    )
    auth_client = FirebaseAuthClient(
        web_api_key=cfg["web_api_key"],
        refresh_token=cfg["refresh_token"],
    )
    image_gen = None
    mode = cfg.get("image_gen_mode", "disabled")
    if mode == "cloud":
        image_gen = CloudFunctionImageGenerator(
            function_url=cfg["function_urls"]["generate_image"],
            get_id_token=auth_client.get_id_token,
        )
    elif mode == "local":
        image_gen = LocalGeminiImageGenerator(api_key=cfg["gemini_api_key"])
    return State(
        project_id=cfg["co_scientist_project_id"],
        owner_uid=cfg["uid"],
        backend=backend,
        image_gen=image_gen,
    )


def main() -> None:
    if os.environ.get("CO_SCIENTIST_USE_MEMORY") == "1":
        state = _build_dev_state()
        print("co-scientist-local: in-memory backend (dev mode)", file=sys.stderr)
    elif os.environ.get("CO_SCIENTIST_PROJECT_ID") and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            state = _build_env_firestore_state()
        except (KeyError, RuntimeError) as e:
            print(f"co-scientist-local: {e}", file=sys.stderr)
            sys.exit(2)
        print(
            f"co-scientist-local: Firestore[{os.environ['FIREBASE_PROJECT_ID']}], "
            f"project={state.project_id}, owner={state.owner_uid}",
            file=sys.stderr,
        )
    else:
        try:
            state = _build_prod_state()
        except FileNotFoundError as e:
            print(
                f"co-scientist-local: {e}\n"
                "Either set CO_SCIENTIST_PROJECT_ID + FIREBASE_PROJECT_ID + "
                "FIREBASE_STORAGE_BUCKET + GOOGLE_APPLICATION_CREDENTIALS env vars, "
                "or set CO_SCIENTIST_USE_MEMORY=1 for dev mode.",
                file=sys.stderr,
            )
            sys.exit(2)
        except ValueError as e:
            print(f"co-scientist-local: {e}", file=sys.stderr)
            sys.exit(2)

    mcp = build_mcp(state)
    mcp.run()


if __name__ == "__main__":
    main()
