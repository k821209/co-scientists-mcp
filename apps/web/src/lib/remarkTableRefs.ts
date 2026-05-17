/**
 * remark plugin: turn `Table N` / `Tab. N` text into anchor links pointing
 * at the corresponding `#table-N` element. Companion to remarkFigureRefs.
 */
import type { Plugin } from "unified";
import type { Root, Text, Link } from "mdast";
import { visit } from "unist-util-visit";

const RE = /\b(Table|Tab\.?)\s+(\d+)([A-Za-z])?\b/g;

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
    out.push({
      type: "link",
      url: `#table-${num}`,
      title: null,
      children: [{ type: "text", value: `${m[1]} ${num}${panel}` }],
    });
    last = m.index + m[0].length;
  }
  if (last < value.length) {
    out.push({ type: "text", value: value.slice(last) });
  }
  return out;
}

export const remarkTableRefs: Plugin<[], Root> = () => {
  return (tree) => {
    visit(tree, "text", (node, index, parent) => {
      if (!parent || typeof index !== "number") return;
      if (parent.type === "link") return;
      const replacement = split((node as Text).value);
      if (!replacement) return;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (parent.children as any).splice(index, 1, ...replacement);
      return ["skip", index + replacement.length];
    });
  };
};
