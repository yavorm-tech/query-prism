import { Loader2, CheckCircle, XCircle } from "lucide-react";

interface Props {
  status: string;
}

export default function StatusIndicator({ status }: Props) {
  const normalized = status.toLowerCase();

  if (normalized === "pending" || normalized === "processing") {
    return (
      <span className="inline-flex items-center gap-1 text-amber-400">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>{status}</span>
      </span>
    );
  }

  if (
    normalized === "processed" ||
    normalized === "completed" ||
    normalized === "ready"
  ) {
    return (
      <span className="inline-flex items-center gap-1 text-green-400">
        <CheckCircle className="h-4 w-4" />
        <span>{status}</span>
      </span>
    );
  }

  if (normalized === "failed" || normalized === "error") {
    return (
      <span className="inline-flex items-center gap-1 text-red-400">
        <XCircle className="h-4 w-4" />
        <span>{status}</span>
      </span>
    );
  }

  // Unknown status — render plain
  return <span className="text-muted">{status}</span>;
}
