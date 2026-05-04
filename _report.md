# Contrix Spec v1 — 最终评审报告

**评审范围**：`contrix-spec/zh/` 全部 50+ 文件 + `artifacts/` 全部机器契约
**评审角色**：发布前最后守门员
**评审日期**：2026-05-04
**评审结论**：**不建议直接发布为 `v1.0-stable`**。当前状态适合标记为 `v1-core-rc` (与 `release-readiness.md` §2 一致)，但存在多处 **BLOCKING** 级问题，会阻止两个独立实现互通。建议先解决本报告 §2 列出的 23 个 BLOCKING 项后，再进入 `v1-interop-preview` 与 `v1.0-stable`。

---

## 0. 评审方法

- 完整阅读 `overview/` (架构、glossary、current-model、matrix-core-differences、release-readiness)
- 完整阅读 `models/object-model-core.md`、`data-structures.md`（前 700 行）以锚定字段语义
- 完整阅读 `authz/event-auth-state-resolution.md` (核心收敛规则)
- 完整阅读 `artifacts/registry/contract-catalog.json` 摘要、`error-code-registry.json`、`id-kind-registry.json`、`mirror-manifest.json`、`registry-manifest.json`
- 委托四组并行子代理（identity+crypto-media、authz+security+models、sync+discovery、extensions+conformance+artifacts）做深度评审
  - 第四组（extensions/conformance/artifacts）因配额被中断，相关章节由我亲自手动抽查补足
- 跑通 `python tools/artifact_pipeline.py check` —— 通过（registry 干净、镜像无 drift）
- 文本字段交叉检查若干高风险声明，避免 agent 误报

总共归并具体发现 **≈ 480 条**，本报告按优先级汇总并合并相互重复的项目。

---

## 1. 总体评价（先讲优点）

Contrix 的协议设计骨架非常扎实，是当前去中心化协作领域少见的工程化提案：

- **架构正交**：identity / write / distribution / projection / presentation / confidentiality / portability 七个 plane 拆分清晰，避免了 Matrix 把 room 当作万能容器、Atproto 把 PDS 当作万能写入入口的两个极端；
- **对象模型现代**：Flow + branch + Space(kind=board/list) + Morph + Relation + View 的组合，第一次让 chat、kanban、agent 协作、文档共享同一套底层语义；
- **安全立场明确**：DID-first 身份、capability + constraint、per-actor event chain、MLS-bound state、`plaintext_visible_services` 透明度声明、auditable E2EE 双 profile、minimal-metadata pseudonymous DID 都很有想法；
- **机器契约**：`artifacts/registry/contract-catalog.json` 作为 canonical source、generated registry views、mirror manifest、`tools/artifact_pipeline.py` 作为统一流水线，把规范和工件锁在一起，是同类项目的最佳实践；
- **范围克制**：`release-readiness.md` 明确把 `core_event_store`、`chat_mvp`、`kanban_mvp` 拆成可启动闭环，避免“全部 v1 或不算 v1”的死局。

下面所有问题，是在这个高水准基础上做最后一道筛选时发现的。它们大多数不是设计错误，而是“多次迭代后留下的 micro-drift”。但因为协议规范一旦发布即冻结字段名、错误码、wire 形状和签名输入，这些 micro-drift 会立刻变成永久互操作债务，所以必须在发布前清掉。

---

## 2. 阻塞性问题（BLOCKING — 必须在 v1.0-stable 前修复）

按修复成本由小到大列出，方便排期。每条都列了位置和修复建议。

### B-01. CHANGELOG.md 是空目录

- 位置：仓库根 `CHANGELOG.md`
- 现状：`CHANGELOG.md` 实际上是个空目录而不是文件；`README.md` 没有引用它，但发布物里出现一个名为 `CHANGELOG.md` 的空目录会让分发站、镜像、压缩包工具行为异常。
- 修复：删除该目录或换成真正的 `CHANGELOG.md` 文件，并填入 `v1-core-rc` 的发布条目。

### B-02. Capability Grant 在三处使用三种不同 envelope shape

- 位置：
  - `models/data-structures.md` §13 用 `id` / `type:"capability"` / `actions[]` / `resources[]` / `constraints[]` / `proofs[]`（复数）
  - `authz/capabilities.md` §3 例子同上（一致）
  - `authz/grant-constraint-schema.md` §2 用 `grant_id` / `type:"capability_grant"` / `scope` (object) / `proof` (单数) / `not_before` / `expires_at`
  - 工件 `artifacts/schemas/capability-grant.schema.json` 与前两者一致
