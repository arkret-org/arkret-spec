---
title: Conformance Suite（自动化互操作测试）
status: candidate
normative: true
stability: v1
updated: 2026-07-30
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
- Station Events API / Station sync surface / E2EE / applet 关键接口

Schema 依赖由注册 Event kind 与 closed payload schema 决定；Realm、Circle 与 Sidecar 使用固定 v1 领域 reducer。v1 不使用顶层 `space_version` wire 字段。

## 2. 测试角色（Profile）

完整 profile 集合、角色分类和 requirement blocks 的机器真相源是 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json)。本节只列首轮 release gate / 文档阅读优先子集；测试 runner MUST 枚举 JSON 中的 `implementation_profiles`、`deployment_profiles` 与 `hardening_profiles`(capability-negotiation profile)，并单独枚举 `vector_groups`(conformance 向量分组，`ak.vector_group.*` 命名空间，非可协商能力)，不得把下列清单解释为穷尽集合。

**向量适用性闭包（normative）**：[`vector-registry.json`](../../artifacts/registry/vector-registry.json) 中每个 active vector MUST 恰好声明一个适用性 selector：`scope="universal"`、`applies_to_profiles[]`、`applies_to_vector_groups[]` 或 `applies_to_fixtures[]`。单值 `profile` 字段禁止出现。某 profile 的认证集合等于：（a）`scope="universal"`；（b）直接列出该 profile 的向量；（c）该 claim 明确包含的 vector group 向量；（d）该 profile 及其全部 `inherits[]` 的 `required_fixtures[]` 所映射向量的并集。runner MUST 先计算继承后的 fixture closure，再按集合去重；未命中该闭包的 vector 不得被实现或认证器自行猜测为必测或免测。fixture selector 只是适用性索引，`source_refs[]` 仍必须包含同一 fixture，二者由 lint 逐字校验。

**规范条款反向覆盖（normative）**：上面的适用性闭包只证明"每个 active vector 都有消费者"，不能证明"每条可测试 MUST 都有测试"。反方向由 [`normative-clause-registry.json`](../../artifacts/registry/normative-clause-registry.json) 承载：每条登记条款绑定稳定 `clause_id`、精确 `source_anchor`（文件 + 章节 slug）、该章节当前正文的 `section_digest`、`testability_grade`（`vector` / `api_shape` / `audit`）以及 `evidence_refs[]` 或显式 `test_plan`。release gate MUST 校验四件事：anchor 指向的章节存在；`section_digest` 与当前正文一致；`vector` 级条款的 `evidence_refs[]` 全部是 active vector；非 `vector` 级条款声明了非空 `test_plan`。因此在已登记章节内新增或修改 normative 文本会直接使门禁失败，直到条款与其证据被重新复核。

该 registry 的覆盖面由其 `coverage_scope` 显式声明，当前限于 wire、安全、隐私、授权、reducer、状态机与分布式写入七类高风险可观察义务。它**不是**对 `spec/v1/zh` 全部规范语句的机械编号——那只会制造无意义的 MUST。门禁全绿只证明"每条已登记条款有活证据、且已登记章节未静默漂移"，MUST NOT 被解读为"规范中每条 MUST 都已被测试覆盖"。在上述类别内新增协议义务时 MUST 在同一次变更中新增或更新条款。

**Fixture runner 归属（normative）**：随件 fixture 顶层 `runner.kind` 是执行层的机读入口，其封闭词表、执行契约摘要与 contract owner 以 [`runner-kind-registry.json`](../../artifacts/registry/runner-kind-registry.json) 为唯一真源；owner 只维护协议执行契约，不指定验证工具。未知 kind MUST 在 lint 与 conformance 加载阶段 fail closed。`named_suite.runner.entrypoint` 是工具中立 suite id，MUST 匹配 `^ak\.suite\.[a-z0-9_.-]+\.v1$`；验证器自行映射到本地实现，未知、语法无效或未映射 suite id MUST fail closed。每个 `runner.kind=named_suite` fixture MUST 至少被一条 active vector 的 `applies_to_fixtures[]` 或 `source_refs[]` 索引，lint 必须双向校验，避免 profile 的 fixture closure 只剩无关 universal vector。`json_schema_validation_cases` runner MUST 逐 case 解析 `schema_ref`、用声明的 JSON Schema dialect 校验 `instance`，并将结果与 `expect_valid` 精确比较；`json_schema_and_semantic_cases` 在完成同一 schema 步骤后，还 MUST 把 `semantic_outcome` 与 `expected_reason_code` 交给 reducer/validator 断言。`required_runner_suites[*].artifact_fixture` MUST 指向 `artifacts/fixtures/` 中存在的随件文件；runner 不得把缺失的本地私有夹具当作 profile 已满足。

