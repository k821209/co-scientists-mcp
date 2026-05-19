// Inject yellow-highlight <mark> wrappers around anchor occurrences in
// a markdown source string.
//
// Design notes (see commits 1c0848f, 5c788d3, 4d704b5, 74357ea, 3990211):
//
//   - selection.toString() captures RENDERED text (post-react-markdown),
//     which contains rendered artifacts our source doesn't:
//     DOI status badges, the "doi:NNN/PATH" link text, line breaks
//     introduced by inline-block badge layout. Strip these from the
//     anchor before matching.
//   - The markdown SOURCE meanwhile carries {doi:N}/{fig:N}/{tab:N}
//     markers and bold/italic/code/strike tokens that the rendered text
//     doesn't. The search regex tolerates any of these sitting between
//     the anchor's words — whitespace runs in the cleaned anchor become
//     [\s\S]{0,300}? (non-greedy).
//   - Multiple anchors may overlap. Overlapping ranges merge into one
//     <mark> carrying all reviewIds (CSV) so no comment goes invisible;
//     CommentHoverPopover renders a 1/N pager when clicked.

import type { AnchorTarget } from "@/lib/remarkAnchorMarks";

export type { AnchorTarget };

export function injectAnchorMarks(body: string, anchors: AnchorTarget[]): string {
  if (!anchors || anchors.length === 0) return body;
  const sorted = [...anchors]
    .filter((a) => a.text && a.text.length >= 3)
    .sort((a, b) => b.text.length - a.text.length);

  type Match = { start: number; end: number; reviewId: string };
  const matches: Match[] = [];
  for (const a of sorted) {
    const stripped = stripRenderArtifacts(a.text);
    if (stripped.length < 3) continue;
    for (const [start, end] of findAnchorPositions(body, stripped)) {
      matches.push({ start, end, reviewId: a.reviewId });
    }
  }
  matches.sort((x, y) => x.start - y.start || x.end - y.end);

  type Group = { start: number; end: number; reviewIds: string[] };
  const groups: Group[] = [];
  for (const m of matches) {
    const last = groups[groups.length - 1];
    if (last && m.start < last.end) {
      last.end = Math.max(last.end, m.end);
      if (!last.reviewIds.includes(m.reviewId)) last.reviewIds.push(m.reviewId);
    } else {
      groups.push({ start: m.start, end: m.end, reviewIds: [m.reviewId] });
    }
  }

  let out = "";
  let pos = 0;
  for (const g of groups) {
    out += body.slice(pos, g.start);
    const inner = body.slice(g.start, g.end);
    const ids = g.reviewIds.map((id) => id.replace(/"/g, "")).join(",");
    const klass = g.reviewIds.length > 1
      ? "cs-anchor-mark cs-anchor-multi"
      : "cs-anchor-mark";
    out += `<mark class="${klass}" data-review-ids="${ids}">${inner}</mark>`;
    pos = g.end;
  }
  out += body.slice(pos);
  return out;
}

/** Strip render-only artifacts so the cleaned text can match the
 *  markdown source. Exported because SelectionBubble applies the same
 *  scrub at save time. */
export function stripRenderArtifacts(text: string): string {
  return text
    // Strip captured {doi:…}/{fig:N}/{tab:N} markers FIRST (selection
    // sometimes scoops up a marker token together with the text).
    .replace(/\{(?:doi|fig|tab):[^}]*\}/g, " ")
    .replace(/[✓⚠]/g, " ")
    // bare DOI link text — stop at brace too so we don't munch the
    // closing `}` of a marker.
    .replace(/\bdoi:[^\s)\]}]+/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Find all [start, end] offsets where `anchor` (already stripped)
 *  occurs in `body`. Tiered matcher:
 *    1. Exact substring
 *    2. Markdown-marker tolerant (whitespace between anchor words may
 *       also match `*`/`_`/`~`/backtick runs in source)
 *    3. Same as #2 plus full `{doi:…}`/`{fig:…}`/`{tab:…}` token may
 *       sit in the gap.
 *  Stops at the first tier that produces hits, so unrelated text far
 *  away never gets vacuumed up by a too-permissive regex. */
function findAnchorPositions(
  body: string,
  anchor: string,
): Array<[number, number]> {
  // Tier 1 — exact
  const exact: Array<[number, number]> = [];
  let idx = body.indexOf(anchor);
  while (idx !== -1) {
    exact.push([idx, idx + anchor.length]);
    idx = body.indexOf(anchor, idx + anchor.length);
  }
  if (exact.length > 0) return exact;

  const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  // Tier 2 — allow markdown markers between anchor words
  const t2 = escapeRe(anchor).replace(/\s+/g, "[\\s*_~`]+");
  const t2Hits = scanAll(body, t2);
  if (t2Hits.length > 0) return t2Hits;

  // Tier 3 — allow markdown markers PLUS full {x:y} tokens, ≤80 chars
  //          between anchor words. Caps prevent cross-sentence jumps.
  const gap = "(?:[\\s*_~`]|\\{[a-z]+:[^}]*\\}){0,80}?";
  const t3 = escapeRe(anchor).replace(/\s+/g, gap);
  return scanAll(body, t3);
}

function scanAll(body: string, pattern: string): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  let re: RegExp;
  try { re = new RegExp(pattern, "g"); } catch { return out; }
  for (let m: RegExpExecArray | null; (m = re.exec(body)); ) {
    out.push([m.index, m.index + m[0].length]);
    if (m[0].length === 0) re.lastIndex++;
  }
  return out;
}