- 影响：实现者完全不知道哪一个是 wire form。这是当前最致命的字段命名 drift，会立即阻断互操作。
- 修复：以 `data-structures.md` §13 + schema 为准，把 `grant-constraint-schema.md` §2 envelope 整段重写为示例引用，强调 envelope 由 §13 定义，本文件只描述 constraint 内部结构。

### B-03. `history_visibility` 的 `invited` / `restricted` 在三个文件语义不一致

- 位置：
  - `authz/event-auth-state-resolution.md` §6：`invited` = "可读取 stripped preview state"
  - `models/conversation-model.md` §12：`invited` = "从被邀请时刻起可见"
  - `models/data-structures.md` §4 的 enum 定义没给详细语义
- 影响：同一枚举三种语义，任何 client 跨实现进入 invited Space 时见到的历史范围都不同。这是协议级行为差异，比字段命名更危险。
- 修复：把 `event-auth-state-resolution.md` §6 的描述提升为 normative，让另两处明确指向它；删除其它两处的语义描述。

### B-04. Constraint 在两个文件双源描述

- 位置：`authz/constraint-schema.md`（声称是规范源）vs `authz/grant-constraint-schema.md`
  - constraint-schema 用 `effect: allow|deny|quarantine|require_review` 与 typed objects（recurrence、condition.when、approval_workflow.mode 等）
  - grant-constraint-schema 用 `delegation: {allowed, max_depth, subset_only}` 等不同 inner shape；`approval mode: "required"` 不在 §9 enum 内
- 影响：实现者无法判断哪个文件 normative；schema 工件也只覆盖前者的部分字段。
- 修复：把 `grant-constraint-schema.md` 重写为 100% 引用 `constraint-schema.md` 的薄包装，禁止该文件引入任何新字段或新 enum 值。

### B-05. `grant-constraint.schema.json` 工件字段不全

- 位置：
  - `constraint-schema.md` §3.1 `recurrence`、§3.2 `max_duration` / `max_session_duration` / `inactivity_timeout`、§4.1 `condition.when` DSL、§4.2 `sensitive_handling` / `sensitive_fields`、§6.2 `allowed_view_kinds` / `allowed_view_renderers`、§9.2 `approval_threshold` 多种枚举值——这些都未在 `artifacts/schemas/grant-constraint.schema.json` 中编码。
- 影响：声称由 schema 校验的 fixture 全部漏掉这些约束类型；reference validator 不可能 enforce 文档语义。
- 修复：把 `constraint-schema.md` 的所有 typed constraint 枚举与子结构补进 schema；同时给 `effect`、`condition.when`、`approval_threshold` 等字段加 enum 限制。

### B-06. Federation 签名 transcript 在 `federation.md` 与 `federation-wire.md` 不一致

- 位置：
  - `sync/federation.md` §3.2：要 `@method, @target-uri, @authority, content-digest, time window (created/expires)`
  - `sync/federation-wire.md` §2：要 `method, target URI, authority, date, content digest`
- 影响：完全是 RFC 9421 名义 vs 旧式名义不同，签名 bytes 不同；两个独立实现按各自文件实现就互不验证。
- 修复：以 RFC 9421 (`@method` / `@target-uri` / `@authority` / `content-digest` / `created` / `expires`) 为准，将 `federation-wire.md` §2 整段重写。

### B-07. OpenAPI 与 operation registry 严重不全

- 位置：`artifacts/openapi/contrix-service-api.openapi.yaml`
  - 大量 path（包括 `/events/batch-get`, `/events/frontier`, `/sync/subscribe`, `/sync/backfill`, `/federation/transactions/{txn_id}`, 全部 `mimi/*` / `applet/*` / `admin/*`）只有 `responses: 200: schema: type: object` 占位，没有 request body 也没有结构化响应；
  - `securitySchemes` 定义了 `bearerAuth` / `httpMessageSignature` / `mutualTls` 但 spec 顶层和绝大多数 path 没有 `security:` 块——默认结果是“匿名可调用”，与 `service-http-binding.md` §2.2 normative 要求完全相反；
  - `ErrorEnvelope.error.code` 是自由 string，未 enum 锚定到 `error-code-registry.json`；
  - 路径参数 (`event_id`, `space_id`, `txn_id`, `backup_id`) 没有 `pattern` 与 `id-kind-registry.json` 对齐；
  - `/contrix/v1/check`、`/contrix/v1/ice-config` 应当用 path-level `servers:` 覆盖（按 `service-api-schema.md` §5），但 OpenAPI 没有覆盖，会被解析成 `/api/v1/contrix/v1/check`。
