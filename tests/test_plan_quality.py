from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def test_plan_quality_warning(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x=1\n", encoding="utf-8")
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/a.py\n"
        "    summary: s\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    (tmp_path / ".codeguard.yml").write_text(
        "rules:\n  plan_quality:\n    enabled: true\n    severity: warning\n",
        encoding="utf-8",
    )
    r = validate_plan(plan, tmp_path, write_artifacts=False, no_cache=True)
    assert any(w.code == "W_PLAN_QUALITY" for w in r.warnings)


def test_plan_quality_blocker(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x=1\n", encoding="utf-8")
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/a.py\n"
        "    summary: s\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    (tmp_path / ".codeguard.yml").write_text(
        "rules:\n  plan_quality:\n    enabled: true\n    severity: block\n",
        encoding="utf-8",
    )
    r = validate_plan(plan, tmp_path, write_artifacts=False, no_cache=True)
    assert any(b.id == "B07" for b in r.blockers)

