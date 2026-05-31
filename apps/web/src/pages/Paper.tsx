import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addDoc, collection, deleteDoc, doc, onSnapshot, orderBy, query,
  setDoc, updateDoc,
} from "firebase/firestore";
import {
  ArrowLeft, MessageSquare, CheckCircle2, Download, Loader2,
  ImageIcon, BookOpen, ExternalLink, Table2, Activity, Beaker,
  FileText, Layers, Clock, RefreshCw, Share2, FileDown, AlertTriangle,
  Paperclip, UploadCloud, Trash2,
} from "lucide-react";
import { db } from "@/firebase";
import {
  downloadProjectBlobAsText, downloadProjectBlobAsFile, getProjectStorage,
} from "@/projectAuth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Markdown } from "@/components/Markdown";
import { SyncDoisDialog } from "@/components/SyncDoisDialog";
import { SharePaperDialog } from "@/components/SharePaperDialog";
import { SelectionBubble } from "@/components/SelectionBubble";
import { CommentHoverPopover } from "@/components/CommentHoverPopover";
import { CommentsList } from "@/components/CommentsList";
import { ZoomableImage } from "@/components/ZoomableImage";
import type { AnchorTarget } from "@/lib/remarkAnchorMarks";
import { cn } from "@/lib/utils";

interface Section {
  id: string;
  key: string;
  title: string;
  body?: string;
  status?: string;
  sort_order?: number;
  word_count?: number;
}

interface Review {
  id: string;
  section?: string | null;
  comment: string;
  source: string;
  reviewer_name?: string | null;
  status: string;
  severity?: string;
  response?: string | null;
  anchor_text?: string | null;
  manuscript_ref?: string | null;
  created_at?: string;
  resolved_at?: string | null;
}

interface Reference {
  id: string;
  citation_key: string;
  doi?: string | null;
  title?: string;
  authors?: string[] | string | null;
  year?: number | null;
  journal?: string | null;
}

interface Figure {
  id: string;
  figure_number: number;
  title: string;
  caption?: string | null;
  legend?: string | null;
  blob_path?: string | null;
  status?: string;
}

interface PaperTable {
  id: string;
  table_number: number;
  title: string;
  content: string;        // markdown table source
  caption?: string | null;
  status?: string;
}

