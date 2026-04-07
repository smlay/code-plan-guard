import subprocess
import sys
from pathlib import Path


def test_cli_init_generates_files(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "code_plan_guard.cli", "init", "--repo", str(tmp_path), "--force"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / ".codeguard.yml").is_file()
    assert (tmp_path / ".codeguard" / "plan.yaml").is_file()


def test_cli_plan_new_and_lint(tmp_path: Path) -> None:
    p = tmp_path / "plan.yaml"
    proc1 = subprocess.run(
        [sys.executable, "-m", "code_plan_guard.cli", "plan", "new", "--out", str(p), "--force"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert proc1.returncode == 0, proc1.stderr
    proc2 = subprocess.run(
        [sys.executable, "-m", "code_plan_guard.cli", "plan", "lint", "--plan", str(p)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert proc2.returncode == 0, proc2.stderr

