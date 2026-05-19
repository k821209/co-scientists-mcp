/**
 * Markdown renderer used across the dashboard for manuscript section bodies,
 * comments, and any user-authored content.
 *
 * Stack:
 *   react-markdown        — CommonMark + extensible AST
 *   remark-gfm            — tables, strikethrough, task lists, autolinks
 *   remark-math           — `$inline$` and `$$display$$` math syntax
 *   rehype-katex          — render math AST to HTML using KaTeX
 *   katex CSS             — fonts + styles (imported once here)
 *
 * Co-scientist convention: math uses `$...$` and `$$...$$` (matches Pandoc).
 * Plain `n = 69`, `α-helix`, `q < 0.005` stays as plain text — same rule as
 * the original repo's `math_lint.py`.
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import "katex/dist/katex.min.css";

import { cn } from "@/lib/utils";
import { remarkDoi } from "@/lib/remarkDoi";
import { remarkFigureRefs } from "@/lib/remarkFigureRefs";
import { remarkTableRefs } from "@/lib/remarkTableRefs";
import type { AnchorTarget } from "@/lib/remarkAnchorMarks";

interface MarkdownProps {
  children: string;
  className?: string;
  /** DOIs that ARE registered in the paper's references collection — used
   *  to badge `{doi:…}` citations ✓ when present, ⚠ when missing. */
  knownDois?: ReadonlySet<string>;
  /** When provided, wraps every occurrence of `text` in <mark> with
   *  data-review-id=reviewId. Used to render comment anchor highlights
   *  as React-managed DOM so they survive re-renders. */
  anchors?: AnchorTarget[];
}

function extractDoiFromHref(href: string | undefined): string | null {
  if (!href) return null;
  const m = href.match(/^https?:\/\/(?:dx\.)?doi\.org\/(.+)$/i);
  return m ? m[1] : null;
}

