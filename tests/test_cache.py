"""§13.2 cache."""

from pathlib import Path

from code_plan_guard.cache import cache_key, load_cache, save_cache
from code_plan_guard.config import GuardConfig


def test_cache_roundtrip(tmp_path: Path) -> None:
    cfg = GuardConfig(cache_enabled=True)
    repo = tmp_path
    (repo / "a.py").write_text("import x\n", encoding="utf-8")
    k = cache_key(repo, cfg, ["a.py"])
    p = tmp_path / "c" / f"{k}.json"
    save_cache(p, {"expected_impact": {"x": 1}, "edges": []})
    assert load_cache(p) == {"expected_impact": {"x": 1}, "edges": []}
