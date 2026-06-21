import { useState } from "react";
import SplitPane from "../components/common/SplitPane";
import AccountPanel from "../components/user/AccountPanel";
import UISettingsPanel from "../components/user/UISettingsPanel";

type Tab = "account" | "ui";

const TABS: { id: Tab; label: string }[] = [
  { id: "account", label: "Account" },
  { id: "ui", label: "UI Settings" },
];

export default function UserSettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("account");

  const nav = (
    <nav className="py-4 pr-4">
      <ul className="space-y-1">
        {TABS.map(({ id, label }) => (
          <li key={id}>
            <button
              type="button"
              onClick={() => setActiveTab(id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === id
                  ? "bg-accent text-white"
                  : "text-text-dim hover:bg-panel hover:text-text"
              }`}
            >
              {label}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );

  return (
    <div className="max-w-4xl mx-auto py-8">
      <h1 className="text-2xl font-bold px-[2.5%] mb-6">User Settings</h1>
      <SplitPane nav={nav}>
        {activeTab === "account" && <AccountPanel />}
        {activeTab === "ui" && <UISettingsPanel />}
      </SplitPane>
    </div>
  );
}
