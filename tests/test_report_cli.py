import json
import subprocess
import sys
from pathlib import Path


def test_report_show_and_diff(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "tool_version": "0.4.0",
                "plan_version": "0.1",
                "blocker_ids": [],
                "warnings": [{"code": "W1", "message": "m"}],
                "blockers": [],
                "edges": [],
                "summary": {},
            }
        ),
        encoding="utf-8",
    )
    b.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "tool_version": "0.4.0",
                "plan_version": "0.1",
                "blocker_ids": ["B03"],
                "warnings": [],
                "blockers": [{"id": "B03", "code": "B03", "message": "x"}],
                "edges": [],
                "summary": {},
            }
        ),
        encoding="utf-8",
    )

    p1 = subprocess.run(
        [sys.executable, "-m", "code_plan_guard.cli", "report", "show", "--path", str(a), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert p1.returncode == 0
    payload = json.loads(p1.stdout)
    assert "summary" in payload

    p2 = subprocess.run(
        [sys.executable, "-m", "code_plan_guard.cli", "report", "diff", "--a", str(a), "--b", str(b)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert p2.returncode == 0
    assert "warnings" in p2.stdout or "blockers" in p2.stdout

