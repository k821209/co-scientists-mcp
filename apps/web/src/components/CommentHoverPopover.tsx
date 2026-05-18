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
        if (review) setActive({ review, rect: mark.getBoundingClientRect() });
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

  const width = 320;
  const popHeight = 240;
  const gap = 10;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const m = active.rect;

  // Position priority (don't cover the highlighted text):
  //   1. To the RIGHT of the mark if width fits
  //   2. To the LEFT if width fits
  //   3. BELOW the mark line if room
  //   4. ABOVE the mark line as last resort
  // Vertical is clamped so the popover never exceeds the viewport.
  const roomRight = vw - m.right - 16;
  const roomLeft = m.left - 16;
  const roomBelow = vh - m.bottom - 16;
  const roomAbove = m.top - 16;

  let top: number;
  let left: number;
  let maxHeight: number;

  if (roomRight >= width) {
    left = m.right + gap;
    top = Math.max(8, Math.min(m.top - 4, vh - popHeight - 8));
    maxHeight = Math.max(140, vh - top - 8);
  } else if (roomLeft >= width) {
    left = m.left - width - gap;
    top = Math.max(8, Math.min(m.top - 4, vh - popHeight - 8));
    maxHeight = Math.max(140, vh - top - 8);
  } else if (roomBelow >= roomAbove) {
    top = m.bottom + gap;
    left = Math.max(8, Math.min(m.left, vw - width - 8));
    maxHeight = Math.max(140, roomBelow - gap);
  } else {
    // place above
    const desiredHeight = Math.min(popHeight, roomAbove - gap);
    top = Math.max(8, m.top - desiredHeight - gap);
    left = Math.max(8, Math.min(m.left, vw - width - 8));
    maxHeight = Math.max(140, roomAbove - gap);
  }

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
      className="fixed z-40 overflow-hidden rounded-lg border bg-white shadow-xl ring-1 ring-black/5 dark:bg-zinc-900 dark:ring-white/10"
      style={{ top, left, width, maxHeight }}
    >
     <div className="flex h-full flex-col overflow-y-auto p-3">
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
    </div>
  );
}
