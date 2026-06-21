import { Button } from "flowbite-react";
import { Plus, Trash2 } from "lucide-react";

interface Props {
  total: number;
  selectedIds: Set<string>;
  onAdd: () => void;
  onDelete: () => void;
  isDeleting: boolean;
}

export default function TopicToolbar({ total, selectedIds, onAdd, onDelete, isDeleting }: Props) {
  const hasSelection = selectedIds.size > 0;

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={onAdd}>
          <Plus size={14} className="mr-1" />
          New topic
        </Button>
        {hasSelection && (
          <Button
            size="sm"
            color="failure"
            onClick={onDelete}
            isProcessing={isDeleting}
            disabled={isDeleting}
          >
            <Trash2 size={14} className="mr-1" />
            Delete ({selectedIds.size})
          </Button>
        )}
      </div>
      <span className="text-sm text-text-dim">
        {total} topic{total !== 1 ? "s" : ""}
      </span>
    </div>
  );
}