`runner-kind-registry.json#runner_kinds[*].execution_status` 是执行契约发布状态。`active` vector 表示“规范要求执行”，不表示任何外部参考仓库已经实现；它只有在所有 `applies_to_fixtures` 的 runner kind 均为 `contract_published` 时才可登记。认证器必须实际执行本地映射并保存逐 case 结果；仅看到 `active` 或 `contract_published` 不得声称 gate 已通过。`planned` / 未知状态的 runner 不得进入 `v1-conformance-certified` 闭包。

Profile 分两类（分类口径以 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 的 `profile_roles` / `role` 为准）:**实现 profile**（声明实现承担的角色与能力集合）与 **hardening profile**（在某实现 profile 之上叠加的安全加固 overlay,`role=admin`,不单独作为可声明的实现角色）。

**实现 profile**:

- `ak.profile.minimal_client.v1`
- `ak.profile.core_event_store.v1`（minimal interop floor；分层口径见 [`conformance-profiles.md`](./conformance-profiles.md) §2.1，是仅声称 v1 Event Store interop 时的最小声明层，非完整实现角色）
- `ak.profile.chat_mvp.v1`
- `ak.profile.kanban_mvp.v1`
- `ak.profile.full_client.v1`
- `ak.profile.e2ee_client.v1`
- `ak.profile.station_events_api.v1`
- `ak.profile.station.v1`
- `ak.profile.federation_minimal.v1`
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

- `ak.profile.mls.minimal_metadata_realm.v1`
- `ak.profile.traffic_metadata_hardened.v1`
- `ak.profile.key_backup.memory_hard.v1`
- 安全域 checkpoint 维护

## 3. OpenAPI 与 Transport 一致性

### 3.1 OpenAPI shape tests

每个实现必须通过以下验收：

- `/_arkret/` 下公开至少包含 `service/identity/events/account/snapshot/blob/authz` 关键 operation。
- 服务 `operation_id` MUST 以 `artifacts/registry/contract-registry.json#operation_registry` 为 canonical source，并通过生成的 `artifacts/registry/operation-registry.json` 供实现消费；operation DTO 字段集合 MUST 以 JSON Schema 与生成的 `artifacts/reports/operation-schema-index.json` 为机器索引；标准 `Event.kind` MUST 以 `artifacts/registry/event-kind-registry.json` 为唯一 generated registry view，并遵守其 `wire_scope` / `reducer_input` 分类；协议 typed ID 前缀 MUST 以 `artifacts/registry/id-kind-registry.json` 为唯一 generated registry view；标准 Event payload class MUST 以 `artifacts/schemas/event-payload.schema.json` 的 `$defs` 为唯一 source of truth，但完整 payload validation MUST 通过 `event-envelope.schema.json` 的 Event.kind dispatch 或等价 registry dispatch 执行，不得直接把 `event-payload.schema.json` 定义包根 schema 当作接受条件。OpenAPI、非 HTTP binding 与说明性 `service-api-schema.mdx` 不得声明 catalog / registry 中不存在的 operation；Event validator、reducer 与 fixture 不得声明 registry 中不存在的标准 `ak.*` event kind，也不得把 `actor_private_event` 当作共享 durable reducer input；Signal 与 DeviceMessage kind 不得登记成 Event.kind；schema、fixture、文档示例和 DTO 不得使用未注册的 `ak:<kind>:` typed ID 前缀。
- 相同操作在 gRPC/WebSocket/SSE 等替代 transport 下，语义输入输出一致（可通过对同一 fixture 做幂等重放对比）。

### 3.2 Canonical envelope tests

- canonical JSON 字段顺序与空值处理一致。
- Event Envelope 校验必须按 kind 选择 payload schema；active 标准 kind 未命中 payload class 或 payload class 校验失败，必须在 reducer 前以 `schema_violation` 失败。
- 同一请求在不同服务节点（Station Events API / Station sync surface）可重放得到一致事件 hash 或查询结果边界。

