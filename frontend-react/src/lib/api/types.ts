export interface User {
  id: string
  username: string
  email: string
  company_id: string
  company_name: string | null
  plan: string
  role: 'member' | 'admin' | 'owner'
  team_ids: string[]
  default_team_id: string | null
  avatar: string | null
}

export interface Team {
  id: string
  name: string
  description: string | null
  company_id: string
  member_count: number | null
}

export interface TeamMember {
  id: string
  username: string
  email: string
  company_role: string
  team_role: string
}

export interface Invite {
  id: string
  token: string
  email: string
  expires_at: string
}

export interface InviteListItem {
  id: string
  email: string
  role: string
  team_name: string
  invited_by_username: string
  status: 'pending' | 'accepted' | 'expired'
  created_at: string
  expires_at: string
  accepted_at: string | null
}

export interface QuestionHistoryItem {
  id: string
  question: string
  answer: string | null
  username: string | null
  asked_at: string
}

export interface InvitePreview {
  company_name: string
  team_name: string
  email: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface IngestResponse {
  document_id: string
  job_id: string
  filename: string
  status: string
  team_id: string
}

export interface IngestStatus {
  document_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  team_id: string
  error_message?: string
}

export interface DocumentItem {
  document_id: string
  original_name: string
  source_type: string
  file_size: number | null
  status: string
  team_id: string
  team_name: string | null
  uploaded_by_username: string | null
  visibility: string
  created_at: string
}

export interface SourceChunk {
  chunk_id: string
  document_id: string
  filename: string
  original_name: string
  source_type: string
  team_id: string | null
  content_preview: string
  similarity: number | null
  rerank_score: number | null
}

export interface StreamEvent {
  type: 'token' | 'sources' | 'done' | 'error'
  content?: string | SourceChunk[]
  cached?: boolean
}

export interface LimitError {
  error: string
  message: string
  plan?: string
  used?: number
  limit?: number
  upgrade_url?: string
}

export interface ChatResponse {
  answer: string;
  sources: SourceChunk[];
  query: string;
  cached: boolean;
  scope?: string;
}

export interface UsageData {
  plan: string
  price_monthly: number
  queries: { used: number; limit: number | null; resets_at: string | null; percent: number }
  storage: { used_bytes: number; used_mb: number; limit_mb: number | null; percent: number }
  teams: { used: number; limit: number | null }
  users: { used: number; limit: number | null }
}

export interface Topic {
  id: string
  name: string
  description: string | null
  team_id: string
  team_name: string | null
  created_by_username: string | null
  document_count: number
  completed_count: number
  created_at: string
}

export interface TopicDocument {
  document_id: string
  original_name: string
  source_type: string
  file_size: number | null
  status: string
  uploaded_by_username: string | null
  created_at: string
}

export interface AuditLogItem {
  id: string
  event_type: string
  actor_username: string | null
  actor_email: string | null
  team_id: string | null
  team_name: string | null
  resource_type: string | null
  resource_id: string | null
  resource_name: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}
