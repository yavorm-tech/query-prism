import { useState, useCallback } from "react";
import { Button } from "flowbite-react";
import { Upload, Trash2 } from "lucide-react";
import { useDocuments, useDeleteDocument, ACTIVE_STATUSES } from "../../hooks/useDocuments";
import DocumentsTable from "./DocumentsTable";
import UploadModal from "./UploadModal";
import type { DocumentItem } from "../../lib/api/types";

interface Props {
  topicId: string;
}

const DONE = new Set(["processed", "completed", "ready"]);

export default function DocumentsTab({ topicId }: Props) {
  const { data: docs = [], isLoading, isError } = useDocuments(topicId);
  const deleteMutation = useDeleteDocument(topicId);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const total = docs.length;
  const processed = docs.filter((d: DocumentItem) => DONE.has(d.status)).length;
  const processing = docs.filter((d: DocumentItem) => ACTIVE_STATUSES.has(d.status)).length;

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const handleDeleteSelected = useCallback(async () => {
    if (selectedIds.size === 0) return;
    const confirmed = window.confirm(
      `Delete ${selectedIds.size} document${selectedIds.size > 1 ? "s" : ""}? This cannot be undone.`
    );
    if (!confirmed) return;
    await Promise.all([...selectedIds].map((id) => deleteMutation.mutateAsync(id)));
    setSelectedIds(new Set());
  }, [selectedIds, deleteMutation]);

  const handleDeleteRow = useCallback(async (id: string) => {
    const doc = docs.find((d: DocumentItem) => d.document_id === id);
    const confirmed = window.confirm(
      `Delete "${doc?.original_name ?? "this document"}"? This cannot be undone.`
    );
    if (!confirmed) return;
    await deleteMutation.mutateAsync(id);
    setSelectedIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
  }, [docs, deleteMutation]);

  return (
    <div className="py-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {selectedIds.size > 0 && (
            <Button
              size="sm"
              color="failure"
              onClick={handleDeleteSelected}
              isProcessing={deleteMutation.isPending}
              disabled={deleteMutation.isPending}
            >
              <Trash2 size={14} className="mr-1" />
              Delete ({selectedIds.size})
            </Button>
          )}
          <Button size="sm" onClick={() => setUploadOpen(true)}>
            <Upload className="h-4 w-4 mr-1" />
            Upload
          </Button>
        </div>
        <p className="text-sm text-muted">
          Total: <span className="font-semibold text-foreground">{total}</span>
          {" · "}Processed: <span className="font-semibold text-foreground">{processed}</span>
          {" · "}Processing: <span className="font-semibold text-foreground">{processing}</span>
        </p>
      </div>

      {isLoading && (
        <p className="text-sm text-muted py-8 text-center">Loading documents…</p>
      )}
      {isError && (
        <p className="text-sm text-red-400 py-8 text-center">Failed to load documents.</p>
      )}
      {!isLoading && !isError && (
        <DocumentsTable
          docs={docs}
          selectedIds={selectedIds}
          onToggleSelect={handleToggleSelect}
          onDeleteRow={handleDeleteRow}
        />
      )}

      <UploadModal
        topicId={topicId}
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
      />
    </div>
  );
}
