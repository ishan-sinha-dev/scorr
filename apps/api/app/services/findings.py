from collections import defaultdict
from typing import Any

from supabase import Client

from app.repositories import control_mappings as control_mappings_repo
from app.repositories import documents as documents_repo
from app.repositories import finding_reviews as finding_reviews_repo
from app.repositories import findings as findings_repo
from app.repositories import internal_controls as internal_controls_repo
from app.repositories import report_entities as report_entities_repo
from app.schemas.finding_reviews import FindingReviewOut
from app.schemas.findings import CoverageStatus, EvidenceKind, EvidenceRef, FindingOut, RiskLevel
from app.services import audit_log


def derive_coverage(
    *,
    mapping_attempted: bool,
    mapping_count: int,
    confirmed_count: int,
    has_linked_cuec: bool,
    has_linked_exception: bool,
) -> CoverageStatus | None:
    """Pure, deterministic — the LLM interprets evidence during Phase 7's
    mapping pass; it never decides coverage status. None means mapping
    hasn't been attempted for this control yet, so the caller persists no
    finding row at all rather than inventing a 6th "unknown" enum value.

    NOT_APPLICABLE is not reachable from this function (no control-category
    field was modeled — YAGNI) — stays human-override-only until Phase 9.
    """
    if not mapping_attempted:
        return None
    if mapping_count == 0:
        return "NOT_COVERED"
    if confirmed_count == 0:
        return "REQUIRES_REVIEW"
    if has_linked_exception or has_linked_cuec:
        return "PARTIAL"
    return "FULL"


def derive_risk_level(status: CoverageStatus) -> RiskLevel:
    """Deterministic — spec: "Risk should be calculated from structured
    facts rather than arbitrary LLM opinions." coverage_status already
    encodes whether any SOC control was found, whether mapping confirmation
    succeeded, and whether a CUEC/exception qualifies the match, so risk is
    derived from that single upstream fact rather than re-deriving from
    raw mapping rows. Kept as one pure function (not a rules table/UI) —
    "configurable" here means "edit this function," which is enough until
    real inputs beyond coverage are actually needed.
    """
    if status in ("NOT_COVERED", "REQUIRES_REVIEW"):
        return "HIGH"
    if status == "PARTIAL":
        return "MEDIUM"
    return "LOW"  # FULL, NOT_APPLICABLE


def _build_reasoning(status: CoverageStatus, mappings: list[dict[str, Any]]) -> str:
    """Templated deterministically from relevance_summary + counts — not
    another LLM call (spec: LLM interprets, it doesn't decide app state)."""
    if status == "NOT_COVERED":
        return "No candidate SOC control was found for this internal control."
    if status == "REQUIRES_REVIEW":
        return (
            f"{len(mappings)} candidate SOC control(s) were found by similarity search, "
            "but AI relevance confirmation did not complete successfully — needs manual review."
        )
    best = max(mappings, key=lambda m: m["similarity_score"])
    summary = str(best["relevance_summary"])
    if status == "PARTIAL":
        return f"{summary} Coverage is partial: a linked CUEC or exception qualifies it."
    return summary


def compute_findings(
    client: Client, *, organization_id: str, audit_period_id: str, actor_user_id: str
) -> int:
    """Recomputes and upserts one finding per internal control in the
    period. Synchronous — pure Python + Postgres reads, no external calls
    — so no Celery task. Returns the number of findings written; a control
    with no mapping attempt yet is skipped, not written as a row.
    """
    controls = internal_controls_repo.list_internal_controls(
        client, audit_period_id=audit_period_id
    )
    mappings = control_mappings_repo.list_control_mappings(client, audit_period_id=audit_period_id)
    mapping_ids = [m["id"] for m in mappings]
    cuec_links = control_mappings_repo.list_mapping_cuecs(client, control_mapping_ids=mapping_ids)
    exception_links = control_mappings_repo.list_mapping_exceptions(
        client, control_mapping_ids=mapping_ids
    )
    cuec_mapping_ids = {link["control_mapping_id"] for link in cuec_links}
    exception_mapping_ids = {link["control_mapping_id"] for link in exception_links}

    mappings_by_control: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for mapping in mappings:
        mappings_by_control[mapping["internal_control_id"]].append(mapping)

    written = 0
    for control in controls:
        control_mappings_list = mappings_by_control.get(control["id"], [])
        confirmed = [m for m in control_mappings_list if not m["requires_review"]]
        has_cuec = any(m["id"] in cuec_mapping_ids for m in confirmed)
        has_exception = any(m["id"] in exception_mapping_ids for m in confirmed)

        status = derive_coverage(
            mapping_attempted=control.get("mapping_attempted_at") is not None,
            mapping_count=len(control_mappings_list),
            confirmed_count=len(confirmed),
            has_linked_cuec=has_cuec,
            has_linked_exception=has_exception,
        )
        if status is None:
            continue

        best = max(control_mappings_list, key=lambda m: m["similarity_score"], default=None)
        findings_repo.upsert_finding(
            client,
            organization_id=organization_id,
            audit_period_id=audit_period_id,
            internal_control_id=control["id"],
            control_mapping_id=str(best["id"]) if best else None,
            coverage_status=status,
            risk_level=derive_risk_level(status),
            confidence=float(best["confidence"]) if best else 0.0,
            reasoning=_build_reasoning(status, control_mappings_list),
        )
        written += 1

    audit_log.record(
        client,
        actor_user_id=actor_user_id,
        action="audit_period.findings_computed",
        entity_type="audit_period",
        entity_id=audit_period_id,
        organization_id=organization_id,
        metadata={"finding_count": written},
    )
    return written


