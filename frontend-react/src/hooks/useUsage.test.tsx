import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";
import { useUsage } from "./useUsage";

vi.mock("../lib/api/billing", () => ({
  getUsage: vi.fn(),
}));

import { getUsage } from "../lib/api/billing";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useUsage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns usage data from getUsage", async () => {
    const mockUsage = {
      plan: "pro",
      price_monthly: 49,
      queries: { used: 100, limit: 1000, resets_at: "2026-07-01T00:00:00Z", percent: 10 },
      storage: { used_bytes: 1048576, used_mb: 1, limit_mb: 1000, percent: 0.1 },
      teams: { used: 2, limit: 5 },
      users: { used: 5, limit: 20 },
    };
    vi.mocked(getUsage).mockResolvedValue(mockUsage);

    const { result } = renderHook(() => useUsage(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockUsage);
    expect(getUsage).toHaveBeenCalledTimes(1);
  });

  it("handles error state", async () => {
    vi.mocked(getUsage).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useUsage(), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });
});
