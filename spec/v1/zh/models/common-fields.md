---
title: Common Fields
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Cokret 协作图所有 canonical object 共享的字段、lifecycle 状态机、主体引用语义与 reducer 总则。每个对象自己的字段表（Realm / Flow / Message / ...）放在该对象的专属文件中；本文只承载"所有对象都遵循"的内容。

## 2. 类型记法

| 记法 | 含义 |
| --- | --- |
| `string` | JSON string。 |
| `boolean` | JSON boolean。 |
| `integer` | JSON integer，不能是 float。 |
| `number` | JSON number，必须满足 `encoding.md` 的 number profile。 |
| `object` | JSON object，字段名必须 snake_case。 |
| `array<T>` | JSON array，元素类型为 `T`。 |
| `map<T>` | JSON object，value 类型为 `T`。 |
| `enum(...)` | 枚举字符串。 |
| `timestamp` | RFC 3339 UTC string，必须以 `Z` 结尾。 |
| `did` | DID URI string。 |
| `id:<kind>` | `ck:<kind>:<uuid>` typed ID，或该 kind 在 `id-kind-registry.json` 声明的特殊 wire form。 |
| `ref:<kind>` | 指向 `<kind>` 的 typed reference material；wire form 同样由 `id-kind-registry.json` 或对应 profile 声明，但字段语义是因果 / proof / content-addressed / profile-scoped reference，而不是普通对象主键。 |
| `hash` | `sha256:<lowercase_hex_digest>`。 |
| `cursor` | `ck:cursor:<base64url>` opaque string。 |
| `patch` | `ck.patch.v1` 形态的 JSON patch 片段，具体路径与 op 规则见 [`event-and-patch.md`](./event-and-patch.md)。 |

注：`device_id` 不是例外字段；它的类型是 `id:device`，wire form MUST 为 `ck:device:<uuid>`。只有部分辅助标识符（如 `transaction_id`、`backup_version`、`stream_id`）使用领域特定前缀（如 `ver_`、`kb_`、`devstream_`），不遵循 `ck:<kind>:<uuid>` 格式。这些标识符的编码规则由各自所在章节定义。`recording_id` 是 [`crypto-media/call-state.md` §5](../crypto-media/call-state.md) 定义的 opaque 领域标识（示例形态 `rtc-recording-<uuid>`）：它是 backend 媒体服务（如 LiveKit Egress）生成的 opaque 录制 lifecycle 句柄，进入 recording key exporter Context，**不是** `ck:*` typed ID。

`ck-` / `cx_` 前缀命名约定（normative）：`ck-` / `ck_` 是 Cokret 的正命名前缀；新增或推荐的 canonical 命名 **MUST NOT** 使用 `ck-` / `cx_` 前缀。MLS GroupContext extension 的当前 wire 名是 `mls_governance_binding`（codepoint 0xF1C0，非 ck 名），实现 MUST 用 `mls_governance_binding`、MUST NOT 把 `cx_governance_binding` 作为当前 wire 名。

字段默认规则：

- 未标记 optional 的字段为 required。
- `null` 只有在类型中明确写出时才允许。
- Event Envelope 顶层未知字段 MUST 被 schema validation 拒绝；非关键扩展只能放入 `payload.x_*`，且仅当该 payload kind 的 schema 显式声明 `x_*` patternProperties 扩展槽时才可使用——未声明扩展槽的 payload kind 不接受任何未知字段（payload schema 的 `additionalProperties: false` 即权威判定）。实现 MUST 在 canonical bytes、存储、转发和 backfill 中保留 schema 允许的 `x_*` 字段，但 MUST NOT 让 `x_*` 字段绕过 capability、schema、policy 或加密约束。需要扩展槽的 payload kind SHOULD 先在对应 schema 登记 `x_*` patternProperties 槽再使用；当前已声明扩展槽的 payload kind 以 schema 为准（现仅 `invite_payload`）。未知 critical extension MUST fail closed。
- 签名和 hash 输入 MUST 使用 canonical JSON。
- `id:<kind>` 在 wire、canonical object、fixture、签名和跨服务引用中 MUST 使用完整 typed ID。数据库内部 MAY 只存 raw id，但在序列化、签名、hash、联邦、sync cursor 和审计回放前必须恢复 `ck:<kind>:` 前缀；不得把数据库主键或表名当作协议 ID 的替代品。
- 当 `id:<kind>` 出现在 JSON object key 中时，它仍然属于 wire value；例如 `messages.{principal_id}.{device_id}` 中的 `{device_id}` MUST 使用完整 `ck:device:<uuid>`，MUST NOT 写成局部别名如 `dev_a` 或 `a`。
- `summary` / `description` 命名约定：canonical object 或 projection row 的短摘要、列表预览、聚合摘要使用 `summary`；Flow 的用户可读短摘要放在 `metadata.summary` 或 `encrypted_metadata`，不得作为顶层 `summary`。原因说明、补充说明、长说明或 schema / registry 元数据说明使用 `description`。OpenAPI 自身标准关键字 `summary` / `description` 按 OpenAPI 语义使用。若字段承载人类可读名称，canonical object 默认使用 `title`；Flow 使用 `metadata.title` 或 `encrypted_metadata`，Actor / user-facing identity profile 使用 `display_name`；`name` 只用于外部协议、加密算法、service surface 或 registry 内部 label，不作为 Realm / Space / Flow 等 canonical object 的显示名。
- Projection row 若表达 canonical object 的同一概念，MUST 沿用 canonical 字段名（例如 `title`、`summary`、`avatar_blob_ref`、`owning_organizations`），MUST NOT 另起 `name`、`avatar`、`official_organizations` 等别名。若服务需要返回渲染友好的派生对象，字段名 MUST 明确带 projection 语义并有 schema；v1 默认不定义通用 `avatar` projection，头像引用使用 `avatar_blob_ref`。
- `_id` / `_ref` / `_did` 后缀约定见 §2.1。简要规则：单一具体 protocol object kind 使用 `_id`；因果 / proof / schema-profile / content-addressed / polymorphic reference 使用 `_ref` / `_refs`；原始 DID ecosystem material 使用 `_did`。字段后缀表达 wire value category，不表达授权、同步、保留或加密是否级联；这些语义 MUST 由 role prefix、schema description 与对象专属章节定义。
- `kind` / `type` 命名约定：`kind` 用于协议内 discriminator、routing、registry event/object family、lattice/reducer 分派和 Relation/View 等 canonical 分类；`type` 用于外部标准 taxonomy、媒体类型、服务分类或不参与 reducer routing 的领域分类。Event Envelope 顶层 `kind` 是唯一 event discriminator；payload 不得用 `type` 重复 event kind。Morph 的 `morph_type` 是 Realm schema-defined 的开放领域分类，不参与 reducer event routing，故使用 `_type` 后缀且字段名固定为 `morph_type`，不得使用裸 `type`；Relation/View 等协议 registry 分类使用 `kind`。MLS `proposal_type` 属于外部 MLS taxonomy，保留 `type`。Genesis `anchorer` 对象的 finality-profile discriminator 是已登记的 `type` 例外（schema `realm.schema.json` 锁定 `anchorer.type`，取值与 `anchor_profile` 枚举同源），不改名为 `kind`。Handle Claim 自身的封闭协议分类使用 `claim_kind`；authorization/VC selector 中选择外部 credential taxonomy 的字段可继续使用 `claim_type`。
- 时间边界命名约定：有效期下界统一使用 `not_before`，有效期上界统一使用 `expires_at`；缓存或派生结果的失效时间使用带领域前缀的 `cache_expires_at`。新增 wire 字段不得使用 `valid_from`、`valid_until` 或 `not_after` 作为同义别名。
- `state` / `status` / `stage` 命名约定：`state` 表示 canonical object 的物理生命周期；`stage` 表示 Flow / Morph 等业务进度轴；`status` 只用于账号、session、delivery、外部过程或 registry 条目状态，不用于表达 object lifecycle 目标值。对象 lifecycle payload 若需要携带目标状态，字段名使用 `target_state`。
- `created_by` / `creator_*` 命名约定：materialized object metadata 使用 `created_by` / `updated_by`，由 reducer 从 Event `actor_id` 派生。`creator_*` 只用于外部协议或加密 transcript 自身的创建者 tuple（例如 MLS group creator），不得作为 object 创建主体字段的别名。
- 哈希字段命名三词词汇表：算法/函数族选择器使用 `<noun>_algorithm`（枚举字符串，例如 `digest_algorithm: "sha256"`）；任意字节的不透明哈希输出使用 `<noun>_digest`（wire 形态必须是自描述 `<alg>:<hex>`）；树状 / Merkle / 累加器的根使用 `<noun>_root`（同样是 `<alg>:<hex>`，区别在于单独验证还需配套包含证明）。**新增 wire 字段名 MUST NOT 以"hash"结尾（不论是 `_hash` 后缀还是 `hash_profile`、`hash_algorithm` 等同义形态）**；含义重叠的算法选择器 MUST 收敛到 `<noun>_algorithm`，含义重叠的字节输出 MUST 收敛到 `<noun>_digest`。遗留 `_hash` 字段在 v1 内全部按上述规则映射，典型映射见 `renames.json`（例如 `payload_hash → payload_digest`、`hash_profile → digest_algorithm`、`state_hash → state_digest`）。复合 commitment 对象（例如 `event_set_commitment`）的外层名描述语义，内部以 `algorithm` + `root` 或 `digest` 表达字节材料；外层 MUST NOT 再追加 `_digest` 后缀。Event proof 绑定 canonical Event bytes 的字段名是 `event_digest`；非 Event 通用 detached proof 使用 `payload_digest`，其说明必须写明被 digest 覆盖的 canonical payload。
- 签名 proof 中表示签名 key DID URL 的字段统一为 `verification_method`，不得使用 `signed_by`。协议级密钥标识使用 `key_id`；JOSE/JWK 结构可保留标准 `kid` / `alg`。若 schema 显式定义紧凑 detached signature tuple `{alg,kid,sig}`，短字段 `sig` 只允许出现在该 tuple 内；协议对象的普通签名字段使用 `signature` 或带角色的 `<role>_signature`。若需要表达消息或通知中的发送主体，使用带角色的 `sender_actor_id`；展示名称使用 `sender_actor_display_name`，不得用裸 `sender` 承载 DID。
- `recipient_service_did` 与 `audience` 不可互换：前者是物理路由目标 service DID，后者是密码学 transcript / proof 的受众绑定。即使 `audience` 只有一个 DID，也不得替代 `recipient_service_did`；反之亦然。
- `scope` 命名约定：wire schema 中不得新增裸 `scope` 字段；必须用领域前缀说明形态与用途，例如 `read_scope`、`receipt_scope`、`event_range`、`match_scope`、`claim_scope`、`erasure_scope`、`agent_key_scope`、`consent_scope`、`realm_key_scope`、`extension_scope`、`constraint_scope`、`policy_scope`、`search_scope`、`relation_scope`。Registry 元数据若表示条目适用范围，可继续使用 `scope`。
- 诊断命名约定：机器可枚举的失败 / 恢复 / reset 原因使用 `reason_code` 或带领域前缀的 `*_reason_code`；人类可读自由文本使用 `reason` 或 `description`。受控枚举不得命名为 `reason`。
- ID kind 与 wire prefix 必须使用完整 snake_case 名称，不得使用缩写前缀（例如使用 `ck:notification:`、`ck:device_message:`、`ck:key_event:`、`ck:moderation_queue_item:`、`ck:request:`、`ck:transaction:`、`ck:franking_proof:`）。
- CRDT lattice 字段使用 `lattice`，枚举值使用 snake_case（如 `or_set`、`mv_register`、`cas_register`、`ordered_log`、`lww_register`）。新增 lattice 枚举不得使用 kebab-case。
- Event kind 动词使用动词原形表达 reducer 动作（如 `authorize`、`revoke`、`rotate`、`tombstone`）；只有纯状态通告或外部标准名有明确理由时才可使用过去分词。
- Capability action 命名约定：
  - **`ck.<entity>.<verb>` 是默认形态**，对应 `target_event_kinds` 中的一个或多个 reducer-input event kind。新增 action 默认 MUST 与被授权 event kind 同名；只有 [`authz/capabilities.md` §5.0](../authz/capabilities.md#50-action--event-kind-偏离类别normative-reference) 登记的偏离类别允许不同名。授权、IAM 工具、SDK 生成和 audit 解析 MUST 读取 capability-action-registry 的 `target_event_kinds`，不得从 action 字符串拆解推断 event kind。
  - **通用 `ck.object.<verb>`**（如 `ck.object.read` / `ck.object.archive` / `ck.object.restore` / `ck.object.stage.set`) 只允许在 Realm-wide admin 或跨实体审计 grant 中使用 (`match_scope` 不限定单一实体 ID); 对单一实体的常规授权 MUST 使用专属 `ck.<entity>.<verb>` (例如 `ck.flow.archive`)。这是为了让 grant author 在最小作用域内表达意图, 同时保留 admin 路径使用通用 action 的能力。
  - **后缀 `.own` / `.others`**: 不带后缀的 action 默认作用域不限定 "creator = grantee"; 加 `.own` 表示 "仅 actor 自己创建的对象" (例如 `ck.message.revise.own`, `ck.message.redact.own`); 加 `.others` 表示 "允许操作他人创建的对象", 通常 risk_tier=high。三种形态 MUST 在 capability-action-registry 中分别登记, 不得当作通配等价。历史命名 `manage_others` 已收敛为 `.others` 后缀（例如 `ck.flow.watch.set.others`）。

