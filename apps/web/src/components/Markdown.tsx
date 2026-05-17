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
import "katex/dist/katex.min.css";

import { cn } from "@/lib/utils";
import { remarkDoi } from "@/lib/remarkDoi";

interface MarkdownProps {
  children: string;
  className?: string;
}

export function Markdown({ children, className }: MarkdownProps) {
  return (
    <div className={cn("prose-co-scientist", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath, remarkDoi]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Use Tailwind classes rather than @tailwindcss/typography to keep
          // bundle small. Tweak per-element styling here.
          h1: ({ children }) => <h2 className="mt-4 mb-2 text-xl font-semibold">{children}</h2>,
          h2: ({ children }) => <h3 className="mt-4 mb-2 text-lg font-semibold">{children}</h3>,
          h3: ({ children }) => <h4 className="mt-3 mb-1.5 text-base font-semibold">{children}</h4>,
          p: ({ children }) => <p className="my-2 leading-relaxed">{children}</p>,
          ul: ({ children }) => <ul className="my-2 ml-5 list-disc space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 ml-5 list-decimal space-y-1">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline underline-offset-2 hover:no-underline"
            >
              {children}
            </a>
          ),
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
        {children}
      </ReactMarkdown>
    </div>
  );
}
