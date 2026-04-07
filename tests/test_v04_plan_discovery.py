import os
from pathlib import Path

from code_plan_guard.pipeline import validate_plan


def test_plan_auto_error_includes_tried_sources(monkeypatch, tmp_path: Path) -> None:
    # Ensure no plan files exist.
    (tmp_path / "src").mkdir()
    monkeypatch.setenv("GITHUB_PR_NUMBER", "1")
    monkeypatch.setenv("GITHUB_REPOSITORY", "x/y")
    r = validate_plan("auto", tmp_path, write_artifacts=False, no_cache=True)
    assert r.exit_code == 2
    assert r.error_kind == "PLAN_NOT_FOUND"
    assert r.fatal_message
    assert "已尝试" in r.fatal_message

