import axios from "axios";
import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, normalizeError, refreshAccessToken } from "./client";
import { getToken, setToken } from "../token";

function respond(config: InternalAxiosRequestConfig, status: number, data: unknown = {}) {
  const response = { data, status, statusText: String(status), headers: {}, config };
  if (status >= 400) {
    return Promise.reject(Object.assign(new Error(`HTTP ${status}`), { config, response, isAxiosError: true }));
  }
  return Promise.resolve(response);
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("api client session refresh", () => {
  it("refreshes once on 401 and retries with the new token", async () => {
    setToken("expired");
    const seen: string[] = [];
    const adapter: AxiosAdapter = (config) => {
      const auth = String(config.headers?.Authorization);
      seen.push(auth);
      return auth === "Bearer fresh" ? respond(config, 200, { ok: true }) : respond(config, 401);
    };
    const post = vi.spyOn(axios, "post").mockResolvedValue({ data: { access_token: "fresh" } });

    const r = await api.get("/auth/me", { adapter });

    expect(r.data).toEqual({ ok: true });
    expect(seen).toEqual(["Bearer expired", "Bearer fresh"]);
    expect(post).toHaveBeenCalledTimes(1);
    expect(getToken()).toBe("fresh");
  });

  it("shares one refresh between concurrent callers", async () => {
    const post = vi.spyOn(axios, "post").mockResolvedValue({ data: { access_token: "t" } });
    const [a, b] = await Promise.all([refreshAccessToken(), refreshAccessToken()]);
    expect(a).toBe("t");
    expect(b).toBe("t");
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("does not try to refresh when login itself returns 401", async () => {
    const post = vi.spyOn(axios, "post");
    const adapter: AxiosAdapter = (config) => respond(config, 401, { detail: "Incorrect email or password" });
    await expect(api.post("/auth/login", {}, { adapter })).rejects.toThrow("Incorrect email or password");
    expect(post).not.toHaveBeenCalled();
  });

  it("clears the token when there is no session", async () => {
    setToken("old");
    vi.spyOn(axios, "post").mockRejectedValue(new Error("401"));
    expect(await refreshAccessToken()).toBeNull();
    expect(getToken()).toBeNull();
  });
});

describe("normalizeError", () => {
  it("extracts detail.message", () => {
    expect(normalizeError({ response: { data: { detail: { message: "boom" } } } }).message).toBe("boom");
  });
  it("falls back to string detail", () => {
    expect(normalizeError({ response: { data: { detail: "nope" } } }).message).toBe("nope");
  });
});
