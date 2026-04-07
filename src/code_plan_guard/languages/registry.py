from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code_plan_guard.languages.base import LangEdge, LangWarning, LanguagePlugin


@dataclass(frozen=True)
class LanguageTruth:
    schema_version: str
    edges: list[dict[str, Any]]
    per_file: dict[str, Any]
    aggregated_targets: list[str]
    warnings: list[dict[str, Any]]


def run_language_plugins(
    repo: Path,
    changed_files: list[str],
    plugins: list[LanguagePlugin],
) -> tuple[LanguageTruth, list[LangEdge], list[LangWarning]]:
    edges: list[LangEdge] = []
    warns: list[LangWarning] = []
    for p in plugins:
        e, w = p.analyze(repo, changed_files)
        edges.extend(e)
        warns.extend(w)

    per_file: dict[str, Any] = {}
    agg: set[str] = set()
    for e in edges:
        per_file.setdefault(e.from_file, {"targets": [], "language": e.language, "source": e.source})
        per_file[e.from_file]["targets"].append(e.to_file)
        agg.add(e.to_file)
    # deterministic
    for k in list(per_file.keys()):
        per_file[k]["targets"] = sorted(set(per_file[k]["targets"]))

    truth = LanguageTruth(
        schema_version="0.1",
        edges=[
            {
                "from_file": e.from_file,
                "to_file": e.to_file,
                "language": e.language,
                "source": e.source,
            }
            for e in edges
        ],
        per_file=per_file,
        aggregated_targets=sorted(agg),
        warnings=[
            {
                "code": w.code,
                "message": w.message,
                "details": w.details,
                "language": w.language,
                "source": w.source,
            }
            for w in warns
        ],
    )
    return truth, edges, warns

