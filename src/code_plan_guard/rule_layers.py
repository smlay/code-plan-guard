from __future__ import annotations

from dataclasses import asdict
from typing import Any

from code_plan_guard.result import BlockerItem, WarningItem


def build_rule_layers(
    *,
    blockers: list[BlockerItem],
    warnings: list[WarningItem],
    llm_warnings: list[Any] | None,
) -> dict[str, Any]:
    """
    Lightweight layer taxonomy for reporting:
    - deterministic: blockers (Bxx) and deterministic warnings (subset)
    - heuristic: most warnings from heuristics/integrations
    - llm: LLM review hook outputs (already warning-only)
    """
    det_blockers = [b.id for b in blockers]
    det_warn_codes: list[str] = []
    heu_warn_codes: list[str] = []
    for w in warnings:
        code = str(w.code or "")
        if code.startswith("W_RUFF_") or code.startswith("W_PYRIGHT_") or code.startswith("W_MYPY_") or code.startswith(
            "W_SEMGREP_"
        ):
            heu_warn_codes.append(code)
        elif code.startswith("W_LANG_") or code.startswith("W_LANGUAGE_") or code.startswith("W_EXTERNAL_"):
            heu_warn_codes.append(code)
        elif code.startswith("W_LLM_"):
            # keep LLM in llm layer
            continue
        else:
            # default: heuristic (conservative; report-only)
            heu_warn_codes.append(code)

    llm_rows: list[Any] = []
    if llm_warnings:
        for x in llm_warnings:
            llm_rows.append(asdict(x) if hasattr(x, "__dataclass_fields__") else x)

    return {
        "deterministic": {"blockers": det_blockers, "warnings": det_warn_codes},
        "heuristic": {"warnings": sorted(set(heu_warn_codes))},
        "llm": {"warnings": llm_rows},
    }

