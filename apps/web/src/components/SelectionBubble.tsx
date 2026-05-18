import { useEffect, useRef, useState } from "react";
import { addDoc, collection } from "firebase/firestore";
import { Copy, MessageSquare, X, Check } from "lucide-react";
import { db } from "@/firebase";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface Props {
  pid: string;
  paperSlug: string;
  /** CSS selector for elements considered "selectable" — only selections
   *  whose anchor sits inside one of these elements show the bubble.
   *  Each match must carry data-section-key="<key>". */
  selectableSelector?: string;
}

interface SelectionInfo {
  text: string;
  sectionKey: string;
  x: number;  // viewport-relative anchor (mouse release point)
  y: number;
}

/** Listens for text selection inside section bodies. Pops up a small
 *  toolbar with [Copy] and [Comment] when ≥3 chars are selected.
 *  Mirrors the original co-scientist's selectionActionMenu. */
export function SelectionBubble({
  pid, paperSlug,
  selectableSelector = "[data-section-key]",
}: Props) {
  const [sel, setSel] = useState<SelectionInfo | null>(null);
  const [composing, setComposing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const composingRef = useRef(composing);
  composingRef.current = composing;

  useEffect(() => {
    function onMouseUp(e: MouseEvent) {
      // Don't interfere if click is inside our own UI.
      const target = e.target as HTMLElement | null;
      if (target?.closest("[data-selection-bubble]")) return;

      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) {
        if (!composingRef.current) setSel(null);
        return;
      }
      const text = selection.toString().trim();
      if (text.length < 3) {
        if (!composingRef.current) setSel(null);
        return;
      }
      // Anchor node must live inside a selectable section.
      const anchorEl = selection.anchorNode?.parentElement;
      const sectionEl = anchorEl?.closest(selectableSelector);
      if (!sectionEl) {
        if (!composingRef.current) setSel(null);
        return;
      }
      const sectionKey = (sectionEl as HTMLElement).dataset.sectionKey || "";
      // Anchor to the mouse release point (most predictable). Fall back
      // to selection's last client rect for touch / keyboard selection
      // where event coords aren't available.
      let x = e.clientX;
      let y = e.clientY;
      if (!x && !y) {
        const rects = selection.getRangeAt(0).getClientRects();
        const last = rects[rects.length - 1];
        if (last) {
          x = last.right;
          y = last.top;
        }
      }
      setSel({ text, sectionKey, x, y });
    }

    function onScroll() {
      // Bubble is positioned to a one-shot rect; hide on scroll rather than
      // chase it. The user can re-select.
      if (!composingRef.current) setSel(null);
    }

    document.addEventListener("mouseup", onMouseUp);
    document.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mouseup", onMouseUp);
      document.removeEventListener("scroll", onScroll, true);
    };
  }, [selectableSelector]);

  if (!sel) return null;

  const copy = async () => {
    try { await navigator.clipboard.writeText(sel.text); } catch {}
    setSel(null);
  };

  // Position the bubble above-left of the mouse release point, clamped
  // to viewport. Width-aware so it doesn't clip off-screen on mobile.
  const bubbleApproxWidth = composing ? 360 : 220;
  const top = Math.max(8, sel.y - 46);
  const left = Math.max(
    8,
    Math.min(sel.x - bubbleApproxWidth / 2, window.innerWidth - bubbleApproxWidth - 8),
  );

  return (
    <div
      data-selection-bubble
      className="fixed z-50"
      style={{ top, left }}
    >
      {!composing ? (
        <div className="flex items-center gap-1 rounded-full border bg-popover px-2 py-1 shadow-md">
          <Button size="sm" variant="ghost" className="h-7 gap-1 px-2 text-xs"
                  onClick={copy} title="Copy selection">
            <Copy className="h-3 w-3" /> Copy
          </Button>
          <span className="h-4 w-px bg-border" />
          <Button size="sm" variant="ghost" className="h-7 gap-1 px-2 text-xs"
                  onClick={() => setComposing(true)} title="Comment on selection">
            <MessageSquare className="h-3 w-3" /> Comment
          </Button>
          <span className="h-4 w-px bg-border" />
          <Button size="icon" variant="ghost" className="h-6 w-6"
                  onClick={() => setSel(null)} aria-label="Close">
            <X className="h-3 w-3" />
          </Button>
        </div>
      ) : (
        <CommentComposer
          quoted={sel.text}
          sectionKey={sel.sectionKey}
          pid={pid}
          paperSlug={paperSlug}
          submitting={submitting}
          onCancel={() => { setComposing(false); setSel(null); }}
          onSubmit={async (comment) => {
            setSubmitting(true);
            try {
              const reviewsRef = collection(
                db, "projects", pid, "papers", paperSlug, "reviews",
              );
              await addDoc(reviewsRef, {
                source: "user",
                reviewer_name: "User",
                section: sel.sectionKey || null,
                severity: "minor",
                status: "open",
                comment,
                anchor_text: sel.text,           // the quoted selection
                manuscript_ref: sel.sectionKey
                  ? `section:${sel.sectionKey}`
                  : null,
                response: null,
                created_at: new Date().toISOString(),
                resolved_at: null,
              });
              setComposing(false);
              setSel(null);
            } finally {
              setSubmitting(false);
            }
          }}
        />
      )}
    </div>
  );
}

function CommentComposer({
  quoted, sectionKey, pid, paperSlug, submitting, onCancel, onSubmit,
}: {
  quoted: string;
  sectionKey: string;
  pid: string;
  paperSlug: string;
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (comment: string) => Promise<void>;
}) {
  const [text, setText] = useState("");
  void pid; void paperSlug;
  return (
    <div className="w-[min(360px,92vw)] space-y-2 rounded-lg border bg-popover p-3 shadow-lg">
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-muted-foreground">
        <span>Comment on {sectionKey ? <code>{sectionKey}</code> : "selection"}</span>
        <Button size="icon" variant="ghost" className="h-5 w-5" onClick={onCancel} aria-label="Close">
          <X className="h-3 w-3" />
        </Button>
      </div>
      <blockquote className="max-h-24 overflow-y-auto rounded border-l-2 border-primary/60 bg-muted/40 px-2 py-1 text-xs italic">
        “{quoted.length > 240 ? quoted.slice(0, 240) + "…" : quoted}”
      </blockquote>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Your comment — Claude Code will see the quoted text + your note."
        rows={3}
        className="text-sm"
        autoFocus
      />
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button
          size="sm"
          disabled={!text.trim() || submitting}
          onClick={() => onSubmit(text.trim())}
        >
          {submitting
            ? <span>Sending…</span>
            : <span className="inline-flex items-center gap-1"><Check className="h-3 w-3" /> Comment</span>}
        </Button>
      </div>
    </div>
  );
}
