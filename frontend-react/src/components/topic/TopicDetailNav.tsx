import { FileText, MessageSquare, History } from "lucide-react";

type Tab = "documents" | "chat" | "history";

interface Props {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

const NAV_ITEMS: { id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "documents", label: "Documents", icon: FileText },
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "history", label: "History", icon: History },
];

export default function TopicDetailNav({ activeTab, onTabChange }: Props) {
  return (
    <nav className="py-4 pr-4">
      <ul className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <li key={id}>
            <button
              onClick={() => onTabChange(id)}
              className={[
                "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left",
                activeTab === id
                  ? "bg-accent/10 text-accent"
                  : "text-muted hover:text-foreground hover:bg-surface-alt",
              ].join(" ")}
              aria-current={activeTab === id ? "page" : undefined}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
