import { useState, useCallback, useRef, useEffect } from "react";
import { streamChat } from "../lib/api/stream";
import type { SourceChunk } from "../lib/api/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface UseChatStreamReturn {
  messages: ChatMessage[];
  ask: (query: string) => void;
  streaming: boolean;
  sources: SourceChunk[];
  limitReached: boolean;
  error: string | null;
  reset: () => void;
}

function appendToken(messages: ChatMessage[], token: string): ChatMessage[] {
  if (!messages.length) return messages;
  const last = messages[messages.length - 1];
  if (last.role !== "assistant") return messages;
  return [
    ...messages.slice(0, -1),
    { ...last, content: last.content + token },
  ];
}

export function useChatStream(
  topicId: string,
  teamId?: string | null
): UseChatStreamReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [sources, setSources] = useState<SourceChunk[]>([]);
  const [limitReached, setLimitReached] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<(() => void) | null>(null);

  // Abort any in-flight stream on unmount to avoid setState-after-unmount
  useEffect(() => () => { abortRef.current?.(); }, []);

  const reset = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    setMessages([]);
    setStreaming(false);
    setSources([]);
    setLimitReached(false);
    setError(null);
  }, []);

  const ask = useCallback(
    (query: string) => {
      if (streaming) return;

      const now = Date.now();
      const userMsg: ChatMessage = {
        id: `user-${now}`,
        role: "user",
        content: query,
      };
      const assistantMsg: ChatMessage = {
        id: `assistant-${now + 1}`,
        role: "assistant",
        content: "",
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setSources([]);
      setStreaming(true);
      setLimitReached(false);
      setError(null);

      const stop = streamChat(
        {
          query,
          topic_id: topicId,
          team_id: teamId ?? undefined,
        },
        {
          onToken: (t) => setMessages((m) => appendToken(m, t)),
          onSources: (s) => setSources(s),
          onDone: () => {
            setStreaming(false);
            abortRef.current = null;
          },
          onError: (msg) => {
            setStreaming(false);
            abortRef.current = null;
            setError(msg ?? "An error occurred while streaming.");
          },
          onLimit: () => {
            setStreaming(false);
            setLimitReached(true);
            abortRef.current = null;
          },
        }
      );

      abortRef.current = stop;
    },
    [streaming, topicId, teamId]
  );

  return { messages, ask, streaming, sources, limitReached, error, reset };
}
