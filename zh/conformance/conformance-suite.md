# Conformance Suite（自动化互操作测试）

## 1. 目标

把 Contrix v1 规范转化为可复现的实现标准。本套件以 profile 为测试入口，强制验证：

- canonical `Event.kind` 与服务 `operation_id` 语义
- reducer 一致性（特别是 auth/state 重算）
- redaction 与隐私字段保留规则
- capability 与授权派生规则
- Principal Server Events API / sync service / E2EE / applet / policy-server 关键接口

所有 schema / profile 变更通过 Event Envelope 的 `requirements.{schema, reducer}` 与 `cx.space.upgrade` 完成；v1 不使用顶层 `space_version` wire 字段。

## 2. 测试角色（Profile）

- `cx.profile.minimal_client.v1`
- `cx.profile.core_event_store.v1`
- `cx.profile.chat_mvp.v1`
- `cx.profile.kanban_mvp.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.principal_server_events_api.v1`
- `cx.profile.principal_server.v1`
- `cx.profile.federation_minimal.v1`
- `cx.profile.identity_registry.v1`
- `cx.profile.blob_node.v1`
- `cx.profile.applet_service.v1`
- `cx.profile.enterprise_client.v1`
- `cx.profile.agent_runtime.v1`
- `cx.profile.mimi_interop.v1`
- `cx.profile.sovereign_deployment.v1`
- `cx.profile.sovereign_client.v1`
- `cx.profile.mls_state_binding.full.v1`

## 3. OpenAPI 与 Transport 一致性

### 3.1 OpenAPI shape tests

每个实现必须通过以下验收：

- `/api/v1` 下公开至少包含 `service/identity/events/sync/blob/authz` 关键 operation。
- 服务 `operation_id` MUST 以 `artifacts/registry/contract-catalog.json#operation_registry` 为 canonical source，并通过生成的 `artifacts/registry/operation-registry.json` 供实现消费；标准 `Event.kind` MUST 以 `artifacts/registry/event-kind-registry.json` 为唯一 generated registry view，并遵守其 `wire_scope` / `reducer_input` 分类；协议 typed ID 前缀 MUST 以 `artifacts/registry/id-kind-registry.json` 为唯一 generated registry view；标准 Event payload class MUST 以 `artifacts/schemas/event-payload.schema.json` 为唯一 source of truth。`service-api-schema.md`、OpenAPI 和非 HTTP binding 不得声明 catalog / registry 中不存在的 operation；Event validator、reducer 与 fixture 不得声明 registry 中不存在的标准 `cx.*` event kind，也不得把 `ephemeral_event` 或 `actor_private_event` 当作共享 durable reducer input；schema、fixture、文档示例和 DTO 不得使用未注册的 `cx:<kind>:` typed ID 前缀。
- 相同操作在 gRPC/WebSocket/SSE 等替代 transport 下，语义输入输出一致（可通过对同一 fixture 做幂等重放对比）。

### 3.2 Canonical envelope tests

- canonical JSON 字段顺序与空值处理一致。
- Event Envelope 校验必须按 kind 选择 payload schema；active 标准 kind 未命中 payload class 或 payload class 校验失败，必须在 reducer 前以 `schema_violation` 失败。
- 同一请求在不同服务节点（Principal Server Events API / sync service）可重放得到一致事件 hash 或查询结果边界。

## 4. Conformance 向量分层

### 4.1 Sync / encoding 向量（已在现有文件）

- `conformance-vectors.md` 与 `sync-fixture.json`：timeline 顺序、分页缺口、snapshot frontier、`event_set_commitment`、MLS 回填、decryption_pending。
- `conformance-vectors.md` 与 `crypto-signature-fixture.json`：canonical JSON、digest、签名绑定、真实 Ed25519 detached JWS、HLC、cursor、encrypted envelope。
- `conformance-vectors.md` 与 `state-resolution-fixture.json`：state 冲突、policy hard deny 优先级、离线写入与 revoke freshness 的收敛向量。
- `conformance-vectors.md`：redaction 保留与审计可见性向量。
- `conformance-vectors.md` 与 `capability-fixture.json`：委派、撤销回滚、Flow discussion branch 不继承 Flow synthesis 权限与审批约束向量。
- `privacy-security-fixture.json`：hidden resource、private contact discovery、plaintext-visible service、private blob 与 blind push 的隐私回归向量。
- `mimi-interop-fixture.json`：MIMI provider directory、room binding、content mapping、identifier query、consent、proxy download 与 unsupported draft 向量。

### 4.2 State resolution 向量

v1 新增以下必测项：

- `cx.vector.state_resolution.conflict_membership.v1`
  - 输入同一成员 state key 的并发冲突事件（join/invite/leave/ban）。
  - 期望 reducer 输出：授权链可解释、冲突记录完整、最终 state 可重建且可再现。
