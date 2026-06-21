import { Spinner, Alert } from "flowbite-react";
import { MessageSquare } from "lucide-react";
import { useQuestions } from "../../hooks/useQuestions";
import type { QuestionHistoryItem } from "../../lib/api/types";

interface Props {
  topicId: string;
  topicName: string;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function HistoryTab({ topicId, topicName }: Props) {
  const { data: questions = [], isLoading, isError } = useQuestions(topicId);

  return (
    <div className="py-4">
      <h2 className="text-base font-semibold mb-4">
        Conversation history — {topicName}
      </h2>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner size="md" />
        </div>
      )}

      {isError && (
        <Alert color="failure">Failed to load conversation history.</Alert>
      )}

      {!isLoading && !isError && questions.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-10 text-muted text-sm">
          <MessageSquare className="h-6 w-6 opacity-40" />
          <p>No questions asked yet.</p>
        </div>
      )}

      {!isLoading && !isError && questions.length > 0 && (
        <ul className="flex flex-col gap-4">
          {questions.map((item: QuestionHistoryItem) => (
            <li
              key={item.id}
              className="rounded-lg border border-border bg-surface p-4 flex flex-col gap-2"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="font-medium text-sm text-foreground">{item.question}</p>
                <span className="text-xs text-muted whitespace-nowrap shrink-0">
                  {formatDate(item.asked_at)}
                </span>
              </div>
              {item.answer && (
                <p className="text-sm text-muted leading-relaxed">{item.answer}</p>
              )}
              {item.username && (
                <p className="text-xs text-muted">Asked by {item.username}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
