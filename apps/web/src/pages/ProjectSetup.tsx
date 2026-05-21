import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { doc, updateDoc } from "firebase/firestore";
import {
  Copy, Check, Download, KeyRound, RefreshCw, Eye, EyeOff,
  Sparkles, ArrowRight, ArrowLeft, FolderOpen,
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
# co-scientist setup — drops .mcp.json + CLAUDE.md + Claude Code skills
# into the current directory.
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

# Wire up Claude Code skills shipped with the co-scientists-mcp package.
# Looks for the repo in a few well-known spots, then symlinks each skill
# folder into .claude/skills/ so 'git pull' on the repo updates them all.
mkdir -p .claude/skills
REPO=""
for candidate in \\
    "$HOME/co-scientists-mcp" \\
    "$HOME/Projects/co-scientists-mcp" \\
    "$HOME/works/co-scientists-mcp" \\
    "$(dirname "$0")/.."; do
  if [ -d "$candidate/packages/skills" ]; then
    REPO="$candidate"
    break
  fi
done
if [ -n "$REPO" ]; then
  for skill_dir in "$REPO"/packages/skills/*/; do
    skill_name="$(basename "$skill_dir")"
    [ -L ".claude/skills/$skill_name" ] && rm ".claude/skills/$skill_name"
    [ -d ".claude/skills/$skill_name" ] && continue   # don't clobber a real folder
    ln -s "$skill_dir" ".claude/skills/$skill_name"
  done
  echo "✓ Linked $(ls "$REPO/packages/skills" | wc -l | tr -d ' ') skills from $REPO/packages/skills"
else
  echo "⚠  co-scientists-mcp repo not found. Skills not installed."
  echo "   Clone https://github.com/k821209/co-scientists-mcp and re-run."
fi

echo "✓ Wrote .mcp.json + CLAUDE.md to $(pwd)"
echo ""
echo "Next: run 'claude' in this directory."
`;
}


function buildClaudeMd(name: string, description: string | undefined, pid: string): string {
  // Keep this file TINY: only project identity. The rest (skills list, tool
  // surface, math/citation/remote conventions) is served by the MCP tool
  // `project_guide()` so updates flow via `pip install --upgrade` instead of
  // forcing users to re-download CLAUDE.md.
  return `# co-scientist project: ${name}

Project id: \`${pid}\`
Dashboard: https://${FIREBASE_PROJECT}.web.app/projects/${pid}/papers
${description ? `\n> ${description}\n` : ""}
## On session start (every session)

1. Call \`mcp__co_scientist__whoami()\` once.
   - Verify the returned \`project_id\` equals \`${pid}\`. If they differ,
     STOP and tell the user — \`.mcp.json\` and \`CLAUDE.md\` were taken
     from two different dashboard projects. Have them re-download both
     from the same project's Setup tab.
2. Call \`mcp__co_scientist__project_guide()\` for the current skill list,
   tool surface, citation/math/remote conventions. The guide lives in the
   installed package so \`pip install --upgrade co-scientist-local\` is
   how you get the latest version — re-downloading this file is rarely
   needed.
3. Call \`mcp__co_scientist__list_papers()\` then, for each paper,
   \`mcp__co_scientist__count_open_user_comments(slug)\`. If non-zero,
   surface the comments and offer \`/paper-revision\`.
`;
}

// User-facing tour of the Claude Code workflow. Each entry: a plain-language
// example of what to say, and the skill it maps to.
const CAPABILITIES: { what: string; say: string; skill: string }[] = [
  { what: "Write or revise the manuscript",
    say: "Write the introduction", skill: "/paper-writing" },
  { what: "Import an existing draft (.docx / .pdf)",
    say: "Import ~/Downloads/draft.docx", skill: "/paper-import" },
  { what: "Address comments left on this dashboard",
    say: "Address the open comments", skill: "/paper-revision" },
  { what: "Find literature and add citations",
    say: "Find papers on X and cite them", skill: "/literature-review" },
  { what: "Run an AI peer review",
    say: "Review this paper", skill: "/paper-review" },
  { what: "Generate a figure",
    say: "Make a pathway diagram", skill: "/scientific-image" },
  { what: "Run a computational analysis",
    say: "Run this analysis script", skill: "/analysis-run" },
  { what: "Export to a journal format",
    say: "Export to a Nature-formatted .docx", skill: "/paper-export" },
  { what: "Build a presentation",
    say: "Make slides for a 15-minute talk", skill: "/paper-deck" },
];

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
    <div className="space-y-6 break-words">
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

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4" /> What you can do from Claude Code
          </CardTitle>
          <CardDescription>
            Once connected, you do the work by talking to Claude Code in plain
            language. This dashboard is the live view of the result.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* The bidirectional loop */}
          <div className="space-y-2 rounded-md border border-dashed p-3 text-sm">
            <div className="flex gap-2">
              <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <span>
                <strong>Claude Code → dashboard.</strong> Sections, figures,
                references, and exports it produces show up here live.
              </span>
            </div>
            <div className="flex gap-2">
              <ArrowLeft className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <span>
                <strong>Dashboard → Claude Code.</strong> Drag-select any
                manuscript text to leave a comment; next session Claude Code
                picks the comments up and revises.
              </span>
            </div>
          </div>

          {/* Capability list */}
          <div className="space-y-1.5">
            {CAPABILITIES.map((c) => (
              <div key={c.skill} className="rounded-md border bg-muted/30 p-2.5">
                <div className="text-sm font-medium">{c.what}</div>
                <div className="mt-0.5 break-words text-xs text-muted-foreground">
                  Say “{c.say}” ·{" "}
                  <code className="bg-muted px-1 py-0.5 text-[10px]">{c.skill}</code>
                </div>
              </div>
            ))}
          </div>

          {/* Local-execution advantage */}
          <div className="flex gap-2 rounded-md border border-dashed bg-muted/30 p-3 text-xs">
            <FolderOpen className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>
              <strong className="text-foreground">
                Claude Code runs on your own computer
              </strong>{" "}
              — so it can read files straight off your disk, no upload step.
              To bring an existing manuscript in, just point it at the path:{" "}
              <code className="bg-muted px-1 py-0.5 text-[10px]">
                Import ~/Downloads/draft.docx
              </code>
              . The same goes for local analysis outputs and figure images.
            </span>
          </div>

          <p className="text-xs text-muted-foreground">
            The <code className="bg-muted px-1 py-0.5 text-[10px]">/skill</code>{" "}
            names are shortcuts — you can type one directly, or just describe
            what you want in plain language and Claude Code picks the right one.
          </p>
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
