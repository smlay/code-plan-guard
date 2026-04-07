"""External tool integrations (warning-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_semgrep_signals(report_path: Path | None) -> list[dict[str, Any]]:
    if report_path is None or not report_path.is_file():
        return []
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[dict[str, Any]] = []
    results = data.get("results", []) if isinstance(data, dict) else []
    if isinstance(results, list):
        for r in results:
            if not isinstance(r, dict):
                continue
            path = ""
            extra = r.get("path")
            if isinstance(extra, str):
                path = extra.replace("\\", "/")
            check_id = str(r.get("check_id", ""))
            msg = ""
            m = r.get("extra", {}).get("message") if isinstance(r.get("extra"), dict) else None
            if isinstance(m, str):
                msg = m
            out.append({"source": "semgrep", "code": check_id, "path": path, "message": msg})
    return out


def load_mypy_signals(report_path: Path | None) -> list[dict[str, Any]]:
    """
    Best-effort mypy report loader.
    Accepts JSON list of {file, line, column, severity, message, code}.
    """
    if report_path is None or not report_path.is_file():
        return []
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    "source": "mypy",
                    "path": str(item.get("file", "")).replace("\\", "/"),
                    "line": item.get("line"),
                    "column": item.get("column"),
                    "severity": str(item.get("severity", "")),
                    "code": str(item.get("code", "")),
                    "message": str(item.get("message", "")),
                }
            )
    return out

