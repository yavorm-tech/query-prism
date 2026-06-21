import { useQuery } from "@tanstack/react-query";
import { qk } from "../lib/queryKeys";
import { getAuditLog } from "../lib/api/auth";

interface AuditLogParams {
  team_id?: string;
  event_type?: string;
  limit?: number;
  offset?: number;
}

export function useAuditLog(params: AuditLogParams = {}) {
  return useQuery({
    queryKey: qk.audit(params),
    queryFn: () => getAuditLog(params),
  });
}
