import json
import subprocess
import sys
from pathlib import Path


def test_cli_json_has_result_version(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "a.py").write_text("from pkg import b\n", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "b.py").write_text("X = 1\n", encoding="utf-8")
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/pkg/a.py\n"
        "    summary: s\n"
        "    impacted_files:\n"
        "      - src/pkg/b.py\n"
        "global_analysis: {}\n"
        "risks_and_rollback:\n  - risk: r\n    mitigation: m\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "code_plan_guard.cli",
            "review",
            "--plan",
            str(plan),
            "--repo",
            str(tmp_path),
            "--no-cache",
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["result_version"] == "0.4"