### 2.1 Identifier 字段命名约定（normative）

本节适用所有持有 protocol identifier、DID material 或 reference material 的 wire 字段。字段名只表达 **value category**，不表达"硬归属 vs 软导航"、权限传播、同步传播、retention 级联或 E2EE key 级联。后者 MUST 由 role prefix、JSON Schema `description` 和对象专属章节共同定义。

#### 2.1.1 `_id`

`_id` 用于单一、具体、已在 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 登记的 protocol kind，或本协议把 DID 当作责任主体 ID 使用的字段。

形式：

```text
id
<kind>_id
<role>_<kind>_id
expected_<role>_<kind>_id
```

规则：

- canonical materialized object 自身 primary identity 字段 MUST 使用 `id`，不得写成 `flow_id` / `message_id` / `actor_profile_id` 等带对象名前缀的字段。Actor / user-facing identity 在 v1 中由 Actor Profile 表达：Profile 对象自身仍使用 `id`，其授权主体 DID 另用 `principal_id`。
- Snapshot manifest 自身也使用 `id`；`snapshot_ref` 只在其他对象、chunk payload、challenge 或 API hint 指向该 manifest 时使用。
- Event Envelope、Receipt、Attestation / Evidence、Key Backup、Applet / Agent 等协议 artifact 或非通用 materialized object MAY 使用 `<artifact>_id` 作为自身标识（例如 `event_id`、`receipt_id`、`attestation_id`、`evidence_id`、`backup_id`、`applet_id`、`agent_id`），因为这些对象经常与 `realm_id`、`actor_id`、`policy_id`、`device_id` 等并列并进入签名 transcript，需要在混合上下文中消歧。该例外不得反向用于 Realm / Space / Flow / Message / Morph / Relation / View / Policy / Actor Profile 等普通 canonical object。
- 单一具体 kind MUST 在字段名中出现 kind slug，例如 `space_id`、`parent_space_id`、`default_realm_id`、`scope_circle_id`、`policy_id`、`retention_policy_id`。
- protocol responsibility subject 使用 `_id`，即使 wire value 是 DID，例如 `actor_id`、`principal_id`、`subject_id`、`watcher_actor_id`。
- Event payload 若写入某个 materialized object / projection 字段的值，payload 字段名 MUST 与该物化字段同名。操作目标、CAS expected head、audit target、selector target 等事件操作角色 MAY 加 role prefix，例如 `space_id` 与 `expected_parent_space_id`。

#### 2.1.2 `_ref` / `_refs`

`_ref` / `_refs` 只用于 reference material，而不是单一具体 object kind 字段。允许类别：

- Event / Anchor / Cell / Snapshot / Receipt 等因果、finality、state 或证明引用：`prev_refs`、`anchor_ref`、`cell_ref`、`snapshot_ref`。
- Blob 或 content-addressed 引用：`blob_ref`、`avatar_blob_ref`、`thumbnail_blob_ref`。
- Schema / Profile / Feature 引用：`schema_refs`、`profile_ref`、`feature_ref`。
- Proof / evidence / transcript 引用：`evidence_ref`、`proof_ref`、`service_acceptance_ref`、`policy_event_ref`。
- Profile-scoped typed reference 或 profile-defined 非 UUID form：例如 `mls_group_ref` 使用 `ck:mls:<profile>:<profile_id>`，由 E2EE profile 校验。它故意不同于 MLS 标准 payload 内的原始 `mls_group_id`。
- Polymorphic reference：字段允许多个 protocol kind、DID、content-addressed value 或 hash 形态时使用 `_ref`，例如 `target_ref`、`object_ref`、Relation 的 `from_ref` / `to_ref`。

新增字段若只允许一个具体 canonical materialized object kind，且不是上述因果、proof、schema/profile、content-addressed 或 profile-scoped reference，MUST 使用 `_id` 而不是 `_ref`。

#### 2.1.3 `_did`

`_did` 只用于必须强调原始 DID ecosystem material 的字段，例如 service endpoint DID、pairwise DID、DID continuity proof 或外部验证服务 DID。例：`service_did`、`recipient_service_did`、`pairwise_did`、`old_did`、`new_did`、`verification_service_did`、`operator_did`、`push_gateway_did`。

普通协议责任主体不得使用 `_did`；使用 `actor_id`、`principal_id`、`subject_id`、`recipient_principal_id`、`agent_principal_id`、`audit_service_actor_id` 等 `_id` 字段。

`verification_method` 保留 W3C DID 规范字段名，承载 DID URL，不改名为 `_id` 或 `_did`。

## 3. Common Object Fields

