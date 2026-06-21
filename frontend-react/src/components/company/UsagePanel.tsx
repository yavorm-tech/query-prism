import { Alert } from "flowbite-react";
import { Progress } from "flowbite-react";
import { useUsage } from "../../hooks/useUsage";

export default function UsagePanel() {
  const { data, isLoading, isError, error } = useUsage();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted text-sm">
        Loading usage…
      </div>
    );
  }

  if (isError) {
    return (
      <Alert color="failure">
        {error instanceof Error ? error.message : "Failed to load usage data."}
      </Alert>
    );
  }

  if (!data) return null;

  const queryPercent = data.queries.percent;
  const storagePercent = data.storage.percent;
  const teamsPercent =
    data.teams.limit != null ? Math.round((data.teams.used / data.teams.limit) * 100) : 0;
  const usersPercent =
    data.users.limit != null ? Math.round((data.users.used / data.users.limit) * 100) : 0;

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-text text-center">Usage</h2>
      <div className="flex justify-end">
        <span className="text-sm text-muted capitalize">
          Plan: <span className="font-medium text-accent">{data.plan}</span>
          {data.price_monthly > 0 && (
            <span className="ml-1 text-muted">(${data.price_monthly}/mo)</span>
          )}
        </span>
      </div>

      <div className="space-y-5">
        <UsageBar
          label="Queries"
          used={data.queries.used}
          limit={data.queries.limit}
          percent={queryPercent}
          suffix={data.queries.resets_at ? `resets ${formatDate(data.queries.resets_at)}` : undefined}
        />
        <UsageBar
          label="Storage"
          used={data.storage.used_mb}
          limit={data.storage.limit_mb}
          percent={storagePercent}
          unit="MB"
        />
        <UsageBar
          label="Teams"
          used={data.teams.used}
          limit={data.teams.limit}
          percent={teamsPercent}
        />
        <UsageBar
          label="Users"
          used={data.users.used}
          limit={data.users.limit}
          percent={usersPercent}
        />
      </div>
    </div>
  );
}

function UsageBar({
  label,
  used,
  limit,
  percent,
  unit,
  suffix,
}: {
  label: string;
  used: number;
  limit: number | null;
  percent: number;
  unit?: string;
  suffix?: string;
}) {
  const color = percent >= 90 ? "red" : percent >= 70 ? "yellow" : "blue";
  const limitLabel = limit != null ? `${limit}${unit ? " " + unit : ""}` : "Unlimited";
  const usedLabel = `${used}${unit ? " " + unit : ""}`;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-text">{label}</span>
        <span className="text-muted">
          {usedLabel} / {limitLabel}
          {suffix && <span className="ml-2 text-xs text-accent-dim">{suffix}</span>}
        </span>
      </div>
      <Progress
        progress={limit != null ? Math.min(percent, 100) : 0}
        color={color}
        size="sm"
      />
    </div>
  );
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}
