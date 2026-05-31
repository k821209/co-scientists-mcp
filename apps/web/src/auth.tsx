import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  GoogleAuthProvider,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut as fbSignOut,
  type User,
} from "firebase/auth";
import { doc, getDoc, onSnapshot, setDoc, updateDoc } from "firebase/firestore";
import { auth, db } from "./firebase";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
  /** plan_id from /users/{uid} — "free" | "pro" | "enterprise". Tracked
   *  live (onSnapshot) so flipping the field in the Firestore console
   *  updates the dashboard without a sign-out / sign-in cycle. */
  planId: string;
  signInGoogle: () => Promise<void>;
  signInEmail: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);


/** Ensure /users/{uid} exists on first sign-in; bump last_login_at on
 *  subsequent sign-ins. The initial doc is plan_id='free' — admin promotes
 *  via Firebase Console (or future: Stripe webhook). */
async function ensureUserDoc(u: User): Promise<void> {
  const ref = doc(db, "users", u.uid);
  const now = new Date().toISOString();
  try {
    const snap = await getDoc(ref);
    if (!snap.exists()) {
      await setDoc(ref, {
        email: u.email ?? null,
        display_name: u.displayName ?? null,
        plan_id: "free",
        plan_started_at: now,
        plan_expires_at: null,
        disabled: false,
        notifications: {},
        created_at: now,
        last_login_at: now,
      });
    } else {
      await updateDoc(ref, { last_login_at: now });
    }
  } catch (err) {
    // Non-fatal: surface to console, the user can still use the app for
    // anything that doesn't require the /users doc (most things).
    console.warn("ensureUserDoc failed:", err);
  }
}


export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [planId, setPlanId] = useState<string>("free");

  useEffect(() => {
    const unsub = auth.onAuthStateChanged(async (u) => {
      setUser(u);
      if (u) {
        // Custom claim `admin: true` is set via Admin SDK from the backend.
        const tokenResult = await u.getIdTokenResult();
        setIsAdmin(tokenResult.claims.admin === true);
        // Self-provision the /users/{uid} doc if missing
        await ensureUserDoc(u);
      } else {
        setIsAdmin(false);
        setPlanId("free");
      }
      setLoading(false);
    });
    return unsub;
  }, []);

  // Live-track the user's plan_id so a Firestore-console flip from
  // free → pro lifts the dashboard's free-tier caps without needing
  // sign-out / sign-in.
  useEffect(() => {
    if (!user) return;
    const ref = doc(db, "users", user.uid);
    const unsub = onSnapshot(
      ref,
      (snap) => {
        const data = snap.data() as { plan_id?: string } | undefined;
        setPlanId(data?.plan_id || "free");
      },
      () => setPlanId("free"),
    );
    return unsub;
  }, [user]);

  const signInGoogle = async () => {
    await signInWithPopup(auth, new GoogleAuthProvider());
  };
  const signInEmail = async (email: string, password: string) => {
    await signInWithEmailAndPassword(auth, email, password);
  };
  const signOut = async () => {
    await fbSignOut(auth);
  };

  return (
    <AuthContext.Provider value={{ user, loading, isAdmin, planId, signInGoogle, signInEmail, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
