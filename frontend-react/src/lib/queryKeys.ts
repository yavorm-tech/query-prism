export const qk = {
  me: ["me"] as const,
  teams: ["teams"] as const,
  topics: (teamId?: string) => ["topics", teamId ?? "all"] as const,
  topic: (id: string) => ["topic", id] as const,
  documents: (topicId: string) => ["documents", topicId] as const,
  questions: (topicId: string) => ["questions", topicId] as const,
  usage: ["usage"] as const,
  invites: ["invites"] as const,
  members: (teamId: string) => ["members", teamId] as const,
  audit: (params: object) => ["audit", params] as const,
};
