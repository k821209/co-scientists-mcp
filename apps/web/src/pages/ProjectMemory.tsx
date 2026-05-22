import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { doc, onSnapshot, setDoc } from "firebase/firestore";
import { Brain, Loader2, Pencil, Check, X } from "lucide-react";
import { db } from "@/firebase";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Markdown } from "@/components/Markdown";
import { type ProjectContext } from "./ProjectShell";

export function ProjectMemory() {
  const { pid } = useOutletContext<ProjectContext>();
  const [content, setContent] = useState("");
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [updatedBy, setUpdatedBy] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pid) return;
    return onSnapshot(
      doc(db, "projects", pid, "memory", "main"),
      (snap) => {
        const d = snap.data();
        setContent((d?.content as string) ?? "");
        setUpdatedAt((d?.updated_at as string) ?? null);
        setUpdatedBy((d?.updated_by as string) ?? null);
        setLoaded(true);
      },
      () => setLoaded(true),
    );
  }, [pid]);

  const startEdit = () => {
    setDraft(content);
    setError(null);
    setEditing(true);
  };

  const save = async () => {
    if (!pid) return;
    setSaving(true);
    setError(null);
    try {
      await setDoc(
        doc(db, "projects", pid, "memory", "main"),
        { content: draft, updated_at: new Date().toISOString(), updated_by: "you" },
        { merge: true },
      );
      setEditing(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (!pid) return null;

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2 space-y-0">
        <div className="min-w-0">
          <CardTitle className="flex items-center gap-2 text-base">
            <Brain className="h-4 w-4" /> Project memory
          </CardTitle>
          <CardDescription>
            Durable project knowledge — writing preferences, decisions,
            approaches tried, gotchas. Claude Code reads this at session
            start and appends to it; you can edit it here.
          </CardDescription>
        </div>
        {!editing && loaded && (
          <Button size="sm" variant="outline" onClick={startEdit}>
            <Pencil className="mr-1 h-3.5 w-3.5" /> Edit
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {!loaded ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : editing ? (
          <>
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={18}
              className="font-mono text-xs"
              placeholder={"# Project memory\n\n- The user prefers …\n- Decision: …"}
            />
            {error && <p className="text-xs text-destructive">{error}</p>}
            <div className="flex gap-2">
              <Button size="sm" onClick={save} disabled={saving}>
                {saving
                  ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                  : <Check className="mr-1 h-3.5 w-3.5" />}
                Save
              </Button>
              <Button
                size="sm" variant="outline" disabled={saving}
                onClick={() => setEditing(false)}
              >
                <X className="mr-1 h-3.5 w-3.5" /> Cancel
              </Button>
            </div>
          </>
        ) : content.trim() ? (
          <>
            <div className="min-w-0 rounded-md border bg-muted/20 p-3">
              <Markdown className="text-sm">{content}</Markdown>
            </div>
            {updatedAt && (
              <p className="text-[10px] text-muted-foreground">
                updated {new Date(updatedAt).toLocaleString()}
                {updatedBy ? ` · ${updatedBy}` : ""}
              </p>
            )}
          </>
        ) : (
          <p className="text-sm italic text-muted-foreground">
            No project memory yet. Claude Code records durable project
            knowledge here as you work — or click Edit to start it.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
