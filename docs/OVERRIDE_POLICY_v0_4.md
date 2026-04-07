# Override Policy（v0.4）

## 指令格式

单行指令（大小写不敏感）：

- `code-plan-guard: override B03 reason=...`
- 可选绑定提交：`code-plan-guard: override B03 reason=... sha=<short-or-full-sha>`

也支持 fenced block（推荐用于 PR 描述）：

```override
code-plan-guard: override B03 reason=...
code-plan-guard: override B05 reason=...
```

## 来源（v0.4）

- 文件：`--override-file`（本地/CI）
- GitHub PR（需要 `gh` + token）：
  - PR body
  - issue comments
  - review comments

## 策略（可配置，v0.4）

位于 `.codeguard.yml` 的 `github:` 下：

- `override_allowed_actors`: 允许 override 的 GitHub 登录名列表
- `override_allowed_teams`: 允许团队（`org:team`）列表（best-effort 解析，失败 warning 降级）
- `override_required_labels`: 允许 override 的 label gate（任意一个命中即可）
- `override_min_reason_length`: reason 最短长度
- `override_min_approvers`: 同一 blocker_id 需要的最少不同 author 数

## 审计（audit_overrides.json）

v0.4 将 `audit_overrides.json` 的 `schema_version` 升级为 `0.3`，并记录：

- 指令来源（source_type/source_ref/author/created_at）
- raw 原文片段（截断）
- sha 绑定信息（如有）
- 应用前后 blockers 列表

