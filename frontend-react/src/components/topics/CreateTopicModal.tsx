import { useState } from "react";
import { useForm } from "@tanstack/react-form";
import { Modal, Button, Label, TextInput, Textarea, Select, Alert } from "flowbite-react";
import { useAuth } from "../../lib/auth-context";
import { useCreateTopic } from "../../hooks/useTopics";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function CreateTopicModal({ open, onClose }: Props) {
  const { teams, activeTeamId } = useAuth();
  const createTopic = useCreateTopic();
  const [error, setError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: {
      team_id: activeTeamId ?? teams[0]?.id ?? "",
      name: "",
      description: "",
    },
    onSubmit: async ({ value }) => {
      setError(null);
      try {
        await createTopic.mutateAsync({
          team_id: value.team_id,
          name: value.name.trim(),
          description: value.description.trim() || undefined,
        });
        form.reset();
        onClose();
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to create topic");
      }
    },
  });

  function handleClose() {
    form.reset();
    setError(null);
    onClose();
  }

  return (
    <Modal show={open} onClose={handleClose} size="md">
      <Modal.Header>New Topic</Modal.Header>
      <Modal.Body>
        {error && (
          <Alert color="failure" className="mb-4">
            {error}
          </Alert>
        )}
        <form
          id="create-topic-form"
          onSubmit={(e) => {
            e.preventDefault();
            form.handleSubmit();
          }}
          className="space-y-4"
        >
          {teams.length > 1 && (
            <form.Field name="team_id">
              {(f) => (
                <div>
                  <Label htmlFor="team_id" value="Team" />
                  <Select
                    id="team_id"
                    value={f.state.value}
                    onChange={(e) => f.handleChange(e.target.value)}
                    required
                  >
                    {teams.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </Select>
                </div>
              )}
            </form.Field>
          )}

          <form.Field name="name">
            {(f) => (
              <div>
                <Label htmlFor="name" value="Name" />
                <TextInput
                  id="name"
                  value={f.state.value}
                  onChange={(e) => f.handleChange(e.target.value)}
                  placeholder="e.g. Product Q&A"
                  required
                  autoFocus
                />
              </div>
            )}
          </form.Field>

          <form.Field name="description">
            {(f) => (
              <div>
                <Label htmlFor="description" value="Description (optional)" />
                <Textarea
                  id="description"
                  value={f.state.value}
                  onChange={(e) => f.handleChange(e.target.value)}
                  placeholder="What is this topic about?"
                  rows={3}
                />
              </div>
            )}
          </form.Field>
        </form>
      </Modal.Body>
      <Modal.Footer>
        <Button
          type="submit"
          form="create-topic-form"
          color="blue"
          isProcessing={createTopic.isPending}
          disabled={createTopic.isPending}
        >
          Create
        </Button>
        <Button color="gray" onClick={handleClose}>
          Cancel
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
