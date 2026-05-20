import { describe, it, expect } from "vitest";
import { generateApiKey, maskKey } from "./projectKey";

describe("generateApiKey", () => {
  it("has the csk_ prefix and 48 hex chars", () => {
    const k = generateApiKey();
    expect(k).toMatch(/^csk_[0-9a-f]{48}$/);
  });

  it("is unique across calls", () => {
    const keys = new Set(Array.from({ length: 100 }, () => generateApiKey()));
    expect(keys.size).toBe(100);
  });
});

describe("maskKey", () => {
  it("returns em-dash for empty input", () => {
    expect(maskKey(undefined)).toBe("—");
    expect(maskKey("")).toBe("—");
  });

  it("returns short keys unchanged", () => {
    expect(maskKey("csk_1234")).toBe("csk_1234");
  });

  it("masks the middle of a real key", () => {
    const k = "csk_" + "a".repeat(48);
    const masked = maskKey(k);
    expect(masked.startsWith("csk_aaaa")).toBe(true);
    expect(masked).toContain("…");
    expect(masked.endsWith("aaaa")).toBe(true);
    expect(masked.length).toBeLessThan(k.length);
  });
});
