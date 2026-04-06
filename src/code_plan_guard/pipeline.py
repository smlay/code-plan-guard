"""§4 orchestration: validate_plan."""

from __future__ import annotations

import subprocess
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from code_plan_guard import messages as msg
from code_plan_guard.cache import cache_key, cache_paths, load_cache, save_cache
from code_plan_guard.config import GuardConfig, discover_config_file, load_config_from_path
from code_plan_guard.imports import build_expected_impact
from code_plan_guard.paths import is_b01_empty_or_absolute, normalize_under_repo
from code_plan_guard.plan_load import load_plan_raw
from code_plan_guard.reconcile import reconcile
from code_plan_guard.reports import (
    config_hash_quick,
    write_expected_impact,
    write_guard_report_md,
    write_reconciliation_report,
)
from code_plan_guard.result import BlockerItem, ValidationResult, WarningItem
from code_plan_guard.schema import PlanModel
from code_plan_guard.style import analyze_style
from code_plan_guard.v02 import (
    apply_overrides,
    git_changed_files,
    git_head_sha,
    llm_review_warning,
    load_pyright_signals,
    load_ruff_signals,
    parse_override_file,
    write_override_audit,
)


def _git_ref_exists(repo: Path, ref: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def validate_plan(
    plan_path: str | Path,
    repo_path: str | Path,
    *,
    write_artifacts: bool = True,
    out_dir: Path | None = None,
    config_path: Path | None = None,
    intent_path: Path | None = None,
    base_ref: str | None = None,
    no_cache: bool = False,
    override_file: Path | None = None,
    ruff_report: Path | None = None,
    pyright_report: Path | None = None,
    strict_plan_diff: bool | None = None,
) -> ValidationResult:
    repo = Path(repo_path).resolve()
    plan_p = Path(plan_path).resolve()
    artifacts: dict[str, Path] = {}
    warnings: list[WarningItem] = []
    blockers: list[BlockerItem] = []
    summary: dict[str, Any] = {
        "changed_files_count": 0,
        "aggregated_h_count": 0,
        "edge_count": 0,
        "unresolved_imports_count": 0,
    }
    external_signals: list[dict[str, Any]] = []
    overrides_applied: list[dict[str, Any]] = []
    llm_warnings: list[WarningItem] = []

    if not repo.is_dir():
        return ValidationResult.fatal(f"仓库路径不是目录：{repo}", "IO_ERROR")

    if config_path is not None:
        cp = Path(config_path).resolve()
        if not cp.is_file():
            return ValidationResult.fatal(f"配置文件不存在：{cp}", "IO_ERROR")

    explicit_cfg = Path(config_path).resolve() if config_path else None
    cfile = discover_config_file(repo, explicit_cfg)
    try:
        cfg = load_config_from_path(cfile, repo)
    except (OSError, ValueError) as e:
        return ValidationResult.fatal(f"配置加载失败：{e}", "CONFIG_ERROR")

    raw, fatal_m, fatal_k = load_plan_raw(plan_p)
    if raw is None:
        return ValidationResult.fatal(fatal_m or "未知错误", fatal_k or "INTERNAL")

    plan: PlanModel | None = None
    try:
        plan = PlanModel.model_validate(raw)
    except ValidationError as e:
        err_list = e.errors()
        is_b04 = any(
            x.get("type") == "too_short" and tuple(x.get("loc", ())) == ("changes",)
            for x in err_list
        )
        if is_b04:
            blockers.append(
                BlockerItem(
                    id="B04",
                    code="B04_EMPTY_CHANGES",
                    message=msg.B04,
                    details={"errors": err_list},
                )
            )
        else:
            blockers.append(
                BlockerItem(
                    id="B01",
                    code="B01_SCHEMA",
                    message=msg.B01.format(details=e),
                    details={"errors": err_list},
                )
            )
        return _finalize_write(
            blockers,
            warnings,
            summary,
            plan_version=str(raw.get("plan_version", "0.1")),
            write_artifacts=write_artifacts,
            out_dir=out_dir,
            repo=repo,
            cfg=cfg,
            artifacts=artifacts,
            intent_path=intent_path,
            expected_impact=None,
            edge_rows=[],
            rec_summary={
                "total_h": 0,
                "covered_by_d": 0,
                "covered_by_e": 0,
                "covered_by_x": 0,
                "missing": 0,
            },
            overrides_applied=[],
            external_signals=[],
            llm_warnings=[],
        )

    assert plan is not None

    if base_ref and not _git_ref_exists(repo, base_ref):
        warnings.append(
            WarningItem(
                code="W_BASE_REF_INVALID",
                message=f"Git 引用无效或不可用：{base_ref}",
                details={"base_ref": base_ref},
            )
        )

    for ch in plan.changes:
        if is_b01_empty_or_absolute(ch.file):
            blockers.append(
                BlockerItem(
                    id="B01",
                    code="B01_SCHEMA",
                    message=msg.B01.format(details=f"非法路径：{ch.file!r}"),
                    details={"file": ch.file},
                )
            )
            continue
        norm, err = normalize_under_repo(repo, ch.file, must_be_file=True)
        if norm is None:
            blockers.append(
                BlockerItem(
                    id="B02",
                    code="B02_FILE_NOT_FOUND",
                    message=msg.B02.format(file=ch.file),
                    details={"file": ch.file, "reason": err},
                )
            )

    changed_ok: list[str] = []
    for ch in plan.changes:
        if is_b01_empty_or_absolute(ch.file):
            continue
        norm, _e = normalize_under_repo(repo, ch.file, must_be_file=True)
        if norm is not None:
            changed_ok.append(norm)

    changed_ok = sorted(set(changed_ok))
    summary["changed_files_count"] = len(changed_ok)
    py_changed = [f for f in changed_ok if f.endswith(".py")]

    # v0.2 base-ref incremental scope
    eff_strict_plan_diff = cfg.strict_plan_diff if strict_plan_diff is None else strict_plan_diff
    if base_ref and _git_ref_exists(repo, base_ref):
        diff_files = git_changed_files(repo, base_ref)
        diff_py = sorted({x for x in diff_files if x.endswith(".py")})
        summary["base_ref"] = base_ref
        summary["base_ref_diff_files_list"] = diff_files[:50]
        summary["base_ref_diff_files"] = len(diff_files)
        summary["base_ref_diff_py_files"] = len(diff_py)
        if diff_py:
            original_set = set(py_changed)
            py_changed = sorted(original_set.intersection(set(diff_py)))
            if not py_changed:
                py_changed = sorted(original_set)
                warnings.append(
                    WarningItem(
                        code="W_BASE_REF_EMPTY_INTERSECTION",
                        message="base-ref 增量与计划变更无交集，已回退到计划文件集合分析。",
                        details={"base_ref": base_ref},
                    )
                )
            mismatch = sorted(set(changed_ok) - set(diff_files))
            if mismatch:
                w = WarningItem(
                    code="W_BASE_REF_PLAN_MISMATCH",
                    message=f"计划文件与增量 diff 不一致：{len(mismatch)} 个文件未出现在 diff 中",
                    details={"mismatch_files": mismatch[:50]},
                )
                if eff_strict_plan_diff:
                    blockers.append(
                        BlockerItem(
                            id="B03",
                            code="B03_MISSING_IMPACT",
                            message=w.message,
                            details=w.details,
                        )
                    )
                else:
                    warnings.append(w)
        summary["analyzed_py_files"] = py_changed[:50]

    use_cache = cfg.cache_enabled and not no_cache
    cdir = cfg.resolved_cache_dir()
    ck = cache_key(repo, cfg, py_changed)
    cpath_cache = cache_paths(cdir, ck)

    expected: dict[str, Any] | None = None
    all_edges: list[tuple[str, str]] = []
    impact_warnings: list[dict[str, Any]] = []
    if use_cache:
        cached = load_cache(cpath_cache)
        if cached is not None:
            expected = cached.get("expected_impact")
            raw_e = cached.get("edges", [])
            all_edges = [tuple(x) for x in raw_e]  # type: ignore[misc]

    if expected is None:
        expected, impact_warnings, all_edges = build_expected_impact(repo, py_changed, cfg)
        if use_cache:
            save_cache(cpath_cache, {"expected_impact": expected, "edges": list(map(list, all_edges))})

    for w in impact_warnings:
        warnings.append(WarningItem(code=w["code"], message=w["message"], details=w.get("details", {})))

    agg = list(expected.get("aggregated_one_hop", []))
    summary["aggregated_h_count"] = len(agg)
    summary["edge_count"] = int(expected.get("stats", {}).get("edge_count", 0))
    summary["unresolved_imports_count"] = int(expected.get("stats", {}).get("unresolved_count", 0))

    edge_rows, missing, rec_summary = reconcile(
        repo, plan, agg, all_edges, cfg.exemption_paths
    )
    for k, v in rec_summary.items():
        summary[f"reconcile_{k}"] = v

    if missing:
        mf = ", ".join(missing[:20])
        if len(missing) > 20:
            mf += f" … +{len(missing) - 20} more"
        blockers.append(
            BlockerItem(
                id="B03",
                code="B03_MISSING_IMPACT",
                message=msg.B03.format(missing_count=len(missing), missing_files=mf),
                details={"missing": missing},
            )
        )

    b5_block, b5_warn = analyze_style(repo, py_changed, cfg)
    for w in b5_warn:
        warnings.append(WarningItem(code=w["code"], message=w["message"], details=w["details"]))
    for b in b5_block:
        blockers.append(
            BlockerItem(
                id="B05",
                code="B05_STYLE",
                message=msg.B05.format(
                    kind=b["kind"],
                    actual=b["actual"],
                    limit=b["limit"],
                    file=b["file"],
                    name=b["name"],
                ),
                details=b,
            )
        )

    # v0.2 integrations (warning-only)
    rp = ruff_report
    if rp is None and cfg.integrations_ruff_enabled and cfg.integrations_ruff_report_path:
        rp = (repo / cfg.integrations_ruff_report_path).resolve()
    pp = pyright_report
    if pp is None and cfg.integrations_pyright_enabled and cfg.integrations_pyright_report_path:
        pp = (repo / cfg.integrations_pyright_report_path).resolve()
    external_signals.extend(load_ruff_signals(rp))
    external_signals.extend(load_pyright_signals(pp))
    if external_signals:
        for sig in external_signals[:50]:
            if sig.get("source") == "ruff":
                warnings.append(
                    WarningItem(
                        code="W_RUFF_SIGNAL",
                        message=f"ruff: {sig.get('code','')} {sig.get('message','')}",
                        details=sig,
                    )
                )
            elif sig.get("source") == "pyright":
                warnings.append(
                    WarningItem(
                        code="W_PYRIGHT_SIGNAL",
                        message=f"pyright: {sig.get('severity','')} {sig.get('message','')}",
                        details=sig,
                    )
                )
        warnings.append(
            WarningItem(
                code="W_EXTERNAL_SIGNAL",
                message=f"检测到外部工具信号：{len(external_signals)} 条（warning-only）",
                details={"count": len(external_signals)},
            )
        )

    # v0.2 LLM review hook (warning-only)
    llm_warnings = llm_review_warning(cfg.llm_review_enabled, summary)
    warnings.extend(llm_warnings)

    # v0.2 override (file-driven)
    if cfg.override_enabled:
        parsed_ov = parse_override_file(override_file)
        if parsed_ov:
            blockers, overrides_applied, ov_warn = apply_overrides(
                blockers, parsed_ov, allowed_blockers=set(cfg.override_allowed_blockers)
            )
            warnings.extend(ov_warn)

    return _finalize_write(
        blockers,
        warnings,
        summary,
        plan_version=plan.plan_version,
        write_artifacts=write_artifacts,
        out_dir=out_dir,
        repo=repo,
        cfg=cfg,
        artifacts=artifacts,
        intent_path=intent_path,
        expected_impact=expected,
        edge_rows=edge_rows,
        rec_summary=rec_summary,
        overrides_applied=overrides_applied,
        external_signals=external_signals,
        llm_warnings=llm_warnings,
    )


def _finalize_write(
    blockers: list[BlockerItem],
    warnings: list[WarningItem],
    summary: dict[str, Any],
    *,
    plan_version: str,
    write_artifacts: bool,
    out_dir: Path | None,
    repo: Path,
    cfg: GuardConfig,
    artifacts: dict[str, Path],
    intent_path: Path | None,
    expected_impact: dict[str, Any] | None,
    edge_rows: list[dict[str, Any]],
    rec_summary: dict[str, int],
    overrides_applied: list[dict[str, Any]],
    external_signals: list[dict[str, Any]],
    llm_warnings: list[WarningItem],
) -> ValidationResult:
    blocker_ids: list[str] = []
    seen: set[str] = set()
    for b in blockers:
        if b.id not in seen:
            seen.add(b.id)
            blocker_ids.append(b.id)

    exit_code = 1 if blockers else 0
    ok = exit_code == 0
    od = (out_dir or (repo / ".codeguard")).resolve()
    intent_note = str(intent_path) if intent_path else None

    if write_artifacts:
        if expected_impact is not None:
            ei = od / "expected_impact.json"
            write_expected_impact(ei, expected_impact)
            artifacts["expected_impact"] = ei
        rr = od / "reconciliation_report.json"
        write_reconciliation_report(
            rr,
            plan_version=plan_version,
            blocker_ids=blocker_ids,
            blockers=blockers,
            warnings=warnings,
            edges=edge_rows,
            summary=rec_summary,
            config_hash=config_hash_quick(cfg),
            overrides=overrides_applied,
            external_signals=external_signals,
            llm_warnings=llm_warnings,
        )
        artifacts["reconciliation_report"] = rr
        gm = od / "guard_report.md"
        write_guard_report_md(
            gm,
            intent_note=intent_note,
            blockers=blockers,
            warnings=warnings,
            summary=summary,
            overrides=overrides_applied,
        )
        artifacts["guard_report_md"] = gm
        if overrides_applied:
            ptxt = json.dumps(
                {"plan_version": plan_version, "summary": summary, "edge_rows": edge_rows},
                ensure_ascii=False,
                sort_keys=True,
            )
            ph = hashlib.sha256(ptxt.encode()).hexdigest()[:16]
            audit_path = write_override_audit(
                od, overrides_applied=overrides_applied, plan_hash=ph, commit_sha=git_head_sha(repo)
            )
            artifacts["audit_overrides"] = audit_path

    return ValidationResult(
        ok=ok,
        exit_code=exit_code,
        blocker_ids=blocker_ids,
        blockers=blockers,
        warnings=warnings,
        artifacts_paths=artifacts,
        summary=summary,
        fatal_message=None,
        error_kind=None,
        overrides=overrides_applied,
        external_signals=external_signals,
        llm_warnings=[{"code": w.code, "message": w.message, "details": w.details} for w in llm_warnings],
    )