- 影响：所有 SDK 生成都不可用；CI 也无法验证。`tools/artifact_pipeline.py` 当前没有 OpenAPI ↔ registry 一致性检查。
- 修复：引入“BEGIN GENERATED OPENAPI INVENTORY”机制，类比 `service-api-schema.md` 的生成块，把 path/operation_id/request body/response/security/error enum 从 `contract-catalog.json#operation_registry` + `error-code-registry.json` 自动渲染。

### B-08. `service-http-binding.md` §9 错误码表与 `api-conventions.md` §5.1、`error-code-registry.json` 三处不一致

- service-http-binding §9 漏列：`causal_conflict`, `dependency_missing`, `discussion_branch_disabled`, `digest_mismatch`, `claim_required`, `unsupported_event_kind`, `projection_incomplete`, `state_mismatch`, `aad_*`, `audit_receipt_invalidated`, `payload_digest_mismatch`, `key_unavailable`
- api-conventions §5.1 同样漏列其中一部分
- registry 定义了 42 个 code，文档表格只覆盖一半
- 影响：实现者按某一文档实现就会漏处理一半生产错误；HTTP 状态码也会出错（如 `quota_exceeded` 在 `service-surface.md` §14.1 写成 "可能 413 或 402"，registry 写 403）
- 修复：删掉两处纸面表格，统一改成"see `artifacts/registry/error-code-registry.json` (canonical)"，同时让 `tools/artifact_pipeline.py` 检查文档里所有出现的 `error.code = "..."` 字面值是否都登记在 registry 中。

### B-09. Redaction 保留字段表与 Event Envelope schema 不匹配

- 位置：`authz/event-auth-state-resolution.md` §10
  - 保留字段含 `hashes`，但 envelope schema (`models/data-structures.md` §9) 没有 `hashes` 字段，只有 `proofs[].payload_hash`
  - 清除字段含 `attachments` / `mentions` / `relations` / `client_generated`，但这四个不是 envelope 顶层字段，全部在 `payload` 里——直接写"清除 payload"已包含
  - **更严重**：保留字段不含 `actor_seq`。但 §11 明确说 rejected event 不能占据 actor chain 中的 `actor_seq`，意味着 redacted accepted 事件必须保留 `actor_seq`，否则后继事件无法验证 `actor_seq - 1` 因果链
- 影响：redaction stub 字段方案直接造成 hash 验证失败 / actor chain 断裂
- 修复：保留字段加入 `actor_seq`、删除 `hashes`、用"`payload` cleared"代替零散子字段；同步更新 `redaction-conformance-vectors.md`

### B-10. KeyPackage 在两个文件出现两套 shape

- 位置：
  - `crypto-media/encrypted-envelope-schema.md` §8.1 用 `actor_id` / `expires_at` / `signature`
  - `crypto-media/device-crypto-verification.md` §7 用 `principal_id` / `device_id` / `keypackage_id` / `device_signature` / `expires_at`
- 影响：MLS 互通的核心结构两套字段名，e2ee_client profile 无法互认 KeyPackage
- 修复：统一为 device-crypto-verification §7 形态（含 device_id、device_signature），并把 envelope-schema §8.1 改成引用

### B-11. 两个 KeyBackup 表达 (secret_storage vs key_backup) 重叠

- 位置：`crypto-media/device-crypto-verification.md` §9 `cx.secret_storage.v1` vs §10 `cx.schema.key_backup.v1`
- §9 说"客户端本地"用 secret_storage，"同步到服务"必须用 key_backup；但两者覆盖类似数据（DID recovery、mls_history、secret），fields/algorithm 不互译
- 影响：两套实现，互不兼容；KeyBackup envelope 缺少签名算法明细、`auth_data.signature` 覆盖范围未定义
- 修复：合并为单一 schema `cx.schema.key_backup.v1`，定义 `domain` enum (did_recovery / secret_storage / mls_history / external)，要求每个 domain 用独立 HKDF info 派生

### B-12. `cx_app_state_ref` MLS GroupContext extension 没有分配 codepoint

- 位置：`crypto-media/encryption-and-audit.md` §2.5 / §2.5.1
- 现状："profile-negotiated; private-use codepoint 只能在双方显式协商后使用"
- 影响：MLS GroupContext extension 在 RFC 9420 中是 IANA 注册项；无 codepoint 即无法实现 `mls_state_binding.full` profile，而该 profile 是 e2ee_client 与 sovereign_deployment 的关键
- 修复：在工件 registry 中分配 Contrix 私有 codepoint（私有用范围 0xF000–0xFFFF），写入 `event-kind-registry.json` 同级位置或独立 mls extension registry

### B-13. RYW (read-your-writes) receipt schema 缺失

