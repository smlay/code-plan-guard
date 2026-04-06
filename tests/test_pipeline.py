"""§14 integration."""

from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def _minimal_plan(p: Path, **extra: str) -> None:
    base = (
        'plan_version: "0.1"\n'
        "changes:\n"
        f'  - file: {extra.get("file", "src/pkg/a.py")}\n'
        '    summary: "s"\n'
    )
    if "impacted" in extra:
        base += f"    impacted_files:\n      - {extra['impacted']}\n"
    base += (
        "global_analysis:\n  dependency_graph_summary: \"\"\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n"
    )
    p.write_text(base, encoding="utf-8")


def test_pass_when_impacted_covers_hop(tmp_repo: Path) -> None:
    plan = tmp_repo / "plan.yaml"
    _minimal_plan(
        plan,
        impacted="src/pkg/b.py",
    )
    r = validate_plan(
        plan,
        tmp_repo,
        write_artifacts=False,
        no_cache=True,
    )
    assert r.exit_code == 0, r.blockers


def test_b03_when_missing_impact(tmp_repo: Path) -> None:
    plan = tmp_repo / "plan.yaml"
    _minimal_plan(plan, impacted="src/pkg/b.py")  # missing a.py
    # a.py imports b - H includes a and b? a imports b -> one hop b. Does a import itself? pkg.a imports pkg.b
    # impacted only b - a is in H from b's reverse? aggregated is targets: b only from a.py
    # Actually one_hop from a.py is b.py only. H = {b}. D = {b}. OK pass.
    # Need case H = {a,b} - add second import in a.py
    (tmp_repo / "src" / "pkg" / "a.py").write_text(
        "from pkg import b\nimport pkg.a\n",
        encoding="utf-8",
    )
    r = validate_plan(plan, tmp_repo, write_artifacts=False, no_cache=True)
    assert any(b.id == "B03" for b in r.blockers)


def test_fatal_bad_plan_path(tmp_repo: Path) -> None:
    r = validate_plan(
        tmp_repo / "nope.yaml",
        tmp_repo,
        write_artifacts=False,
    )
    assert r.exit_code == 2
    assert r.fatal_message


def test_write_artifacts(tmp_repo: Path) -> None:
    plan = tmp_repo / "plan.yaml"
    _minimal_plan(plan, impacted="src/pkg/b.py")
    out = tmp_repo / "out"
    r = validate_plan(plan, tmp_repo, write_artifacts=True, out_dir=out, no_cache=True)
    assert (out / "expected_impact.json").is_file()
    assert (out / "reconciliation_report.json").is_file()
    assert (out / "guard_report.md").is_file()
    assert r.exit_code == 0
