import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { collection, onSnapshot } from "firebase/firestore";
import { FileText, ArrowRight } from "lucide-react";
import { db } from "@/firebase";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { type ProjectContext } from "./ProjectShell";

interface Paper {
  id: string;
  slug: string;
  title: string;
  journal?: string | null;
  status?: string;
  updated_at?: string;
}

export function ProjectPapers() {
  const { pid } = useOutletContext<ProjectContext>();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!pid) return;
    return onSnapshot(
      collection(db, "projects", pid, "papers"),
      (snap) => {
        const items = snap.docs
          .map((d) => ({ id: d.id, slug: d.id, ...(d.data() as Omit<Paper, "id" | "slug">) }))
          .sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
        setPapers(items);
        setLoading(false);
      },
      () => setLoading(false),
    );
  }, [pid]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading papers…</p>;
  }

  if (papers.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No papers yet</CardTitle>
          <CardDescription>
            Connect Claude Code first — see the{" "}
            <Link to={`/projects/${pid}/setup`} className="font-medium text-foreground underline">
              Setup guide
            </Link>{" "}
            tab. Then in Claude Code say{" "}
            <code className="bg-muted px-1 py-0.5 text-xs">
              /paper-writing "Your paper title"
            </code>{" "}
            and the paper will appear here live.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link
            to={`/projects/${pid}/setup`}
            className="inline-flex items-center gap-2 text-sm font-medium text-foreground hover:underline"
          >
            Go to Setup guide <ArrowRight className="h-4 w-4" />
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {papers.map((p) => (
        <Link key={p.id} to={`/projects/${pid}/papers/${p.slug}`}>
          <Card className="h-full transition-colors hover:bg-accent">
            <CardHeader>
              <CardTitle className="flex items-start gap-2 text-base">
                <FileText className="mt-0.5 h-4 w-4 shrink-0" />
                <span className="truncate">{p.title}</span>
              </CardTitle>
              <CardDescription className="flex flex-wrap items-center gap-2">
                {p.journal && <span>{p.journal}</span>}
                {p.status && (
                  <Badge variant="secondary" className="text-[10px]">{p.status}</Badge>
                )}
              </CardDescription>
            </CardHeader>
            {p.updated_at && (
              <CardContent className="text-xs text-muted-foreground">
                updated {new Date(p.updated_at).toLocaleString()}
              </CardContent>
            )}
          </Card>
        </Link>
      ))}
    </div>
  );
}
