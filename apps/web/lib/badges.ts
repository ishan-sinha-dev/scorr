export type CoverageStatus = "FULL" | "PARTIAL" | "NOT_COVERED" | "NOT_APPLICABLE" | "REQUIRES_REVIEW";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export const COVERAGE_LABELS: Record<CoverageStatus, string> = {
  FULL: "Full",
  PARTIAL: "Partial",
  NOT_COVERED: "Not covered",
  NOT_APPLICABLE: "Not applicable",
  REQUIRES_REVIEW: "Needs review",
};

export const COVERAGE_TONES: Record<CoverageStatus, "green" | "yellow" | "red" | "gray"> = {
  FULL: "green",
  PARTIAL: "yellow",
  NOT_COVERED: "red",
  NOT_APPLICABLE: "gray",
  REQUIRES_REVIEW: "red",
};

export const RISK_LABELS: Record<RiskLevel, string> = {
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
};

export const RISK_TONES: Record<RiskLevel, "green" | "yellow" | "red"> = {
  LOW: "green",
  MEDIUM: "yellow",
  HIGH: "red",
};
