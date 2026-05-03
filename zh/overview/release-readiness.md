# 实现就绪与发布门槛

## 1. 目标

本文定义 Contrix v1 的当前发布基线、机器工件覆盖范围、实现不变量与稳定发布门槛。

## 2. 当前发布基线

实现者应从机器工件与中文规范读取同一套协议事实模型：

- 唯一共享 wire fact 是 Event Envelope
- reducer、frontier、snapshot、sync、federation 和 fixture 以 `event_id` / actor frontier 为语义单位
- `operation_id` 仅表示服务 canonical operation 或 SDK 内部幂等标识
- 标准 Event kind、服务 operation、schema id、typed ID prefix 均有机器 registry
- OpenAPI、非 HTTP binding、fixture 与中文规范均可回指这些 registry

## 3. 工件矩阵

| 主题 | 对应工件 | 当前要求 |
| --- | --- | --- |
| 唯一事实 envelope | `zh/sync/operations-sync.md`, `artifacts/schemas/event-schema.json`, `artifacts/schemas/event-payload.schema.json` | Event Envelope 是唯一共享 wire fact；Operation 只用于服务 operation 或 SDK 内部构造路径。 |
| Event kind 与 payload | `artifacts/registry/event-kind-registry.json`, `artifacts/schemas/event-payload.schema.json` | active 标准 kind 必须选择对应 payload class，失败即 `schema_violation`。 |
| 服务 operation 映射 | `artifacts/registry/contract-catalog.json`, `artifacts/registry/operation-registry.json`, `artifacts/openapi/contrix-service-api.openapi.yaml`, `artifacts/bindings/non-http-bindings.yaml` | `contract-catalog.json#operation_registry` 是 operation 的 canonical source。 |
| Schema registry | `artifacts/registry/schema-registry.json`, `zh/conformance/schema-registry.md` | 对象、Event、snapshot、moderation、Agent Authority、MIMI 等 schema 已注册。 |
| Typed ID prefix | `artifacts/registry/id-kind-registry.json` | 标准 `cx:<kind>:` prefix 以机器注册表为准。 |
| Profile 矩阵 | `zh/conformance/conformance-profiles.md`, `artifacts/profiles/conformance-profiles.json` | `core_event_store`、`chat_mvp`、`kanban_mvp` 与客户端/服务角色可独立声明。 |
| Conformance vectors | `artifacts/fixtures/*.json`, `zh/conformance/fixtures/*.json` | encoding、crypto、state resolution、redaction、capability、sync、privacy/security、federation、MIMI 均有机器 fixture 入口。 |
| Snapshot 约束 | `artifacts/schemas/snapshot.schema.json`, `zh/conformance/snapshot-schema.md`, `zh/sync/operations-sync.md` | manifest 必须包含 `event_set_commitment`；高保障 profile 支持 inclusion / omission challenge。 |
| Moderation / abuse | `artifacts/schemas/moderation-report.schema.json`, `artifacts/schemas/moderation-queue-item.schema.json`, OpenAPI moderation endpoints | report、queue item、E2EE evidence / franking 边界有 schema 与服务绑定。 |
| Privacy / security | `artifacts/fixtures/privacy-security-fixture.json`, `zh/conformance/conformance-profiles.md` | hidden resource、private contact discovery、plaintext-visible service、private blob、blind push 有回归向量。 |
| Agent 权限边界 | `artifacts/schemas/agent-authority.schema.json`, `zh/authz/capabilities.md`, `zh/extensions/agent-protocol-interop.md` | owner presence、knowledge source、join policy、responsible actor 与 grant 解释面已固定。 |

## 4. 必须保持的不变量

- 标准 `cx.*` Event kind 必须出现在 `event-kind-registry.json`，不得只写在 Markdown 中
- Event Envelope 必须先验证 envelope schema，再验证 kind-selected payload schema，最后才进入 auth / reducer
- Snapshot 签名不能单独证明无遗漏；实现必须校验 `event_set_commitment`
- Sync、Directory、Blob、Push、Moderation、Agent 和受托 search / projection 等服务不得绕过 capability、Space policy、history visibility、plaintext-visible service 或 E2EE 边界
- 未知 non-critical 字段必须在 canonical bytes、存储、转发和 backfill 中保留
- 未知 critical extension 必须 fail closed

## 5. 发布门槛

### 5.1 `v1-core-rc`

- `zh/` 与 `artifacts/` registry lint 通过
- `core_event_store`、`chat_mvp`、`kanban_mvp` 的 schema、fixture、profile 已冻结

### 5.2 `v1-interop-preview`

- 至少两个独立实现通过同一 reference validator 的 `core_event_store` 向量
- 能重放官方 sync / state / capability fixture

### 5.3 `v1.0-stable`

- reference validator、reference reducer、reference authz evaluator 与 conformance runner 已发布
- canonical JSON、Event Envelope negative vectors、state resolution、capability、privacy/security、sync 与 snapshot vectors 由 CI 执行
- 公开发布的翻译与附属文档不得偏离同一 registry 与 fixture 基线

## 6. 工程交付要求

- 提供官方 reference validator / reducer / authz 包
- 用 CI 自动校验 Markdown 示例、OpenAPI、registry、schema 与 fixture 一致性
- 从 OpenAPI / JSON Schema 生成 SDK 类型与 contract tests
- 对宽泛 payload schema 提供 reference validator 中的语义校验，不能只凭 JSON Schema 宣称完全互操作