- 位置：`crypto-media/encryption-and-audit.md` §3.3 step 3 normative MUST 等待 RYW receipt
- 现状：没有 schema、没有事件 kind 注册、没有 fixture
- 影响：normative MUST 没有可验证 artifact；auditable E2EE 不可实现
- 修复：注册 `cx.audit.ryw_receipt` event kind 与 schema，加入 conformance vector

### B-14. DID 通过 Push token / TURN credential 泄露

- 位置：
  - `crypto-media/devices-and-auth.md` §5：push payload `target_did: "did:web:alice.com"` 直接发给 APNs/FCM
  - `crypto-media/webrtc-signaling.md` §6.2：TURN username `1699999999:did_plc_alice` 把 DID 传给 TURN 运营方
  - `crypto-media/webrtc-signaling.md` §14：push payload 含 `sender: "did:web:alice.example.com"`
- 影响：直接违反 §1 / §6.2 同段宣称的"脱敏"目标。DID 是稳定跨 Space 标识，泄露给第三方推送/TURN 即等于泄露用户全图行为模式
- 修复：所有 push / TURN 路径只传 Space-scoped pairwise pseudonym 或一次性短期 token；按 minimal-metadata 同样处理。把这条作为 conformance MUST_NOT，加入 `privacy-security-fixture.json` 回归向量

### B-15. `default_join_rule="private"` 既被防御性 reject 又不在 enum 中

- 位置：`models/data-structures.md` §4 `default_join_rule` enum = `(public, invite, knock, restricted, knock_restricted, closed)`，无 `private`；`event-auth-state-resolution.md` §6 又特意要求 reject `private`
- 影响：v1 schema 永远不会出现 `private`，"防御性 reject" 是死代码；但有读者会把它当作合法 enum 值
- 修复：要么把规则改成"reject 任何不在 enum 内的 join_rule，列举 `private` 仅作迁移备注"，要么删掉这段；同时统一文档语言

### B-16. `cx:space:` 模糊枚举（容器 vs 安全边界）尚未传递到工件

- 位置：`models/data-structures.md` §4.1 给了决策树，但 `space.schema.json` 没有把 `boundary_profile` 默认派生规则编码（`board/list -> container`，其它标准 kind -> `security_boundary`）；`enclave` kind 在文档中是 `security_boundary`，schema 里只是普通枚举
- 影响：schema 通过的 Space object 不一定符合决策树；reducer 只能靠文档约束
- 修复：在 schema 里加 `if/then` 条件块，强制 `kind=board|list -> boundary_profile=container`；新增 conformance vector 验证

### B-17. Standard state event 列表漏 `cx.account.status` / `cx.moderation.report` / `cx.moderation.frank`

- 位置：`authz/event-auth-state-resolution.md` §8 列出 30+ standard state event，但 `account-lifecycle.md` §3 用 `cx.account.status`、`moderation.md` §3 用 `cx.moderation.report` / `cx.moderation.frank`，这些在 §4 auth_refs 表也没有对应行
- 影响：实现无法判断这些事件如何参与 state resolution，是否需要 auth_refs，state_key 如何派生
- 修复：补全 §4 auth_refs 表与 §8 state event 列表，或在对应文档明确"非 state event"并说明如何参与共享 reducer

### B-18. State event `state_key` 复合键 (`a|b|c`) 没有转义规则

- 位置：`models/conversation-model.md` §6 / `event-auth-state-resolution.md` §8 / `crypto-media/devices-and-auth.md` 多处用 `cx:flow:...|discussion|did:web:...`、`{principal_id}|{device_id}` 等管道分隔字符串
- 影响：DID 字符可以包含管道字符（DID grammar 允许 `path-abempty`），出现碰撞的可能性虽然小但完全不可控；实现者不知道是否要 URL-escape、是否长度受限
- 修复：定义 canonical state_key encoding：要么用 `sha256(canonical_json([part1, part2, ...]))`，要么用 percent-encoding；写入 `encoding.md` 并加 conformance vector

### B-19. `Message.branch` enum 锁死 vs `FlowBranch.name` 开放有冲突

- 位置：`models/data-structures.md` §6.4 Message `branch` 是 `enum(discussion)`（固定），但 §6.1 FlowBranch.name 是任意 `^[a-z][a-z0-9_]{0,63}$`；profile 可声明新 branch name
- 影响：未来 profile 想在新 branch 名（如 `review`）下挂消息，必须修改 v1 wire schema；与 `current-model.md` 的开放性原则冲突
- 修复：把 Message.branch 改成 string pattern，由 schema/profile 限制；保留 v1 reducer 默认只处理 `discussion` 但 wire form 不锁

