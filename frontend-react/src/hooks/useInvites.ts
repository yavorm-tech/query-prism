import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { qk } from "../lib/queryKeys";
import { getInvites, createInvite } from "../lib/api/auth";

export function useInvites() {
  return useQuery({ queryKey: qk.invites, queryFn: getInvites });
}

export function useCreateInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createInvite,
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.invites }),
  });
}
