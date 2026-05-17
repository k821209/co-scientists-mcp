import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { doc, onSnapshot } from "firebase/firestore";
import { useAuth } from "@/auth";
import { db } from "@/firebase";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
export function Account() {
    const { user, signOut } = useAuth();
    const [profile, setProfile] = useState(null);
    useEffect(() => {
        if (!user)
            return;
        return onSnapshot(doc(db, "users", user.uid), (snap) => setProfile(snap.data() ?? null));
    }, [user]);
    if (!user)
        return null;
    return (_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { children: [_jsx("h1", { className: "text-2xl font-bold tracking-tight", children: "Account" }), _jsx("p", { className: "text-sm text-muted-foreground", children: "Manage your profile, subscription, and compute servers." })] }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { children: "Profile" }) }), _jsxs(CardContent, { className: "space-y-2 text-sm", children: [_jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-muted-foreground", children: "Email" }), _jsx("span", { children: user.email })] }), _jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-muted-foreground", children: "User ID" }), _jsx("span", { className: "font-mono text-xs", children: user.uid })] }), _jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-muted-foreground", children: "Display name" }), _jsx("span", { children: profile?.display_name ?? user.displayName ?? "—" })] })] })] }), _jsxs(Card, { children: [_jsxs(CardHeader, { children: [_jsx(CardTitle, { children: "Subscription" }), _jsx(CardDescription, { children: "Plan changes are made by an admin \u2014 contact us to upgrade." })] }), _jsxs(CardContent, { className: "space-y-2 text-sm", children: [_jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-muted-foreground", children: "Plan" }), _jsx("span", { children: profile?.plan_id ?? "free" })] }), profile?.plan_expires_at != null && (_jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-muted-foreground", children: "Expires" }), _jsx("span", { children: String(profile.plan_expires_at) })] }))] })] }), _jsx(Card, { children: _jsxs(CardHeader, { children: [_jsx(CardTitle, { children: "Compute servers" }), _jsxs(CardDescription, { children: ["Coming soon \u2014 manage your registered HPC nodes here. For v0 use the MCP tools", _jsx("code", { className: "ml-1 text-xs", children: "add_server" }), " /", _jsx("code", { className: "ml-1 text-xs", children: "list_servers" }), "."] })] }) }), _jsxs(Card, { children: [_jsx(CardHeader, { children: _jsx(CardTitle, { children: "Danger zone" }) }), _jsx(CardContent, { children: _jsx(Button, { variant: "destructive", onClick: signOut, children: "Sign out" }) })] })] }));
}