### B-20. `conformance-profiles.md:36` 提到 "Flow（含 `card` / `room` kind）"

- 位置：`zh/conformance/conformance-profiles.md` line 36
- 现状：Flow 当前没有 `kind` 字段；v1 模型用 `branches[]` 表达 synthesis vs discussion；`card` / `room` 是早期模型留下的死语
- 影响：实现者按这条文字实现会误以为 Flow 有 `kind=card`/`room`
- 修复：删除该括号内容或改为"Flow（含 synthesis / discussion branch）"

### B-21. `space.kind=enclave` 与高隔离需求未在 schema 体现

- 位置：data-structures.md §4 `kind` enum 含 `enclave`，但工件 schema 与 sovereign-deployment.md 之间无强约束（没有要求 enclave 默认 federation_policy=closed）
- 影响：实现者可能创建 `kind=enclave` 但 federation 全开的 Space，违反 §11 conformance 期望
- 修复：在 schema 增加 `if kind==enclave then federation_policy default "closed"`，conformance profile 加测试

### B-22. Encrypted attachment `key_ref` 在两个文件 shape 不同

- 位置：
  - `crypto-media/media-and-blob.md` §3 `key_ref: "mls_epoch:42"` (字符串)
  - `crypto-media/encrypted-envelope-schema.md` §2.1 `key_ref: {algorithm, group_state_ref}` (对象)
- 影响：附件加密的关键引用结构两套，存储与协议层互不兼容
- 修复：以 envelope-schema §2.1 对象形态为准，统一所有附件使用

### B-23. Blob 没有 `space_id` 关联

- 位置：`crypto-media/media-and-blob.md` §2 metadata 没有 `space_id`
- 影响：§5 下载授权检查"按 Space 可见性"无 anchor 字段；上传后 Space 解散/迁移时无法 GC
- 修复：加 `space_id` (optional 仅对全局 blob 例外) 到 `blob.schema.json`

---

## 3. 重大问题（MAJOR — 应在 v1.0-stable 前修复，否则需在 changelog 中明确）

### 3.1 字段命名/枚举/形状层 drift（高优先）

- M-01 `event_kind` vs `event_type` 在 `encrypted-envelope-schema.md` §2.1 / §2.2 仍并存；§2.2 标 deprecated 但 schema 例子里仍写。建议彻底删除 `event_type` 字面量与 `aad_ambiguous_kind` 错误码（在最终发布版可保留过渡期 1 个 minor 版本）
- M-02 `principal_id` / `subject` / `holder_did` / `holder_subject` 表示同一概念，分别出现在 key-management、devices-and-auth、progressive-disclosure 三处
- M-03 `session_key_pub` (devices-and-auth.md §3.2) vs `session_public_key` (key-management.md §6) 同字段两名
- M-04 `relationship` enum (`owner|sponsor|host|issuer`) 在 `cx.space.organization` 与 `data-structures.md` 的 `owning_organizations: did[]` 模型并存——一个有关系类型一个只有数组
- M-05 `Proof.kind` enum 当前只有 `detached_jws`；缺少未来扩展占位（建议加 `cx.profile.proof.detached_jws.v1` 等 namespace，不要把 enum 完全锁死）
- M-06 Policy `rules: array<object>` 没有内部 schema；同样 Capability `subject` 的 condition object 也没有形态描述
- M-07 `read_marker.id` 字段类型为 `string` 但无 pattern；不同实现会派生不同 ID
- M-08 ULID 大小写：`encoding.md` §4 已要求 v1 wire 必须小写，但 `device-crypto-verification.md:13` 示例用 `cx:device:01HV...`（大写）。所有示例需要 lint 一遍

### 3.2 授权/状态收敛层

- M-09 `auth_weight` 11 个权重桶（700/650/...）无法处理大型 fork；建议显式说明 tie-break 的 `causal_depth` 计算公式
- M-10 缺少 `cx.reaction.add/remove` / `cx.message.redact` / `cx.invite.*` / `cx.notification.ack` 等的 auth_refs 行
- M-11 `cx.capability.derived` 在 §8 列为 state event 但 capabilities.md 没正式介绍它，space-hierarchy.md §7 才提及
- M-12 离线写入"30 天 max backlog"是 hard rule 但与 `account-lifecycle.md` 的 `suspended` / `soft_logged_out` 没有交互定义
- M-13 `partial_auth_state` 标记字段 `auth_incomplete | read_only` 是否唯一/或写未明
- M-14 quarantine 释放语义说"重新执行完整 validation 并以原 event_id 进入 accepted"，但若原 envelope bytes 已被改写则 hash 不匹配；需明确"必须保留原 envelope bytes"

