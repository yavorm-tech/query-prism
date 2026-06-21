import { api } from "./client";
import type { User, Team, TeamMember, Invite, InviteListItem, AuditLogItem } from "./types";

export const register = (b: { company_name: string; username: string; email: string; password: string }) =>
  api.post<{ access_token: string }>("/auth/register", b).then((r) => r.data);
export const login = (b: { email: string; password: string }) =>
  api.post<{ access_token: string }>("/auth/login", b).then((r) => r.data);
export const getMe = () => api.get<User>("/auth/me").then((r) => r.data);
export const forgotPassword = (email: string) => api.post("/auth/forgot-password", { email }).then(() => {});
export const resetPassword = (b: { token: string; new_password: string }) =>
  api.post("/auth/reset-password", b).then(() => {});
export const getInvitePreview = (token: string) =>
  api.get<{ company_name: string; team_name: string; email: string }>(`/auth/invite/${token}`).then((r) => r.data);
export const acceptInvite = (token: string, b: { username: string; password: string }) =>
  api.post<{ access_token: string }>(`/auth/invite/${token}/accept`, b).then((r) => r.data);
export const getInvites = () => api.get<InviteListItem[]>("/auth/invites").then((r) => r.data);
export const createInvite = (b: { email: string; team_id: string; role?: string }) =>
  api.post<Invite>("/auth/invite", b).then((r) => r.data);
export const getTeams = () => api.get<Team[]>("/auth/teams").then((r) => r.data);
export const createTeam = (b: { name: string; description?: string }) =>
  api.post<Team>("/auth/teams", b).then((r) => r.data);
export const getTeamMembers = (teamId: string) =>
  api.get<TeamMember[]>(`/auth/teams/${teamId}/members`).then((r) => r.data);
export const addTeamMember = (teamId: string, userId: string, role = "member") =>
  api.post(`/auth/teams/${teamId}/members`, null, { params: { user_id: userId, role } }).then(() => {});
export const removeTeamMember = (teamId: string, userId: string) =>
  api.delete(`/auth/teams/${teamId}/members/${userId}`).then(() => {});
export const completeOAuth = (b: { pending_token: string; company_name: string; username: string }) =>
  api.post<{ access_token: string }>("/auth/oauth/complete", b).then((r) => r.data);
export const getAuditLog = (params: { team_id?: string; event_type?: string; limit?: number; offset?: number }) =>
  api.get<AuditLogItem[]>("/audit", { params }).then((r) => r.data);
export const uploadAvatar = (avatar: string) =>
  api.put("/auth/me/avatar", { avatar }).then(() => {});
export const deleteAvatar = () =>
  api.delete("/auth/me/avatar").then(() => {});
