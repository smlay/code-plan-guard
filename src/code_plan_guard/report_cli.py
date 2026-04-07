"""Artifacts viewer CLI helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_reconciliation(report: dict[str, Any]) -> dict[str, Any]:
    blockers = report.get("blockers", []) or []
    warnings = report.get("warnings", []) or []
    return {
        "tool_version": report.get("tool_version", ""),
        "plan_version": report.get("plan_version", ""),
        "blockers": len(blockers),
        "warnings": len(warnings),
        "blocker_ids": [b.get("id") for b in blockers[:10] if isinstance(b, dict)],
        "warning_codes": [w.get("code") for w in warnings[:10] if isinstance(w, dict)],
    }

