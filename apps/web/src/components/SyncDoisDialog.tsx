import { useEffect, useRef, useState } from "react";
import { doc, deleteDoc, updateDoc } from "firebase/firestore";
import { X, CheckCircle2, AlertTriangle, HelpCircle, Trash2, RefreshCw } from "lucide-react";
import { db } from "@/firebase";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { verifyOne, type Verdict, type CrossrefMeta } from "@/lib/crossref";

interface Reference {
  id: string;
  citation_key: string;
  doi?: string | null;
  title?: string;
  year?: number | null;
  journal?: string | null;
  authors?: string[] | string | null;
}

interface Props {
  pid: string;
  slug: string;
  references: Reference[];
  onClose: () => void;
}

interface RowResult {
  ref: Reference;
  verdict: Verdict;
}

/** Modal: sequentially verify every reference's DOI against CrossRef,
 *  optionally fill in missing fields from CrossRef, and let the user
 *  delete hallucinated DOIs or accept CrossRef's title on mismatches. */
export function SyncDoisDialog({ pid, slug, references, onClose }: Props) {
  const [results, setResults] = useState<RowResult[]>([]);
  const [doneCount, setDoneCount] = useState(0);
  const [running, setRunning] = useState(true);
  const [filling, setFilling] = useState(true);
  const aborter = useRef<AbortController | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    aborter.current = ctrl;
    let cancelled = false;

    (async () => {
      const out: RowResult[] = [];
      for (const ref of references) {
        if (cancelled) break;
        const verdict = await verifyOne(ref.doi, ref.title ?? "", ctrl.signal);
        out.push({ ref, verdict });
        if (cancelled) break;
        setResults([...out]);
        setDoneCount(out.length);
        // Auto-fill missing fields when we have CrossRef metadata
        if (filling && (verdict.kind === "resolved" || verdict.kind === "title_mismatch")) {
          await maybeFillMissingFields(pid, slug, ref, verdict.meta);
        }
        // Gentle pacing to be a good CrossRef citizen
        await sleep(150);
      }
      if (!cancelled) setRunning(false);
    })();

    return () => {
      cancelled = true;
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cancel = () => {
    aborter.current?.abort();
    setRunning(false);
    onClose();
  };

  const total = references.length;
  const counts = countByKind(results);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 backdrop-blur-sm sm:items-center sm:p-4"
         onClick={cancel}>
      <div
        className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl bg-background shadow-xl sm:max-w-2xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <div className="text-sm font-semibold">Sync DOIs against CrossRef</div>
            <div className="text-xs text-muted-foreground">
              {running
                ? `Checking ${doneCount}/${total}…`
                : `Done — ${doneCount}/${total} checked`}
            </div>
          </div>
          <Button size="icon" variant="ghost" onClick={cancel} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Progress bar */}
        <div className="h-1 w-full bg-muted">
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${total === 0 ? 0 : (doneCount / total) * 100}%` }}
          />
        </div>

        {/* Summary counts */}
        <div className="flex flex-wrap gap-2 border-b px-4 py-2 text-xs">
          <SummaryPill kind="resolved" count={counts.resolved} />
          <SummaryPill kind="unresolved" count={counts.unresolved} />
          <SummaryPill kind="title_mismatch" count={counts.title_mismatch} />
          <SummaryPill kind="missing_doi" count={counts.missing_doi} />
          {counts.error > 0 && <SummaryPill kind="error" count={counts.error} />}
        </div>

        {/* Per-ref results */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {results.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">
              <RefreshCw className="mx-auto mb-2 h-4 w-4 animate-spin" />
              Contacting CrossRef…
            </div>
          )}
          <div className="space-y-3">
            {results.map((r) => (
              <ResultRow key={r.ref.id} pid={pid} slug={slug} row={r} />
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 border-t bg-muted/30 px-4 py-3">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={filling}
              onChange={(e) => setFilling(e.target.checked)}
              disabled={!running ? false : true}
              className="h-3.5 w-3.5"
            />
            Auto-fill missing fields from CrossRef
          </label>
          <Button onClick={onClose} size="sm">
            {running ? "Run in background" : "Close"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function ResultRow({ pid, slug, row }: { pid: string; slug: string; row: RowResult }) {
  const { ref, verdict } = row;
  const [acted, setActed] = useState<string | null>(null);

  const acceptCrossrefTitle = async (meta: CrossrefMeta) => {
    await updateDoc(refDoc(pid, slug, ref.id), {
      title: meta.title,
      journal: meta.journal,
      year: meta.year,
      authors: meta.authors,
      updated_at: new Date().toISOString(),
    });
    setActed("Updated from CrossRef");
  };

  const removeReference = async () => {
    if (!confirm(`Delete reference '${ref.citation_key}'?`)) return;
    await deleteDoc(refDoc(pid, slug, ref.id));
    setActed("Deleted");
  };

  return (
    <div className="rounded-md border bg-card p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">{ref.citation_key}</code>
        <KindBadge kind={verdict.kind} />
        {ref.doi && (
          <a
            href={`https://doi.org/${ref.doi}`}
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-primary underline underline-offset-2"
          >
            doi:{ref.doi}
          </a>
        )}
      </div>
      {ref.title && (
        <div className="text-xs text-muted-foreground">stored: {ref.title}</div>
      )}
      {verdict.kind === "title_mismatch" && (
        <div className="mt-1 text-xs">
          <span className="text-muted-foreground">CrossRef: </span>
          <span className="font-medium">{verdict.meta.title}</span>
          <span className="ml-2 text-[10px] text-muted-foreground">
            ({verdict.sharedWords} shared word{verdict.sharedWords === 1 ? "" : "s"})
          </span>
        </div>
      )}
      {verdict.kind === "error" && (
        <div className="mt-1 text-xs text-orange-600">{verdict.message}</div>
      )}
      {!acted && (
        <div className="mt-2 flex flex-wrap gap-2">
          {verdict.kind === "title_mismatch" && (
            <Button size="sm" variant="outline" onClick={() => acceptCrossrefTitle(verdict.meta)}>
              Use CrossRef title
            </Button>
          )}
          {(verdict.kind === "unresolved" || verdict.kind === "title_mismatch") && (
            <Button
              size="sm"
              variant="outline"
              className="text-destructive hover:bg-destructive/10"
              onClick={removeReference}
            >
              <Trash2 className="mr-1 h-3 w-3" /> Delete reference
            </Button>
          )}
        </div>
      )}
      {acted && (
        <div className="mt-2 text-xs font-medium text-green-700">{acted}</div>
      )}
    </div>
  );
}

