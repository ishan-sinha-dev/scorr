import { apiFetch } from "@/lib/api";

// The browser can't attach the apps/api bearer token to a plain fetch()
// from a client component, so this proxies through the same authenticated
// apiFetch() every other mutation on this page already uses — same
// pattern as the findings export route.
export async function GET(
  _request: Request,
  {
    params,
  }: { params: Promise<{ orgId: string; auditPeriodId: string; documentId: string }> }
) {
  const { orgId, auditPeriodId, documentId } = await params;
  const response = await apiFetch(
    `/organizations/${orgId}/audit-periods/${auditPeriodId}/documents/${documentId}/analysis-status`
  );

  if (!response.ok) {
    return new Response("Failed to fetch analysis status", { status: response.status });
  }

  return Response.json(await response.json());
}
