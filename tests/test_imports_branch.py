"""§8.2.2 if False / TYPE_CHECKING."""

from pathlib import Path

from code_plan_guard.config import GuardConfig
from code_plan_guard.imports import analyze_py_file


def test_skip_type_checking_skips_local_module(tmp_path: Path) -> None:
    cfg = GuardConfig(
        skip_imports_in_false_branch=True,
        skip_imports_in_type_checking_if=True,
        src_roots=["."],
    )
    (tmp_path / "foo.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "bar.py").write_text("Y = 1\n", encoding="utf-8")
    (tmp_path / "m.py").write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    import foo\n"
        "import bar\n",
        encoding="utf-8",
    )
    edges, _u, _w = analyze_py_file(tmp_path, "m.py", cfg)
    targets = {t for _f, t in edges}
    assert "bar.py" in targets or any(t.endswith("bar.py") for t in targets)
    assert not any(t.endswith("foo.py") for t in targets)


def test_if_false_orelse_imported(tmp_path: Path) -> None:
    cfg = GuardConfig(skip_imports_in_false_branch=True, src_roots=["."])
    (tmp_path / "bar.py").write_text("Y = 1\n", encoding="utf-8")
    (tmp_path / "m.py").write_text(
        "if False:\n"
        "    import json\n"
        "else:\n"
        "    import bar\n",
        encoding="utf-8",
    )
    edges, _u, _w = analyze_py_file(tmp_path, "m.py", cfg)
    targets = {t for _f, t in edges}
    assert any(t.endswith("bar.py") for t in targets)
