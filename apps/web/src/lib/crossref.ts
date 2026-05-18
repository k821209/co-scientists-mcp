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

// ─── high-level verdict per reference ──────────────────────────────────────
export type Verdict =
  | { kind: "resolved"; meta: CrossrefMeta; sharedWords: number }
  | { kind: "unresolved"; doi: string }                       // hallucinated
  | { kind: "title_mismatch"; meta: CrossrefMeta; sharedWords: number; storedTitle: string }
  | { kind: "missing_doi" }
  | { kind: "error"; message: string };

export async function verifyOne(
  doi: string | null | undefined,
  storedTitle: string,
  signal?: AbortSignal,
): Promise<Verdict> {
  const d = (doi ?? "").trim();
  if (!d) return { kind: "missing_doi" };
  try {
    const meta = await fetchCrossref(d, signal);
    const shared = sharedTitleWords(storedTitle ?? "", meta.title);
    if ((storedTitle ?? "").trim() && shared < 3) {
      return { kind: "title_mismatch", meta, sharedWords: shared, storedTitle };
    }
    return { kind: "resolved", meta, sharedWords: shared };
  } catch (e) {
    if (e instanceof DoiNotFound) return { kind: "unresolved", doi: d };
    return { kind: "error", message: (e as Error).message };
  }
}
