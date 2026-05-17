import { jsx as _jsx } from "react/jsx-runtime";
import { createContext, useContext, useEffect, useState } from "react";
import { GoogleAuthProvider, signInWithEmailAndPassword, signInWithPopup, signOut as fbSignOut, } from "firebase/auth";
import { auth } from "./firebase";
const AuthContext = createContext(null);
export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [isAdmin, setIsAdmin] = useState(false);
    useEffect(() => {
        const unsub = auth.onAuthStateChanged(async (u) => {
            setUser(u);
            if (u) {
                // Custom claim `admin: true` is set via Admin SDK from the backend.
                const tokenResult = await u.getIdTokenResult();
                setIsAdmin(tokenResult.claims.admin === true);
            }
            else {
                setIsAdmin(false);
            }
            setLoading(false);
        });
        return unsub;
    }, []);
    const signInGoogle = async () => {
        await signInWithPopup(auth, new GoogleAuthProvider());
    };
    const signInEmail = async (email, password) => {
        await signInWithEmailAndPassword(auth, email, password);
    };
    const signOut = async () => {
        await fbSignOut(auth);
    };
    return (_jsx(AuthContext.Provider, { value: { user, loading, isAdmin, signInGoogle, signInEmail, signOut }, children: children }));
}
export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx)
        throw new Error("useAuth must be used inside <AuthProvider>");
    return ctx;
}
