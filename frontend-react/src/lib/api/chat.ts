import { api } from "./client";
import type { ChatResponse } from "./types";

export const postChat = (b: { query: string; team_id?: string; source_type?: string; skip_cache?: boolean }) =>
  api.post<ChatResponse>("/chat", b).then((r) => r.data);
