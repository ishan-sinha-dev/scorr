import Link from "next/link";
import { notFound } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/badge";
import { PollingActionButton } from "@/components/polling-action-button";
import { SubmitButton } from "@/components/submit-button";
import {
  analyzeDocument,
  carryForwardControls,
  mapControls,
  parseInternalControls,
  uploadDocument,
} from "./actions";

const ANALYZABLE_DOCUMENT_TYPES = new Set(["soc_report", "bridge_letter"]);

type ExtractionStatus = "pending" | "processing" | "complete" | "failed";

type Document = {
  id: string;
  document_type: "soc_report" | "bridge_letter" | "internal_control_framework";
  file_name: string;
  created_at: string;
  view_url: string;
  extraction_status: ExtractionStatus | null;
};

const DOCUMENT_TYPE_LABELS: Record<Document["document_type"], string> = {
  soc_report: "SOC report",
  bridge_letter: "Bridge letter",
  internal_control_framework: "Internal control framework",
};

// Extraction runs async (Celery) — this badge is the only signal in the UI
// that it's happened at all, so a document that's stuck 'pending' because
// no worker is running is visible, not silently invisible.
const EXTRACTION_STATUS_LABELS: Record<ExtractionStatus, string> = {
  pending: "Extraction pending",
  processing: "Extracting…",
  complete: "Extracted",
  failed: "Extraction failed",
};

type InternalControl = {
  id: string;
  control_id: string | null;
  description: string;
  extraction_method: "deterministic" | "ai";
  requires_review: boolean;
};

type AuditPeriod = {
  id: string;
  name: string;
};

