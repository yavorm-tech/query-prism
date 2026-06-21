import { useState, useRef, useEffect, type FormEvent, type ReactNode } from "react";
import { Modal, Button } from "flowbite-react";
import { Send } from "lucide-react";
import { useChatStream } from "../../hooks/useChatStream";
import Sources from "./Sources";

interface ChatPanelProps {
  topicId: string;
  topicName: string;
  teamId?: string | null;
}

function formatInline(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>
    return part
  })
}

function FormattedText({ text }: { text: string }) {
  if (!text) return null
  const lines = text.split('\n')
  const elements: ReactNode[] = []
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (line.startsWith('### ')) elements.push(<h3 key={i}>{line.slice(4)}</h3>)
    else if (line.startsWith('## ')) elements.push(<h2 key={i}>{line.slice(3)}</h2>)
    else if (line.startsWith('# ')) elements.push(<h1 key={i}>{line.slice(2)}</h1>)
    else if (line.startsWith('- ') || line.startsWith('* ')) elements.push(<li key={i}>{formatInline(line.slice(2))}</li>)
    else if (line.trim() === '') elements.push(<br key={i} />)
    else elements.push(<p key={i}>{formatInline(line)}</p>)
  }
  return <>{elements}</>
}

export default function ChatPanel({ topicId, topicName, teamId }: ChatPanelProps) {
  const { messages, ask, streaming, sources, limitReached, error, reset } =
    useChatStream(topicId, teamId);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || streaming) return;
    setInput("");
    ask(q);
  }

  const lastAssistantIdx = messages
    .map((m, i) => (m.role === "assistant" ? i : -1))
    .filter((i) => i !== -1)
    .pop();

  return (
    <div className="flex flex-col h-full min-h-0">
      <h2 className="text-sm font-semibold text-muted mb-4 px-1">
        Ask a question in <span className="text-foreground">{topicName}</span>
      </h2>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.map((msg, idx) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={
                msg.role === "user"
                  ? "bg-accent text-white rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[80%] text-sm"
                  : "bg-panel border border-border rounded-2xl rounded-tl-sm px-4 py-2.5 max-w-[85%] text-sm"
              }
            >
              {msg.role === "assistant" ? (
                <>
                  <div className="prose">
                    <FormattedText text={msg.content || ""} />
                    {streaming && idx === messages.length - 1 && (
                      <span className="inline-block w-2 h-4 bg-accent ml-0.5 animate-pulse align-middle" />
                    )}
                  </div>
                </>
              ) : (
                <span>{msg.content}</span>
              )}
            </div>
            {/* Sources rendered outside the bubble, below the last assistant answer */}
            {msg.role === "assistant" && !streaming && idx === lastAssistantIdx && sources.length > 0 && (
              <div className="w-full">
                <Sources sources={sources} />
              </div>
            )}
          </div>
        ))}
        {messages.length === 0 && (
          <p className="text-center text-muted text-sm py-12">
            Ask a question to get started.
          </p>
        )}
        {error && (
          <p className="text-center text-red-500 text-sm py-2">{error}</p>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="flex gap-2 pt-3 border-t border-border"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          disabled={streaming}
          className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50"
        />
        <Button
          type="submit"
          disabled={!input.trim() || streaming}
          size="sm"
          color="blue"
        >
          <Send size={14} />
        </Button>
      </form>

      {/* Limit modal */}
      <Modal show={limitReached} onClose={reset} size="sm">
        <Modal.Header>Usage limit reached</Modal.Header>
        <Modal.Body>
          <p className="text-sm text-muted">
            You've reached your query limit. Upgrade your plan to continue asking
            questions.
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button color="blue" onClick={reset}>
            Dismiss
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}
