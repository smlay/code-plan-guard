"""v0.2 features: overrides, base-ref diff, external signals."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def _plan(path: Path, impacted: str) -> None:
    path.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/pkg/a.py\n"
        '    summary: "s"\n'
        "    impacted_files:\n"
        f"      - {impacted}\n"
        "global_analysis:\n"
        "  dependency_graph_summary: \"\"\n"
        "risks_and_rollback:\n"
        "  - risk: r\n"
        "    mitigation: m\n",
        encoding="utf-8",
    )


def test_override_b03(tmp_repo: Path) -> None:
    # Force B03: include self-import creates extra H target not in D
    (tmp_repo / "src" / "pkg" / "a.py").write_text(
        "from pkg import b\nimport pkg.a\n", encoding="utf-8"
    )
    plan = tmp_repo / "plan.yaml"
    _plan(plan, "src/pkg/b.py")
    ov = tmp_repo / "override.txt"
    ov.write_text("code-plan-guard: override B03 reason=approved-by-human\n", encoding="utf-8")
    out = tmp_repo / "out"
    r = validate_plan(plan, tmp_repo, write_artifacts=True, out_dir=out, override_file=ov, no_cache=True)
    assert r.exit_code == 0
    assert r.overrides
    assert (out / "audit_overrides.json").is_file()


def test_base_ref_diff_warning(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "pkg" / "a.py").write_text("from pkg import b\n", encoding="utf-8")
    (repo / "src" / "pkg" / "b.py").write_text("X = 1\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "src" / "pkg" / "a.py").write_text("from pkg import b\nimport pkg.a\n", encoding="utf-8")
    plan = repo / "plan.yaml"
    _plan(plan, "src/pkg/b.py")
    r = validate_plan(
        plan,
        repo,
        write_artifacts=False,
        base_ref="HEAD",
        no_cache=True,
    )
    # HEAD..HEAD gives empty diff, pipeline should not crash and should return blocker due to missing impact
    assert any(b.id == "B03" for b in r.blockers)


def test_external_signal_reports(tmp_repo: Path) -> None:
    plan = tmp_repo / "plan.yaml"
    _plan(plan, "src/pkg/b.py")
    ruff = tmp_repo / "ruff.json"
    ruff.write_text(
        json.dumps(
            [
                {
                    "code": "F401",
                    "filename": "src/pkg/a.py",
                    "message": "unused import",
                }
            ]
        ),
        encoding="utf-8",
    )
    pyright = tmp_repo / "pyright.json"
    pyright.write_text(
        json.dumps(
            {
                "generalDiagnostics": [
                    {
                        "severity": "error",
                        "file": "src/pkg/a.py",
                        "message": "type error",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    r = validate_plan(
        plan,
        tmp_repo,
        write_artifacts=False,
        ruff_report=ruff,
        pyright_report=pyright,
        no_cache=True,
    )
    assert any(w.code == "W_RUFF_SIGNAL" for w in r.warnings)
    assert any(w.code == "W_PYRIGHT_SIGNAL" for w in r.warnings)


def test_llm_warning_hook_via_config(tmp_repo: Path) -> None:
    plan = tmp_repo / "plan.yaml"
    _plan(plan, "src/pkg/b.py")
    cfg = tmp_repo / ".codeguard.yml"
    cfg.write_text(
        "llm_review:\n  enabled: true\n",
        encoding="utf-8",
    )
    r = validate_plan(plan, tmp_repo, write_artifacts=False, no_cache=True)
    assert any(w.code == "W_LLM_REVIEW" for w in r.warnings)


def test_reconciliation_report_has_v02_fields(tmp_repo: Path) -> None:
    plan = tmp_repo / "plan.yaml"
    _plan(plan, "src/pkg/b.py")
    ov = tmp_repo / "override.txt"
    ov.write_text("code-plan-guard: override B03 reason=ok\n", encoding="utf-8")
    out = tmp_repo / "out"
    r = validate_plan(plan, tmp_repo, write_artifacts=True, out_dir=out, override_file=ov, no_cache=True)
    report = json.loads((out / "reconciliation_report.json").read_text(encoding="utf-8"))
    assert "overrides" in report
    assert "external_signals" in report
    assert "llm_warnings" in report
    assert "context" in report
