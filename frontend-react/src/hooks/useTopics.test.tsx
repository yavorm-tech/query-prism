import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";
import { useTopics } from "./useTopics";

vi.mock("../lib/api/topics", () => ({
  getTopics: vi.fn(),
  createTopic: vi.fn(),
  deleteTopic: vi.fn(),
}));

import { getTopics } from "../lib/api/topics";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useTopics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns topics data from getTopics", async () => {
    const mockTopics = [
      {
        id: "1",
        name: "T",
        description: null,
        team_id: "t1",
        team_name: null,
        created_by_username: null,
        document_count: 0,
        completed_count: 0,
        created_at: "2024-01-01T00:00:00Z",
      },
    ];
    vi.mocked(getTopics).mockResolvedValue(mockTopics);

    const { result } = renderHook(() => useTopics(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockTopics);
    expect(getTopics).toHaveBeenCalledWith(undefined);
  });

  it("passes teamId to getTopics", async () => {
    vi.mocked(getTopics).mockResolvedValue([]);

    const { result } = renderHook(() => useTopics("team-123"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(getTopics).toHaveBeenCalledWith("team-123");
  });
});
