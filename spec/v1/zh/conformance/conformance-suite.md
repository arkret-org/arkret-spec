---
title: Conformance Suite（自动化互操作测试）
status: candidate
normative: true
stability: v1
updated: 2026-07-13
sidebar:
  label: Conformance Suite
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

把 Arkret v1 规范转化为可复现的实现标准。本套件以 profile 为测试入口，强制验证：

- canonical `Event.kind` 与服务 `operation_id` 语义
- reducer 一致性（特别是 auth/state 重算）
- redaction 与隐私字段保留规则
- capability 与授权派生规则
- Principal Server Events API / Sync Service / E2EE / applet / Policy Server 关键接口

所有 schema / profile 变更通过 Event Envelope 的 `requirements.{schema, reducer}` 与 `ak.realm.upgrade` 完成；v1 不使用顶层 `space_version` wire 字段。

## 2. 测试角色（Profile）

完整 profile 集合、角色分类和 requirement blocks 的机器真相源是 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json)。本节只列首轮 release gate / 文档阅读优先子集；测试 runner MUST 枚举 JSON 中的 `implementation_profiles`、`deployment_profiles` 与 `hardening_profiles`(capability-negotiation profile)，并单独枚举 `vector_groups`(conformance 向量分组，`ak.vector_group.*` 命名空间，非可协商能力)，不得把下列清单解释为穷尽集合。

**向量适用性闭包（normative）**：[`vector-registry.json`](../../artifacts/registry/vector-registry.json) 中每个 active vector MUST 恰好声明一个适用性 selector：`scope="universal"`、`applies_to_profiles[]`、`applies_to_vector_groups[]` 或 `applies_to_fixtures[]`。单值 `profile` 字段禁止出现。某 profile 的认证集合等于：（a）`scope="universal"`；（b）直接列出该 profile 的向量；（c）该 claim 明确包含的 vector group 向量；（d）该 profile 及其全部 `inherits[]` 的 `required_fixtures[]` 所映射向量的并集。runner MUST 先计算继承后的 fixture closure，再按集合去重；未命中该闭包的 vector 不得被实现或认证器自行猜测为必测或免测。fixture selector 只是适用性索引，`source_refs[]` 仍必须包含同一 fixture，二者由 lint 逐字校验。

**Fixture runner 归属（normative）**：随件 fixture 顶层 `runner.kind` 是执行层的机读入口，其封闭词表、执行契约摘要与 owner 以 [`runner-kind-registry.json`](../../artifacts/registry/runner-kind-registry.json) 为唯一真源；未知 kind MUST 在 lint 与 conformance 加载阶段 fail closed。`json_schema_validation_cases` runner MUST 逐 case 解析 `schema_ref`、用声明的 JSON Schema dialect 校验 `instance`，并将结果与 `expect_valid` 精确比较；`json_schema_and_semantic_cases` 在完成同一 schema 步骤后，还 MUST 把 `semantic_outcome` 与 `expected_reason_code` 交给 reducer/validator 断言。`required_cotest_suites[*].artifact_fixture` MUST 指向 `artifacts/fixtures/` 中存在的随件文件；runner 不得把缺失的本地私有夹具当作 profile 已满足。

Profile 分两类（分类口径以 [`conformance-profiles.md`](./conformance-profiles.md) §6 与 `conformance-profiles.json` 的 `role` 为准）:**实现 profile**（声明实现承担的角色与能力集合）与 **hardening profile**（在某实现 profile 之上叠加的安全加固 overlay,`role=admin`,不单独作为可声明的实现角色）。

**实现 profile**:

- `ak.profile.minimal_client.v1`
- `ak.profile.core_event_store.v1`（minimal interop floor；分层口径见 [`conformance-profiles.md`](./conformance-profiles.md) §2.1，是仅声称 v1 Event Store interop 时的最小声明层，非完整实现角色）
- `ak.profile.chat_mvp.v1`
- `ak.profile.kanban_mvp.v1`
- `ak.profile.full_client.v1`
- `ak.profile.e2ee_client.v1`
- `ak.profile.principal_server_events_api.v1`
- `ak.profile.principal_server.v1`
- `ak.profile.auth_server.v1`
- `ak.profile.federation_minimal.v1`
- `ak.profile.federation.high_assurance.v1`
- `ak.profile.identity_registry.v1`
- `ak.profile.applet_service.v1`
- `ak.profile.enterprise_client.v1`
- `ak.profile.agent_runtime.v1`
- `ak.profile.mimi_interop.v1`
- `ak.profile.sovereign_deployment.v1`
- `ak.profile.sovereign_client.v1`

