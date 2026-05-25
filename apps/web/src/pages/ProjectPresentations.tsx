import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useOutletContext } from "react-router-dom";
import {
  addDoc, collection, doc, onSnapshot, updateDoc,
} from "firebase/firestore";
import {
  Presentation, FileText, ArrowRight, ChevronDown, ChevronRight, Download,
  MessageSquare, ArrowUp, ArrowDown, Check, Loader2, Play, X, ChevronLeft,
  StickyNote,
} from "lucide-react";
import { db } from "@/firebase";
import { useAuth } from "@/auth";
import { downloadProjectBlobAsFile, getProjectStorage } from "@/projectAuth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { type ProjectContext } from "./ProjectShell";

interface Paper { id: string; slug: string; title: string }

interface Deck {
  id: string;
  paperSlug: string;
  paperTitle: string;
  title: string;
  audience?: string | null;
  duration_min?: number | null;
  theme?: string | null;
  concept?: string | null;
  status?: string;
  slide_count?: number;
  aspect_ratio?: string;
  created_at?: string;
  updated_at?: string;
}

interface Region {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  fit?: string;
  render_mode?: string;
  image_blob_path?: string | null;
  caption?: string | null;
}

interface DeckExport {
  id: string;
  filename: string;
  blob_path: string;
  size_bytes?: number;
  slide_count?: number;
  missing_renders?: number[];
  created_at?: string;
}

interface Slide {
  id: string;
  slide_number?: number;
  role?: string;
  title?: string;
  body?: string;
  prompt?: string;
  notes?: string;
  code?: string;
  render_mode?: string;
  figure_number?: number | null;
  image_blob_path?: string | null;
  regions?: Region[];
  status?: string;
}

interface SlideComment {
  id: string;
  text: string;
  author?: string;
  status?: string;          // open | resolved | rejected
  source?: string;          // user | ai
  region_id?: string | null;
  created_at?: string;
  resolved_at?: string | null;
}