### 3.3 同步与服务层

- M-15 `client-sync.md` §2 `subscriptions` example 用 `"space:..."` 而非 `"cx:space:..."`，会被 SDK 误学
- M-16 `client-sync.md` 引入 `$ME` 魔法字符串与 `*` 通配但无 schema
- M-17 `non-http-bindings.yaml` MQ topic 集合远小于 operation registry；websocket frame 字段名 (`operation_id`) 与 `transport-bindings.md` 例子 (`operation`) 不一致
- M-18 federation §4.4 grant/capability revoke fanout 没有最大延迟/peer 发现机制
- M-19 federation `verify_actor` 返回 `valid: bool`，但语义警告"不等于授权"——建议改为 `validation_class` enum
- M-20 federation push-operations 无 idempotency 强制
- M-21 OpenAPI 把 `/sync` 的 `headers: X-Contrix-Wait-For` 错放在 operation level（应该在 response level）

### 3.4 加密 / E2EE / 媒体

- M-22 MLS history sharing：私钥销毁与"撤销已发出 history key"之间的边界没说清
- M-23 SAS QR 验证流程缺一次性消费、显示设备签名、目标设备 id 互绑；存在重放风险
- M-24 SVG / authenticated media 无 CSP / sanitize 要求
- M-25 minimal-metadata profile 中 `cx.identity_link` 何时通过 MLS application message 推送、与 epoch 顺序如何保证未明确
- M-26 cipher 允许集合在 key-management.md 与 devices-and-auth.md 不一致（`xchacha20_poly1305` vs `AES-GCM-FIPS`）

### 3.5 身份 / 渐进披露 / TSP

- M-27 `did:plc` 默认但 Core profile 只要求 `did:web` + `did:key`，文字与 §10 conformance 矛盾
- M-28 `did:plc` 的 `degraded_mirror_only` 状态无可恢复的延长机制（hard 7 天上限）
- M-29 `cx.did.proof` 用 `kind` 字段，与 Event Envelope `kind` 概念冲突，建议 `proof_kind`
- M-30 `did:webs`、`did:webvh`、`did:keri` 在不同文件出现但没有统一在 identity-did.md §3 表格内
- M-31 `accepted_issuers` 的可信链验证算法未指定
- M-32 progressive-disclosure 的 holder identifier 同时叫 `holder_did` / `holder_subject` 两个名字
- M-33 TSP service 类型字符串 `cx.service.tsp` 在 DID Document 中未在 identity-did §6 授权

### 3.6 模型 / View / Relation

- M-34 Renderer enum 在 `data-structures.md` §11 是平面，但 `views.md` §4 限定每个 `kind` 可用的 renderer 子集——schema 较松，文档较严，会造成实现/校验差异
- M-35 Flow `state` enum 含 `redacted` 但 Flow 不应整体 redacted（redaction 是事件级）
- M-36 Relation cardinality 表里 "Space(kind=board) -> Space(kind=list) one_to_many" 与 "List 在边界内最多一个 active Board parent" 表述方向不一致
- M-37 Space.relation_profiles 数组无 uniqueness 约束（schema 没有 enforce `(relation_kind, from_type, to_type, scope)` 唯一）

### 3.7 扩展 (Applet / Agent / MIMI)

- M-38 Applet namespace pattern `cx:space:p0rta100000000000000000000:slack:*` 违反 typed ID 格式 `cx:space:<ulid>`；要么明确 namespace 是 glob，不是真实 id
- M-39 Agent endpoint `cx.agent.endpoint` event 与 DID Document service entry 的关系不清
- M-40 MIMI provider facade `cx.mimi.room_binding` lifecycle 在 mimi-interop.md 简略描述，缺缘起、迁移、撤销详细 vector

### 3.8 Conformance / 工件

- M-41 OpenAPI 的 ErrorEnvelope.error.code 不 enum 锚定 registry
- M-42 `tools/artifact_pipeline.py` `check` 没有 OpenAPI ↔ registry 一致性测试，也没扫 Markdown 中出现的 error code 字面值
- M-43 `conformance-profiles.json` 中 `vector_profiles` (10 项) 不在 `implementation_profiles` (22 项) 中；`profile_requirements` 把两类 mix 在一起，两边交叉对不齐 18 项
- M-44 `release-readiness.md` §2 声明 `v1-core-rc` 但 README 把它当作"维护中"，没有标记发布状态
- M-45 fixture 文件覆盖 10 个域，但 `conformance-suite.md` §4.2 提到的若干 vector id（如 `cx.vector.state_resolution.schema_update.v1`）在 fixture 里搜不到——需要核对

