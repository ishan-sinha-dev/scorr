import { Download } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { FindingsTable, type Finding } from "@/components/findings-table";
import { computeFindings, reviewFinding } from "./actions";

export default async function FindingsPage({
  params,
}: {
  params: Promise<{ orgId: string; auditPeriodId: string }>;
}) {
  const { orgId, auditPeriodId } = await params;
  const response = await apiFetch(`/organizations/${orgId}/audit-periods/${auditPeriodId}/findings`);

  if (response.status === 403 || response.status === 404) {
    notFound();
  }

  const findings: Finding[] = response.ok ? await response.json() : [];
  const computeForThisPeriod = computeFindings.bind(null, orgId, auditPeriodId);
  const reviewForThisPeriod = reviewFinding.bind(null, orgId, auditPeriodId);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link
            href={`/organizations/${orgId}/audit-periods/${auditPeriodId}`}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← Documents
          </Link>
          <h1 className="mt-1 text-lg font-semibold text-foreground">Findings</h1>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={`/organizations/${orgId}/audit-periods/${auditPeriodId}/findings/export`}
            className="flex items-center gap-1.5 rounded-md border border-input px-3 py-2 text-sm font-medium text-foreground"
          >
            <Download className="h-4 w-4" />
            Export
          </a>
          <form action={computeForThisPeriod}>
            <button
              type="submit"
              className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
            >
              Compute findings
            </button>
          </form>
        </div>
      </div>

      {findings.length === 0 ? (
        <p className="rounded-md border border-border px-4 py-3 text-sm text-muted-foreground">
          No findings computed yet.
        </p>
      ) : (
        <FindingsTable findings={findings} reviewAction={reviewForThisPeriod} />
      )}
    </div>
  );
}
