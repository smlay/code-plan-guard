"""v0.4 optional tree-sitter scan (best-effort; warning-only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code_plan_guard.result import WarningItem


def scan_js_ts_with_tree_sitter(repo: Path, changed_files: list[str]) -> tuple[list[dict[str, Any]], list[WarningItem]]:
    """
    If tree_sitter is available, try to produce import signals.
    In v0.4 we keep it best-effort; if dependency is missing, return warnings and empty signals.
    """
    try:
        import tree_sitter  # type: ignore  # noqa: F401
    except Exception:
        return [], [
            WarningItem(
                code="W_TREE_SITTER_UNAVAILABLE",
                message="tree-sitter 不可用，已降级到启发式多语言扫描。",
                details={},
            )
        ]
    # Placeholder: real parser wiring deferred to v0.5+. Keep contract.
    return [], [
        WarningItem(
            code="W_TREE_SITTER_NOT_IMPLEMENTED",
            message="tree-sitter 扫描尚未实现（v0.4 占位，已保持 warning-only）。",
            details={},
        )
    ]

