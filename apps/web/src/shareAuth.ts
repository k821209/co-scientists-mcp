/**
 * Share-link auth for anonymous paper reviewers.
 *
 * A share link is `/shared/{pid}/{slug}/{shareId}`. The shareId is an
 * unguessable secret. This module:
 *   1. POSTs {pid, slug, shareId} to /exchange_share_token.
 *   2. Gets back a Firebase custom token carrying share_paper claim.
 *   3. signInWithCustomToken on a SECONDARY FirebaseApp (inMemoryPersistence)
 *      so a logged-in owner previewing their own link doesn't get their
 *      main session clobbered.
 *   4. Hands back Firestore + Storage handles authed as the share visitor.
 *
 * The share session is read-only for the paper + create-only for its
 * `reviews` (comments) — enforced by Firestore/Storage security rules
 * against the share_paper claim.
 */
import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import {
  getAuth,
  inMemoryPersistence,
  setPersistence,
  signInWithCustomToken,
} from "firebase/auth";
import { getFirestore, type Firestore } from "firebase/firestore";
import { getStorage, type FirebaseStorage } from "firebase/storage";

import firebaseConfig from "./firebase-config.json";

const EXCHANGE_URL =
  `https://us-central1-${firebaseConfig.projectId}.cloudfunctions.net/exchange_share_token`;

export interface ShareSession {
  app: FirebaseApp;
  db: Firestore;
  storage: FirebaseStorage;
  pid: string;
  slug: string;
  scope: string;
  paperTitle: string | null;
}

const cache = new Map<string, Promise<ShareSession>>();

async function _build(pid: string, slug: string, shareId: string): Promise<ShareSession> {
  const resp = await fetch(EXCHANGE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pid, slug, shareId }),
  });
  if (!resp.ok) {
    let msg = `share link error (${resp.status})`;
    try {
      const j = await resp.json();
      if (j.error) msg = j.error;
    } catch { /* keep generic */ }
    throw new Error(msg);
  }
  const { customToken, scope, paperTitle } =
    (await resp.json()) as { customToken: string; scope: string; paperTitle: string | null };

  // Secondary app — never touches the main dashboard session.
  const appName = `share-${pid}-${slug}`;
  let app = getApps().find((a) => a.name === appName);
  if (!app) app = initializeApp(firebaseConfig, appName);

  const auth = getAuth(app);
  await setPersistence(auth, inMemoryPersistence);
  await signInWithCustomToken(auth, customToken);

  return {
    app,
    db: getFirestore(app),
    storage: getStorage(app),
    pid, slug,
    scope: scope || "comment",
    paperTitle: paperTitle ?? null,
  };
}

/** Exchange a share link for an authed Firestore/Storage session.
 *  Cached per (pid, slug, shareId) for the page's lifetime. */
export function openShareSession(
  pid: string,
  slug: string,
  shareId: string,
): Promise<ShareSession> {
  const key = `${pid}/${slug}/${shareId}`;
  let p = cache.get(key);
  if (!p) {
    p = _build(pid, slug, shareId).catch((e) => {
      cache.delete(key);   // don't cache failures
      throw e;
    });
    cache.set(key, p);
  }
  return p;
}