**gateway profile**（`role=gateway`;完整定义与子 profile 见 [`conformance-profiles.md`](./conformance-profiles.md) §11）:

- `ak.profile.push_gateway.v1`（`depends_on` `ak.profile.push_gateway.blind_wakeup.v1`;`visible_notification` / `matrix_passthrough` 为 opt-in）。注意 `ak.profile.push_gateway.matrix_passthrough.v1` 的 `role` 机器真源（[`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json)）为 **`interop`**（非 `gateway`），它在此处仅作为 push_gateway 的 opt-in 互通扩展列出；其 role 以 json `role` 字段为准，与 [`conformance-profiles.md`](./conformance-profiles.md) §11 表一致。
- `ak.profile.blob_node.v1`

**hardening profile**（overlay,`role=admin`,非独立实现角色；权威全集以 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 的 `hardening_profiles` 为准）:

- `ak.profile.mls_governance_binding.full.v1`
- `ak.profile.attested_audit.e2ee.v1`
- `ak.profile.disclosed_audit.e2ee.v1`
- `ak.profile.cross_signing.reset.v1`
- `ak.profile.mls.minimal_metadata_realm.v1`
- `ak.profile.traffic_metadata_hardened.v1`
- `ak.profile.key_backup.memory_hard.v1`
- `ak.profile.circle_seal_cadence.fixed_5m.v1`
- `ak.profile.accountable_principals.strict_reject.v1`

## 3. OpenAPI 与 Transport 一致性

### 3.1 OpenAPI shape tests

每个实现必须通过以下验收：

- `/_arkret/` 下公开至少包含 `service/identity/events/account/snapshot/blob/authz` 关键 operation。
- 服务 `operation_id` MUST 以 `artifacts/registry/contract-catalog.json#operation_registry` 为 canonical source，并通过生成的 `artifacts/registry/operation-registry.json` 供实现消费；operation DTO 字段集合 MUST 以 JSON Schema 与生成的 `artifacts/reports/operation-schema-index.json` 为机器索引；标准 `Event.kind` MUST 以 `artifacts/registry/event-kind-registry.json` 为唯一 generated registry view，并遵守其 `wire_scope` / `reducer_input` 分类；协议 typed ID 前缀 MUST 以 `artifacts/registry/id-kind-registry.json` 为唯一 generated registry view；标准 Event payload class MUST 以 `artifacts/schemas/event-payload.schema.json` 的 `$defs` 为唯一 source of truth，但完整 payload validation MUST 通过 `event-envelope.schema.json` 的 Event.kind dispatch 或等价 registry dispatch 执行，不得直接把 `event-payload.schema.json` root generic fallback 当作接受条件。OpenAPI、非 HTTP binding 与说明性 `service-api-schema.mdx` 不得声明 catalog / registry 中不存在的 operation；Event validator、reducer 与 fixture 不得声明 registry 中不存在的标准 `ak.*` event kind，也不得把 `ephemeral_event` 或 `actor_private_event` 当作共享 durable reducer input；schema、fixture、文档示例和 DTO 不得使用未注册的 `ak:<kind>:` typed ID 前缀。
- 相同操作在 gRPC/WebSocket/SSE 等替代 transport 下，语义输入输出一致（可通过对同一 fixture 做幂等重放对比）。

### 3.2 Canonical envelope tests

- canonical JSON 字段顺序与空值处理一致。
- Event Envelope 校验必须按 kind 选择 payload schema；active 标准 kind 未命中 payload class 或 payload class 校验失败，必须在 reducer 前以 `schema_violation` 失败。
- 同一请求在不同服务节点（Principal Server Events API / Sync Service）可重放得到一致事件 hash 或查询结果边界。

## 4. Conformance 向量分层

### 4.1 Sync / encoding 向量（已在现有文件）

- `conformance-vectors.md` 与 `sync-fixture.json`：timeline 顺序、分页缺口、snapshot frontier、`event_set_commitment`、MLS 回填、decryption_pending。
- `conformance-vectors.md` 与 `crypto-signature-fixture.json`：canonical JSON、digest、签名绑定、真实 Ed25519 detached JWS、HLC、cursor、encrypted envelope。
- `conformance-vectors.md` 与 `cba-lattice-fixture.json`：CBA 双平面、DataEvent acceptance、Control Move Seal finality、Lattice bottom、同批授权不可提前推进与 Seal covered_set 的收敛向量。
- `conformance-vectors.md`：redaction 保留与审计可见性向量。
- `conformance-vectors.md` 与 `capability-fixture.json`：委派、撤销回滚、Strand discussion track 不继承 Strand synthesis 权限与审批约束向量。
- `privacy-security-fixture.json`：hidden resource、private contact discovery、plaintext-visible service、private blob 与 blind push 的隐私回归向量。
- `mimi-interop-fixture.json`：MIMI provider directory、room binding、content mapping、identifier query、consent、proxy download 与 unsupported draft 的 fixture cases，已注册为 `ak.vector.mimi.*`。

### 4.2 State resolution 向量

本节为优先级示例，完整必测集合以 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 为准。以下为优先必测项：

- `ak.vector.cba_lattice.data_event_accepts_without_seal_finality.v1`
  - 输入带有效 `seal_ref` 与 `auth_context` 的 DataEvent。
  - 期望 reducer 输出：本地接受、可投影、无需被 Seal 覆盖。
- `ak.vector.cba_lattice.control_move_requires_seal_basis_and_seal.v1`
  - 输入带有效 `seal_basis` 的 Control Move 及缺失/错误 basis 的负向样例。
  - 期望输出：Control Move 先 pending，只有被有效 Seal 覆盖并重算 `state_root` 后进入 `sealed`。
- `ak.vector.cba_lattice.same_batch_does_not_advance_authorization_basis.v1`
  - 输入同一 ordered submit batch 内相互依赖的 Control Move。
  - 期望输出：同批前序 effect 不提前成为后续授权 basis，依赖方必须等待后续 Seal。

### 4.3 Redaction 向量

本节为优先级示例，完整必测集合以 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 为准。

- `ak.vector.redaction.preserve_fields.v1`
  - 输入 target event + redaction event（不同时序）。
  - 期望输出：仅保留被允许的字段，其余不可逆地清除；事件 envelope 不可被改写。
- `ak.vector.redaction.policy_scope.v1`
  - redaction 对已归档事件、加密事件、外部可见字段的影响。
  - 期望输出：索引与审计可见性一致，不可把 redaction 解读为物理删除。

### 4.4 Capability 向量

本节为优先级示例，完整必测集合以 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 为准。

- `ak.vector.capability.delegate_chain.v1`
  - grant 链条（多层委派）与 selector 条件（时间、对象、速率）冲突场景。
  - 期望输出：可验证且具备时间边界的派生有效性。
- `ak.vector.capability.revoke_rollback.v1`
  - 撤销后既有事件在历史范围内的生效/失效行为。
- `ak.vector.capability.approval_constraint.v1`
  - high risk action 未满足 approval 时应软拒绝或进入 proposal 流程。

**Capability coverage plan（normative gate plan）**：进入 `v1-conformance-certified` 前，capability fixture / runner MUST 增加并执行下列负向与正向覆盖；在对应 `ak.vector.*` 行进入 `vector-registry.json` active 状态前，实现不得声称这些行为已通过 vector gate：

规模型授权上限已由 active `ak.vector.scalability.capability_limits.v1` 与 `scalability-limits-fixture.json` 的生成式 runner 固化：delegation chain 深度 5、单次展开 1,025 grants、单 grant 65 constraints、selector AST 深度 17 均必须 fail closed；这些 case 与下列语义型 capability coverage 同属认证闭包，不得只运行其一。

- 首发 grant issuer 上界校验：grant 的 `actions[]` / `resources[]` 超出 issuer 当前 effective capability 时 MUST 拒绝（`grant_exceeds_issuer_authority`），并覆盖 freshness unknown fail-closed。
- effective validity window 归一化：`effective_not_before >= effective_expires_at` MUST 拒绝（`grant_validity_window_empty`）。
- `delegation_expiry_seal` 防滚动续期：re-delegate MUST NOT 刷新整条链的 expiry seal，任何 widened expiry MUST 拒绝。
- delegation cycle detection：含 revoke-then-re-delegate 与 batch 场景的环 MUST 拒绝（`delegation_cycle`）。
- `depends_on_moderation_state` 静态 lint：满足 capabilities.md §18.1 条件而缺少显式 `true` 的 grant MUST schema-fail。
- freshness 风险表：高风险 `stale` / `unknown` MUST fail closed；中风险 `unknown` MUST fail closed；本地 pending tier 在 `unknown` 下 MUST 不对外同步。
- 跨 grant 全局合并：任一命中 grant 的 deny / quarantine / require_review MUST 全局生效，runner MUST 覆盖"MUST NOT 逐 grant 独立求值后取任一 ALLOWED 即放行"的负向样例。

### 4.5 Client Sync coverage plan

进入 `v1-conformance-certified` 前，sync fixture / runner MUST 增加并执行下列覆盖；在对应 `ak.vector.*` 行进入 `vector-registry.json` active 状态前，实现不得声称这些行为已通过 vector gate：

- explicit delivery ack：`ack_token` 签发、累计单调 ack、cross-binding 校验、invalid ack 拒绝，以及服务端丢弃未确认 to-device 消息后 `to_device.lost=true` 的升级路径。
- cursor binding：`filter_digest` canonical 计算、query-scope digest 绑定、跨 scope 回传 cursor 时返回 `cursor_integrity_invalid`。
- limited timeline state：实现返回确定性 `state_at_window_start` 时，MUST 使用 limited timeline 首事件 `prev_refs` 因果闭包在最近 Seal basis 下的 deterministic join；无法计算时 MUST 使用安全降级而不得伪造状态。

## 5. 组件级测试矩阵（必测）

| 组件 | MUST 覆盖 | SHOULD 覆盖 |
| --- | --- | --- |
| Minimal/Full Client | filter、pagination、state_after、decryption_pending | snapshot frontier、causal wait |
| Events API | submitEvent、eventIdempotency、eventDigest 验证、signature 校验 | snapshot generation、event batch receipt |
| Principal Server | sync stream 续传、backfill 顺序、重复过滤、加密转发不解密、来源限速与回压 | 多上游 federation、快照指针 |
| E2EE Client | epoch 回填、to-device、removed 成员 fail-closed | 本地 search 协调 |
| Applet Bridge | 注册签名、transaction 幂等、namespace 冲突、未授权写入拒绝 | portal realm 映射 |
| MIMI Provider Facade | draft pinning、room binding、KeyPackage claim、message/content roundtrip、policy mapping、identifier privacy、consent isolation、proxy download、unsupported draft fail-closed | MIMI content extension lossless preservation |
| Policy Server | decision 签名、replay 保护、hard_deny / quarantine 语义、rate_limit / spam 风险码 | federation 再检 |
| Identity Registry | DID log 一致性、witness receipt、method adapter | witness-only、read-replica |
| Moderation | report / queue item schema、E2EE evidence package、franking、operator ACL | appeal / audit trail |
| Agent Runtime | capability grant 解释、knowledge source 声明、owner presence policy、join policy、capability revoke | approval UX、tool call audit |

**向量与 operation clause 覆盖（normative）**：领域行为的 active 向量以 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 为真相源；HTTP/API 行为以 [`operation-clause-registry.json`](../../artifacts/registry/operation-clause-registry.json) 的 selector-based clause closure 为认证入口。runner MUST 先计算 profile 继承后的 `required_endpoints`，再对每个 operation 执行全部匹配的 active `AK-OP-NNN` clause；OpenAPI shape、认证、错误、限额、幂等/uncertain outcome、stream recovery、partial outcome 与 privacy evidence 任一缺失，均不得声明该 profile 为 `v1-conformance-certified`。prose 或 OpenAPI 形状检查不能替代 registry 声明的行为证据。

不变量（normative）：实现 **MUST NOT 仅凭通过现有向量集合就宣称尚未被 registry active vectors 覆盖的行"已认证覆盖"**；某行的 gate 是否生效 MUST 以 vector-registry 的 active 状态、fixture 证据与 runner 断言为准（见 §6.1），不得以本表"MUST 覆盖"承诺或任何 prose 列举替代该查询。

## 6. 执行与发布要求

- 每个实现 MUST 提供覆盖结果文档，声明通过/失败的 vector 列表。
- 每条失败向量必须包含最小复现实例。
- 实现 MAY 发布未全部通过向量的 profile 支持声明，但 MUST NOT 将该 profile 标记为“完全互操作”；分级声明规则见 §6.1。
- 本套件目标是在 v1 reducer/schema profile 下形成稳定收敛，避免为实现差异引入新 profile 版本。

### 6.1 发布分级

规范文本闭环不等于实现生态已经稳定。Arkret 发布时 SHOULD 使用以下分级：

| 标签 | 允许用途 | 必须满足 |
| --- | --- | --- |
| `v1.0.0` | 对外发布稳定规范基线。 | `zh/` + `artifacts/` registry lint 通过；`core_event_store`、`chat_mvp`、`kanban_mvp` 的 schema / fixture / profile 已冻结；OpenAPI、cryptographic fixture 和 Markdown JSON 示例不得包含未发布占位、非 active wire 字段、未注册 Event kind 或 schema-invalid `constraint_type`。只做结构验证的 fixture MUST 声明 `fixture_kind="schema_only"`，其占位 nonce / ciphertext / signature 不计为 cryptographic vector。 |
| `v1-interop-preview` | 多实现试验互通。 | 至少两个独立实现通过同一 reference validator 的 `core_event_store` 向量，并能重放官方 sync / state / capability fixture。 |
| `v1-conformance-certified` | 某实现宣称完全通过指定 profile。 | reference validator、reference reducer、reference authz evaluator 和 conformance runner 已发布；canonical JSON、Event Envelope negative vectors、CBA/Lattice、capability、privacy/security、sync 和 snapshot vectors 均由 CI 或公开认证报告执行；并且 profile operation closure 中每个 endpoint 的全部 active `AK-OP-NNN` clause 均有不可变证据。英文或其他翻译不得作为 stale source of truth 发布。 |

当前仓库仍是 candidate，尚未发布 `v1.0.0` 稳定基线。只有 §6.1 的 stable gate 全部通过并完成显式发布后，仓库才可切换为 `v1.0.0`；在此之前实现只能声明“试验性支持某些 v1 profile”，不得声明稳定规范兼容或 `v1-conformance-certified`。

若某 profile 的 payload schema 仍使用宽泛结构（例如 `state_content` 或 `generic_standard_content`），该 profile 的 stable 声明必须额外依赖 reference reducer / validator 中的语义校验，不能只依赖 JSON Schema 通过。

### 6.2 Conformance Verifier（一致性验证机构）

**Conformance Verifier** 是协议定义的中立角色：运行本 conformance suite（按 §2 的 profile 入口与 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 注册的向量集合），并对**通过**结果签发 verification artifact 的机构。verification artifact MUST 至少包含：

- `verification_run_id` — 本次 suite 运行的标识；
- `artifact_digest` — artifact 内容 hash（`sha256:<hex>`）；
- `artifact_ref` — artifact 的检索引用（URI 或 transparency-log 引用）；
- verifier 的 DID（`verifier_did`）与其对 `profile_id`、`verification_run_id`、`artifact_digest`、`artifact_ref`、verifier 与时间戳的签名；
- 验证时间戳（与可选 `expires_at`）。

`ServiceDescribe.verified_profiles` 的每个条目（`claim_kind="conformance_verified"`）引用一个这样的 verification artifact；字段约束与客户端校验义务见 [`service-surface.md`](../sync/service-surface.md) §3.0 与 `ak.schema.service_describe.v1`。协议只绑定本节定义的角色与 artifact 形态，不绑定任何具体验证工具或机构名。

> informative：`cotest` 是该角色的一个参考实现。
