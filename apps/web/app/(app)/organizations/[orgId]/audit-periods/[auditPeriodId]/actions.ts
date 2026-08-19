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

export async function analyzeDocument(
  organizationId: string,
  auditPeriodId: string,
  documentId: string
) {
  const response = await apiFetch(
    `/organizations/${organizationId}/audit-periods/${auditPeriodId}/documents/${documentId}/analyze`,
    { method: "POST" }
  );

  if (!response.ok) {
    throw new Error(`Failed to queue analysis (${response.status})`);
  }

  revalidatePath(`/organizations/${organizationId}/audit-periods/${auditPeriodId}`);
}

export async function parseInternalControls(
  organizationId: string,
  auditPeriodId: string,
  documentId: string
) {
  const response = await apiFetch(
    `/organizations/${organizationId}/audit-periods/${auditPeriodId}/documents/${documentId}/parse-internal-controls`,
    { method: "POST" }
  );

  if (!response.ok) {
    throw new Error(`Failed to parse internal controls (${response.status})`);
  }

  revalidatePath(`/organizations/${organizationId}/audit-periods/${auditPeriodId}`);
}

export async function mapControls(organizationId: string, auditPeriodId: string) {
  const response = await apiFetch(
    `/organizations/${organizationId}/audit-periods/${auditPeriodId}/map-controls`,
    { method: "POST" }
  );

  if (!response.ok) {
    throw new Error(`Failed to queue control mapping (${response.status})`);
  }

  revalidatePath(`/organizations/${organizationId}/audit-periods/${auditPeriodId}`);
}

export async function carryForwardControls(
  organizationId: string,
  auditPeriodId: string,
  formData: FormData
) {
  const fromAuditPeriodId = formData.get("from_audit_period_id");
  if (!fromAuditPeriodId) return;

  const response = await apiFetch(
    `/organizations/${organizationId}/audit-periods/${auditPeriodId}/carry-forward-controls` +
      `?from_audit_period_id=${encodeURIComponent(String(fromAuditPeriodId))}`,
    { method: "POST" }
  );

  if (!response.ok) {
    throw new Error(`Failed to carry forward controls (${response.status})`);
  }

  revalidatePath(`/organizations/${organizationId}/audit-periods/${auditPeriodId}`);
}
