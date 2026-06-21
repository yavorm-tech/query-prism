import { useState, useEffect } from "react";
import { useForm } from "@tanstack/react-form";
import { Modal, Button, Label, TextInput, Textarea, Alert } from "flowbite-react";
import { useUpdateTopic } from "../../hooks/useTopics";
import type { Topic } from "../../lib/api/types";

interface Props {
  topic: Topic | null;
  onClose: () => void;
}

export default function EditTopicModal({ topic, onClose }: Props) {
  const updateTopic = useUpdateTopic();
  const [error, setError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: { name: "", description: "" },
    onSubmit: async ({ value }) => {
      if (!topic) return;
      setError(null);
      try {
        await updateTopic.mutateAsync({
          id: topic.id,
          body: { name: value.name.trim(), description: value.description.trim() || undefined },
        });
        onClose();
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to update topic");
      }
    },
  });

  useEffect(() => {
    if (topic) {
      form.setFieldValue("name", topic.name);
      form.setFieldValue("description", topic.description ?? "");
      setError(null);
    }
  }, [topic]);

  function handleClose() {
    form.reset();
    setError(null);
    onClose();
  }

  return (
    <Modal show={!!topic} onClose={handleClose} size="md">
      <Modal.Header>Edit Topic</Modal.Header>
      <Modal.Body>
        {error && <Alert color="failure" className="mb-4">{error}</Alert>}
        <form
          id="edit-topic-form"
          onSubmit={(e) => { e.preventDefault(); form.handleSubmit(); }}
          className="space-y-4"
        >
          <form.Field name="name">
            {(f) => (
              <div>
                <Label htmlFor="edit-name" value="Name" />
                <TextInput
                  id="edit-name"
                  value={f.state.value}
                  onChange={(e) => f.handleChange(e.target.value)}
                  required
                  autoFocus
                />
              </div>
            )}
          </form.Field>
          <form.Field name="description">
            {(f) => (
              <div>
                <Label htmlFor="edit-description" value="Description (optional)" />
                <Textarea
                  id="edit-description"
                  value={f.state.value}
                  onChange={(e) => f.handleChange(e.target.value)}
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
          form="edit-topic-form"
          color="blue"
          isProcessing={updateTopic.isPending}
          disabled={updateTopic.isPending}
        >
          Save
        </Button>
        <Button color="gray" onClick={handleClose}>Cancel</Button>
      </Modal.Footer>
    </Modal>
  );
}