interface Analysis {
  id: string;
  name: string;
  description?: string | null;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

interface AnalysisRun {
  id: string;
  run_key: string;
  command: string;
  host?: string;
  env_name?: string | null;
  pid?: number | null;
  started_at?: string;
  finished_at?: string | null;
  exit_code?: number | null;
  log_path?: string | null;
}

interface ActivityEntry {
  id: string;
  action: string;
  detail?: Record<string, unknown>;
  actor?: string;
  created_at?: string;
}

interface ExportRow {
  id: string;
  filename?: string;
  format?: string;
  size_bytes?: number;
  blob_path?: string | null;
  csl_filename?: string | null;
  csl_status?: string | null;
  created_at?: string;
  updated_at?: string;
}

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

interface Finding {
  id: string;
  doi: string;
  kind: "resolved" | "unresolved" | "title_mismatch" | "context_mismatch" | "missing_doi" | "error";
  source: "registered_ref" | "inline";
  ref_citation_key?: string;
  stored_title?: string;
  crossref_title?: string;
  shared_words?: number;
  message?: string;
  context_sentence?: string;
  context_section?: string;
  doi_verified?: boolean | null;
  doi_checked_at?: string;
  doi_checked_by?: "sync" | "agent";
  context_verified?: boolean | null;
  context_checked_at?: string;
  context_checked_by?: "sync" | "agent";
  detected_at?: string;
  acknowledged?: boolean;
}

export function Paper() {
  const { pid, slug } = useParams<{ pid: string; slug: string }>();
  const [paper, setPaper] = useState<Record<string, unknown> | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [references, setReferences] = useState<Reference[]>([]);
  const [figures, setFigures] = useState<Figure[]>([]);
  const [tables, setTables] = useState<PaperTable[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [exports, setExports] = useState<ExportRow[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [viewMode, setViewMode] = useState<"sections" | "compiled">("sections");
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [shareOpen, setShareOpen] = useState(false);

  useEffect(() => {
    if (!pid || !slug) return;
    const paperRef = doc(db, "projects", pid, "papers", slug);
    const unsubPaper = onSnapshot(paperRef, (snap) => setPaper(snap.data() ?? null));
    const sectionsRef = collection(paperRef, "sections");
    const unsubSec = onSnapshot(query(sectionsRef, orderBy("sort_order")), (snap) =>
      setSections(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Section, "id">) }))),
    );
    const reviewsRef = collection(paperRef, "reviews");
    const unsubRev = onSnapshot(query(reviewsRef, orderBy("created_at", "desc")), (snap) =>
      setReviews(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Review, "id">) }))),
    );
    const referencesRef = collection(paperRef, "references");
    const unsubRefs = onSnapshot(referencesRef, (snap) =>
      setReferences(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Reference, "id">) }))),
    );
    const figuresRef = collection(paperRef, "figures");
    const unsubFigs = onSnapshot(query(figuresRef, orderBy("figure_number")), (snap) =>
      setFigures(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Figure, "id">) }))),
    );
    const tablesRef = collection(paperRef, "tables");
    const unsubTabs = onSnapshot(query(tablesRef, orderBy("table_number")), (snap) =>
      setTables(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<PaperTable, "id">) }))),
    );
    const analysesRef = collection(paperRef, "analyses");
    const unsubAna = onSnapshot(query(analysesRef, orderBy("created_at", "desc")), (snap) =>
      setAnalyses(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Analysis, "id">) }))),
    );
    const activityRef = collection(paperRef, "activity_log");
    const unsubAct = onSnapshot(
      query(activityRef, orderBy("created_at", "desc")),
      (snap) =>
        setActivity(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<ActivityEntry, "id">) }))),
      () => {/* empty subcollection is fine */},
    );
    const findingsRef = collection(paperRef, "verification_findings");
    const unsubFnd = onSnapshot(
      findingsRef,
      (snap) =>
        setFindings(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Finding, "id">) }))),
      () => {/* empty subcollection is fine */},
    );
    const exportsRef = collection(paperRef, "exports");
    const unsubExp = onSnapshot(
      exportsRef,
      (snap) =>
        setExports(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<ExportRow, "id">) }))),
      () => {/* empty subcollection is fine */},
    );
    const materialsRef = collection(paperRef, "materials");
    const unsubMat = onSnapshot(
      materialsRef,
      (snap) =>
        setMaterials(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Material, "id">) }))),
      () => {/* empty subcollection is fine */},
    );
    return () => {
      unsubPaper(); unsubSec(); unsubRev(); unsubRefs();
      unsubFigs(); unsubTabs(); unsubAna(); unsubAct(); unsubFnd(); unsubExp();
      unsubMat();
    };
  }, [pid, slug]);

  const knownDois = useMemo<ReadonlySet<string>>(
    () => new Set(references.map((r) => r.doi).filter((d): d is string => !!d)),
    [references],
  );

  const mainFigures = useMemo(() => figures.filter((f) => f.figure_number < 101), [figures]);
  const suppFigures = useMemo(() => figures.filter((f) => f.figure_number >= 101), [figures]);
  const mainTables = useMemo(() => tables.filter((t) => t.table_number < 101), [tables]);
  const suppTables = useMemo(() => tables.filter((t) => t.table_number >= 101), [tables]);

  const compiled = useMemo<string>(() => {
    const title = (paper?.title as string) ?? slug ?? "Untitled";
    const lines = [`# ${title}`, ""];
    const ordered = [...sections].sort(
      (a, b) => (a.sort_order ?? 999) - (b.sort_order ?? 999),
    );
    for (const s of ordered) {
      lines.push(`## ${s.title || s.key}`);
      if (s.body) {
        lines.push("");
        lines.push(s.body);
      }
      lines.push("");
    }
    return lines.join("\n");
  }, [paper, sections, slug]);

  const downloadManuscript = async () => {
    if (!pid || !slug) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      const text = await downloadProjectBlobAsText(
        pid,
        `projects/${pid}/papers/${slug}/manuscript.md`,
      );
      const blob = new Blob([text], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${slug}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError((err as Error).message);
    } finally {
      setDownloading(false);
    }
  };

  if (!pid || !slug) return null;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {pid && slug && <SelectionBubble pid={pid} paperSlug={slug} />}
      {pid && slug && (
        <CommentHoverPopover pid={pid} paperSlug={slug} reviews={reviews} />
      )}
      <div>
        <Link
          to={`/projects/${pid}/papers`}
          className="-ml-3 inline-flex h-9 items-center rounded-md px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to project
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h1 className="break-words text-2xl font-bold tracking-tight">
              {(paper?.title as string) ?? slug}
            </h1>
            <p className="text-sm text-muted-foreground">
              {(paper?.journal as string) ?? "no journal"} ·{" "}
              <Badge variant="secondary" className="text-[10px]">
                {(paper?.status as string) ?? "draft"}
              </Badge>
            </p>
          </div>
          <Button
            size="sm" variant="outline"
            onClick={() => setShareOpen(true)}
            className="gap-1"
          >
            <Share2 className="h-4 w-4" /> Share for review
          </Button>
        </div>
      </div>
      {shareOpen && pid && slug && (
        <SharePaperDialog
          pid={pid} slug={slug}
          paperTitle={(paper?.title as string) ?? slug}
          onClose={() => setShareOpen(false)}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-6">
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0">
            <div>
              <CardTitle>Manuscript</CardTitle>
              <CardDescription>
                {sections.length} sections ·{" "}
                {sections.reduce((s, x) => s + (x.word_count ?? 0), 0)} words
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-md border p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setViewMode("sections")}
                  className={cn(
                    "inline-flex items-center gap-1 rounded px-2 py-1 transition-colors",
                    viewMode === "sections"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent",
                  )}
                  aria-pressed={viewMode === "sections"}
                  title="Per-section view with comment buttons"
                >
                  <Layers className="h-3 w-3" /> Sections
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("compiled")}
                  className={cn(
                    "inline-flex items-center gap-1 rounded px-2 py-1 transition-colors",
                    viewMode === "compiled"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent",
                  )}
                  aria-pressed={viewMode === "compiled"}
                  title="Compiled view — single continuous document"
                >
                  <FileText className="h-3 w-3" /> Compiled
                </button>
              </div>
              <Button size="sm" variant="outline" onClick={downloadManuscript} disabled={downloading}>
                {downloading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                {downloading ? "Downloading…" : "Download .md"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {!sections.length ? (
              <p className="text-sm italic text-muted-foreground">
                No sections yet. Create one from Claude Code with{" "}
                <code className="bg-muted px-1 py-0.5 text-xs">/paper-writing</code>.
              </p>
            ) : viewMode === "sections" ? (
              sections.map((s) => (
                <SectionView
                  key={s.id} section={s} pid={pid} paperSlug={slug}
                  knownDois={knownDois} reviews={reviews}
                />
              ))
            ) : (
              <div data-section-key="__compiled__">
                <Markdown className="text-sm" knownDois={knownDois}>{compiled}</Markdown>
              </div>
            )}
            {downloadError && (
              <p className="mt-2 text-xs text-destructive">{downloadError}</p>
            )}
          </CardContent>
        </Card>

        <MaterialsCard pid={pid} slug={slug} materials={materials} />

        {mainFigures.length > 0 && (
          <div className="space-y-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <ImageIcon className="h-5 w-5" /> Figures
            </h2>
            {mainFigures.map((f) => (
              <FigureCard key={f.id} pid={pid} figure={f} knownDois={knownDois} />
            ))}
          </div>
        )}

        {mainTables.length > 0 && (
          <div className="space-y-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Table2 className="h-5 w-5" /> Tables
            </h2>
            {mainTables.map((t) => (
              <TableCard key={t.id} table={t} knownDois={knownDois} />
            ))}
          </div>
        )}

        {suppFigures.length > 0 && (
          <div className="space-y-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <ImageIcon className="h-5 w-5" /> Supplementary Figures
            </h2>
            {suppFigures.map((f) => (
              <FigureCard
                key={f.id} pid={pid} figure={f} knownDois={knownDois}
                supplementary
              />
            ))}
          </div>
        )}

        {suppTables.length > 0 && (
          <div className="space-y-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Table2 className="h-5 w-5" /> Supplementary Tables
            </h2>
            {suppTables.map((t) => (
              <TableCard key={t.id} table={t} knownDois={knownDois} supplementary />
            ))}
          </div>
        )}

        {analyses.length > 0 && (
          <div className="">
            <AnalysesCard pid={pid} paperSlug={slug} analyses={analyses} />
          </div>
        )}

        <div className="">
          <ReferencesCard
            pid={pid} slug={slug} references={references}
            sections={sections} cited={knownDois} findings={findings}
          />
        </div>

        {exports.length > 0 && (
          <div className="">
            <ExportsCard pid={pid} exports={exports} />
          </div>
        )}

        {activity.length > 0 && (
          <div className="">
            <ActivityCard entries={activity} />
          </div>
        )}
        </div>

        {/* Right: persistent comment list — the reliable view of the
            review thread even after edits dissolve the highlights.
            Owner can Resolve / Withdraw straight from a row. */}
        <div className="min-w-0 lg:sticky lg:top-4 lg:self-start">
          <CommentsList
            reviews={reviews}
            onResolve={(id) =>
              updateDoc(
                doc(db, "projects", pid!, "papers", slug!, "reviews", id),
                { status: "resolved", resolved_at: new Date().toISOString() },
              )
            }
            onWithdraw={(id) =>
              updateDoc(
                doc(db, "projects", pid!, "papers", slug!, "reviews", id),
                { status: "rejected", resolved_at: new Date().toISOString() },
              )
            }
          />
        </div>
      </div>
    </div>
  );
}

