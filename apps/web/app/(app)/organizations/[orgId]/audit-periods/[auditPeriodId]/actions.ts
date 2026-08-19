"use server";

import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api";

export async function uploadDocument(
  organizationId: string,
  auditPeriodId: string,
  formData: FormData
) {
  const file = formData.get("file");
  const documentType = formData.get("document_type");
  if (!(file instanceof File) || file.size === 0 || !documentType) return;

  const response = await apiFetch(
    `/organizations/${organizationId}/audit-periods/${auditPeriodId}/documents`,
    { method: "POST", body: formData }
  );

  if (!response.ok) {
    throw new Error(`Failed to upload document (${response.status})`);
  }

  revalidatePath(`/organizations/${organizationId}/audit-periods/${auditPeriodId}`);
}