- `cx.vector.state_resolution.capability_rebind.v1`
  - 输入 grant/revoke/regrant 并发链 + 依赖 auth state。
  - 期望输出：只允许 auth 通过者进入 winner；无授权候选回退到 base state。
- `cx.vector.state_resolution.schema_update.v1`
  - `cx.space.policy.set` (state_key=`schema_refs`) 与 `cx.space.policy.set` (state_key=`policy_server`) 的并发写入。
  - 期望输出：按优先级类 + tie-break 顺序稳定收敛。

### 4.3 Redaction 向量

- `cx.vector.redaction.preserve_fields.v1`
  - 输入 target event + redaction event（不同时序）。
  - 期望输出：仅保留被允许的字段，其余不可逆地清除；事件 envelope 不可被改写。
- `cx.vector.redaction.policy_scope.v1`
  - redaction 对已归档事件、加密事件、外部可见字段的影响。
  - 期望输出：索引与审计可见性一致，不可把 redaction 解读为物理删除。

### 4.4 Capability 向量

- `cx.vector.capability.delegate_chain.v1`
  - grant 链条（多层委派）与 selector 条件（时间、对象、速率）冲突场景。
  - 期望输出：可验证且具备时间边界的派生有效性。
- `cx.vector.capability.revoke_rollback.v1`
  - 撤销后既有事件在历史范围内的生效/失效行为。
- `cx.vector.capability.approval_constraint.v1`
  - high risk action 未满足 approval 时应软拒绝或进入 proposal 流程。

## 5. 组件级测试矩阵（必测）

| 组件 | MUST 覆盖 | SHOULD 覆盖 |
| --- | --- | --- |
| Minimal/Full Client | filter、pagination、state_after、decryption_pending | snapshot frontier、causal wait |
| Events API | submitEvent、eventIdempotency、eventDigest 验证、signature 校验 | snapshot generation、event batch receipt |
| Principal Server | sync stream 续传、backfill 顺序、重复过滤、加密转发不解密、来源限速与回压 | 多上游 federation、快照指针 |
| E2EE Client | epoch 回填、to-device、removed 成员 fail-closed | 本地 search 协调 |
| Applet Bridge | 注册签名、transaction 幂等、namespace 冲突、未授权写入拒绝 | portal space 映射 |
| MIMI Provider Facade | draft pinning、room binding、KeyPackage claim、message/content roundtrip、policy mapping、identifier privacy、consent isolation、proxy download、unsupported draft fail-closed | MIMI content extension lossless preservation |
| Policy Server | decision 签名、replay 保护、hard_deny / quarantine 语义、rate_limit / spam 风险码 | federation 再检 |
| Identity Registry | DID log 一致性、witness receipt、method adapter | witness-only、read-replica |
| Moderation | report / queue item schema、E2EE evidence package、franking、operator ACL | appeal / audit trail |
| Agent Runtime | agent authority panel、knowledge source 声明、owner presence policy、join policy、capability revoke | approval UX、tool call audit |

## 6. 执行与发布要求

- 每个实现 MUST 提供覆盖结果文档，声明通过/失败的 vector 列表。
- 每条失败向量必须包含最小复现实例。
- 未通过的 profile 可通过但不得标记为“完全互操作”。
- 本套件目标是在 v1 reducer/schema profile 下形成稳定收敛，避免为实现差异引入新 profile 版本。

### 6.1 发布分级

规范文本闭环不等于实现生态已经稳定。Contrix 发布时 SHOULD 使用以下分级：

| 标签 | 允许用途 | 必须满足 |
| --- | --- | --- |
| `v1-core-rc` | 面向实现者启动互操作开发。 | `zh/` + `artifacts/` registry lint 通过；`core_event_store`、`chat_mvp`、`kanban_mvp` 的 schema / fixture / profile 已冻结。 |
| `v1-interop-preview` | 多实现试验互通。 | 至少两个独立实现通过同一 reference validator 的 `core_event_store` 向量，并能重放官方 sync / state / capability fixture。 |
| `v1.0-stable` | 对外宣称稳定协议版本。 | reference validator、reference reducer、reference authz evaluator 和 conformance runner 已发布；canonical JSON、Event Envelope negative vectors、state resolution、capability、privacy/security、sync 和 snapshot vectors 均由 CI 执行；英文或其他翻译不得作为 stale source of truth 发布。 |

当前仓库若未同时发布上述 reference validator / reducer / authz evaluator / runner，并在 CI 执行核心 vectors，只能声明为 `v1-core-rc` 候选或更低等级，不得声明 `v1.0-stable`。

若某 profile 的 payload schema 仍使用宽泛结构（例如 `state_content` 或 `generic_standard_content`），该 profile 的 stable 声明必须额外依赖 reference reducer / validator 中的语义校验，不能只依赖 JSON Schema 通过。
