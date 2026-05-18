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
  // Longest first so 'plant pangenome' doesn't get pre-empted by 'plant'.
  const sorted = [...anchors]
    .filter((a) => a.text && a.text.length >= 3)
    .sort((a, b) => b.text.length - a.text.length);
  let out = body;
  const consumedRanges: Array<[number, number]> = [];
  for (const a of sorted) {
    const re = new RegExp(
      a.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
      "g",
    );
    out = out.replace(re, (match, offset: number) => {
      // Avoid re-wrapping inside an already-injected <mark>
      for (const [s, e] of consumedRanges) {
        if (offset >= s && offset < e) return match;
      }
      const wrapped = `<mark class="cs-anchor-mark" data-review-id="${
        a.reviewId.replace(/"/g, "")
      }">${match}</mark>`;
      consumedRanges.push([offset, offset + wrapped.length]);
      return wrapped;
    });
  }
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
          mark: ({ children, ...props }) => (
            <mark
              {...(props as React.HTMLAttributes<HTMLElement>)}
              className="cs-anchor-mark"
              // Inline style so this works regardless of Tailwind purge or
              // mobile browser <mark> default reset.
              style={{
                backgroundColor: "#fde68a",
                color: "inherit",
                borderRadius: "2px",
                padding: "0 2px",
                cursor: "pointer",
              }}
            >
              {children}
            </mark>
          ),
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
