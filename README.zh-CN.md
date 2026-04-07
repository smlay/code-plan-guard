# code-plan-guard

[English](README.md) | [简体中文](README.zh-CN.md)

面向 AI（或人工）变更计划的**计划阶段完整性门卫**。在执行/生成代码之前，先用**确定性优先**的规则把“影响面”变成可审计、可复现的产物：

- 计划 Schema 校验
- 静态 import “真值” (`expected_impact.json`)
- 基于真值与计划声明的对账（reconciliation）

本项目的原则是：**LLM 永远只能给 warning/suggestion，不能作为 blocker 依据**。

## 目录

- [为什么需要](#为什么需要)
- [它做什么](#它做什么)
- [安装](#安装)
- [快速开始](#快速开始)
- [产物（artifacts）](#产物artifacts)
- [配置](#配置)
- [版本更新摘要](#版本更新摘要)
- [诚实边界](#诚实边界)
- [开发](#开发)
- [许可证](#许可证)

## 为什么需要

AI 协作写代码很容易跳过影响分析，导致“改了一个文件、炸了 N 个地方”的技术债。
`code-plan-guard` 把**计划阶段**变成一道门：计划不清楚/影响面不一致，就不应该进入自动执行。

## 它做什么

给定一个 plan 文件（YAML/JSON）描述变更，本工具会：

- 校验计划结构与必填字段（Schema）
- 为 Python 构建静态 import 真值（并可扩展到多语言真值）
- 用推导出的 1-hop（或多跳）影响面与 plan 中声明的 `impacted_files` 做对账
- 输出机器可读的 artifacts，供 CI、报表、审计使用

## 安装

需要 **Python 3.10+**。

```bash
# 开发安装
pip install -e ".[dev]"

# （发布后）pip install code-plan-guard
```

## 快速开始

```bash
code-plan-guard review --plan path/to/plan.yaml --repo .
```

常用参数：

- `--out-dir`、`--config`、`--intent`
- `--base-ref`（根据 git diff 缩小增量分析范围）
- `--no-cache`
- `--override-file`（本地 override 模拟）
- `--override-from-github`（可选：从 PR body/comments 获取 override，需要 `gh` + token）
- `--ruff-report`、`--pyright-report`、`--mypy-report`、`--semgrep-report`（外部信号：warning-only）
- `--json`（机器可读 CLI 输出）
- `--plan auto`（CI/PR 场景自动发现 plan）

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

## 产物（artifacts）

默认写入 `<repo>/.codeguard/`：

- `expected_impact.json` — 静态分析真值
- `reconciliation_report.json` — 对账明细 + warnings + context
- `guard_report.md` — 人类可读摘要
- `signals.json` — 外部工具信号（可选）
- `audit_overrides.json` — override 审计（可选）

## 配置

在仓库根目录放置 `.codeguard.yml` 或 `.code-plan-guard.yml`。
配置里出现未知字段会被忽略（前向兼容）。

仓库内可用文档：

- `docs/INTEGRATION.md`（CI 与本地 hooks）
- `docs/PLAN_CONVENTIONS.md`（plan 命名与自动发现约定）
- `docs/OVERRIDE_POLICY_v0_4.md`（override 策略/治理）
- `docs/SCHEMA_POLICY.md`（产物 schema 版本策略）

## 版本更新摘要

完整变更请看 [`CHANGELOG.md`](CHANGELOG.md)。

### 0.4.0 (2026-04-06)

- Plan discovery v2：`--plan auto` + PR body `plan:` 指针
- `reconciliation_report.json` 增强 GitHub 运行上下文字段
- override 治理：actors/teams、label gate、SHA 绑定、N-of-M（best-effort）
- 规则增强：循环检测可选扩展、验证步骤质量规则（可配）
- 性能阈值与确定性降级
- 实验性多语言真值（JS/TS 启发式 + tree-sitter 可选降级）

### 0.3.0 (2026-04-06)

- GitHub override 获取 + 更丰富审计信息
- `reconciliation_report.json` 增加 `context`
- 循环检测规则（可配置 severity）
- 实验性多语言扫描（warning-only）

### 0.2.0 (2026-04-06)

- GitHub Actions 示例
- override + `audit_overrides.json`
- `--base-ref` 增量分析
- 外部信号：ruff / pyright（warning-only）
- 可选 LLM 二轮审查钩子（warning-only）

## 诚实边界

- **不替代 PR review**：通过 guard 不代表业务/架构一定正确。
- **静态分析边界**：动态导入/`importlib`/字符串加载仅 best-effort。
- **非 Python 变更**：会做路径存在性校验，但 Python import 真值只覆盖 `.py`。
- **LLM（如启用）**：只能输出 warning/suggestion，不能触发 blocker。

## 开发

```bash
python -m pytest -q
```

## 许可证

MIT，见 [`LICENSE`](LICENSE)。

