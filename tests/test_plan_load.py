"""§14.1 Markdown / IO."""

from pathlib import Path

import pytest

from code_plan_guard.plan_load import load_plan_raw


def test_md_no_block(tmp_path: Path) -> None:
    p = tmp_path / "p.md"
    p.write_text("# x\nno yaml\n", encoding="utf-8")
    d, m, k = load_plan_raw(p)
    assert d is None and m and k == "MD_PARSE"


def test_md_two_blocks(tmp_path: Path) -> None:
    p = tmp_path / "p.md"
    p.write_text(
        "```yaml\na: 1\n```\n\n```yaml\nb: 2\n```\n",
        encoding="utf-8",
    )
    d, m, k = load_plan_raw(p)
    assert d is None and k == "MD_PARSE"


def test_yaml_ok(tmp_path: Path) -> None:
    p = tmp_path / "p.yaml"
    p.write_text("x: 1\n", encoding="utf-8")
    d, m, k = load_plan_raw(p)
    assert d == {"x": 1} and m is None
