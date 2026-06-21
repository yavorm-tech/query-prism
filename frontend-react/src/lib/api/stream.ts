import { getToken } from "../token";
import type { SourceChunk, LimitError } from "./types";

export interface StreamHandlers {
  onToken: (t: string) => void;
  onSources: (s: SourceChunk[]) => void;
  onDone: (cached: boolean) => void;
  onError: (msg: string) => void;
  onLimit?: (detail?: LimitError) => void;
}
export interface StreamParams {
  query: string; team_id?: string; topic_id?: string; source_type?: string; skip_cache?: boolean;
}

export function streamChat(p: StreamParams, h: StreamHandlers): () => void {
  const ctrl = new AbortController();
  const base = import.meta.env.VITE_API_URL || "http://localhost:8000";
  const qs = new URLSearchParams({ query: p.query });
  if (p.team_id) qs.set("team_id", p.team_id);
  if (p.topic_id) qs.set("topic_id", p.topic_id);
  if (p.source_type) qs.set("source_type", p.source_type);
  if (p.skip_cache) qs.set("skip_cache", "true");

  (async () => {
    try {
      const res = await fetch(`${base}/chat/stream?${qs}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
        signal: ctrl.signal,
      });
      if (res.status === 429 || res.status === 413) {
        const body = await res.json().catch(() => null);
        h.onLimit?.(body?.detail ?? undefined);
        return;
      }
      if (!res.ok) { h.onError(`HTTP ${res.status}`); return; }
      if (!res.body) { h.onError("No stream body"); return; }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const part of parts) {
          const line = part.replace(/^data: ?/, "").trim();
          if (!line) continue;
          const evt = JSON.parse(line);
          if (evt.type === "token") h.onToken(evt.content);
          else if (evt.type === "sources") h.onSources(evt.content);
          else if (evt.type === "done") h.onDone(!!evt.cached);
          else if (evt.type === "error") h.onError(evt.content || "Stream error");
        }
      }
    } catch (e: any) {
      if (e.name !== "AbortError") h.onError(e.message || "Stream failed");
    }
  })();

  return () => ctrl.abort();
}