### 3.9 安全模型

- M-46 server-threat-model.md §2.2 "当前不成立攻击" 段太短，可信度不足
- M-47 §4.2 reason_code 与 policy-server.md §4 的 enum 不完全一致（前者无 `ok` `policy_violation`）
- M-48 §4.4 文件名 sanitization 规则未指定 RFC 6266 / strip non-ASCII
- M-49 没有针对 cross-Space `cx.flow.branch.member` external admission 泄露的威胁项

---

## 4. 次要问题（MINOR — 文档质量 / 风格 / 编辑 / 长尾）

合并较多次要项，列举不展开（具体出处见 §0 子代理详细报告）。

- 多处 SHOULD 在安全关键位置应改 MUST：`account-lifecycle §2.1` 例如/SHOULD; `capabilities §2.1` issuer/subject 应 MUST 用 DID
- conversation-model §4 / progressive-disclosure §10 / moderation §3.4 §5.3 §7 中英混排
- 多处例子使用 `did:web:alice.example` vs `did:web:alice.example.com` 不一致
- HLC 排序在 `operations-sync.md` §16 与 `client-sync.md` §6 略不同（前者无 actor_seq）
- Protobuf gRPC service 列表 vs operation registry 不全
- `conformance-profiles.md` 列出 `cx.profile.applet_service.v1` 但工件 implementation_profiles 中没有它
- 多个空示例占位符如 `presentation: {}`, `proof: {}` 在 v1 中应已填实
- `cx:space:01NEW...` 等明显占位文本最好改为有效 ULID 或加 `<space_id_placeholder>` 标注
- `audit_actors: did[]` 没有 MLS leaf binding 验证规则细化

---

## 5. 设计层观察（QUESTION — 不一定要修复，但应在 changelog 提及决策）

- Q-01 Capability `auth_weight` 用 11 个固定权重 + tie-break 是否够稳？大型 federated Space 出现的并发 grant 数量级是否真测试过？
- Q-02 `auditable_e2ee.software_only.v1` 与 `auditable_e2ee.tee_required.v1` 双 profile：在没有 TEE attestation 时，"audit_process_only" 标签会让市场被误读为加密审计——是否需要另起名（如 `policy_attested_e2ee`）减少混淆？
- Q-03 hard erasure stub 仍保留 envelope digest——对短/可预测明文（"yes"/"no" 投票、PIN 等）等同长期承诺；spec 已警告但未给出 commitment-based 替代方案的注册 schema
- Q-04 `did:plc` 是否真的应作为公网默认？规范鼓励 `did:web` / `did:webvh` 同时存在，但 `did:plc` 的 directory 集中度长远是去中心化目标的妥协
- Q-05 Sovereign deployment 与 `kind=enclave` 是否有重叠？两层模型可能让用户分不清何时用哪个
- Q-06 `cx.flow.convert` 与 `cx.flow.branch.set_primary` 语义重叠
- Q-07 v1 没有 schema_id_classes（`schema_registry.schemas` 里也都是 schema_id 不分 class），未来给 schema 进版会麻烦
- Q-08 `state_key` 跨多 Space 的 principal-scoped state event 复用 (`cx.device.*` / `cx.session.grant`) 设计文档化得不够清楚

---

## 6. 跨切关注点（系统性建议）

1. **Single source of truth 原则尚未彻底落实**：错误码、event kind、id kind、operation 都进了 registry，但 schema(field-level)、capability action enum、policy applies_to enum、constraint type enum、state_key encoding 仍只存在于 Markdown。建议每个枚举都进 registry，让 lint 强制一致。
2. **生成块还可以扩展**：当前只有 `service-api-schema.md` 用 `BEGIN/END GENERATED` 块由 contract-catalog 渲染。可以把"全部 cx.* event kind 表"、"标准 capability action 表"、"error code 表"、"OpenAPI 全部 path"、"non-HTTP binding 全部 topic" 同样改成生成块，drift 立刻被 CI 抓到。
3. **Markdown ↔ JSON Schema lint 缺位**：当前 `tools/artifact_pipeline.py check` 只查 generated registries 是否与 catalog 一致，并不检查文档中出现的字段名是否真在 schema 中存在；这是本次评审发现绝大多数 BLOCKING 的源头。建议加 markdown link/reference linter。
4. **Conformance vector 与 reference impl 并行发布**：`release-readiness.md` 已经声明发布 `v1.0-stable` 必须有 reference validator + reducer + authz evaluator + runner；当前仓库未携带任何参考实现。在 v1.0-stable 之前必须解决。
5. **示例与编辑统一**：所有 `did:web:alice.example` / `did:web:alice.example.com` 例子需要一次 sweep；多语言混排需要一次编辑。
6. **存档：明确"未来 minor"占位**：当前规范里许多"profile 后续注册"句子没有把对应 placeholder 提前登记到 registry，建议把"占位条目，待 v1.x 扩展"也明确登记到工件，方便 pre-commit lint。
7. **CHANGELOG.md 应是文件不是目录**（再次强调）。

