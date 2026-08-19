"use client";

import { Eye, EyeOff } from "lucide-react";
import { Fragment, useMemo, useState } from "react";

import { Badge } from "@/components/badge";
import {
  COVERAGE_LABELS,
  COVERAGE_TONES,
  type CoverageStatus,
  RISK_LABELS,
  RISK_TONES,
  type RiskLevel,
} from "@/lib/badges";

type EvidenceKind = "soc_control" | "cuec" | "exception";

type Evidence = {
  kind: EvidenceKind;
  document_id: string;
  file_name: string;
  page_number: number;
  excerpt: string;
  view_url: string;
};

type Review = {
  id: string;
  decision: "approved" | "overridden" | "requires_reanalysis";
  override_coverage_status: CoverageStatus | null;
  notes: string | null;
  created_at: string;
};

export type Finding = {
  id: string;
  internal_control_id: string;
  internal_control_code: string | null;
  internal_control_description: string;
  coverage_status: CoverageStatus;
  effective_coverage_status: CoverageStatus;
  risk_level: RiskLevel;
  effective_risk_level: RiskLevel;
  confidence: number;
  reasoning: string;
  evidence: Evidence[];
  latest_review: Review | null;
};

const EVIDENCE_KIND_LABELS: Record<EvidenceKind, string> = {
  soc_control: "SOC control",
  cuec: "CUEC",
  exception: "Exception",
};

const COVERAGE_OPTIONS: CoverageStatus[] = [
  "FULL",
  "PARTIAL",
  "NOT_COVERED",
  "NOT_APPLICABLE",
  "REQUIRES_REVIEW",
];
const RISK_OPTIONS: RiskLevel[] = ["LOW", "MEDIUM", "HIGH"];

export function FindingsTable({
  findings,
  reviewAction,
}: {
  findings: Finding[];
  reviewAction: (findingId: string, formData: FormData) => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<CoverageStatus | "ALL">("ALL");
  const [riskFilter, setRiskFilter] = useState<RiskLevel | "ALL">("ALL");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    return findings.filter((finding) => {
      if (statusFilter !== "ALL" && finding.effective_coverage_status !== statusFilter) {
        return false;
      }
      if (riskFilter !== "ALL" && finding.effective_risk_level !== riskFilter) {
        return false;
      }
      if (search.trim()) {
        const query = search.toLowerCase();
        const haystack =
          `${finding.internal_control_code ?? ""} ${finding.internal_control_description}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }, [findings, search, statusFilter, riskFilter]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search controls..."
          className="w-64 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
        />
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as CoverageStatus | "ALL")}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
        >
          <option value="ALL">All statuses</option>
          {COVERAGE_OPTIONS.map((status) => (
            <option key={status} value={status}>
              {COVERAGE_LABELS[status]}
            </option>
          ))}
        </select>
        <select
          value={riskFilter}
          onChange={(event) => setRiskFilter(event.target.value as RiskLevel | "ALL")}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
        >
          <option value="ALL">All risk levels</option>
          {RISK_OPTIONS.map((risk) => (
            <option key={risk} value={risk}>
              {RISK_LABELS[risk]}
            </option>
          ))}
        </select>
        <span className="text-sm text-muted-foreground">{filtered.length} items</span>
      </div>

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-muted-foreground">
              <th className="px-4 py-2 font-medium">Control ID</th>
              <th className="px-4 py-2 font-medium">Description</th>
              <th className="px-4 py-2 font-medium">Coverage</th>
              <th className="px-4 py-2 font-medium">Risk</th>
              <th className="px-4 py-2 font-medium">Confidence</th>
              <th className="px-4 py-2 font-medium">Reviewed</th>
              <th className="px-4 py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filtered.map((finding) => (
              <Fragment key={finding.id}>
                <tr className="text-foreground">
                  <td className="px-4 py-3 font-medium">
                    {finding.internal_control_code ?? "—"}
                  </td>
                  <td className="max-w-sm truncate px-4 py-3">
                    {finding.internal_control_description}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={COVERAGE_TONES[finding.effective_coverage_status]}>
                      {COVERAGE_LABELS[finding.effective_coverage_status]}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={RISK_TONES[finding.effective_risk_level]}>
                      {RISK_LABELS[finding.effective_risk_level]}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">{Math.round(finding.confidence * 100)}%</td>
                  <td className="px-4 py-3">
                    {finding.latest_review ? (
                      <Badge tone="green">Yes</Badge>
                    ) : (
                      <Badge tone="gray">No</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => setExpandedId(expandedId === finding.id ? null : finding.id)}
                      className="text-primary hover:underline"
                      title={expandedId === finding.id ? "Hide detail" : "View detail"}
                    >
                      {expandedId === finding.id ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </td>
                </tr>
                {expandedId === finding.id && (
                  <tr>
                    <td colSpan={7} className="border-t border-border bg-muted/30 px-4 py-4">
                      <div className="space-y-4">
                        <p className="text-sm text-muted-foreground">{finding.reasoning}</p>

                        {finding.evidence.length > 0 && (
                          <ul className="space-y-1">
                            {finding.evidence.map((evidence, index) => (
                              <li key={`${evidence.document_id}-${index}`} className="text-xs">
                                <span className="mr-2 rounded-full bg-muted px-2 py-0.5 text-muted-foreground">
                                  {EVIDENCE_KIND_LABELS[evidence.kind]}
                                </span>
                                <a
                                  href={evidence.view_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-primary hover:underline"
                                >
                                  {evidence.file_name} · Page {evidence.page_number}
                                </a>
                                <span className="ml-2 text-muted-foreground">
                                  {evidence.excerpt}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}

                        {finding.latest_review && (
                          <p className="text-xs text-muted-foreground">
                            Last review: {finding.latest_review.decision}
                            {finding.latest_review.override_coverage_status &&
                              ` → ${COVERAGE_LABELS[finding.latest_review.override_coverage_status]}`}
                            {finding.latest_review.notes &&
                              ` — "${finding.latest_review.notes}"`}
                          </p>
                        )}

                        <div className="flex flex-wrap items-end gap-4 border-t border-border pt-3">
                          <form action={reviewAction.bind(null, finding.id)}>
                            <input type="hidden" name="decision" value="approved" />
                            <button
                              type="submit"
                              className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                            >
                              Approve
                            </button>
                          </form>
                          <form action={reviewAction.bind(null, finding.id)}>
                            <input type="hidden" name="decision" value="requires_reanalysis" />
                            <button
                              type="submit"
                              className="rounded-md border border-input px-3 py-1.5 text-xs font-medium text-foreground"
                            >
                              Request re-analysis
                            </button>
                          </form>
                          <form
                            action={reviewAction.bind(null, finding.id)}
                            className="flex items-end gap-2"
                          >
                            <input type="hidden" name="decision" value="overridden" />
                            <div className="flex flex-col gap-1">
                              <label className="text-xs text-muted-foreground">
                                Override to
                              </label>
                              <select
                                name="override_coverage_status"
                                className="rounded-md border border-input bg-background px-2 py-1.5 text-xs"
                              >
                                {COVERAGE_OPTIONS.map((status) => (
                                  <option key={status} value={status}>
                                    {COVERAGE_LABELS[status]}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <input
                              name="notes"
                              placeholder="Reason (optional)"
                              className="rounded-md border border-input bg-background px-2 py-1.5 text-xs"
                            />
                            <button
                              type="submit"
                              className="rounded-md border border-input px-3 py-1.5 text-xs font-medium text-foreground"
                            >
                              Override
                            </button>
                          </form>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-sm text-muted-foreground">
                  No findings match your filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
