import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import {
  addDoc, collection, doc, onSnapshot, updateDoc,
} from "firebase/firestore";
import {
  Presentation, FileText, ArrowRight, ChevronDown, ChevronRight, Download,
  MessageSquare, ArrowUp, ArrowDown, Check, Loader2,
} from "lucide-react";
import { db } from "@/firebase";
import { useAuth } from "@/auth";
import { downloadProjectBlobAsFile } from "@/projectAuth";
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
  created_at?: string;
  updated_at?: string;
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
        paper{papers.length === 1 ? "" : "s"}. Rendering (slide PNGs +
        .pptx export) is Phase 3 — for now decks are content-only.
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
              {slides.map((s, i) => (
                <SlideRow
                  key={s.id}
                  slide={s}
                  pid={pid}
                  paperSlug={deck.paperSlug}
                  deckId={deck.id}
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
    </Card>
  );
}

function SlideRow({
  slide, pid, paperSlug, deckId, canMoveUp, canMoveDown, onMoveUp, onMoveDown,
}: {
  slide: Slide;
  pid: string;
  paperSlug: string;
  deckId: string;
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
