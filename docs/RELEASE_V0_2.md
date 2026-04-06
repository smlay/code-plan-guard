# code-plan-guard v0.2 发布说明（PRD §15）

## 新增能力（相对 v0.1）

- GitHub Actions：在 `pull_request` 上执行 `code-plan-guard review`，并上传 `.codeguard/` 产物。
- override（v0.2）：支持在文本中写入 `code-plan-guard: override Bxx reason=...`，并生成 `.codeguard/audit_overrides.json` 审计文件。  
  - 默认允许 override：`B03`、`B05`。
  - override 只影响允许的 blocker 集合，不改变 Schema/B02 契约。
- `--base-ref`：当 git ref 可用时，按 `base-ref..HEAD` 的变更集合缩小 analysis 范围（否则回退 v0.1 行为并给出 warning）。
- 外部工具信号复用（warning-only）：读取 ruff/pyright JSON 报告，将其映射为 warning 附在 `reconciliation_report.json`。
- 可选 LLM 二轮审查（warning-only）：开启后只追加 warning，不触发 B01–B04 blocker。

## 配置要点

通过 `.codeguard.yml` / `.code-plan-guard.yml` 配置以下扩展项：

- `override.enabled`、`override.allowed_blockers`
- `integrations.ruff.enabled`、`integrations.ruff.report_path`
- `integrations.pyright.enabled`、`integrations.pyright.report_path`
- `llm_review.enabled` / `llm_review.model`（v0.2 路径默认只做 warning-only mock）

## 已知限制

- override 指令解析为“行级”规则，v0.2 仅支持简单单行形式。
- `--base-ref` 的 diff 依赖 git ref 可解析；当 ref 不存在时不会失败，只会 warning。

## 迁移注意

- 若你在 v0.1 使用默认 CLI：v0.2 新增参数不会破坏兼容。
- 若要在 PR 中使用 override：请确保 CI 侧使用了 `--override-file`（或后续 v0.3 实现的 GitHub comment 抓取机制）。

