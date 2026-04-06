"""§6 Schema B01/B04."""

import pytest
from pydantic import ValidationError

from code_plan_guard.schema import PlanModel


def test_b04_empty_changes() -> None:
    raw = {
        "plan_version": "0.1",
        "changes": [],
        "global_analysis": {},
        "risks_and_rollback": [{"risk": "r", "mitigation": "m"}],
    }
    with pytest.raises(ValidationError) as ei:
        PlanModel.model_validate(raw)
    errs = ei.value.errors()
    assert any(x.get("type") == "too_short" for x in errs)


def test_b01_bad_version() -> None:
    raw = {
        "plan_version": "0.2",
        "changes": [{"file": "a.py", "summary": "s"}],
        "global_analysis": {},
        "risks_and_rollback": [{"risk": "r", "mitigation": "m"}],
    }
    with pytest.raises(ValidationError):
        PlanModel.model_validate(raw)
