from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def _write_plan(p: Path) -> None:
    p.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/a.py\n"
        "    summary: s\n"
        "    impacted_files:\n"
        "      - src/b.py\n"
        "  - file: src/b.py\n"
        "    summary: s2\n"
        "    impacted_files:\n"
        "      - src/a.py\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )


def test_cycles_warning_when_enabled(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("import a\n", encoding="utf-8")
    plan = tmp_path / "plan.yaml"
    _write_plan(plan)
    (tmp_path / ".codeguard.yml").write_text(
        "rules:\n  cycles:\n    enabled: true\n    severity: warning\n",
        encoding="utf-8",
    )
    r = validate_plan(plan, tmp_path, write_artifacts=False, no_cache=True)
    assert any(w.code == "W_CYCLE_DETECTED" for w in r.warnings)


def test_cycles_blocker_when_severity_block(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("import a\n", encoding="utf-8")
    plan = tmp_path / "plan.yaml"
    _write_plan(plan)
    (tmp_path / ".codeguard.yml").write_text(
        "rules:\n  cycles:\n    enabled: true\n    severity: block\n",
        encoding="utf-8",
    )
    r = validate_plan(plan, tmp_path, write_artifacts=False, no_cache=True)
    assert any(b.id == "B06" for b in r.blockers)


def test_cycles_expand_one_hop_finds_cycle(tmp_path: Path) -> None:
    # Only a.py in changes; b.py is 1-hop target. Expand mode should include b.py and detect cycle.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("import a\n", encoding="utf-8")
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/a.py\n"
        "    summary: s\n"
        "    impacted_files:\n"
        "      - src/b.py\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    (tmp_path / ".codeguard.yml").write_text(
        "rules:\n  cycles:\n    enabled: true\n    severity: warning\n    expand_one_hop: true\n    max_extra_files: 10\n",
        encoding="utf-8",
    )
    r = validate_plan(plan, tmp_path, write_artifacts=False, no_cache=True)
    assert any(w.code == "W_CYCLE_DETECTED" for w in r.warnings)

