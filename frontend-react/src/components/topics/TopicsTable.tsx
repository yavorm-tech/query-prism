import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Folder, Trash2, Pencil } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import DataTable from "../common/DataTable";
import type { Topic } from "../../lib/api/types";

interface Props {
  topics: Topic[];
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onDeleteRow: (id: string) => void;
  onEditRow: (topic: Topic) => void;
  toolbar: React.ReactNode;
}

export default function TopicsTable({
  topics,
  selectedIds,
  onToggleSelect,
  onDeleteRow,
  onEditRow,
  toolbar,
}: Props) {
  const columns = useMemo<ColumnDef<Topic>[]>(
    () => [
      {
        id: "select",
        header: "",
        cell: ({ row }) => (
          <input
            type="checkbox"
            className="rounded border-border text-accent focus:ring-accent"
            checked={selectedIds.has(row.original.id)}
            onChange={() => onToggleSelect(row.original.id)}
            aria-label={`Select ${row.original.name}`}
          />
        ),
      },
      {
        id: "name",
        header: "Topic",
        cell: ({ row }) => (
          <Link
            to={`/topics/${row.original.id}`}
            className="flex items-start gap-2 hover:text-accent transition-colors"
            aria-label={`Open ${row.original.name}`}
          >
            <Folder size={16} className="mt-0.5 shrink-0 text-accent" />
            <div>
              <div className="font-medium text-sm">{row.original.name}</div>
              {row.original.description && (
                <div className="text-xs text-muted mt-0.5">{row.original.description}</div>
              )}
            </div>
          </Link>
        ),
      },
      {
        id: "info",
        header: () => <span className="block text-right">Info</span>,
        cell: ({ row }) => (
          <div className="text-right text-sm text-text-dim">
            <div>{row.original.document_count} docs</div>
            {row.original.created_by_username && (
              <div className="text-xs text-muted">
                owner: {row.original.created_by_username}
              </div>
            )}
          </div>
        ),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <div className="flex items-center justify-end gap-2">
            <button
              aria-label={`Edit ${row.original.name}`}
              title="Edit topic"
              className="text-muted hover:text-accent transition-colors"
              onClick={(e) => { e.preventDefault(); onEditRow(row.original); }}
            >
              <Pencil className="h-4 w-4" />
            </button>
            <button
              aria-label={`Delete ${row.original.name}`}
              title="Delete topic"
              className="text-muted hover:text-red-400 transition-colors"
              onClick={(e) => { e.preventDefault(); onDeleteRow(row.original.id); }}
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ),
      },
    ],
    [selectedIds, onToggleSelect, onDeleteRow, onEditRow]
  );

  return <DataTable data={topics} columns={columns} toolbar={toolbar} />;
}
