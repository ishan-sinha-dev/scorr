import Link from "next/link";
import { notFound } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { createAuditPeriod, deleteAuditPeriod } from "./actions";
import { DeleteAuditPeriodButton } from "./delete-audit-period-button";

type AuditPeriod = {
  id: string;
  name: string;
  period_start: string;
  period_end: string;
};

export default async function OrganizationAuditPeriodsPage({
  params,
}: {
  params: Promise<{ orgId: string }>;
}) {
  const { orgId } = await params;
  const response = await apiFetch(`/organizations/${orgId}/audit-periods`);

  if (response.status === 403 || response.status === 404) {
    notFound();
  }

  const periods: AuditPeriod[] = response.ok ? await response.json() : [];
  const createForThisOrg = createAuditPeriod.bind(null, orgId);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Audit periods</h1>
      </div>

      <form action={createForThisOrg} className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <input
          name="name"
          required
          placeholder="Name (e.g. FY2026)"
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground sm:col-span-2"
        />
        <input
          name="period_start"
          type="date"
          required
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
        />
        <input
          name="period_end"
          type="date"
          required
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
        />
        <button
          type="submit"
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground sm:col-span-4"
        >
          Add audit period
        </button>
      </form>

      <ul className="divide-y divide-border rounded-md border border-border">
        {periods.map((period) => (
          <li key={period.id} className="flex items-center justify-between px-4 py-3">
            <Link
              href={`/organizations/${orgId}/audit-periods/${period.id}`}
              className="flex-1 text-sm text-foreground hover:underline"
            >
              {period.name}
              <span className="ml-2 text-muted-foreground">
                {period.period_start} – {period.period_end}
              </span>
            </Link>
            <form action={deleteAuditPeriod.bind(null, orgId, period.id)}>
              <DeleteAuditPeriodButton periodName={period.name} />
            </form>
          </li>
        ))}
        {periods.length === 0 && (
          <li className="px-4 py-3 text-sm text-muted-foreground">No audit periods yet.</li>
        )}
      </ul>
    </div>
  );
}