/** Pick out the open user comments for a given section and return them as
 *  AnchorTarget[] for the Markdown component's remarkAnchorMarks plugin. */
function anchorsForSection(reviews: Review[], _sectionKey: string): AnchorTarget[] {
  // section / manuscript_ref are HINTS — but a comment made in the
  // compiled view lands with section="__compiled__" (no real section
  // owner), and very old comments may have neither field. Always offer
  // every anchored open user comment to the injector and let it match
  // wherever the anchor text actually lives in the body. False matches
  // would require the same exact phrase to appear in two sections,
  // which is rare; missed matches (section filter wrong) were silent.
  // Highlight comments from ALL sources — owner ("user"), shared
  // reviewer via a /shared link ("external"), and AI reviewer ("ai").
  return reviews
    .filter(
      (r) =>
        r.status === "open" &&
        !!r.anchor_text &&
        r.anchor_text.length >= 3,
    )
    .map((r) => ({ text: r.anchor_text!, reviewId: r.id }));
}


function SectionView({ section, pid, paperSlug, knownDois, reviews }: {
  section: Section; pid: string; paperSlug: string;
  knownDois: ReadonlySet<string>;
  reviews: Review[];
}) {
  const [showComment, setShowComment] = useState(false);
  const anchors = useMemo(
    () => anchorsForSection(reviews, section.key),
    [reviews, section.key],
  );
  return (
    <div className="group mb-6 border-l-2 border-transparent pl-4 hover:border-accent">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-semibold">{section.title}</h3>
        <div className="flex items-center gap-2">
          {section.status && (
            <Badge variant="outline" className="text-[10px]">{section.status}</Badge>
          )}
          <Button
            size="sm" variant="ghost"
            className="opacity-0 group-hover:opacity-100"
            onClick={() => setShowComment(!showComment)}
          >
            <MessageSquare className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      {section.body ? (
        <div data-section-key={section.key}>
          <Markdown className="text-sm" knownDois={knownDois} anchors={anchors}>
            {section.body}
          </Markdown>
        </div>
      ) : (
        <p className="text-sm italic text-muted-foreground">empty</p>
      )}
      {showComment && (
        <div className="mt-3">
          <NewCommentBox pid={pid} paperSlug={paperSlug} section={section.key} />
        </div>
      )}
    </div>
  );
}

