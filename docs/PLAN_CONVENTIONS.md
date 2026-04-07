# Plan 约定与来源策略

## 推荐的仓库约定

- 计划文件固定在：`.codeguard/plan.yaml`
- 配置文件固定在：`.codeguard.yml`

## `--plan auto` 的发现顺序（确定性）

1. `github.plan_path`（配置显式指定）
2. PR body 中的显式指针：
   - `plan: path/to/plan.yaml`
   - 或 markdown 链接：`[plan](path/to/plan.yaml)`
3. 约定路径（按顺序）：
   - `docs/plan.yaml`
   - `.codeguard/plan.yaml`
   - `plan.yaml`
   - `examples/minimal-plan.yaml`

## 最小可操作性要求（推荐）

建议在 `global_analysis.verification_steps` 至少写 1 条可执行验证步骤，例如：

- `run: python -m pytest -q`

