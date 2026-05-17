import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  GoogleAuthProvider,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut as fbSignOut,
  type User,
} from "firebase/auth";
import { doc, getDoc, setDoc, updateDoc } from "firebase/firestore";
import { auth, db } from "./firebase";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
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
      }
      setLoading(false);
    });
    return unsub;
  }, []);

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
    <AuthContext.Provider value={{ user, loading, isAdmin, signInGoogle, signInEmail, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
