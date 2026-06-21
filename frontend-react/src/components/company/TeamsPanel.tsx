import { useState } from "react";
import { useForm } from "@tanstack/react-form";
import { Alert, Button, Label, Modal, TextInput, Badge } from "flowbite-react";
import type { ColumnDef } from "@tanstack/react-table";
import { Plus, Users, Trash2, ChevronLeft } from "lucide-react";
import DataTable from "../common/DataTable";
import {
  useTeams,
  useCreateTeam,
  useTeamMembers,
  useRemoveMember,
} from "../../hooks/useTeams";
import { useAuth } from "../../lib/auth-context";
import type { Team, TeamMember } from "../../lib/api/types";

export default function TeamsPanel() {
  const { user } = useAuth();
  const { data: teams, isLoading, isError, error } = useTeams();
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const isAdmin = user?.role === "owner" || user?.role === "admin";

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted text-sm">
        Loading teams…
      </div>
    );
  }

  if (isError) {
    return (
      <Alert color="failure">
        {error instanceof Error ? error.message : "Failed to load teams."}
      </Alert>
    );
  }

  if (selectedTeamId) {
    const team = teams?.find((t) => t.id === selectedTeamId);
    return (
      <div className="space-y-4">
        <button
          onClick={() => setSelectedTeamId(null)}
          className="flex items-center gap-1 text-sm text-accent hover:underline"
        >
          <ChevronLeft size={14} /> Back to teams
        </button>
        {team && <TeamMembersView team={team} isAdmin={isAdmin} />}
      </div>
    );
  }

  const teamColumns: ColumnDef<Team>[] = [
    { accessorKey: "name", header: "Name" },
    {
      accessorKey: "description",
      header: "Description",
      cell: ({ getValue }) => getValue<string | null>() ?? "—",
    },
    {
      accessorKey: "member_count",
      header: "Members",
      cell: ({ getValue }) => getValue<number | null>() ?? 0,
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <button
          onClick={() => setSelectedTeamId(row.original.id)}
          className="flex items-center gap-1 text-xs text-accent hover:underline"
        >
          <Users size={12} /> Members
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-text text-center">Teams</h2>
      <div className="flex items-center justify-between">
        {isAdmin && (
          <Button size="xs" onClick={() => setShowCreate(true)}>
            <Plus size={14} className="mr-1" />
            New team
          </Button>
        )}
      </div>

      <DataTable<Team>
        data={teams ?? []}
        columns={teamColumns}
        pageSize={10}
      />

      <CreateTeamModal
        show={showCreate}
        onClose={() => setShowCreate(false)}
      />
    </div>
  );
}

function CreateTeamModal({ show, onClose }: { show: boolean; onClose: () => void }) {
  const createTeam = useCreateTeam();
  const [apiError, setApiError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: { name: "", description: "" },
    onSubmit: async ({ value }) => {
      try {
        setApiError(null);
        await createTeam.mutateAsync({
          name: value.name,
          description: value.description || undefined,
        });
        handleClose();
      } catch (e) {
        setApiError(e instanceof Error ? e.message : "Failed to create team.");
      }
    },
  });

  function handleClose() {
    form.reset();
    setApiError(null);
    onClose();
  }

  return (
    <Modal show={show} onClose={handleClose} size="md">
      <Modal.Header>New Team</Modal.Header>
      <Modal.Body>
        {apiError && <Alert color="failure" className="mb-4">{apiError}</Alert>}
        <form
          id="create-team-form"
          onSubmit={(e) => { e.preventDefault(); form.handleSubmit(); }}
          className="space-y-4"
        >
          <form.Field name="name">
            {(f) => (
              <div>
                <Label htmlFor="team-name" value="Name" />
                <TextInput
                  id="team-name"
                  value={f.state.value}
                  onChange={(e) => f.handleChange(e.target.value)}
                  placeholder="Engineering"
                  required
                  autoFocus
                />
              </div>
            )}
          </form.Field>
          <form.Field name="description">
            {(f) => (
              <div>
                <Label htmlFor="team-desc" value="Description (optional)" />
                <TextInput
                  id="team-desc"
                  value={f.state.value}
                  onChange={(e) => f.handleChange(e.target.value)}
                  placeholder="Team description"
                />
              </div>
            )}
          </form.Field>
        </form>
      </Modal.Body>
      <Modal.Footer>
        <form.Subscribe selector={(s) => s.isSubmitting}>
          {(isSubmitting) => (
            <Button type="submit" form="create-team-form" disabled={isSubmitting}>
              {isSubmitting ? "Creating…" : "Create"}
            </Button>
          )}
        </form.Subscribe>
        <Button color="gray" onClick={handleClose}>Cancel</Button>
      </Modal.Footer>
    </Modal>
  );
}

function TeamMembersView({ team, isAdmin }: { team: Team; isAdmin: boolean }) {
  const { data: members, isLoading, isError, error } = useTeamMembers(team.id);
  const removeMember = useRemoveMember();

  const memberColumns: ColumnDef<TeamMember>[] = [
    { accessorKey: "username", header: "Username" },
    { accessorKey: "email", header: "Email" },
    {
      accessorKey: "team_role",
      header: "Team role",
      cell: ({ getValue }) => (
        <Badge color="gray" className="w-fit">
          {getValue<string>()}
        </Badge>
      ),
    },
    { accessorKey: "company_role", header: "Company role" },
    ...(isAdmin
      ? [
          {
            id: "remove",
            header: "",
            cell: ({ row }: { row: { original: TeamMember } }) => (
              <button
                onClick={() => removeMember.mutate({ teamId: team.id, userId: row.original.id })}
                className="text-red-500 hover:text-red-700"
                title="Remove member"
              >
                <Trash2 size={14} />
              </button>
            ),
          } as ColumnDef<TeamMember>,
        ]
      : []),
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-muted text-sm">
        Loading members…
      </div>
    );
  }

  if (isError) {
    return (
      <Alert color="failure">
        {error instanceof Error ? error.message : "Failed to load members."}
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold text-text">{team.name}</h2>
        {team.description && (
          <span className="text-sm text-muted">— {team.description}</span>
        )}
      </div>
      <DataTable<TeamMember>
        data={members ?? []}
        columns={memberColumns}
        pageSize={10}
      />
    </div>
  );
}
