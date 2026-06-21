import { useState } from "react";
import SplitPane from "../components/common/SplitPane";
import TeamsPanel from "../components/company/TeamsPanel";
import InvitesPanel from "../components/company/InvitesPanel";
import CompanyPanel from "../components/company/CompanyPanel";
import UsagePanel from "../components/company/UsagePanel";
import AuditLogPanel from "../components/company/AuditLogPanel";

type Tab = "teams" | "invites" | "company" | "usage" | "audit";

const TABS: { id: Tab; label: string }[] = [
  { id: "teams", label: "Teams" },
  { id: "invites", label: "Invites" },
  { id: "company", label: "Company" },
  { id: "usage", label: "Usage" },
  { id: "audit", label: "Audit Log" },
];

export default function CompanySettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("teams");

  const nav = (
    <nav className="flex flex-col gap-1 p-2">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveTab(tab.id)}
          className={[
            "text-left px-3 py-2 rounded text-sm font-medium transition-colors",
            activeTab === tab.id
              ? "bg-accent text-white"
              : "text-text-dim hover:bg-surface hover:text-text",
          ].join(" ")}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );

  return (
    <div className="py-6">
      <SplitPane nav={nav}>
        {activeTab === "teams" && <TeamsPanel />}
        {activeTab === "invites" && <InvitesPanel />}
        {activeTab === "company" && <CompanyPanel />}
        {activeTab === "usage" && <UsagePanel />}
        {activeTab === "audit" && <AuditLogPanel />}
      </SplitPane>
    </div>
  );
}
