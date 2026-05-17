import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addDoc, collection, doc, onSnapshot, orderBy, query, updateDoc,
} from "firebase/firestore";
import {
  ArrowLeft, MessageSquare, CheckCircle2, XCircle, Download, Loader2,
} from "lucide-react";
import { db } from "@/firebase";
import { downloadProjectBlobAsText } from "@/projectAuth";
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

export function Paper() {
  const { pid, slug } = useParams<{ pid: string; slug: string }>();
  const [paper, setPaper] = useState<Record<string, unknown> | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
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
    return () => { unsubPaper(); unsubSec(); unsubRev(); };
  }, [pid, slug]);

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
              <SectionView key={s.id} section={s} pid={pid} paperSlug={slug} />
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
            <ReviewView key={r.id} review={r} pid={pid} paperSlug={slug} />
          ))}
        </div>
      </div>
    </div>
  );
}

function SectionView({ section, pid, paperSlug }: { section: Section; pid: string; paperSlug: string }) {
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
        <Markdown className="text-sm">{section.body}</Markdown>
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

function ReviewView({ review, pid, paperSlug }: { review: Review; pid: string; paperSlug: string }) {
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
        <Markdown className="text-sm">{review.comment}</Markdown>
        {review.response && (
          <div className="rounded-md bg-muted p-2 text-xs">
            <div className="mb-1 font-medium">Claude's response:</div>
            <Markdown className="text-xs">{review.response}</Markdown>
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
