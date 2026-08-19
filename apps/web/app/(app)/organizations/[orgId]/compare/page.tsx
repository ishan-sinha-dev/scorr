import Link from "next/link";
import { notFound } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/badge";

type AuditPeriod = {
  id: string;
  name: string;
};

type ControlChange = {
  control_code: string;
  description_from: string;
  description_to: string;
};

type ControlComparison = {
  added: { control_code: string; description: string }[];
  removed: { control_code: string; description: string }[];
  changed: ControlChange[];
  unchanged_count: number;
};

type EntityCounts = {
  cuecs: number;
  exceptions: number;
  subservice_organizations: number;
};

type AuditPeriodComparison = {
  from_audit_period_id: string;
  from_audit_period_name: string;
  to_audit_period_id: string;
  to_audit_period_name: string;
  controls: ControlComparison;
  entity_counts_from: EntityCounts;
  entity_counts_to: EntityCounts;
};

export default async function ComparePage({
  params,
  searchParams,
}: {
  params: Promise<{ orgId: string }>;
  searchParams: Promise<{ from?: string; to?: string }>;
}) {
  const { orgId } = await params;
  const { from, to } = await searchParams;

  const periodsResponse = await apiFetch(`/organizations/${orgId}/audit-periods`);
  if (periodsResponse.status === 403 || periodsResponse.status === 404) {
    notFound();
  }
  const periods: AuditPeriod[] = periodsResponse.ok ? await periodsResponse.json() : [];

  let comparison: AuditPeriodComparison | null = null;
  if (from && to && from !== to) {
    const comparisonResponse = await apiFetch(
      `/organizations/${orgId}/compare-audit-periods?from_audit_period_id=${from}&to_audit_period_id=${to}`
    );
    comparison = comparisonResponse.ok ? await comparisonResponse.json() : null;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <Link
          href={`/organizations/${orgId}`}
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Audit periods
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-foreground">Compare audit periods</h1>
      </div>

      <form className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">From</label>
          <select
            name="from"
            defaultValue={from ?? ""}
            required
            className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="" disabled>
              Select period
            </option>
            {periods.map((period) => (
              <option key={period.id} value={period.id}>
                {period.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">To</label>
          <select
            name="to"
            defaultValue={to ?? ""}
            required
            className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="" disabled>
              Select period
            </option>
            {periods.map((period) => (
              <option key={period.id} value={period.id}>
                {period.name}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
        >
          Compare
        </button>
      </form>

      {from && to && from === to && (
        <p className="text-sm text-muted-foreground">Pick two different audit periods.</p>
      )}

      {from && to && from !== to && !comparison && (
        <p className="text-sm text-muted-foreground">
          Could not load comparison for the selected periods.
        </p>
      )}

      {comparison && (
        <div className="space-y-6">
          <p className="text-sm text-muted-foreground">
            {comparison.from_audit_period_name} → {comparison.to_audit_period_name}
          </p>

          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-md border border-border p-4">
              <p className="text-xs text-muted-foreground">CUECs</p>
              <p className="mt-1 text-sm text-foreground">
                {comparison.entity_counts_from.cuecs} → {comparison.entity_counts_to.cuecs}
              </p>
            </div>
            <div className="rounded-md border border-border p-4">
              <p className="text-xs text-muted-foreground">Exceptions</p>
              <p className="mt-1 text-sm text-foreground">
                {comparison.entity_counts_from.exceptions} →{" "}
                {comparison.entity_counts_to.exceptions}
              </p>
            </div>
            <div className="rounded-md border border-border p-4">
              <p className="text-xs text-muted-foreground">Subservice orgs</p>
              <p className="mt-1 text-sm text-foreground">
                {comparison.entity_counts_from.subservice_organizations} →{" "}
                {comparison.entity_counts_to.subservice_organizations}
              </p>
            </div>
          </div>

          <div>
            <h2 className="text-sm font-semibold text-foreground">
              SOC controls ({comparison.controls.unchanged_count} unchanged)
            </h2>
            <ul className="mt-2 space-y-1">
              {comparison.controls.added.map((control) => (
                <li key={`added-${control.control_code}`} className="flex items-center gap-2 text-sm">
                  <Badge tone="green">Added</Badge>
                  <span className="font-medium text-foreground">{control.control_code}</span>
                  <span className="text-muted-foreground">{control.description}</span>
                </li>
              ))}
              {comparison.controls.removed.map((control) => (
                <li key={`removed-${control.control_code}`} className="flex items-center gap-2 text-sm">
                  <Badge tone="red">Removed</Badge>
                  <span className="font-medium text-foreground">{control.control_code}</span>
                  <span className="text-muted-foreground">{control.description}</span>
                </li>
              ))}
              {comparison.controls.changed.map((change) => (
                <li key={`changed-${change.control_code}`} className="text-sm">
                  <div className="flex items-center gap-2">
                    <Badge tone="yellow">Changed</Badge>
                    <span className="font-medium text-foreground">{change.control_code}</span>
                  </div>
                  <p className="ml-16 text-xs text-muted-foreground">
                    {change.description_from} → {change.description_to}
                  </p>
                </li>
              ))}
              {comparison.controls.added.length === 0 &&
                comparison.controls.removed.length === 0 &&
                comparison.controls.changed.length === 0 && (
                  <li className="text-sm text-muted-foreground">
                    No control changes between these periods.
                  </li>
                )}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
