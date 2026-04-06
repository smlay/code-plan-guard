"""§6 Plan Schema (pydantic v2)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

# code-plan-guard-prd:§13.1 — reconciliation_notes length limit; exceed → B01.
_MAX_NOTES = 32768


class ReconciliationExceptionItem(BaseModel):
    to_file: str
    reason: str
    from_file: str | None = None


class ChangeItem(BaseModel):
    file: str
    summary: str
    impacted_files: list[str] | None = None
    reconciliation_exceptions: list[ReconciliationExceptionItem] | None = None
    reconciliation_notes: str | None = None
    new_deps: list[str] | None = None
    removed_deps: list[str] | None = None
    impacted_modules: list[str] | None = None

    @field_validator("reconciliation_notes")
    @classmethod
    def notes_len(cls, v: str | None) -> str | None:
        if v is not None and len(v) > _MAX_NOTES:
            raise ValueError(f"reconciliation_notes exceeds {_MAX_NOTES} characters")
        return v


class RiskRollbackItem(BaseModel):
    risk: str
    mitigation: str


class PlanModel(BaseModel):
    plan_version: Literal["0.1"]
    changes: Annotated[list[ChangeItem], Field(min_length=1)]
    global_analysis: dict[str, Any]
    risks_and_rollback: list[RiskRollbackItem]
