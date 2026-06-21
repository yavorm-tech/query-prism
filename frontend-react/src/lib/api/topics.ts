import { api } from "./client";
import type { Topic, QuestionHistoryItem, DocumentItem } from "./types";

export const getTopics = (teamId?: string) =>
  api.get<Topic[]>("/topics", { params: teamId ? { team_id: teamId } : {} }).then((r) => r.data);
export const getTopic = (id: string) => api.get<Topic>(`/topics/${id}`).then((r) => r.data);
export const createTopic = (b: { team_id: string; name: string; description?: string }) =>
  api.post<Topic>("/topics", b).then((r) => r.data);
export const updateTopic = (id: string, b: { name?: string; description?: string }) =>
  api.patch<Topic>(`/topics/${id}`, b).then((r) => r.data);
export const deleteTopic = (id: string) => api.delete(`/topics/${id}`).then(() => {});
export const getTopicQuestions = (id: string) =>
  api.get<QuestionHistoryItem[]>(`/topics/${id}/questions`).then((r) => r.data);
export const getTopicDocuments = (id: string) =>
  api.get<DocumentItem[]>(`/topics/${id}/documents`).then((r) => r.data);
