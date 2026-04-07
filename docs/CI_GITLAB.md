# GitLab CI 示例（最小可用）

将以下 job 合并进你的 `.gitlab-ci.yml`：

```yaml
code_plan_guard:
  image: python:3.11
  stage: test
  script:
    - pip install -e ".[dev]"
    - code-plan-guard review --plan auto --repo . --no-cache
  artifacts:
    when: always
    paths:
      - .codeguard/expected_impact.json
      - .codeguard/reconciliation_report.json
      - .codeguard/guard_report.md
      - .codeguard/audit_overrides.json
```

建议在 GitLab 的 merge request 规则中将该 job 设为 required，以达到“不可绕过”。

