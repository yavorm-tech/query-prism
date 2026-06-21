import ChatPanel from "../chat/ChatPanel";

interface ChatTabProps {
  topicId: string;
  topicName: string;
  teamId?: string | null;
}

export default function ChatTab({ topicId, topicName, teamId }: ChatTabProps) {
  return (
    <div className="py-4 flex flex-col h-full min-h-[400px]">
      <ChatPanel topicId={topicId} topicName={topicName} teamId={teamId} />
    </div>
  );
}
