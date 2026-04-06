"""§9 reconciliation B03."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from code_plan_guard.paths import normalize_under_repo
from code_plan_guard.schema import PlanModel


def path_exempt(rel: str, patterns: list[str]) -> bool:
    """Glob-like exemption: support * and prefix/**."""
    rel = rel.replace("\\", "/")
    for raw in patterns:
        p = raw.replace("\\", "/")
        if p.endswith("/**"):
            prefix = p[:-3].rstrip("/")
            if rel == prefix or rel.startswith(prefix + "/"):
                return True
        elif "**" in p or "*" in p or "?" in p:
            if fnmatch.fnmatch(rel, p):
                return True
        else:
            if rel == p or rel.startswith(p + "/"):
                return True
    return False


def collect_d_and_exceptions(
    repo: Path, plan: PlanModel
) -> tuple[set[str], list[dict[str, Any]]]:
    d: set[str] = set()
    exceptions: list[dict[str, Any]] = []
    for ch in plan.changes:
        if ch.impacted_files:
            for s in ch.impacted_files:
                r, _ = normalize_under_repo(repo, s, must_be_file=False)
                if r:
                    d.add(r)
        if ch.reconciliation_exceptions:
            for ex in ch.reconciliation_exceptions:
                to_r, _ = normalize_under_repo(repo, ex.to_file, must_be_file=False)
                if not to_r:
                    continue
                from_r: str | None = None
                if ex.from_file:
                    from_r, _ = normalize_under_repo(repo, ex.from_file, must_be_file=False)
                exceptions.append(
                    {
                        "to_file": to_r,
                        "from_file": from_r,
                        "reason": ex.reason,
                        "match_mode": "exact" if from_r else "to_only",
                    }
                )
    return d, exceptions


def covered_by_exception(from_file: str, to_file: str, exceptions: list[dict[str, Any]]) -> bool:
    for ex in exceptions:
        if ex["to_file"] != to_file:
            continue
        if ex["from_file"] is None:
            return True
        if ex["from_file"] == from_file:
            return True
    return False


def target_covered(
    to_file: str,
    d: set[str],
    exemption_paths: list[str],
    exceptions: list[dict[str, Any]],
    edges: list[tuple[str, str]],
) -> bool:
    """§9.3 — to_file ∈ H is covered by D, E, or X."""
    if to_file in d:
        return True
    if path_exempt(to_file, exemption_paths):
        return True
    for from_f, t in edges:
        if t == to_file and covered_by_exception(from_f, to_file, exceptions):
            return True
    return False


def reconcile(
    repo: Path,
    plan: PlanModel,
    aggregated_one_hop: list[str],
    edges: list[tuple[str, str]],
    exemption_paths: list[str],
) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    """Build edge rows for report and B03 missing list."""
    d, exceptions = collect_d_and_exceptions(repo, plan)
    h = set(aggregated_one_hop)
    rows: list[dict[str, Any]] = []

    for from_f, to_f in edges:
        row: dict[str, Any] = {
            "from_file": from_f,
            "to_file": to_f,
            "status": "missing",
            "resolution": None,
        }
        if to_f in d:
            row["status"] = "covered"
            row["resolution"] = "D"
        elif path_exempt(to_f, exemption_paths):
            row["status"] = "covered"
            row["resolution"] = "E"
        elif covered_by_exception(from_f, to_f, exceptions):
            row["status"] = "covered"
            row["resolution"] = "X"
            for ex in exceptions:
                if ex["to_file"] == to_f and ex["from_file"] is None:
                    row["match_mode"] = "to_only"
                    break
        rows.append(row)

    missing = [t for t in sorted(h) if not target_covered(t, d, exemption_paths, exceptions, edges)]

    summary = {
        "total_h": len(h),
        "covered_by_d": sum(1 for t in h if t in d),
        "covered_by_e": sum(1 for t in h if path_exempt(t, exemption_paths)),
        "covered_by_x": sum(
            1
            for t in h
            if t not in d
            and not path_exempt(t, exemption_paths)
            and any(covered_by_exception(f, t, exceptions) for f, tf in edges if tf == t)
        ),
        "missing": len(missing),
    }
    return rows, missing, summary
