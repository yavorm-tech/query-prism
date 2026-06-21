import { api } from "./client";
import type { UsageData } from "./types";

export const getUsage = () => api.get<UsageData>("/usage").then((r) => r.data);
