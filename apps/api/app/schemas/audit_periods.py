from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuditPeriodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def check_period_order(self) -> Self:
        # Mirrors the DB check constraint (audit_periods_period_order) so the
        # caller gets a clear 422 instead of a raw Postgres error.
        if self.period_end <= self.period_start:
            raise ValueError("period_end must be after period_start")
        return self


class AuditPeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    period_start: date
    period_end: date
    created_by: str
    created_at: datetime