function refDoc(pid: string, slug: string, citationKey: string) {
  return doc(db, "projects", pid, "papers", slug, "references", citationKey);
}

async function maybeFillMissingFields(
  pid: string,
  slug: string,
  ref: Reference,
  meta: CrossrefMeta,
) {
  const fields: Record<string, unknown> = {};
  if (!ref.title?.trim() && meta.title) fields.title = meta.title;
  if (!ref.journal?.trim() && meta.journal) fields.journal = meta.journal;
  if (!ref.year && meta.year) fields.year = meta.year;
  const hasAuthors = Array.isArray(ref.authors) ? ref.authors.length > 0 : !!ref.authors;
  if (!hasAuthors && meta.authors.length > 0) fields.authors = meta.authors;
  if (Object.keys(fields).length === 0) return;
  fields.updated_at = new Date().toISOString();
  await updateDoc(refDoc(pid, slug, ref.id), fields);
}

function countByKind(rows: RowResult[]) {
  const counts = { resolved: 0, unresolved: 0, title_mismatch: 0, missing_doi: 0, error: 0 };
  for (const r of rows) counts[r.verdict.kind]++;
  return counts;
}

function SummaryPill({ kind, count }: { kind: keyof ReturnType<typeof countByKind>; count: number }) {
  const styles: Record<typeof kind, string> = {
    resolved: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    unresolved: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    title_mismatch: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
    missing_doi: "bg-muted text-muted-foreground",
    error: "bg-orange-100 text-orange-800",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${styles[kind]}`}>
      <KindBadge kind={kind} bare /> {count} {kind.replace("_", " ")}
    </span>
  );
}

function KindBadge({ kind, bare }: { kind: Verdict["kind"]; bare?: boolean }) {
  const Icon =
    kind === "resolved" ? CheckCircle2
    : kind === "unresolved" ? AlertTriangle
    : kind === "title_mismatch" ? AlertTriangle
    : HelpCircle;
  const label =
    kind === "resolved" ? "verified"
    : kind === "unresolved" ? "hallucinated"
    : kind === "title_mismatch" ? "title mismatch"
    : kind === "missing_doi" ? "no DOI"
    : "error";
  const color =
    kind === "resolved" ? "text-green-700"
    : kind === "unresolved" ? "text-red-700"
    : kind === "title_mismatch" ? "text-amber-700"
    : "text-muted-foreground";
  if (bare) return <Icon className={`h-3 w-3 ${color}`} />;
  return (
    <Badge variant="outline" className={`gap-1 text-[10px] ${color}`}>
      <Icon className="h-3 w-3" /> {label}
    </Badge>
  );
}

function sleep(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms));
}
