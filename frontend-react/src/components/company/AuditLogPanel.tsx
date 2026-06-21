import { Alert } from "flowbite-react";
import type { ColumnDef } from "@tanstack/react-table";
import DataTable from "../common/DataTable";
import { useAuditLog } from "../../hooks/useAuditLog";
import type { AuditLogItem } from "../../lib/api/types";

const columns: ColumnDef<AuditLogItem>[] = [
  {
    accessorKey: "created_at",
    header: "Timestamp",
    cell: ({ getValue }) => {
      const val = getValue<string>();
      try {
        return new Date(val).toLocaleString();
      } catch {
        return val;
      }
    },
  },
  { accessorKey: "event_type", header: "Event" },
  {
    id: "actor",
    header: "Actor",
    cell: ({ row }) =>
      row.original.actor_username ?? row.original.actor_email ?? "—",
  },
  {
    id: "team",
    header: "Team",
    cell: ({ row }) => row.original.team_name ?? "—",
  },
  {
    id: "object",
    header: "Object",
    cell: ({ row }) => {
      const { event_type, resource_name, metadata } = row.original;
      if (event_type === "question.asked") {
        const q = ((metadata as Record<string, unknown>)?.question as string) ?? "";
        const prefix = resource_name ? `[${resource_name}] ` : "";
        const snippet = q.length > 60 ? `${q.slice(0, 60)}…` : q;
        return `${prefix}"${snippet}"`;
      }
      return resource_name ?? "—";
    },
  },
];

export default function AuditLogPanel() {
  const { data, isLoading, isError, error } = useAuditLog({ limit: 100 });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted text-sm">
        Loading audit log…
      </div>
    );
  }

  if (isError) {
    return (
      <Alert color="failure">
        {error instanceof Error ? error.message : "Failed to load audit log."}
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-text text-center">Audit Log</h2>
      <DataTable<AuditLogItem>
        data={data ?? []}
        columns={columns}
        pageSize={20}
      />
    </div>
  );
}
