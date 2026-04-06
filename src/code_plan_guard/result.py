"""§5.4 ValidationResult and item types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BlockerItem:
    id: str
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class WarningItem:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    ok: bool
    exit_code: int
    blocker_ids: list[str]
    blockers: list[BlockerItem]
    warnings: list[WarningItem]
    artifacts_paths: dict[str, Path]
    summary: dict[str, Any]
    fatal_message: str | None
    error_kind: str | None
    overrides: list[dict[str, Any]] = field(default_factory=list)
    external_signals: list[dict[str, Any]] = field(default_factory=list)
    llm_warnings: list[dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def fatal(message: str, kind: str) -> ValidationResult:
        return ValidationResult(
            ok=False,
            exit_code=2,
            blocker_ids=[],
            blockers=[],
            warnings=[],
            artifacts_paths={},
            summary={},
            fatal_message=message,
            error_kind=kind,
            overrides=[],
            external_signals=[],
            llm_warnings=[],
        )
