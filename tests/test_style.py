"""§10.2 B05."""

from pathlib import Path

from code_plan_guard.config import GuardConfig
from code_plan_guard.style import analyze_style


def test_docstring_only_function_zero_lines(tmp_path: Path) -> None:
    cfg = GuardConfig(count_docstrings=False, style_severity="warning", max_function_lines=5)
    (tmp_path / "x.py").write_text(
        'def f():\n    """d"""\n',
        encoding="utf-8",
    )
    block, warn = analyze_style(tmp_path, ["x.py"], cfg)
    assert not block
    assert not warn


def test_function_too_long_warning(tmp_path: Path) -> None:
    cfg = GuardConfig(
        count_docstrings=False,
        style_severity="warning",
        max_function_lines=2,
        max_class_lines=600,
    )
    body = "\n".join(["    x = 1"] * 5)
    (tmp_path / "x.py").write_text(f"def f():\n{body}\n", encoding="utf-8")
    block, warn = analyze_style(tmp_path, ["x.py"], cfg)
    assert not block
    assert any(w["code"] == "W_FUNCTION_TOO_LONG" for w in warn)
