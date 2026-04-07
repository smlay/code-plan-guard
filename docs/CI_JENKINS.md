# Jenkins 示例（最小可用）

示例 `Jenkinsfile`（Declarative Pipeline）：

```groovy
pipeline {
  agent any
  stages {
    stage('Install') {
      steps {
        sh 'python -m pip install -e ".[dev]"'
      }
    }
    stage('code-plan-guard') {
      steps {
        sh 'code-plan-guard review --plan auto --repo . --no-cache'
      }
      post {
        always {
          archiveArtifacts artifacts: '.codeguard/*', fingerprint: true, allowEmptyArchive: true
        }
      }
    }
  }
}
```

建议将该 stage 作为合并门槛（required），以达到“不可绕过”。

