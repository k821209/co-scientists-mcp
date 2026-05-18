import { useEffect, useRef, useState } from "react";
import { doc, deleteDoc, setDoc, updateDoc, type DocumentReference } from "firebase/firestore";
import {
  X, CheckCircle2, AlertTriangle, HelpCircle, Trash2, RefreshCw, BookPlus,
} from "lucide-react";
import { db } from "@/firebase";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  verifyOne, extractDoiContexts,
  type Verdict, type CrossrefMeta, type DoiContext,
} from "@/lib/crossref";

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
  inlineDois?: string[];   // unregistered DOIs found in section bodies
  sections?: Array<{ key?: string; body?: string }>;  // for context extraction
  onClose: () => void;
}

/** A row can come from a registered reference doc or from an inline DOI
 *  that hasn't been registered yet. The action set differs. */
type Source =
  | { kind: "ref"; ref: Reference }
  | { kind: "inline"; doi: string };

interface RowResult {
  source: Source;
  verdict: Verdict;
}

/** Modal: sequentially verify every reference's DOI against CrossRef,
 *  optionally fill in missing fields from CrossRef, and let the user
 *  delete hallucinated DOIs or accept CrossRef's title on mismatches. */
export function SyncDoisDialog({
  pid, slug, references, inlineDois, sections = [], onClose,
}: Props) {
  const contexts = extractDoiContexts(sections);
  const [results, setResults] = useState<RowResult[]>([]);
  const [doneCount, setDoneCount] = useState(0);
  const [running, setRunning] = useState(true);
  const [filling, setFilling] = useState(true);
  const aborter = useRef<AbortController | null>(null);

  // Build the queue: registered references first, then unregistered inline DOIs.
  const queue: Source[] = [
    ...references.map((ref): Source => ({ kind: "ref", ref })),
    ...(inlineDois ?? []).map((doi): Source => ({ kind: "inline", doi })),
  ];
  const total = queue.length;

  useEffect(() => {
    const ctrl = new AbortController();
    aborter.current = ctrl;
    let cancelled = false;

    (async () => {
      const out: RowResult[] = [];
      for (const source of queue) {
        if (cancelled) break;
        const doi = source.kind === "ref" ? source.ref.doi : source.doi;
        const storedTitle = source.kind === "ref" ? (source.ref.title ?? "") : "";
        const ctxs: DoiContext[] = (doi && contexts.get(doi.toLowerCase())) || [];
        const verdict = await verifyOne(doi, storedTitle, ctxs, ctrl.signal);
        out.push({ source, verdict });
        if (cancelled) break;
        setResults([...out]);
        setDoneCount(out.length);
        if (
          filling && source.kind === "ref" &&
          (verdict.kind === "resolved" || verdict.kind === "title_mismatch")
        ) {
          await maybeFillMissingFields(pid, slug, source.ref, verdict.meta);
        }
        // Persist verdict so Claude Code can read it in a later session.
        await writeFinding(pid, slug, source, verdict).catch((e) =>
          console.warn("writeFinding failed:", e),
        );
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
          <SummaryPill kind="context_mismatch" count={counts.context_mismatch} />
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
            {results.map((r, i) => (
              <ResultRow key={rowKey(r, i)} pid={pid} slug={slug} row={r} />
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
  const { source, verdict } = row;
  const [acted, setActed] = useState<string | null>(null);

  const isInline = source.kind === "inline";
  const doi = source.kind === "ref" ? source.ref.doi : source.doi;
  const storedTitle = source.kind === "ref" ? source.ref.title : undefined;
  const citationKey = source.kind === "ref" ? source.ref.citation_key : null;

  const acceptCrossrefTitle = async (meta: CrossrefMeta) => {
    if (source.kind !== "ref") return;
    await updateDoc(refDoc(pid, slug, source.ref.id), {
      title: meta.title,
      journal: meta.journal,
      year: meta.year,
      authors: meta.authors,
      updated_at: new Date().toISOString(),
    });
    if (source.ref.doi) await deleteDoc(findingDoc(pid, slug, source.ref.doi));
    setActed("Updated from CrossRef");
  };

  const removeReference = async () => {
    if (source.kind !== "ref") return;
    if (!confirm(`Delete reference '${source.ref.citation_key}'?`)) return;
    await deleteDoc(refDoc(pid, slug, source.ref.id));
    if (source.ref.doi) await deleteDoc(findingDoc(pid, slug, source.ref.doi));
    setActed("Deleted");
  };

  const registerAsReference = async (meta: CrossrefMeta) => {
    const key = await deriveAvailableKey(pid, slug, meta);
    const now = new Date().toISOString();
    await setDoc(refDoc(pid, slug, key), {
      citation_key: key,
      title: meta.title,
      authors: meta.authors,
      journal: meta.journal,
      year: meta.year,
      doi: meta.doi,
      pmid: null,
      bibtex: null,
      cited_in: [],
      created_at: now,
      updated_at: now,
    });
    // Upgrade the finding from inline → registered_ref (overwrite same doc id)
    await setDoc(findingDoc(pid, slug, meta.doi), {
      doi: meta.doi.toLowerCase(),
      kind: "resolved",
      source: "registered_ref",
      ref_citation_key: key,
      crossref_title: meta.title,
      detected_at: now,
      acknowledged: false,
    });
    setActed(`Registered as '${key}'`);
  };

  return (
    <div className="rounded-md border bg-card p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        {citationKey ? (
          <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">{citationKey}</code>
        ) : (
          <Badge variant="outline" className="text-[10px] text-amber-700">inline</Badge>
        )}
        <KindBadge kind={verdict.kind} />
        {doi && (
          <a
            href={`https://doi.org/${doi}`}
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-primary underline underline-offset-2"
          >
            doi:{doi}
          </a>
        )}
      </div>
      {storedTitle && (
        <div className="text-xs text-muted-foreground">stored: {storedTitle}</div>
      )}
      {(verdict.kind === "resolved" ||
        verdict.kind === "title_mismatch" ||
        verdict.kind === "context_mismatch") && (
        <div className="mt-1 text-xs">
          <span className="text-muted-foreground">CrossRef: </span>
          <span className="font-medium">{verdict.meta.title}</span>
          {verdict.kind !== "resolved" && (
            <span className="ml-2 text-[10px] text-muted-foreground">
              ({verdict.sharedWords} shared word{verdict.sharedWords === 1 ? "" : "s"})
            </span>
          )}
        </div>
      )}
      {verdict.kind === "context_mismatch" && (
        <div className="mt-2 rounded border-l-2 border-amber-400 bg-amber-50 p-2 text-[11px] leading-snug text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
          <div className="text-[10px] uppercase tracking-wide text-amber-700">
            Manuscript context ({verdict.worstContext.section})
          </div>
          <div className="italic">"{verdict.worstContext.sentence}"</div>
          <div className="mt-1 text-[10px]">
            The context above and the CrossRef title share fewer than 2
            substantive words — likely a real DOI cited for the wrong paper.
          </div>
        </div>
      )}
      {verdict.kind === "error" && (
        <div className="mt-1 text-xs text-orange-600">{verdict.message}</div>
      )}
      {!acted && (
        <div className="mt-2 flex flex-wrap gap-2">
          {isInline && verdict.kind === "resolved" && (
            <Button size="sm" onClick={() => registerAsReference(verdict.meta)}>
              <BookPlus className="mr-1 h-3 w-3" /> Register as reference
            </Button>
          )}
          {!isInline && verdict.kind === "title_mismatch" && (
            <Button size="sm" variant="outline" onClick={() => acceptCrossrefTitle(verdict.meta)}>
              Use CrossRef title
            </Button>
          )}
          {!isInline && (
            verdict.kind === "unresolved" ||
            verdict.kind === "title_mismatch" ||
            verdict.kind === "context_mismatch"
          ) && (
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

function rowKey(r: RowResult, i: number): string {
  return r.source.kind === "ref" ? `ref:${r.source.ref.id}` : `inline:${r.source.doi}:${i}`;
}

async function deriveAvailableKey(pid: string, slug: string, meta: CrossrefMeta): Promise<string> {
  const base = deriveBase(meta);
  // Check Firestore for collisions; append a-z if needed.
  const { getDoc } = await import("firebase/firestore");
  let candidate = base;
  for (const suffix of ["", ..."abcdefghijklmnopqrstuvwxyz"]) {
    candidate = base + suffix;
    const snap = await getDoc(refDoc(pid, slug, candidate));
    if (!snap.exists()) return candidate;
  }
  throw new Error(`citation_key ${base} exhausted (a–z all taken)`);
}

function deriveBase(meta: CrossrefMeta): string {
  if (meta.authors.length > 0 && meta.year) {
    const surname = (meta.authors[0].split(/\s+/).pop() ?? "").toLowerCase();
    const ascii = surname.replace(/[^a-z]/g, "");
    if (ascii) return `${ascii}${meta.year}`;
  }
  const tail = (meta.doi.split("/").pop() ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");
  return tail || "ref";
}

function refDoc(pid: string, slug: string, citationKey: string) {
  return doc(db, "projects", pid, "papers", slug, "references", citationKey);
}

function findingDoc(pid: string, slug: string, doi: string): DocumentReference {
  const safe = doi.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "_";
  return doc(db, "projects", pid, "papers", slug, "verification_findings", safe);
}

async function writeFinding(
  pid: string,
  slug: string,
  source: Source,
  verdict: Verdict,
): Promise<void> {
  const doi = source.kind === "ref" ? source.ref.doi : source.doi;
  if (!doi) return;  // nothing to key on
  const payload: Record<string, unknown> = {
    doi: doi.toLowerCase(),
    kind: verdict.kind,
    source: source.kind === "ref" ? "registered_ref" : "inline",
    detected_at: new Date().toISOString(),
    acknowledged: false,
  };
  if (source.kind === "ref") {
    payload.ref_citation_key = source.ref.citation_key;
    if (source.ref.title) payload.stored_title = source.ref.title;
  }
  if (
    verdict.kind === "resolved" ||
    verdict.kind === "title_mismatch" ||
    verdict.kind === "context_mismatch"
  ) {
    payload.crossref_title = verdict.meta.title;
    payload.shared_words = verdict.sharedWords;
    if (verdict.kind === "title_mismatch") payload.stored_title = verdict.storedTitle;
    if (verdict.kind === "context_mismatch") {
      payload.context_sentence = verdict.worstContext.sentence;
      payload.context_section = verdict.worstContext.section;
    }
  }
  if (verdict.kind === "error") payload.message = verdict.message;
  await setDoc(findingDoc(pid, slug, doi), payload);
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
  const counts = {
    resolved: 0, unresolved: 0, title_mismatch: 0,
    context_mismatch: 0, missing_doi: 0, error: 0,
  };
  for (const r of rows) counts[r.verdict.kind]++;
  return counts;
}

function SummaryPill({ kind, count }: { kind: keyof ReturnType<typeof countByKind>; count: number }) {
  const styles: Record<typeof kind, string> = {
    resolved: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    unresolved: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    context_mismatch: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
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
    : kind === "context_mismatch" ? "wrong paper"
    : kind === "missing_doi" ? "no DOI"
    : "error";
  const color =
    kind === "resolved" ? "text-green-700"
    : kind === "unresolved" ? "text-red-700"
    : kind === "title_mismatch" ? "text-amber-700"
    : kind === "context_mismatch" ? "text-red-700"
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
