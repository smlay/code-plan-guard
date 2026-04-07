from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def test_plan_quality_score_in_summary(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print('x')\n", encoding="utf-8")
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: a.py\n"
        "    summary: s\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    r = validate_plan(plan, tmp_path, write_artifacts=False, no_cache=True)
    assert "plan_quality_score" in r.summary