function ActivityCard({ entries }: { entries: ActivityEntry[] }) {
  const labels: Record<string, string> = {
    paper_created: "Paper created",
    section_updated: "Section updated",
    review_added: "Comment added",
    review_resolved: "Comment resolved",
  };
  const shown = entries.slice(0, 20);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Clock className="h-4 w-4" /> Activity
          <Badge variant="secondary" className="ml-auto text-[10px]">
            {entries.length}
          </Badge>
        </CardTitle>
        <CardDescription>Most recent {shown.length} of {entries.length} events.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {shown.map((e) => {
          const detail = e.detail || {};
          const label = labels[e.action] || e.action;
          const dt = e.created_at ? new Date(e.created_at) : null;
          return (
            <div key={e.id} className="flex items-baseline gap-2 text-xs">
              <Badge
                variant={e.actor === "user" ? "warning" : "outline"}
                className="shrink-0 text-[10px]"
              >
                {e.actor || "system"}
              </Badge>
              <div className="min-w-0 flex-1">
                <div className="font-medium text-foreground">{label}</div>
                <ActivityDetail action={e.action} detail={detail} />
              </div>
              {dt && (
                <time
                  className="shrink-0 text-[10px] text-muted-foreground"
                  dateTime={e.created_at}
                  title={dt.toLocaleString()}
                >
                  {timeAgo(dt)}
                </time>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

function ActivityDetail({ action, detail }: {
  action: string; detail: Record<string, unknown>;
}) {
  if (action === "section_updated") {
    const key = detail.key as string | undefined;
    const wc = detail.word_count as number | undefined;
    return (
      <div className="text-muted-foreground">
        <code className="text-[10px]">{key}</code>
        {wc !== undefined && <span> · {wc} words</span>}
      </div>
    );
  }
  if (action === "review_added") {
    const section = detail.section as string | null;
    const severity = detail.severity as string | undefined;
    return (
      <div className="text-muted-foreground">
        {section && <code className="text-[10px]">{section}</code>}
        {severity && <span> · {severity}</span>}
      </div>
    );
  }
  if (action === "review_resolved") {
    const status = detail.status as string | undefined;
    const preview = detail.response_preview as string | undefined;
    return (
      <div className="text-muted-foreground">
        <span>{status}</span>
        {preview && <span className="ml-1 italic">— {preview}</span>}
      </div>
    );
  }
  if (action === "paper_created") {
    const title = detail.title as string | undefined;
    return <div className="truncate text-muted-foreground">{title}</div>;
  }
  return null;
}

function timeAgo(d: Date): string {
  const diffSec = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (diffSec < 60) return `${Math.floor(diffSec)}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** Renders what citation style an export used — the journal-format check
 *  the user cares about. csl_status comes from the MCP export pipeline. */
function CslLabel({ csl_filename, csl_status }: {
  csl_filename?: string | null; csl_status?: string | null;
}) {
  // Export docs written before the CSL feature have no csl_status.
  if (!csl_status) return null;
  if (csl_status === "downloaded" || csl_status === "explicit") {
    return (
      <span>
        Citation style:{" "}
        <span className="font-medium text-foreground">{csl_filename}</span>
      </span>
    );
  }
  if (csl_status === "missing") {
    return (
      <span className="inline-flex items-center gap-1 text-amber-600">
        <AlertTriangle className="h-3 w-3" />
        {csl_filename ?? "CSL"} not found — default style used
      </span>
    );
  }
  if (csl_status === "no_journal") {
    return <span>No target journal — default citation style</span>;
  }
  // no_references — CSL is moot
  return <span>No references — citation style N/A</span>;
}

function ExportsCard({ pid, exports }: { pid: string; exports: ExportRow[] }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const sorted = useMemo(
    () =>
      [...exports].sort((a, b) =>
        (b.updated_at ?? "").localeCompare(a.updated_at ?? ""),
      ),
    [exports],
  );

  const download = async (e: ExportRow) => {
    if (!e.blob_path || !e.filename) return;
    setBusy(e.id);
    setErr(null);
    try {
      await downloadProjectBlobAsFile(pid, e.blob_path, e.filename);
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileDown className="h-4 w-4" /> Exports
        </CardTitle>
        <CardDescription>
          Files produced by{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
            /paper-export
          </code>{" "}
          — citations formatted for the target journal.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {sorted.map((e) => (
          <div
            key={e.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-2 text-sm"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate font-medium">{e.filename}</span>
                {e.format && (
                  <Badge variant="secondary" className="text-[10px] uppercase">
                    {e.format}
                  </Badge>
                )}
              </div>
              <div className="mt-0.5 text-xs text-muted-foreground">
                <CslLabel
                  csl_filename={e.csl_filename}
                  csl_status={e.csl_status}
                />
                {e.csl_status && (typeof e.size_bytes === "number" || e.updated_at)
                  ? " · "
                  : null}
                {typeof e.size_bytes === "number" && formatBytes(e.size_bytes)}
                {typeof e.size_bytes === "number" && e.updated_at ? " · " : null}
                {e.updated_at && timeAgo(new Date(e.updated_at))}
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={busy === e.id || !e.blob_path}
              onClick={() => download(e)}
            >
              {busy === e.id ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
            </Button>
          </div>
        ))}
        {err && <p className="text-xs text-destructive">{err}</p>}
      </CardContent>
    </Card>
  );
}


const MATERIAL_MAX_BYTES = 25 * 1024 * 1024; // 25 MB

function safeMaterialName(name: string): string {
  const base = name.split(/[/\\]/).pop() || "file";
  const cleaned = base.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[._]+|[._]+$/g, "");
  return (cleaned || "file").slice(0, 120);
}

function newMaterialId(): string {
  // 12-char opaque id, matching the MCP's uuid4().hex[:12] shape.
  const u = (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`).replace(/-/g, "");
  return u.slice(0, 12);
}

/** Reference materials: user-uploaded source files Claude Code reads via the
 *  MCP (list_materials / get_material). Stored at
 *  projects/{pid}/papers/{slug}/materials/ — doc + Storage blob, mirroring
 *  what the MCP writes so files uploaded here are pullable locally. */
function MaterialsCard({ pid, slug, materials }: {
  pid: string; slug: string; materials: Material[];
}) {
  const [busy, setBusy] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const sorted = useMemo(
    () =>
      [...materials].sort((a, b) =>
        (b.created_at ?? "").localeCompare(a.created_at ?? ""),
      ),
    [materials],
  );

  const upload = async (file: File) => {
    setErr(null);
    if (file.size > MATERIAL_MAX_BYTES) {
      setErr(`"${file.name}" is ${formatBytes(file.size)} — over the 25 MB limit.`);
      return;
    }
    setBusy(true);
    try {
      const materialId = newMaterialId();
      const filename = safeMaterialName(file.name);
      const blobPath = `projects/${pid}/papers/${slug}/materials/${materialId}__${filename}`;
      const { ref, uploadBytes } = await import("firebase/storage");
      const storage = await getProjectStorage(pid);
      await uploadBytes(ref(storage, blobPath), file, {
        contentType: file.type || "application/octet-stream",
      });
      const now = new Date().toISOString();
      await setDoc(
        doc(db, "projects", pid, "papers", slug, "materials", materialId),
        {
          material_id: materialId,
          filename,
          content_type: file.type || "application/octet-stream",
          size_bytes: file.size,
          blob_path: blobPath,
          description: null,
          uploaded_by: "user",
          created_at: now,
          updated_at: now,
        },
      );
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
      await deleteDoc(doc(db, "projects", pid, "papers", slug, "materials", m.material_id));
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
            <Paperclip className="h-4 w-4" /> Reference materials
          </CardTitle>
          <CardDescription>
            Source files for Claude Code to consult — PDFs, datasets, prior
            drafts, notes. Pull them locally with{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
              list_materials
            </code>{" "}
            /{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
              get_material
            </code>
            .
          </CardDescription>
        </div>
        <label
          className={cn(
            buttonVariants({ variant: "outline", size: "sm" }),
            busy ? "pointer-events-none opacity-50" : "cursor-pointer",
          )}
        >
          <input type="file" multiple className="hidden" onChange={onPick} disabled={busy} />
          {busy ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <UploadCloud className="mr-2 h-4 w-4" />
          )}
          {busy ? "Uploading…" : "Upload"}
        </label>
      </CardHeader>
      <CardContent className="space-y-2">
        {sorted.length === 0 ? (
          <p className="text-sm italic text-muted-foreground">
            No materials yet. Upload files here and Claude Code can read them
            via the MCP.
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
                  {typeof m.size_bytes === "number" && m.created_at ? " · " : null}
                  {m.created_at && timeAgo(new Date(m.created_at))}
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


function AnalysesCard({ pid, paperSlug, analyses }: {
  pid: string; paperSlug: string; analyses: Analysis[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Beaker className="h-4 w-4" /> Analyses
          <Badge variant="secondary" className="ml-auto text-[10px]">
            {analyses.length}
          </Badge>
        </CardTitle>
        <CardDescription>
          Named pipelines run from Claude Code via{" "}
          <code className="bg-muted px-1 py-0.5 text-[10px]">/analysis-run</code>.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {analyses.map((a) => (
          <AnalysisRow key={a.id} pid={pid} paperSlug={paperSlug} analysis={a} />
        ))}
      </CardContent>
    </Card>
  );
}


function AnalysisRow({ pid, paperSlug, analysis }: {
  pid: string; paperSlug: string; analysis: Analysis;
}) {
  // Lazy-listen to the runs subcollection: get the latest run for status.
  const [latest, setLatest] = useState<AnalysisRun | null>(null);
  const [runCount, setRunCount] = useState(0);

  useEffect(() => {
    const runsRef = collection(
      db, "projects", pid, "papers", paperSlug,
      "analyses", analysis.id, "runs",
    );
    const unsub = onSnapshot(
      query(runsRef, orderBy("started_at", "desc")),
      (snap) => {
        setRunCount(snap.size);
        setLatest((snap.docs[0]?.data() as AnalysisRun) ?? null);
      },
      () => {/* swallow — empty subcollection is fine */},
    );
    return unsub;
  }, [pid, paperSlug, analysis.id]);

  const isRunning = latest && !latest.finished_at;
  const success = latest?.exit_code === 0;

  return (
    <div className="space-y-1 border-l-2 border-muted pl-3 text-sm">
      <div className="flex flex-wrap items-baseline gap-2">
        <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
          {analysis.name}
        </code>
        {analysis.status && (
          <Badge variant="outline" className="text-[10px]">{analysis.status}</Badge>
        )}
        <span className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground">
          <Activity className="h-3 w-3" /> {runCount} run{runCount === 1 ? "" : "s"}
        </span>
      </div>
      {analysis.description && (
        <div className="text-xs text-muted-foreground">{analysis.description}</div>
      )}
      {latest && (
        <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
          {isRunning ? (
            <Badge variant="warning" className="text-[10px]">
              <Loader2 className="mr-1 h-3 w-3 animate-spin" /> running
            </Badge>
          ) : success ? (
            <Badge variant="success" className="text-[10px]">
              <CheckCircle2 className="mr-1 h-3 w-3" /> exit 0
            </Badge>
          ) : (
            <Badge variant="destructive" className="text-[10px]">
              exit {latest.exit_code ?? "?"}
            </Badge>
          )}
          {latest.host && <span>host: {latest.host}</span>}
          {latest.started_at && (
            <span>started {new Date(latest.started_at).toLocaleString()}</span>
          )}
        </div>
      )}
    </div>
  );
}


function VerificationRibbons({ finding }: { finding?: Finding }) {
  const { doi, ctx } = deriveAxes(finding);
  return (
    <div className="flex items-center gap-1">
      <Ribbon
        label="DOI"
        state={doi === true ? "ok" : doi === false ? "bad" : "unknown"}
        title={
          doi === true ? "CrossRef found this DOI"
          : doi === false ? "CrossRef returned 404 — hallucinated DOI"
          : "DOI not yet verified — click Sync DOIs"
        }
      />
      <Ribbon
        label="Context"
        state={ctx === true ? "ok" : ctx === false ? "bad" : "unknown"}
        title={
          ctx === true ? "Manuscript context matches the cited paper"
          : ctx === false ? "Manuscript context doesn't match the cited paper (likely a real DOI on the wrong paper)"
          : "Context not yet verified — run validate_references() in Claude Code"
        }
      />
    </div>
  );
}

/** Read explicit doi_verified/context_verified flags if set, else derive
 *  from the legacy `kind` field. Old findings (pre two-axis model) only
 *  have `kind`; new findings have explicit booleans. */
function deriveAxes(f?: Finding): {
  doi: boolean | null; ctx: boolean | null;
} {
  if (!f) return { doi: null, ctx: null };
  const explicit_doi = f.doi_verified;
  const explicit_ctx = f.context_verified;
  const has_explicit = explicit_doi !== undefined || explicit_ctx !== undefined;
  if (has_explicit) {
    return {
      doi: explicit_doi === undefined ? null : explicit_doi,
      ctx: explicit_ctx === undefined ? null : explicit_ctx,
    };
  }
  // Legacy fallback — infer from kind. Conservative: don't claim a
  // context check that may have been done by an obsolete browser sync.
  switch (f.kind) {
    case "resolved":         return { doi: true,  ctx: null };
    case "unresolved":       return { doi: false, ctx: null };
    case "title_mismatch":   return { doi: true,  ctx: null };
    case "context_mismatch": return { doi: true,  ctx: false };
    case "missing_doi":      return { doi: null,  ctx: null };
    case "error":            return { doi: null,  ctx: null };
    default:                 return { doi: null,  ctx: null };
  }
}

function Ribbon({ label, state, title }: {
  label: string;
  state: "ok" | "bad" | "unknown";
  title: string;
}) {
  const styles =
    state === "ok"
      ? "border-green-300 bg-green-50 text-green-700"
    : state === "bad"
      ? "border-red-300 bg-red-50 text-red-700"
      : "border-muted text-muted-foreground";
  const mark = state === "ok" ? "✓" : state === "bad" ? "✗" : "?";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0 text-[9px] font-medium ${styles}`}
      title={title}
    >
      <span>{mark}</span>
      <span>{label}</span>
    </span>
  );
}


function ReferencesCard({ pid, slug, references, sections, cited, findings }: {
  pid: string;
  slug: string;
  references: Reference[];
  sections: Section[];
  cited: ReadonlySet<string>;
  findings: Finding[];
}) {
  const problemFindings = useMemo(
    () => findings.filter((f) => !f.acknowledged && f.kind !== "resolved"),
    [findings],
  );
  const findingByDoi = useMemo(() => {
    const m = new Map<string, Finding>();
    for (const f of findings) if (f.doi) m.set(f.doi.toLowerCase(), f);
    return m;
  }, [findings]);
  const [syncOpen, setSyncOpen] = useState(false);
  const sorted = [...references].sort((a, b) =>
    (a.citation_key || "").localeCompare(b.citation_key || ""),
  );
  // Find inline {doi:...} citations in section bodies that aren't yet
  // registered as references — counts as "to verify".
  const inlineDois = useMemo(() => {
    const found = new Set<string>();
    const re = /\{doi:([^}\s]+)\}/gi;
    for (const sec of sections) {
      const body = sec.body || "";
      let m: RegExpExecArray | null;
      while ((m = re.exec(body)) !== null) found.add(m[1].toLowerCase());
    }
    // Subtract DOIs already registered as references
    for (const d of cited) found.delete(d.toLowerCase());
    return found;
  }, [sections, cited]);
  const toVerifyCount = references.length + inlineDois.size;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BookOpen className="h-4 w-4" /> References
          <Badge variant="secondary" className="text-[10px]">
            {references.length}
            {inlineDois.size > 0 && (
              <span className="ml-1 text-amber-700">+{inlineDois.size}</span>
            )}
          </Badge>
          {problemFindings.length > 0 && (
            <Badge
              variant="outline"
              className="border-red-300 bg-red-50 text-[10px] text-red-700"
              title="Unacknowledged verification problems"
            >
              ⚠ {problemFindings.length}
            </Badge>
          )}
          <Button
            size="sm"
            variant="outline"
            className="ml-auto h-7 gap-1 text-xs"
            onClick={() => setSyncOpen(true)}
            disabled={toVerifyCount === 0}
            title="Verify every DOI against CrossRef"
          >
            <RefreshCw className="h-3 w-3" /> Sync DOIs
          </Button>
        </CardTitle>
        <CardDescription>
          Two verifications per citation:{" "}
          <span className="font-medium">DOI</span> (Sync DOIs button —
          CrossRef existence) and{" "}
          <span className="font-medium">Context</span> (
          <code className="bg-muted px-1 py-0.5 text-[10px]">
            validate_references
          </code>{" "}
          in Claude Code — manuscript semantics). Both green = trusted.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {sorted.map((r) => {
          const authors = Array.isArray(r.authors)
            ? r.authors.join(", ")
            : r.authors || "";
          const doiUrl = r.doi ? `https://doi.org/${r.doi}` : null;
          const finding = r.doi ? findingByDoi.get(r.doi.toLowerCase()) : undefined;
          return (
            <div key={r.id} className="space-y-1 border-l-2 border-muted pl-3 text-sm">
              <div className="flex flex-wrap items-baseline gap-2">
                <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
                  {r.citation_key}
                </code>
                {r.year && (
                  <span className="text-xs text-muted-foreground">{r.year}</span>
                )}
                <VerificationRibbons finding={finding} />
              </div>
              {r.title && <div className="font-medium">{r.title}</div>}
              {authors && (
                <div className="text-xs text-muted-foreground">{authors}</div>
              )}
              {(r.journal || doiUrl) && (
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  {r.journal && (
                    <span className="italic text-muted-foreground">{r.journal}</span>
                  )}
                  {doiUrl && (
                    <a
                      href={doiUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-0.5 text-primary underline underline-offset-2 hover:no-underline"
                    >
                      doi:{r.doi}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
      {syncOpen && (
        <SyncDoisDialog
          pid={pid}
          slug={slug}
          references={references}
          inlineDois={[...inlineDois]}
          onClose={() => setSyncOpen(false)}
        />
      )}
    </Card>
  );
}


function TableCard({ table, knownDois, supplementary = false }: {
  table: PaperTable;
  knownDois: ReadonlySet<string>;
  supplementary?: boolean;
}) {
  const displayNum = supplementary ? table.table_number - 100 : table.table_number;
  const label = supplementary ? `STab ${displayNum}` : `Tab ${displayNum}`;
  return (
    <Card id={`table-${table.table_number}`} className="scroll-mt-4">
      <CardHeader>
        <CardTitle className="flex items-baseline gap-2 text-base">
          <span className={cn(
            "rounded px-1.5 py-0.5 text-xs",
            supplementary
              ? "bg-secondary text-secondary-foreground"
              : "bg-primary text-primary-foreground",
          )}>
            {label}
          </span>
          <span className="flex-1 truncate">{table.title}</span>
          {table.status && (
            <Badge variant="outline" className="text-[10px]">{table.status}</Badge>
          )}
        </CardTitle>
        {table.caption && <CardDescription>{table.caption}</CardDescription>}
      </CardHeader>
      <CardContent>
        {table.content ? (
          <Markdown className="text-xs" knownDois={knownDois}>{table.content}</Markdown>
        ) : (
          <p className="text-xs italic text-muted-foreground">no content yet</p>
        )}
      </CardContent>
    </Card>
  );
}


function FigureCard({ pid, figure, knownDois, supplementary = false }: {
  pid: string; figure: Figure; knownDois: ReadonlySet<string>;
  supplementary?: boolean;
}) {
  const displayNum = supplementary ? figure.figure_number - 100 : figure.figure_number;
  const label = supplementary ? `SFig ${displayNum}` : `Fig ${displayNum}`;
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [imgError, setImgError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!figure.blob_path) return;
    (async () => {
      try {
        const storage = await getProjectStorage(pid);
        const { getDownloadURL, ref } = await import("firebase/storage");
        const url = await getDownloadURL(ref(storage, figure.blob_path!));
        if (!cancelled) setImgUrl(url);
      } catch (err) {
        if (!cancelled) setImgError((err as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, [pid, figure.blob_path]);

  return (
    <Card id={`figure-${figure.figure_number}`} className="scroll-mt-4">
      <CardHeader>
        <CardTitle className="flex items-baseline gap-2 text-base">
          <span className={cn(
            "rounded px-1.5 py-0.5 text-xs",
            supplementary
              ? "bg-secondary text-secondary-foreground"
              : "bg-primary text-primary-foreground",
          )}>
            {label}
          </span>
          <span className="flex-1 truncate">{figure.title}</span>
          {figure.status && (
            <Badge variant="outline" className="text-[10px]">{figure.status}</Badge>
          )}
        </CardTitle>
        {figure.caption && (
          <CardDescription>{figure.caption}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {figure.blob_path ? (
          imgUrl ? (
            <ZoomableImage
              src={imgUrl}
              alt={figure.title}
              className="max-h-[400px] w-auto max-w-full rounded border"
            />
          ) : imgError ? (
            <p className="text-xs italic text-destructive">image: {imgError}</p>
          ) : (
            <p className="text-xs italic text-muted-foreground">loading image…</p>
          )
        ) : (
          <p className="text-xs italic text-muted-foreground">
            no image uploaded yet
          </p>
        )}
        {figure.legend && (
          <Markdown className="text-xs text-muted-foreground" knownDois={knownDois}>
            {figure.legend}
          </Markdown>
        )}
      </CardContent>
    </Card>
  );
}


function NewCommentBox({ pid, paperSlug, section }: { pid: string; paperSlug: string; section?: string }) {
  const [text, setText] = useState("");
  const [severity, setSeverity] = useState<"minor" | "major" | "suggestion">("minor");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    try {
      const reviewsRef = collection(db, "projects", pid, "papers", paperSlug, "reviews");
      await addDoc(reviewsRef, {
        source: "user",
        reviewer_name: "User",
        section: section ?? null,
        severity,
        status: "open",
        comment: text,
        response: null,
        created_at: new Date().toISOString(),
        resolved_at: null,
      });
      setText("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-2">
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={section ? `comment on ${section}…` : "general comment…"}
        rows={3}
      />
      <div className="flex items-center gap-2">
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value as "minor" | "major" | "suggestion")}
          className="h-8 rounded-md border bg-background px-2 text-xs"
        >
          <option value="minor">minor</option>
          <option value="major">major</option>
          <option value="suggestion">suggestion</option>
        </select>
        <Button type="submit" size="sm" disabled={busy || !text.trim()}>
          {busy ? "…" : "Send"}
        </Button>
      </div>
    </form>
  );
}
