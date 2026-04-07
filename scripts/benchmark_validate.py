from __future__ import annotations

import time
from pathlib import Path

from code_plan_guard import validate_plan


def main() -> None:
    repo = Path(".").resolve()
    plan = repo / ".codeguard" / "plan.yaml"
    if not plan.is_file():
        print("missing .codeguard/plan.yaml; run `code-plan-guard init --repo .` first")
        raise SystemExit(2)
    t0 = time.time()
    r = validate_plan(plan, repo, write_artifacts=False, no_cache=True)
    dt = time.time() - t0
    print(f"exit_code={r.exit_code} ok={r.ok} blockers={len(r.blockers)} warnings={len(r.warnings)} time_s={dt:.4f}")


if __name__ == "__main__":
    main()

