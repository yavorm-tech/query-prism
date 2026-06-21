import { useAuth } from "../../lib/auth-context";

export default function CompanyPanel() {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-text text-center">Company</h2>
      <div className="bg-panel border border-border rounded-lg divide-y divide-border">
        <Row label="Company name" value={user.company_name ?? "—"} />
        <Row label="Plan" value={user.plan} capitalize />
        <Row label="Your role" value={user.role} capitalize />
        <Row label="Email" value={user.email} />
        <Row label="Username" value={user.username} />
      </div>
    </div>
  );
}

function Row({ label, value, capitalize = false }: { label: string; value: string; capitalize?: boolean }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-sm text-muted">{label}</span>
      <span className={`text-sm font-medium text-text${capitalize ? " capitalize" : ""}`}>{value}</span>
    </div>
  );
}
