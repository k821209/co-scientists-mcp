import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { addDoc, collection, doc, onSnapshot, orderBy, query, updateDoc, } from "firebase/firestore";
import { ArrowLeft, MessageSquare, CheckCircle2, XCircle, Download, Loader2, } from "lucide-react";
import { db } from "@/firebase";
import { downloadProjectBlobAsText } from "@/projectAuth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
export function Paper() {
    const { pid, slug } = useParams();
    const [paper, setPaper] = useState(null);
    const [sections, setSections] = useState([]);
    const [reviews, setReviews] = useState([]);
    const [downloading, setDownloading] = useState(false);
    const [downloadError, setDownloadError] = useState(null);
    useEffect(() => {
        if (!pid || !slug)
            return;
        const paperRef = doc(db, "projects", pid, "papers", slug);
        const unsubPaper = onSnapshot(paperRef, (snap) => setPaper(snap.data() ?? null));
        const sectionsRef = collection(paperRef, "sections");
        const unsubSec = onSnapshot(query(sectionsRef, orderBy("sort_order")), (snap) => setSections(snap.docs.map((d) => ({ id: d.id, ...d.data() }))));
        const reviewsRef = collection(paperRef, "reviews");
        const unsubRev = onSnapshot(query(reviewsRef, orderBy("created_at", "desc")), (snap) => setReviews(snap.docs.map((d) => ({ id: d.id, ...d.data() }))));
        return () => { unsubPaper(); unsubSec(); unsubRev(); };
    }, [pid, slug]);
    const downloadManuscript = async () => {
        if (!pid || !slug)
            return;
        setDownloading(true);
        setDownloadError(null);
        try {
            const text = await downloadProjectBlobAsText(pid, `projects/${pid}/papers/${slug}/manuscript.md`);
            const blob = new Blob([text], { type: "text/markdown" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${slug}.md`;
            a.click();
            URL.revokeObjectURL(url);
        }
        catch (err) {
            setDownloadError(err.message);
        }
        finally {
            setDownloading(false);
        }
    };
    if (!pid || !slug)
        return null;
    const openComments = reviews.filter((r) => r.status === "open" && r.source === "user");
    return (_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { children: [_jsxs(Link, { to: `/projects/${pid}/papers`, className: "-ml-3 inline-flex h-9 items-center rounded-md px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground", children: [_jsx(ArrowLeft, { className: "mr-2 h-4 w-4" }), " Back to project"] }), _jsx("h1", { className: "mt-2 text-2xl font-bold tracking-tight", children: paper?.title ?? slug }), _jsxs("p", { className: "text-sm text-muted-foreground", children: [paper?.journal ?? "no journal", " \u00B7", " ", _jsx(Badge, { variant: "secondary", className: "text-[10px]", children: paper?.status ?? "draft" })] })] }), _jsxs("div", { className: "grid gap-6 lg:grid-cols-[1fr_320px]", children: [_jsxs(Card, { children: [_jsxs(CardHeader, { className: "flex flex-row items-start justify-between space-y-0", children: [_jsxs("div", { children: [_jsx(CardTitle, { children: "Manuscript" }), _jsxs(CardDescription, { children: [sections.length, " sections \u00B7", " ", sections.reduce((s, x) => s + (x.word_count ?? 0), 0), " words"] })] }), _jsxs(Button, { size: "sm", variant: "outline", onClick: downloadManuscript, disabled: downloading, children: [downloading ? (_jsx(Loader2, { className: "mr-2 h-4 w-4 animate-spin" })) : (_jsx(Download, { className: "mr-2 h-4 w-4" })), downloading ? "Downloading…" : "Download .md"] })] }), _jsxs(CardContent, { children: [sections.map((s) => (_jsx(SectionView, { section: s, pid: pid, paperSlug: slug }, s.id))), !sections.length && (_jsxs("p", { className: "text-sm italic text-muted-foreground", children: ["No sections yet. Create one from Claude Code with", " ", _jsx("code", { className: "bg-muted px-1 py-0.5 text-xs", children: "/paper-writing" }), "."] })), downloadError && (_jsx("p", { className: "mt-2 text-xs text-destructive", children: downloadError }))] })] }), _jsxs("div", { className: "space-y-4", children: [_jsxs(Card, { children: [_jsxs(CardHeader, { children: [_jsxs(CardTitle, { className: "flex items-center gap-2 text-base", children: [_jsx(MessageSquare, { className: "h-4 w-4" }), " Comments", openComments.length > 0 && (_jsxs(Badge, { variant: "warning", className: "ml-auto", children: [openComments.length, " open"] }))] }), _jsx(CardDescription, { children: "Comments here are picked up by Claude Code on its next session." })] }), _jsx(CardContent, { children: _jsx(NewCommentBox, { pid: pid, paperSlug: slug }) })] }), reviews.map((r) => (_jsx(ReviewView, { review: r, pid: pid, paperSlug: slug }, r.id)))] })] })] }));
}
function SectionView({ section, pid, paperSlug }) {
    const [showComment, setShowComment] = useState(false);
    return (_jsxs("div", { className: "group mb-6 border-l-2 border-transparent pl-4 hover:border-accent", children: [_jsxs("div", { className: "mb-2 flex items-center justify-between", children: [_jsx("h3", { className: "font-semibold", children: section.title }), _jsxs("div", { className: "flex items-center gap-2", children: [section.status && (_jsx(Badge, { variant: "outline", className: "text-[10px]", children: section.status })), _jsx(Button, { size: "sm", variant: "ghost", className: "opacity-0 group-hover:opacity-100", onClick: () => setShowComment(!showComment), children: _jsx(MessageSquare, { className: "h-3.5 w-3.5" }) })] })] }), section.body ? (_jsx("p", { className: "whitespace-pre-wrap text-sm leading-relaxed", children: section.body })) : (_jsx("p", { className: "text-sm italic text-muted-foreground", children: "empty" })), showComment && (_jsx("div", { className: "mt-3", children: _jsx(NewCommentBox, { pid: pid, paperSlug: paperSlug, section: section.key }) }))] }));
}
function NewCommentBox({ pid, paperSlug, section }) {
    const [text, setText] = useState("");
    const [severity, setSeverity] = useState("minor");
    const [busy, setBusy] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        if (!text.trim())
            return;
        setBusy(true);
        try {
            const reviewsRef = collection(db, "projects", pid, "papers", paperSlug, "reviews");
            await addDoc(reviewsRef, {
                source: "user",
                reviewer_name: "User",
                section: section ?? null,
                severity,
                status: "open",
                comment: text,
                response: null,
                created_at: new Date().toISOString(),
                resolved_at: null,
            });
            setText("");
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsxs("form", { onSubmit: submit, className: "space-y-2", children: [_jsx(Textarea, { value: text, onChange: (e) => setText(e.target.value), placeholder: section ? `comment on ${section}…` : "general comment…", rows: 3 }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsxs("select", { value: severity, onChange: (e) => setSeverity(e.target.value), className: "h-8 rounded-md border bg-background px-2 text-xs", children: [_jsx("option", { value: "minor", children: "minor" }), _jsx("option", { value: "major", children: "major" }), _jsx("option", { value: "suggestion", children: "suggestion" })] }), _jsx(Button, { type: "submit", size: "sm", disabled: busy || !text.trim(), children: busy ? "…" : "Send" })] })] }));
}
function ReviewView({ review, pid, paperSlug }) {
    const isResolved = review.status !== "open";
    return (_jsx(Card, { children: _jsxs(CardContent, { className: "space-y-2 p-4", children: [_jsxs("div", { className: "flex items-center gap-2 text-xs text-muted-foreground", children: [_jsx(Badge, { variant: review.source === "ai" ? "secondary" : "outline", className: "text-[10px]", children: review.source }), review.section && (_jsx(Badge, { variant: "outline", className: "text-[10px]", children: review.section })), review.severity && (_jsx(Badge, { variant: review.severity === "major" ? "destructive" : "outline", className: "text-[10px]", children: review.severity })), isResolved ? (_jsx(CheckCircle2, { className: "ml-auto h-3.5 w-3.5 text-emerald-500" })) : null] }), _jsx("p", { className: "text-sm", children: review.comment }), review.response && (_jsxs("div", { className: "rounded-md bg-muted p-2 text-xs", children: [_jsx("span", { className: "font-medium", children: "Claude's response: " }), review.response] })), !isResolved && (_jsx("div", { className: "flex gap-2", children: _jsxs(Button, { size: "sm", variant: "ghost", onClick: () => updateDoc(doc(db, "projects", pid, "papers", paperSlug, "reviews", review.id), { status: "rejected", resolved_at: new Date().toISOString() }), children: [_jsx(XCircle, { className: "mr-1 h-3 w-3" }), " Withdraw"] }) }))] }) }));
}
