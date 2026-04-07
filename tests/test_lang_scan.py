from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def test_lang_scan_warning_only(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.js").write_text("import x from './b'\n", encoding="utf-8")
    (tmp_path / "src" / "b.js").write_text("export const x = 1\n", encoding="utf-8")
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/a.js\n"
        "    summary: s\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    (tmp_path / ".codeguard.yml").write_text("rules:\n  languages:\n    enabled: true\n", encoding="utf-8")
    r = validate_plan(plan, tmp_path, write_artifacts=False, no_cache=True)
    assert any(w.code == "W_LANG_IMPORT" for w in r.warnings)
    assert r.exit_code in (0, 1)

