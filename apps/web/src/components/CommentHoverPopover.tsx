import { useEffect, useState } from "react";
import { doc, updateDoc } from "firebase/firestore";
import { CheckCircle2, XCircle, X } from "lucide-react";
import { db } from "@/firebase";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Review {
  id: string;
  section?: string | null;
  comment: string;
  source: string;
  status: string;
  severity?: string;
  response?: string | null;
  anchor_text?: string | null;
  manuscript_ref?: string | null;
  created_at?: string;
}

interface Props {
  pid: string;
  paperSlug: string;
  reviews: Review[];
}

/** Global click-to-open popover for inline anchored comments.
 *  Click <mark.cs-anchor-mark> → popover opens below the mark.
 *  Click another mark → moves to that one. Click outside → closes.
 *  No hover trigger (intentional — less twitchy on dense paragraphs). */
export function CommentHoverPopover({ pid, paperSlug, reviews }: Props) {
  const [active, setActive] = useState<{ review: Review; rect: DOMRect } | null>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      const target = e.target as HTMLElement;
      const mark = target.closest("mark.cs-anchor-mark") as HTMLElement | null;
      if (mark) {
        const reviewId = mark.dataset.reviewId;
        const review = reviews.find((r) => r.id === reviewId);
        if (review) {
          setActive({ review, rect: mark.getBoundingClientRect() });
        }
        return;
      }
      // Ignore clicks inside the popover itself
      if (target.closest("[data-comment-popover]")) return;
      setActive(null);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setActive(null);
    }
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [reviews]);

  if (!active) return null;

  const width = 360;
  const gap = 6;
  // Prefer BELOW the mark; flip above if would clip viewport bottom.
  const wouldClipBelow = active.rect.bottom + 220 > window.innerHeight;
  const top = wouldClipBelow
    ? Math.max(8, active.rect.top - 220 - gap)
    : active.rect.bottom + gap;
  const left = Math.max(
    8,
    Math.min(active.rect.left, window.innerWidth - width - 8),
  );

  const review = active.review;
  const isResolved = review.status !== "open";

  const resolve = async () => {
    await updateDoc(
      doc(db, "projects", pid, "papers", paperSlug, "reviews", review.id),
      { status: "resolved", resolved_at: new Date().toISOString() },
    );
    setActive(null);
  };
  const withdraw = async () => {
    await updateDoc(
      doc(db, "projects", pid, "papers", paperSlug, "reviews", review.id),
      { status: "rejected", resolved_at: new Date().toISOString() },
    );
    setActive(null);
  };

  return (
    <div
      data-comment-popover
      className="fixed z-40 rounded-lg border bg-white p-3 shadow-xl ring-1 ring-black/5 dark:bg-zinc-900 dark:ring-white/10"
      style={{ top, left, width }}
    >
      <div className="flex items-center gap-2">
        <Badge
          variant={review.source === "ai" ? "secondary" : "outline"}
          className="text-[10px]"
        >
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
        {isResolved && (
          <Badge variant="secondary" className="text-[10px]">{review.status}</Badge>
        )}
        <Button
          size="icon"
          variant="ghost"
          className="ml-auto h-5 w-5"
          onClick={() => setActive(null)}
          aria-label="Close"
        >
          <X className="h-3 w-3" />
        </Button>
      </div>
      <div className="mt-2 max-h-40 overflow-y-auto text-sm whitespace-pre-wrap">
        {review.comment}
      </div>
      {review.response && (
        <div className="mt-2 rounded-md bg-muted p-2 text-xs">
          <div className="mb-1 font-medium">Claude's response:</div>
          <div className="whitespace-pre-wrap">{review.response}</div>
        </div>
      )}
      {!isResolved && (
        <div className="mt-2 flex gap-2 border-t pt-2">
          <Button size="sm" variant="ghost" onClick={resolve}>
            <CheckCircle2 className="mr-1 h-3 w-3" /> Resolve
          </Button>
          <Button size="sm" variant="ghost" onClick={withdraw}>
            <XCircle className="mr-1 h-3 w-3" /> Withdraw
          </Button>
        </div>
      )}
    </div>
  );
}
