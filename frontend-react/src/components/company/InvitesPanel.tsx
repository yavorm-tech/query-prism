import { useState } from "react";
import { useForm } from "@tanstack/react-form";
import { Alert, Button, Label, Modal, TextInput, Select } from "flowbite-react";
import type { ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import DataTable from "../common/DataTable";
import { useInvites, useCreateInvite } from "../../hooks/useInvites";
import { useTeams } from "../../hooks/useTeams";
import { useAuth } from "../../lib/auth-context";
import type { InviteListItem } from "../../lib/api/types";

const columns: ColumnDef<InviteListItem>[] = [
  { accessorKey: "email", header: "Email" },
  { accessorKey: "role", header: "Role" },
  { accessorKey: "team_name", header: "Team" },
  { accessorKey: "invited_by_username", header: "Invited by" },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ getValue }) => {
      const s = getValue<string>();
      const color = s === "accepted" ? "text-green-400" : s === "expired" ? "text-red-400" : "text-amber-400";
      return <span className={`text-xs font-medium capitalize ${color}`}>{s}</span>;
    },
  },
  {
    accessorKey: "expires_at",
    header: "Expires",
    cell: ({ getValue }) => {
      const val = getValue<string>();
      try { return new Date(val).toLocaleDateString(); } catch { return val; }
    },
  },
];

export default function InvitesPanel() {
  const { user } = useAuth();
  const { data: invites, isLoading, isError, error } = useInvites();
  const [showForm, setShowForm] = useState(false);

  const isAdmin = user?.role === "owner" || user?.role === "admin";

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted text-sm">
        Loading invites…
      </div>
    );
  }

  if (isError) {
    return (
      <Alert color="failure">
        {error instanceof Error ? error.message : "Failed to load invites."}
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-text text-center">Invites</h2>
      <div className="flex items-center justify-between">
        {isAdmin && (
          <Button size="xs" onClick={() => setShowForm(true)}>
            <Plus size={14} className="mr-1" />
            Invite user
          </Button>
        )}
      </div>

      <DataTable<InviteListItem>
        data={invites ?? []}
        columns={columns}
        pageSize={10}
      />

      <InviteModal
        show={showForm}
        onClose={() => setShowForm(false)}
      />
    </div>
  );
}

function InviteModal({ show, onClose }: { show: boolean; onClose: () => void }) {
  const { data: teams } = useTeams();
  const createInvite = useCreateInvite();
  const [apiError, setApiError] = useState<string | null>(null);
  const [teamError, setTeamError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: { email: "", team_id: "", role: "member" },
    onSubmit: async ({ value }) => {
      if (!value.team_id) {
        setTeamError("Please select a team.");
        return;
      }
      try {
        setTeamError(null);
        setApiError(null);
        await createInvite.mutateAsync({
          email: value.email,
          team_id: value.team_id,
          role: value.role || undefined,
        });
        handleClose();
      } catch (e) {
        setApiError(e instanceof Error ? e.message : "Failed to send invite.");
      }
    },
  });

  function handleClose() {
    form.reset();
    setApiError(null);
    setTeamError(null);
    onClose();
  }

  return (
    <Modal show={show} onClose={handleClose} size="md">
      <Modal.Header>Invite User</Modal.Header>
      <Modal.Body>
        {apiError && <Alert color="failure" className="mb-4">{apiError}</Alert>}
        <form
          id="invite-user-form"
          onSubmit={(e) => { e.preventDefault(); form.handleSubmit(); }}
          className="space-y-4"
        >
          <form.Field name="email">
            {(f) => (
              <div>
                <Label htmlFor="invite-email" value="Email" />
                <TextInput
                  id="invite-email"
                  type="email"
                  value={f.state.value}
                  onChange={(e) => f.handleChange(e.target.value)}
                  placeholder="user@example.com"
                  required
                  autoFocus
                />
              </div>
            )}
          </form.Field>
          <form.Field name="team_id">
            {(f) => (
              <div>
                <Label htmlFor="invite-team" value="Team" />
                <Select
                  id="invite-team"
                  value={f.state.value}
                  onChange={(e) => {
                    f.handleChange(e.target.value);
                    if (e.target.value) setTeamError(null);
                  }}
                  color={teamError ? "failure" : undefined}
                >
                  <option value="">Select a team…</option>
                  {(teams ?? []).map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </Select>
                {teamError && <p className="mt-1 text-xs text-red-600">{teamError}</p>}
              </div>
            )}
          </form.Field>
          <form.Field name="role">
            {(f) => (
              <div>
                <Label htmlFor="invite-role" value="Role" />
                <Select
                  id="invite-role"
                  value={f.state.value}
                  onChange={(e) => f.handleChange(e.target.value)}
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </Select>
              </div>
            )}
          </form.Field>
        </form>
      </Modal.Body>
      <Modal.Footer>
        <form.Subscribe selector={(s) => ({ isSubmitting: s.isSubmitting, teamId: s.values.team_id })}>
          {({ isSubmitting, teamId }) => (
            <Button type="submit" form="invite-user-form" disabled={isSubmitting || !teamId}>
              {isSubmitting ? "Sending…" : "Send invite"}
            </Button>
          )}
        </form.Subscribe>
        <Button color="gray" onClick={handleClose}>Cancel</Button>
      </Modal.Footer>
    </Modal>
  );
}
