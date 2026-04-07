# code-plan-guard

**code-plan-guard** 是一个“计划阶段守门器”：在你让 AI 执行/落地代码前，先用可重复、低误报的规则把计划结构、影响面与对账证据做成可审计的产物（artifacts）。

## 快速入口

- `REQUIREMENTS.md`：产品需求文档（PRD）
- `INTEGRATION.md`：CI 与本地 Git hooks 集成
- `PLAN_CONVENTIONS.md`：计划文件规范与自动发现约定
- `SCHEMA_POLICY.md`：产物 schema 版本策略

## 产物（artifacts）

`code-plan-guard review` 会在输出目录写入：

- `expected_impact.json`
- `reconciliation_report.json`
- `guard_report.md`
- `signals.json`（可选）
- `audit_overrides.json`（可选）

