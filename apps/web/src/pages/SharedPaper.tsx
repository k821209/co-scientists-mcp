import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { collection, doc, onSnapshot, orderBy, query } from "firebase/firestore";
import { MessageSquare, Pencil, ImageIcon, Table2, BookOpen, ExternalLink } from "lucide-react";
import { Markdown } from "@/components/Markdown";
import { SelectionBubble } from "@/components/SelectionBubble";
import { CommentHoverPopover } from "@/components/CommentHoverPopover";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { openShareSession, type ShareSession } from "@/shareAuth";
import { randomReviewerName } from "@/lib/randomName";
import type { AnchorTarget } from "@/lib/remarkAnchorMarks";

interface Section {
  id: string;
  key: string;
  title: string;
  body?: string;
  sort_order?: number;
}
interface Review {
  id: string;
  section?: string | null;
  comment: string;
  source: string;
  status: string;
  severity?: string;
  anchor_text?: string | null;
  manuscript_ref?: string | null;
}
interface Figure {
  id: string;
  figure_number: number;
  title: string;
  caption?: string | null;
  legend?: string | null;
  blob_path?: string | null;
}
interface PaperTable {
  id: string;
  table_number: number;
  title: string;
  content: string;
  caption?: string | null;
}
interface Reference {
  id: string;
  citation_key: string;
  title?: string;
  authors?: string[] | string | null;
  year?: number | null;
  journal?: string | null;
  doi?: string | null;
}

const NAME_STORAGE_KEY = "cs-shared-reviewer-name";
const RANDOM_NAME_KEY = "cs-shared-random-name";

