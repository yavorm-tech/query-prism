import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { getTopic } from "../lib/api/topics";
import { qk } from "../lib/queryKeys";
import { useAuth } from "../lib/auth-context";
import SplitPane from "../components/common/SplitPane";
import TopicDetailNav from "../components/topic/TopicDetailNav";
import DocumentsTab from "../components/documents/DocumentsTab";
import ChatTab from "../components/topic/ChatTab";
import HistoryTab from "../components/topic/HistoryTab";

type Tab = "documents" | "chat" | "history";

export default function TopicDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<Tab>("documents");
  const { activeTeamId } = useAuth();

  const { data: topic, isLoading, isError } = useQuery({
    queryKey: qk.topic(id),
    queryFn: () => getTopic(id),
    enabled: Boolean(id),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted text-sm">
        Loading topic…
      </div>
    );
  }

  if (isError || !topic) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <p className="text-red-400 text-sm">Failed to load topic.</p>
        <Link to="/topics" className="text-accent text-sm hover:underline">
          Back to topics
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 py-4">
      {/* Breadcrumb */}
      <div className="px-[2.5%]">
        <Link
          to="/topics"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Topics
        </Link>
        <h1 className="text-xl font-semibold mt-1">{topic.name}</h1>
        {topic.description && (
          <p className="text-sm text-muted mt-0.5">{topic.description}</p>
        )}
      </div>

      <SplitPane
        nav={
          <TopicDetailNav
            activeTab={activeTab}
            onTabChange={(tab) => setActiveTab(tab)}
          />
        }
      >
        {activeTab === "documents" && <DocumentsTab topicId={id} />}

        {activeTab === "chat" && (
          <ChatTab topicId={id} topicName={topic.name} teamId={activeTeamId} />
        )}

        {activeTab === "history" && (
          <HistoryTab topicId={id} topicName={topic.name} />
        )}
      </SplitPane>
    </div>
  );
}