所有 durable canonical object SHOULD 使用以下公共字段，除非对象类型另有说明。公共字段的 canonical 排列顺序以 §3.2 为单一真源（content → lifecycle → audit）：即 `state`、`state_changed_at`、`stage`、`stage_changed_at` 等 lifecycle 簇 MUST 排在 `created_by`、`created_at`、`updated_by`、`updated_at`、`deleted_at` 等 audit 簇之前（与全部已实现 schema 一致）。对象专属字段 MAY 插入在 scope / lifecycle / body 分组中，但同名公共字段的相对顺序 MUST 与 §3.2 和 `tools/field-order-rules.json` 保持一致。本节字段表（§3.1）仅为概念性字段清单，不作为顺序真源。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:*` | typed ID 前缀决定对象种类（`ck:flow:` 即 flow 对象，依此类推）。 | 对象稳定 ID；前缀就是 type，不再单独写 `type` 字段。 |
| `schema` | yes | `string` | SHOULD 是 `ck.schema.*.vN` 或反向域名 schema id。 | 验证 schema id。 |
| `realm_id` | conditional | `id:realm` | Realm 外对象可省略。 | 所属 Realm。 |
| `created_by` | conditional | `did` | 系统派生对象可由 `derived_from` 替代。 | 创建主体（创建该对象的 Event 的 `actor_id`）。 |
| `created_at` | yes | `timestamp` | 不能作为因果真相。 | 创建时间。 |
| `updated_by` | no | `did` | 更新时 SHOULD 设置。 | 最近更新主体。 |
| `updated_at` | no | `timestamp` | MUST be no earlier than `created_at`。 | 最近更新时间。 |
| `deleted_at` | no | `timestamp` | durable tombstone 可用。对没有独立 `deleted` / `tombstoned` 终态的对象（Flow / Morph，其不可逆终态是 `redacted`），`deleted_at` 仅表示该对象因 `ck.redaction` 进入 `redacted` 的逻辑删除时间，不暗示存在单独的 deleted 终态；对有 `tombstoned` / `deleted` 终态的对象（Space / Realm / Message 的相应终态），表示该终态发生时间。 | 逻辑删除时间。 |
| `state_changed_at` | conditional | `timestamp` | **Reducer-derived,actor 不可信:** 所有具有 `state` 字段的对象（Flow / Space / Message / Morph / Relation）当 `state != active` 时 MUST 写入;reducer **MUST** 忽略任何 wire payload 中 actor-supplied 的 `state_changed_at` 值，以触发该 state transition 的 Event 的 `created_at`(或对应 anchor 的 `anchored_at`,以两者中较晚者为准)覆盖写入。MUST be no earlier than `created_at`,MUST ≤ `updated_at`(当后者存在时)。 | 最近一次 state 转换时间。 |
| `stage` | conditional | `enum` | 适用对象自己的 schema 声明本字段时可用（v1 适用对象 = Flow / Morph，详见 §5.3）；Flow MAY 省略，Morph 必填。取值为 §5.3 的协议级 8 值枚举。**禁止与 `state` 混用**：`stage` 表达业务进度，`state` 表达物理生命周期，两者正交。Flow 的 `metadata.fields.stage` / `metadata.fields.lifecycle` / `metadata.fields.progress_state` / `metadata.fields.stage_reason`，以及 Morph 的 `fields.stage` / `fields.lifecycle` / `fields.progress_state` / `fields.stage_reason` 等同名/近名 wire 路径 MUST 被拒绝（见 [`artifacts/registry/forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json)）。stage 变更的"为什么"解释通过 discussion track Message 表达，不在对象字段中携带。 | 业务进度阶段。 |
| `stage_changed_at` | conditional | `timestamp` | **Reducer-derived，actor 不可信：** 适用对象 `stage` 字段每次实际变更时 MUST 写入；Flow 缺少 `stage` 时 MUST NOT 单独出现。reducer **MUST** 忽略 wire payload 的 actor-supplied 值，以触发该 transition 的 `ck.<kind>.stage.set` event 的 `created_at` 覆盖写入。MUST be no earlier than `created_at`。same-value self-transition（stage 值未变）reducer MUST NOT 更新本字段。 | 最近一次 stage 转换时间。 |
| `labels` | no | `array<string>` | SHOULD 小写短标签。 | 用户或系统标签。 |
| `fields` | no | `object` | 字段 schema 由对象类型自身的 `schema_refs` 决定。 | 扩展字段；v1 唯一标准扩展容器。 |

对象种类由 `id` 的 typed prefix（`ck:flow:` / `ck:realm:` / ...）唯一决定；扩展字段统一走 `fields`，由对象 `schema_refs` 约束。Event Envelope 不是 Materialized Object，事件类型由顶层 `kind` 表达。

### 3.0.1 Size 字段命名

表示字节数的字段 MUST 使用 `_bytes` 后缀，例如 `size_bytes`、`max_total_blob_bytes`、`canonical_payload_bytes`。不得新增裸 `size` 表示字节数；Blob metadata、Media metadata、Content Block descriptor 与 Snapshot chunk descriptor 均使用 `size_bytes`。

### 3.0.2 Duration 字段命名

表示机器处理时长的新增 wire 字段 SHOULD 使用整数加显式单位后缀，优先选择 `_ms` 或 `_seconds`，例如 `retry_after_ms`、`ttl_seconds`、`refresh_lead_seconds`。字段名不得只靠 description 表达单位。

需要 profile author 直接书写的人类可读策略时长 MUST 使用 ISO 8601 duration 字符串（如 `PT24H`、`P30D`、`P1Y`），并以统一 pattern `^P(?:[0-9]+Y)?(?:[0-9]+M)?(?:[0-9]+W)?(?:[0-9]+D)?(?:T(?:[0-9]+H)?(?:[0-9]+M)?(?:[0-9]+S)?)?$` 约束。v1 内**只有这一种 duration 字符串格式**：自造的 compact duration mini-DSL（如 `^[0-9]+(ms|s|m|h|d)$`）与无 pattern 的裸 duration string MUST NOT 出现在新增 wire 字段中；既有 compact-form 字段（`message_edit_window`、`message_redact_window`、`period`、`timeout`、`key_rotation_period`、`max_key_age`、`claim_max_age`、`application_ttl`、`cooldown_after_reject` 等）已全部映射为 ISO 8601，见 `renames.json`。

时长名词按语义区分：`ttl` 表示对象或凭据存活期；`timeout` 表示等待无响应后的放弃；`window` 表示允许动作发生的相对窗口；`period` 表示周期性轮换/复发；`cooldown` 表示拒绝或关闭后的最短重试间隔；`age` / `staleness` 表示已存在材料相对当前时间的新鲜度上限。

### 3.1 字段 × 对象适用性矩阵（normative reference）

下表把 §3 列出的公共字段按对象 kind 标注必填 / 可选 / 不适用。SDK / projection / fixture 生成器 MUST 严格按此表验证，不得给"不适用"格写值；新增对象 kind 时 MUST 先在本表落表再发布 schema。术语：`Y` = 必填；`O` = 可选；`R` = reducer-derived（actor MUST NOT 写）；`—` = 不适用（schema MUST 拒绝该字段）。

字段按用途分四组：

- **Universal**：所有 durable canonical object 都用。
- **Authorship**：协作图对象记录创建 / 更新主体；与 reducer 派生关系紧密。
- **Lifecycle**：物理生命周期（active / archived / tombstoned / ...），与 `ck.<kind>.archive` / `restore` / `tombstone` 系列 event 配对。
- **Progress**：业务进度（v1 仅 Flow / Morph），与 `ck.<kind>.stage.set` event 配对。

| 字段 | 组 | Realm | Circle | Space | Flow | Message | Morph | Relation | View | Policy | Blob meta | Capability Grant | Invite | Read Cursor | Notification | Actor Profile |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | Universal | Y | Y | Y | Y | Y | Y | Y | Y | Y | —（见 `blob_ref`，§3.2 第 2 类） | Y | Y | Y | Y | Y |
| `schema` | Universal | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| `realm_id` | Universal | —（Realm 自身即边界，无 `realm_id` 字段，schema 拒绝） | Y | Y | Y | Y | Y | Y | Y | O | O | O | Y | Y | O | O |
| `created_by` | Authorship | Y | Y | Y | Y | Y (reducer-derived from Event `actor_id`) | Y | Y | Y | Y | Y | — (see `issuer`) | — (see `inviter`) | — (see `actor_id`) | — (see `actor_id`) | — (see `principal_id`) |
| `created_at` | Authorship | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | —（见 `issued_at`，§3.2） | Y | —（仅 `updated_at`，见 §3.2） | Y | Y |
| `updated_by` | Authorship | O | O | O | O | O | O | O | O | O | O | O | O | — | — | O |
| `updated_at` | Authorship | O | O | O | O | O | O | O | O | O | O | O | O | Y | O | O |
| `deleted_at` | Lifecycle | —（Realm 终态由 lifecycle facet 表达，schema 拒绝） | — | — | O | O | O | — | — | — | O | — | — | — | — | — |
| `state` | Lifecycle | —（Realm 终态由 lifecycle facet 表达，schema 拒绝） | Y | O | O | Y | O | O | — | — | — | — | Y（流程状态轴，见附注） | — | Y（特例语义，见附注） | — (see `status`，mirrors account status) |
| `state_changed_at` | Lifecycle | —（Realm 终态由 lifecycle facet 表达，schema 拒绝） | R when state≠active | R when state≠active | R when state≠active | R when state≠active | R when state≠active | R when state≠active | — | — | — | — | — | — | — | — |
| `stage` | Progress | — | — | — | O | — | Y | — | — | — | — | — | — | — | — | — |
| `stage_changed_at` | Progress | — | — | — | R per `ck.flow.stage.set` | — | R per `ck.morph.stage.set` | — | — | — | — | — | — | — | — | — |
| `labels` | Universal | O | — | O | O | O | O | — | — | — | — | — | — | — | — | — |
| `fields` / `metadata.fields` | Universal | O | — | O | O (`metadata.fields`) | O (`metadata.fields`) | Y (主要载荷) | O | — | — | — | — | — | — | — | — (see `profile_fields`) |

