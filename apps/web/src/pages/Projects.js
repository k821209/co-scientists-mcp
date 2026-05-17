import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { addDoc, collection, onSnapshot, query, where, } from "firebase/firestore";
import { Folder, Plus, X } from "lucide-react";
import { useAuth } from "@/auth";
import { db } from "@/firebase";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { generateApiKey } from "@/lib/projectKey";
const FREE_TIER_LIMIT = 3;
export function Projects() {
    const { user } = useAuth();
    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showNew, setShowNew] = useState(false);
    useEffect(() => {
        if (!user)
            return;
        const q = query(collection(db, "projects"), where("owner_uid", "==", user.uid));
        const unsub = onSnapshot(q, (snap) => {
            const items = snap.docs
                .map((d) => ({ id: d.id, ...d.data() }))
                .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
            setProjects(items);
            setLoading(false);
        }, (err) => {
            console.error("projects listener:", err);
            setLoading(false);
        });
        return unsub;
    }, [user]);
    const atLimit = projects.length >= FREE_TIER_LIMIT;
    return (_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { className: "flex flex-wrap items-center justify-between gap-3", children: [_jsxs("div", { children: [_jsx("h1", { className: "text-2xl font-bold tracking-tight", children: "Projects" }), _jsxs("p", { className: "text-sm text-muted-foreground", children: [projects.length, "/", FREE_TIER_LIMIT, " on free tier. Each project gets its own MCP, agent, and skill set."] })] }), _jsxs(Button, { onClick: () => setShowNew(true), disabled: atLimit, children: [_jsx(Plus, { className: "mr-2 h-4 w-4" }), "New Project"] })] }), showNew && (_jsx(NewProjectForm, { onCancel: () => setShowNew(false), onCreated: () => setShowNew(false) })), loading ? (_jsx("p", { className: "text-sm text-muted-foreground", children: "Loading\u2026" })) : projects.length === 0 ? (_jsx(Card, { children: _jsxs(CardHeader, { children: [_jsxs(CardTitle, { className: "flex items-center gap-2", children: [_jsx(Folder, { className: "h-4 w-4" }), " No projects yet"] }), _jsx(CardDescription, { children: "Click \"New Project\" to create your first one (e.g. \"Arabidopsis genome\"). Each project gets its own MCP config bundle to download." })] }) })) : (_jsx("div", { className: "grid gap-3 sm:grid-cols-2 lg:grid-cols-3", children: projects.map((p) => (_jsx(Link, { to: `/projects/${p.id}/papers`, children: _jsxs(Card, { className: "h-full transition-colors hover:bg-accent", children: [_jsxs(CardHeader, { children: [_jsxs(CardTitle, { className: "flex items-start gap-2 text-base", children: [_jsx(Folder, { className: "mt-0.5 h-4 w-4 shrink-0" }), _jsx("span", { className: "truncate", children: p.name })] }), p.description && (_jsx(CardDescription, { className: "line-clamp-2", children: p.description }))] }), _jsxs(CardContent, { className: "text-xs text-muted-foreground", children: ["plan: ", p.plan_id || "free", " \u00B7", " ", p.created_at
                                        ? `created ${new Date(p.created_at).toLocaleDateString()}`
                                        : "—"] })] }) }, p.id))) }))] }));
}
function NewProjectForm({ onCancel, onCreated }) {
    const { user } = useAuth();
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const submit = async (e) => {
        e.preventDefault();
        if (!user)
            return;
        setBusy(true);
        setError(null);
        try {
            const now = new Date().toISOString();
            await addDoc(collection(db, "projects"), {
                owner_uid: user.uid,
                name: name.trim(),
                description: description.trim() || null,
                plan_id: "free",
                api_key: generateApiKey(),
                api_key_created_at: now,
                created_at: now,
                updated_at: now,
            });
            onCreated();
        }
        catch (err) {
            setError(err.message);
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsxs(Card, { children: [_jsxs(CardHeader, { className: "flex flex-row items-center justify-between space-y-0", children: [_jsx(CardTitle, { className: "text-base", children: "New Project" }), _jsx(Button, { variant: "ghost", size: "icon", onClick: onCancel, "aria-label": "cancel", children: _jsx(X, { className: "h-4 w-4" }) })] }), _jsx(CardContent, { children: _jsxs("form", { onSubmit: submit, className: "space-y-3", children: [_jsx(Input, { placeholder: "Project name (e.g. Arabidopsis genome)", value: name, onChange: (e) => setName(e.target.value), required: true }), _jsx(Input, { placeholder: "Description (optional)", value: description, onChange: (e) => setDescription(e.target.value) }), _jsx(Button, { type: "submit", disabled: busy || !name.trim(), children: busy ? "Creating…" : "Create project" }), error && _jsx("p", { className: "text-sm text-destructive", children: error })] }) })] }));
}
