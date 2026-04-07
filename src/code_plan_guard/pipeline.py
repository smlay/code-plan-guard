"""§4 orchestration: validate_plan."""

from __future__ import annotations

import subprocess
import hashlib
import json
import os
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
    write_signals_json,
)
from code_plan_guard.constants import __version__
from code_plan_guard.result import BlockerItem, ValidationResult, WarningItem
from code_plan_guard.schema import PlanModel
from code_plan_guard.style import analyze_style
from code_plan_guard.cycles import find_any_cycle
from code_plan_guard.lang_scan import scan_js_ts_imports
from code_plan_guard.tree_sitter_scan import scan_js_ts_with_tree_sitter
from code_plan_guard.languages import JsTsPlugin
from code_plan_guard.languages.registry import run_language_plugins
from code_plan_guard.plan_quality import link_external_signals_to_plan, score_plan_quality
from code_plan_guard.rule_layers import build_rule_layers
from code_plan_guard.v02 import (
    apply_overrides,
    git_changed_files,
    git_head_sha,
    llm_review_warning,
    load_pyright_signals,
    load_ruff_signals,
)
from code_plan_guard.v03 import (
    OverrideDirective,
    build_override_audit_payload,
    fetch_pr_body,
    labels_from_github_pr,
    overrides_from_file,
    overrides_from_github_pr,
    overrides_from_github_review_comments,
    plan_path_from_pr_body,
    members_of_team,
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
    mypy_report: Path | None = None,
    semgrep_report: Path | None = None,
    strict_plan_diff: bool | None = None,
    override_from_github: bool | None = None,
) -> ValidationResult:
    repo = Path(repo_path).resolve()
    plan_p_raw = Path(plan_path)
    # v0.3: allow "auto" discovery for CI/PR usage.
    if str(plan_path).strip().lower() == "auto":
        plan_p = None
    else:
        plan_p = plan_p_raw.resolve()
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
    override_directives: list[OverrideDirective] = []
    blockers_before_override: list[str] = []
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

    eff_override_from_github = cfg.github_override_enabled if override_from_github is None else override_from_github

    if plan_p is None:
        tried: list[str] = []
        candidates: list[Path] = []
        # 1) config path
        if cfg.github_plan_path:
            p = (repo / cfg.github_plan_path)
            candidates.append(p)
            tried.append(f"config:github.plan_path={cfg.github_plan_path}")

        # 2) PR explicit pointer (best-effort)
        pr_body, pr_warns = fetch_pr_body(repo)
        warnings.extend(pr_warns)
        if pr_body:
            pr_plan = plan_path_from_pr_body(pr_body)
            if pr_plan:
                candidates.append(repo / pr_plan)
                tried.append(f"pr_body:plan_ref={pr_plan}")

        # 3) conventions
        for p in [
            repo / "docs" / "plan.yaml",
            repo / ".codeguard" / "plan.yaml",
            repo / "plan.yaml",
            repo / "examples" / "minimal-plan.yaml",
        ]:
            candidates.append(p)
            tried.append(f"convention:{p.relative_to(repo).as_posix()}")

        found = next((p for p in candidates if p.is_file()), None)
        if found is None:
            plan_msg = "未找到 plan 文件。已尝试：\n- " + "\n- ".join(tried[:20])
            if len(tried) > 20:
                plan_msg += f"\n- … +{len(tried) - 20} more"
            plan_msg += "\n建议：设置 github.plan_path，或在 PR body 写 `plan: path/to/plan.yaml`，或传入 --plan <path>。"
            return ValidationResult.fatal(plan_msg, "PLAN_NOT_FOUND")
        plan_p = found.resolve()
        summary["plan_source"] = tried[candidates.index(found)] if found in candidates else "auto"

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
    if len(changed_ok) > int(cfg.perf_max_changed_files):
        warnings.append(
            WarningItem(
                code="W_TOO_MANY_CHANGED_FILES",
                message="变更文件过多，已降级仅分析前 N 个文件（确定性截断）。",
                details={"changed_files": len(changed_ok), "max_changed_files": int(cfg.perf_max_changed_files)},
            )
        )
        changed_ok = changed_ok[: int(cfg.perf_max_changed_files)]
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
        plan_not_in_diff = sorted(set(changed_ok) - set(diff_files))
        diff_not_in_plan = sorted(set(diff_files) - set(changed_ok))
        summary["plan_scope_plan_not_in_diff"] = len(plan_not_in_diff)
        summary["plan_scope_diff_not_in_plan"] = len(diff_not_in_plan)
        if plan_not_in_diff or diff_not_in_plan:
            details: dict[str, Any] = {
                "plan_not_in_diff": plan_not_in_diff[:50],
                "diff_not_in_plan": diff_not_in_plan[:50],
            }
            w = WarningItem(
                code="W_PLAN_SCOPE_MISMATCH",
                message=(
                    "计划与 base-ref 增量 diff 不一致："
                    f"plan_not_in_diff={len(plan_not_in_diff)} "
                    f"diff_not_in_plan={len(diff_not_in_plan)}"
                ),
                details=details,
            )
            if eff_strict_plan_diff:
                blockers.append(
                    BlockerItem(
                        id="B09",
                        code="B09_PLAN_SCOPE_MISMATCH",
                        message=w.message,
                        details=w.details,
                    )
                )
            else:
                warnings.append(w)

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
            summary["cache"] = "hit"
            summary["cache_key_prefix"] = ck[:12]
        else:
            summary["cache"] = "miss"
            summary["cache_key_prefix"] = ck[:12]
    else:
        summary["cache"] = "disabled"

    if expected is None:
        expected, impact_warnings, all_edges = build_expected_impact(repo, py_changed, cfg)
        if use_cache:
            save_cache(cpath_cache, {"expected_impact": expected, "edges": list(map(list, all_edges))})

    # final: multi-language truth (additive; never blocks)
    lang_truth, _lang_edges, lang_warns = run_language_plugins(repo, changed_ok, [JsTsPlugin()])
    expected["language_truth"] = {
        "schema_version": lang_truth.schema_version,
        "per_file": lang_truth.per_file,
        "aggregated_targets": lang_truth.aggregated_targets,
        "edges": lang_truth.edges,
        "warnings": lang_truth.warnings,
    }
    for w in lang_warns[:50]:
        warnings.append(
            WarningItem(
                code="W_LANGUAGE_TRUTH",
                message=w.message,
                details={"code": w.code, "language": w.language, "source": w.source, "details": w.details},
            )
        )

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
    # final: mypy/semgrep (warning-only)
    if mypy_report is not None or semgrep_report is not None:
        from code_plan_guard.integrations import load_mypy_signals, load_semgrep_signals

        external_signals.extend(load_mypy_signals(mypy_report))
        external_signals.extend(load_semgrep_signals(semgrep_report))
    if external_signals:
        # H2: link signals to plan scope (best-effort; reporting only)
        plan_changed_files = sorted({c.file.replace("\\", "/") for c in plan.changes})
        plan_impacted_files: list[str] = []
        for c in plan.changes:
            if c.impacted_files:
                plan_impacted_files.extend([x.replace("\\", "/") for x in c.impacted_files])
        external_signals = link_external_signals_to_plan(
            plan_changed_files=plan_changed_files,
            plan_impacted_files=sorted(set(plan_impacted_files)),
            external_signals=external_signals,
        )
        summary["external_signals_total"] = len(external_signals)
        summary["external_signals_linked_change"] = sum(1 for s in external_signals if s.get("linked_change"))
        summary["external_signals_linked_impacted"] = sum(1 for s in external_signals if s.get("linked_impacted"))

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
            elif sig.get("source") == "mypy":
                warnings.append(
                    WarningItem(
                        code="W_MYPY_SIGNAL",
                        message=f"mypy: {sig.get('code','')} {sig.get('message','')}",
                        details=sig,
                    )
                )
            elif sig.get("source") == "semgrep":
                warnings.append(
                    WarningItem(
                        code="W_SEMGREP_SIGNAL",
                        message=f"semgrep: {sig.get('code','')} {sig.get('message','')}",
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

    # H3: plan quality score (non-blocking; always-on for reporting)
    pq = score_plan_quality(plan)
    summary["plan_quality_score"] = pq.score
    summary["plan_quality_reasons"] = pq.reasons
    if pq.score < 70:
        warnings.append(
            WarningItem(
                code="W_PLAN_QUALITY_SCORE",
                message=f"计划质量评分偏低（score={pq.score}，仅提示不阻塞）。",
                details={"score": pq.score, "reasons": pq.reasons},
            )
        )

    # v0.4 plan quality rule (deterministic; default off)
    if cfg.plan_quality_enabled:
        vs = plan.global_analysis.get("verification_steps") if isinstance(plan.global_analysis, dict) else None
        ok_vs = isinstance(vs, list) and any(str(x).strip() for x in vs)
        if not ok_vs:
            if cfg.plan_quality_severity == "block":
                blockers.append(
                    BlockerItem(
                        id="B07",
                        code="B07_MISSING_VERIFICATION_STEPS",
                        message=msg.B07,
                        details={},
                    )
                )
            else:
                warnings.append(WarningItem(code="W_PLAN_QUALITY", message=msg.B07, details={}))

    # v0.2 LLM review hook (warning-only)
    llm_warnings = llm_review_warning(cfg.llm_review_enabled, summary)
    warnings.extend(llm_warnings)

    # E1: rule layer snapshot (report-only; additive)
    summary["rule_layers"] = build_rule_layers(blockers=blockers, warnings=warnings, llm_warnings=llm_warnings)

    # v0.3 experimental language scan (warning-only; default off)
    if cfg.languages_enabled:
        if cfg.tree_sitter_enabled:
            ts_sigs, ts_warn = scan_js_ts_with_tree_sitter(repo, changed_ok)
            warnings.extend(ts_warn)
            if ts_sigs:
                external_signals.extend(ts_sigs)
        sigs = scan_js_ts_imports(repo, changed_ok)
        if sigs:
            external_signals.extend(sigs)
            for sig in sigs[:50]:
                warnings.append(
                    WarningItem(
                        code="W_LANG_IMPORT",
                        message=f"lang-scan: {sig.get('path')} imports {sig.get('import_target')}",
                        details=sig,
                    )
                )

    # v0.4 cycles rule (deterministic; default off; optional 1-hop expansion)
    if cfg.cycles_enabled:
        cyc = find_any_cycle(all_edges)
        if cyc is None and cfg.cycles_expand_one_hop:
            # Expand analysis set by including 1-hop target files (bounded).
            extra = [x for x in agg if x.endswith(".py")]
            if len(extra) > int(cfg.cycles_max_extra_files):
                warnings.append(
                    WarningItem(
                        code="W_CYCLE_EXPAND_SKIPPED",
                        message="循环检测扩展扫描已跳过：extra files 超过阈值",
                        details={"extra_files": len(extra), "max_extra_files": int(cfg.cycles_max_extra_files)},
                    )
                )
            else:
                expanded = sorted(set(py_changed) | set(extra))
                exp_expected, exp_w, exp_edges = build_expected_impact(repo, expanded, cfg)
                for w in exp_w:
                    warnings.append(
                        WarningItem(code=w["code"], message=w["message"], details=w.get("details", {}))
                    )
                cyc = find_any_cycle(exp_edges)
        if cyc:
            cycle_s = " -> ".join(cyc)
            if cfg.cycles_severity == "block":
                blockers.append(
                    BlockerItem(
                        id="B06",
                        code="B06_CYCLE_DETECTED",
                        message=msg.B06.format(cycle=cycle_s),
                        details={"cycle": cyc},
                    )
                )
            else:
                warnings.append(
                    WarningItem(
                        code="W_CYCLE_DETECTED",
                        message=msg.B06.format(cycle=cycle_s),
                        details={"cycle": cyc},
                    )
                )

    # v0.3 override (file + optional GitHub sources)
    if cfg.override_enabled:
        override_directives.extend(overrides_from_file(override_file))
        if eff_override_from_github:
            gh_dirs, gh_warn = overrides_from_github_pr(repo)
            override_directives.extend(gh_dirs)
            warnings.extend(gh_warn)
            rv_dirs, rv_warn = overrides_from_github_review_comments(repo)
            override_directives.extend(rv_dirs)
            warnings.extend(rv_warn)

            # Optional label gate: require certain labels to accept any non-file overrides.
            req_labels = set(x for x in cfg.github_override_required_labels if str(x).strip())
            if req_labels:
                labels, lab_warn = labels_from_github_pr(repo)
                warnings.extend(lab_warn)
                present = set(labels)
                if not (present & req_labels):
                    warnings.append(
                        WarningItem(
                            code="W_OVERRIDE_POLICY_REJECTED",
                            message="override 被策略拒绝：缺少 required label",
                            details={"required_labels": sorted(req_labels), "present_labels": sorted(present)},
                        )
                    )
                    override_directives = [d for d in override_directives if d.source_type == "file"]
        if override_directives:
            # v0.3 override policy (best-effort; warning-only rejections)
            allowed = set(x for x in cfg.github_override_allowed_actors if str(x).strip())
            for t in cfg.github_override_allowed_teams:
                mem, w = members_of_team(repo, str(t))
                warnings.extend(w)
                allowed |= set(mem)
            filtered: list[OverrideDirective] = []
            for d in override_directives:
                if d.source_type != "file":
                    if allowed and (not d.author or d.author not in allowed):
                        warnings.append(
                            WarningItem(
                                code="W_OVERRIDE_POLICY_REJECTED",
                                message="override 被策略拒绝：author 不在允许列表",
                                details={
                                    "blocker_id": d.blocker_id,
                                    "author": d.author,
                                    "allowed_actors": sorted(allowed),
                                    "source_type": d.source_type,
                                    "source_ref": d.source_ref,
                                },
                            )
                        )
                        continue
                    if len(d.reason) < int(cfg.override_min_reason_length):
                        warnings.append(
                            WarningItem(
                                code="W_OVERRIDE_POLICY_REJECTED",
                                message="override 被策略拒绝：reason 太短",
                                details={
                                    "blocker_id": d.blocker_id,
                                    "reason_length": len(d.reason),
                                    "min_reason_length": int(cfg.override_min_reason_length),
                                    "source_type": d.source_type,
                                    "source_ref": d.source_ref,
                                },
                            )
                        )
                        continue
                    if d.sha and not git_head_sha(repo).startswith(d.sha):
                        warnings.append(
                            WarningItem(
                                code="W_OVERRIDE_POLICY_REJECTED",
                                message="override 被策略拒绝：sha 不匹配当前 HEAD",
                                details={
                                    "blocker_id": d.blocker_id,
                                    "sha": d.sha,
                                    "head_sha": git_head_sha(repo),
                                    "source_type": d.source_type,
                                    "source_ref": d.source_ref,
                                },
                            )
                        )
                        continue
                filtered.append(d)
            # N-of-M approvers: require N distinct authors per blocker_id for non-file directives
            n = max(1, int(cfg.github_override_min_approvers))
            by: dict[str, set[str]] = {}
            for d in filtered:
                if d.source_type == "file":
                    continue
                if d.author:
                    by.setdefault(d.blocker_id, set()).add(d.author)
            final: list[OverrideDirective] = []
            for d in filtered:
                if d.source_type == "file":
                    final.append(d)
                    continue
                if len(by.get(d.blocker_id, set())) >= n:
                    final.append(d)
                else:
                    warnings.append(
                        WarningItem(
                            code="W_OVERRIDE_POLICY_REJECTED",
                            message="override 被策略拒绝：未满足最小复核人数",
                            details={
                                "blocker_id": d.blocker_id,
                                "min_approvers": n,
                                "distinct_authors": sorted(by.get(d.blocker_id, set())),
                            },
                        )
                    )
            override_directives = final

            blockers_before_override = [b.id for b in blockers]
            parsed_ov = [{"blocker_id": d.blocker_id, "reason": d.reason} for d in override_directives]
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
        override_directives=override_directives,
        blockers_before_override=blockers_before_override,
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
    override_directives: list[OverrideDirective],
    blockers_before_override: list[str],
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
    ctx: dict[str, Any] = {}

    if write_artifacts:
        if expected_impact is not None:
            ei = od / "expected_impact.json"
            write_expected_impact(ei, expected_impact)
            artifacts["expected_impact"] = ei
        rr = od / "reconciliation_report.json"
        ctx = {
            "github_repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "github_actor": os.environ.get("GITHUB_ACTOR", ""),
            "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "github_workflow": os.environ.get("GITHUB_WORKFLOW", ""),
            "github_job": os.environ.get("GITHUB_JOB", ""),
            "github_base_ref": os.environ.get("GITHUB_BASE_REF", ""),
            "github_head_ref": os.environ.get("GITHUB_HEAD_REF", ""),
            "pr_number": os.environ.get("GITHUB_PR_NUMBER", "") or os.environ.get("PR_NUMBER", ""),
            "github_sha": os.environ.get("GITHUB_SHA", ""),
            "config_snapshot_hash": config_hash_quick(cfg),
            "tool_version": __version__,
        }
        write_reconciliation_report(
            rr,
            plan_version=plan_version,
            blocker_ids=blocker_ids,
            blockers=blockers,
            warnings=warnings,
            edges=edge_rows,
            summary=summary,
            context=ctx,
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
        if external_signals:
            sj = od / "signals.json"
            write_signals_json(sj, external_signals)
            artifacts["signals_json"] = sj
        if overrides_applied:
            ptxt = json.dumps(
                {"plan_version": plan_version, "summary": summary, "edge_rows": edge_rows},
                ensure_ascii=False,
                sort_keys=True,
            )
            ph = hashlib.sha256(ptxt.encode()).hexdigest()[:16]
            payload = build_override_audit_payload(
                overrides_applied=overrides_applied,
                directives=override_directives,
                plan_hash=ph,
                commit_sha=git_head_sha(repo),
                blockers_before=blockers_before_override,
                blockers_after=[b.id for b in blockers],
            )
            audit_path = od / "audit_overrides.json"
            audit_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            artifacts["audit_overrides"] = audit_path

    return ValidationResult(
        ok=ok,
        exit_code=exit_code,
        blocker_ids=blocker_ids,
        blockers=blockers,
        warnings=warnings,
        artifacts_paths=artifacts,
        summary=summary,
        context=ctx,
        fatal_message=None,
        error_kind=None,
        overrides=overrides_applied,
        external_signals=external_signals,
        llm_warnings=[{"code": w.code, "message": w.message, "details": w.details} for w in llm_warnings],
    )
