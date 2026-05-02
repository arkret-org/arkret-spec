# Conformance Suite（自动化互操作测试）

## 1. 目标

把 Contrix v1 规范转化为可复现的实现标准。本套件以 profile 为测试入口，强制验证：

- canonical `Event.kind` 与服务 `operation_id` 语义
- reducer 兼容性（特别是 auth/state 重算）
- redaction 与隐私字段保留规则
- capability 与授权派生规则
- Principal Server Events API / sync service / index / E2EE / applet / policy-server 关键接口

本版本不新增 `space_version`；所有兼容性演进通过 `space_version=1` 下的 profile 与字段废弃流程完成。

## 2. 测试角色（Profile）

- `cx.profile.minimal_client.v1`
- `cx.profile.core_event_store.v1`
- `cx.profile.chat_mvp.v1`
- `cx.profile.kanban_mvp.v1`
- `cx.profile.chat_only_client.v1`
- `cx.profile.kanban_only_client.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.principal_server_events_api.v1`
- `cx.profile.principal_server.v1`
- `cx.profile.federation_minimal.v1`
- `cx.profile.index_node.v1`
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

- `/api/v1` 下公开至少包含 `service/identity/events/sync/index/blob/authz` 关键 operation。
- 服务 `operation_id` MUST 以 `artifacts/registry/operation-registry.json` 为唯一 source of truth；标准 `Event.kind` MUST 以 `artifacts/registry/event-kind-registry.json` 为唯一 source of truth，并遵守其 `wire_scope` / `reducer_input` 分类；协议 typed ID 前缀 MUST 以 `artifacts/registry/id-kind-registry.json` 为唯一 source of truth。`service-api-schema.md`、OpenAPI 和非 HTTP binding 不得声明 registry 中不存在的 operation；Event validator、reducer 与 fixture 不得声明 registry 中不存在的标准 `cx.*` event kind，也不得把 `ephemeral_event` 或 `actor_private_event` 当作共享 durable reducer input；schema、fixture、文档示例和 DTO 不得使用未注册的 `cx:<kind>:` typed ID 前缀。
- 相同操作在 gRPC/WebSocket/SSE 等替代 transport 下，语义输入输出一致（可通过对同一 fixture 做幂等重放对比）。

### 3.2 Canonical envelope tests

- canonical JSON 字段顺序与空值处理一致。
- 同一请求在不同服务节点（Principal Server Events API / sync service / index）可重放得到一致事件 hash 或查询结果边界。

## 4. Conformance 向量分层

### 4.1 Sync / encoding 向量（已在现有文件）

- `sync-conformance-vectors.md`：timeline 顺序、分页缺口、snapshot frontier、MLS 回填、decryption_pending。
- `encoding-conformance-vectors.md` 与 `crypto-signature-fixture.json`：canonical JSON、digest、签名绑定、真实 Ed25519 detached JWS、HLC、cursor、encrypted envelope。
- `state-resolution-conformance-vectors.md`：state 冲突与收敛向量（本文件未完全展开的补充）。
- `redaction-conformance-vectors.md`：redaction 保留与审计可见性向量。
- `capability-conformance-vectors.md`：委派、撤销回滚与审批约束向量。
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
  - `cx.space.schema` 与 `cx.space.policy_server` 的并发写入。
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
  - 撤销后旧事件在历史范围内的生效/失效行为。
- `cx.vector.capability.approval_constraint.v1`
  - high risk action 未满足 approval 时应软拒绝或进入 proposal 流程。

## 5. 组件级测试矩阵（必测）

| 组件 | MUST 覆盖 | SHOULD 覆盖 |
| --- | --- | --- |
| Minimal/Full Client | filter、pagination、state_after、decryption_pending | snapshot frontier、causal wait |
| Events API | submitEvent、eventIdempotency、eventDigest 验证、signature 校验 | snapshot generation、event batch receipt |
| Principal Server | sync stream 续传、backfill 顺序、重复过滤、加密转发不解密、来源限速与回压 | 多上游 federation、快照指针 |
| Index Node | query 结果可重建性、授权过滤、wait-for 前沿、stale 标记、目录结果可见性一致 | notification materialization |
| E2EE Client | epoch 回填、to-device、removed 成员 fail-closed | 本地 search 协调 |
| Applet Bridge | 注册签名、transaction 幂等、namespace 冲突、未授权写入拒绝 | portal space 映射 |
| MIMI Provider Facade | draft pinning、room binding、KeyPackage claim、message/content roundtrip、policy mapping、identifier privacy、consent isolation、proxy download、unsupported draft fail-closed | MIMI content extension lossless preservation |
| Policy Server | decision 签名、replay 保护、hard_deny / quarantine 语义、rate_limit / spam 风险码 | federation 再检 |
| Identity Registry | DID log 一致性、witness receipt、method adapter | witness-only、read-replica |

## 6. 执行与发布要求

- 每个实现 MUST 提供覆盖结果文档，声明通过/失败的 vector 列表。
- 每条失败向量必须包含最小复现实例。
- 未通过的 profile 可通过但不得标记为“完全互操作”。
- 本套件目标是在当前 `space_version=1` 下形成稳定收敛，避免为兼容问题引入新 space version。
