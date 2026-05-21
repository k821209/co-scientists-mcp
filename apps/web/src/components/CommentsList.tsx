import { useMemo } from "react";
import { MessageSquare, CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface CommentReview {
  id: string;
  comment: string;
  source: string;
  reviewer_name?: string | null;
  status: string;
  response?: string | null;
  anchor_text?: string | null;
  created_at?: string;
}

interface Props {
  reviews: CommentReview[];
  /** Mark rows authored by this name with a "you" chip (share view). */
  myName?: string;
  /** Owner-only: when provided, open comments get Resolve / Withdraw
   *  buttons. Omit for the read-only share view. */
  onResolve?: (id: string) => void;
  onWithdraw?: (id: string) => void;
}

/** Persistent comment list — the reliable view of the review thread
 *  even after manuscript edits dissolve the inline highlights. Used by
 *  both the owner Paper page and the /shared reviewer page. */
export function CommentsList({ reviews, myName, onResolve, onWithdraw }: Props) {
  const sorted = useMemo(() => {
    const rank = (s: string) => (s === "open" ? 0 : 1);
    return [...reviews].sort((a, b) => {
      const r = rank(a.status) - rank(b.status);
      if (r !== 0) return r;
      return (b.created_at || "").localeCompare(a.created_at || "");
    });
  }, [reviews]);

  const openCount = reviews.filter((r) => r.status === "open").length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquare className="h-4 w-4" /> Comments
          <Badge variant="secondary" className="ml-auto text-[10px]">
            {openCount} open
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="max-h-[70vh] space-y-2 overflow-y-auto break-words">
        {reviews.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No comments yet. Drag-select any passage in the manuscript to
            leave one.
          </p>
        ) : (
          sorted.map((r) => (
            <CommentRow
              key={r.id}
              review={r}
              mine={!!myName && r.reviewer_name === myName}
              onResolve={onResolve}
              onWithdraw={onWithdraw}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}

function CommentRow({ review, mine, onResolve, onWithdraw }: {
  review: CommentReview;
  mine: boolean;
  onResolve?: (id: string) => void;
  onWithdraw?: (id: string) => void;
}) {
  const status = review.status;
  const meta =
    status === "open"
      ? { label: "open", cls: "border-amber-300 bg-amber-50 text-amber-700" }
    : status === "rejected"
      ? { label: "declined", cls: "border-red-300 bg-red-50 text-red-700" }
    : { label: "addressed", cls: "border-green-300 bg-green-50 text-green-700" };

  const jump = () => {
    if (!review.anchor_text) return;
    const marks = document.querySelectorAll<HTMLElement>("mark.cs-anchor-mark");
    for (const m of marks) {
      const ids = (m.dataset.reviewIds ?? m.dataset.reviewId ?? "").split(",");
      if (ids.includes(review.id)) {
        m.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
    }
  };

  const who =
    review.source === "external"
      ? (review.reviewer_name || "anonymous")
      : review.source === "ai"
        ? `AI · ${review.reviewer_name || "reviewer"}`
        : "author";

  const canAct = status === "open" && (onResolve || onWithdraw);

  return (
    <div className="rounded-md border p-2 text-xs">
      <div
        className={review.anchor_text ? "cursor-pointer" : ""}
        onClick={jump}
        role={review.anchor_text ? "button" : undefined}
      >
        <div className="mb-1 flex flex-wrap items-center gap-1">
          <span className={`rounded-full border px-1.5 py-0 text-[9px] font-medium ${meta.cls}`}>
            {meta.label}
          </span>
          <span className="text-[10px] text-muted-foreground">{who}</span>
          {mine && (
            <span className="rounded bg-sky-100 px-1 text-[9px] text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
              you
            </span>
          )}
        </div>
        {review.anchor_text && (
          <blockquote className="mb-1 line-clamp-2 border-l-2 border-amber-400 pl-2 italic text-muted-foreground">
            "{review.anchor_text.length > 120
              ? review.anchor_text.slice(0, 120) + "…"
              : review.anchor_text}"
          </blockquote>
        )}
        <div className="line-clamp-3 whitespace-pre-wrap">{review.comment}</div>
        {review.response && (
          <div className="mt-1 rounded bg-muted/60 p-1.5 text-[11px]">
            <span className="font-medium">Author's reply: </span>
            <span className="whitespace-pre-wrap">{review.response}</span>
          </div>
        )}
      </div>
      {canAct && (
        <div className="mt-2 flex gap-1 border-t pt-2">
          {onResolve && (
            <Button
              size="sm" variant="ghost" className="h-6 gap-1 px-2 text-[11px]"
              onClick={() => onResolve(review.id)}
            >
              <CheckCircle2 className="h-3 w-3" /> Resolve
            </Button>
          )}
          {onWithdraw && (
            <Button
              size="sm" variant="ghost" className="h-6 gap-1 px-2 text-[11px]"
              onClick={() => onWithdraw(review.id)}
            >
              <XCircle className="h-3 w-3" /> Withdraw
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
