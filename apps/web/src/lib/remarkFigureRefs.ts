/**
 * remark plugin: turn `Figure N` / `Fig. N` / `Figure Na` text into anchor
 * links pointing at the corresponding `#figure-N` element on the same page.
 *
 * The Paper page renders each figure card with `id="figure-{N}"` so this
 * gives users one-click navigation from prose to the figure.
 *
 * Patterns matched:
 *   "Figure 1"           → #figure-1
 *   "Fig. 2"             → #figure-2
 *   "Fig 3"              → #figure-3
 *   "Figure 4a", "Fig 5b" → #figure-4, #figure-5  (panel letter stripped for nav)
 *
 * Skipped (would create false positives):
 *   bold/italic context is preserved — plugin only touches plain text nodes
 *   inside parentheses is still matched (common citation pattern)
 */
import type { Plugin } from "unified";
import type { Root, Text, Link } from "mdast";
import { visit } from "unist-util-visit";

const RE = /\b(Figure|Fig\.?)\s+(\d+)([A-Za-z])?\b/g;

type Segment = Text | Link;

function split(value: string): Segment[] | null {
  RE.lastIndex = 0;
  if (!RE.test(value)) return null;
  RE.lastIndex = 0;
  const out: Segment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = RE.exec(value)) !== null) {
    if (m.index > last) {
      out.push({ type: "text", value: value.slice(last, m.index) });
    }
    const num = m[2];
    const panel = m[3] ?? "";
    const display = `${m[1]} ${num}${panel}`;
    out.push({
      type: "link",
      url: `#figure-${num}`,
      title: null,
      children: [{ type: "text", value: display }],
    });
    last = m.index + m[0].length;
  }
  if (last < value.length) {
    out.push({ type: "text", value: value.slice(last) });
  }
  return out;
}

export const remarkFigureRefs: Plugin<[], Root> = () => {
  return (tree) => {
    visit(tree, "text", (node, index, parent) => {
      if (!parent || typeof index !== "number") return;
      // Skip if we're already inside a link — don't rewrite link text
      if (parent.type === "link") return;
      const replacement = split((node as Text).value);
      if (!replacement) return;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (parent.children as any).splice(index, 1, ...replacement);
      return ["skip", index + replacement.length];
    });
  };
};