## 4. Conformance 向量分层

### 4.1 Sync / encoding 向量（已在现有文件）

- `authority-commit-fixture.json`、`cursor-negative-fixture.json` 与 `privacy-security-fixture.json`：独立 stream 顺序、分页缺口、snapshot、MLS 当前 epoch 与 decryption_pending。
- `conformance-vectors.md` 与 `crypto-signature-fixture.json`：canonical JSON、digest、签名绑定、真实 Ed25519 detached JWS、HLC、cursor、encrypted envelope。
- `conformance-vectors.md` 与 `authority-commit-fixture.json`：独立 Realm/Circle/Sidecar authority stream、Event acceptance、state-changing Event RealmCommit finality、安全状态的唯一确认顺序与治理 Station handoff 向量。
- `conformance-vectors.md`：redaction 保留与审计可见性向量。
- `conformance-vectors.md` 与 `capability-fixture.json`：委派、撤销回滚、Strand discussion track 不继承 Strand synthesis 权限与审批约束向量。
- `privacy-security-fixture.json`：hidden resource、private contact discovery、plaintext-visible service、private blob 与 blind push 的隐私回归向量。
- `mimi-interop-fixture.json`：MIMI provider directory、room binding、content mapping、identifier query、consent、proxy download 与 unsupported draft 的 fixture cases，已注册为 `ak.vector.mimi.*`。

### 4.2 State resolution 向量

本节为优先级示例，完整必测集合以 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 为准。以下为优先必测项：

- `ak.vector.authority_commit_projection.ordinary_event_accepts_without_commit_finality.v1`
  - 输入一条 Event，其 `authorization_ref` 在当前治理 Station 的已提交 typed state 中解析为有效授权实例。
  - 期望 reducer 输出：本地接受、可投影、无需被 RealmCommit 覆盖。
- `ak.vector.authority_commit_projection.state_change_requires_expected_revision_and_commit.v1`
  - 输入带有效 `expected_revision` 的 state-changing Event 及缺失/错误 basis 的负向样例。
  - 期望输出：state-changing Event 先 pending，只有取得该 stream 上有效的 RealmCommit 后进入 `committed`；v1 没有 `state_root`，判据是 Commit 本身，不是重算出来的状态根。
- `ak.vector.authority_commit_projection.same_batch_does_not_advance_authorization_basis.v1`
  - 输入同一 ordered submit batch 内相互依赖的 state-changing Event。
  - 期望输出：同批前序 projected write 不提前成为后续授权 basis，依赖方必须等待后续 RealmCommit。

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

- `ak.vector.capability.authority_chain.v1`
  - grant 链条（多层委派）与 selector 条件（时间、对象、速率）冲突场景。
  - 期望输出：可验证且具备时间边界的派生有效性。
- `ak.vector.capability.revoke_rollback.v1`
  - 撤销后既有事件在历史范围内的生效/失效行为。
- `ak.vector.capability.approval_constraint.v1`
  - high risk action 未满足 approval 时应软拒绝或进入 proposal 流程。

**Capability semantic coverage（normative gate）**：下列行为已由 `protocol-edge-cases-fixture.json` 的 active 向量固化：`ak.vector.capability.issuer_authority_bound.v1`、`ak.vector.capability.validity_window.v1`、`ak.vector.capability.authority_expiry_commit.v1`、`ak.vector.capability.authority_cycle.v1`、`ak.vector.capability.moderation_dependency.v1`、`ak.vector.capability.freshness_risk_matrix.v1`、`ak.vector.capability.global_decision_merge.v1`。进入 `v1-conformance-certified` 前，capability runner MUST 执行其全部正负例并保存逐 case 结果：

规模型授权上限已由 active `ak.vector.scalability.capability_limits.v1` 与 `scalability-limits-fixture.json` 的生成式 runner 固化：delegation chain 深度 5、单次展开 1,025 grants、单 grant 65 constraints、selector AST 深度 9 均必须 fail closed；这些 case 与下列语义型 capability coverage 同属认证闭包，不得只运行其一。

