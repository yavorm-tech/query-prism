import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { qk } from "../lib/queryKeys";
import { listDocuments, uploadDocument, deleteDocument } from "../lib/api/ingest";

export const ACTIVE_STATUSES = new Set(["pending", "processing"]);

export function useDocuments(topicId: string) {
  return useQuery({
    queryKey: qk.documents(topicId),
    queryFn: () => listDocuments({ topic_id: topicId }),
    refetchInterval: (q) => (q.state.data?.some((d: any) => ACTIVE_STATUSES.has(d.status)) ? 4000 : false),
  });
}

export function useUploadDocument(topicId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { file: File; team_id?: string }) =>
      uploadDocument(v.file, { topic_id: topicId, team_id: v.team_id, visibility: "team" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.documents(topicId) }),
  });
}

export function useDeleteDocument(topicId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.documents(topicId) }),
  });
}
