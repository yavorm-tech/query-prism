import { useState } from "react";
import SplitPane from "../components/common/SplitPane";
import BillingPlansPanel from "../components/billing/BillingPlansPanel";
import InvoicesPanel from "../components/billing/InvoicesPanel";

type Tab = "plans" | "invoices";

const TABS: { id: Tab; label: string }[] = [
  { id: "plans", label: "Billing Plans" },
  { id: "invoices", label: "Invoices" },
];

export default function PricingPage() {
  const [activeTab, setActiveTab] = useState<Tab>("plans");

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
        {activeTab === "plans" && <BillingPlansPanel />}
        {activeTab === "invoices" && <InvoicesPanel />}
      </SplitPane>
    </div>
  );
}
