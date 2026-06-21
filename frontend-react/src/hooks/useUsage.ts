import { useQuery } from "@tanstack/react-query";
import { qk } from "../lib/queryKeys";
import { getUsage } from "../lib/api/billing";

export function useUsage() {
  return useQuery({ queryKey: qk.usage, queryFn: getUsage });
}
