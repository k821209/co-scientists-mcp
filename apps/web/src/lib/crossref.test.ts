import { describe, it, expect, vi, afterEach } from "vitest";
import {
  normalizeDoi, sharedTitleWords, substantiveWordCount,
  sentenceAround, extractDoiContexts, fetchCrossref, verifyOne,
  DoiNotFound,
} from "./crossref";

describe("normalizeDoi", () => {
  it("strips https://doi.org/ prefix", () => {
    expect(normalizeDoi("https://doi.org/10.1/x")).toBe("10.1/x");
  });
  it("strips http + doi: prefixes", () => {
    expect(normalizeDoi("http://doi.org/10.1/x")).toBe("10.1/x");
    expect(normalizeDoi("doi:10.1/x")).toBe("10.1/x");
  });
  it("trims whitespace and leading slashes", () => {
    expect(normalizeDoi("  /10.1/x  ")).toBe("10.1/x");
  });
  it("leaves a bare DOI unchanged", () => {
    expect(normalizeDoi("10.1038/nature12373")).toBe("10.1038/nature12373");
  });
});

describe("sharedTitleWords", () => {
  it("counts substantive shared words, ignoring stopwords", () => {
    const n = sharedTitleWords(
      "the plant pangenome of arabidopsis",
      "a pangenome reference for arabidopsis thaliana",
    );
    expect(n).toBe(2);  // pangenome, arabidopsis ('the','a','of','for' are stopwords)
  });
  it("is zero for unrelated titles", () => {
    expect(sharedTitleWords(
      "T2T plant assembly",
      "Somatic mutation rates across mammals",
    )).toBe(0);
  });
  it("ignores short words (<3 chars)", () => {
    expect(sharedTitleWords("an ox or", "an ox or")).toBe(0);
  });
});

describe("substantiveWordCount", () => {
  it("counts non-stopword words ≥3 chars", () => {
    expect(substantiveWordCount("the quick brown fox")).toBe(3);  // quick, brown, fox
  });
  it("is zero for a stopword-only string", () => {
    expect(substantiveWordCount("the and of to")).toBe(0);
  });
});

describe("sentenceAround", () => {
  it("extracts the sentence containing the range", () => {
    const body = "First sentence. The marker is HERE in the middle. Last one.";
    const idx = body.indexOf("HERE");
    const s = sentenceAround(body, idx, idx + 4);
    expect(s).toBe("The marker is HERE in the middle");
  });
  it("handles range at the start of the body", () => {
    const body = "Opening words then more text.";
    const s = sentenceAround(body, 0, 7);
    expect(s).toBe("Opening words then more text");
  });
});

describe("extractDoiContexts", () => {
  it("finds {doi:X} markers with their section + sentence", () => {
    const sections = [
      { key: "intro", body: "Pangenomes are useful {doi:10.1/a} for crops." },
      { key: "methods", body: "We used method {doi:10.1/b}." },
    ];
    const ctx = extractDoiContexts(sections);
    expect(ctx.get("10.1/a")?.[0].section).toBe("intro");
    expect(ctx.get("10.1/a")?.[0].sentence).toContain("Pangenomes are useful");
    expect(ctx.get("10.1/b")?.[0].section).toBe("methods");
  });
  it("returns an empty map when there are no markers", () => {
    expect(extractDoiContexts([{ key: "x", body: "no markers here" }]).size).toBe(0);
  });
  it("collects multiple occurrences of the same DOI", () => {
    const ctx = extractDoiContexts([
      { key: "a", body: "first {doi:10.1/x}. second {doi:10.1/x}." },
    ]);
    expect(ctx.get("10.1/x")?.length).toBe(2);
  });
});

// ─── network-mocked fetchCrossref / verifyOne ───────────────────────────

afterEach(() => { vi.restoreAllMocks(); });

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => ({
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  })));
}

describe("fetchCrossref", () => {
  it("normalizes a 200 response", async () => {
    mockFetch(200, {
      message: {
        DOI: "10.1/x",
        title: ["A study"],
        author: [{ given: "Jane", family: "Smith" }],
        "container-title": ["Cell"],
        issued: { "date-parts": [[2024]] },
      },
    });
    const meta = await fetchCrossref("10.1/x");
    expect(meta.title).toBe("A study");
    expect(meta.authors).toEqual(["Jane Smith"]);
    expect(meta.journal).toBe("Cell");
    expect(meta.year).toBe(2024);
  });

  it("throws DoiNotFound on 404", async () => {
    mockFetch(404, {});
    await expect(fetchCrossref("10.9/fake")).rejects.toBeInstanceOf(DoiNotFound);
  });

  it("rejects an empty DOI", async () => {
    await expect(fetchCrossref("")).rejects.toThrow(/required/);
  });
});

describe("verifyOne", () => {
  it("returns resolved for a real DOI", async () => {
    mockFetch(200, { message: { DOI: "10.1/x", title: ["Plant pangenome study"] } });
    const v = await verifyOne("10.1/x", "Plant pangenome study");
    expect(v.kind).toBe("resolved");
  });

  it("returns unresolved on 404", async () => {
    mockFetch(404, {});
    const v = await verifyOne("10.9/fake", "anything");
    expect(v.kind).toBe("unresolved");
  });

  it("returns missing_doi for empty input", async () => {
    const v = await verifyOne("", "title");
    expect(v.kind).toBe("missing_doi");
  });

  it("flags title_mismatch when stored title diverges", async () => {
    mockFetch(200, { message: { DOI: "10.1/x", title: ["Completely different mammal genetics"] } });
    const v = await verifyOne("10.1/x", "Plant pangenome of arabidopsis");
    expect(v.kind).toBe("title_mismatch");
  });
});
