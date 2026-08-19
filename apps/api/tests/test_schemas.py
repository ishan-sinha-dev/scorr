import pytest
from pydantic import ValidationError

from app.schemas.audit_periods import AuditPeriodCreate


def test_audit_period_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError):
        AuditPeriodCreate(name="FY2026", period_start="2026-12-31", period_end="2026-01-01")  # type: ignore[arg-type]


def test_audit_period_rejects_equal_dates() -> None:
    with pytest.raises(ValidationError):
        AuditPeriodCreate(name="FY2026", period_start="2026-01-01", period_end="2026-01-01")  # type: ignore[arg-type]


def test_audit_period_accepts_valid_range() -> None:
    period = AuditPeriodCreate(
        name="FY2026", period_start="2026-01-01", period_end="2026-12-31"  # type: ignore[arg-type]
    )
    assert period.period_end > period.period_start
