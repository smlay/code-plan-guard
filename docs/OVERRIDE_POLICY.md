# Override Policy（v0.2）

本文件定义 `code-plan-guard` 在 v0.2 的人工 override 规则与审计要求。

## 1. 指令格式

支持在文本中写入如下单行指令（本地文件或 PR comment 抓取结果）：

```text
code-plan-guard: override B03 reason=your_reason_here
```

当前解析规则：

- blocker id 形如 `Bxx`（示例：`B03`）
- `reason=` 后整行作为原因文本
- 大小写不敏感

## 2. 可 override 范围

v0.2 默认允许：`B03`、`B05`。  
默认不允许：`B01`、`B02`、`B04`（基础契约失败不可跳过）。

可通过配置调整：

```yaml
override:
  enabled: true
  allowed_blockers: ["B03", "B05"]
```

## 3. 审计产物

当有 override 生效时，写出：

- `.codeguard/audit_overrides.json`

字段至少包含：

- `actor`（优先 `GITHUB_ACTOR`，本地为 `local`）
- `timestamp`
- `commit_sha`
- `plan_hash`
- `overrides`（包含 `blocker_id` 与 `reason`）

## 4. 报告联动

- `reconciliation_report.json` 中应包含 `overrides` 字段
- `guard_report.md` 推荐增加 override 摘要（v0.2 可先通过 JSON 报告体现）

## 5. 安全建议

- reason 仅用于审计与显示，禁止执行
- 不允许通过 override 绕过系统级错误（`exit_code=2`）

