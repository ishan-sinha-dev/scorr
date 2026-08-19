from pydantic import BaseModel


class ControlChange(BaseModel):
    control_code: str
    description_from: str
    description_to: str


class ControlComparison(BaseModel):
    added: list[dict[str, str]]  # [{"control_code": ..., "description": ...}]
    removed: list[dict[str, str]]
    changed: list[ControlChange]
    unchanged_count: int


class EntityCounts(BaseModel):
    cuecs: int
    exceptions: int
    subservice_organizations: int


class AuditPeriodComparison(BaseModel):
    """Scoped comparison (Phase 12): SOC controls are diffed item-by-item
    by control_code, a stable identifier (e.g. "CC6.1"). CUECs, exceptions,
    and subservice organizations have no equivalent stable identifier
    across periods — extracted freeform per report — so they're reported
    as counts per period only, not matched item-to-item. A full semantic
    diff of those would need its own AI matching pass; documented as a
    known limitation rather than built as a guess.
    """

    from_audit_period_id: str
    from_audit_period_name: str
    to_audit_period_id: str
    to_audit_period_name: str
    controls: ControlComparison
    entity_counts_from: EntityCounts
    entity_counts_to: EntityCounts
