"""v0.2 helpers: base-ref diff, override, external signals, llm warning."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_plan_guard.result import BlockerItem, WarningItem

_OVERRIDE_RE = re.compile(
    r"code-plan-guard:\s*override\s+(B\d{2})\s+reason=(.+)$", re.IGNORECASE
)


def git_changed_files(repo: Path, base_ref: str) -> list[str]:
    """Return changed files (POSIX relative) in base_ref..HEAD."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}..HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    out = []
    for line in proc.stdout.splitlines():
        s = line.strip().replace("\\", "/")
        if s:
            out.append(s)
    return sorted(set(out))


def parse_override_file(path: Path | None) -> list[dict[str, str]]:
    """Parse override directives from free-text file."""
    if path is None or not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    rows: list[dict[str, str]] = []
    for raw in text.splitlines():
        m = _OVERRIDE_RE.search(raw.strip())
        if not m:
            continue
        rows.append({"blocker_id": m.group(1).upper(), "reason": m.group(2).strip()})
    return rows


def apply_overrides(
    blockers: list[BlockerItem],
    overrides: list[dict[str, str]],
    *,
    allowed_blockers: set[str],
) -> tuple[list[BlockerItem], list[dict[str, Any]], list[WarningItem]]:
    """Return (effective_blockers, applied_override_records, warnings)."""
    keep: list[BlockerItem] = []
    applied: list[dict[str, Any]] = []
    warns: list[WarningItem] = []
    by_id: dict[str, list[str]] = {}
    for o in overrides:
        by_id.setdefault(o["blocker_id"], []).append(o["reason"])

    for b in blockers:
        reasons = by_id.get(b.id, [])
        if not reasons:
            keep.append(b)
            continue
        if b.id not in allowed_blockers:
            warns.append(
                WarningItem(
                    code="W_OVERRIDE_REJECTED",
                    message=f"override 被拒绝：{b.id} 不在允许列表",
                    details={"blocker_id": b.id, "allowed_blockers": sorted(allowed_blockers)},
                )
            )
            keep.append(b)
            continue
        applied.append({"blocker_id": b.id, "reason": reasons[-1], "match_count": len(reasons)})
    return keep, applied, warns


def write_override_audit(
    out_dir: Path,
    *,
    overrides_applied: list[dict[str, Any]],
    plan_hash: str,
    commit_sha: str,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    actor = os.environ.get("GITHUB_ACTOR", "local")
    data = {
        "schema_version": "0.1",
        "actor": actor,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit_sha": commit_sha,
        "plan_hash": plan_hash,
        "overrides": overrides_applied,
    }
    p = out_dir / "audit_overrides.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def git_head_sha(repo: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def load_ruff_signals(report_path: Path | None) -> list[dict[str, Any]]:
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
                    "source": "ruff",
                    "code": str(item.get("code", "")),
                    "path": str(item.get("filename", item.get("path", ""))).replace("\\", "/"),
                    "message": str(item.get("message", "")),
                }
            )
    return out


def load_pyright_signals(report_path: Path | None) -> list[dict[str, Any]]:
    if report_path is None or not report_path.is_file():
        return []
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[dict[str, Any]] = []
    g = data.get("generalDiagnostics", []) if isinstance(data, dict) else []
    if isinstance(g, list):
        for item in g:
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    "source": "pyright",
                    "severity": str(item.get("severity", "")),
                    "rule": str(item.get("rule", "")),
                    "path": str(item.get("file", "")).replace("\\", "/"),
                    "message": str(item.get("message", "")),
                }
            )
    return out


def llm_review_warning(enabled: bool, summary: dict[str, Any]) -> list[WarningItem]:
    """v0.2 mock hook: warning-only, no blocker side effects."""
    if not enabled:
        return []
    if int(summary.get("reconcile_missing", 0)) > 0:
        return [
            WarningItem(
                code="W_LLM_REVIEW",
                message="LLM 二轮审查建议：存在未覆盖影响面，请人工复核。",
                details={"reconcile_missing": int(summary.get("reconcile_missing", 0))},
            )
        ]
    return [
        WarningItem(
            code="W_LLM_REVIEW",
            message="LLM 二轮审查已启用（warning-only）。",
            details={},
        )
    ]