def _evidence_ref(
    entity: dict[str, Any],
    *,
    kind: EvidenceKind,
    client: Client,
    documents_by_id: dict[str, dict[str, Any]],
) -> EvidenceRef | None:
    document = documents_by_id.get(entity["document_id"])
    if document is None:
        return None
    view_url = documents_repo.create_signed_url(client, storage_path=document["storage_path"])
    return EvidenceRef(
        kind=kind,
        document_id=document["id"],
        file_name=document["file_name"],
        page_number=entity["page_number"],
        excerpt=entity["excerpt"],
        view_url=view_url,
    )


def list_findings(client: Client, *, audit_period_id: str) -> list[FindingOut]:
    """Evidence is assembled here, at read time, by joining
    findings -> control_mappings -> soc_controls (+ the two junction
    tables) — nothing is duplicated into a separate evidence table.
    """
    finding_rows = findings_repo.list_findings(client, audit_period_id=audit_period_id)
    if not finding_rows:
        return []

    controls_by_id = {
        c["id"]: c
        for c in internal_controls_repo.list_internal_controls(
            client, audit_period_id=audit_period_id
        )
    }
    mappings_by_id = {
        m["id"]: m
        for m in control_mappings_repo.list_control_mappings(
            client, audit_period_id=audit_period_id
        )
    }
    soc_controls_by_id = {
        c["id"]: c
        for c in report_entities_repo.list_soc_controls(client, audit_period_id=audit_period_id)
    }
    cuecs_by_id = {
        c["id"]: c
        for c in report_entities_repo.list_cuecs(client, audit_period_id=audit_period_id)
    }
    exceptions_by_id = {
        c["id"]: c
        for c in report_entities_repo.list_exceptions(client, audit_period_id=audit_period_id)
    }
    documents_by_id = {
        d["id"]: d for d in documents_repo.list_documents(client, audit_period_id=audit_period_id)
    }

    mapping_ids_needed = [
        row["control_mapping_id"] for row in finding_rows if row["control_mapping_id"]
    ]
    cuec_links = control_mappings_repo.list_mapping_cuecs(
        client, control_mapping_ids=mapping_ids_needed
    )
    exception_links = control_mappings_repo.list_mapping_exceptions(
        client, control_mapping_ids=mapping_ids_needed
    )

    # Latest review per finding (Phase 9). Reviews are append-only, so
    # "latest" is just the last row per finding_id once ordered by
    # created_at — no separate "current review" column/table needed.
    review_rows = finding_reviews_repo.list_reviews(
        client, finding_ids=[row["id"] for row in finding_rows]
    )
    latest_review_by_finding: dict[str, dict[str, Any]] = {}
    for review_row in review_rows:
        latest_review_by_finding[review_row["finding_id"]] = review_row
    cuec_ids_by_mapping: dict[str, list[str]] = defaultdict(list)
    for link in cuec_links:
        cuec_ids_by_mapping[link["control_mapping_id"]].append(link["cuec_id"])
    exception_ids_by_mapping: dict[str, list[str]] = defaultdict(list)
    for link in exception_links:
        exception_ids_by_mapping[link["control_mapping_id"]].append(link["exception_id"])

    results: list[FindingOut] = []
    for row in finding_rows:
        control = controls_by_id.get(row["internal_control_id"])
        if control is None:
            continue

        evidence: list[EvidenceRef] = []
        mapping = (
            mappings_by_id.get(row["control_mapping_id"]) if row["control_mapping_id"] else None
        )
        if mapping is not None:
            soc_control = soc_controls_by_id.get(mapping["soc_control_id"])
            if soc_control is not None:
                ref = _evidence_ref(
                    soc_control, kind="soc_control", client=client, documents_by_id=documents_by_id
                )
                if ref is not None:
                    evidence.append(ref)
            for cuec_id in cuec_ids_by_mapping.get(mapping["id"], []):
                cuec = cuecs_by_id.get(cuec_id)
                if cuec is not None:
                    ref = _evidence_ref(
                        cuec, kind="cuec", client=client, documents_by_id=documents_by_id
                    )
                    if ref is not None:
                        evidence.append(ref)
            for exception_id in exception_ids_by_mapping.get(mapping["id"], []):
                exception = exceptions_by_id.get(exception_id)
                if exception is not None:
                    ref = _evidence_ref(
                        exception, kind="exception", client=client, documents_by_id=documents_by_id
                    )
                    if ref is not None:
                        evidence.append(ref)

        latest_review_row = latest_review_by_finding.get(row["id"])
        latest_review = (
            FindingReviewOut.model_validate(latest_review_row) if latest_review_row else None
        )
        effective_status: CoverageStatus = row["coverage_status"]
        if latest_review is not None and latest_review.decision == "overridden":
            # The DB check constraint (finding_reviews_override_status_shape)
            # guarantees this is set whenever decision='overridden'.
            assert latest_review.override_coverage_status is not None
            effective_status = latest_review.override_coverage_status

        results.append(
            FindingOut(
                id=row["id"],
                internal_control_id=control["id"],
                internal_control_code=control.get("control_id"),
                internal_control_description=control["description"],
                coverage_status=row["coverage_status"],
                confidence=row["confidence"],
                reasoning=row["reasoning"],
                created_at=row["created_at"],
                evidence=evidence,
                effective_coverage_status=effective_status,
                latest_review=latest_review,
                risk_level=row["risk_level"] or derive_risk_level(row["coverage_status"]),
                effective_risk_level=derive_risk_level(effective_status),
            )
        )
    return results
