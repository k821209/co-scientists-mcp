import { useEffect, useState } from "react";
import {
  collection, doc, onSnapshot, setDoc, updateDoc,
} from "firebase/firestore";
import { X, Copy, Check, Link2, Trash2, Plus } from "lucide-react";
import { db } from "@/firebase";
import { Button } from "@/components/ui/button";

interface Share {
  id: string;
  scope?: string;
  revoked?: boolean;
  created_at?: string;
  open_count?: number;
}

interface Props {
  pid: string;
  slug: string;
  paperTitle: string;
  onClose: () => void;
}

/** 32 hex chars of entropy — the share link's unguessable secret. */
function newShareId(): string {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

/** Owner-side dialog: create / list / revoke share links for a paper.
 *  Anyone with an active link can read the paper + leave comments,
 *  anonymously — no account needed. */
export function SharePaperDialog({ pid, slug, paperTitle, onClose }: Props) {
  const [shares, setShares] = useState<Share[]>([]);
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    const ref = collection(db, "projects", pid, "papers", slug, "shares");
    return onSnapshot(
      ref,
      (snap) =>
        setShares(
          snap.docs
            .map((d) => ({ id: d.id, ...(d.data() as Omit<Share, "id">) }))
            .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")),
        ),
      () => setShares([]),
    );
  }, [pid, slug]);

  const linkFor = (shareId: string) =>
    `${window.location.origin}/shared/${pid}/${slug}/${shareId}`;

  const create = async () => {
    setCreating(true);
    try {
      const shareId = newShareId();
      await setDoc(
        doc(db, "projects", pid, "papers", slug, "shares", shareId),
        {
          scope: "comment",
          paper_title: paperTitle,
          revoked: false,
          expires_at_ms: null,
          open_count: 0,
          created_at: new Date().toISOString(),
        },
      );
    } finally {
      setCreating(false);
    }
  };

  const revoke = async (shareId: string) => {
    if (!confirm("Revoke this link? Anyone using it loses access immediately.")) return;
    await updateDoc(
      doc(db, "projects", pid, "papers", slug, "shares", shareId),
      { revoked: true },
    );
  };

  const copy = async (shareId: string) => {
    try {
      await navigator.clipboard.writeText(linkFor(shareId));
      setCopied(shareId);
      setTimeout(() => setCopied(null), 1500);
    } catch { /* clipboard blocked */ }
  };

  const active = shares.filter((s) => !s.revoked);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl bg-background shadow-xl sm:max-w-lg sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Link2 className="h-4 w-4" /> Share for review
            </div>
            <div className="text-xs text-muted-foreground">
              A link lets anyone read this paper and leave comments — no
              account needed.
            </div>
          </div>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {active.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No active share links. Create one to send to a collaborator.
            </p>
          )}
          {active.map((s) => (
            <div key={s.id} className="rounded-md border p-3">
              <div className="mb-2 flex items-center gap-2">
                <code className="flex-1 truncate rounded bg-muted px-2 py-1 text-[11px]">
                  {linkFor(s.id)}
                </code>
                <Button
                  size="icon" variant="outline" className="h-7 w-7 shrink-0"
                  onClick={() => copy(s.id)}
                  aria-label="Copy link"
                >
                  {copied === s.id
                    ? <Check className="h-3.5 w-3.5" />
                    : <Copy className="h-3.5 w-3.5" />}
                </Button>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                <span>opened {s.open_count ?? 0}×</span>
                {s.created_at && (
                  <span>created {new Date(s.created_at).toLocaleDateString()}</span>
                )}
                <Button
                  size="sm" variant="ghost"
                  className="ml-auto h-6 gap-1 px-2 text-[11px] text-destructive hover:bg-destructive/10"
                  onClick={() => revoke(s.id)}
                >
                  <Trash2 className="h-3 w-3" /> Revoke
                </Button>
              </div>
            </div>
          ))}
        </div>

        <div className="border-t bg-muted/30 px-4 py-3">
          <Button onClick={create} disabled={creating} className="gap-1">
            <Plus className="h-4 w-4" />
            {creating ? "Creating…" : "Create a share link"}
          </Button>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Comments from a shared link appear in the manuscript as
            highlights and feed <code>/paper-revision</code> like any other
            review (source: external).
          </p>
        </div>
      </div>
    </div>
  );
}