export function SharedPaper() {
  const { pid, slug, shareId } = useParams<{
    pid: string; slug: string; shareId: string;
  }>();
  const [session, setSession] = useState<ShareSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paper, setPaper] = useState<Record<string, unknown> | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [figures, setFigures] = useState<Figure[]>([]);
  const [tables, setTables] = useState<PaperTable[]>([]);
  const [references, setReferences] = useState<Reference[]>([]);

  // Reviewer name — persisted in localStorage so it survives reloads.
  const [name, setName] = useState<string>(() => {
    return localStorage.getItem(NAME_STORAGE_KEY) || "";
  });
  // Random fallback name — also persisted so a no-name reviewer keeps the
  // SAME identity across reloads in this browser. Multiple people on the
  // same link each get their own (their browser's localStorage differs).
  const [randomName] = useState(() => {
    const saved = localStorage.getItem(RANDOM_NAME_KEY);
    if (saved) return saved;
    const fresh = randomReviewerName();
    localStorage.setItem(RANDOM_NAME_KEY, fresh);
    return fresh;
  });
  const effectiveName = name.trim() || randomName;
  useEffect(() => {
    if (name.trim()) localStorage.setItem(NAME_STORAGE_KEY, name.trim());
  }, [name]);

  // 1. Exchange the share link for an authed session.
  useEffect(() => {
    if (!pid || !slug || !shareId) {
      setError("Malformed share link.");
      return;
    }
    let cancelled = false;
    openShareSession(pid, slug, shareId)
      .then((s) => { if (!cancelled) setSession(s); })
      .catch((e) => { if (!cancelled) setError((e as Error).message); });
    return () => { cancelled = true; };
  }, [pid, slug, shareId]);

  // 2. Once authed, subscribe to paper + sections + reviews.
  useEffect(() => {
    if (!session) return;
    const { db, pid: p, slug: s } = session;
    const paperRef = doc(db, "projects", p, "papers", s);
    const u1 = onSnapshot(paperRef, (snap) => setPaper(snap.data() ?? null));
    const u2 = onSnapshot(
      query(collection(paperRef, "sections"), orderBy("sort_order")),
      (snap) => setSections(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Section, "id">) }))),
      () => {/* empty ok */},
    );
    const u3 = onSnapshot(
      collection(paperRef, "reviews"),
      (snap) => setReviews(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Review, "id">) }))),
      () => {/* empty ok */},
    );
    const u4 = onSnapshot(
      query(collection(paperRef, "figures"), orderBy("figure_number")),
      (snap) => setFigures(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Figure, "id">) }))),
      () => {/* empty ok */},
    );
    const u5 = onSnapshot(
      query(collection(paperRef, "tables"), orderBy("table_number")),
      (snap) => setTables(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<PaperTable, "id">) }))),
      () => {/* empty ok */},
    );
    const u6 = onSnapshot(
      collection(paperRef, "references"),
      (snap) => setReferences(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Reference, "id">) }))),
      () => {/* empty ok */},
    );
    return () => { u1(); u2(); u3(); u4(); u5(); u6(); };
  }, [session]);

  if (error) {
    return (
      <div className="mx-auto max-w-lg p-8">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Can't open this paper</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">{error}</CardContent>
        </Card>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Opening shared paper…
      </div>
    );
  }

  const title = (paper?.title as string) ?? session.paperTitle ?? slug;

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-8">
      {/* Name banner */}
      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 p-4">
          <Pencil className="h-4 w-4 shrink-0 text-muted-foreground" />
          <label className="text-sm font-medium" htmlFor="reviewer-name">
            Commenting as
          </label>
          <Input
            id="reviewer-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={randomName}
            className="h-8 max-w-[200px]"
          />
          <span className="text-xs text-muted-foreground">
            {name.trim()
              ? "Your comments are signed with this name."
              : `No name set — comments are signed "${randomName}".`}
          </span>
        </CardContent>
      </Card>

      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        <p className="text-sm text-muted-foreground">
          {(paper?.journal as string) ?? "shared for review"} · read-only —
          drag-select any text to leave a comment
        </p>
      </div>

      {/* Comment tooling */}
      <SelectionBubble
        pid={session.pid}
        paperSlug={session.slug}
        reviewSource="external"
        reviewerName={effectiveName}
        firestore={session.db}
      />
      <CommentHoverPopover
        pid={session.pid}
        paperSlug={session.slug}
        reviews={reviews}
        readOnly
        firestore={session.db}
      />

      {/* Manuscript */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquare className="h-4 w-4" /> Manuscript
            <Badge variant="secondary" className="ml-auto text-[10px]">
              {reviews.filter((r) => r.status === "open").length} open comments
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {sections.length === 0 && (
            <p className="text-sm italic text-muted-foreground">
              No sections yet.
            </p>
          )}
          {sections.map((s) => (
            <SharedSection key={s.id} section={s} reviews={reviews} />
          ))}
        </CardContent>
      </Card>

      {/* Figures */}
      {figures.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ImageIcon className="h-4 w-4" /> Figures
              <Badge variant="secondary" className="ml-auto text-[10px]">
                {figures.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {figures.map((f) => (
              <SharedFigure key={f.id} figure={f} storage={session.storage} />
            ))}
          </CardContent>
        </Card>
      )}

      {/* Tables */}
      {tables.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Table2 className="h-4 w-4" /> Tables
              <Badge variant="secondary" className="ml-auto text-[10px]">
                {tables.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {tables.map((t) => (
              <div key={t.id}>
                <div className="mb-1 text-sm font-semibold">
                  Table {t.table_number >= 101 ? `S${t.table_number - 100}` : t.table_number}
                  {" — "}{t.title}
                </div>
                {t.caption && (
                  <p className="mb-1 text-xs text-muted-foreground">{t.caption}</p>
                )}
                <Markdown className="text-xs">{t.content}</Markdown>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* References */}
      {references.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BookOpen className="h-4 w-4" /> References
              <Badge variant="secondary" className="ml-auto text-[10px]">
                {references.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {[...references]
              .sort((a, b) => (a.citation_key || "").localeCompare(b.citation_key || ""))
              .map((r) => {
                const authors = Array.isArray(r.authors)
                  ? r.authors.join(", ")
                  : r.authors || "";
                return (
                  <div key={r.id} className="border-l-2 border-muted pl-3 text-sm">
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
                    {(r.journal || r.doi) && (
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        {r.journal && (
                          <span className="italic text-muted-foreground">{r.journal}</span>
                        )}
                        {r.doi && (
                          <a
                            href={`https://doi.org/${r.doi}`}
                            target="_blank" rel="noreferrer"
                            className="inline-flex items-center gap-0.5 text-primary underline underline-offset-2"
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
      )}
    </div>
  );
}

function SharedFigure({ figure, storage }: {
  figure: Figure; storage: ShareSession["storage"];
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!figure.blob_path) return;
    let cancelled = false;
    (async () => {
      try {
        const { getDownloadURL, ref } = await import("firebase/storage");
        const u = await getDownloadURL(ref(storage, figure.blob_path!));
        if (!cancelled) setUrl(u);
      } catch (e) {
        if (!cancelled) setErr((e as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, [figure.blob_path, storage]);
  const supp = figure.figure_number >= 101;
  const label = supp ? `SFig ${figure.figure_number - 100}` : `Fig ${figure.figure_number}`;
  return (
    <div>
      <div className="mb-1 text-sm font-semibold">{label} — {figure.title}</div>
      {figure.caption && (
        <p className="mb-1 text-xs text-muted-foreground">{figure.caption}</p>
      )}
      {figure.blob_path ? (
        url ? (
          <img src={url} alt={figure.title}
               className="max-h-[400px] w-auto max-w-full rounded border" />
        ) : err ? (
          <p className="text-xs italic text-destructive">image: {err}</p>
        ) : (
          <p className="text-xs italic text-muted-foreground">loading image…</p>
        )
      ) : (
        <p className="text-xs italic text-muted-foreground">no image</p>
      )}
      {figure.legend && (
        <p className="mt-1 text-xs text-muted-foreground">{figure.legend}</p>
      )}
    </div>
  );
}

function SharedSection({ section, reviews }: {
  section: Section; reviews: Review[];
}) {
  const anchors = useMemo<AnchorTarget[]>(
    () =>
      reviews
        .filter(
          (r) =>
            r.status === "open" &&
            !!r.anchor_text &&
            r.anchor_text.length >= 3,
        )
        .map((r) => ({ text: r.anchor_text!, reviewId: r.id })),
    [reviews],
  );
  return (
    <div>
      <h3 className="mb-2 font-semibold">{section.title}</h3>
      {section.body ? (
        <div data-section-key={section.key}>
          <Markdown className="text-sm" anchors={anchors}>{section.body}</Markdown>
        </div>
      ) : (
        <p className="text-sm italic text-muted-foreground">empty</p>
      )}
    </div>
  );
}