---

## 7. 流水线 / CI / 工程交付观察

- `python tools/artifact_pipeline.py check` 当前在仓库中**通过**（125 event kinds, 34 schemas, 37 typed ID kinds, 83 operations, 40 profiles）。
- `.github/workflows/artifact-lint.yml` 只做 `check` 不做 `generate -- dry-run`；建议加 `--check-only generate`，防止生成块漂移。
- 没有 OpenAPI lint（如 spectral）、没有 JSON Schema 元 schema 校验。
- `tools/artifact_pipeline.py` 没有 markdown 链接断链检查（虽然 `check_mirrors` 调用 `lint_artifacts.py` 会做一些，但 `zh/*.md → artifacts/*` 之间的具名引用没有 enforce）。
- 工件 README 与 zh/README 都说"参考 reference validator/reducer/authz evaluator"，但仓库内没有。需要计划：要么在本仓库提供 reference runner，要么在另一个仓库链回。

---

## 8. 推荐的发布路径

按优先级和工作量分批处理：

| 阶段 | 内容 | 估计 |
| --- | --- | --- |
| **PR 1（一次清扫）** | B-01 (CHANGELOG)、B-15、B-19、B-20、B-21、M-01、M-08、M-15、M-16、M-29、M-32、M-44、所有 MINOR 编辑统一 | 1 周 |
| **PR 2（envelope/字段统一）** | B-02、B-04、B-05、B-09、B-10、B-11、B-22、M-02 ~ M-07 | 1–2 周 |
| **PR 3（错误/api/openapi）** | B-07、B-08、B-23、M-21 ~ M-22、§6 generated-block 扩展、§7 lint 工具 | 1–2 周 |
| **PR 4（语义对齐）** | B-03、B-06、B-12、B-13、B-14、B-17、B-18、M-09 ~ M-14 | 2–3 周 |
| **PR 5（auditable / minimal-metadata 收紧）** | B-13 实质实现、Q-02/Q-03 决策、增加 conformance vector | 2 周 |
| **PR 6（参考实现 + CI）** | reference validator/reducer/authz、`tools/artifact_pipeline.py` 增强 | 4–6 周 |
| **发布 `v1-interop-preview`** | 至少两个独立实现通过 core_event_store vector | — |
| **发布 `v1.0-stable`** | 全部 BLOCKING + 关键 MAJOR 解决 | — |

---

## 9. 最终判定（守门员意见）

- **当前状态**：可以发布 `v1-core-rc`（与 `release-readiness.md` 一致）。
- **不可以发布 `v1.0-stable`**：上述 23 个 BLOCKING 问题中，有约 8 个会让两个独立实现无法互通（B-02、B-03、B-06、B-07、B-09、B-10、B-12、B-22），4 个会泄露隐私或破坏 E2EE 安全模型（B-13、B-14、B-18、B-23），其余多数是文档与 schema drift。
- **总体评价**：架构层非常优秀，但发布前需要一次"对齐扫除"：把所有字段名、enum 值、error code、envelope shape 在 spec / schema / fixture / OpenAPI 之间机械对齐，并强化生成式 lint 规则。建议把这次扫除做成单 PR 并加入 CI，避免发布后再次 drift。
- **具体放行条件**：
  1. §2 全部 23 个 BLOCKING 修复或在 changelog 明确豁免；
  2. `tools/artifact_pipeline.py check` 增加 OpenAPI/operation registry 一致性、error code 字面值校验、Markdown 例子 ULID 大小写校验后通过；
  3. 至少 2 个独立实现通过 `cx.profile.core_event_store.v1` vector；
  4. reference validator / reducer / authz evaluator 公开可用。

---

**附录 A：本次评审子代理产物**：四个深度评审 agent 各自产出 100–200 条具体引用与定位（identity+crypto-media 约 135 条；sync+discovery 约 200 条；authz+security+models 约 145 条；extensions+conformance+artifacts 因配额中断由我手动补足）。这些原始发现已在 §2–§5 整合归并，避免重复列举；如需逐文件复盘可重新跑一次同样的子代理。
