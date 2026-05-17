import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  addDoc, collection, onSnapshot, query, where,
} from "firebase/firestore";
import { Folder, Plus, X } from "lucide-react";
import { useAuth } from "@/auth";
import { db } from "@/firebase";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { generateApiKey } from "@/lib/projectKey";

interface Project {
  id: string;
  name: string;
  description?: string;
  plan_id?: string;
  created_at?: string;
  updated_at?: string;
}

const FREE_TIER_LIMIT = 3;

export function Projects() {
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);

  useEffect(() => {
    if (!user) return;
    const q = query(
      collection(db, "projects"),
      where("owner_uid", "==", user.uid),
    );
    const unsub = onSnapshot(
      q,
      (snap) => {
        const items = snap.docs
          .map((d) => ({ id: d.id, ...(d.data() as Omit<Project, "id">) }))
          .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
        setProjects(items);
        setLoading(false);
      },
      (err) => {
        console.error("projects listener:", err);
        setLoading(false);
      },
    );
    return unsub;
  }, [user]);

  const atLimit = projects.length >= FREE_TIER_LIMIT;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Projects</h1>
          <p className="text-sm text-muted-foreground">
            {projects.length}/{FREE_TIER_LIMIT} on free tier. Each project gets its own
            MCP, agent, and skill set.
          </p>
        </div>
        <Button onClick={() => setShowNew(true)} disabled={atLimit}>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </div>

      {showNew && (
        <NewProjectForm
          onCancel={() => setShowNew(false)}
          onCreated={() => setShowNew(false)}
        />
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : projects.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Folder className="h-4 w-4" /> No projects yet
            </CardTitle>
            <CardDescription>
              Click "New Project" to create your first one (e.g. "Arabidopsis genome").
              Each project gets its own MCP config bundle to download.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Link key={p.id} to={`/projects/${p.id}/papers`}>
              <Card className="h-full transition-colors hover:bg-accent">
                <CardHeader>
                  <CardTitle className="flex items-start gap-2 text-base">
                    <Folder className="mt-0.5 h-4 w-4 shrink-0" />
                    <span className="truncate">{p.name}</span>
                  </CardTitle>
                  {p.description && (
                    <CardDescription className="line-clamp-2">
                      {p.description}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground">
                  plan: {p.plan_id || "free"} ·{" "}
                  {p.created_at
                    ? `created ${new Date(p.created_at).toLocaleDateString()}`
                    : "—"}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function NewProjectForm({ onCancel, onCreated }: {
  onCancel: () => void;
  onCreated: () => void;
}) {
  const { user } = useAuth();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!user) return;
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
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">New Project</CardTitle>
        <Button variant="ghost" size="icon" onClick={onCancel} aria-label="cancel">
          <X className="h-4 w-4" />
        </Button>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <Input
            placeholder="Project name (e.g. Arabidopsis genome)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <Input
            placeholder="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <Button type="submit" disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create project"}
          </Button>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </form>
      </CardContent>
    </Card>
  );
}
