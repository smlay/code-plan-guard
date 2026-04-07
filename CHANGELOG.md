+---# Changelog

## 0.3.0

发布日期：2026-04-06

### 新增

- Plan 自动发现：`--plan auto` 支持从配置 `github.plan_path` 与常见路径自动定位计划文件，适配 CI/PR 场景。
- GitHub override（可选）：支持从 PR body 与 issue comments 抓取 override 指令（需要 `gh` 与 token），并在 `.codeguard/audit_overrides.json` 记录更丰富的来源信息（source_type/source_ref/author 等）。
- override 策略（可选）：支持配置 `github.override_allowed_actors` 与 `github.override_min_reason_length`，不符合策略的 override 将被拒绝并输出 warning。
- `reconciliation_report.json` 新增 `context` 字段，记录 GitHub 运行环境元信息（repo/actor/run_id/base_ref/head_ref/pr_number）。
- 新增确定性规则：循环依赖检测（`rules.cycles.enabled`，默认 warning，可配置为 blocker）。
- 增加实验性多语言扫描（warning-only）：对变更的 JS/TS 文件进行 import/require 近似扫描并输出结构化信号（默认关闭）。
- CLI 增强：新增 `--override-from-github` 与 `--print-artifacts-paths`。

### 修复/行为变更

- `--strict-plan-diff` 不再复用 B03：改为 `B09_PLAN_SCOPE_MISMATCH`，并输出更细粒度 mismatch 统计。
- `--json` 输出新增 `result_version=0.3`，用于契约稳定。

## 0.4.0

发布日期：2026-04-06

### 新增

- Plan discovery v2：`--plan auto` 可从 PR body 解析 `plan:` 指针并输出“已尝试来源”错误信息。
- PR 元信息扩展：`reconciliation_report.json` 的 `context` 增强（workflow/job/run_attempt/sha 等）。
- override 来源扩展：issue comments + review comments + fenced override block；支持 label gate。
- override 策略治理：allowed actors/teams（best-effort）、min reason、sha 绑定、最小复核人数（N-of-M）。
- override 审计升级：`audit_overrides.json` schema_version=`0.3`，记录 raw/sha/source 等。
- 规则扩展：B06 支持可选 expand_one_hop；新增 B07（verification_steps 缺失，warning/block 可配）。
- 性能/缓存：阈值可配置（max_changed_files/max_file_bytes）；summary 记录 cache hit/miss 与 key prefix。
- 多语言：启发式增强 + tree-sitter 可选接入（缺依赖自动降级 warning-only）。
- CLI：`--json` 输出 `result_version=0.4`，新增 `--plan-source`、`--dump-context`。

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

