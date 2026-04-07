from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class LangEdge:
    from_file: str
    to_file: str
    language: str
    source: str


@dataclass(frozen=True)
class LangWarning:
    code: str
    message: str
    details: dict[str, Any]
    language: str
    source: str


class LanguagePlugin(Protocol):
    name: str

    def analyze(self, repo: Path, changed_files: list[str]) -> tuple[list[LangEdge], list[LangWarning]]:
        ...

