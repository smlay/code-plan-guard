# code-plan-guard

轻量、**确定性优先**的计划阶段完整性门卫：对 AI/人写的**变更计划**做 Schema 校验、静态 import **真值**（`expected_impact.json`）与 **1-hop 对账**（B01–B04），默认不把 LLM 作为 blocker 依据。

详细需求见 [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)（PRD v1.8）。

## 诚实边界（请务必阅读）

1. **不替代 PR review**：通过本工具仍可能出现业务或架构层面的错误。  
2. **静态 AST + import**：**不保证**动态导入、`importlib`、字符串加载等。  
3. **非 `.py` 变更项**：仍检查路径存在性（B02），**不参与** 1-hop 分析。  
4. **LLM 审查**（若未来启用）：仅可作为 warning，**不得**作为 B01–B04 的依据。  
5. **规则可豁免**：可通过 `.codeguard.yml` 调整阈值与豁免路径。

### 已知限制（import 解析 v0.4）

- `if typing.TYPE_CHECKING:`（非裸名 `TYPE_CHECKING`）**不会**自动跳过块内 import。  
- `if 0:` 等非常量 `False` 的死分支**不**自动识别。  
- `new_deps` / `removed_deps` 在计划中仅为**文档字段**，格式约定为 **PEP 508** 字符串列表（不参与对账）。

## 安装

```bash
pip install -e ".[dev]"   # 开发
# 或发布后: pip install code-plan-guard
```

需要 **Python 3.10+**。

## 用法

```bash
code-plan-guard review --plan path/to/plan.yaml --repo .
```

常用参数：

- `--out-dir`、`--config`、`--intent`
- `--base-ref`（v0.2 增量范围参与分析）
- `--no-cache`
- `--override-file`（v0.2，本地模拟 PR override）
- `--override-from-github`（v0.4，可选，从 PR body/comments/review comments 拉取 override）
- `--ruff-report`、`--pyright-report`（v0.2 外部信号）
- `--json`（v0.2 机器可读输出）
- `--plan auto`（v0.4，自动发现 plan；支持 PR body 的 `plan:` 指针）
- `--plan-source`、`--dump-context`（v0.4 调试）

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
print(r.overrides, len(r.external_signals))
```

## 产物

默认写入 `<repo>/.codeguard/`：

- `expected_impact.json` — 静态分析真值  
- `reconciliation_report.json` — 对账明细（含 `overrides` / `external_signals`）  
- `guard_report.md` — 人类可读摘要  
- `audit_overrides.json` — override 审计（如有）

## v0.4 新增能力速览

- Plan 自动发现 v2：`--plan auto` + PR body `plan:` 指针
- override 来源扩展：issue comments + review comments + fenced override block
- override 策略：allowed actors/teams、required labels、sha 绑定、最小复核人数
- 新规则：B07（验证步骤缺失，可配置 warning/block）、B06 循环检测可选扩展 1-hop
- 性能/缓存：阈值可配置、cache hit/miss 可观测
- 多语言：启发式增强 + tree-sitter（可选，缺依赖自动降级）

## 配置

项目根目录放置 `.codeguard.yml` 或 `.code-plan-guard.yml`，示例见 PRD **附录 A**。  
override 规则见 [docs/OVERRIDE_POLICY.md](docs/OVERRIDE_POLICY.md)。

配置中的未知字段在当前实现中默认**忽略**（前向兼容策略），不会导致失败。

## 开发

```bash
pytest -q
```

PRD 决策点与测试登记见 [docs/prd_traceability.md](docs/prd_traceability.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。

## 发布前

请自行复查 [PyPI](https://pypi.org/project/code-plan-guard/) 与 GitHub 上包名是否可用。