附注：

- Realm 使用通用 `created_by` 字段；其额外语义是 Realm create event 的 authorizing principal，并作为 genesis member bootstrap 主体（见 §4.1 / §4.2 与 [`realm-and-space.md` §2.5](./realm-and-space.md#25-ckrealmcreate-reducer-bootstrapnormative)）。
- Capability Grant / Invite / Read Cursor / Notification / Actor Profile 用领域特有的 authorship 字段（`issuer` / `inviter` / `actor_id` / `principal_id`），各对象 schema 内部独立约束；本表对应格写"—"是因为它们不使用通用 `created_by`，并不表示没有创建主体记录。
- Read Cursor / Notification 是 actor-private 状态：`realm_id` 在 Read Cursor 上必填（`read-cursor.schema.json` 列入 `required[]`），在 Notification 上可选（允许 actor-scoped 视图省略）；`updated_by` 均不适用——这些对象由系统派生或 actor 本人推进。
- 任何承载物理 lifecycle `state` 轴的对象（Circle / Space / Flow / Message / Morph / Relation）在 `state != active` 时 MUST 写入 `state_changed_at`；该字段被 reducer 强制覆盖，actor wire 值 MUST 被忽略（详见 §5.1）。本条不适用于 Notification / Invite 的特例 `state` 轴（见下条）。
- Notification 的 `state` 是 schema required 字段（enum `unread / read / dismissed / archived`）：它承载 actor-private 的通知处理轴，是 Notification 的特例语义，不是 §5 协作对象物理 lifecycle 枚举；字段名保留 `state`，且 Notification 无 `state_changed_at`。Invite 的 `state` 同为 schema required，承载邀请流程状态轴（命名例外，见 [`governance-objects.md` §5](./governance-objects.md)），同样不落入 §5 lifecycle 状态机。
- `stage_changed_at` 仅 Flow / Morph 适用，且仅当 `stage` 存在并真正发生 stage 变更时写入；同值 self-transition reducer MUST NOT 更新（详见 §3 与 §5.3）。
- `labels` 对 Relation / View / Policy / Blob meta / Capability Grant / Invite / Read Cursor / Notification / Actor Profile 不适用：这些对象的 "标签" 语义由各自的 schema-specific 字段（如 `tags`、`reason`、`category`）承担，避免与协作对象 labels 投影冲突。
- `fields` 是协作对象的扩展容器；Flow / Message 的用户可读扩展放入 `metadata.fields` 或 `encrypted_metadata`，不得作为顶层 `fields`；View / Policy / Blob meta / Capability Grant / Invite / Read Cursor / Notification 不暴露开放扩展容器。
- **View 无 durable 终态**：v1 的 View 只有 `ck.view.create` / `ck.view.update` / `ck.view.reconcile`，`view.schema.json` 不含 `state` / `deleted_at`，registry 也无 `ck.view.tombstone`；故本表 View 的 `state` / `deleted_at` 为 "—"。共享 View 的"移除"是 owner-private / 带外操作（或由后续 reconcile 覆盖），不走对象生命周期终态。这是有意取舍，待未来若出现"可治理删除"的需求再单独引入 lifecycle event。
- **Realm 无 materialized `state` 字段**：Realm 的 `archived` / `frozen` / `tombstoned` / `destroyed` 由 `ck.component.realm.*` lifecycle facet 表达，`realm.schema.json` 拒绝 `state` / `state_changed_at` / `deleted_at`。Projection MAY 把 `ck.realm.tombstone` 与 `ck.realm.destroy` 均显示为 `realm_terminal_state`，并用 `terminal_kind=tombstone|destroy` 或同等字段区分 successor 迁移与永久退役；不得把该 projection 状态写回 Realm 对象。

### 3.2 字段声明 / 展示顺序约定（normative reference）

本表是 §3 / §3.1 之外的**顺序**约定：它不改变任何字段的必填性，只规定 schema `properties` 的声明顺序与 SDK / 文档生成器的展示顺序，使不同对象族呈现统一字段簇。本表为各 schema 的 canonical property ordering 真源；§3.1 的概念性字段表不应被当作顺序真源。

按结构角色把对象分三类，各自的顺序如下：

1. **canonical materialized object**（Realm / Circle / Space / Flow / Message / Morph / Relation / View / Policy / Actor Profile 等）字段簇顺序 SHOULD 为：
   1. identity：`id`、`schema`
   2. scope / container：`realm_id`、`space_id`、`flow_id`、其它 parent refs（如 `parent_space_id`、`scope_circle_id`）
   3. object discriminator / 引用：`kind`、`rank`、`schema_refs`
   4. content / config：`title`、`metadata`、`fields`、policy / config 字段
   5. lifecycle：`state`、`state_changed_at`、`stage`、`stage_changed_at`
   6. audit：`created_by`、`created_at`、`updated_by`、`updated_at`、`deleted_at`
   7. extension / profile 容器（若未在第 4 组出现）
2. **protocol artifact / proof**（Blob meta、attestation、receipt 等）：`schema`、`<artifact>_id`、scope refs、issuer / subject、artifact body、validity（`not_before`、`expires_at`）、签发 / 审计字段。这类对象 MAY 不含顶层 `id`（使用 `<artifact>_id`），不视为遗漏。
3. **private projection / process artifact**（Read Cursor、Capability Grant、Notification 等）：projection id / scope、grant / body、validity、lifecycle update（`updated_by`、`updated_at`）、revocation（`revoked_by`、`revoked_at`）。

排序硬规则（对全部三类生效，可被 lint 机器校验）：

- `created_at` MUST 排在 `updated_at` 之前；`created_by` MUST 排在 `created_at` 之前；`updated_by` MUST 排在 `updated_at` 之前。
- `state_changed_at` MUST 紧跟 `state`；`stage_changed_at` MUST 紧跟 `stage`。
- 任何同时承载 validity 字段簇（`not_before` / `issued_at` / `effective_at` / `expires_at`）与 audit 字段簇（`created_by` / `created_at` / `updated_*`）的对象，validity 簇 MUST 整体排在 audit 簇之前（即 `expires_at` 等有效期字段 MUST 排在 `created_by` / `created_at` 之前）。validity 簇内部 MUST 满足：`not_before` MUST 排在 `expires_at` 之前、`issued_at` MUST 排在 `expires_at` 之前（签发 / 生效下界先于有效期上界）；`not_before` 与 `issued_at` 同时存在时二者相对顺序不强制，按对象语义择一在前。以上由 `tools/field-order-rules.json` 的 `cluster_precedence` + `ordered_groups.validity` 经 `check_field_order` 强制。
- 开放扩展容器（`fields` / `metadata`）MUST 落在 content / config 区，紧邻对象内容字段，MUST NOT 混入 audit 字段簇。对 Realm 这类把 `fields` 置于审计字段之前的配置根对象，按本节"对象族例外"声明即可。

对象族例外 MUST 在对应 schema description 或本节列明。Realm 是配置根对象：`title` / `summary` / `security_class` 可在 `trust_domain` / `schema_refs` 之前展示，以便管理端先呈现人类可读身份和安全等级；`trust_domain` 仍是 create-locked replay boundary，`schema_refs` 仍是字段验证引用，不改变其语义。

**role ordering guidance（说明性，非强制改 schema）**：identity / scope / subject role 字段（`realm_id` / `actor_id` / `event_id` 等）的相对顺序按对象语义选择，并 MUST 在对应 schema description 或本节显式化例外——event 主体对象 MAY 采用 event-first（`event_id` 先，如 `event-envelope.schema.json` 的 `event_id` → `realm_id` → `actor_id`）；receipt / projection 类 MAY 采用 scope-first（`realm_id` 先，如 `read-receipt.schema.json` 的 `realm_id` → `actor_id` → `event_id`）；actor 私有 / actor 维度对象 MAY 采用 actor-first（`actor_id` 先，如 `notification.schema.json` 的 `actor_id` → `realm_id`）。这三种排列是依对象语义的有意例外、非漂移；审查与 lint MUST NOT 据单一全局 role 顺序判错。本节的硬排序规则（`created_*` / `updated_*`、`state_changed_at` / `stage_changed_at` 紧邻、validity 字段簇顺序）仍对全部三类生效，不受本 guidance 影响。

**过程型 / private object 例外**：第 3 类对象（见本节上方 private projection / process artifact 分类）不套用 canonical materialized object 的 audit 字段簇规则——

- **Read Cursor** 是仅更新态 projection，必填 `updated_at` 而**无** `created_at`；这是有意设计，不是字段遗漏。读者 / 生成器 MUST NOT 据 §3.1 推断它缺 `created_at`。
- **Capability Grant** 使用 grant 语义字段（签发 / 撤销相关）表达生命周期；其"创建时间"语义由 `issued_at`（而非通用 `created_at`）承载，retention / audit / 排序查询 MUST 使用 grant 自身的 `issued_at` / `expires_at` / `revoked_at`，不要回退到通用 `created_at`。
- **Notification** 同属 actor-private projection，不暴露开放扩展容器（见 §3.1 附注）。

> 说明：§3.2 排序硬规则已由 `tools/lint_artifacts.py` 的 `check_field_order` 自动校验——递归全部 `artifacts/schemas/*.schema.json` 的每个 `properties` 对象，强制 `created_by < created_at < updated_at`、`updated_by < updated_at`，以及 `state_changed_at` / `stage_changed_at` 紧邻 `state` / `stage`。规则按字段存在性条件触发，故 Read Cursor（无 `created_at`）、Capability Grant（用 `issued_at`）等有意例外天然不触发，无需白名单。

## 4. 主体引用字段交叉对照

### 4.1 DID 适用边界

DID 是 Cokret 的主体标识，不是普通协作对象 ID。标准协作对象（Realm / Circle / Space / Flow / Message / Morph / Relation / View / Policy / Grant / Invite / Blob 等）MUST 使用 `ck:<kind>:` typed ID 作为对象 ID；只有当字段表达 actor / principal / issuer / subject / service / controller / accountable party 时，才使用 DID 或 DID URL。设备不在此列：设备不是 actor 主体、没有自己的 DID，其标识是 `device_id`（`ck:device:<uuid>` typed ID），见 [`../crypto-media/device-lifecycle.md` §4](../crypto-media/device-lifecycle.md)。

因此，"需要有 DID"的对象与结构按下表理解：

| 对象 / 结构 | 必须包含的 DID 字段 | 说明 |
| --- | --- | --- |
| Actor identity（user / org / team / agent / service / integration） | DID 本身 | Actor 的身份根就是 DID；若需要在协作图中展示，则用 Actor Profile 承载展示字段。**不含 device**：设备不是 actor 主体、无独立 DID，仅有 `device_id`（`ck:device:<uuid>`），见 device-lifecycle §4。 |
| Actor Profile (`ck:actor_profile:`) | `principal_id` | Profile 只是展示镜像；`principal_id` 才是授权、签名和审计归属的主体 DID。 |
| Event Envelope (`ck:event:`) | `actor_id`; Proof 中的 `verification_method` 为 DID URL | `actor_id` 是签署并提交事件的 actor DID，MUST 匹配 proof 控制链。 |
| Realm (`ck:realm:`) | `created_by` | Realm create event 的授权 principal；`owning_organizations[]` 可选使用组织 DID。 |
| Circle / Space / Flow / Message / Morph / Relation / View / Policy / Blob metadata | `created_by`; 更新时可有 `updated_by` | 这些对象自身不使用 DID 做 `id`；DID 只记录创建 / 更新主体。协作图对象的创建 / 更新主体由 reducer 从对应 Event 的 `actor_id` 派生；Blob metadata 的 `created_by` 来自 authenticated media 写入主体。 |
| Capability Grant (`ck:grant:`) | `issuer`; `subject` 为具体主体时必须是 DID | `subject` 也可以是条件 selector；handle、邮箱、域名用户名等不得作为权限主体主键。 |
| Invite (`ck:invite:`) | `inviter`; `invitee` 在直接 DID 邀请时使用 DID | [3PID](../overview/glossary.md) 邀请可没有 `invitee`，但认领后必须绑定可验证主体。 |
| Read Cursor / Notification | `actor_id` | actor-private 或派生对象，`actor_id` 表示该私有状态所属主体。 |
| Event Batch Receipt / Identity Receipt / Audit Receipt | `issuer` 或 schema 声明的签发 / 主体 DID 字段 | receipt 的签发、覆盖范围和验证必须回到可解析 DID。 |
| Relation endpoint | 当 endpoint 是 Actor 时，`from_ref` / `to_ref` 使用 DID | 指向普通对象时仍使用 `ck:<kind>:` typed ID；Relation 不把对象 ID 转换为 DID。 |

任何可签名、可被授予 capability、可作为审计责任主体或可被 Realm / service policy allowlist 的实体，MUST 有可解析 DID。仅作为内容、容器、投影或关系事实存在的对象，不需要也不得发明独立 DID；它们通过 typed ID 被引用，通过 `created_by` / `updated_by` 等字段关联到 DID 主体。

### 4.2 主体引用字段

| 字段 | 出现对象 | 含义 |
| --- | --- | --- |
| `actor_id` | Event Envelope、Read Cursor、Notification | 直接执行该 Event / 拥有该私有状态的 actor DID（`actor_kind` 决定它是 user / agent / service 等）。 |
| `watcher_actor_id` / `target_actor_id` / `writer_actor_id` | Event payload、Audit payload | 带角色限定的 actor DID-as-id；字段名必须说明角色，避免回退到模糊的 `actor_did`。 |
| `principal_id` | Actor Profile | Profile 对应的 principal DID；权限根。 |
| `created_by` / `updated_by` | 所有 Materialized Object | 创建 / 最近更新该对象的 Event 的 `actor_id`，由 reducer 派生。Realm 的 `created_by` 还承担 genesis member bootstrap 的 authorizing principal 语义。 |
| `issuer` | Capability Grant、Identity Receipt | 签发授权或 receipt 的 DID；必须持有签发权限。 |
| `subject` | Capability Grant | 被授权 DID 或 selector condition。 |
| `subject_id` | Handle / invite / delivery binding candidate | 当 subject 必须是具体 principal DID 且进入可验证 transcript 时使用；generic / raw handle claim subject 仍使用 `subject`。`MemberDeliveryBindingCandidate.subject_id` MUST equal 上游 handle claim 的 `subject`。 |
| `inviter` / `invitee` | Invite | 邀请方 DID / 被邀请 DID。 |
| `accountable_principal_ids` | Actor Profile | 该 Actor Profile 声明可问责到的一组 principal DID（每个条目须有对应 active `ck.identity.accountability_grant` 背书）。array 形态使用 `_ids` 复数，与 agent key payload 的 scalar `accountable_principal_id` 共用同一 accountability 主体词汇；责任主体一律走 `_id` / `_ids`，不使用 `_to` 介词后缀或裸关系短语。 |
| `agent_principal_id` / `audit_service_actor_id` | Agent key payload、Audit release evidence | agent / audit release service 作为协议责任主体时使用 DID-as-id；承载运行或托管服务身份时另用 `service_did`。 |

这些不是同一字段的别名，每条都有独立语义角色；该表用于读 spec 时快速建立对应关系。

主体字段新增策略：

- 既定 crypto / governance 角色名词（如 `issuer`、`inviter`、`holder`、`anchorer`）可保留并应在 §4.3 角色名词登记索引登记（其权威定义仍在对应对象 schema / glossary / 专属章节）。新增的普通作者 / 操作者归属字段默认使用 `<verb>_by`（例如 `approved_by`、`revoked_by`），时间点使用 `<verb>_at`。
- 过程结果词汇按对象族固定：receipt 使用 `outcome` / `outcome_reason_code`，执行或 session 使用 `result`，moderation / appeal 裁决使用 `verdict`。新增相邻对象不得随机换用近义词。

### 4.3 角色名词登记索引

下表收敛 v1 已确立的 crypto / governance 角色名词，供读 spec / 评审命名时一次定位。本表是 **informative 索引**：每个角色的字段形态、约束与 normative 语义以「权威定义」列指向的 schema / glossary / 专属章节为单一真相源，本表不重复承载约束，也不得与权威定义冲突。新增 normative 文本引入主体 / 操作者归属字段时，先查本表确认是否已有既定角色名词，再按上文「主体字段新增策略」决定复用或使用 `<verb>_by`。

| 角色名词 | 类别 | 权威定义 | 角色语义 |
| --- | --- | --- | --- |
| `issuer` | id 字段（§4.2） | §4.1 / §4.2；[glossary `Capability Grant` / `Move`](../overview/glossary.md) | 签发 Capability Grant / Identity Receipt 或签署 Move 的主体 DID；必须持有对应签发权限。 |
| `subject` / `subject_id` | id 字段（§4.2） | §4.1 / §4.2；[glossary `Subject`](../overview/glossary.md) | Capability grant 的授予对象：`subject` 为 DID 或 condition selector，`subject_id` 用于必须是具体 principal DID 且进入可验证 transcript 的场景。 |
| `inviter` / `invitee` | id 字段（§4.2） | §4.1 / §4.2；[`governance-objects.md` §5 Invite](./governance-objects.md)；[`invite.schema.json`](../../artifacts/schemas/invite.schema.json) | 邀请方 DID / 被邀请方 DID；3PID 邀请可暂无 `invitee`，认领后必须绑定可验证主体。member 引用形态另用 `inviter_member_ref` / `invitee_member_ref`（见 [`invite-delivery-request.schema.json`](../../artifacts/schemas/invite-delivery-request.schema.json)）。 |
| `holder` | 叙述性角色名词 | [`consent-model.md` §2.1](../identity/consent-model.md)；[`client-preferences.md`](../discovery/client-preferences.md)；[glossary `Consent`](../overview/glossary.md) | consent / blocklist / recovery share / pairwise 假名等 holder-private 状态的归属主体；只有 holder 本人或其显式授权的 controller / agent 可写。 |
| `anchorer` | 叙述性角色名词 | [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)；[glossary `Anchor` / `Anchorer Cell`](../overview/glossary.md)；[`capabilities.md`](../authz/capabilities.md) | Anchor ordering authority：对 Move frontier 签名承诺的主体；由 `anchorer_cell`（`cas_register + bottom=reject`）授权，冲突时触发 Realm-wide Anchor pause。 |
| `witness` | 叙述性角色名词 | [glossary `Witness`](../overview/glossary.md)；[`federation.md`](../sync/federation.md)；[`operations-sync.md`](../sync/operations-sync.md)；[`identity-did.md`](../identity/identity-did.md) | 对 frontier、range completeness、DID key-log 头部或 handover frontier 签发 attestation / receipt 的受信背书主体；不替代 Event 自身签名、Anchor finality 或 reducer 验证。 |
| `controller` | 叙述性角色名词 | [`identity-did.md`](../identity/identity-did.md)（DID controller proof）；[`actor.md` §3.3](./actor.md)（Native Personal Agent controller） | DID 控制主体（method history 中以 controller proof 证明控制权），或受 holder / principal 显式授权代为写入 / provision 的控制方。 |

## 5. State 枚举对齐

`state`、`stage`、`status`、`runtime_status` 和 `binding_state` 分属不同状态轴，不是同一字段的别名：

速记规则：

- `state` 回答“这个对象在物理生命周期上还能不能作为活对象使用”。
- `stage` 回答“这件事在业务推进上走到哪里”，用于跨 Realm / 跨产品聚合。
- `status` 只留给账号、session、delivery、moderation workflow、registry entry 等过程型对象。
- Jira-style workflow status、Trello 自定义列表名、审核节点名等细粒度业务状态 MUST 由 Realm workflow profile 或 schema 字段声明，并映射到 `stage`；不得把它们当作 `state` 或新的协议级 `stage` 枚举。

| 字段 | 使用场景 | 语义轴 |
| --- | --- | --- |
| `state` | Realm / Circle / Space / Flow / Message / Morph / Relation 等 canonical object | 物理生命周期：active、archived、redacted、tombstoned / deleted 等。 |
| `stage` | Flow / Morph | 业务进度，与物理生命周期正交；完整枚举为 8 值（draft、proposed、planned、in_progress、blocked、done、cancelled、superseded），权威定义见 §5.3.2。 |
| `status` | Account、agent session、delivery、moderation workflow、registry entry 等过程型对象 | 外部过程或会话状态；不得替代 object lifecycle。 |
| `runtime_status` | Applet bridge / runtime metadata | 跨协议 runtime 可用性或执行态，避免与 canonical object `status` / `state` 混淆。 |
| `binding_state` | Handle claim / identity binding | claim 绑定验证状态：pending、verified、revoked、expired；不是 materialized object lifecycle。 |

各对象的 `state` 字段值不完全相同（部分名字承载了已稳定的 `ck.*.tombstone` event 命名约定），但在 reducer / projection 语义层等价于以下规范状态机：

| 规范状态 | 语义 | Flow | Circle | Space | Message | Morph | Relation | Realm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `active` | 当前可用 | `active` | `active` | `active` | `active` | `active` | `active` | `active` |
| `archived` | 软隐藏，UI 默认不展示，可撤销 | `archived` | `archived` | `archived` | — | `archived` | — | `archived` |
| `redacted` | 内容已根据 redaction policy 清除，envelope 与审计元数据保留 | `redacted` | — | — | `redacted` | `redacted` | `tombstoned`（合并 deleted+redacted） | — |
| `deleted` | 不可逆删除：content / encrypted_content / encrypted_payload 清空，仅保留 envelope 用于审计 | — | `tombstoned` | `tombstoned` | — | — | `tombstoned` | `realm_terminal_state`（projection；Realm 对象无 `state` 字段，`ck.realm.tombstone` / `ck.realm.destroy` 均映射到此终态类别） |

约定：

- 写入路径 MUST 来自对应 reducer-input event（`ck.<kind>.archive` / `ck.<kind>.restore` / `ck.<kind>.tombstone` / `ck.<kind>.redact` 或等价命名）；不得直接 PATCH 对象顶层 state。`archived -> active` 是显式的可逆转换，由 `ck.<kind>.restore`（Flow、Space、Morph 均已注册对应 restore event）承担；`tombstoned` / `deleted` / `redacted` 是不可逆终态，MUST NOT 被 restore。
- `state != active` 时 MUST 写入 `state_changed_at`（见 §3 公共字段）。

#### 5.1 Canonical state-transition table

每个 reducer-input lifecycle event 都 MUST 校验**当前 state**(reducer 视角下的 pre-state)落在下表"合法源"集合内，否则 MUST 返回 `failed_precondition`,`reason` 取下表 `reason_code` 列。

| event family | 允许的源 state | 目标 state | `failed_precondition` reason_code |
| --- | --- | --- | --- |
| `ck.<kind>.archive` | `active` | `archived` | `<kind>_not_active` |
| `ck.<kind>.restore` | `archived` | `active` | `<kind>_not_archived` |
| `ck.<kind>.tombstone` | `active`、`archived` | `tombstoned` / `deleted`(各对象 schema 自命名) | `<kind>_already_terminal` |
| `ck.<kind>.redact` 或 cross-object `ck.redaction` 指向该对象 | `active`、`archived` | `redacted`(如对象支持),或合并到 `tombstoned` | `<kind>_already_terminal` |

> **Flow / Morph 豁免**:上表 `ck.<kind>.tombstone` 行是通用模板;Flow 与 Morph **没有** `tombstone` 终态(也不用 `deleted`),其不可逆终态经指向该对象的 `ck.redaction` 进入 `redacted`(见 §5.2 模板槽与 [flow-and-message.md §9.1](./flow-and-message.md))。对 Flow / Morph 提交 `ck.<kind>.tombstone` 不适用。

`<kind>` 是 schema 类型短名(`flow`、`circle`、`space`、`morph`、`message`、`relation`),所有 reducer 实现 MUST 用相同 reason_code,使跨实现错误诊断一致。具体值如:`flow_not_active` / `flow_not_archived` / `flow_already_terminal`,`circle_not_active` / `circle_not_archived` / `circle_already_terminal`,`space_not_active` / `space_not_archived` / `space_already_terminal`,`morph_not_active` / `morph_not_archived` / `morph_already_terminal`,以及无 archived 态对象的 `message_already_terminal` / `relation_already_terminal`(见本节末段)。

附加规则:

- **未知对象容忍**:reducer 若收到的 event 指向尚未在本地物化的对象(create event 尚未通过 causal / backfill 到达),MUST NOT 返回 `failed_precondition` 也不改写任何状态——直接 `Ok` 跳过本次副作用。这是 causal-order 安全性，与"对已知对象的 state 校验"不冲突:校验只在物化对象存在时执行。Conformance 实现 MAY 把这种 event 标记为 `pending_causal_apply` 等内部 hint。
- **终态等价**:`tombstoned` / `deleted` 在 state-machine 中等价，都属于"不可逆终态";`redacted` 单独占一格但对 archive / restore / tombstone 而言同样是"不可逆终态"(MUST NOT 被这些 event 修改)。
- **不允许 same-state self-transition**:`ck.<kind>.archive` 在 `state == "archived"` 时 MUST 返回 `<kind>_not_active`,**MUST NOT** 当作 idempotent no-op。这保证 reducer 路径上每个 state transition 都对应一次 audit-able 状态变化；客户端如果想"重新 archive"应当先 restore 再 archive,或确认目标对象 state 后跳过事件提交。
- **`state_changed_at` reducer-derived(normative)**:reducer **MUST** 忽略 wire payload 中任何 actor-supplied 的 `state_changed_at` 值。该字段的权威值是触发本次 state transition 的 Event 的 `created_at`,或 cell update 时该 Event 落在 anchor frontier 上的 `anchored_at`(两者较晚者),与 §3 字段表一致。客户端不得依赖 wire 上的 `state_changed_at` 做时序判断；若 wire 值与 reducer 派生值不一致,SDK SHOULD 报警并以 reducer 派生值为准。该规则防止 actor 通过填错时间戳干扰 retention、audit timeline、conflict tie-break(虽然 §6 已禁止 HLC / event id / actor_seq 作为 cell winner 选边，但 retention 与 audit query 仍可能 group by `state_changed_at`)。

`*.create` 与 `*.update` 永远 set state 为 `active`(或保持当前 active);对一个非 active 对象提交 update MUST 失败(`failed_precondition`,reason 同 `archive_not_active` 家族),否则编辑会隐式复活已 archive/tombstone 的对象——这与 `*.restore` 的语义冲突。Conformance 实现 MUST 把"update on non-active object"视为 invariant 违反。

Message 与 Relation 没有 `archived` 态(见 §5.2 模板使用约束):它们的非 `active` state 一律是不可逆终态。因此对非 active 的 Message / Relation 提交 update(如 `ck.message.revise`)MUST 返回 `failed_precondition`,`reason_code` 取 `<kind>_already_terminal`(即 `message_already_terminal` / `relation_already_terminal`),不使用 `_not_active` 家族。

#### 5.2 Unified lifecycle event template（doc-only canonical）

任何 durable canonical object 的 lifecycle event 家族 SHOULD 按以下模板派生(实际 wire kind 仍按对象自身命名，不强制重命名；本节统一描述以便新对象注册时直接对齐，无需在 event-kind-registry 重新讨论一次):

| 模板槽 | 含义 | 已有实例 |
| --- | --- | --- |
| `ck.<kind>.create` | 创建对象，落 state=`active`,写入 `created_by` / `created_at`。 | `ck.flow.create`、`ck.space.create`、`ck.morph.create`、`ck.message.create` |
| `ck.<kind>.update` | 增量更新 active 对象字段;reducer 拒绝非 active 源。**新对象 SHOULD 沿用 `ck.patch.v1` 统一 patch 表达，不应再造单字段 update event。** | `ck.flow.update`、`ck.morph.update`、`ck.patch.v1`(unified) |
| `ck.<kind>.archive` | active → archived;写入 `state_changed_at`。 | `ck.flow.archive`、`ck.space.archive`、`ck.morph.archive` |
| `ck.<kind>.restore` | archived → active;写入 `state_changed_at`。 | `ck.flow.restore`、`ck.space.restore`、`ck.morph.restore` |
| `ck.<kind>.tombstone` 或 cross-object `ck.redaction` | active/archived → terminal(`tombstoned`/`deleted`/`redacted`);不可逆。Flow 与 Morph 的终态仅通过指向该对象的 `ck.redaction` 表达。 | `ck.space.tombstone`、`ck.relation.tombstone`、`ck.redaction`(指向 flow / space / morph / message) |
| `ck.<kind>.redact` 或 cross-object `ck.redaction` | active/archived → `redacted`(若对象支持);envelope 保留,content 清空。v1 wire 实际注册形态请以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 为准:Message 走 `ck.message.redact`;Flow / Morph / Space / Relation 等未单独注册 `ck.<kind>.redact` 的对象走 cross-object `ck.redaction`。两种 wire 形态都是 canonical (`active` status),按对象选择;reducer 不得自行折叠或互换。 | `ck.message.redact`、`ck.redaction`(用于 flow / morph / space / relation 等未单独注册的对象) |

模板使用约束:

- **不是命名 mandate**,但 **MUST 与 registry 对齐**:模板槽列出的"已有实例"必须存在于 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中;`ck.message.create` 是 v1 标准 wire kind。新对象在注册时按模板选择需要的槽，但**不得**列出 registry 中不存在的 wire kind 当作示例。
- **不创造新槽**:新增 lifecycle 行为(例如"软隔离 / 待审 / 撤回审核")MUST 先在本节扩展模板；否则不得作为标准 lifecycle event 入 registry。
- **patch 优先**:新对象 lifecycle 中的"字段更新"槽 SHOULD 由 `ck.patch.v1` 承载(参见 [`flow-and-message.md` §4.8](./flow-and-message.md) 的 `ck.flow.tracks.update` 实例);避免出现 `ck.<kind>.set_<field>` / `ck.<kind>.toggle_<field>` 这类单点 event 膨胀。**stage 是该原则的明确例外**:`ck.<kind>.stage.set` 走专用 event 是为了 capability 切分与审计过滤(见 §5.3),而非字段膨胀。
- **stage 模板槽**:适配 §5.3 的对象 MUST 注册一条 `ck.<kind>.stage.set` event,走 `object_stage_set_payload` 形态(详见 [`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json));`ck.<kind>.update` patch 路径 MUST NOT 修改 `stage` / `stage_changed_at`(违者 `schema_violation`,单源约束)。**stage 变更不携带 reason 字段**:事件本身已经 durable 且 `created_by` / `created_at` 即审计归属；需要解释"为什么 cancel / block / supersede"时,actor SHOULD 在该对象的 discussion track 发一条 Message(`ck.message.create`),通过 `references` Relation 指向本次 `ck.<kind>.stage.set` event,而不是把 reason 藏在对象字段里。
- **可逆 lifecycle facet 的两种合规形态**:`ck.<kind>.archive` / `ck.<kind>.restore` 模板槽描述的是**独立 archive event + 独立 restore event** 成对形态（Flow / Space / Morph 即此形态）。但可逆 lifecycle 也允许第二种形态：**单一 reversible boolean facet event**（同一 `ck.<kind>.archive` 写 `true` / `false` 在 active ↔ archived 间切换，不发布独立 `ck.<kind>.restore`）。Realm 的 `ck.realm.archive` / `ck.realm.freeze` 即此形态（见 [`realm-and-space.md` §2.6.0](./realm-and-space.md#260-realm-可逆-lifecycle-facetckrealmarchive--ckrealmfreeze)）。具体某对象用哪种，以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 的 `lifecycle_modality` 为准：`reversible` boolean facet 不要求也不应存在配套 `ck.<kind>.restore`。
- **state 校验来源唯一**:本节所有模板事件的状态机校验入口都是 §5.1 表，不在各对象文档重复说明转换矩阵。
- "Space 没有 redacted"：Space 不承载用户 content（仅承载结构容器元数据），无需独立 redaction 状态；title / summary 的内容清理通过 `ck.space.tombstone` 或 `ck.redaction` 一并完成。
- "Message / Relation 没有 archived"：Message timeline 是有时序流，Relation 是边——两者都不需要"软隐藏可撤销"语义；要隐藏 Message 用 redaction，要解除 Relation 用删除即可。
- "Relation 用 `tombstoned` 单一终态"：删除与 redaction 在边语义上不可区分（边只有"存在"或"不存在"），故物化 state 合并为单一 `tombstoned`；具体 reason 在对应 `ck.relation.tombstone` / `ck.redaction` event 中保留。
- Reducer 与 projection MUST 把 `tombstoned` 视为不可逆删除状态；Flow / Morph 不使用 `deleted`，其不可逆内容清除状态是 `redacted`。UI 展示策略（隐藏 vs 显示 tombstone 占位符）由 client 根据对象类型决定。

### 5.3 Stage 轴（业务进度，与 state 正交）

`state` 表达**物理生命周期**（对象是否存在 / 是否可写 / 是否已被 redact）；`stage` 表达**业务进度**（一件事从想法走到完成的过程）。两个字段在不同 reducer 路径上独立维护，**MUST NOT 互相 implicate**：archive 不会把 `stage` 推到 cancelled，`stage=done` 不会自动 archive 对象。

#### 5.3.1 适用对象（v1）

| 对象 | 是否声明 `stage` | 必填语义 | 触发 event |
| --- | --- | --- | --- |
| `Flow` | yes | 可选；`ck.flow.create` MAY 省略，普通业务 Flow SHOULD 填写，DM 主 Flow MAY 省略或选填合法值 | `ck.flow.stage.set` |
| `Morph` | yes | `ck.morph.create` 时 actor 必填 | `ck.morph.stage.set` |
| Realm / Space / Message / Relation / View / Policy / ... | no | — | — |

适用对象自己的 schema MUST 显式枚举允许值；`flow.schema.json` MUST 把 `stage` 声明为可选字段，且 `stage_changed_at` MUST NOT 在缺少 `stage` 时单独出现；`morph.schema.json` MUST 把 `stage` 列入 `required[]`。不适用对象 MUST NOT 暴露 `stage` 顶层字段。**未来如有新对象需要 stage 轴**,扩展时 MUST 同步在本节登记。

#### 5.3.2 协议级枚举（8 值，固定）

| 值 | bucket | 含义 |
| --- | --- | --- |
| `draft` | `todo` | 起草 / scoping,未对外承诺。 |
| `proposed` | `todo` | 待评审 / 决策(accept or reject)。 |
| `planned` | `todo` | 已接受，排期中，未启动。 |
| `in_progress` | `doing` | 当前正在被推进。 |
| `blocked` | `doing` | 在做但被外部依赖卡住。 |
| `done` | `closed` | 成功完成。 |
| `cancelled` | `closed` | 主动放弃，未完成，无替代品。 |
| `superseded` | `closed` | 被另一个对象取代;SHOULD 配套写 Relation `superseded_by` 指向继任。 |

`bucket`(`todo / doing / closed`)是**派生**分类，不入 wire / canonical bytes / 签名输入;projection 自行映射用于 dashboard / filter。bucket 命名刻意避开 `active`,防止与 `state=active` 撞名。

枚举值在 v1 内**固定**,profile MUST NOT 新增 stage value;细粒度业务状态(`needs_review` / `qa` / `signed_off` 等)走 per-Realm workflow profile 或 `fields.<custom_status>`,**不**在协议级 stage 表达。

#### 5.3.3 转换规则（reducer-enforced 硬约束)

`stage` 的细粒度 transition matrix 由 per-Realm workflow profile(profile-level)声明;**核心 reducer 不强制 stage 之间的方向**(`done → in_progress` 回炉、`cancelled → planned` 复活均合法)。但以下硬约束 MUST 由 core reducer 强制:

1. **物理终态优先**:对象 `state ∈ {redacted, tombstoned, deleted}` 时,`ck.<kind>.stage.set` MUST 返回 `failed_precondition`,`reason="<kind>_already_terminal"`。
2. **non-active 拒写**:对象 `state=archived` 时,`ck.<kind>.stage.set` MUST 返回 `failed_precondition`,`reason="<kind>_not_active"`(与 §5.1 update on non-active 同语义);想推进 stage 必须先 `ck.<kind>.restore`。
3. **`stage_changed_at` reducer-derived**:reducer **MUST** 忽略 wire payload 中 actor-supplied 的 `stage_changed_at`,以触发 event 的 `created_at` 覆盖。
4. **same-value self-transition no-op**:`ck.<kind>.stage.set` 把 `stage` 设为与当前相同值时,reducer **不更新** `stage_changed_at`,且不计入审计变更(与 §5.1 `ck.<kind>.archive` 在 same-state 时 fail 的规则**不同** —— stage 是软进度字段，允许 idempotent no-op)。
5. **stage 变更不携带 reason 字段**:`ck.<kind>.stage.set` payload **不**定义 reason / note / explanation 字段。需要解释时 SHOULD 在该对象的 discussion track 发 Message 并通过 Relation `references` 指向本次 stage event;事件日志本身的 `created_by` / `created_at` 已经是审计归属真源。reserved-name guard:对象顶层与 `fields.*` 上 `stage_reason` / `stage_note` / `stage_explanation` / `stage_comment` MUST 被 forbidden-wire-fields 拒绝。
6. **`ck.<kind>.update` 禁写 stage**:patch path `stage` / `stage_changed_at` MUST 被 forbidden-wire-fields 拒绝(单源:stage 变更只能走 `ck.<kind>.stage.set`)。

#### 5.3.4 与 workflow profile 的关系

未启用 workflow profile 的 Realm:actor 通过 `ck.<kind>.stage.set` 直接推进 stage,reducer 只走 §5.3.3 硬约束。

启用 workflow profile 的 Realm(profile-level,non-core):

- 每个 workflow state SHOULD 声明 `stage_category`(取上面 8 值之一);
- workflow 推进 event 在变更 `workflow_state_ref` 时,reducer SHOULD 派生写入对应 `stage`;
- 客户端直接发 `ck.<kind>.stage.set` 仍合法，但 profile MAY 收紧为只允许 workflow event 路径(profile-defined,非 core)。

携带 `stage` 的对象使用该字段作为 workflow 的协议级粗投影，跨 Realm dashboard 可聚合(同一个 `stage=in_progress` bucket 涵盖各 Realm 自定义的"In Dev / Reviewing / QA"等 fine-grained state)。

## 6. 通用对象 ID 约定

Protocol typed identifier / reference 的 wire value MUST 使用带类型前缀的稳定字符串：

```text
ck:realm:<uuid>
ck:space:<uuid>
ck:flow:<uuid>
ck:message:<uuid>
ck:morph:<uuid>
ck:relation:<uuid>
ck:actor_profile:<uuid>
ck:event:<uuid>
ck:view:<uuid>
ck:policy:<uuid>
ck:capability:<uuid>     # abstract capability definition reference（非签名 grant；签名 grant 用 ck:grant:）；真源 artifacts/registry/id-kind-registry.json `capability` 条目
ck:grant:<uuid>
ck:invite:<uuid>
ck:applet:<uuid>
ck:blob:<hash>
ck:receipt:<uuid>
ck:trust_domain:<trust_domain_label>   # 非 UUID 形态，见下方说明
```

UUID 部分 MUST 使用 UUIDv7（time-ordered），便于审计与排序；content-addressed form 使用对应 digest。

并非所有 ID kind 都是 `ck:<kind>:<uuidv7>`。`ck:trust_domain:` 是 deployment-scoped replay boundary 标识：其 wire form 为 `ck:trust_domain:<trust_domain_label>`，`<trust_domain_label>` 是稳定的部署信任域标签（例如 `ck:trust_domain:did.webvh.acme.example`），不是 UUID。它 create-locked 在 Realm `trust_domain` 字段上，MUST 匹配部署 `ServiceDescribe.trust_domain` 与 Realm receive context（见 [`realm-and-space.md` §2.3](./realm-and-space.md)）。

`ck:cell:` / `ck:cursor:` / `ck:anchor:` 等同步 / 状态原语的 wire form 见各自章节与 `artifacts/registry/id-kind-registry.json`，不在本协作图对象 ID 约定表内。上表只是常见 wire value 形态摘要，完整 ID kind 注册表及唯一真源见 `artifacts/registry/id-kind-registry.json`。本节不决定字段名：普通 canonical object 主键仍是 `id`，Event / Receipt / Backup 等 artifact 可用 `<artifact>_id`，Blob / Snapshot / MLS 等 reference 形态按 §2.1 使用 `_ref`。

### 6.1 Policy 对象 vs 内联配置的字段命名约定（normative）

实现者经常困惑：同一个对象上既有 `<axis>_profile` / `<axis>_policy` 这样的内联枚举字段（如 `encryption_profile`、`federation_policy`、`anchor_profile`、`digest_algorithm`），又有 `<axis>_policy_id` 这样指向独立 Policy 对象的字段（如 `policy_id`、`retention_policy_id`、`disclosure_policy_id`、`rate_limit_policy_id`）。这是有意区分，规则如下：

- **`<axis>_profile`**：v1 协议级**固定选项**（create-locked 或 reducer-enforced 收敛），值是封闭 enum 字符串（`"mls_rfc9420"` / `"single_did"` / `"sha256"` / ...）。schema 内联约束，无需引用独立对象。变更需要新 event kind（如 hash-transition Anchor）或新 Realm。
- **`<axis>_policy`**：v1 协议级**软策略字段**，值仍是 enum 字符串（`"open"` / `"restricted"` / `"closed"` / `"quarantine"` 等），但描述运行时执行策略，与其他 cell state 有交互。同样内联，不通过引用对象。
- **`<axis>_policy_id`**：指向独立 Policy 对象（`ck:policy:<uuid>`）的 ID，pattern `^ck:policy:[0-9a-f]{8}-...`。Policy 对象自身有 schema 与版本，可以被多个对象共享、被 governance event 修订。独立对象用于：(a) 跨对象复用、(b) 大体积或频繁变更、(c) 需要独立审计 / 签名链。
- **`<axis>_floor`**：某条加密 / 隐私轴上的**下限**字段，值与对应 `<axis>_profile` 取同一封闭 enum，但语义是"只能向上收紧、MUST NOT 放宽继承到的上游基线"。它用于子作用域声明比父作用域更严格的下限：父作用域（Realm）声明基线时用 `<axis>_profile`（例如 Realm 的 `metadata_encryption_floor`），子作用域（Circle、Space `child_scope_policy`）声明下限时用 `<axis>_floor`（例如 Circle 的 `metadata_encryption_floor`）。effective 值取上游 `_profile` 与各层 `_floor` 的更严格者（见 [`circle.md` §7](./circle.md)）。父字段保留 `_profile` 名、子字段使用 `_floor` 名是有意区分，不视为同义别名混用。

判定流程：写新字段时若是**封闭 enum**（值集已知、协议级固定）用 `_profile` 或 `_policy`；若是**指向 Policy 对象**用 `_policy_id`；不得在同一对象上同时定义 `xxx_policy` 与 `xxx_policy_id` 表示同一个轴。若字段引用的是"授权该决策的 policy revision Event"，使用带 event 语义的 `_ref` 名称，例如 `policy_event_ref`，不得与 `policy_id` 混用。

公共字段示例：

```json
{
  "id": "ck:flow:01964137-0000-7000-8000-000000000000",
  "schema": "ck.schema.flow.v1",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "created_by": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "updated_at": "2026-04-26T00:00:00Z"
}
```

## 7. Reducer 总则

Reducer 总则的 normative 表述以 [`event-and-patch.md` §6](./event-and-patch.md) 为唯一权威；本节不再重复列出验证步骤，避免两份独立维护的清单漂移。

§5 state-transition 表与 §5.1 `failed_precondition` reason-code 族属于本节关注的"对象 lifecycle 层 reducer 行为"; 它们与 §6 (Event-level reducer 总则) 形成"对象层 ↔ 事件层"两个互补侧面，均受 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 统一约束。

## 8. 规范性引用

- 完整 ID kind registry：`artifacts/registry/id-kind-registry.json`。
- Schema registry：`artifacts/registry/schema-registry.json` 与 [`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- Canonical JSON、hash、签名、cursor、HLC、rank 编码：[`../conformance/encoding.md`](../conformance/encoding.md)。
- Reducer conformance vector：[`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md)。
