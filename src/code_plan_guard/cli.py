"""§5.1 CLI entry."""

from __future__ import annotations

import sys
import json
from dataclasses import asdict
from pathlib import Path

import click
import yaml

from code_plan_guard.pipeline import validate_plan
from code_plan_guard.report_cli import load_json, summarize_reconciliation
from code_plan_guard.audit_cli import summarize_audits


def _ensure_utf8_stdio() -> None:
    """Best-effort fix for Windows console mojibake."""

    def _reconfigure(stream: object) -> None:
        try:
            # Python 3.7+: io.TextIOWrapper has reconfigure()
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            return

    _reconfigure(sys.stdout)
    _reconfigure(sys.stderr)


@click.group()
def main() -> None:
    """code-plan-guard — 计划阶段完整性门卫 (PRD v0.1)."""
    _ensure_utf8_stdio()


def _write_text(path: Path, text: str, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise click.ClickException(f"文件已存在：{path}（用 --force 覆盖）")
    path.write_text(text, encoding="utf-8")


@main.command("init")
@click.option("--repo", "repo_path", required=True, type=click.Path(path_type=Path, exists=True, dir_okay=True))
@click.option("--force", is_flag=True, default=False)
def init(repo_path: Path, force: bool) -> None:
    """一键生成最小接入文件（配置/plan 模板/说明）。"""
    repo = repo_path.resolve()
    cfg_path = repo / ".codeguard.yml"
    plan_path = repo / ".codeguard" / "plan.yaml"
    _write_text(
        cfg_path,
        yaml.safe_dump(
            {
                "version": "1",
                "github": {"plan_path": ".codeguard/plan.yaml"},
                "rules": {
                    "plan_quality": {"enabled": True, "severity": "warning"},
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        force=force,
    )
    _write_text(
        plan_path,
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: src/example.py\n"
        '    summary: "describe your change"\n'
        "    impacted_files:\n"
        "      - src/example_dep.py\n"
        "global_analysis:\n"
        "  dependency_graph_summary: \"\"\n"
        "  verification_steps:\n"
        "    - \"run: python -m pytest -q\"\n"
        "risks_and_rollback:\n"
        "  - risk: \"describe risk\"\n"
        "    mitigation: \"describe mitigation / rollback\"\n",
        force=force,
    )
    click.echo(f"已生成：{cfg_path}")
    click.echo(f"已生成：{plan_path}")
    click.echo("下一步：运行 `code-plan-guard review --plan auto --repo .`")


@main.group("plan")
def plan_group() -> None:
    """计划相关子命令。"""


@plan_group.command("new")
@click.option("--out", "out_path", required=True, type=click.Path(path_type=Path))
@click.option("--force", is_flag=True, default=False)
def plan_new(out_path: Path, force: bool) -> None:
    """生成 plan skeleton。"""
    _write_text(
        out_path,
        'plan_version: "0.1"\n'
        "changes:\n"
        "  - file: path/to/changed_file.py\n"
        '    summary: "what and why"\n'
        "    impacted_files:\n"
        "      - path/to/impacted_file.py\n"
        "global_analysis:\n"
        "  dependency_graph_summary: \"\"\n"
        "  verification_steps:\n"
        "    - \"run: python -m pytest -q\"\n"
        "risks_and_rollback:\n"
        "  - risk: \"risk\"\n"
        "    mitigation: \"rollback/mitigation\"\n",
        force=force,
    )
    click.echo(f"已生成：{out_path}")


@plan_group.command("lint")
@click.option("--plan", "plan_path", required=True, type=click.Path(path_type=Path, exists=True))
def plan_lint(plan_path: Path) -> None:
    """对 plan 做确定性 lint（不依赖仓库文件）。"""
    raw = plan_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    issues: list[str] = []
    if not isinstance(data, dict):
        raise click.ClickException("plan 根节点必须是 mapping")
    if data.get("plan_version") != "0.1":
        issues.append("plan_version 必须为 0.1")
    changes = data.get("changes")
    if not isinstance(changes, list) or not changes:
        issues.append("changes 必须为非空数组")
    ga = data.get("global_analysis")
    if not isinstance(ga, dict):
        issues.append("global_analysis 必须为对象")
    else:
        vs = ga.get("verification_steps")
        if not (isinstance(vs, list) and any(str(x).strip() for x in vs)):
            issues.append("global_analysis.verification_steps 不能为空（至少 1 条）")
    rr = data.get("risks_and_rollback")
    if not isinstance(rr, list) or not rr:
        issues.append("risks_and_rollback 不能为空（至少 1 条）")
    if issues:
        for x in issues:
            click.echo(f"- {x}", err=True)
        raise SystemExit(1)
    click.echo("OK")


@main.group("report")
def report_group() -> None:
    """产物查看器。"""


@report_group.command("show")
@click.option("--path", "path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--json", "as_json", is_flag=True, default=False)
def report_show(path: Path, as_json: bool) -> None:
    """显示 artifacts 摘要。"""
    p = path
    if p.is_dir():
        p = p / "reconciliation_report.json"
    report = load_json(p)
    summary = summarize_reconciliation(report)
    if as_json:
        click.echo(json.dumps({"summary": summary, "report_path": str(p)}, ensure_ascii=False))
    else:
        click.echo(f"report={p}")
        for k, v in summary.items():
            click.echo(f"{k}={v}")


@report_group.command("diff")
@click.option("--a", "a_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--b", "b_path", required=True, type=click.Path(path_type=Path, exists=True))
def report_diff(a_path: Path, b_path: Path) -> None:
    """对比两个 reconciliation_report（粗粒度）。"""
    ra = load_json(a_path if a_path.is_file() else (a_path / "reconciliation_report.json"))
    rb = load_json(b_path if b_path.is_file() else (b_path / "reconciliation_report.json"))
    sa = summarize_reconciliation(ra)
    sb = summarize_reconciliation(rb)
    click.echo(f"a={a_path}")
    click.echo(f"b={b_path}")
    for k in sorted(set(sa) | set(sb)):
        if sa.get(k) != sb.get(k):
            click.echo(f"- {k}: {sa.get(k)} -> {sb.get(k)}")


@main.group("audit")
def audit_group() -> None:
    """审计工具。"""


@audit_group.command("summarize")
@click.option("--path", "path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--json", "as_json", is_flag=True, default=False)
def audit_summarize(path: Path, as_json: bool) -> None:
    s = summarize_audits(path)
    if as_json:
        click.echo(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        for k, v in s.items():
            click.echo(f"{k}={v}")


@main.command("review")
@click.option(
    "--plan",
    "plan_path",
    required=True,
    type=click.Path(path_type=Path, exists=False),
    help='计划文件路径；也可传 "auto" 启用自动发现（用于 CI/PR）。',
)
@click.option(
    "--repo",
    "repo_path",
    required=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True, exists=True),
)
@click.option("--intent", "intent_path", type=click.Path(path_type=Path, exists=True), default=None)
@click.option("--base-ref", default="main", show_default=True)
@click.option("--out-dir", type=click.Path(path_type=Path), default=None)
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=None)
@click.option("--no-cache", is_flag=True, default=False)
@click.option("--override-file", type=click.Path(path_type=Path, exists=True), default=None)
@click.option("--ruff-report", type=click.Path(path_type=Path, exists=True), default=None)
@click.option("--pyright-report", type=click.Path(path_type=Path, exists=True), default=None)
@click.option("--mypy-report", type=click.Path(path_type=Path, exists=True), default=None)
@click.option("--semgrep-report", type=click.Path(path_type=Path, exists=True), default=None)
@click.option("--strict-plan-diff/--no-strict-plan-diff", default=None)
@click.option(
    "--override-from-github/--no-override-from-github",
    default=None,
    help="是否从 GitHub PR body/comments 拉取 override（需要 gh + token）。默认跟随配置。",
)
@click.option("--json", "json_output", is_flag=True, default=False)
@click.option(
    "--print-artifacts-paths",
    is_flag=True,
    default=False,
    help="在文本模式下额外输出 artifacts 路径（便于 CI 脚本消费）。",
)
@click.option("--plan-source", is_flag=True, default=False, help="输出 plan 自动发现来源（调试用）。")
@click.option("--dump-context", is_flag=True, default=False, help="输出将写入 report 的 context（调试用）。")
def review(
    plan_path: Path,
    repo_path: Path,
    intent_path: Path | None,
    base_ref: str,
    out_dir: Path | None,
    config_path: Path | None,
    no_cache: bool,
    override_file: Path | None,
    ruff_report: Path | None,
    pyright_report: Path | None,
    mypy_report: Path | None,
    semgrep_report: Path | None,
    strict_plan_diff: bool | None,
    override_from_github: bool | None,
    json_output: bool,
    print_artifacts_paths: bool,
    plan_source: bool,
    dump_context: bool,
) -> None:
    """校验计划文件与仓库静态影响面。"""
    r = validate_plan(
        plan_path,
        repo_path,
        write_artifacts=True,
        out_dir=out_dir,
        config_path=config_path,
        intent_path=intent_path,
        base_ref=base_ref,
        no_cache=no_cache,
        override_file=override_file,
        ruff_report=ruff_report,
        pyright_report=pyright_report,
        mypy_report=mypy_report,
        semgrep_report=semgrep_report,
        strict_plan_diff=strict_plan_diff,
        override_from_github=override_from_github,
    )
    if json_output:
        payload = {
            "result_version": "0.4",
            "ok": r.ok,
            "exit_code": r.exit_code,
            "blocker_ids": r.blocker_ids,
            "blockers": [asdict(x) for x in r.blockers],
            "warnings": [asdict(x) for x in r.warnings],
            "artifacts_paths": {k: str(v) for k, v in r.artifacts_paths.items()},
            "summary": r.summary,
            "context": r.context,
            "fatal_message": r.fatal_message,
            "error_kind": r.error_kind,
            "overrides": r.overrides,
            "external_signals": r.external_signals,
            "llm_warnings": r.llm_warnings,
        }
        click.echo(json.dumps(payload, ensure_ascii=False))
        sys.exit(r.exit_code)
    if r.exit_code == 2:
        # code-plan-guard-prd:§5.4 — stderr for fatal
        if r.fatal_message:
            click.echo(r.fatal_message, err=True)
        sys.exit(2)
    if r.blockers:
        for b in r.blockers:
            click.echo(b.message, err=True)
    if r.warnings:
        for w in r.warnings:
            click.echo(w.message, err=False)
    if plan_source:
        click.echo(f"plan_source={r.summary.get('plan_source','')}", err=False)
    if dump_context:
        click.echo(json.dumps(r.context, ensure_ascii=False, indent=2), err=False)
    if print_artifacts_paths and r.artifacts_paths:
        for k, v in r.artifacts_paths.items():
            click.echo(f"artifact[{k}]={v}", err=False)
    sys.exit(r.exit_code)


if __name__ == "__main__":
    main()
