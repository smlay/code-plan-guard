"""v0.2 CI workflow smoke."""

from pathlib import Path


def test_ci_contains_guard_job() -> None:
    wf = Path(".github/workflows/ci.yml")
    text = wf.read_text(encoding="utf-8")
    assert "guard:" in text
    assert "code-plan-guard review" in text
    assert "--plan auto" in text
    assert "upload-artifact" in text
