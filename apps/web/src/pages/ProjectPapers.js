import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { collection, doc, onSnapshot, updateDoc } from "firebase/firestore";
import { ArrowLeft, FileText, Copy, Check, Download, KeyRound, RefreshCw, Eye, EyeOff, } from "lucide-react";
import { db } from "@/firebase";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { generateApiKey, maskKey } from "@/lib/projectKey";
const FIREBASE_PROJECT = "co-scientist-5af1a";
const FIREBASE_BUCKET = "co-scientist-5af1a.firebasestorage.app";
const FIREBASE_WEB_API_KEY = "AIzaSyCap5WxY6br-vo-D0l6mIS7uohPxuROz4E";
const INSTRUCTIONS_GIST = "";
function buildMcpJson(_pid, apiKey) {
    // Note: project_id is NOT in env — the MCP gets it from /exchange_key
    // along with owner_uid, so leaking the key only compromises one project.
    return JSON.stringify({
        mcpServers: {
            co_scientist: {
                type: "stdio",
                command: "python3",
                args: ["-m", "co_scientist_local"],
                env: {
                    CO_SCIENTIST_API_KEY: apiKey,
                    FIREBASE_PROJECT_ID: FIREBASE_PROJECT,
                    FIREBASE_STORAGE_BUCKET: FIREBASE_BUCKET,
                    FIREBASE_WEB_API_KEY: FIREBASE_WEB_API_KEY,
                },
            },
        },
    }, null, 2);
}
function buildClaudeMd(project, pid) {
    return `# co-scientist project: ${project.name}

You are assisting on the **${project.name}** project (id: \`${pid}\`).
${project.description ? `\n> ${project.description}\n` : ""}
This directory is wired to a co-scientist MCP server (Firestore-backed)
running on Firebase project \`${FIREBASE_PROJECT}\`. Every paper, section,
review, figure, table, reference, and analysis lives under
\`/projects/${pid}/...\` in Firestore.

## How this project works

A human collaborator views the dashboard at
\`https://${FIREBASE_PROJECT}.web.app/projects/${pid}/papers\` and can leave
inline comments on paragraphs, figures, and claims. Those comments land in
Firestore as \`reviews\` with \`source='user'\`.

When this Claude Code session starts, check for open user comments:

\`\`\`
mcp__co_scientist__list_papers()
\`\`\`

For each paper, run:

\`\`\`
mcp__co_scientist__count_open_user_comments(slug)
\`\`\`

If non-zero, surface to the human and offer \`/paper-revision\` to address them.

## Available skills

- \`/paper-writing [title]\` — create or update manuscript sections
- \`/paper-revision\` — address open user comments (the bidirectional loop)
- \`/paper-review\` — run AI reviewers
- \`/paper-export [docx|tex|pdf]\` — pandoc-based export
- \`/literature-review [topic]\` — search + add references
- \`/analysis-run [name] [command]\` — local or registered-HPC

## Tool surface

The MCP exposes ~60 tools under \`mcp__co_scientist__*\`:

- **papers**: \`create_paper\`, \`list_papers\`, \`get_paper_state\`, \`update_paper\`, \`delete_paper\`
- **sections**: \`get_section\`, \`update_section\`, \`list_sections\`, \`get_manuscript\`
- **reviews/comments**: \`add_review\`, \`list_reviews\`, \`update_review\`, \`count_open_user_comments\`
- **figures**: \`add_figure\`, \`update_figure\`, \`list_figures\`, \`delete_figure\`
- **tables**: \`add_table\`, \`update_table\`, \`list_tables\`, \`delete_table\`
- **references**: \`add_reference\`, \`search_references\`, \`list_references\`
- **analyses**: \`create_analysis\`, \`list_analyses\`, \`record_analysis_run\`, \`launch_local_job\`
- **servers (HPC)**: \`add_server\`, \`server_status\`, \`submit_remote_job\`, \`tail_remote_log\`, \`kill_remote_job\`
- **export**: \`prepare_export\`, \`export_to_path\` (writes to user's disk + uploads to Storage)
- **image gen**: \`generate_image\` (requires subscription or local \`GEMINI_API_KEY\`)

## Citation format

Use inline DOI: \`{doi:10.1234/example}\`. References are auto-managed via
\`mcp__co_scientist__add_reference_by_doi\` and assembled into BibTeX on export.

## Math mode (Pandoc)

Use \`$...$\` (inline) or \`$$...$$\` (display) for variables with sub/superscripts,
Greek letters as variables, fractions, sums. Leave \`n = 69\` / \`q < 0.005\` /
\`α-helix\` as plain text. \`prepare_export\` returns \`math_warnings\` flagging
violations.

## Remote job rule

**Never** launch a long-running remote job via raw \`ssh <alias> "nohup ..."\`.
Use \`mcp__co_scientist__submit_remote_job\` so the run is tracked in
\`analysis_runs\` and visible in the dashboard. The PreToolUse hook (when
installed) hard-blocks the raw form.
`;
}
export function ProjectPapers() {
    const { pid } = useParams();
    const [project, setProject] = useState(null);
    const [papers, setPapers] = useState([]);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        if (!pid)
            return;
        const unsubProject = onSnapshot(doc(db, "projects", pid), (snap) => {
            setProject(snap.data() ?? null);
        });
        const unsubPapers = onSnapshot(collection(db, "projects", pid, "papers"), (snap) => {
            const items = snap.docs
                .map((d) => ({ id: d.id, slug: d.id, ...d.data() }))
                .sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
            setPapers(items);
            setLoading(false);
        }, () => setLoading(false));
        return () => { unsubProject(); unsubPapers(); };
    }, [pid]);
    // Backfill api_key on first view if the project was created before this feature
    useEffect(() => {
        if (!pid || !project)
            return;
        if (!project.api_key) {
            updateDoc(doc(db, "projects", pid), {
                api_key: generateApiKey(),
                api_key_created_at: new Date().toISOString(),
            }).catch((err) => console.error("api_key backfill failed:", err));
        }
    }, [pid, project]);
    if (!pid)
        return null;
    return (_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { children: [_jsxs(Link, { to: "/projects", className: "-ml-3 inline-flex h-9 items-center rounded-md px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground", children: [_jsx(ArrowLeft, { className: "mr-2 h-4 w-4" }), " All projects"] }), _jsx("h1", { className: "mt-2 text-2xl font-bold tracking-tight", children: project?.name || pid }), project?.description && (_jsx("p", { className: "text-sm text-muted-foreground", children: project.description }))] }), _jsx(ConnectClaudeCode, { pid: pid, project: project }), loading ? (_jsx("p", { className: "text-sm text-muted-foreground", children: "Loading papers\u2026" })) : papers.length === 0 ? (_jsx(Card, { children: _jsxs(CardHeader, { children: [_jsx(CardTitle, { children: "No papers yet" }), _jsxs(CardDescription, { children: ["Once Claude Code is connected (see above), say", _jsx("code", { className: "ml-1 bg-muted px-1 py-0.5 text-xs", children: "/paper-writing \"Your paper title\"" }), "and it will appear here."] })] }) })) : (_jsxs("div", { children: [_jsx("h2", { className: "mb-3 text-lg font-semibold", children: "Papers" }), _jsx("div", { className: "grid gap-3 sm:grid-cols-2 lg:grid-cols-3", children: papers.map((p) => (_jsx(Link, { to: `/projects/${pid}/papers/${p.slug}`, children: _jsxs(Card, { className: "h-full transition-colors hover:bg-accent", children: [_jsxs(CardHeader, { children: [_jsxs(CardTitle, { className: "flex items-start gap-2 text-base", children: [_jsx(FileText, { className: "mt-0.5 h-4 w-4 shrink-0" }), _jsx("span", { className: "truncate", children: p.title })] }), _jsxs(CardDescription, { className: "flex flex-wrap items-center gap-2", children: [p.journal && _jsx("span", { children: p.journal }), p.status && (_jsx(Badge, { variant: "secondary", className: "text-[10px]", children: p.status }))] })] }), p.updated_at && (_jsxs(CardContent, { className: "text-xs text-muted-foreground", children: ["updated ", new Date(p.updated_at).toLocaleString()] }))] }) }, p.id))) })] }))] }));
}
function ConnectClaudeCode({ pid, project }) {
    const [showKey, setShowKey] = useState(false);
    const [rotating, setRotating] = useState(false);
    const apiKey = project?.api_key || "";
    const mcp = apiKey ? buildMcpJson(pid, apiKey) : "";
    const claudeMd = project ? buildClaudeMd(project, pid) : "";
    const rotateKey = async () => {
        if (!confirm("Rotate API key? Any existing .mcp.json with the old key will stop working."))
            return;
        setRotating(true);
        try {
            await updateDoc(doc(db, "projects", pid), {
                api_key: generateApiKey(),
                api_key_created_at: new Date().toISOString(),
            });
        }
        catch (err) {
            alert(`Rotate failed: ${err.message}`);
        }
        finally {
            setRotating(false);
        }
    };
    const downloadFile = (filename, content, mime) => {
        const blob = new Blob([content], { type: mime });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    };
    return (_jsxs(Card, { children: [_jsxs(CardHeader, { children: [_jsx(CardTitle, { className: "text-base", children: "Connect Claude Code to this project" }), _jsxs(CardDescription, { children: ["Project ID: ", _jsx("code", { className: "text-xs", children: pid }), INSTRUCTIONS_GIST && (_jsxs(_Fragment, { children: [" · ", _jsx("a", { className: "underline", href: INSTRUCTIONS_GIST, children: "view setup as text" })] }))] })] }), _jsxs(CardContent, { className: "space-y-5", children: [_jsxs("div", { children: [_jsxs("h4", { className: "mb-2 flex items-center gap-2 text-sm font-semibold", children: [_jsx(KeyRound, { className: "h-4 w-4" }), " Project API key"] }), _jsxs("p", { className: "mb-2 text-xs text-muted-foreground", children: ["Identifies this project to the MCP. Stored on the project doc, readable only by you. Future: validated server-side via ", _jsx("code", { className: "text-[10px]", children: "/exchange_key" }), " Cloud Function."] }), _jsxs("div", { className: "flex flex-wrap items-center gap-2", children: [_jsx("code", { className: "flex-1 min-w-0 truncate rounded-md border bg-muted/50 px-3 py-2 text-xs", children: apiKey ? (showKey ? apiKey : maskKey(apiKey)) : "generating…" }), _jsx(Button, { size: "icon", variant: "outline", onClick: () => setShowKey(!showKey), title: showKey ? "Hide" : "Show", "aria-label": "toggle visibility", children: showKey ? _jsx(EyeOff, { className: "h-3.5 w-3.5" }) : _jsx(Eye, { className: "h-3.5 w-3.5" }) }), _jsx(CopyButton, { value: apiKey, disabled: !apiKey, label: "Copy key" }), _jsxs(Button, { size: "sm", variant: "outline", onClick: rotateKey, disabled: rotating || !apiKey, children: [_jsx(RefreshCw, { className: `mr-1 h-3.5 w-3.5 ${rotating ? "animate-spin" : ""}` }), "Rotate"] })] })] }), _jsxs(Step, { n: 1, title: "Install the local MCP (one-time)", children: [_jsx("p", { className: "mb-2 text-sm text-muted-foreground", children: "Clone the repo (gives you the source \u2014 useful for editing skills, hooks, tools) and install in editable mode:" }), _jsx(CodeBlock, { value: `git clone https://github.com/k821209/co-scientists-mcp.git ~/co-scientists-mcp
pip install -e ~/co-scientists-mcp/apps/local-mcp` }), _jsxs("p", { className: "mt-2 text-xs text-muted-foreground", children: ["One-line pip-only alternative (no source clone):", _jsx("br", {}), _jsx("code", { className: "text-[10px]", children: "pip install \"git+https://github.com/k821209/co-scientists-mcp.git#subdirectory=apps/local-mcp\"" })] })] }), _jsx(Step, { n: 2, title: "Drop these two files into your project directory", children: _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "flex flex-wrap items-center gap-2", children: [_jsxs("p", { className: "flex-1 text-sm text-muted-foreground", children: [_jsx("code", { className: "text-xs", children: ".mcp.json" }), " \u2014 wires up the MCP with your project's API key. The MCP auto-exchanges the key for a project-scoped Firebase token, so no service-account JSON is needed."] }), _jsxs(Button, { size: "sm", variant: "outline", disabled: !apiKey, onClick: () => downloadFile(".mcp.json", mcp, "application/json"), children: [_jsx(Download, { className: "mr-2 h-4 w-4" }), " Download .mcp.json"] })] }), apiKey && _jsx(CodeBlock, { value: mcp }), _jsxs("div", { className: "flex flex-wrap items-center gap-2", children: [_jsxs("p", { className: "flex-1 text-sm text-muted-foreground", children: [_jsx("code", { className: "text-xs", children: "CLAUDE.md" }), " \u2014 project-aware instructions Claude Code auto-loads"] }), _jsxs(Button, { size: "sm", variant: "outline", disabled: !project, onClick: () => downloadFile("CLAUDE.md", claudeMd, "text/markdown"), children: [_jsx(Download, { className: "mr-2 h-4 w-4" }), " Download CLAUDE.md"] })] })] }) }), _jsxs(Step, { n: 3, title: "Open Claude Code in that directory", children: [_jsx(CodeBlock, { value: `cd /path/to/your/project\nclaude` }), _jsxs("p", { className: "mt-2 text-xs text-muted-foreground", children: ["Claude Code will auto-load ", _jsx("code", { children: "CLAUDE.md" }), " + launch the MCP. Try", " ", _jsx("code", { className: "bg-muted px-1 py-0.5 text-xs", children: "/paper-writing \"Your paper title\"" }), " ", "and watch this page update live."] })] })] })] }));
}
function Step({ n, title, children }) {
    return (_jsxs("div", { children: [_jsxs("h4", { className: "mb-2 flex items-center gap-2 text-sm font-semibold", children: [_jsx("span", { className: "inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] text-primary-foreground", children: n }), title] }), _jsx("div", { className: "ml-7", children: children })] }));
}
function CodeBlock({ value }) {
    const [copied, setCopied] = useState(false);
    const copy = async () => {
        try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        }
        catch {
            /* clipboard blocked */
        }
    };
    return (_jsxs("div", { className: "group relative mt-2", children: [_jsx("pre", { className: "overflow-x-auto rounded-md border bg-muted/50 p-3 text-xs leading-relaxed", children: value }), _jsx(Button, { size: "sm", variant: "ghost", onClick: copy, className: "absolute right-1.5 top-1.5 h-7 w-7 p-0 opacity-0 group-hover:opacity-100", "aria-label": "copy", children: copied ? _jsx(Check, { className: "h-3.5 w-3.5" }) : _jsx(Copy, { className: "h-3.5 w-3.5" }) })] }));
}
function CopyButton({ value, disabled, label }) {
    const [copied, setCopied] = useState(false);
    const copy = async () => {
        if (!value)
            return;
        try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        }
        catch { }
    };
    return (_jsxs(Button, { size: "sm", variant: "outline", onClick: copy, disabled: disabled, children: [copied ? _jsx(Check, { className: "mr-1 h-3.5 w-3.5" }) : _jsx(Copy, { className: "mr-1 h-3.5 w-3.5" }), label] }));
}