export function ProjectPresentations() {
  const { pid } = useOutletContext<ProjectContext>();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [decksByPaper, setDecksByPaper] = useState<Record<string, Deck[]>>({});
  const [loading, setLoading] = useState(true);
  const [openDeck, setOpenDeck] = useState<string | null>(null);

  // Subscribe to papers list.
  useEffect(() => {
    if (!pid) return;
    return onSnapshot(
      collection(db, "projects", pid, "papers"),
      (snap) => {
        setPapers(snap.docs.map((d) => ({
          id: d.id,
          slug: d.id,
          title: (d.data() as { title?: string }).title || d.id,
        })));
        setLoading(false);
      },
      () => setLoading(false),
    );
  }, [pid]);

  // For each paper, subscribe to its decks subcollection.
  useEffect(() => {
    if (!pid || papers.length === 0) {
      setDecksByPaper({});
      return;
    }
    const unsubs: Array<() => void> = [];
    for (const p of papers) {
      const ref = collection(db, "projects", pid, "papers", p.slug, "decks");
      const unsub = onSnapshot(
        ref,
        (snap) => {
          const decks: Deck[] = snap.docs.map((d) => ({
            ...(d.data() as Omit<Deck, "id" | "paperSlug" | "paperTitle">),
            id: d.id,
            paperSlug: p.slug,
            paperTitle: p.title,
          }));
          setDecksByPaper((prev) => ({ ...prev, [p.slug]: decks }));
        },
        () => {/* empty subcoll → keep */},
      );
      unsubs.push(unsub);
    }
    return () => { for (const u of unsubs) u(); };
  }, [pid, papers]);

  const allDecks = useMemo(() => {
    const out: Deck[] = [];
    for (const slug of Object.keys(decksByPaper)) out.push(...decksByPaper[slug]);
    out.sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
    return out;
  }, [decksByPaper]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading presentations…</p>;
  }

  if (papers.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No papers yet</CardTitle>
          <CardDescription>
            Decks attach to papers. Create a paper first via{" "}
            <code className="bg-muted px-1 py-0.5 text-xs">/paper-writing</code>{" "}
            in Claude Code, then build a deck with{" "}
            <code className="bg-muted px-1 py-0.5 text-xs">/paper-deck</code>.
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

  if (allDecks.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Presentation className="h-4 w-4" /> Presentations
          </CardTitle>
          <CardDescription>
            No decks yet. In Claude Code, run{" "}
            <code className="bg-muted px-1 py-0.5 text-xs">
              /paper-deck &lt;paper-slug&gt; "lab seminar" 20
            </code>{" "}
            and the deck will appear here live.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {allDecks.length} deck{allDecks.length === 1 ? "" : "s"} across{" "}
        {Object.keys(decksByPaper).filter((s) => (decksByPaper[s]?.length ?? 0) > 0).length}{" "}
        paper{papers.length === 1 ? "" : "s"}. Expand a slide to preview it,
        comment on it, or reorder it.
      </p>
      {allDecks.map((d) => (
        <DeckCard
          key={`${d.paperSlug}::${d.id}`}
          pid={pid!}
          deck={d}
          open={openDeck === `${d.paperSlug}::${d.id}`}
          onToggle={() =>
            setOpenDeck(
              openDeck === `${d.paperSlug}::${d.id}`
                ? null
                : `${d.paperSlug}::${d.id}`,
            )
          }
        />
      ))}
    </div>
  );
}

function DeckCard({ pid, deck, open, onToggle }: {
  pid: string;
  deck: Deck;
  open: boolean;
  onToggle: () => void;
}) {
  const [slides, setSlides] = useState<Slide[]>([]);
  const [exports, setExports] = useState<DeckExport[]>([]);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [slideshowAt, setSlideshowAt] = useState<number | null>(null);

  useEffect(() => {
    if (!open) return;
    const ref = collection(
      db, "projects", pid, "papers", deck.paperSlug, "decks", deck.id, "slides",
    );
    return onSnapshot(
      ref,
      (snap) =>
        setSlides(
          snap.docs
            .map((d) => ({ id: d.id, ...(d.data() as Omit<Slide, "id">) }))
            .sort((a, b) => (a.slide_number || 0) - (b.slide_number || 0)),
        ),
      () => setSlides([]),
    );
  }, [open, pid, deck.id, deck.paperSlug]);

  useEffect(() => {
    if (!open) return;
    const ref = collection(
      db, "projects", pid, "papers", deck.paperSlug, "decks", deck.id, "exports",
    );
    return onSnapshot(
      ref,
      (snap) =>
        setExports(
          snap.docs
            .map((d) => ({ id: d.id, ...(d.data() as Omit<DeckExport, "id">) }))
            .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")),
        ),
      () => setExports([]),
    );
  }, [open, pid, deck.id, deck.paperSlug]);

  const download = async (exp: DeckExport) => {
    setDownloading(exp.id);
    try {
      await downloadProjectBlobAsFile(pid, exp.blob_path, exp.filename);
    } catch (e) {
      alert(`Download failed: ${(e as Error).message}`);
    } finally {
      setDownloading(null);
    }
  };

  // Accent color from the deck's concept — keeps the preview's accents
  // (top stripe, rule under title) in sync with what the exported PPTX
  // actually uses.
  const accentColor = useMemo(
    () => parseAccentColor(deck.concept ?? null),
    [deck.concept],
  );

  // Reorder: swap a slide's slide_number with its display neighbour.
  const moveSlide = async (index: number, dir: -1 | 1) => {
    const a = slides[index];
    const b = slides[index + dir];
    if (!a || !b) return;
    const base = ["projects", pid, "papers", deck.paperSlug,
                  "decks", deck.id, "slides"] as const;
    const now = new Date().toISOString();
    await Promise.all([
      updateDoc(doc(db, ...base, a.id),
                { slide_number: b.slide_number ?? 0, updated_at: now }),
      updateDoc(doc(db, ...base, b.id),
                { slide_number: a.slide_number ?? 0, updated_at: now }),
    ]);
  };

  return (
    <Card>
      <CardHeader
        onClick={onToggle}
        className="cursor-pointer select-none"
      >
        <CardTitle className="flex items-center gap-2 text-base">
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          <Presentation className="h-4 w-4" />
          <span className="truncate">{deck.title}</span>
          {deck.status && (
            <Badge
              variant={deck.status === "rendered" ? "default" : "secondary"}
              className="text-[10px]"
            >
              {deck.status}
            </Badge>
          )}
          <Badge variant="outline" className="ml-auto text-[10px]">
            {deck.slide_count ?? 0} slide{(deck.slide_count ?? 0) === 1 ? "" : "s"}
          </Badge>
        </CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-2 text-xs">
          <Link
            to={`/projects/${pid}/papers/${deck.paperSlug}`}
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 hover:underline"
          >
            <FileText className="h-3 w-3" /> {deck.paperTitle}
          </Link>
          {deck.audience && <span>• {deck.audience}</span>}
          {deck.duration_min != null && <span>• {deck.duration_min} min</span>}
          {deck.theme && (
            <Badge variant="outline" className="text-[10px]">{deck.theme}</Badge>
          )}
        </CardDescription>
      </CardHeader>
      {open && (
        <CardContent className="space-y-3">
          {deck.concept && (
            <details className="rounded-md border bg-muted/30 p-2 text-xs">
              <summary className="cursor-pointer font-medium">Concept (palette / typography / motif)</summary>
              <pre className="mt-2 whitespace-pre-wrap font-mono text-[11px] text-muted-foreground">
                {deck.concept}
              </pre>
            </details>
          )}
          {exports.length > 0 && (
            <div className="rounded-md border bg-muted/30 p-2">
              <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                Exports
              </div>
              <div className="space-y-1">
                {exports.map((e) => (
                  <div key={e.id} className="flex items-center gap-2 text-xs">
                    <span className="flex-1 truncate font-mono">{e.filename}</span>
                    {e.size_bytes && (
                      <span className="text-[10px] text-muted-foreground">
                        {(e.size_bytes / 1024).toFixed(0)} KB
                      </span>
                    )}
                    {e.missing_renders && e.missing_renders.length > 0 && (
                      <Badge variant="outline" className="border-amber-300 text-[10px] text-amber-700">
                        {e.missing_renders.length} unrendered
                      </Badge>
                    )}
                    <Button
                      size="sm" variant="outline" className="h-7 gap-1 text-xs"
                      onClick={() => download(e)}
                      disabled={downloading === e.id}
                    >
                      <Download className="h-3 w-3" />
                      {downloading === e.id ? "…" : "Download"}
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
          {exports.length === 0 && deck.status === "rendered" && (
            <p className="text-xs italic text-muted-foreground">
              All slides rendered. Run{" "}
              <code className="bg-muted px-1 py-0.5 text-[10px]">
                export_deck_to_pptx
              </code>{" "}
              in Claude Code to generate a downloadable .pptx.
            </p>
          )}
          {slides.length === 0 ? (
            <p className="text-xs italic text-muted-foreground">
              No slides yet. Run <code>/paper-deck</code> to draft.
            </p>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  Slides
                </span>
                <Button
                  size="sm" variant="outline"
                  className="h-7 gap-1 text-xs"
                  onClick={() => setSlideshowAt(0)}
                >
                  <Play className="h-3 w-3" /> Slideshow
                </Button>
              </div>
              {slides.map((s, i) => (
                <SlideRow
                  key={s.id}
                  slide={s}
                  pid={pid}
                  paperSlug={deck.paperSlug}
                  deckId={deck.id}
                  aspectRatio={deck.aspect_ratio || "16:9"}
                  accentColor={accentColor}
                  canMoveUp={i > 0}
                  canMoveDown={i < slides.length - 1}
                  onMoveUp={() => moveSlide(i, -1)}
                  onMoveDown={() => moveSlide(i, 1)}
                />
              ))}
            </div>
          )}
        </CardContent>
      )}
      {slideshowAt !== null && slides.length > 0 && (
        <SlideshowOverlay
          pid={pid}
          slides={slides}
          aspectRatio={deck.aspect_ratio || "16:9"}
          accentColor={accentColor}
          startIndex={slideshowAt}
          onClose={() => setSlideshowAt(null)}
        />
      )}
    </Card>
  );
}

function SlideRow({
  slide, pid, paperSlug, deckId, aspectRatio, accentColor,
  canMoveUp, canMoveDown, onMoveUp, onMoveDown,
}: {
  slide: Slide;
  pid: string;
  paperSlug: string;
  deckId: string;
  aspectRatio: string;
  accentColor: string;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const { user } = useAuth();
  const [expanded, setExpanded] = useState(false);
  const [comments, setComments] = useState<SlideComment[]>([]);
  const [draft, setDraft] = useState("");
  const [posting, setPosting] = useState(false);
  const notesMissing = !slide.notes || !slide.notes.trim();

  useEffect(() => {
    const ref = collection(
      db, "projects", pid, "papers", paperSlug, "decks", deckId,
      "slides", slide.id, "comments",
    );
    return onSnapshot(
      ref,
      (snap) =>
        setComments(
          snap.docs
            .map((d) => ({ id: d.id, ...(d.data() as Omit<SlideComment, "id">) }))
            .sort((a, b) => (a.created_at || "").localeCompare(b.created_at || "")),
        ),
      () => setComments([]),
    );
  }, [pid, paperSlug, deckId, slide.id]);

  const openCount = comments.filter((c) => (c.status ?? "open") === "open").length;

  const postComment = async () => {
    const text = draft.trim();
    if (!text) return;
    setPosting(true);
    try {
      await addDoc(
        collection(db, "projects", pid, "papers", paperSlug, "decks", deckId,
                   "slides", slide.id, "comments"),
        {
          text,
          author: user?.displayName || user?.email || "you",
          status: "open",
          source: "user",
          region_id: null,
          created_at: new Date().toISOString(),
        },
      );
      setDraft("");
    } catch (e) {
      alert(`Comment failed: ${(e as Error).message}`);
    } finally {
      setPosting(false);
    }
  };

  const setCommentStatus = (commentId: string, status: string) =>
    updateDoc(
      doc(db, "projects", pid, "papers", paperSlug, "decks", deckId,
          "slides", slide.id, "comments", commentId),
      {
        status,
        resolved_at: status === "open" ? null : new Date().toISOString(),
      },
    );

  return (
    <div className="rounded-md border bg-card p-2">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <Badge variant="outline" className="shrink-0 font-mono text-[10px]">
            {slide.slide_number ?? "?"}
          </Badge>
          {slide.role && (
            <Badge variant="secondary" className="shrink-0 text-[10px]">
              {slide.role}
            </Badge>
          )}
          <span className="min-w-0 flex-1 truncate text-sm font-medium">
            {slide.title || <em className="text-muted-foreground">untitled</em>}
          </span>
          {openCount > 0 && (
            <Badge
              variant="outline"
              className="shrink-0 gap-1 border-primary/40 text-[10px] text-primary"
            >
              <MessageSquare className="h-3 w-3" /> {openCount}
            </Badge>
          )}
          {slide.render_mode && (
            <Badge variant="outline" className="hidden shrink-0 text-[10px] sm:inline-flex">
              {slide.render_mode}
            </Badge>
          )}
          {notesMissing && (
            <Badge variant="outline" className="shrink-0 border-amber-300 text-[10px] text-amber-700">
              no notes
            </Badge>
          )}
          {expanded
            ? <ChevronDown className="h-3 w-3 shrink-0" />
            : <ChevronRight className="h-3 w-3 shrink-0" />}
        </button>
        <div className="flex shrink-0">
          <button
            type="button" aria-label="move slide up" disabled={!canMoveUp}
            onClick={onMoveUp}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-30"
          >
            <ArrowUp className="h-3.5 w-3.5" />
          </button>
          <button
            type="button" aria-label="move slide down" disabled={!canMoveDown}
            onClick={onMoveDown}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-30"
          >
            <ArrowDown className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {expanded && (
        <div className="mt-2 space-y-2 text-xs">
          <SlidePreview
            pid={pid} slide={slide}
            aspectRatio={aspectRatio} accentColor={accentColor}
          />
          {slide.body && (
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">Body</div>
              <pre className="whitespace-pre-wrap rounded bg-muted/30 p-2 font-mono text-[11px]">
                {slide.body}
              </pre>
            </div>
          )}
          {slide.notes && (
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">Speaker notes</div>
              <div className="rounded bg-muted/30 p-2 leading-relaxed">{slide.notes}</div>
            </div>
          )}
          {slide.prompt && (
            <details className="rounded border bg-muted/30 p-2">
              <summary className="cursor-pointer text-[10px] uppercase tracking-wide text-muted-foreground">
                Image prompt
              </summary>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px]">{slide.prompt}</pre>
            </details>
          )}
          {slide.code && (
            <details className="rounded border bg-muted/30 p-2">
              <summary className="cursor-pointer text-[10px] uppercase tracking-wide text-muted-foreground">
                Code
              </summary>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px]">{slide.code}</pre>
            </details>
          )}
          {slide.figure_number != null && (
            <a
              href={`#figure-${slide.figure_number}`}
              className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
            >
              References paper figure {slide.figure_number}
            </a>
          )}

          {/* Per-slide comments — reviewers leave feedback here; Claude
              Code reads the open ones with list_deck_comments. */}
          <div>
            <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
              Comments
            </div>
            {comments.length === 0 ? (
              <p className="italic text-muted-foreground">
                No comments on this slide yet.
              </p>
            ) : (
              <div className="space-y-1.5">
                {comments.map((c) => (
                  <div key={c.id} className="rounded border bg-muted/30 p-2">
                    <div className="whitespace-pre-wrap break-words">{c.text}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-muted-foreground">
                      <span>{c.author || "anon"}</span>
                      {c.created_at && (
                        <span>· {new Date(c.created_at).toLocaleString()}</span>
                      )}
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[9px]",
                          (c.status ?? "open") === "open"
                            ? "border-primary/40 text-primary"
                            : "text-muted-foreground",
                        )}
                      >
                        {c.status ?? "open"}
                      </Badge>
                      {(c.status ?? "open") === "open" ? (
                        <button
                          type="button"
                          onClick={() => setCommentStatus(c.id, "resolved")}
                          className="inline-flex items-center gap-0.5 text-primary hover:underline"
                        >
                          <Check className="h-3 w-3" /> Resolve
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setCommentStatus(c.id, "open")}
                          className="hover:underline"
                        >
                          Reopen
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-2 space-y-1.5">
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={2}
                placeholder="Comment on this slide…"
                className="text-xs"
              />
              <Button
                size="sm"
                className="h-7 gap-1 text-xs"
                disabled={posting || !draft.trim()}
                onClick={postComment}
              >
                {posting
                  ? <Loader2 className="h-3 w-3 animate-spin" />
                  : <MessageSquare className="h-3 w-3" />}
                Comment
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ─── slide preview ──────────────────────────────────────────────────────────

function arCss(aspectRatio: string): string {
  if (aspectRatio === "4:3") return "4 / 3";
  if (aspectRatio === "16:10") return "16 / 10";
  return "16 / 9";
}

/** Extract the deck's accent color from its concept string — keeps the
 *  preview's accents in sync with what the exported PPTX actually uses. */
function parseAccentColor(concept: string | null): string {
  if (!concept) return "#2E7D32";
  const m = concept.match(/\baccent\s*:\s*(#[0-9a-fA-F]{6})\b/);
  return m ? m[1] : "#2E7D32";
}

const _INLINE_MD_RE =
  /(\*\*.+?\*\*|__.+?__|\*[^*\n]+?\*|_[^_\n]+?_|`[^`\n]+?`)/g;

/** Render inline **bold** / *italic* / `code` so the preview shows the
 *  same emphasis as the exported PPTX. */
function renderInline(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let i = 0;
  for (const tok of text.split(_INLINE_MD_RE)) {
    if (!tok) continue;
    if ((tok.startsWith("**") && tok.endsWith("**"))
        || (tok.startsWith("__") && tok.endsWith("__"))) {
      out.push(<strong key={i++}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("`") && tok.endsWith("`")) {
      out.push(
        <code key={i++} className="rounded bg-muted px-1 font-mono">
          {tok.slice(1, -1)}
        </code>,
      );
    } else if ((tok.startsWith("*") && tok.endsWith("*"))
               || (tok.startsWith("_") && tok.endsWith("_"))) {
      out.push(<em key={i++}>{tok.slice(1, -1)}</em>);
    } else {
      out.push(<span key={i++}>{tok}</span>);
    }
  }
  return out;
}

/** Render a slide body's markdown as a tiny preview — headings, bullets
 *  with indentation, plain paragraphs, with inline emphasis intact. */
function MiniMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-0.5">
      {lines.map((raw, i) => {
        if (!raw.trim()) return null;
        const h = raw.match(/^\s*#{1,6}\s+(.+\S)\s*$/);
        if (h) {
          return (
            <div
              key={i}
              className="mt-1 font-semibold text-foreground"
              style={{ fontSize: "1.3em" }}
            >
              {renderInline(h[1])}
            </div>
          );
        }
        const b = raw.match(/^(\s*)[-*]\s+(.+\S)\s*$/);
        if (b) {
          const depth = Math.min(Math.floor(b[1].length / 2), 3);
          return (
            <div
              key={i} className="flex gap-1"
              style={{ paddingLeft: `${depth * 0.8}em` }}
            >
              <span aria-hidden>•</span>
              <span className="min-w-0">{renderInline(b[2])}</span>
            </div>
          );
        }
        return <div key={i}>{renderInline(raw.trim())}</div>;
      })}
    </div>
  );
}

function StorageImg({ pid, blobPath, className, alt }: {
  pid: string; blobPath: string; className?: string; alt?: string;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { getDownloadURL, ref } = await import("firebase/storage");
        const storage = await getProjectStorage(pid);
        const u = await getDownloadURL(ref(storage, blobPath));
        if (!cancelled) setUrl(u);
      } catch {
        if (!cancelled) setErr(true);
      }
    })();
    return () => { cancelled = true; };
  }, [pid, blobPath]);
  if (err) {
    return (
      <div className="flex h-full w-full items-center justify-center text-[9px] text-destructive">
        image unavailable
      </div>
    );
  }
  if (!url) {
    return (
      <div className="flex h-full w-full items-center justify-center text-[9px] text-muted-foreground">
        loading…
      </div>
    );
  }
  return <img src={url} alt={alt} className={className} />;
}

/** Shared frame for native text + hybrid previews — themed background,
 *  top accent stripe, title, and the short accent rule under the title.
 *  Geometry tracks `_add_slide_frame` in the export. */
function SlideFrame({
  title, accentColor, ar, children,
}: {
  title?: string;
  accentColor: string;
  ar: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      className="relative overflow-hidden rounded-md border bg-card"
      style={{ aspectRatio: ar, containerType: "inline-size" }}
    >
      <div
        className="absolute inset-x-0 top-0 h-1.5"
        style={{ background: accentColor }}
      />
      <div
        className="absolute line-clamp-2 font-bold leading-tight"
        style={{
          left: "5%", top: "6%", width: "90%",
          fontSize: "max(14px, 3.5cqw)",
        }}
      >
        {title || <span className="text-muted-foreground">untitled</span>}
      </div>
      <div
        className="absolute"
        style={{
          left: "5.4%", top: "20.3%", width: "16.5%", height: "3px",
          background: accentColor,
        }}
      />
      {children}
    </div>
  );
}

/** A visual of the slide, so a reviewer can comment against what they see.
 *  Geometry, accent color, and inline markdown emphasis track the exported
 *  PPTX so the dashboard preview matches the file. */
function SlidePreview({ pid, slide, aspectRatio, accentColor }: {
  pid: string;
  slide: Slide;
  aspectRatio: string;
  accentColor: string;
}) {
  const ar = arCss(aspectRatio);
  const mode = slide.render_mode || "code-shape";

  // Image slide → full-bleed picture, no frame.
  if (mode !== "hybrid" && slide.image_blob_path) {
    return (
      <div
        className="overflow-hidden rounded-md border bg-muted/20"
        style={{ aspectRatio: ar }}
      >
        <StorageImg
          pid={pid} blobPath={slide.image_blob_path} alt={slide.title}
          className="h-full w-full object-contain"
        />
      </div>
    );
  }

  // Hybrid → frame + left-half body + positioned regions.
  if (mode === "hybrid") {
    const regions = slide.regions || [];
    const body = (slide.body || "").trim();
    return (
      <SlideFrame title={slide.title} accentColor={accentColor} ar={ar}>
        {body && (
          <div
            className="absolute overflow-hidden leading-snug text-muted-foreground"
            style={{
              left: "5%", top: "22%", width: "44%", height: "74%",
              fontSize: "max(10px, 1.9cqw)",
            }}
          >
            <MiniMarkdown text={body} />
          </div>
        )}
        {regions.map((r) => (
          <div
            key={r.id}
            className="absolute overflow-hidden"
            style={{
              left: `${r.x * 100}%`, top: `${r.y * 100}%`,
              width: `${r.w * 100}%`, height: `${r.h * 100}%`,
            }}
          >
            {r.image_blob_path ? (
              <StorageImg
                pid={pid} blobPath={r.image_blob_path} alt={r.id}
                className={cn(
                  "h-full w-full",
                  r.fit === "cover" ? "object-cover" : "object-contain",
                )}
              />
            ) : (
              <div
                className="flex h-full w-full items-center justify-center rounded border border-dashed text-muted-foreground"
                style={{ fontSize: "max(9px, 1.3cqw)" }}
              >
                {r.id} · {r.render_mode}
              </div>
            )}
          </div>
        ))}
        {regions.length === 0 && !body && (
          <div
            className="absolute text-muted-foreground"
            style={{
              left: "5%", top: "45%", fontSize: "max(10px, 1.9cqw)",
            }}
          >
            empty hybrid slide
          </div>
        )}
      </SlideFrame>
    );
  }

  // text slide (or not yet rendered) → frame + full-width body. Not
  // pixel-perfect with the PPTX but emphasis / bullets / accent stripe
  // all match so review against this is faithful.
  return (
    <SlideFrame title={slide.title} accentColor={accentColor} ar={ar}>
      {slide.body && (
        <div
          className="absolute overflow-hidden leading-snug text-muted-foreground"
          style={{
            left: "5%", top: "26%", width: "90%", height: "67%",
            fontSize: "max(11px, 2.1cqw)",
          }}
        >
          <MiniMarkdown text={slide.body} />
        </div>
      )}
      {mode !== "text" && (
        <div
          className="absolute italic text-amber-600"
          style={{
            left: "5%", bottom: "3%", fontSize: "max(9px, 1.1cqw)",
          }}
        >
          not rendered yet — preview shows the slide content
        </div>
      )}
    </SlideFrame>
  );
}


// ─── fullscreen slideshow ─────────────────────────────────────────────────

/** A presenter-style slideshow over the deck. One slide at a time, sized
 *  to fit the viewport while keeping the deck's aspect ratio. Keyboard:
 *  ←/→/Space (navigate), Esc (close), N (toggle speaker notes). Click the
 *  left / right half of the slide to navigate too. Rendered into a portal
 *  so parent overflow / transforms can't clip it. */
function SlideshowOverlay({
  pid, slides, aspectRatio, accentColor, startIndex, onClose,
}: {
  pid: string;
  slides: Slide[];
  aspectRatio: string;
  accentColor: string;
  startIndex: number;
  onClose: () => void;
}) {
  const [index, setIndex] = useState(() =>
    Math.max(0, Math.min(startIndex, slides.length - 1)),
  );
  const [showNotes, setShowNotes] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);

  // Clamp the index whenever the slide list changes underneath us (e.g.
  // someone reorders or deletes a slide while the show is open).
  useEffect(() => {
    setIndex((i) => Math.max(0, Math.min(i, slides.length - 1)));
  }, [slides.length]);

  const next = useCallback(() => {
    setIndex((i) => Math.min(i + 1, slides.length - 1));
  }, [slides.length]);
  const prev = useCallback(() => {
    setIndex((i) => Math.max(i - 1, 0));
  }, []);

  // Keyboard shortcuts (presenter conventions). Attached to the document
  // so they fire no matter where focus is, but the early-return on a typing
  // element keeps text inputs usable inside the overlay if we add any.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tgt = e.target as HTMLElement | null;
      if (tgt && (tgt.tagName === "INPUT" || tgt.tagName === "TEXTAREA"
                  || tgt.isContentEditable)) return;
      if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") {
        e.preventDefault(); next();
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault(); prev();
      } else if (e.key === "Escape") {
        e.preventDefault(); onClose();
      } else if (e.key === "n" || e.key === "N") {
        e.preventDefault(); setShowNotes((s) => !s);
      } else if (e.key === "Home") {
        e.preventDefault(); setIndex(0);
      } else if (e.key === "End") {
        e.preventDefault(); setIndex(slides.length - 1);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [next, prev, onClose, slides.length]);

  // Lock background scroll so the slide is the only thing on screen.
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prevOverflow; };
  }, []);

  const slide = slides[index];
  if (!slide) return null;
  const ar = arCss(aspectRatio);
  // Width factor derived from the deck's aspect ratio — used so the slide
  // can be as tall as `100vh - chrome` without overrunning the viewport
  // horizontally for narrow (4:3) decks, or shorter (16:10) ones.
  const arNumeric = aspectRatio === "4:3"
    ? 4 / 3 : aspectRatio === "16:10" ? 16 / 10 : 16 / 9;

  return createPortal(
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex flex-col bg-black/95 text-white"
      role="dialog"
      aria-modal="true"
      aria-label="Slideshow"
    >
      {/* close + counter bar */}
      <div className="flex items-center justify-between px-4 py-2 text-xs">
        <div className="flex items-center gap-3">
          <span className="font-mono tabular-nums">
            {index + 1} / {slides.length}
          </span>
          {slide.role && (
            <span className="rounded border border-white/20 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-white/70">
              {slide.role}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowNotes((s) => !s)}
            className={cn(
              "inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] hover:bg-white/10",
              showNotes && "bg-white/10",
            )}
            title="Toggle speaker notes (N)"
          >
            <StickyNote className="h-3.5 w-3.5" /> Notes
          </button>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] hover:bg-white/10"
            title="Close (Esc)"
          >
            <X className="h-3.5 w-3.5" /> Close
          </button>
        </div>
      </div>

      {/* slide stage — flexes to fill remaining vertical space */}
      <div className="relative flex flex-1 min-h-0 items-center justify-center px-4 pb-4">
        {/* click zones for prev / next, behind the slide */}
        <button
          type="button"
          onClick={prev}
          disabled={index === 0}
          aria-label="Previous slide"
          className="absolute inset-y-0 left-0 z-10 w-1/3 cursor-w-resize bg-transparent disabled:cursor-not-allowed"
        />
        <button
          type="button"
          onClick={next}
          disabled={index === slides.length - 1}
          aria-label="Next slide"
          className="absolute inset-y-0 right-0 z-10 w-1/3 cursor-e-resize bg-transparent disabled:cursor-not-allowed"
        />

        {/* the actual slide, scaled to fit while keeping its aspect ratio.
            SlidePreview's root sets aspect-ratio + fills the parent's width
            (block default), so matching the outer width + aspect-ratio
            here means the inner preview takes the exact same box. */}
        <div
          className="relative z-20 shadow-2xl text-foreground"
          style={{
            aspectRatio: ar,
            width: `min(96vw, calc((100vh - 9rem) * ${arNumeric}))`,
          }}
        >
          <SlidePreview
            pid={pid} slide={slide}
            aspectRatio={aspectRatio} accentColor={accentColor}
          />
        </div>

        {/* visible nav arrows (also reachable by keyboard) */}
        <button
          type="button"
          onClick={prev}
          disabled={index === 0}
          aria-label="Previous slide"
          className="absolute left-2 top-1/2 z-30 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white hover:bg-white/20 disabled:opacity-30"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={next}
          disabled={index === slides.length - 1}
          aria-label="Next slide"
          className="absolute right-2 top-1/2 z-30 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white hover:bg-white/20 disabled:opacity-30"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      {/* speaker notes (toggled via the Notes button or "N") */}
      {showNotes && (
        <div className="border-t border-white/10 bg-black/60 px-6 py-3 text-sm">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-white/50">
            Speaker notes
          </div>
          {slide.notes && slide.notes.trim() ? (
            <div className="max-h-32 overflow-y-auto whitespace-pre-wrap leading-relaxed">
              {slide.notes}
            </div>
          ) : (
            <div className="italic text-white/40">
              No speaker notes on this slide.
            </div>
          )}
        </div>
      )}

      {/* keyboard hint footer */}
      <div className="border-t border-white/5 px-4 py-1.5 text-[10px] text-white/40">
        ← / → navigate · Space next · N notes · Esc close
      </div>
    </div>,
    document.body,
  );
}
