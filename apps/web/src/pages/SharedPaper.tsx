import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { collection, doc, onSnapshot, orderBy, query } from "firebase/firestore";
import { MessageSquare, Pencil } from "lucide-react";
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

const NAME_STORAGE_KEY = "cs-shared-reviewer-name";

export function SharedPaper() {
  const { pid, slug, shareId } = useParams<{
    pid: string; slug: string; shareId: string;
  }>();
  const [session, setSession] = useState<ShareSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paper, setPaper] = useState<Record<string, unknown> | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);

  // Reviewer name — persisted in localStorage so it survives reloads.
  const [name, setName] = useState<string>(() => {
    return localStorage.getItem(NAME_STORAGE_KEY) || "";
  });
  // The name actually attached to comments: typed name, or a stable random.
  const [randomName] = useState(() => randomReviewerName());
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
    return () => { u1(); u2(); u3(); };
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
