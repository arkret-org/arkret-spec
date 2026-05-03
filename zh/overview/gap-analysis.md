# 闭环状态分析

## 1. 目标

本文记录 Contrix v1 当前协议是否已经形成可实现、可测试、可审计的闭环。

判断范围以 `zh/` 与 `artifacts/` 为准；根目录 README 已声明 `en/` 为 stale 翻译，不参与 v1 当前闭环判定。

## 2. 总体结论

当前 v1 协议闭环已完成。实现者可以从机器工件和中文规范中得到同一套事实模型：

- wire 上的唯一共享事实对象是 Event Envelope。
- reducer、frontier、snapshot、sync、federation 和 fixture 均以 `event_id` / actor frontier 为语义单位。
- `operation_id` 只表示服务 canonical operation，或旧 SDK 本地幂等别名；Canonical Operation Object 不进入互操作主路径。
- 标准 Event kind、服务 operation、schema id、typed ID prefix 均有机器 registry。
- OpenAPI、非 HTTP binding、fixture 和中文规范均可回指这些 registry。
- 关键安全边界已有 schema、profile 或 fixture 固定，不再只停留在文字规则。

## 3. 闭环矩阵

| 闭环主题 | 当前工件 | 状态 |
| --- | --- | --- |
| 唯一事实 envelope | `zh/sync/operations-sync.md`, `artifacts/schemas/event-schema.json`, `artifacts/schemas/event-payload.schema.json` | 已闭环：Event Envelope 是唯一共享 wire fact；Operation 仅为服务 operation 或 SDK 内部 builder。 |
| Event kind 与 payload | `artifacts/registry/event-kind-registry.json`, `artifacts/schemas/event-payload.schema.json` | 已闭环：active 标准 kind 必须按 kind 选择 payload class，失败即 `schema_violation`。 |
| 服务 operation 映射 | `artifacts/registry/contract-catalog.json`, `artifacts/registry/operation-registry.json`, `artifacts/openapi/contrix-service-api.openapi.yaml`, `artifacts/bindings/non-http-bindings.yaml` | 已闭环：`contract-catalog.json#operation_registry` 是 canonical source；HTTP / gRPC / MQ 等 binding 消费生成 registry 或等价生成物。 |
| Schema registry | `artifacts/registry/schema-registry.json`, `zh/conformance/schema-registry.md` | 已闭环：对象、Event、snapshot、moderation、Agent Authority、MIMI 等 schema 已注册。 |
| Typed ID prefix | `artifacts/registry/id-kind-registry.json` | 已闭环：标准 `cx:<kind>:` prefix 有机器来源；fixture / schema 可 lint。 |
| MVP profile | `zh/conformance/conformance-profiles.md`, `artifacts/profiles/conformance-profiles.json` | 已闭环：`core_event_store`、`chat_mvp`、`kanban_mvp` 与客户端/服务角色可独立声明。 |
| Conformance vectors | `artifacts/fixtures/*.json`, `zh/conformance/fixtures/*.json` | 已闭环：encoding、crypto、state resolution、redaction、capability、sync、privacy/security、federation、MIMI 均有机器 fixture 入口。 |
| Snapshot 防遗漏 | `artifacts/schemas/snapshot.schema.json`, `zh/conformance/snapshot-schema.md`, `zh/sync/operations-sync.md` | 已闭环：manifest 必须包含 `event_set_commitment`，高保障 profile 支持 inclusion / omission challenge。 |
| Moderation / abuse | `artifacts/schemas/moderation-report.schema.json`, `artifacts/schemas/moderation-queue-item.schema.json`, OpenAPI moderation endpoints | 已闭环：report、queue item、E2EE evidence / frank 边界有 schema 和服务绑定。 |
| Privacy / security | `artifacts/fixtures/privacy-security-fixture.json`, `zh/conformance/conformance-profiles.md` | 已闭环：hidden resource、private contact discovery、plaintext-visible service、private blob、blind push 有回归向量。 |
| Agent 权限边界 | `artifacts/schemas/agent-authority.schema.json`, `zh/authz/capabilities.md`, `zh/extensions/agent-protocol-interop.md` | 已闭环：owner presence、knowledge source、join policy、responsible actor、grant 解释面已固化。 |

## 4. 当前必须保持的不变量

- 标准 `cx.*` Event kind 必须出现在 `event-kind-registry.json`，不得只写在 Markdown 中。
- Event Envelope 必须先验证 envelope schema，再验证 kind-selected payload schema，最后才进入 auth / reducer。
- Snapshot 签名不能单独证明没有遗漏；实现必须校验 `event_set_commitment`，高保障场景还要执行 inclusion / omission challenge。
- Sync、Directory、Blob、Push、Moderation、Agent 和受托 search / projection 等服务不得因部署便利绕过 capability、Space policy、history visibility、plaintext-visible service 或 E2EE 边界。
- Linked Room 不继承 Card 权限；Agent 不继承 owner 权限；MIMI consent 不授予 Space read/write。
- 未知 non-critical 字段必须在 canonical bytes、存储、转发和 backfill 中保留；未知 critical extension 必须 fail closed。

## 5. 发布判定

当前没有阻塞 `v1-core-rc` 的规范缺陷。协议事实模型、服务面、schema、profile 和首批 conformance vectors 已经能支撑实现开始互操作。

但 `v1.0-stable` 仍必须以可执行验收为门槛，而不是只以规范文本完成为门槛。稳定发布前 SHOULD 至少满足：

- 官方 reference validator / reducer / authz evaluator 可运行，并能加载 `artifacts/` registry、schema、profile 和 fixtures。
- canonical JSON parser 明确拒绝 malformed UTF-8、duplicate key、未知 critical extension、非法 number profile 和非规范 timestamp。
- `core_event_store`、`chat_mvp`、`kanban_mvp` 至少有两个独立实现通过同一 conformance runner。
- 使用宽泛 payload schema 的 profile 必须有额外 reducer / semantic validator 覆盖；不能只凭 JSON Schema 通过宣称完全互操作。
- 英文目录或其他翻译必须去掉 stale 标记并通过同一 registry lint 后，才能作为公开 source of truth。

## 6. 剩余事项

剩余事项属于实现工程化和覆盖增强：

- 提供官方 reference validator / reducer / authz 包。
- 用 CI 自动校验 Markdown 示例、OpenAPI、registry、schema 和 fixture 的一致性。
- 从 OpenAPI / JSON Schema 生成 SDK 类型与 contract tests。
- 扩展更多生产参数向量，例如大规模 federation、policy server 压测、E2EE key backup 和 deployment profile 推荐值。
- 将 `state_content` / `generic_standard_content` 覆盖的高风险事件逐步拆成更严格的 per-kind payload schema，或在 reference validator 中提供等价语义校验。

这些事项会提高实现质量和发布效率。它们不阻塞 `v1-core-rc`，但其中 reference validator / reducer / authz evaluator 与可执行 conformance runner 应作为 `v1.0-stable` 的发布门槛。
