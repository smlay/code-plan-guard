from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from code_plan_guard.schema import PlanModel


@dataclass(frozen=True)
class PlanQualityScore:
    score: int
    reasons: list[str]


def score_plan_quality(plan: PlanModel) -> PlanQualityScore:
    """
    Non-blocking, deterministic score meant for reporting only.
    Range: 0..100. Additive-only in report consumers.
    """
    score = 100
    reasons: list[str] = []

    ga = plan.global_analysis if isinstance(plan.global_analysis, dict) else {}
    vs = ga.get("verification_steps")
    ok_vs = isinstance(vs, list) and any(str(x).strip() for x in vs)
    if not ok_vs:
        score -= 40
        reasons.append("missing_verification_steps")

    if not (isinstance(plan.risks_and_rollback, list) and len(plan.risks_and_rollback) >= 1):
        score -= 30
        reasons.append("missing_risks_and_rollback")

    missing_summary = 0
    any_impacted = False
    for ch in plan.changes:
        if not str(ch.summary or "").strip():
            missing_summary += 1
        if ch.impacted_files:
            any_impacted = True
    if missing_summary:
        score -= min(30, 10 * missing_summary)
        reasons.append(f"missing_change_summary:{missing_summary}")
    if not any_impacted:
        score -= 10
        reasons.append("no_impacted_files_anywhere")

    score = max(0, min(100, score))
    return PlanQualityScore(score=score, reasons=reasons)


def link_external_signals_to_plan(
    *,
    plan_changed_files: list[str],
    plan_impacted_files: list[str],
    external_signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Add best-effort linkage fields for reporting.
    - linked_change: whether signal.path matches a changed file
    - linked_impacted: whether signal.path matches a declared impacted file
    """
    changed = set(plan_changed_files)
    impacted = set(plan_impacted_files)
    out: list[dict[str, Any]] = []
    for s in external_signals:
        if not isinstance(s, dict):
            continue
        path = str(s.get("path", "")).replace("\\", "/")
        linked_change = path in changed if path else False
        linked_impacted = path in impacted if path else False
        cp = dict(s)
        cp["linked_change"] = linked_change
        cp["linked_impacted"] = linked_impacted
        out.append(cp)
    return out

