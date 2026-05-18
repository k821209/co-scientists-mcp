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
  x: number;  // viewport-relative anchor X (drag-start point)
  y: number;  // viewport-relative selection top (or bottom if flipBelow)
  flipBelow: boolean;
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
  // Captures where the drag started, so we can anchor the bubble there
  // even when the user drags downward and mouseup is far from where their
  // attention was when they pressed down.
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      dragStartRef.current = { x: e.clientX, y: e.clientY };
    }
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
      // Anchor strategy:
      //   - X: horizontal start of the drag (where the user's eye was
      //     when they began the selection). Falls back to the first
      //     selection rect's left if dragStart is unavailable.
      //   - Y: top of the selection's FIRST client rect — the visual top
      //     of the selected text — so the bubble appears above the
      //     selection regardless of drag direction.
      const rects = selection.getRangeAt(0).getClientRects();
      const firstRect = rects[0];
      const lastRect = rects[rects.length - 1];
      const start = dragStartRef.current;
      let x = start?.x ?? firstRect?.left ?? e.clientX;
      let y = firstRect?.top ?? e.clientY;
      // If selection's top is too close to the viewport top, flip the
      // bubble to BELOW the selection's bottom edge.
      const flipBelow = y < 60;
      if (flipBelow && lastRect) y = lastRect.bottom;
      setSel({ text, sectionKey, x, y, flipBelow });
    }

    function onScroll() {
      // Bubble is positioned to a one-shot rect; hide on scroll rather than
      // chase it. The user can re-select.
      if (!composingRef.current) setSel(null);
    }

    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("mouseup", onMouseUp);
    document.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("mouseup", onMouseUp);
      document.removeEventListener("scroll", onScroll, true);
    };
  }, [selectableSelector]);

  if (!sel) return null;

  const copy = async () => {
    try { await navigator.clipboard.writeText(sel.text); } catch {}
    setSel(null);
  };

  // sel.y is selection's visual top (or bottom if flipBelow).
  // sel.x is the drag-start X — bubble centers on that horizontally.
  const bubbleApproxWidth = composing ? 360 : 220;
  const bubbleApproxHeight = composing ? 200 : 36;
  const gap = 8;
  const top = sel.flipBelow
    ? Math.min(window.innerHeight - bubbleApproxHeight - 8, sel.y + gap)
    : Math.max(8, sel.y - bubbleApproxHeight - gap);
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
        <div className="flex items-center gap-1 rounded-full border bg-white px-2 py-1 shadow-lg ring-1 ring-black/5 dark:bg-zinc-900 dark:ring-white/10">
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
    <div className="w-[min(360px,92vw)] space-y-2 rounded-lg border bg-white p-3 shadow-xl ring-1 ring-black/5 dark:bg-zinc-900 dark:ring-white/10">
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