function injectAnchorMarks(body: string, anchors: AnchorTarget[]): string {
  if (!anchors || anchors.length === 0) return body;
  // selection.toString() captures the RENDERED text (no markdown markers);
  // tolerate **bold**, _italic_, `code`, ~~strike~~ tokens sitting in the
  // source between the anchor's words.
  const sorted = [...anchors]
    .filter((a) => a.text && a.text.length >= 3)
    .sort((a, b) => b.text.length - a.text.length);

  type Match = { start: number; end: number; reviewId: string };
  const matches: Match[] = [];
  for (const a of sorted) {
    const escaped = a.text
      .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      .replace(/\s+/g, "[\\s*_~`]+");
    let re: RegExp;
    try {
      re = new RegExp(escaped, "g");
    } catch { continue; }
    for (let m: RegExpExecArray | null; (m = re.exec(body)); ) {
      matches.push({ start: m.index, end: m.index + m[0].length, reviewId: a.reviewId });
      if (m[0].length === 0) re.lastIndex++;
    }
  }
  matches.sort((x, y) => x.start - y.start || x.end - y.end);

  // MERGE overlapping ranges into one mark carrying all reviewIds, so
  // overlapping comments don't disappear behind each other. The popover
  // reads `data-review-ids` (CSV) and lets the user page through them.
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

export function Markdown({ children, className, knownDois, anchors }: MarkdownProps) {
  const source = anchors && anchors.length > 0
    ? injectAnchorMarks(children, anchors)
    : children;
  return (
    <div className={cn("prose-co-scientist", className)}>
      <ReactMarkdown
        remarkPlugins={[
          remarkGfm, remarkMath, remarkDoi, remarkFigureRefs, remarkTableRefs,
        ]}
        rehypePlugins={[rehypeRaw, rehypeKatex]}
        components={{
          mark: ({ children, node, ...props }) => {
            // Read the IDs from any of the places they might land:
            // - React kebab-case prop (HTML attribute pass-through)
            // - React camelCase prop (hast-util-to-jsx-runtime normalization)
            // - hast node.properties (always present, kebab-case keys)
            const p = props as Record<string, unknown> & {
              className?: string;
            };
            const fromProps =
              (p["data-review-ids"] as string | undefined) ??
              (p["dataReviewIds"] as string | undefined) ??
              "";
            const hastProps = (node as { properties?: Record<string, unknown> } | undefined)?.properties;
            const fromNode = hastProps
              ? ((hastProps["data-review-ids"] as string | undefined) ??
                 (hastProps["dataReviewIds"] as string | undefined) ?? "")
              : "";
            const ids = (fromProps || fromNode)
              .split(",").map((s) => s.trim()).filter(Boolean);
            const multi = ids.length > 1;
            // Inline style: survives Tailwind Preflight + mobile mark reset.
            // Explicitly write data-review-ids so the popover's
            // mark.dataset.reviewIds always sees it, regardless of how
            // hast-util-to-jsx-runtime spelled the incoming prop.
            return (
              <mark
                className="cs-anchor-mark"
                data-review-ids={ids.join(",")}
                style={{
                  backgroundColor: multi ? "#fcd34d" : "#fde68a",
                  color: "inherit",
                  borderRadius: "2px",
                  padding: "0 2px",
                  cursor: "pointer",
                  boxShadow: multi ? "inset 0 -2px 0 #f59e0b" : undefined,
                }}
              >
                {children}
                {multi && (
                  <sup
                    style={{
                      marginLeft: 2,
                      fontSize: "0.65em",
                      fontWeight: 600,
                      color: "#92400e",
                    }}
                  >
                    ×{ids.length}
                  </sup>
                )}
              </mark>
            );
          },
          // Use Tailwind classes rather than @tailwindcss/typography to keep
          // bundle small. Tweak per-element styling here.
          h1: ({ children }) => <h2 className="mt-4 mb-2 text-xl font-semibold">{children}</h2>,
          h2: ({ children }) => <h3 className="mt-4 mb-2 text-lg font-semibold">{children}</h3>,
          h3: ({ children }) => <h4 className="mt-3 mb-1.5 text-base font-semibold">{children}</h4>,
          p: ({ children }) => <p className="my-2 leading-relaxed">{children}</p>,
          ul: ({ children }) => <ul className="my-2 ml-5 list-disc space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 ml-5 list-decimal space-y-1">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          a: ({ href, children }) => {
            // In-page anchor (e.g. #figure-2) — let the browser handle natively
            if (href?.startsWith("#")) {
              return (
                <a
                  href={href}
                  className="text-primary underline underline-offset-2 hover:no-underline"
                >
                  {children}
                </a>
              );
            }
            const doi = extractDoiFromHref(href);
            if (doi !== null) {
              // DOI link — check against paper's registered references
              const known = knownDois?.has(doi);
              if (knownDois) {
                const cls = known
                  ? "text-emerald-700 hover:text-emerald-900"
                  : "text-amber-700 hover:text-amber-900";
                const title = known
                  ? "registered reference"
                  : "DOI not in this paper's references — run /literature-review or add it";
                return (
                  <a
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    title={title}
                    className={cn(
                      "inline-flex items-baseline gap-1 underline underline-offset-2 hover:no-underline",
                      cls,
                    )}
                  >
                    <span aria-hidden="true">{known ? "✓" : "⚠"}</span>
                    <span>{children}</span>
                  </a>
                );
              }
              // No knownDois passed — render as a plain DOI link
            }
            return (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                className="text-primary underline underline-offset-2 hover:no-underline"
              >
                {children}
              </a>
            );
          },
          code: ({ className: codeClass, children, ...rest }) => {
            const isInline = !codeClass?.startsWith("language-");
            return isInline ? (
              <code
                className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
                {...rest}
              >
                {children}
              </code>
            ) : (
              <code className={codeClass} {...rest}>
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="my-3 overflow-x-auto rounded-md border bg-muted/50 p-3 text-xs leading-relaxed">
              {children}
            </pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-primary/40 pl-3 italic text-muted-foreground">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b bg-muted/40 px-2 py-1 text-left font-semibold">{children}</th>
          ),
          td: ({ children }) => (
            <td className="border-b px-2 py-1">{children}</td>
          ),
          hr: () => <hr className="my-4 border-border" />,
          img: ({ src, alt }) => (
            <img src={src} alt={alt} className="my-3 max-w-full rounded-md border" />
          ),
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
