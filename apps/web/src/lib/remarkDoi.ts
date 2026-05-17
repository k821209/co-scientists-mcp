/**
 * remark plugin: turn `{doi:10.xxx/yyy}` into clickable links to doi.org.
 *
 * The original co-scientist convention is `{doi:10.xxx/yyy}` inline in the
 * manuscript (per CLAUDE.md). Pandoc resolves these to BibTeX entries on
 * export. For the live dashboard view, we want them rendered as links.
 *
 * Also autolinks bare `https://doi.org/10.xxx` URLs the same way (the
 * default markdown autolinker handles most URLs but the DOI URL family
 * benefits from a consistent styled treatment).
 */
import type { Plugin } from "unified";
import type { Root, Text, Link } from "mdast";
import { visit } from "unist-util-visit";

const DOI_INLINE = /\{doi:([^}]+)\}/g;
const DOI_URL = /\b(https?:\/\/(?:dx\.)?doi\.org\/(10\.\d{4,9}\/[-._;()/:A-Z0-9]+))/gi;

type Segment = Text | Link;

function splitTextByDoi(value: string): Segment[] | null {
  // Two-pass: first replace inline {doi:…}, then bare doi.org URLs.
  // If neither pattern matches, return null so caller skips the node.
  const hasInline = DOI_INLINE.test(value);
  DOI_INLINE.lastIndex = 0;
  const hasUrl = DOI_URL.test(value);
  DOI_URL.lastIndex = 0;
  if (!hasInline && !hasUrl) return null;

  // Tokenize: walk through the string collecting either text or link tokens
  // for each match of the combined pattern.
  const combined = new RegExp(`${DOI_INLINE.source}|${DOI_URL.source}`, "gi");
  const segments: Segment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = combined.exec(value)) !== null) {
    if (m.index > last) {
      segments.push({ type: "text", value: value.slice(last, m.index) });
    }
    // m[1] = inline {doi:X} capture (the DOI itself, no scheme)
    // m[2] = URL form full URL,   m[3] = DOI portion of URL
    const inlineDoi = m[1];
    const fullUrl = m[2];
    const urlDoi = m[3];
    if (inlineDoi !== undefined) {
      segments.push({
        type: "link",
        url: `https://doi.org/${inlineDoi}`,
        title: null,
        children: [{ type: "text", value: `doi:${inlineDoi}` }],
      });
    } else if (fullUrl !== undefined && urlDoi !== undefined) {
      segments.push({
        type: "link",
        url: fullUrl,
        title: null,
        children: [{ type: "text", value: `doi:${urlDoi}` }],
      });
    }
    last = m.index + m[0].length;
  }
  if (last < value.length) {
    segments.push({ type: "text", value: value.slice(last) });
  }
  return segments;
}

export const remarkDoi: Plugin<[], Root> = () => {
  return (tree) => {
    visit(tree, "text", (node, index, parent) => {
      if (!parent || typeof index !== "number") return;
      const replacement = splitTextByDoi((node as Text).value);
      if (!replacement) return;
      // unist parent.children type is PhrasingContent[] in mdast contexts;
      // our Segments (Text | Link) are valid PhrasingContent.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (parent.children as any).splice(index, 1, ...replacement);
      return ["skip", index + replacement.length];
    });
  };
};
