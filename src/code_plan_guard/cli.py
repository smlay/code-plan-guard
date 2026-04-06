"""§5.1 CLI entry."""

from __future__ import annotations

import sys
import json
from dataclasses import asdict
from pathlib import Path

import click

from code_plan_guard.pipeline import validate_plan


@click.group()
def main() -> None:
    """code-plan-guard — 计划阶段完整性门卫 (PRD v0.1)."""


@main.command("review")
@click.option("--plan", "plan_path", required=True, type=click.Path(path_type=Path, exists=True))
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
@click.option("--strict-plan-diff/--no-strict-plan-diff", default=None)
@click.option("--json", "json_output", is_flag=True, default=False)
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
    strict_plan_diff: bool | None,
    json_output: bool,
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
        strict_plan_diff=strict_plan_diff,
    )
    if json_output:
        payload = {
            "ok": r.ok,
            "exit_code": r.exit_code,
            "blocker_ids": r.blocker_ids,
            "blockers": [asdict(x) for x in r.blockers],
            "warnings": [asdict(x) for x in r.warnings],
            "artifacts_paths": {k: str(v) for k, v in r.artifacts_paths.items()},
            "summary": r.summary,
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
    sys.exit(r.exit_code)


if __name__ == "__main__":
    main()
