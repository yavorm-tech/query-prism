import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Sources from "./Sources";
import type { SourceChunk } from "../../lib/api/types";

const makeChunk = (overrides: Partial<SourceChunk> = {}): SourceChunk => ({
  chunk_id: "c1",
  document_id: "d1",
  filename: "doc.pdf",
  original_name: "My Document.pdf",
  source_type: "pdf",
  team_id: "t1",
  content_preview: "Some preview text",
  similarity: 0.85,
  rerank_score: null,
  ...overrides,
});

describe("Sources", () => {
  it("renders chips for each source with label and score", () => {
    const chunks: SourceChunk[] = [
      makeChunk({ chunk_id: "c1", original_name: "Alpha.pdf", rerank_score: 0.92, similarity: 0.8 }),
      makeChunk({ chunk_id: "c2", original_name: "Beta.docx", source_type: "docx", rerank_score: null, similarity: 0.75 }),
    ];
    render(<Sources sources={chunks} />);

    expect(screen.getByText("Alpha.pdf")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();

    expect(screen.getByText("Beta.docx")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("renders nothing when sources array is empty", () => {
    const { container } = render(<Sources sources={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("falls back to filename when original_name is empty", () => {
    const chunk = makeChunk({ original_name: "", filename: "fallback.txt", source_type: "txt" });
    render(<Sources sources={[chunk]} />);
    expect(screen.getByText("fallback.txt")).toBeInTheDocument();
  });

  it("shows rerank_score over similarity when both present", () => {
    const chunk = makeChunk({ rerank_score: 0.9, similarity: 0.6 });
    render(<Sources sources={[chunk]} />);
    // rerank_score wins: 90%, not 60%
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.queryByText("60%")).not.toBeInTheDocument();
  });
});
