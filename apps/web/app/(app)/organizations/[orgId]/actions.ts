"use server";

import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api";

export async function createAuditPeriod(organizationId: string, formData: FormData) {
  const name = String(formData.get("name") ?? "").trim();
  const periodStart = String(formData.get("period_start") ?? "");
  const periodEnd = String(formData.get("period_end") ?? "");
  if (!name || !periodStart || !periodEnd) return;

  const response = await apiFetch(`/organizations/${organizationId}/audit-periods`, {
    method: "POST",
    body: JSON.stringify({ name, period_start: periodStart, period_end: periodEnd }),
  });

  if (!response.ok) {
    throw new Error(`Failed to create audit period (${response.status})`);
  }

  revalidatePath(`/organizations/${organizationId}`);
}

export async function deleteAuditPeriod(organizationId: string, auditPeriodId: string) {
  const response = await apiFetch(`/organizations/${organizationId}/audit-periods/${auditPeriodId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`Failed to delete audit period (${response.status})`);
  }

  revalidatePath(`/organizations/${organizationId}`);
}
