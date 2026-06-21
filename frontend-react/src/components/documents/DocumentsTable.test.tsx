import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";
import DocumentsTable from "./DocumentsTable";
import type { DocumentItem } from "../../lib/api/types";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const docs: DocumentItem[] = [
  {
    document_id: "doc-1",
    original_name: "report.pdf",
    source_type: "upload",
    file_size: 1024,
    status: "processed",
    team_id: "team-1",
    team_name: "Alpha",
    uploaded_by_username: "alice",
    visibility: "team",
    created_at: "2024-01-01T00:00:00Z",
  },
  {
    document_id: "doc-2",
    original_name: "notes.docx",
    source_type: "upload",
    file_size: 512,
    status: "processing",
    team_id: "team-1",
    team_name: "Alpha",
    uploaded_by_username: "bob",
    visibility: "team",
    created_at: "2024-01-02T00:00:00Z",
  },
];

const noop = () => {};

describe("DocumentsTable", () => {
  const onDeleteRow = vi.fn();

  beforeEach(() => {
    onDeleteRow.mockClear();
  });

  it("renders both document filenames", () => {
    render(
      <DocumentsTable docs={docs} selectedIds={new Set()} onToggleSelect={noop} onDeleteRow={onDeleteRow} />,
      { wrapper }
    );
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
    expect(screen.getByText("notes.docx")).toBeInTheDocument();
  });

  it("renders a remove control per row", () => {
    render(
      <DocumentsTable docs={docs} selectedIds={new Set()} onToggleSelect={noop} onDeleteRow={onDeleteRow} />,
      { wrapper }
    );
    const removeButtons = screen.getAllByRole("button", { name: /remove|delete/i });
    expect(removeButtons).toHaveLength(2);
  });

  it("calls onDeleteRow when remove button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <DocumentsTable docs={docs} selectedIds={new Set()} onToggleSelect={noop} onDeleteRow={onDeleteRow} />,
      { wrapper }
    );
    const removeButtons = screen.getAllByRole("button", { name: /remove|delete/i });
    await user.click(removeButtons[0]);
    expect(onDeleteRow).toHaveBeenCalledWith("doc-1");
  });

  it("renders status indicators for each row", () => {
    render(
      <DocumentsTable docs={docs} selectedIds={new Set()} onToggleSelect={noop} onDeleteRow={onDeleteRow} />,
      { wrapper }
    );
    expect(screen.getByText("processed")).toBeInTheDocument();
    expect(screen.getByText("processing")).toBeInTheDocument();
  });
});
