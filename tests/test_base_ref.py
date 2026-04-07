"""W_BASE_REF_INVALID."""

from pathlib import Path
import subprocess

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


def _git(cmd: list[str], cwd: Path) -> None:
    subprocess.run(["git", *cmd], cwd=cwd, check=True, capture_output=True, text=True)


def test_plan_scope_mismatch_warning_when_not_strict(tmp_path: Path) -> None:
    # Create a minimal git repo with a diff scope.
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "b.py").write_text("y = 2\n", encoding="utf-8")
    _git(["init"], tmp_path)
    _git(["add", "."], tmp_path)
    _git(["-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-m", "init"], tmp_path)

    # Make a diff that includes only b.py
    (tmp_path / "src" / "pkg" / "b.py").write_text("y = 3\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-m", "chg"], tmp_path)

    plan = tmp_path / "plan.yaml"
    # Plan mentions a.py (not in diff), diff contains b.py (not in plan) => mismatch both sides.
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/pkg/a.py\n"
        "    summary: s\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    r = validate_plan(plan, tmp_path, write_artifacts=False, no_cache=True, base_ref="HEAD~1")
    assert any(w.code == "W_PLAN_SCOPE_MISMATCH" for w in r.warnings)
    assert not any(b.id == "B09" for b in r.blockers)


def test_plan_scope_mismatch_blocker_when_strict(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "b.py").write_text("y = 2\n", encoding="utf-8")
    _git(["init"], tmp_path)
    _git(["add", "."], tmp_path)
    _git(["-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-m", "init"], tmp_path)

    (tmp_path / "src" / "pkg" / "b.py").write_text("y = 3\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-m", "chg"], tmp_path)

    plan = tmp_path / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/pkg/a.py\n"
        "    summary: s\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    r = validate_plan(
        plan,
        tmp_path,
        write_artifacts=False,
        no_cache=True,
        base_ref="HEAD~1",
        strict_plan_diff=True,
    )
    assert any(b.id == "B09" for b in r.blockers)
