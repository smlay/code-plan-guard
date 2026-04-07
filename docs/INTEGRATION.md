# 集成指南（强制不可绕过）

## 1) GitHub：Required Check（推荐）

1. 在仓库中启用 `.github/workflows/ci.yml` 的 `guard` job（本项目已包含示例）。
2. 在 GitHub 仓库设置里将该 workflow 对应的 check 设为 **Required**：
   - Settings → Branches → Branch protection rules → Require status checks to pass before merging
   - 选中 `CI / guard`（名称以实际显示为准）

这样可以实现：**未通过 Guard（exit_code=1/2）就无法合并**（不可绕过）。

## 2) 本地：pre-commit / pre-push（可选）

项目提供模板：`githooks/pre-commit`、`githooks/pre-push`。

启用方式（示例）：

```bash
cp githooks/pre-commit .git/hooks/pre-commit
cp githooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-commit .git/hooks/pre-push
```

常用环境变量：

- `CODE_PLAN_GUARD_PLAN`：默认 `auto`
- `CODE_PLAN_GUARD_OUT_DIR`：默认 `.codeguard`
- `GUARD_SOFT_FAIL=true`：允许 exit_code=1（仅 blocker）不阻断（**不推荐**在主分支）

