"""§12 configuration load and defaults (appendix A/B)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# code-plan-guard-prd:§1.2 — unknown YAML keys are ignored (no error) for forward compatibility.
_IGNORE_UNKNOWN_KEYS = True


@dataclass
class GuardConfig:
    version: str = "1"
    src_roots: list[str] = field(default_factory=lambda: [".", "src"])
    skip_imports_in_false_branch: bool = True
    skip_imports_in_type_checking_if: bool = True
    hop_depth: int = 1
    module_roll_up: bool = False
    max_edges_before_roll_up: int = 10
    max_function_lines: int = 300
    max_class_lines: int = 600
    count_docstrings: bool = False
    style_severity: str = "warning"  # warning | block
    exemption_paths: list[str] = field(default_factory=list)
    cache_enabled: bool = True
    cache_dir: str = "~/.codeguard/cache"
    llm_review_enabled: bool = False
    llm_review_provider: str = "none"
    llm_review_model: str = ""
    override_enabled: bool = True
    override_allowed_blockers: list[str] = field(default_factory=lambda: ["B03", "B05"])
    github_plan_path: str = ""
    integrations_ruff_enabled: bool = False
    integrations_ruff_report_path: str = ""
    integrations_pyright_enabled: bool = False
    integrations_pyright_report_path: str = ""
    strict_plan_diff: bool = False

    def resolved_cache_dir(self) -> Path:
        return Path(os.path.expanduser(self.cache_dir))


def _get(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def load_config_dict(raw: dict[str, Any]) -> GuardConfig:
    """Merge user YAML into defaults."""
    cfg = GuardConfig()
    if not raw:
        return cfg
    cfg.version = str(raw.get("version", cfg.version))
    analysis = raw.get("analysis") or {}
    if isinstance(analysis, dict):
        if "src_roots" in analysis and analysis["src_roots"]:
            cfg.src_roots = list(analysis["src_roots"])
        cfg.skip_imports_in_false_branch = bool(
            analysis.get("skip_imports_in_false_branch", cfg.skip_imports_in_false_branch)
        )
        cfg.skip_imports_in_type_checking_if = bool(
            analysis.get("skip_imports_in_type_checking_if", cfg.skip_imports_in_type_checking_if)
        )
    rules = raw.get("rules") or {}
    if isinstance(rules, dict):
        rec = rules.get("reconciliation") or {}
        if isinstance(rec, dict):
            cfg.hop_depth = int(rec.get("hop_depth", cfg.hop_depth))
            cfg.module_roll_up = bool(rec.get("module_roll_up", cfg.module_roll_up))
            cfg.max_edges_before_roll_up = int(
                rec.get("max_edges_before_roll_up", cfg.max_edges_before_roll_up)
            )
        style = rules.get("style") or {}
        if isinstance(style, dict):
            cfg.max_function_lines = int(style.get("max_function_lines", cfg.max_function_lines))
            cfg.max_class_lines = int(style.get("max_class_lines", cfg.max_class_lines))
            cfg.count_docstrings = bool(style.get("count_docstrings", cfg.count_docstrings))
            cfg.style_severity = str(style.get("severity", cfg.style_severity))
    ex = raw.get("exemptions") or {}
    if isinstance(ex, dict) and "paths" in ex:
        cfg.exemption_paths = list(ex.get("paths") or [])
    cache = raw.get("cache") or {}
    if isinstance(cache, dict):
        cfg.cache_enabled = bool(cache.get("enabled", cfg.cache_enabled))
        if "dir" in cache:
            cfg.cache_dir = str(cache["dir"])
    llm = raw.get("llm_review") or {}
    if isinstance(llm, dict):
        cfg.llm_review_enabled = bool(llm.get("enabled", cfg.llm_review_enabled))
        cfg.llm_review_provider = str(llm.get("provider", cfg.llm_review_provider))
        cfg.llm_review_model = str(llm.get("model", cfg.llm_review_model))
    ov = raw.get("override") or {}
    if isinstance(ov, dict):
        cfg.override_enabled = bool(ov.get("enabled", cfg.override_enabled))
        if ov.get("allowed_blockers"):
            cfg.override_allowed_blockers = [str(x) for x in ov.get("allowed_blockers", [])]
    gh = raw.get("github") or {}
    if isinstance(gh, dict):
        cfg.github_plan_path = str(gh.get("plan_path", cfg.github_plan_path))
    integ = raw.get("integrations") or {}
    if isinstance(integ, dict):
        ruff = integ.get("ruff") or {}
        if isinstance(ruff, dict):
            cfg.integrations_ruff_enabled = bool(
                ruff.get("enabled", cfg.integrations_ruff_enabled)
            )
            cfg.integrations_ruff_report_path = str(
                ruff.get("report_path", cfg.integrations_ruff_report_path)
            )
        pyright = integ.get("pyright") or {}
        if isinstance(pyright, dict):
            cfg.integrations_pyright_enabled = bool(
                pyright.get("enabled", cfg.integrations_pyright_enabled)
            )
            cfg.integrations_pyright_report_path = str(
                pyright.get("report_path", cfg.integrations_pyright_report_path)
            )
    plan_scope = raw.get("plan_scope") or {}
    if isinstance(plan_scope, dict):
        cfg.strict_plan_diff = bool(plan_scope.get("strict_diff", cfg.strict_plan_diff))
    return cfg


def discover_config_file(repo: Path, explicit: Path | None) -> Path | None:
    """§5.5 order."""
    if explicit is not None and explicit.is_file():
        return explicit
    for name in (".codeguard.yml", ".code-plan-guard.yml"):
        p = repo / name
        if p.is_file():
            return p
    return None


def load_config_from_path(path: Path | None, repo: Path) -> GuardConfig:
    if path is None:
        return load_config_dict({})
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError("config root must be a mapping")
    return load_config_dict(raw)


def config_for_cache_hash(cfg: GuardConfig) -> str:
    """Subset serialized for cache key §13.2."""
    d = {
        "src_roots": cfg.src_roots,
        "skip_false": cfg.skip_imports_in_false_branch,
        "skip_tc": cfg.skip_imports_in_type_checking_if,
        "hop_depth": cfg.hop_depth,
        "module_roll_up": cfg.module_roll_up,
        "max_edges_roll": cfg.max_edges_before_roll_up,
        "style": {
            "max_function_lines": cfg.max_function_lines,
            "max_class_lines": cfg.max_class_lines,
            "count_docstrings": cfg.count_docstrings,
            "severity": cfg.style_severity,
        },
        "exemptions": cfg.exemption_paths,
        "override": {
            "enabled": cfg.override_enabled,
            "allowed_blockers": cfg.override_allowed_blockers,
        },
        "integrations": {
            "ruff": {
                "enabled": cfg.integrations_ruff_enabled,
                "report_path": cfg.integrations_ruff_report_path,
            },
            "pyright": {
                "enabled": cfg.integrations_pyright_enabled,
                "report_path": cfg.integrations_pyright_report_path,
            },
        },
        "plan_scope": {"strict_diff": cfg.strict_plan_diff},
    }
    return yaml.dump(d, sort_keys=True)
