import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useAuth } from "@/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
export function Admin() {
    const { isAdmin } = useAuth();
    if (!isAdmin) {
        return (_jsx(Card, { children: _jsxs(CardHeader, { children: [_jsx(CardTitle, { children: "Admins only" }), _jsxs(CardDescription, { children: ["You don't have the ", _jsx("code", { children: "admin" }), " custom claim on your Firebase user."] })] }) }));
    }
    return (_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { children: [_jsx("h1", { className: "text-2xl font-bold tracking-tight", children: "Admin" }), _jsx("p", { className: "text-sm text-muted-foreground", children: "Manage users, grant subscriptions, view audit log." })] }), _jsxs(Card, { children: [_jsxs(CardHeader, { children: [_jsx(CardTitle, { children: "Coming in next session" }), _jsxs(CardDescription, { children: ["For v0, grant subscriptions by editing ", _jsx("code", { children: "/users/{uid}.plan_id" }), " ", "directly in the Firebase Console."] })] }), _jsx(CardContent, { className: "text-sm text-muted-foreground", children: "Planned screens: Users list with inline plan editor \u00B7 Plans CRUD \u00B7 Audit log feed \u00B7 Bootstrap second admin via Firebase Admin SDK." })] })] }));
}
