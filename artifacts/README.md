# Artifacts

`artifacts/` 存放 Contrix 的机器可读协议契约（machine-readable contract）。

## 1. 约定与分层

### 1.1 真实来源（Canonical）

- `artifacts/registry/contract-catalog.json`
  - 事件 kind、schema、typed-ID 与 operation 的源定义。
- `artifacts/registry/error-code-registry.json`
  - 错误码体系。
- `artifacts/registry/mirror-manifest.json`
  - `zh/` 与工件文件镜像关系。
- `artifacts/registry/registry-manifest.json`
  - `artifacts/registry/` 下所有机器注册表索引。

### 1.2 生成视图（Generated）

以下文件由 `contract-catalog.json` 派生，**不得直接手工编辑**：

- `artifacts/registry/event-kind-registry.json`
- `artifacts/registry/schema-registry.json`
- `artifacts/registry/id-kind-registry.json`
- `artifacts/registry/operation-registry.json`

## 2. 维护与校验流水线

统一入口：

```bash
python tools/artifact_pipeline.py generate
python tools/artifact_pipeline.py sync
python tools/artifact_pipeline.py check
```

流水线职责：

- 合成生成文件
- 同步文档镜像与机器注册表
- 触发约束校验与 profile 一致性检查

其中 `check` 会执行三层校验：

- 与 `contract-catalog.json` 的 drift 检测
- 基于 `artifacts/lint_artifacts.py` 的 registry-first 校验（包括镜像漂移与 Markdown 链接完整性）
- Profile 与 registry 变化摘要输出

## 3. CI 要求

`.github/workflows/artifact-lint.yml` 会以同一入口在持续集成中执行协议约束校验，保证仓库内协议契约与机器视图一致。
