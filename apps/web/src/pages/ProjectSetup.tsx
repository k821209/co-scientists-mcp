import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { doc, updateDoc } from "firebase/firestore";
import {
  Copy, Check, Download, KeyRound, RefreshCw, Eye, EyeOff,
} from "lucide-react";
import { db } from "@/firebase";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { generateApiKey, maskKey } from "@/lib/projectKey";
import { type ProjectContext } from "./ProjectShell";

const FIREBASE_PROJECT = "co-scientist-5af1a";

function buildMcpJson(apiKey: string): string {
  // Only the API key is user-specific. Firebase project/bucket/web-key are
  // baked into the co_scientist_local package constants.
  return JSON.stringify(
    {
      mcpServers: {
        co_scientist: {
          type: "stdio",
          command: "python3",
          args: ["-m", "co_scientist_local"],
          env: {
            CO_SCIENTIST_API_KEY: apiKey,
          },
        },
      },
    },
    null,
    2,
  );
}

function buildSetupScript(
  projectSlug: string,
  mcpJson: string,
  claudeMd: string,
): string {
  // Unique heredoc markers so the embedded content can never collide.
  const m1 = "CO_SCIENTIST_MCP_END_" + Math.random().toString(36).slice(2, 10).toUpperCase();
  const m2 = "CO_SCIENTIST_CLAUDE_END_" + Math.random().toString(36).slice(2, 10).toUpperCase();
  return `#!/usr/bin/env bash
# co-scientist setup — drops .mcp.json + CLAUDE.md into the current directory.
# Usage:
#   cd /path/to/your/project
#   bash setup-${projectSlug}.sh
set -euo pipefail

cat > .mcp.json <<'${m1}'
${mcpJson}
${m1}

cat > CLAUDE.md <<'${m2}'
${claudeMd}
${m2}

echo "✓ Wrote .mcp.json + CLAUDE.md to $(pwd)"
echo ""
echo "Next: run 'claude' in this directory."
`;
}


function buildClaudeMd(name: string, description: string | undefined, pid: string): string {
  return `# co-scientist project: ${name}

You are assisting on the **${name}** project (id: \`${pid}\`).
${description ? `\n> ${description}\n` : ""}
This directory is wired to a co-scientist MCP server (Firestore-backed).
Every paper, section, review, figure, table, reference, and analysis lives
under \`/projects/${pid}/...\` in Firestore.

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

If non-zero, surface them and offer \`/paper-revision\` to address them.

## Available skills

- \`/paper-writing [title]\` — create or update manuscript sections
- \`/paper-revision\` — address open user comments (the bidirectional loop)
- \`/paper-review\` — run AI reviewers
- \`/paper-export [docx|tex|pdf]\` — pandoc-based export
- \`/literature-review [topic]\` — search + add references
- \`/analysis-run [name] [command]\` — local or registered-HPC

## Tool surface (~60 tools under mcp__co_scientist__*)

papers · sections · reviews · figures · tables · references · analyses · runs
servers (HPC) · exports · image gen

## Citation format

Inline DOI: \`{doi:10.1234/example}\`. References auto-managed via
\`mcp__co_scientist__add_reference_by_doi\`, assembled into BibTeX on export.

## Math mode (Pandoc)

Use \`$...$\` (inline) or \`$$...$$\` (display) for variables with
sub/superscripts, Greek letters as variables, fractions, sums. Leave
\`n = 69\` / \`q < 0.005\` / \`α-helix\` as plain text. \`prepare_export\` returns
\`math_warnings\` flagging violations.

## Remote job rule

**Never** launch a long-running remote job via raw \`ssh <alias> "nohup ..."\`.
Use \`mcp__co_scientist__submit_remote_job\` so the run is tracked in
\`analysis_runs\` and visible in the dashboard.
`;
}

