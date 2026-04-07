import json
from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def test_rule_layers_written_to_report(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import missing_mod\n", encoding="utf-8")
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: a.py\n"
        "    summary: s\n"
        "global_analysis:\n  verification_steps: [\"python -m pytest -q\"]\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    _r = validate_plan(plan, tmp_path, write_artifacts=True, out_dir=out, no_cache=True)
    rep = json.loads((out / "reconciliation_report.json").read_text(encoding="utf-8"))
    assert "rule_layers" in rep["summary"]
    assert "heuristic" in rep["summary"]["rule_layers"]

