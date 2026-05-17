import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addDoc, collection, doc, onSnapshot, orderBy, query, updateDoc,
} from "firebase/firestore";
import {
  ArrowLeft, MessageSquare, CheckCircle2, XCircle, Download, Loader2,
  ImageIcon, BookOpen, ExternalLink, Table2, Activity, Beaker,
} from "lucide-react";
import { db } from "@/firebase";
import { downloadProjectBlobAsText, getProjectStorage } from "@/projectAuth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Markdown } from "@/components/Markdown";

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
  status: string;
  severity?: string;
  response?: string | null;
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

export function Paper() {
  const { pid, slug } = useParams<{ pid: string; slug: string }>();
  const [paper, setPaper] = useState<Record<string, unknown> | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [references, setReferences] = useState<Reference[]>([]);
  const [figures, setFigures] = useState<Figure[]>([]);
  const [tables, setTables] = useState<PaperTable[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

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
    return () => {
      unsubPaper(); unsubSec(); unsubRev(); unsubRefs();
      unsubFigs(); unsubTabs(); unsubAna();
    };
  }, [pid, slug]);

  const knownDois = useMemo<ReadonlySet<string>>(
    () => new Set(references.map((r) => r.doi).filter((d): d is string => !!d)),
    [references],
  );

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

  const openComments = reviews.filter((r) => r.status === "open" && r.source === "user");

  return (
    <div className="space-y-6">
      <div>
        <Link
          to={`/projects/${pid}/papers`}
          className="-ml-3 inline-flex h-9 items-center rounded-md px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to project
        </Link>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">
          {(paper?.title as string) ?? slug}
        </h1>
        <p className="text-sm text-muted-foreground">
          {(paper?.journal as string) ?? "no journal"} ·{" "}
          <Badge variant="secondary" className="text-[10px]">
            {(paper?.status as string) ?? "draft"}
          </Badge>
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Card>
          <CardHeader className="flex flex-row items-start justify-between space-y-0">
            <div>
              <CardTitle>Manuscript</CardTitle>
              <CardDescription>
                {sections.length} sections ·{" "}
                {sections.reduce((s, x) => s + (x.word_count ?? 0), 0)} words
              </CardDescription>
            </div>
            <Button size="sm" variant="outline" onClick={downloadManuscript} disabled={downloading}>
              {downloading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              {downloading ? "Downloading…" : "Download .md"}
            </Button>
          </CardHeader>
          <CardContent>
            {sections.map((s) => (
              <SectionView key={s.id} section={s} pid={pid} paperSlug={slug} knownDois={knownDois} />
            ))}
            {!sections.length && (
              <p className="text-sm italic text-muted-foreground">
                No sections yet. Create one from Claude Code with{" "}
                <code className="bg-muted px-1 py-0.5 text-xs">/paper-writing</code>.
              </p>
            )}
            {downloadError && (
              <p className="mt-2 text-xs text-destructive">{downloadError}</p>
            )}
          </CardContent>
        </Card>

        {figures.length > 0 && (
          <div className="lg:col-span-1 space-y-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <ImageIcon className="h-5 w-5" /> Figures
            </h2>
            {figures.map((f) => (
              <FigureCard key={f.id} pid={pid} figure={f} knownDois={knownDois} />
            ))}
          </div>
        )}

        {tables.length > 0 && (
          <div className="lg:col-span-1 space-y-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Table2 className="h-5 w-5" /> Tables
            </h2>
            {tables.map((t) => (
              <TableCard key={t.id} table={t} knownDois={knownDois} />
            ))}
          </div>
        )}

        {analyses.length > 0 && (
          <div className="lg:col-span-1">
            <AnalysesCard pid={pid} paperSlug={slug} analyses={analyses} />
          </div>
        )}

        {references.length > 0 && (
          <div className="lg:col-span-1">
            <ReferencesCard references={references} cited={knownDois} />
          </div>
        )}

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <MessageSquare className="h-4 w-4" /> Comments
                {openComments.length > 0 && (
                  <Badge variant="warning" className="ml-auto">
                    {openComments.length} open
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Comments here are picked up by Claude Code on its next session.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <NewCommentBox pid={pid} paperSlug={slug} />
            </CardContent>
          </Card>

          {reviews.map((r) => (
            <ReviewView key={r.id} review={r} pid={pid} paperSlug={slug} knownDois={knownDois} />
          ))}
        </div>
      </div>
    </div>
  );
}

function SectionView({ section, pid, paperSlug, knownDois }: {
  section: Section; pid: string; paperSlug: string; knownDois: ReadonlySet<string>;
}) {
  const [showComment, setShowComment] = useState(false);
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
        <Markdown className="text-sm" knownDois={knownDois}>{section.body}</Markdown>
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


function ReferencesCard({ references, cited }: {
  references: Reference[];
  cited: ReadonlySet<string>;  // DOIs that appear in /references — same Set we use for badges
}) {
  // Sort: alphabetical by citation_key (matches BibTeX export order)
  const sorted = [...references].sort((a, b) =>
    (a.citation_key || "").localeCompare(b.citation_key || ""),
  );
  void cited; // currently every registered reference is "cited" by virtue of being registered

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BookOpen className="h-4 w-4" /> References
          <Badge variant="secondary" className="ml-auto text-[10px]">
            {references.length}
          </Badge>
        </CardTitle>
        <CardDescription>
          Registered via{" "}
          <code className="bg-muted px-1 py-0.5 text-[10px]">
            mcp__co_scientist__add_reference
          </code>{" "}
          (manually or by DOI/PMID lookup).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {sorted.map((r) => {
          const authors = Array.isArray(r.authors)
            ? r.authors.join(", ")
            : r.authors || "";
          const doiUrl = r.doi ? `https://doi.org/${r.doi}` : null;
          return (
            <div key={r.id} className="space-y-1 border-l-2 border-muted pl-3 text-sm">
              <div className="flex items-baseline gap-2">
                <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
                  {r.citation_key}
                </code>
                {r.year && (
                  <span className="text-xs text-muted-foreground">{r.year}</span>
                )}
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
    </Card>
  );
}


function TableCard({ table, knownDois }: {
  table: PaperTable;
  knownDois: ReadonlySet<string>;
}) {
  return (
    <Card id={`table-${table.table_number}`} className="scroll-mt-4">
      <CardHeader>
        <CardTitle className="flex items-baseline gap-2 text-base">
          <span className="rounded bg-primary px-1.5 py-0.5 text-xs text-primary-foreground">
            Tab {table.table_number}
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


function FigureCard({ pid, figure, knownDois }: {
  pid: string; figure: Figure; knownDois: ReadonlySet<string>;
}) {
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
          <span className="rounded bg-primary px-1.5 py-0.5 text-xs text-primary-foreground">
            Fig {figure.figure_number}
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
            <img
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

function ReviewView({ review, pid, paperSlug, knownDois }: {
  review: Review; pid: string; paperSlug: string; knownDois: ReadonlySet<string>;
}) {
  const isResolved = review.status !== "open";
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant={review.source === "ai" ? "secondary" : "outline"} className="text-[10px]">
            {review.source}
          </Badge>
          {review.section && (
            <Badge variant="outline" className="text-[10px]">{review.section}</Badge>
          )}
          {review.severity && (
            <Badge
              variant={review.severity === "major" ? "destructive" : "outline"}
              className="text-[10px]"
            >
              {review.severity}
            </Badge>
          )}
          {isResolved ? (
            <CheckCircle2 className="ml-auto h-3.5 w-3.5 text-emerald-500" />
          ) : null}
        </div>
        <Markdown className="text-sm" knownDois={knownDois}>{review.comment}</Markdown>
        {review.response && (
          <div className="rounded-md bg-muted p-2 text-xs">
            <div className="mb-1 font-medium">Claude's response:</div>
            <Markdown className="text-xs" knownDois={knownDois}>{review.response}</Markdown>
          </div>
        )}
        {!isResolved && (
          <div className="flex gap-2">
            <Button
              size="sm" variant="ghost"
              onClick={() => updateDoc(
                doc(db, "projects", pid, "papers", paperSlug, "reviews", review.id),
                { status: "rejected", resolved_at: new Date().toISOString() },
              )}
            >
              <XCircle className="mr-1 h-3 w-3" /> Withdraw
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
