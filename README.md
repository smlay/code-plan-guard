# code-plan-guard

[English](README.md) | [简体中文](README.zh-CN.md)

Plan-stage Integrity Guard for AI-generated (or human-written) change plans.
It enforces **deterministic** checks *before* code execution:

- Plan schema validation
- Static import “ground truth” (`expected_impact.json`)
- Reconciliation between declared impact and inferred impact

This project intentionally **does not** rely on LLM output as a blocker signal.

## Table of contents

- [Why](#why)
- [What it does](#what-it-does)
- [Install](#install)
- [Quick start](#quick-start)
- [Artifacts](#artifacts)
- [Configuration](#configuration)
- [Version highlights](#version-highlights)
- [Honest boundaries](#honest-boundaries)
- [Development](#development)
- [License](#license)

## Why

AI coding assistants can create technical debt by skipping impact analysis.
`code-plan-guard` adds a **plan-stage gate** so “what will be impacted” is explicit,
auditable, and consistently enforced.

## What it does

Given a plan file (YAML/JSON) describing intended changes, the guard:

- Validates the plan shape and required fields (schema)
- Builds static dependency truth for Python imports (and optional language truth)
- Reconciles inferred 1-hop (or multi-hop) impact vs declared impacted files
- Writes machine-readable artifacts for CI, reporting, and auditing

## Install

Requires **Python 3.10+**.

```bash
# development
pip install -e ".[dev]"

# (after publishing) pip install code-plan-guard
```

## Quick start

```bash
code-plan-guard review --plan path/to/plan.yaml --repo .
```

Common options:

- `--out-dir`, `--config`, `--intent`
- `--base-ref` (incremental scope based on git diff)
- `--no-cache`
- `--override-file` (local override simulation)
- `--override-from-github` (optional: pull overrides from PR body/comments; requires `gh` + token)
- `--ruff-report`, `--pyright-report`, `--mypy-report`, `--semgrep-report` (warning-only signals)
- `--json` (machine-readable CLI output)
- `--plan auto` (auto-discover plan path in CI/PR)

### Python API

```python
from pathlib import Path
from code_plan_guard import validate_plan

r = validate_plan(
    Path("plan.yaml"),
    Path("."),
    write_artifacts=True,
    base_ref="main",
)
print(r.exit_code, r.ok, r.blocker_ids)
```

## Artifacts

By default artifacts are written to `<repo>/.codeguard/`:

- `expected_impact.json` — static analysis ground truth
- `reconciliation_report.json` — reconciliation details + warnings + context
- `guard_report.md` — human-readable summary
- `signals.json` — external tool signals (optional)
- `audit_overrides.json` — override audit trail (optional)

## Configuration

Place `.codeguard.yml` or `.code-plan-guard.yml` at repo root.
Unknown keys are ignored by design (forward compatibility).

Useful docs:

- `docs/INTEGRATION.md` (CI + local git hooks)
- `docs/PLAN_CONVENTIONS.md` (plan naming + auto-discovery)
- `docs/OVERRIDE_POLICY_v0_4.md` (override governance)
- `docs/SCHEMA_POLICY.md` (artifact schema versioning)

## Version highlights

For the complete list, see [`CHANGELOG.md`](CHANGELOG.md).

### 0.4.0 (2026-04-06)

- Plan discovery v2: `--plan auto` + PR body `plan:` pointer
- Richer GitHub runtime context in `reconciliation_report.json`
- Override governance: actors/teams, label gate, SHA binding, N-of-M reviewers (best-effort)
- New/expanded rules: cycles (optional 1-hop expansion), verification steps quality rule (configurable)
- Performance thresholds + deterministic degradation
- Experimental language truth (JS/TS heuristic + optional tree-sitter fallback)

### 0.3.0 (2026-04-06)

- GitHub override ingestion (PR body/comments) + richer audit payloads
- `context` field in `reconciliation_report.json`
- Cycle detection rule (configurable severity)
- Experimental multi-language scan (warning-only)

### 0.2.0 (2026-04-06)

- GitHub Actions integration example
- Human overrides + `audit_overrides.json`
- `--base-ref` incremental analysis
- External tool signals: ruff / pyright (warning-only)
- Optional LLM review hook (warning-only)

## Honest boundaries

- **Not a replacement for PR review**: passing the guard does not guarantee architectural correctness.
- **Static analysis**: dynamic imports / `importlib` / string loading are best-effort.
- **Non-Python change items**: path existence is checked, but Python import truth is only for `.py`.
- **LLM (if enabled)**: warnings only; must never become a blocker signal.

## Development

```bash
python -m pytest -q
```

## License

MIT. See [`LICENSE`](LICENSE).
