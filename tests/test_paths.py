"""§7 paths."""

import os
from pathlib import Path

from code_plan_guard.paths import is_b01_empty_or_absolute, normalize_under_repo


def test_normalize_ok(tmp_path: Path) -> None:
    f = tmp_path / "a.py"
    f.write_text("x=1", encoding="utf-8")
    r, e = normalize_under_repo(tmp_path, "a.py", must_be_file=True)
    assert r == "a.py" and e is None


def test_b02_not_file(tmp_path: Path) -> None:
    (tmp_path / "d").mkdir()
    r, e = normalize_under_repo(tmp_path, "d", must_be_file=True)
    assert r is None


def test_b01_absolute() -> None:
    p = os.path.abspath(os.path.join(os.sep, "abs_guard_test_file.py"))
    assert is_b01_empty_or_absolute(p) is True
