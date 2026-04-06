"""W_STAR_IMPORT."""

from pathlib import Path

from code_plan_guard.config import GuardConfig
from code_plan_guard.imports import analyze_py_file


def test_star_import_warning(tmp_path: Path) -> None:
    cfg = GuardConfig(src_roots=["."])
    (tmp_path / "m.py").write_text("from os import *\n", encoding="utf-8")
    _e, _u, w = analyze_py_file(tmp_path, "m.py", cfg)
    assert any(x["code"] == "W_STAR_IMPORT" for x in w)
