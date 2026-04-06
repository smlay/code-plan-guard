# Changelog

## 0.2.0

发布日期：2026-04-06

### 新增

- GitHub Actions 集成：在 PR 上执行 `code-plan-guard review`，并上传 `.codeguard/` 产物（`expected_impact.json`、`reconciliation_report.json`、`guard_report.md`、`audit_overrides.json`）。
- Override（人类豁免）v0.2：通过文本指令解析 override，并输出 `.codeguard/audit_overrides.json` 审计文件；override 仅影响允许的 blocker 集合。
- `--base-ref` 增量范围参与分析：当 git ref 可用时，按 `base-ref..HEAD` 的变更集合缩小分析范围，并记录 base-ref 相关摘要。
- 外部工具信号复用（warning-only）：支持读取 ruff/pyright JSON 报告，将结果映射为 warning 写入 `reconciliation_report.json`。
- 可选 LLM 二轮审查钩子（warning-only）：启用后仅输出 warning，不触发 B01–B04 blocker。
- CLI 输出增强：新增 `--override-file`、`--ruff-report`、`--pyright-report`、`--strict-plan-diff/--no-strict-plan-diff` 与 `--json`。

### 修复/行为变更

- `reconciliation_report.json` 现在包含 `overrides` / `external_signals` / `llm_warnings` 等 v0.2 相关字段（在 v0.1 基础上扩展）。

### 已知限制

- v0.2 的 override 解析仅支持简单单行指令；更复杂的 PR comment 抓取/多消息合并在 v0.3+ 扩展。
- `--base-ref` 增量依赖 git ref 可解析；ref 不可用时仅记录 warning。

