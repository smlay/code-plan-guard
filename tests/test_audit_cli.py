import json
import subprocess
import sys
from pathlib import Path


def test_audit_summarize(tmp_path: Path) -> None:
    d = tmp_path / "out"
    d.mkdir()
    (d / "audit_overrides.json").write_text(
        json.dumps(
            {
                "schema_version": "0.3",
                "actor": "a",
                "timestamp": "t",
                "commit_sha": "c",
                "plan_hash": "p",
                "overrides": [{"blocker_id": "B03", "reason": "r", "match_count": 1}],
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "code_plan_guard.cli", "audit", "summarize", "--path", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["parsed"] >= 1

