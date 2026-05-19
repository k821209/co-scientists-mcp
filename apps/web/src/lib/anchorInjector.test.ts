import { describe, it, expect } from "vitest";
import { injectAnchorMarks, stripRenderArtifacts } from "./anchorInjector";

describe("stripRenderArtifacts", () => {
  it("removes DOI status badges", () => {
    expect(stripRenderArtifacts("hello ✓ world")).toBe("hello world");
    expect(stripRenderArtifacts("warn ⚠ here")).toBe("warn here");
  });

  it("removes rendered doi:... link text", () => {
    expect(stripRenderArtifacts("see doi:10.1038/nature12373 paper")).toBe("see paper");
  });

  it("removes accidentally captured markdown markers", () => {
    expect(stripRenderArtifacts("intro {doi:10.1/x} next")).toBe("intro next");
    expect(stripRenderArtifacts("Figure {fig:1} caption")).toBe("Figure caption");
  });

  it("collapses whitespace", () => {
    expect(stripRenderArtifacts("a\n\n  b\t c")).toBe("a b c");
  });

  it("handles the field-reported case", () => {
    const raw = "nchored plant molecular biology for more than two decades \n✓\ndoi:10.1038/35048692\n.";
    const cleaned = stripRenderArtifacts(raw);
    expect(cleaned).toBe("nchored plant molecular biology for more than two decades .");
  });
});

describe("injectAnchorMarks", () => {
  it("returns body unchanged when no anchors", () => {
    expect(injectAnchorMarks("hello world", [])).toBe("hello world");
  });

  it("wraps a simple exact match", () => {
    const out = injectAnchorMarks("hello world", [{ text: "world", reviewId: "r1" }]);
    expect(out).toBe(
      'hello <mark class="cs-anchor-mark" data-review-ids="r1">world</mark>',
    );
  });

  it("tolerates markdown bold markers between anchor words", () => {
    const body = "**T2T plant** assemblies are routine";
    const anchor = { text: "T2T plant assemblies", reviewId: "r1" };
    const out = injectAnchorMarks(body, [anchor]);
    expect(out).toContain('<mark');
    expect(out).toContain("T2T plant");
    expect(out).toContain("assemblies");
  });

  it("tolerates {doi:...} markers between anchor words (the field bug)", () => {
    const body = "anchored plant molecular biology for more than two decades {doi:10.1038/35048692}. Yet Col-0 stops here";
    // Anchor stored from selection.toString() includes rendered ✓ + doi: text
    const anchor = {
      text: "nchored plant molecular biology for more than two decades \n✓\ndoi:10.1038/35048692\n.",
      reviewId: "r1",
    };
    const out = injectAnchorMarks(body, [anchor]);
    expect(out).toContain('<mark class="cs-anchor-mark" data-review-ids="r1">');
    // The literal {doi:...} marker should be inside the mark since the
    // anchor's range covers it.
    const markStart = out.indexOf("<mark");
    const markEnd = out.indexOf("</mark>");
    expect(out.slice(markStart, markEnd)).toContain("{doi:10.1038/35048692}");
  });

  it("merges overlapping anchors into one mark with all reviewIds", () => {
    const body = "the quick brown fox jumps over the lazy dog";
    const anchors = [
      { text: "quick brown fox", reviewId: "a" },
      { text: "brown fox jumps", reviewId: "b" },
    ];
    const out = injectAnchorMarks(body, anchors);
    // Only ONE mark, carrying both IDs
    const markCount = (out.match(/<mark/g) ?? []).length;
    expect(markCount).toBe(1);
    expect(out).toContain('data-review-ids="a,b"');
    expect(out).toContain("cs-anchor-multi");
  });

  it("keeps non-overlapping anchors as separate marks", () => {
    const body = "section one. section two. section three.";
    const out = injectAnchorMarks(body, [
      { text: "section one", reviewId: "a" },
      { text: "section three", reviewId: "b" },
    ]);
    const markCount = (out.match(/<mark/g) ?? []).length;
    expect(markCount).toBe(2);
    expect(out).toContain('data-review-ids="a"');
    expect(out).toContain('data-review-ids="b"');
  });

  it("skips anchors shorter than 3 chars", () => {
    expect(injectAnchorMarks("hi there", [{ text: "hi", reviewId: "r1" }]))
      .toBe("hi there");
  });

  it("doesn't crash on regex-special-char anchors", () => {
    const body = "see (a+b)*c here";
    const out = injectAnchorMarks(body, [{ text: "(a+b)*c", reviewId: "r1" }]);
    expect(out).toContain("<mark");
  });

  it("strips render artifacts from anchor before search", () => {
    const body = "anchored plant biology";
    const anchor = { text: "anchored ✓ plant biology", reviewId: "r1" };
    const out = injectAnchorMarks(body, [anchor]);
    expect(out).toContain('<mark');
    expect(out).toContain("anchored plant biology");
  });

  it("escapes double quotes inside reviewId in the attribute", () => {
    // reviewId from Firestore shouldn't contain quotes, but be defensive
    const out = injectAnchorMarks("hello world", [
      { text: "world", reviewId: 'r"injected' },
    ]);
    // We just strip quotes from the ID to avoid breaking the attribute
    expect(out).toContain('data-review-ids="rinjected"');
  });

  it("handles the {fig:N} marker case", () => {
    const body = "the gene expression {fig:2} showed";
    const anchor = { text: "the gene expression showed", reviewId: "r1" };
    const out = injectAnchorMarks(body, [anchor]);
    expect(out).toContain("<mark");
    const markText = out.match(/<mark[^>]*>(.*?)<\/mark>/s)?.[1] ?? "";
    expect(markText).toContain("{fig:2}");
  });
});
