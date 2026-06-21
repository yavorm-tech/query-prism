import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { qk } from "../lib/queryKeys";
import {
  getTeams,
  createTeam,
  getTeamMembers,
  addTeamMember,
  removeTeamMember,
} from "../lib/api/auth";

export function useTeams() {
  return useQuery({ queryKey: qk.teams, queryFn: getTeams });
}

export function useTeamMembers(teamId: string) {
  return useQuery({
    queryKey: qk.members(teamId),
    queryFn: () => getTeamMembers(teamId),
    enabled: !!teamId,
  });
}

export function useCreateTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTeam,
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.teams }),
  });
}

export function useAddMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ teamId, userId, role }: { teamId: string; userId: string; role?: string }) =>
      addTeamMember(teamId, userId, role),
    onSuccess: (_data, { teamId }) => {
      qc.invalidateQueries({ queryKey: qk.members(teamId) });
      qc.invalidateQueries({ queryKey: qk.teams });
    },
  });
}

export function useRemoveMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ teamId, userId }: { teamId: string; userId: string }) =>
      removeTeamMember(teamId, userId),
    onSuccess: (_data, { teamId }) => {
      qc.invalidateQueries({ queryKey: qk.members(teamId) });
      qc.invalidateQueries({ queryKey: qk.teams });
    },
  });
}
