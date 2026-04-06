"""§9 B03."""

from pathlib import Path

from code_plan_guard.reconcile import reconcile
from code_plan_guard.schema import ChangeItem, PlanModel, RiskRollbackItem


def test_b03_missing_impact(tmp_path: Path) -> None:
    plan = PlanModel(
        plan_version="0.1",
        changes=[
            ChangeItem(
                file="x.py",
                summary="s",
                impacted_files=["src/pkg/b.py"],
            )
        ],
        global_analysis={},
        risks_and_rollback=[RiskRollbackItem(risk="r", mitigation="m")],
    )
    agg = ["src/pkg/a.py", "src/pkg/b.py"]
    edges = [("src/pkg/x.py", "src/pkg/a.py"), ("src/pkg/x.py", "src/pkg/b.py")]
    rows, missing, summ = reconcile(tmp_path, plan, agg, edges, [])
    assert "src/pkg/a.py" in missing
    assert "src/pkg/b.py" not in missing
