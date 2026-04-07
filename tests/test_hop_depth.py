from pathlib import Path

from code_plan_guard.config import GuardConfig
from code_plan_guard.imports import build_expected_impact


def test_hop_depth_expands_targets(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import c\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("x = 1\n", encoding="utf-8")
    cfg = GuardConfig()
    cfg.src_roots = ["."]
    cfg.hop_depth = 2
    out, warn, _edges = build_expected_impact(tmp_path, ["a.py"], cfg)
    assert "b.py" in out["aggregated_one_hop"]
    assert "c.py" in out["aggregated_one_hop"]
    assert out["analysis"]["hop_depth"] == 2

