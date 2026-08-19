from supabase import Client

from app.repositories import audit_periods as audit_periods_repo
from app.repositories import report_entities as report_entities_repo
from app.schemas.comparison import (
    AuditPeriodComparison,
    ControlChange,
    ControlComparison,
    EntityCounts,
)


def _diff_controls(
    from_controls: list[dict[str, str]], to_controls: list[dict[str, str]]
) -> ControlComparison:
    # control_code is nullable at the DB level (AI extraction isn't
    # guaranteed to find one) — a control with no code can't be matched
    # across periods, so it's excluded from the diff entirely rather than
    # matched on a NULL key (which would falsely pair unrelated controls).
    from_by_code = {c["control_code"]: c for c in from_controls if c.get("control_code")}
    to_by_code = {c["control_code"]: c for c in to_controls if c.get("control_code")}

    added = [
        {"control_code": code, "description": to_by_code[code]["description"]}
        for code in sorted(to_by_code.keys() - from_by_code.keys())
    ]
    removed = [
        {"control_code": code, "description": from_by_code[code]["description"]}
        for code in sorted(from_by_code.keys() - to_by_code.keys())
    ]
    changed = []
    unchanged_count = 0
    for code in sorted(from_by_code.keys() & to_by_code.keys()):
        from_description = from_by_code[code]["description"]
        to_description = to_by_code[code]["description"]
        if from_description != to_description:
            changed.append(
                ControlChange(
                    control_code=code,
                    description_from=from_description,
                    description_to=to_description,
                )
            )
        else:
            unchanged_count += 1

    return ControlComparison(
        added=added, removed=removed, changed=changed, unchanged_count=unchanged_count
    )


def compare_audit_periods(
    client: Client, *, from_audit_period_id: str, to_audit_period_id: str
) -> AuditPeriodComparison:
    from_period = audit_periods_repo.get_audit_period(client, audit_period_id=from_audit_period_id)
    to_period = audit_periods_repo.get_audit_period(client, audit_period_id=to_audit_period_id)

    from_controls = report_entities_repo.list_soc_controls(
        client, audit_period_id=from_audit_period_id
    )
    to_controls = report_entities_repo.list_soc_controls(
        client, audit_period_id=to_audit_period_id
    )

    def counts(period_id: str) -> EntityCounts:
        return EntityCounts(
            cuecs=len(report_entities_repo.list_cuecs(client, audit_period_id=period_id)),
            exceptions=len(
                report_entities_repo.list_exceptions(client, audit_period_id=period_id)
            ),
            subservice_organizations=len(
                report_entities_repo.list_subservice_organizations(
                    client, audit_period_id=period_id
                )
            ),
        )

    return AuditPeriodComparison(
        from_audit_period_id=from_audit_period_id,
        from_audit_period_name=from_period["name"],
        to_audit_period_id=to_audit_period_id,
        to_audit_period_name=to_period["name"],
        controls=_diff_controls(from_controls, to_controls),
        entity_counts_from=counts(from_audit_period_id),
        entity_counts_to=counts(to_audit_period_id),
    )
