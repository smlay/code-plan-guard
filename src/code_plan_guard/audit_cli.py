from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def summarize_audits(root: Path) -> dict[str, Any]:
    paths = list(root.rglob("audit_overrides.json")) if root.is_dir() else [root]
    total = 0
    by_blocker: Counter[str] = Counter()
    by_reason: Counter[str] = Counter()
    actors: Counter[str] = Counter()
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        total += 1
        actors[str(data.get("actor", ""))] += 1
        for ov in data.get("overrides", []) or []:
            if not isinstance(ov, dict):
                continue
            bid = str(ov.get("blocker_id", ""))
            rs = str(ov.get("reason", ""))
            if bid:
                by_blocker[bid] += 1
            if rs:
                by_reason[rs] += 1
    return {
        "audit_files": len(paths),
        "parsed": total,
        "top_blockers": by_blocker.most_common(20),
        "top_reasons": by_reason.most_common(20),
        "top_actors": actors.most_common(20),
    }

