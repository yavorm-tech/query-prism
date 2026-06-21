import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";
import { useQuestions } from "./useQuestions";

vi.mock("../lib/api/topics", () => ({
  getTopicQuestions: vi.fn(),
}));

import { getTopicQuestions } from "../lib/api/topics";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useQuestions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns question history from getTopicQuestions", async () => {
    const mockQuestions = [
      {
        id: "q1",
        question: "What is the policy?",
        answer: "The policy is X.",
        username: "alice",
        asked_at: "2024-03-01T10:00:00Z",
      },
    ];
    vi.mocked(getTopicQuestions).mockResolvedValue(mockQuestions);

    const { result } = renderHook(() => useQuestions("topic-123"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockQuestions);
    expect(getTopicQuestions).toHaveBeenCalledWith("topic-123");
  });

  it("handles empty question list", async () => {
    vi.mocked(getTopicQuestions).mockResolvedValue([]);

    const { result } = renderHook(() => useQuestions("topic-456"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
    expect(getTopicQuestions).toHaveBeenCalledWith("topic-456");
  });
});
