import json
from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def test_expected_impact_has_language_truth(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.js").write_text("import './b'\n", encoding="utf-8")
    (tmp_path / "src" / "b.js").write_text("export const x = 1\n", encoding="utf-8")
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/a.js\n"
        "    summary: s\n"
        "global_analysis:\n"
        "  verification_steps:\n"
        "    - run: echo ok\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    r = validate_plan(plan, tmp_path, write_artifacts=True, out_dir=out, no_cache=True)
    assert r.exit_code in (0, 1)
    ei = json.loads((out / "expected_impact.json").read_text(encoding="utf-8"))
    assert "language_truth" in ei
    assert "per_file" in ei["language_truth"]

