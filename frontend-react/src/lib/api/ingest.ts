import { api } from "./client";
import type { DocumentItem } from "./types";

export const listDocuments = (params: { team_id?: string; topic_id?: string }) =>
  api.get<DocumentItem[]>("/ingest", { params }).then((r) => r.data);
export const getDocumentStatus = (id: string) =>
  api.get<{ document_id: string; status: string; team_id: string; topic_id: string; error_message?: string }>(`/ingest/${id}`).then((r) => r.data);
export const deleteDocument = (id: string) => api.delete(`/ingest/${id}`).then(() => {});
export const uploadDocument = (file: File, params: { team_id?: string; topic_id?: string; visibility?: string }) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post("/ingest", fd, { params, headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
};
