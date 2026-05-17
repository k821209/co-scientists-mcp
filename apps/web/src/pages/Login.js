import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
export function Login() {
    const { signInGoogle, signInEmail } = useAuth();
    const navigate = useNavigate();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    const handleEmail = async (e) => {
        e.preventDefault();
        setError(null);
        setBusy(true);
        try {
            await signInEmail(email, password);
            navigate("/papers");
        }
        catch (err) {
            setError(err.message);
        }
        finally {
            setBusy(false);
        }
    };
    const handleGoogle = async () => {
        setError(null);
        setBusy(true);
        try {
            await signInGoogle();
            navigate("/papers");
        }
        catch (err) {
            setError(err.message);
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsx("div", { className: "flex min-h-screen items-center justify-center bg-background p-4", children: _jsxs(Card, { className: "w-full max-w-sm", children: [_jsxs(CardHeader, { children: [_jsx(CardTitle, { children: "co-scientist" }), _jsx(CardDescription, { children: "Sign in to access your papers, comments, and analyses." })] }), _jsxs(CardContent, { className: "space-y-4", children: [_jsx(Button, { onClick: handleGoogle, disabled: busy, className: "w-full", variant: "outline", children: "Continue with Google" }), _jsxs("div", { className: "relative", children: [_jsx("div", { className: "absolute inset-0 flex items-center", children: _jsx("span", { className: "w-full border-t" }) }), _jsx("div", { className: "relative flex justify-center text-xs uppercase", children: _jsx("span", { className: "bg-card px-2 text-muted-foreground", children: "Or with email" }) })] }), _jsxs("form", { onSubmit: handleEmail, className: "space-y-3", children: [_jsx(Input, { type: "email", placeholder: "you@plantprofile.net", value: email, onChange: (e) => setEmail(e.target.value), required: true }), _jsx(Input, { type: "password", placeholder: "password", value: password, onChange: (e) => setPassword(e.target.value), required: true }), _jsx(Button, { type: "submit", disabled: busy, className: "w-full", children: "Sign in" })] }), error && _jsx("p", { className: "text-sm text-destructive", children: error })] })] }) }));
}
