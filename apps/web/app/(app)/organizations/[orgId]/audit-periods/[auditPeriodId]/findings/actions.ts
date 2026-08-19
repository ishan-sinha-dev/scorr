"use server";

import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api";

export async function computeFindings(organizationId: string, auditPeriodId: string) {
  const response = await apiFetch(
    `/organizations/${organizationId}/audit-periods/${auditPeriodId}/compute-findings`,
    { method: "POST" }
  );

  if (!response.ok) {
    throw new Error(`Failed to compute findings (${response.status})`);
  }

  revalidatePath(
    `/organizations/${organizationId}/audit-periods/${auditPeriodId}/findings`
  );
}

export async function reviewFinding(
  organizationId: string,
  auditPeriodId: string,
  findingId: string,
  formData: FormData
) {
  const decision = formData.get("decision");
  const overrideStatus = formData.get("override_coverage_status");
  const notes = formData.get("notes");

  const response = await apiFetch(
    `/organizations/${organizationId}/audit-periods/${auditPeriodId}/findings/${findingId}/review`,
    {
      method: "POST",
      body: JSON.stringify({
        decision,
        override_coverage_status: decision === "overridden" ? overrideStatus || null : null,
        notes: notes && String(notes).trim() ? notes : null,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to record review (${response.status})`);
  }

  revalidatePath(
    `/organizations/${organizationId}/audit-periods/${auditPeriodId}/findings`
  );
}
