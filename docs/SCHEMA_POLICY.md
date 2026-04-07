# Artifacts Schema Policy（只增不改）

## 目标

对外输出的 artifacts（JSON/MD）是机器可读契约与审计依据，必须做到：

- **可复现**：同输入同输出（同版本、同配置、同文件内容）
- **可前向兼容**：新版本只能“新增字段”，不得移除/重命名既有字段

## 版本策略

- **工具版本**：遵循 SemVer（`MAJOR.MINOR.PATCH`）
- **artifacts 内 `schema_version`**：
  - 仅用于描述该 JSON 的结构版本
  - **只允许递增**（例如 `0.1` → `0.2` → `0.3`）
  - 既有字段 **只增不改**；若必须变更语义，采用“新增字段 + 保留旧字段”的方式过渡

## 文件清单

- `expected_impact.json`
- `reconciliation_report.json`
- `audit_overrides.json`（如启用 override）

## 向后兼容要求（实现侧）

- 解析方必须忽略未知字段（forward compatible）
- 生产方不得依赖外部服务作为 blocker 的唯一依据（外部不可用时必须降级为 warning）