- 首发 grant issuer 上界校验：grant 的 `actions[]` / `resources[]` 超出 issuer 当前 effective capability 时 MUST 拒绝（`grant_exceeds_issuer_authority`），并覆盖 freshness unknown fail-closed。runner MUST 覆盖 owner authority 的两个合法来源：(a) authority-root typed current result（`realm_authority_root`）的 current controller 凭同一 RealmCommit basis 下的 registered inclusion proof 取得 effective `ak.realm.owner`，其上界来自该 typed current result 的 `grant_authority_actions`；(b) 由此派生的可撤销 co-owner `ak.realm.owner` grant。负例 MUST 包含：以 `created_by`、membership 或 `realm_state.owner` 一类 projection mirror 回退充当上界来源，以及 controller 不匹配 / root typed current result 缺失（`realm_authority_controller_mismatch` / `realm_authority_root_missing`）。
- effective validity window 归一化：`effective_not_before >= effective_expires_at` MUST 拒绝（`grant_validity_window_empty`）。
- `authority_expiry_commit` 防滚动续期：re-delegate MUST NOT 刷新整条链的 expiry authority commit，任何 widened expiry MUST 拒绝。
- delegation cycle detection：含 revoke-then-re-delegate 与 batch 场景的环 MUST 拒绝（`authority_cycle`）。
- `depends_on_moderation_state` 静态 lint：满足 capabilities.md §18.1 条件而缺少显式 `true` 的 grant MUST schema-fail。
- freshness 风险表：高风险 `stale` / `unknown` MUST fail closed；中风险 `unknown` MUST fail closed；本地 pending tier 在 `unknown` 下 MUST 不对外同步。
- 跨 grant 全局合并：任一命中 grant 的 deny / quarantine / require_review MUST 全局生效，runner MUST 覆盖"MUST NOT 逐 grant 独立求值后取任一 ALLOWED 即放行"的负向样例。

### 4.5 Client Sync coverage plan

进入 `v1-conformance-certified` 前，sync runner MUST 执行 `protocol-edge-cases-fixture.json` 中 active 的 `ak.vector.sync.delivery_ack.v1`、`ak.vector.sync.cursor_binding.v1` 与 `ak.vector.sync.state_at_window_start.v1` 全部覆盖：

- explicit delivery ack：`ack_token` 签发、累计单调 ack、cross-binding 校验、invalid ack 拒绝，以及服务端丢弃未确认 to-device 消息后 `to_device.lost=true` 的升级路径。
- cursor binding：`filter_digest` canonical 计算、query-scope digest 绑定、跨 scope 回传 cursor 时返回 `cursor_integrity_invalid`。
- limited timeline state：实现返回确定性 `state_at_window_start` 时，MUST 分别按 limited timeline 首事件 `domain_refs` 因果闭包重建普通投影，并按对应历史 confirmed RealmCommit state 取得安全/MLS 投影；无法计算时 MUST 使用安全降级而不得伪造状态。

## 5. 组件级测试矩阵（必测）

| 组件 | MUST 覆盖 | SHOULD 覆盖 |
| --- | --- | --- |
| Minimal/Full Client | filter、pagination、state_after、decryption_pending | snapshot checkpoint、causal wait |
| Events API | submitEvent、eventIdempotency、eventDigest 验证、signature 校验 | snapshot generation、event batch receipt |
| Station | sync stream 续传、backfill 顺序、重复过滤、加密转发不解密、来源限速与回压 | 多上游 federation、快照指针 |
| Auth Server | issuer-record ID/JTI 重算、canonical JWK、DPoP binding、durable exact replay/conflict/terminal outcome、原子 refresh/revoke/introspection | issuer key rotation、commit 后响应丢失与并发重试 |
| E2EE Client | epoch 回填、to-device、removed 成员 fail-closed | 本地 search 协调 |
| Applet Bridge | 注册签名、transaction 幂等、namespace 冲突、未授权写入拒绝 | portal realm 映射 |
| MIMI Provider Facade | draft pinning、room binding、KeyPackage claim、message/content roundtrip、policy mapping、identifier privacy、consent isolation、proxy download、unsupported draft fail-closed | MIMI content extension lossless preservation |
| Identity Registry | DID log 一致性、witness receipt、method adapter | witness-only、read-replica |
| Moderation | report / queue item schema、E2EE evidence package、franking、operator ACL | audit trail |
| Agent Runtime | capability grant 解释、knowledge source 声明、owner presence policy、join policy、capability revoke | approval UX、tool call audit |

