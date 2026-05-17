/**
 * Project-scoped Firebase auth for the dashboard.
 *
 * The user signs in to the dashboard with Google → their main Firebase Auth
 * session is Google-OAuth-backed, **no `project_id` claim**. That session is
 * fine for reading Firestore (rules also accept `owner_uid` match) but NOT
 * for reading Storage blobs (Storage rules require the custom claim).
 *
 * To unlock Storage reads we run a SECONDARY Firebase app per project:
 *
 *   1. Read the project's API key from /projects/{pid}.api_key (owner-only
 *      via Firestore rules — only the user themselves can fetch it).
 *   2. Exchange the key via /exchange_key Cloud Function for a Firebase
 *      custom token carrying `project_id`.
 *   3. signInWithCustomToken on a secondary FirebaseApp instance with
 *      **inMemoryPersistence** so the main session/persistence aren't
 *      disturbed.
 *   4. Hand back a Storage handle authenticated for that project.
 *
 * The secondary app is cached per-pid so subsequent reads in the same page
 * session don't re-do the exchange.
 */
import { initializeApp, getApps } from "firebase/app";
import { getAuth, inMemoryPersistence, setPersistence, signInWithCustomToken, } from "firebase/auth";
import { doc, getDoc } from "firebase/firestore";
import { getStorage } from "firebase/storage";
import { db } from "./firebase";
import firebaseConfig from "./firebase-config.json";
const EXCHANGE_URL = `https://us-central1-${firebaseConfig.projectId}.cloudfunctions.net/exchange_key`;
const projectAppCache = new Map();
async function _buildProjectApp(pid) {
    // 1. Get the project's API key (owner-only readable in Firestore rules)
    const snap = await getDoc(doc(db, "projects", pid));
    if (!snap.exists()) {
        throw new Error(`project ${pid} not found`);
    }
    const apiKey = snap.data()?.api_key;
    if (!apiKey) {
        throw new Error(`project ${pid} has no api_key`);
    }
    // 2. Exchange for a Firebase custom token
    const resp = await fetch(EXCHANGE_URL, {
        method: "POST",
        headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
        },
        body: "{}",
    });
    if (!resp.ok) {
        const body = await resp.text();
        throw new Error(`/exchange_key failed (${resp.status}): ${body.slice(0, 200)}`);
    }
    const { customToken } = (await resp.json());
    // 3. Create or reuse a secondary FirebaseApp for this project
    const appName = `proj-${pid}`;
    let app = getApps().find((a) => a.name === appName);
    if (!app) {
        app = initializeApp(firebaseConfig, appName);
    }
    // 4. In-memory persistence so we don't disturb the main session,
    //    then sign in with the custom token.
    const auth = getAuth(app);
    await setPersistence(auth, inMemoryPersistence);
    await signInWithCustomToken(auth, customToken);
    return app;
}
/** Returns a FirebaseStorage handle authenticated for `pid`.
 *
 * Throws if the user is not the project owner (Firestore rule blocks the
 * api_key read) or if /exchange_key rejects the key.
 */
export async function getProjectStorage(pid) {
    let appPromise = projectAppCache.get(pid);
    if (!appPromise) {
        appPromise = _buildProjectApp(pid);
        projectAppCache.set(pid, appPromise);
    }
    try {
        const app = await appPromise;
        return getStorage(app);
    }
    catch (err) {
        // Don't cache failures so retries work
        projectAppCache.delete(pid);
        throw err;
    }
}
/** Convenience: download a Storage blob as text under project-scoped auth. */
export async function downloadProjectBlobAsText(pid, path) {
    const { getBytes, ref } = await import("firebase/storage");
    const storage = await getProjectStorage(pid);
    const bytes = await getBytes(ref(storage, path));
    return new TextDecoder().decode(bytes);
}
