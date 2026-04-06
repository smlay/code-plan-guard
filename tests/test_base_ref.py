"""W_BASE_REF_INVALID."""

from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def test_invalid_base_ref_warning(tmp_path: Path, monkeypatch) -> None:
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n  - file: a.py\n    summary: s\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")
    r = validate_plan(
        plan,
        tmp_path,
        write_artifacts=False,
        no_cache=True,
        base_ref="refs/heads/__nonexistent_ref_zz__",
    )
    assert any(w.code == "W_BASE_REF_INVALID" for w in r.warnings)
