import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { qk } from "../lib/queryKeys";
import { getTopics, createTopic, updateTopic, deleteTopic } from "../lib/api/topics";

export function useTopics(teamId?: string) {
  return useQuery({ queryKey: qk.topics(teamId), queryFn: () => getTopics(teamId) });
}

export function useCreateTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTopic,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}

export function useUpdateTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: { name?: string; description?: string } }) =>
      updateTopic(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}

export function useDeleteTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteTopic,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}