export default async function AuditPeriodDocumentsPage({
  params,
}: {
  params: Promise<{ orgId: string; auditPeriodId: string }>;
}) {
  const { orgId, auditPeriodId } = await params;
  const [response, controlsResponse, periodsResponse] = await Promise.all([
    apiFetch(`/organizations/${orgId}/audit-periods/${auditPeriodId}/documents`),
    apiFetch(`/organizations/${orgId}/audit-periods/${auditPeriodId}/internal-controls`),
    apiFetch(`/organizations/${orgId}/audit-periods`),
  ]);

  if (response.status === 403 || response.status === 404) {
    notFound();
  }

  const documents: Document[] = response.ok ? await response.json() : [];
  const internalControls: InternalControl[] = controlsResponse.ok
    ? await controlsResponse.json()
    : [];
  const otherPeriods: AuditPeriod[] = periodsResponse.ok
    ? (await periodsResponse.json()).filter((p: AuditPeriod) => p.id !== auditPeriodId)
    : [];
  const uploadForThisPeriod = uploadDocument.bind(null, orgId, auditPeriodId);
  const carryForwardForThisPeriod = carryForwardControls.bind(null, orgId, auditPeriodId);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <Link
            href={`/organizations/${orgId}`}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← Audit periods
          </Link>
          <h1 className="mt-1 text-lg font-semibold text-foreground">Documents</h1>
        </div>
        <div className="flex items-center gap-4">
          <Link
            href={`/organizations/${orgId}/compare?to=${auditPeriodId}`}
            className="text-sm text-muted-foreground hover:underline"
          >
            Compare periods
          </Link>
          <Link
            href={`/organizations/${orgId}/audit-periods/${auditPeriodId}/findings`}
            className="text-sm text-primary hover:underline"
          >
            Findings →
          </Link>
        </div>
      </div>

      <form action={uploadForThisPeriod} className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <select
          name="document_type"
          required
          defaultValue="soc_report"
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground sm:col-span-2"
        >
          <option value="soc_report">SOC report</option>
          <option value="bridge_letter">Bridge letter</option>
          <option value="internal_control_framework">Internal control framework</option>
        </select>
        <input
          name="file"
          type="file"
          required
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground file:mr-2 file:rounded file:border-0 file:bg-muted file:px-2 file:py-1 sm:col-span-2"
        />
        <button
          type="submit"
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground sm:col-span-4"
        >
          Upload document
        </button>
      </form>

      <ul className="divide-y divide-border rounded-md border border-border">
        {documents.map((doc) => (
          <li
            key={doc.id}
            className="flex items-center justify-between px-4 py-3 text-sm text-foreground"
          >
            <span>
              {doc.file_name}
              <span className="ml-2 text-muted-foreground">
                {DOCUMENT_TYPE_LABELS[doc.document_type]} ·{" "}
                {new Date(doc.created_at).toLocaleDateString()}
              </span>
              {doc.extraction_status && (
                <span
                  className={
                    "ml-2 rounded-full px-2 py-0.5 text-xs " +
                    (doc.extraction_status === "failed"
                      ? "bg-destructive/10 text-destructive"
                      : doc.extraction_status === "complete"
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground")
                  }
                >
                  {EXTRACTION_STATUS_LABELS[doc.extraction_status]}
                </span>
              )}
            </span>
            <span className="flex items-center gap-3">
              {ANALYZABLE_DOCUMENT_TYPES.has(doc.document_type) &&
                doc.extraction_status === "complete" && (
                  <PollingActionButton
                    kind="analyze"
                    action={analyzeDocument.bind(null, orgId, auditPeriodId, doc.id)}
                    statusUrl={`/organizations/${orgId}/audit-periods/${auditPeriodId}/documents/${doc.id}/analysis-status`}
                    pendingLabel="Analyzing…"
                    className="text-primary hover:underline disabled:opacity-50"
                  >
                    Analyze
                  </PollingActionButton>
                )}
              {doc.document_type === "internal_control_framework" && (
                <form action={parseInternalControls.bind(null, orgId, auditPeriodId, doc.id)}>
                  <SubmitButton
                    pendingLabel="Parsing…"
                    className="text-primary hover:underline disabled:opacity-50"
                  >
                    Parse internal controls
                  </SubmitButton>
                </form>
              )}
              <a
                href={doc.view_url}
                target="_blank"
                rel="noreferrer"
                className="text-primary hover:underline"
              >
                View
              </a>
            </span>
          </li>
        ))}
        {documents.length === 0 && (
          <li className="px-4 py-3 text-sm text-muted-foreground">No documents yet.</li>
        )}
      </ul>

      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-foreground">Internal controls</h2>
          <div className="flex items-center gap-3">
            {otherPeriods.length > 0 && (
              <form action={carryForwardForThisPeriod} className="flex items-center gap-2">
                <select
                  name="from_audit_period_id"
                  required
                  className="rounded-md border border-input bg-background px-2 py-1.5 text-xs text-foreground"
                >
                  <option value="">Carry forward from…</option>
                  {otherPeriods.map((period) => (
                    <option key={period.id} value={period.id}>
                      {period.name}
                    </option>
                  ))}
                </select>
                <button type="submit" className="text-sm text-primary hover:underline">
                  Carry forward
                </button>
              </form>
            )}
            {internalControls.length > 0 && (
              <PollingActionButton
                kind="map-controls"
                action={mapControls.bind(null, orgId, auditPeriodId)}
                statusUrl={`/organizations/${orgId}/audit-periods/${auditPeriodId}/mapping-status`}
                pendingLabel="Mapping…"
                className="text-sm text-primary hover:underline disabled:opacity-50"
              >
                Map controls
              </PollingActionButton>
            )}
          </div>
        </div>
        {internalControls.length > 0 ? (
          <div className="mt-2 overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm text-foreground">
              <thead>
                <tr className="border-b border-border bg-muted/50 text-left text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Control ID</th>
                  <th className="px-4 py-2 font-medium">Description</th>
                  <th className="px-4 py-2 font-medium">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {internalControls.map((control) => (
                  <tr key={control.id}>
                    <td className="px-4 py-2 font-medium">{control.control_id ?? "—"}</td>
                    <td className="px-4 py-2">{control.description}</td>
                    <td className="px-4 py-2">
                      <span className="flex items-center gap-2">
                        <Badge tone="blue">
                          {control.extraction_method === "ai" ? "AI extracted" : "Spreadsheet"}
                        </Badge>
                        {control.requires_review && <Badge tone="yellow">Needs review</Badge>}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-2 rounded-md border border-border px-4 py-3 text-sm text-muted-foreground">
            No internal controls parsed yet.
          </p>
        )}
      </div>
    </div>
  );
}