**向量与 operation clause 覆盖（normative）**：领域行为的 active 向量以 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 为真相源；HTTP/API 行为以 [`operation-clause-registry.json`](../../artifacts/registry/operation-clause-registry.json) 的 selector-based clause closure 为认证入口。runner MUST 先计算 profile 继承后的 `operation_requirements`，再对每个 operation 执行全部匹配的 active `AK-OP-NNN` clause；OpenAPI shape、认证、错误、限额、幂等/uncertain outcome、stream recovery、partial outcome 与 privacy evidence 任一缺失，均不得声明该 profile 为 `v1-conformance-certified`。prose 或 OpenAPI 形状检查不能替代 registry 声明的行为证据。

不变量（normative）：实现 **MUST NOT 仅凭通过现有向量集合就宣称尚未被 registry active vectors 覆盖的行"已认证覆盖"**；某行的 gate 是否生效 MUST 以 vector-registry 的 active 状态、fixture 证据与 runner 断言为准（见 §6.1），不得以本表"MUST 覆盖"承诺或任何 prose 列举替代该查询。

## 6. 执行与发布要求

- 每个实现 MUST 提供覆盖结果文档，声明通过/失败的 vector 列表。
- 每条失败向量必须包含最小复现实例。
- 实现 MAY 发布未全部通过向量的 profile 支持声明，但 MUST NOT 将该 profile 标记为“完全互操作”；分级声明规则见 §6.1。
- 本套件目标是在 v1 reducer/schema profile 下形成稳定收敛，避免为实现差异引入新 profile 版本。

### 6.1 发布分级

规范文本闭环不等于实现生态已经稳定。Arkret 发布时 MUST 使用以下封闭分级；实现与发布方不得自造等价标签绕过各级门槛：

| 标签 | 允许用途 | 必须满足 |
| --- | --- | --- |
| `v1.0.0` | 对外发布稳定规范基线。 | MUST 满足 [`release-readiness.md` §5](../overview/release-readiness.md) 的全部 stable promotion gate；该节是唯一权威清单。 |
| `v1-interop-preview` | 多实现试验互通。 | 至少两个独立实现通过同一 reference validator 的 `core_event_store` 向量，并能重放官方 sync / state / capability fixture。 |
| `v1-conformance-certified` | 某实现宣称完全通过指定 profile。 | reference validator、reference reducer、reference authz evaluator 和 conformance runner 已发布；canonical JSON、Event Envelope negative vectors、authority-commit projection、capability、privacy/security、sync 和 snapshot vectors 均由 CI 或公开认证报告执行；并且 profile operation closure 中每个 endpoint 的全部 active `AK-OP-NNN` clause 均有不可变证据。英文或其他翻译不得作为 stale source of truth 发布。 |

当前仓库仍是 candidate，尚未发布 `v1.0.0` 稳定基线。只有 §6.1 的 stable gate 全部通过并完成显式发布后，仓库才可切换为 `v1.0.0`；在此之前实现只能声明“试验性支持某些 v1 profile”，不得声明稳定规范兼容或 `v1-conformance-certified`。

若某 profile 的 payload schema 仍使用宽泛结构（例如 `state_content` 或 `generic_standard_content`），该 profile 的 stable 声明必须额外依赖 reference reducer / validator 中的语义校验，不能只依赖 JSON Schema 通过。

### 6.2 Conformance Verifier（一致性验证机构）

**Conformance Verifier** 是协议定义的中立角色：运行本 conformance suite（按 §2 的 profile 入口与 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 注册的向量集合），并对**通过**结果签发 verification artifact 的机构。verification artifact MUST 至少包含：

- `verification_run_id` — 本次 suite 运行的标识；
- `artifact_digest` — artifact 内容 hash（`sha256:<hex>`）；
- `artifact_ref` — artifact 的检索引用（URI 或 transparency-log 引用）；
- verifier 的 DID（`verifier_id`）与其对 `profile_id`、`verification_run_id`、`artifact_digest`、`artifact_ref`、verifier 与时间戳的签名；
- 验证时间戳（与可选 `expires_at`）。

`ServiceDescribe.verified_profiles` 的每个条目（`claim_kind="conformance_verified"`）引用一个这样的 verification artifact；字段约束与客户端校验义务见 [`service-surface.md`](../sync/service-surface.md) §3.0 与 `ak.schema.service_describe.v1`。协议只绑定本节定义的角色与 artifact 形态，不绑定任何具体验证工具或机构名。

> informative：`cotest` 是该角色的一个参考实现。