export function ProjectSetup() {
  const { pid, project } = useOutletContext<ProjectContext>();
  const [showKey, setShowKey] = useState(false);
  const [rotating, setRotating] = useState(false);

  // Backfill api_key on first view if missing (existing projects from before this feature)
  useEffect(() => {
    if (!pid || !project) return;
    if (!project.api_key) {
      updateDoc(doc(db, "projects", pid), {
        api_key: generateApiKey(),
        api_key_created_at: new Date().toISOString(),
      }).catch((err) => console.error("api_key backfill failed:", err));
    }
  }, [pid, project]);

  const apiKey = project?.api_key || "";
  const mcp = apiKey ? buildMcpJson(apiKey) : "";
  const claudeMd = project ? buildClaudeMd(project.name, project.description, pid) : "";
  const projectSlug = project?.name
    ? project.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
    : pid;
  const setupScript = (apiKey && project)
    ? buildSetupScript(projectSlug, mcp, claudeMd)
    : "";

  const rotateKey = async () => {
    if (!confirm("Rotate API key? Any existing .mcp.json with the old key will stop working.")) return;
    setRotating(true);
    try {
      await updateDoc(doc(db, "projects", pid), {
        api_key: generateApiKey(),
        api_key_created_at: new Date().toISOString(),
      });
    } catch (err) {
      alert(`Rotate failed: ${(err as Error).message}`);
    } finally {
      setRotating(false);
    }
  };

  const downloadFile = (filename: string, content: string, mime: string) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Connect Claude Code to this project</CardTitle>
          <CardDescription>
            Project ID: <code className="text-xs">{pid}</code>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">

          {/* API key */}
          <div>
            <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <KeyRound className="h-4 w-4" /> Project API key
            </h4>
            <p className="mb-2 text-xs text-muted-foreground">
              Identifies this project to the MCP. Stored on the project doc, readable only by you.
              Exchanged via the <code className="text-[10px]">/exchange_key</code> Cloud Function
              for a Firebase custom token with the <code className="text-[10px]">project_id</code> claim
              — security rules enforce per-project scope.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <code className="flex-1 min-w-0 truncate rounded-md border bg-muted/50 px-3 py-2 text-xs">
                {apiKey ? (showKey ? apiKey : maskKey(apiKey)) : "generating…"}
              </code>
              <Button size="icon" variant="outline" onClick={() => setShowKey(!showKey)}
                      title={showKey ? "Hide" : "Show"} aria-label="toggle visibility">
                {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </Button>
              <CopyButton value={apiKey} disabled={!apiKey} label="Copy key" />
              <Button size="sm" variant="outline" onClick={rotateKey}
                      disabled={rotating || !apiKey}>
                <RefreshCw className={`mr-1 h-3.5 w-3.5 ${rotating ? "animate-spin" : ""}`} />
                Rotate
              </Button>
            </div>
          </div>

          <Step n={1} title="Install the local MCP (one-time)">
            <p className="mb-2 text-sm text-muted-foreground">
              Clone the repo and install in editable mode:
            </p>
            <CodeBlock value={`git clone https://github.com/k821209/co-scientists-mcp.git ~/co-scientists-mcp
pip install -e ~/co-scientists-mcp/apps/local-mcp`} />
            <p className="mt-2 text-xs text-muted-foreground">
              One-liner pip-only alternative (no source):
              <br />
              <code className="text-[10px]">
                pip install "git+https://github.com/k821209/co-scientists-mcp.git#subdirectory=apps/local-mcp"
              </code>
            </p>
          </Step>

          <Step n={2} title="Set up the project directory (one command)">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="flex-1 text-sm text-muted-foreground">
                  One script that drops <code className="text-xs">.mcp.json</code> +{" "}
                  <code className="text-xs">CLAUDE.md</code> into the current directory.
                  The MCP auto-exchanges your API key for a project-scoped Firebase token —
                  no service-account JSON anywhere.
                </p>
                <Button size="sm" disabled={!apiKey || !project}
                        onClick={() =>
                          downloadFile(`setup-${projectSlug}.sh`, setupScript, "text/x-shellscript")
                        }>
                  <Download className="mr-2 h-4 w-4" /> Download setup script
                </Button>
              </div>
              <CodeBlock value={`cd /path/to/your/project
bash ~/Downloads/setup-${projectSlug}.sh`} />

              <details className="rounded-md border bg-muted/30 p-3 text-xs">
                <summary className="cursor-pointer text-muted-foreground">
                  Or download the two files individually (inspect before using)
                </summary>
                <div className="mt-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <code className="text-xs">.mcp.json</code>
                    <Button size="sm" variant="outline" disabled={!apiKey}
                            onClick={() => downloadFile(".mcp.json", mcp, "application/json")}>
                      <Download className="mr-2 h-4 w-4" /> Download .mcp.json
                    </Button>
                  </div>
                  <div className="flex items-center justify-between">
                    <code className="text-xs">CLAUDE.md</code>
                    <Button size="sm" variant="outline" disabled={!project}
                            onClick={() => downloadFile("CLAUDE.md", claudeMd, "text/markdown")}>
                      <Download className="mr-2 h-4 w-4" /> Download CLAUDE.md
                    </Button>
                  </div>
                </div>
              </details>
            </div>
          </Step>

          <Step n={3} title="Open Claude Code in that directory">
            <CodeBlock value={`cd /path/to/your/project\nclaude`} />
            <p className="mt-2 text-xs text-muted-foreground">
              Claude Code will auto-load <code>CLAUDE.md</code> + launch the MCP. Try{" "}
              <code className="bg-muted px-1 py-0.5 text-xs">
                /paper-writing "Your paper title"
              </code>{" "}
              and watch the Papers tab update live.
            </p>
          </Step>
        </CardContent>
      </Card>
    </div>
  );
}


function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] text-primary-foreground">
          {n}
        </span>
        {title}
      </h4>
      <div className="ml-7">{children}</div>
    </div>
  );
}

function CodeBlock({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked */ }
  };
  return (
    <div className="group relative mt-2">
      <pre className="overflow-x-auto rounded-md border bg-muted/50 p-3 text-xs leading-relaxed">
        {value}
      </pre>
      <Button
        size="sm" variant="ghost" onClick={copy}
        className="absolute right-1.5 top-1.5 h-7 w-7 p-0 opacity-0 group-hover:opacity-100"
        aria-label="copy"
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </Button>
    </div>
  );
}

function CopyButton({ value, disabled, label }: {
  value: string; disabled?: boolean; label: string;
}) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };
  return (
    <Button size="sm" variant="outline" onClick={copy} disabled={disabled}>
      {copied ? <Check className="mr-1 h-3.5 w-3.5" /> : <Copy className="mr-1 h-3.5 w-3.5" />}
      {label}
    </Button>
  );
}
