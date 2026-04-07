"""§11 artifacts and guard_report.md."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from code_plan_guard.config import GuardConfig
from code_plan_guard.constants import __version__
from code_plan_guard.result import BlockerItem, WarningItem


def write_expected_impact(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_reconciliation_report(
    path: Path,
    *,
    plan_version: str,
    blocker_ids: list[str],
    blockers: list[BlockerItem],
    warnings: list[WarningItem],
    edges: list[dict[str, Any]],
    summary: dict[str, int],
    context: dict[str, Any] | None = None,
    config_hash: str | None = None,
    overrides: list[dict[str, Any]] | None = None,
    external_signals: list[dict[str, Any]] | None = None,
    llm_warnings: list[Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": "0.1",
        "tool_version": __version__,
        "plan_version": plan_version,
        "blocker_ids": blocker_ids,
        "warnings": [asdict(w) for w in warnings],
        "blockers": [asdict(b) for b in blockers],
        "edges": edges,
        "summary": summary,
    }
    if context is not None:
        payload["context"] = context
    if config_hash:
        payload["config_snapshot_hash"] = config_hash
    if overrides is not None:
        payload["overrides"] = overrides
    if external_signals is not None:
        payload["external_signals"] = external_signals
    if llm_warnings is not None:
        payload["llm_warnings"] = [
            asdict(x) if hasattr(x, "__dataclass_fields__") else x for x in llm_warnings
        ]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_signals_json(path: Path, signals: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": "0.1", "signals": signals}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_guard_report_md(
    path: Path,
    *,
    intent_note: str | None,
    blockers: list[BlockerItem],
    warnings: list[WarningItem],
    summary: dict[str, Any],
    overrides: list[dict[str, Any]],
) -> None:
    lines = ["# code-plan-guard 报告\n"]
    if intent_note:
        lines.append(f"**意图文件**：{intent_note}\n")
    lines.append("## 摘要\n")
    for k, v in summary.items():
        lines.append(f"- {k}: {v}\n")
    lines.append("\n## Blockers\n")
    if not blockers:
        lines.append("无。\n")
    else:
        for b in blockers:
            lines.append(f"- **{b.id}** ({b.code}): {b.message}\n")
    lines.append("\n## Warnings\n")
    if not warnings:
        lines.append("无。\n")
    else:
        for w in warnings:
            lines.append(f"- ({w.code}) {w.message}\n")
    lines.append("\n## Overrides\n")
    if not overrides:
        lines.append("无。\n")
    else:
        for ov in overrides:
            lines.append(
                f"- blocker={ov.get('blocker_id')} reason={ov.get('reason')} (match_count={ov.get('match_count')})\n"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def config_hash_quick(cfg: GuardConfig) -> str:
    from code_plan_guard.config import config_for_cache_hash

    return hashlib.sha256(config_for_cache_hash(cfg).encode()).hexdigest()[:16]
