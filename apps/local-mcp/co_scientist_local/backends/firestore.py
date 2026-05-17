"""Firestore + Cloud Storage backend.

Same interface as InMemoryBackend, so tools cannot tell which is in use.
firebase-admin is lazy-imported so test environments without it still pass.

Initialization:
    backend = FirestoreBackend(
        project_id="my-project",
        bucket_name="my-project.appspot.com",
        credentials_path="/path/to/serviceAccount.json",  # or None for ADC
    )

The local MCP will eventually call this with a Firebase Auth user credential
rather than a service account, so writes are scoped to the user via security
rules. For initial production deploys, service-account auth is fine and
isolation is enforced by always prefixing paths with `users/{uid}/`.
"""
from __future__ import annotations

from .base import Backend, NotFound


class FirestoreBackend(Backend):
    def __init__(
        self,
        project_id: str,
        bucket_name: str,
        credentials_path: str | None = None,
        app_name: str = "co-scientist-local",
    ) -> None:
        # Lazy-import so test deps stay light
        import firebase_admin
        from firebase_admin import credentials as fb_credentials
        from firebase_admin import firestore, storage

        if app_name in firebase_admin._apps:
            app = firebase_admin.get_app(app_name)
        else:
            if credentials_path:
                cred = fb_credentials.Certificate(credentials_path)
            else:
                # Application Default Credentials (gcloud auth / metadata server)
                cred = fb_credentials.ApplicationDefault()
            app = firebase_admin.initialize_app(
                cred,
                {"projectId": project_id, "storageBucket": bucket_name},
                name=app_name,
            )

        self._app = app
        self._db = firestore.client(app=app)
        self._bucket = storage.bucket(name=bucket_name, app=app)

    # --- documents -----------------------------------------------------------

    def get_doc(self, path: str) -> dict | None:
        snap = self._db.document(path).get()
        return snap.to_dict() if snap.exists else None

    def set_doc(self, path: str, data: dict) -> None:
        self._db.document(path).set(data)

    def update_doc(self, path: str, fields: dict) -> None:
        from google.api_core import exceptions as gax_exc
        try:
            self._db.document(path).update(fields)
        except gax_exc.NotFound as e:
            raise NotFound(f"doc not found: {path!r}") from e

    def delete_doc(self, path: str) -> bool:
        ref = self._db.document(path)
        snap = ref.get()
        if not snap.exists:
            return False
        ref.delete()
        return True

    def list_collection(self, path: str) -> list[tuple[str, dict]]:
        col = self._db.collection(path)
        out: list[tuple[str, dict]] = []
        for snap in col.stream():
            out.append((snap.id, snap.to_dict() or {}))
        out.sort(key=lambda kv: kv[0])
        return out

    # --- blobs ---------------------------------------------------------------

    def put_blob(self, path: str, content: bytes | str) -> None:
        blob = self._bucket.blob(path)
        if isinstance(content, str):
            blob.upload_from_string(content, content_type="text/markdown")
        else:
            blob.upload_from_string(content)

    def get_blob(self, path: str) -> bytes | None:
        blob = self._bucket.blob(path)
        if not blob.exists():
            return None
        return blob.download_as_bytes()

    def delete_blob(self, path: str) -> bool:
        blob = self._bucket.blob(path)
        if not blob.exists():
            return False
        blob.delete()
        return True
