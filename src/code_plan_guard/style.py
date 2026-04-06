"""§10.2 B05 style line counts."""

from __future__ import annotations

import ast
from pathlib import Path

from code_plan_guard.config import GuardConfig


def _leading_docstring_end(body: list[ast.stmt]) -> int:
    """Return index after leading docstring stmt, or 0."""
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return 1
    return 0


def _stmt_block_lines(body: list[ast.stmt], count_docstrings: bool) -> int:
    # code-plan-guard-prd:§10.2 — empty body after docstring strip → 0 body lines
    if not count_docstrings:
        i = _leading_docstring_end(body)
        body = body[i:]
    if not body:
        return 0
    first_ln = body[0].lineno
    last = body[-1]
    end_ln = last.end_lineno if last.end_lineno is not None else last.lineno
    return end_ln - first_ln + 1


def analyze_style(
    repo: Path, py_files: list[str], cfg: GuardConfig
) -> tuple[list[dict], list[dict]]:
    """Returns (blockers_for_b05, warnings)."""
    blockers: list[dict] = []
    warnings: list[dict] = []
    if cfg.style_severity not in ("warning", "block"):
        cfg.style_severity = "warning"

    for rel in py_files:
        path = repo / rel
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(path))
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nlines = _stmt_block_lines(node.body, cfg.count_docstrings)
                if nlines > cfg.max_function_lines:
                    item = {
                        "kind": "function",
                        "file": rel,
                        "name": node.name,
                        "actual": nlines,
                        "limit": cfg.max_function_lines,
                    }
                    if cfg.style_severity == "block":
                        blockers.append(item)
                    else:
                        warnings.append(
                            {
                                "code": "W_FUNCTION_TOO_LONG",
                                "message": f"{rel}:{node.name} 函数体 {nlines} 行超过 {cfg.max_function_lines}",
                                "details": item,
                            }
                        )
            elif isinstance(node, ast.ClassDef):
                nlines = _stmt_block_lines(node.body, cfg.count_docstrings)
                if nlines > cfg.max_class_lines:
                    item = {
                        "kind": "class",
                        "file": rel,
                        "name": node.name,
                        "actual": nlines,
                        "limit": cfg.max_class_lines,
                    }
                    if cfg.style_severity == "block":
                        blockers.append(item)
                    else:
                        warnings.append(
                            {
                                "code": "W_CLASS_TOO_LONG",
                                "message": f"{rel}:{node.name} 类体 {nlines} 行超过 {cfg.max_class_lines}",
                                "details": item,
                            }
                        )
    return blockers, warnings
