import { useState, useCallback } from "react";
import { Spinner, Alert } from "flowbite-react";
import { useAuth } from "../lib/auth-context";
import { useTopics, useDeleteTopic } from "../hooks/useTopics";
import TopicsTable from "../components/topics/TopicsTable";
import TopicToolbar from "../components/topics/TopicToolbar";
import CreateTopicModal from "../components/topics/CreateTopicModal";
import EditTopicModal from "../components/topics/EditTopicModal";
import type { Topic } from "../lib/api/types";

export default function TopicsPage() {
  const { activeTeamId } = useAuth();
  const { data: topics = [], isLoading, isError, error } = useTopics(activeTeamId ?? undefined);
  const deleteTopic = useDeleteTopic();

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showCreate, setShowCreate] = useState(false);
  const [editingTopic, setEditingTopic] = useState<Topic | null>(null);

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const handleDeleteSelected = useCallback(async () => {
    if (selectedIds.size === 0) return;
    const confirmed = window.confirm(
      `Delete ${selectedIds.size} topic${selectedIds.size > 1 ? "s" : ""}? This cannot be undone.`
    );
    if (!confirmed) return;
    await Promise.all([...selectedIds].map((id) => deleteTopic.mutateAsync(id)));
    setSelectedIds(new Set());
  }, [selectedIds, deleteTopic]);

  const handleDeleteRow = useCallback(async (id: string) => {
    const topic = topics.find((t) => t.id === id);
    const confirmed = window.confirm(
      `Delete "${topic?.name ?? "this topic"}"? This cannot be undone.`
    );
    if (!confirmed) return;
    await deleteTopic.mutateAsync(id);
    setSelectedIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
  }, [topics, deleteTopic]);

  const toolbar = (
    <TopicToolbar
      total={topics.length}
      selectedIds={selectedIds}
      onAdd={() => setShowCreate(true)}
      onDelete={handleDeleteSelected}
      isDeleting={deleteTopic.isPending}
    />
  );

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4 text-center">Topics</h1>

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {isError && (
        <Alert color="failure" className="mb-4">
          {error instanceof Error ? error.message : "Failed to load topics"}
        </Alert>
      )}

      {!isLoading && !isError && (
        <TopicsTable
          topics={topics}
          selectedIds={selectedIds}
          onToggleSelect={handleToggleSelect}
          onDeleteRow={handleDeleteRow}
          onEditRow={setEditingTopic}
          toolbar={toolbar}
        />
      )}

      <CreateTopicModal open={showCreate} onClose={() => setShowCreate(false)} />
      <EditTopicModal topic={editingTopic} onClose={() => setEditingTopic(null)} />
    </div>
  );
}
