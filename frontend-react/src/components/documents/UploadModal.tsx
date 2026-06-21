import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Modal, Button, Label } from "flowbite-react";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import { useUploadDocument } from "../../hooks/useDocuments";
import { useAuth } from "../../lib/auth-context";
import { qk } from "../../lib/queryKeys";

interface Props {
  topicId: string;
  open: boolean;
  onClose: () => void;
}

interface FileResult {
  name: string;
  state: "pending" | "uploading" | "done" | "error";
  error?: string;
}

export default function UploadModal({ topicId, open, onClose }: Props) {
  const { activeTeamId } = useAuth();
  const queryClient = useQueryClient();
  const uploadMutation = useUploadDocument(topicId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [results, setResults] = useState<FileResult[]>([]);
  const [submitting, setSubmitting] = useState(false);

  function handleClose() {
    setResults([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
    queryClient.invalidateQueries({ queryKey: qk.documents(topicId) });
    onClose();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const files = fileInputRef.current?.files;
    if (!files || files.length === 0) return;

    const fileList = Array.from(files);
    setResults(fileList.map((f) => ({ name: f.name, state: "pending" })));
    setSubmitting(true);

    let hasErrors = false;
    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      setResults((prev) =>
        prev.map((r, idx) => (idx === i ? { ...r, state: "uploading" } : r))
      );
      try {
        await uploadMutation.mutateAsync({
          file,
          team_id: activeTeamId ?? undefined,
        });
        setResults((prev) =>
          prev.map((r, idx) => (idx === i ? { ...r, state: "done" } : r))
        );
      } catch (err) {
        hasErrors = true;
        const msg = err instanceof Error ? err.message : "Upload failed";
        setResults((prev) =>
          prev.map((r, idx) => (idx === i ? { ...r, state: "error", error: msg } : r))
        );
      }
    }

    setSubmitting(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (!hasErrors) setTimeout(handleClose, 800);
  }

  return (
    <Modal show={open} onClose={handleClose} size="md">
      <Modal.Header>Upload Documents</Modal.Header>
      <Modal.Body>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <Label htmlFor="file-upload" value="Select files" className="mb-2 block" />
            <input
              id="file-upload"
              type="file"
              multiple
              ref={fileInputRef}
              className="block w-full text-sm text-muted file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-accent file:text-white hover:file:bg-accent/80"
              disabled={submitting}
            />
          </div>

          {results.length > 0 && (
            <ul className="flex flex-col gap-2 max-h-48 overflow-y-auto">
              {results.map((r, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  {r.state === "uploading" && (
                    <Loader2 className="h-4 w-4 animate-spin text-amber-400 shrink-0" />
                  )}
                  {r.state === "done" && (
                    <CheckCircle className="h-4 w-4 text-green-400 shrink-0" />
                  )}
                  {r.state === "error" && (
                    <XCircle className="h-4 w-4 text-red-400 shrink-0" />
                  )}
                  {r.state === "pending" && (
                    <span className="h-4 w-4 shrink-0" />
                  )}
                  <span className="truncate">{r.name}</span>
                  {r.error && (
                    <span className="text-red-400 text-xs ml-1">{r.error}</span>
                  )}
                </li>
              ))}
            </ul>
          )}

          <div className="flex justify-end gap-2">
            <Button color="gray" onClick={handleClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Uploading…" : "Upload"}
            </Button>
          </div>
        </form>
      </Modal.Body>
    </Modal>
  );
}
