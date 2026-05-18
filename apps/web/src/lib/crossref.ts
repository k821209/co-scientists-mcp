/** Browser-side CrossRef DOI verifier. Mirrors apps/local-mcp's
 *  tools/references.py logic so the dashboard "Sync DOIs" button gives
 *  the same verdicts as the MCP's validate_references tool. */

const CROSSREF_BASE = "https://api.crossref.org/works/";
const CROSSREF_UA = "co-scientist-web/0.1 (mailto:dev@co-scientist.example)";

export class DoiNotFound extends Error {
  constructor(public doi: string) {
    super(`DOI not found in CrossRef: ${doi}`);
    this.name = "DoiNotFound";
  }
}

export interface CrossrefMeta {
  doi: string;
  title: string;
  authors: string[];
  journal: string | null;
  year: number | null;
  url: string | null;
  type: string | null;
}

/** Strip URL prefix / lowercase / trim. */
export function normalizeDoi(input: string): string {
  let doi = (input || "").trim().replace(/^\/+/, "");
  for (const prefix of ["https://doi.org/", "http://doi.org/", "doi:"]) {
    if (doi.toLowerCase().startsWith(prefix)) {
      doi = doi.slice(prefix.length);
      break;
    }
  }
  return doi;
}

export async function fetchCrossref(rawDoi: string, signal?: AbortSignal): Promise<CrossrefMeta> {
  const doi = normalizeDoi(rawDoi);
  if (!doi) throw new Error("doi is required");
  const url = CROSSREF_BASE + encodeURI(doi);
  const resp = await fetch(url, {
    headers: { "User-Agent": CROSSREF_UA },
    signal,
  });
  if (resp.status === 404) throw new DoiNotFound(doi);
  if (!resp.ok) throw new Error(`CrossRef HTTP ${resp.status} for ${doi}`);
  const payload = await resp.json();
  return normalize(payload.message ?? {}, doi);
}

function normalize(msg: Record<string, unknown>, fallbackDoi: string): CrossrefMeta {
  const titleList = (msg.title as string[] | undefined) ?? [];
  const containerList = (msg["container-title"] as string[] | undefined) ?? [];
  const issued = (msg.issued as { "date-parts"?: number[][] } | undefined)?.["date-parts"] ?? [[]];
  const authors: string[] = [];
  for (const a of (msg.author as Array<{ given?: string; family?: string; name?: string }> | undefined) ?? []) {
    const full = `${a.given ?? ""} ${a.family ?? ""}`.trim() || a.name || "";
    if (full) authors.push(full);
  }
  return {
    doi: ((msg.DOI as string) || fallbackDoi).toLowerCase(),
    title: titleList[0] ?? "",
    authors,
    journal: containerList[0] ?? null,
    year: issued[0]?.[0] ?? null,
    url: (msg.URL as string) ?? null,
    type: (msg.type as string) ?? null,
  };
}

// ─── title-match heuristic (mirrors references.py _shared_words) ───────────
const STOPWORDS = new Set([
  "a", "an", "the", "of", "and", "or", "in", "on", "for", "to", "from",
  "with", "by", "is", "are", "was", "were", "be", "been", "as", "at",
  "this", "that", "these", "those", "we", "our", "their", "its",
]);

export function sharedTitleWords(a: string, b: string): number {
  const words = (s: string) =>
    new Set(
      (s.toLowerCase().match(/[a-z]+/g) ?? []).filter(
        (w) => w.length > 2 && !STOPWORDS.has(w),
      ),
    );
  const A = words(a);
  const B = words(b);
  let n = 0;
  for (const w of A) if (B.has(w)) n++;
  return n;
}

export function substantiveWordCount(s: string): number {
  return new Set(
    (s.toLowerCase().match(/[a-z]+/g) ?? []).filter(
      (w) => w.length > 2 && !STOPWORDS.has(w),
    ),
  ).size;
}

/** Extract the sentence around a {doi:X} marker in section text. */
export function sentenceAround(body: string, start: number, end: number): string {
  let s = start;
  while (s > 0 && !".!?\n".includes(body[s - 1])) s--;
  let e = end;
  while (e < body.length && !".!?\n".includes(body[e])) e++;
  return body.slice(s, e).trim();
}

/** Scan section bodies for {doi:X} markers, return {doi: [{section, sentence}]}. */
export function extractDoiContexts(
  sections: Array<{ key?: string; body?: string }>,
): Map<string, Array<{ section: string; sentence: string }>> {
  const contexts = new Map<string, Array<{ section: string; sentence: string }>>();
  const pattern = /\{doi:([^}\s]+)\}/gi;
  for (const sec of sections) {
    const body = sec.body || "";
    if (!body) continue;
    let m: RegExpExecArray | null;
    while ((m = pattern.exec(body)) !== null) {
      const doi = m[1].toLowerCase();
      const sentence = sentenceAround(body, m.index, m.index + m[0].length);
      const arr = contexts.get(doi) ?? [];
      arr.push({ section: sec.key ?? "", sentence });
      contexts.set(doi, arr);
    }
  }
  return contexts;
}

// ─── high-level verdict per reference ──────────────────────────────────────
export interface DoiContext { section: string; sentence: string }

export type Verdict =
  | { kind: "resolved"; meta: CrossrefMeta; sharedWords: number; contextShared?: number }
  | { kind: "unresolved"; doi: string }
  | { kind: "title_mismatch"; meta: CrossrefMeta; sharedWords: number; storedTitle: string }
  | { kind: "context_mismatch"; meta: CrossrefMeta; sharedWords: number; worstContext: DoiContext }
  | { kind: "missing_doi" }
  | { kind: "error"; message: string };

export async function verifyOne(
  doi: string | null | undefined,
  storedTitle: string,
  contexts: DoiContext[],
  signal?: AbortSignal,
): Promise<Verdict> {
  const d = (doi ?? "").trim();
  if (!d) return { kind: "missing_doi" };
  try {
    const meta = await fetchCrossref(d, signal);
    const titleShared = sharedTitleWords(storedTitle ?? "", meta.title);

    // Context check — find the best-matching ctx, gate on substantive
    // word count so "(reviewed in {doi:X})" doesn't false-positive.
    const checkable = contexts.filter(
      (c) => substantiveWordCount(c.sentence) >= 3,
    );
    let bestCtxShared = -1;
    let worstCtx: DoiContext | null = null;
    for (const c of checkable) {
      const n = sharedTitleWords(c.sentence, meta.title);
      if (n > bestCtxShared) bestCtxShared = n;
      if (worstCtx === null ||
          n < sharedTitleWords(worstCtx.sentence, meta.title)) {
        worstCtx = c;
      }
    }

    // Context mismatch is the LOUDEST signal — preferred verdict when it fires.
    if (checkable.length > 0 && bestCtxShared < 2 && worstCtx) {
      return {
        kind: "context_mismatch", meta, sharedWords: bestCtxShared, worstContext: worstCtx,
      };
    }
    if ((storedTitle ?? "").trim() && titleShared < 3) {
      return { kind: "title_mismatch", meta, sharedWords: titleShared, storedTitle };
    }
    return {
      kind: "resolved", meta, sharedWords: titleShared,
      contextShared: bestCtxShared >= 0 ? bestCtxShared : undefined,
    };
  } catch (e) {
    if (e instanceof DoiNotFound) return { kind: "unresolved", doi: d };
    return { kind: "error", message: (e as Error).message };
  }
}
