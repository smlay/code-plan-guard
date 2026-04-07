from pathlib import Path

from code_plan_guard.v03 import parse_overrides_from_text, overrides_from_file, plan_path_from_pr_body


def test_parse_overrides_from_text_keeps_metadata() -> None:
    text = "x\ncode-plan-guard: override b03 reason=hello\n"
    out = parse_overrides_from_text(text, source_type="pr_body", source_ref="pr:1", author="u", created_at="t")
    assert len(out) == 1
    d = out[0]
    assert d.blocker_id == "B03"
    assert d.reason == "hello"
    assert d.raw.lower().startswith("code-plan-guard:")
    assert d.source_type == "pr_body"
    assert d.source_ref == "pr:1"
    assert d.author == "u"
    assert d.created_at == "t"


def test_overrides_from_file_reads_text(tmp_path: Path) -> None:
    p = tmp_path / "ov.txt"
    p.write_text("code-plan-guard: override B05 reason=r\n", encoding="utf-8")
    out = overrides_from_file(p)
    assert len(out) == 1
    assert out[0].blocker_id == "B05"


def test_parse_override_block_fence() -> None:
    text = "```override\ncode-plan-guard: override B03 reason=ok sha=abcdef1\n```\n"
    out = parse_overrides_from_text(text, source_type="pr_body", source_ref="pr:1")
    assert len(out) == 1
    assert out[0].blocker_id == "B03"
    assert out[0].sha == "abcdef1"
    assert "sha=abcdef1" in out[0].raw


def test_plan_path_from_pr_body() -> None:
    assert plan_path_from_pr_body("plan: .codeguard/plan.yaml\n") == ".codeguard/plan.yaml"
