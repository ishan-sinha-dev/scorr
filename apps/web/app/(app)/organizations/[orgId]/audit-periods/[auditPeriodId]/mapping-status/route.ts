import { apiFetch } from "@/lib/api";

// Same proxy pattern as the sibling analysis-status route — the browser
// can't attach the apps/api bearer token itself.
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ orgId: string; auditPeriodId: string }> }
) {
  const { orgId, auditPeriodId } = await params;
  const response = await apiFetch(
    `/organizations/${orgId}/audit-periods/${auditPeriodId}/mapping-status`
  );

  if (!response.ok) {
    return new Response("Failed to fetch mapping status", { status: response.status });
  }

  return Response.json(await response.json());
}
