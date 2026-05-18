/** Module-level registry of comment anchor highlights.
 *
 *  Single global CSS Highlight named "comment-anchor" — all ranges across
 *  all sections + all reviews end up in it. The CSS rule
 *  `::highlight(comment-anchor)` paints them yellow.
 *
 *  We keep a JS-side map of (range → reviewId) so click handlers can
 *  find which review a click landed in via point-in-rect tests
 *  (CSS Highlights are not DOM elements, so we can't delegate events).
 */

interface Entry { range: Range; reviewId: string }

// Keyed by `${sectionKey}::${reviewId}` so a re-run of one section's hook
// only replaces its own contribution.
const entriesByOwner = new Map<string, Entry[]>();

function applyToCss() {
  const w = window as unknown as {
    Highlight?: { new (...ranges: Range[]): Highlight };
    CSS: typeof CSS;
  };
  const highlights = (w.CSS as unknown as { highlights?: Map<string, Highlight> }).highlights;
  if (!highlights || !w.Highlight) return;
  const allRanges: Range[] = [];
  for (const list of entriesByOwner.values()) {
    for (const e of list) allRanges.push(e.range);
  }
  if (allRanges.length === 0) {
    highlights.delete("comment-anchor");
    return;
  }
  highlights.set("comment-anchor", new w.Highlight(...allRanges));
}

export function setAnchorRanges(
  ownerKey: string,         // `${sectionKey}::${reviewId}`
  ranges: Range[],
  reviewId: string,
): void {
  if (ranges.length === 0) {
    entriesByOwner.delete(ownerKey);
  } else {
    entriesByOwner.set(ownerKey, ranges.map((range) => ({ range, reviewId })));
  }
  applyToCss();
}

export function clearAnchorRanges(ownerKey: string): void {
  entriesByOwner.delete(ownerKey);
  applyToCss();
}

/** Find a review whose anchor range contains (clientX, clientY). */
export function findReviewAtPoint(
  x: number, y: number,
): { reviewId: string; rect: DOMRect } | null {
  for (const list of entriesByOwner.values()) {
    for (const { range, reviewId } of list) {
      const rects = range.getClientRects();
      for (const rect of rects) {
        if (x >= rect.left && x <= rect.right &&
            y >= rect.top  && y <= rect.bottom) {
          return { reviewId, rect };
        }
      }
    }
  }
  return null;
}

/** Returns true if the point lies inside any active anchor range. */
export function isPointOnAnchor(x: number, y: number): boolean {
  return findReviewAtPoint(x, y) !== null;
}
