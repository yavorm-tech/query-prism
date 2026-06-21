import { FileText, Image, Video, File } from "lucide-react";
import type { SourceChunk } from "../../lib/api/types";

const typeIcon = (type: string) => {
  if (type === "pdf" || type === "docx" || type === "txt") return FileText;
  if (type === "image") return Image;
  if (type === "video") return Video;
  return File;
};

interface SourcesProps {
  sources: SourceChunk[];
}

export default function Sources({ sources }: SourcesProps) {
  if (!sources.length) return null;

  return (
    <div className="mt-3 space-y-1.5 animate-fade-in">
      <p className="text-xs text-muted font-medium uppercase tracking-wide">Sources</p>
      <div className="flex flex-wrap gap-2">
        {sources.map((s) => {
          const Icon = typeIcon(s.source_type);
          const score = s.rerank_score ?? s.similarity;
          return (
            <div
              key={s.chunk_id}
              title={s.content_preview}
              className="flex items-center gap-1.5 bg-surface border border-border rounded-lg px-2.5 py-1.5 text-xs text-text-dim hover:border-muted transition-colors cursor-default"
            >
              <Icon size={11} className="text-muted shrink-0" />
              <span className="max-w-[140px] truncate">{s.original_name || s.filename}</span>
              {score != null && (
                <span className="text-muted ml-0.5">{Math.round(score * 100)}%</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
