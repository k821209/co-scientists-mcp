import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  GoogleAuthProvider,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut as fbSignOut,
  type User,
} from "firebase/auth";
import { auth } from "./firebase";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
  signInGoogle: () => Promise<void>;
  signInEmail: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

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
