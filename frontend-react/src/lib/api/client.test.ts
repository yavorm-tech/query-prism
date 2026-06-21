import { describe, it, expect, beforeEach } from "vitest";

describe("normalizeError", () => {
  beforeEach(() => localStorage.clear());
  it("extracts detail.message", async () => {
    const { normalizeError } = await import("./client");
    expect(normalizeError({ response: { data: { detail: { message: "boom" } } } }).message).toBe("boom");
  });
  it("falls back to string detail", async () => {
    const { normalizeError } = await import("./client");
    expect(normalizeError({ response: { data: { detail: "nope" } } }).message).toBe("nope");
  });
});
