/** remark plugin: wrap occurrences of given `anchor_text` strings in
 *  <mark> elements at parse time so they're part of React's virtual DOM
 *  and survive every re-render. The earlier DOM-mutation and CSS Custom
 *  Highlight API approaches both fought React's reconciliation; this
 *  doesn't.
 *
 *  Pass `anchors = [{text, reviewId}, ...]`. Any text node containing
 *  one of those substrings gets split into [before, <mark>, after] in
 *  the MDAST. rehype renders the mark as <mark class="cs-anchor-mark"
 *  data-review-id="...">. The click handler in CommentHoverPopover
 *  delegates on that selector.
 *
 *  Limitation: anchor must fit inside a single text node. Selections
 *  that crossed bold/link/inline-code boundaries won't render an inline
 *  mark — the comment itself still works, just no highlight.
 */
import { visit, SKIP } from "unist-util-visit";
import type { Plugin } from "unified";
import type { Root, Text, Parent, RootContent } from "mdast";

export interface AnchorTarget {
  text: string;
  reviewId: string;
}

// Custom node type — mdast-util-to-hast's "unknown handler" produces an
// element from data.hName/hProperties even for unrecognized types.
// We tried emphasis-with-hName-override but the emphasis handler in some
// versions doesn't apply data.hName, leaving us with <em> instead of <mark>.
interface MarkNode extends Parent {
  type: "anchorMark";
  data: {
    hName: "mark";
    hProperties: { className: "cs-anchor-mark"; "data-review-id": string };
  };
  children: Text[];
}

export const remarkAnchorMarks: Plugin<[AnchorTarget[]], Root> = (anchors) => {
  // Build a quick map by text, prefer longest first so substrings of
  // bigger anchors don't pre-empt them.
  const sorted = [...(anchors ?? [])]
    .filter((a) => a.text && a.text.length >= 3)
    .sort((a, b) => b.text.length - a.text.length);
  return (tree) => {
    if (sorted.length === 0) return;
    visit(tree, "text", (node: Text, index, parent: Parent | undefined) => {
      if (!parent || index == null) return;
      // Don't process text inside an already-created mark
      if ((parent as { type: string }).type === "anchorMark") return SKIP;
      const text = node.value;
      // Find the earliest match across all anchors in this text node.
      let bestStart = -1;
      let bestEnd = -1;
      let bestReviewId = "";
      for (const a of sorted) {
        const i = text.indexOf(a.text);
        if (i === -1) continue;
        if (bestStart === -1 || i < bestStart ||
            (i === bestStart && a.text.length > bestEnd - bestStart)) {
          bestStart = i;
          bestEnd = i + a.text.length;
          bestReviewId = a.reviewId;
        }
      }
      if (bestStart === -1) return;

      const before = text.slice(0, bestStart);
      const anchor = text.slice(bestStart, bestEnd);
      const after = text.slice(bestEnd);

      const replacement: RootContent[] = [];
      if (before) replacement.push({ type: "text", value: before });
      const mark: MarkNode = {
        type: "anchorMark",
        data: {
          hName: "mark",
          hProperties: {
            className: "cs-anchor-mark",
            "data-review-id": bestReviewId,
          },
        },
        children: [{ type: "text", value: anchor }],
      };
      replacement.push(mark as unknown as RootContent);
      if (after) replacement.push({ type: "text", value: after });

      parent.children.splice(index, 1, ...replacement);
      // Continue past the inserted nodes so we keep matching after `after`.
      return index + replacement.length;
    });
  };
};
