"""v0.2 config extension behavior."""

from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def test_unknown_config_keys_ignored(tmp_repo: Path) -> None:
    cfg = tmp_repo / ".codeguard.yml"
    cfg.write_text(
        "unknown_root: 1\nrules:\n  style:\n    severity: warning\nunknown2:\n  a: b\n",
        encoding="utf-8",
    )
    plan = tmp_repo / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n  - file: src/pkg/a.py\n    summary: s\n    impacted_files:\n      - src/pkg/b.py\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    r = validate_plan(plan, tmp_repo, write_artifacts=False, no_cache=True)
    assert r.exit_code == 0

