import Link from "next/link";
import { notFound } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { uploadDocument } from "./actions";

type Document = {
  id: string;
  document_type: "soc_report" | "bridge_letter" | "internal_control_framework";
  file_name: string;
  created_at: string;
  view_url: string;
};

const DOCUMENT_TYPE_LABELS: Record<Document["document_type"], string> = {
  soc_report: "SOC report",
  bridge_letter: "Bridge letter",
  internal_control_framework: "Internal control framework",
};

export default async function AuditPeriodDocumentsPage({
  params,
}: {
  params: Promise<{ orgId: string; auditPeriodId: string }>;
}) {
  const { orgId, auditPeriodId } = await params;
  const response = await apiFetch(
    `/organizations/${orgId}/audit-periods/${auditPeriodId}/documents`
  );

  if (response.status === 403 || response.status === 404) {
    notFound();
  }

  const documents: Document[] = response.ok ? await response.json() : [];
  const uploadForThisPeriod = uploadDocument.bind(null, orgId, auditPeriodId);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <Link
          href={`/organizations/${orgId}`}
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Audit periods
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-foreground">Documents</h1>
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
            </span>
            <a
              href={doc.view_url}
              target="_blank"
              rel="noreferrer"
              className="text-primary hover:underline"
            >
              View
            </a>
          </li>
        ))}
        {documents.length === 0 && (
          <li className="px-4 py-3 text-sm text-muted-foreground">No documents yet.</li>
        )}
      </ul>
    </div>
  );
}
