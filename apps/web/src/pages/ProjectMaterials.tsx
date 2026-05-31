import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useOutletContext } from "react-router-dom";
import {
  collection, deleteDoc, doc, onSnapshot, setDoc,
} from "firebase/firestore";
import { Paperclip, UploadCloud, Download, Trash2, Loader2 } from "lucide-react";
import { db } from "@/firebase";
import { downloadProjectBlobAsFile, getProjectStorage } from "@/projectAuth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { type ProjectContext } from "./ProjectShell";

interface Material {
  id: string;
  material_id: string;
  filename: string;
  content_type?: string;
  size_bytes?: number;
  blob_path?: string | null;
  description?: string | null;
  uploaded_by?: string;
  created_at?: string;
}

const MAX_BYTES = 25 * 1024 * 1024; // 25 MB

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function safeName(name: string): string {
  const base = name.split(/[/\\]/).pop() || "file";
  const cleaned = base.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[._]+|[._]+$/g, "");
  return (cleaned || "file").slice(0, 120);
}

function newMaterialId(): string {
  // 12-char opaque id, matching the MCP's uuid4().hex[:12] shape.
  const u = (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`).replace(/-/g, "");
  return u.slice(0, 12);
}

export function ProjectMaterials() {
  const { pid } = useOutletContext<ProjectContext>();
  const [materials, setMaterials] = useState<Material[]>([]);
  const [busy, setBusy] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!pid) return;
    return onSnapshot(
      collection(db, "projects", pid, "materials"),
      (snap) =>
        setMaterials(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Material, "id">) }))),
      () => {/* empty collection is fine */},
    );
  }, [pid]);

  const sorted = useMemo(
    () =>
      [...materials].sort((a, b) =>
        (b.created_at ?? "").localeCompare(a.created_at ?? ""),
      ),
    [materials],
  );

  const upload = async (file: File) => {
    setErr(null);
    if (file.size > MAX_BYTES) {
      setErr(`"${file.name}" is ${formatBytes(file.size)} — over the 25 MB limit.`);
      return;
    }
    setBusy(true);
    try {
      const materialId = newMaterialId();
      const filename = safeName(file.name);
      const blobPath = `projects/${pid}/materials/${materialId}__${filename}`;
      const { ref, uploadBytes } = await import("firebase/storage");
      const storage = await getProjectStorage(pid);
      await uploadBytes(ref(storage, blobPath), file, {
        contentType: file.type || "application/octet-stream",
      });
      const now = new Date().toISOString();
      await setDoc(doc(db, "projects", pid, "materials", materialId), {
        material_id: materialId,
        filename,
        content_type: file.type || "application/octet-stream",
        size_bytes: file.size,
        blob_path: blobPath,
        description: null,
        uploaded_by: "user",
        created_at: now,
        updated_at: now,
      });
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onPick = (e: FormEvent<HTMLInputElement>) => {
    const input = e.currentTarget;
    const files = Array.from(input.files ?? []);
    input.value = ""; // allow re-picking the same file
    (async () => {
      for (const f of files) await upload(f);
    })();
  };

  const download = async (m: Material) => {
    if (!m.blob_path) return;
    setBusyId(m.id);
    setErr(null);
    try {
      await downloadProjectBlobAsFile(pid, m.blob_path, m.filename);
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (m: Material) => {
    if (!confirm(`Delete "${m.filename}"? Claude Code will no longer see it.`)) return;
    setBusyId(m.id);
    setErr(null);
    try {
      if (m.blob_path) {
        const { ref, deleteObject } = await import("firebase/storage");
        const storage = await getProjectStorage(pid);
        await deleteObject(ref(storage, m.blob_path)).catch(() => {/* blob already gone */});
      }
      await deleteDoc(doc(db, "projects", pid, "materials", m.material_id));
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2 text-base">
            <Paperclip className="h-4 w-4" /> Materials
          </CardTitle>
          <CardDescription>
            Reference files shared across this project — PDFs, datasets, prior
            drafts, notes. Claude Code reads them via{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
              list_materials
            </code>{" "}
            /{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
              get_material
            </code>{" "}
            and pulls any it needs to your working directory.
          </CardDescription>
        </div>
        <label
          className={cn(
            buttonVariants({ variant: "default", size: "sm" }),
            busy ? "pointer-events-none opacity-50" : "cursor-pointer",
          )}
        >
          <input type="file" multiple className="hidden" onChange={onPick} disabled={busy} />
          {busy ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <UploadCloud className="mr-2 h-4 w-4" />
          )}
          {busy ? "Uploading…" : "Upload files"}
        </label>
      </CardHeader>
      <CardContent className="space-y-2">
        {sorted.length === 0 ? (
          <p className="text-sm italic text-muted-foreground">
            No materials yet. Upload files here — Claude Code picks them up with{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-[10px]">list_materials</code>{" "}
            next session.
          </p>
        ) : (
          sorted.map((m) => (
            <div
              key={m.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-2 text-sm"
            >
              <div className="min-w-0">
                <div className="truncate font-medium">{m.filename}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {typeof m.size_bytes === "number" && formatBytes(m.size_bytes)}
                  {m.uploaded_by === "agent" ? " · from Claude Code" : null}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  size="sm" variant="outline"
                  disabled={busyId === m.id || !m.blob_path}
                  onClick={() => download(m)}
                  aria-label="download"
                >
                  {busyId === m.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  size="sm" variant="ghost"
                  disabled={busyId === m.id}
                  onClick={() => remove(m)}
                  aria-label="delete"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))
        )}
        {err && <p className="text-xs text-destructive">{err}</p>}
      </CardContent>
    </Card>
  );
}
