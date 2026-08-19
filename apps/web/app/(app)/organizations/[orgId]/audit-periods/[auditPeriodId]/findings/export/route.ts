import { apiFetch } from "@/lib/api";

// The browser can't attach the apps/api bearer token to a plain <a href>
// download, so this route re-uses the same authenticated apiFetch() every
// other mutation on this page already uses, and streams the xlsx back.
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ orgId: string; auditPeriodId: string }> }
) {
  const { orgId, auditPeriodId } = await params;
  const response = await apiFetch(
    `/organizations/${orgId}/audit-periods/${auditPeriodId}/findings/export.xlsx`
  );

  if (!response.ok) {
    return new Response("Failed to export findings", { status: response.status });
  }

  return new Response(response.body, {
    headers: {
      "Content-Type":
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": 'attachment; filename="findings.xlsx"',
    },
  });
}
