import { useMemo } from "react";
import { Trash2 } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import DataTable from "../common/DataTable";
import StatusIndicator from "../common/StatusIndicator";
import type { DocumentItem } from "../../lib/api/types";

interface Props {
  docs: DocumentItem[];
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onDeleteRow: (id: string) => void;
}

export default function DocumentsTable({ docs, selectedIds, onToggleSelect, onDeleteRow }: Props) {
  const columns = useMemo<ColumnDef<DocumentItem>[]>(
    () => [
      {
        id: "select",
        header: "",
        cell: ({ row }) => (
          <input
            type="checkbox"
            className="rounded border-border text-accent focus:ring-accent"
            checked={selectedIds.has(row.original.document_id)}
            onChange={() => onToggleSelect(row.original.document_id)}
            aria-label={`Select ${row.original.original_name}`}
          />
        ),
      },
      {
        accessorKey: "original_name",
        header: "Filename",
        cell: (info) => (
          <span className="font-medium text-sm">{info.getValue<string>()}</span>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: (info) => <StatusIndicator status={info.getValue<string>()} />,
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <button
            aria-label={`Remove ${row.original.original_name}`}
            title="Remove document"
            className="text-muted hover:text-red-400 transition-colors"
            onClick={() => onDeleteRow(row.original.document_id)}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        ),
      },
    ],
    [selectedIds, onToggleSelect, onDeleteRow]
  );

  return <DataTable<DocumentItem> data={docs} columns={columns} pageSize={10} />;
}
