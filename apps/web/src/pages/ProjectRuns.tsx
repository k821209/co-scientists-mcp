import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import {
  collectionGroup, onSnapshot, orderBy, query, where,
} from "firebase/firestore";
import { Activity, CheckCircle2, Loader2, XCircle, Server, FileText } from "lucide-react";
import { db } from "@/firebase";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { type ProjectContext } from "./ProjectShell";

interface Run {
  id: string;
  run_key: string;
  project_id: string;
  paper_slug: string;
  analysis_name: string;
  command: string;
  host?: string;
  env_name?: string | null;
  pid?: number | null;
  started_at?: string;
  finished_at?: string | null;
  exit_code?: number | null;
  log_path?: string | null;
  notes?: string | null;
}

const RECENT_LIMIT = 50;

export function ProjectRuns() {
  const { pid } = useOutletContext<ProjectContext>();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pid) return;
    const q = query(
      collectionGroup(db, "runs"),
      where("project_id", "==", pid),
      orderBy("started_at", "desc"),
    );
    const unsub = onSnapshot(
      q,
      (snap) => {
        setRuns(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Run, "id">) })));
        setLoading(false);
        setError(null);
      },
      (err) => {
        // Firestore can throw "the query requires an index" — surface the
        // message so the user (or me reading the deploy logs) can act.
        setError(err.message);
        setLoading(false);
      },
    );
    return unsub;
  }, [pid]);

  const running = runs.filter((r) => !r.finished_at);
  const recent = runs.filter((r) => r.finished_at).slice(0, RECENT_LIMIT);

  if (!pid) return null;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Loader2 className="h-4 w-4" /> Running now
            <Badge variant={running.length > 0 ? "warning" : "outline"} className="ml-auto text-[10px]">
              {running.length}
            </Badge>
          </CardTitle>
          <CardDescription>
            Unfinished analysis runs across all papers in this project. Pushed
            by the local MCP when{" "}
            <code className="bg-muted px-1 py-0.5 text-[10px]">submit_remote_job</code>{" "}
            or <code className="bg-muted px-1 py-0.5 text-[10px]">launch_local_job</code>{" "}
            is called.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : error ? (
            <p className="text-xs text-destructive">{error}</p>
          ) : running.length === 0 ? (
            <p className="text-sm italic text-muted-foreground">No jobs running.</p>
          ) : (
            running.map((r) => <RunRow key={r.id} run={r} pid={pid} />)
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="h-4 w-4" /> Recent
            <Badge variant="secondary" className="ml-auto text-[10px]">
              {recent.length}
            </Badge>
          </CardTitle>
          <CardDescription>
            Last {RECENT_LIMIT} finished runs, newest first.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {recent.length === 0 ? (
            <p className="text-sm italic text-muted-foreground">
              No finished runs yet.
            </p>
          ) : (
            recent.map((r) => <RunRow key={r.id} run={r} pid={pid} />)
          )}
        </CardContent>
      </Card>
    </div>
  );
}


function RunRow({ run, pid }: { run: Run; pid: string }) {
  const running = !run.finished_at;
  const success = run.exit_code === 0;

  const status = running ? (
    <Badge variant="warning" className="text-[10px]">
      <Loader2 className="mr-1 h-3 w-3 animate-spin" /> running
    </Badge>
  ) : success ? (
    <Badge variant="success" className="text-[10px]">
      <CheckCircle2 className="mr-1 h-3 w-3" /> exit 0
    </Badge>
  ) : (
    <Badge variant="destructive" className="text-[10px]">
      <XCircle className="mr-1 h-3 w-3" /> exit {run.exit_code ?? "?"}
    </Badge>
  );

  const startedAgo = run.started_at ? timeAgo(new Date(run.started_at)) : "—";
  const elapsedMs = run.finished_at && run.started_at
    ? Date.parse(run.finished_at) - Date.parse(run.started_at)
    : null;

  return (
    <div className="space-y-1 border-l-2 border-muted pl-3 text-sm">
      <div className="flex flex-wrap items-baseline gap-2">
        {status}
        <Link
          to={`/projects/${pid}/papers/${run.paper_slug}`}
          className="inline-flex items-center gap-1 text-xs text-primary underline underline-offset-2 hover:no-underline"
        >
          <FileText className="h-3 w-3" />
          {run.paper_slug}
        </Link>
        <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
          {run.analysis_name}
        </code>
        <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-muted-foreground">
          <Server className="h-3 w-3" />
          {run.host || "local"}
        </span>
      </div>
      <div className={cn(
        "rounded bg-muted/30 px-2 py-1 font-mono text-[11px] leading-tight",
        running ? "text-foreground" : "text-muted-foreground",
      )}>
        {run.command}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-muted-foreground">
        <span>started {startedAgo}</span>
        {elapsedMs !== null && <span>· duration {formatDuration(elapsedMs)}</span>}
        {run.env_name && <span>· env {run.env_name}</span>}
        {run.pid && <span>· pid {run.pid}</span>}
      </div>
    </div>
  );
}


function timeAgo(d: Date): string {
  const sec = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (sec < 60) return `${Math.floor(sec)}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

function formatDuration(ms: number): string {
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h}h ${m}m`;
}
