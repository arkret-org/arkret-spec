---
title: Common Fields
---

## 1. 目标

本文定义 Contrix 协作图所有 canonical object 共享的字段、lifecycle 状态机、主体引用语义与 reducer 总则。每个对象自己的字段表（Realm / Flow / Message / ...）放在该对象的专属文件中；本文只承载"所有对象都遵循"的内容。

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
| `id:<kind>` | `cx:<kind>:<uuid>` typed ID，或该 kind 在 `id-kind-registry.json` 声明的特殊 wire form。 |
| `hash` | `sha256:<lowercase_hex_digest>`。 |
| `cursor` | `cx:cursor:<base64url>` opaque string。 |
| `patch` | `cx.patch.v1` 形态的 JSON patch 片段，具体路径与 op 规则见 [`event-and-patch.md`](./event-and-patch.md)。 |

注：`device_id` 不是例外字段；它的类型是 `id:device`，wire form MUST 为 `cx:device:<uuid>`。只有部分辅助标识符（如 `transaction_id`、`backup_version`、`stream_id`）使用领域特定前缀（如 `ver_`、`kb_`、`devstream_`），不遵循 `cx:<kind>:<uuid>` 格式。这些标识符的编码规则由各自所在章节定义。

字段默认规则：

- 未标记 optional 的字段为 required。
- `null` 只有在类型中明确写出时才允许。
- 实现 MUST 保留未知字段，但 MUST NOT 让未知字段绕过 capability、schema、policy 或加密约束。
- 签名和 hash 输入 MUST 使用 canonical JSON。
- `id:<kind>` 在 wire、canonical object、fixture、签名和跨服务引用中 MUST 使用完整 typed ID。数据库内部 MAY 只存 raw id，但在序列化、签名、hash、联邦、sync cursor 和审计回放前必须恢复 `cx:<kind>:` 前缀；不得把数据库主键或表名当作协议 ID 的替代品。
- 当 `id:<kind>` 出现在 JSON object key 中时，它仍然属于 wire value；例如 `messages.{principal_id}.{device_id}` 中的 `{device_id}` MUST 使用完整 `cx:device:<uuid>`，不得写成局部别名如 `dev_a` 或 `a`。
- `summary` / `description` 命名约定：canonical object 或 projection row 的短摘要、列表预览、聚合摘要使用 `summary`；原因说明、补充说明、长说明或 schema / registry 元数据说明使用 `description`。OpenAPI 自身标准关键字 `summary` / `description` 按 OpenAPI 语义使用。若字段承载人类可读名称，canonical object 默认使用 `title`，Actor / user-facing identity profile 使用 `display_name`；`name` 只用于外部协议、加密算法、service surface 或 registry 内部 label，不作为 Realm / Space / Flow 等 canonical object 的显示名。
- Projection row 若表达 canonical object 的同一概念，MUST 沿用 canonical 字段名（例如 `title`、`summary`、`avatar_blob_ref`、`owning_organizations`），不得另起 `name`、`avatar`、`official_organizations` 等别名。若服务需要返回渲染友好的派生对象，字段名 MUST 明确带 projection 语义并有 schema；v1 默认不定义通用 `avatar` projection，头像引用使用 `avatar_blob_ref`。
- `_id` / `_ref` / `_did` 后缀约定：`_id` 表示 typed protocol id，或本协议把 DID 当作责任主体 id 使用的字段（如 `actor_id`、`principal_id`、`subject_id`、`watcher_actor_id`）；`_ref` 表示可解引用对象、版本、receipt、anchor 或 content-addressed reference；`_did` 只在字段必须强调“原始 DID material”并与 pairwise DID、DID URL、外部 DID 或 disclosure transcript 对照时使用。新增主体字段默认不得使用 `_did` 后缀。
- `kind` / `type` 命名约定：`kind` 用于协议内 discriminator、routing、registry event/object family、lattice/reducer 分派和 Relation/View 等 canonical 分类；`type` 用于外部标准 taxonomy、媒体类型、服务分类或不参与 reducer routing 的领域分类。Event Envelope 顶层 `kind` 是唯一 event discriminator；payload 不得用 `type` 重复 event kind。
- 时间边界命名约定：有效期下界统一使用 `not_before`，有效期上界统一使用 `expires_at`；缓存或派生结果的失效时间使用带领域前缀的 `cache_expires_at`。新增 wire 字段不得使用 `valid_from`、`valid_until` 或 `not_after` 作为同义别名。
- `state` / `status` / `stage` 命名约定：`state` 表示 canonical object 的物理生命周期；`stage` 表示 Flow / Morph 等业务进度轴；`status` 只用于账号、session、delivery、外部过程或 registry 条目状态，不用于表达 object lifecycle 目标值。对象 lifecycle payload 若需要携带目标状态，字段名使用 `target_state`。
- `created_by` / `creator_*` 命名约定：materialized object metadata 使用 `created_by` / `updated_by`，由 reducer 从 Event `actor_id` 派生。`creator_*` 只用于外部协议或加密 transcript 自身的创建者 tuple（例如 MLS group creator），不得作为 object 创建主体字段的别名。
- Event proof 中绑定 canonical Event bytes 的字段名是 `event_digest`。`payload_hash` 仅可用于非 Event 的通用 detached proof，且其说明必须写明被 hash 的 canonical payload；不得在 Event proof 或 Event digest 语义中使用 `payload_hash`。
- 签名 proof 中表示签名 key DID URL 的字段统一为 `verification_method`，不得使用 `signed_by`。若需要表达消息或通知中的发送主体，使用带角色的 `sender_actor_id`；展示名称使用 `sender_actor_display_name`，不得用裸 `sender` 承载 DID。
- `recipient_service_did` 与 `audience` 不可互换：前者是物理路由目标 service DID，后者是密码学 transcript / proof 的受众绑定。即使 `audience` 只有一个 DID，也不得替代 `recipient_service_did`；反之亦然。
- `scope` 命名约定：wire schema 中不得新增裸 `scope` 字段；必须用领域前缀说明形态与用途，例如 `read_scope`、`receipt_scope`、`event_range`、`match_scope`、`claim_scope`、`erasure_scope`、`agent_key_scope`、`consent_scope`、`realm_key_scope`、`extension_scope`、`constraint_scope`、`policy_scope`、`search_scope`、`relation_scope`。Registry 元数据若表示条目适用范围，可继续使用 `scope`。
- 诊断命名约定：机器可枚举的失败 / 恢复 / reset 原因使用 `reason_code` 或带领域前缀的 `*_reason_code`；人类可读自由文本使用 `reason` 或 `description`。受控枚举不得命名为 `reason`。
- ID kind 与 wire prefix 必须使用完整 snake_case 名称，不得使用缩写前缀（例如使用 `cx:notification:`、`cx:device_message:`、`cx:key_event:`、`cx:moderation_queue_item:`、`cx:request:`、`cx:transaction:`、`cx:franking_proof:`）。
- CRDT lattice 字段使用 `lattice`，枚举值使用 snake_case（如 `or_set`、`mv_register`、`cas_register`、`ordered_log`、`lww_register`）。新增 lattice 枚举不得使用 kebab-case。
- Event kind 动词使用动词原形表达 reducer 动作（如 `authorize`、`revoke`、`rotate`、`tombstone`）；只有纯状态通告或外部标准名有明确理由时才可使用过去分词。
- Capability action 命名约定：
  - **`cx.<entity>.<verb>` 是默认形态**，对应 `target_event_kinds` 中的一个或多个 reducer-input event kind。Action name 与 event kind 可以重合 (例如 `cx.flow.archive` action 授权同名 event)，也可以不同 (例如 `cx.invite.create_third_party` action 授权 `cx.invite.third_party` event), 由 capability-action-registry `target_event_kinds` 字段桥接, 无需在命名上一致。
  - **通用 `cx.object.<verb>`**（如 `cx.object.read` / `cx.object.archive` / `cx.object.restore` / `cx.object.stage.set`) 只允许在 Realm-wide admin 或跨实体审计 grant 中使用 (`match_scope` 不限定单一实体 ID); 对单一实体的常规授权 MUST 使用专属 `cx.<entity>.<verb>` (例如 `cx.flow.archive`)。这是为了让 grant author 在最小作用域内表达意图, 同时保留 admin 路径使用通用 action 的能力。
  - **后缀 `.own` / `.others`**: 不带后缀的 action 默认作用域不限定 "creator = grantee"; 加 `.own` 表示 "仅 actor 自己创建的对象" (例如 `cx.message.revise.own`, `cx.message.redact.own`); 加 `.others` 表示 "允许操作他人创建的对象", 通常 risk_tier=high。三种形态 MUST 在 capability-action-registry 中分别登记, 不得当作通配等价。历史命名 `manage_others` 已收敛为 `.others` 后缀（例如 `cx.flow.watch.set.others`）。

## 3. Common Object Fields

所有 durable canonical object SHOULD 使用以下公共字段，除非对象类型另有说明。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:*` | typed ID 前缀决定对象种类（`cx:flow:` 即 flow 对象，依此类推）。 | 对象稳定 ID；前缀就是 type，不再单独写 `type` 字段。 |
| `realm_id` | conditional | `id:realm` | Realm 外对象可省略。 | 所属 Realm。 |
| `schema` | yes | `string` | SHOULD 是 `cx.schema.*.vN` 或反向域名 schema id。 | 验证 schema id。 |
| `created_by` | conditional | `did` | 系统派生对象可由 `derived_from` 替代。 | 创建主体（创建该对象的 Event 的 `actor_id`）。 |
| `created_at` | yes | `timestamp` | 不能作为因果真相。 | 创建时间。 |
| `updated_by` | no | `did` | 更新时 SHOULD 设置。 | 最近更新主体。 |
| `updated_at` | no | `timestamp` | MUST 不早于 `created_at`。 | 最近更新时间。 |
| `deleted_at` | no | `timestamp` | durable tombstone 可用。 | 逻辑删除时间。 |
| `state_changed_at` | conditional | `timestamp` | **Reducer-derived,actor 不可信:** 所有具有 `state` 字段的对象（Flow / Space / Message / Morph / Relation）当 `state != active` 时 MUST 写入;reducer **MUST** 忽略任何 wire payload 中 actor-supplied 的 `state_changed_at` 值,以触发该 state transition 的 Event 的 `created_at`(或对应 anchor 的 `anchored_at`,以两者中较晚者为准)覆盖写入。MUST 不早于 `created_at`,MUST ≤ `updated_at`(当后者存在时)。 | 最近一次 state 转换时间。 |
| `stage` | conditional | `enum` | 适用对象自己的 schema 声明本字段时必填（v1 适用对象 = Flow / Morph，详见 §5.3）；取值为 §5.3 的协议级 8 值枚举。**禁止与 `state` 混用**：`stage` 表达业务进度，`state` 表达物理生命周期，两者正交。`fields.stage` / `fields.lifecycle` / `fields.progress_state` / `fields.stage_reason` 等同名/近名 wire 路径 MUST 被拒绝（见 [`artifacts/registry/forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json)）。stage 变更的"为什么"解释通过 discussion track Message 表达，不在对象字段中携带。 | 业务进度阶段。 |
| `stage_changed_at` | conditional | `timestamp` | **Reducer-derived，actor 不可信：** 适用对象 `stage` 字段每次实际变更时 MUST 写入；reducer **MUST** 忽略 wire payload 的 actor-supplied 值，以触发该 transition 的 `cx.<kind>.stage.set` event 的 `created_at` 覆盖写入。MUST 不早于 `created_at`。same-value self-transition（stage 值未变）reducer MUST NOT 更新本字段。 | 最近一次 stage 转换时间。 |
| `labels` | no | `array<string>` | SHOULD 小写短标签。 | 用户或系统标签。 |
| `fields` | no | `object` | 字段 schema 由对象类型自身的 `schema_refs` 决定。 | 扩展字段；v1 唯一标准扩展容器。 |

对象种类由 `id` 的 typed prefix（`cx:flow:` / `cx:realm:` / ...）唯一决定；扩展字段统一走 `fields`，由对象 `schema_refs` 约束。Event Envelope 不是 Materialized Object，事件类型由顶层 `kind` 表达。

## 4. 主体引用字段交叉对照

### 4.1 DID 适用边界

DID 是 Contrix 的主体标识，不是普通协作对象 ID。标准协作对象（Realm / Space / Flow / Message / Morph / Relation / View / Policy / Grant / Invite / Blob 等）MUST 使用 `cx:<kind>:` typed ID 作为对象 ID；只有当字段表达 actor / principal / issuer / subject / service / device / controller / accountable party 时，才使用 DID 或 DID URL。

因此，"需要有 DID"的对象与结构按下表理解：

| 对象 / 结构 | 必须包含的 DID 字段 | 说明 |
| --- | --- | --- |
| Actor identity（user / org / team / agent / service / device / integration） | DID 本身 | Actor 的身份根就是 DID；若需要在协作图中展示，则用 Actor Profile 承载展示字段。 |
| Actor Profile (`cx:actor_profile:`) | `principal_id` | Profile 只是展示镜像；`principal_id` 才是授权、签名和审计归属的主体 DID。 |
| Event Envelope (`cx:event:`) | `actor_id`; Proof 中的 `verification_method` 为 DID URL | `actor_id` 是签署并提交事件的 actor DID，MUST 匹配 proof 控制链。 |
| Realm (`cx:realm:`) | `created_by_principal` | Realm create event 的授权 principal；`owning_organizations[]` 可选使用组织 DID。 |
| Space / Flow / Message / Morph / Relation / View / Policy / Blob metadata | `created_by`; 更新时可有 `updated_by` | 这些对象自身不使用 DID 做 `id`；DID 只记录创建 / 更新主体。协作图对象的创建 / 更新主体由 reducer 从对应 Event 的 `actor_id` 派生；Blob metadata 的 `created_by` 来自 authenticated media 写入主体。 |
| Capability Grant (`cx:grant:`) | `issuer`; `subject` 为具体主体时必须是 DID | `subject` 也可以是条件 selector；handle、邮箱、域名用户名等不得作为权限主体主键。 |
| Invite (`cx:invite:`) | `inviter`; `invitee` 在直接 DID 邀请时使用 DID | 3PID 邀请可没有 `invitee`，但认领后必须绑定可验证主体。 |
| Read Cursor / Notification | `actor_id` | actor-private 或派生对象，`actor_id` 表示该私有状态所属主体。 |
| Event Batch Receipt / Identity Receipt / Audit Receipt | `issuer` 或 schema 声明的签发 / 主体 DID 字段 | receipt 的签发、覆盖范围和验证必须回到可解析 DID。 |
| Relation endpoint | 当 endpoint 是 Actor 时，`from_ref` / `to_ref` 使用 DID | 指向普通对象时仍使用 `cx:<kind>:` typed ID；Relation 不把对象 ID 转换为 DID。 |

任何可签名、可被授予 capability、可作为审计责任主体或可被 Realm / service policy allowlist 的实体，MUST 有可解析 DID。仅作为内容、容器、投影或关系事实存在的对象，不需要也不得发明独立 DID；它们通过 typed ID 被引用，通过 `created_by` / `updated_by` 等字段关联到 DID 主体。

### 4.2 主体引用字段

| 字段 | 出现对象 | 含义 |
| --- | --- | --- |
| `actor_id` | Event Envelope、Read Cursor、Notification | 直接执行该 Event / 拥有该私有状态的 actor DID（`actor_kind` 决定它是 user / agent / service 等）。 |
| `watcher_actor_id` / `target_actor_id` / `writer_actor_id` | Event payload、Audit payload | 带角色限定的 actor DID-as-id；字段名必须说明角色，避免回退到模糊的 `actor_did`。 |
| `principal_id` | Actor Profile | Profile 对应的 principal DID；权限根。 |
| `created_by` / `updated_by` | 所有 Materialized Object | 创建 / 最近更新该对象的 Event 的 `actor_id`，由 reducer 派生。 |
| `issuer` | Capability Grant、Identity Receipt | 签发授权或 receipt 的 DID；必须持有签发权限。 |
| `subject` | Capability Grant | 被授权 DID 或 selector condition。 |
| `subject_id` | Handle / invite / delivery binding candidate | 当 subject 必须是具体 principal DID 且进入可验证 transcript 时使用；generic claim subject 仍使用 `subject`。 |
| `inviter` / `invitee` | Invite | 邀请方 DID / 被邀请 DID。 |
| `created_by_principal` | Realm | Realm create event 的授权 principal（与该事件 `actor_id` 一致）。 |

这些不是同一字段的别名，每条都有独立语义角色；该表用于读 spec 时快速建立对应关系。

## 5. State 枚举对齐

各对象的 `state` 字段值不完全相同（部分名字承载了已稳定的 `cx.*.tombstone` event 命名约定），但在 reducer / projection 语义层等价于以下规范状态机：

| 规范状态 | 语义 | Flow | Space | Message | Morph | Relation | Realm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `active` | 当前可用 | `active` | `active` | `active` | `active` | `active` | `active` |
| `archived` | 软隐藏，UI 默认不展示，可撤销 | `archived` | `archived` | — | `archived` | — | `archived` |
| `redacted` | 内容已根据 redaction policy 清除，envelope 与审计元数据保留 | `redacted` | — | `redacted` | `redacted` | `tombstone`（合并 deleted+redacted） | — |
| `deleted` | 不可逆删除：content / encrypted_payload 清空，仅保留 envelope 用于审计 | — | `tombstoned` | `deleted` | — | `tombstone` | `tombstoned` |

约定：

- 写入路径 MUST 来自对应 reducer-input event（`cx.<kind>.archive` / `cx.<kind>.restore` / `cx.<kind>.tombstone` / `cx.<kind>.redact` 或等价命名）；不得直接 PATCH 对象顶层 state。`archived -> active` 是显式的可逆转换，由 `cx.<kind>.restore`（Flow、Space、Morph 均已注册对应 restore event）承担；`tombstoned` / `deleted` / `redacted` 是不可逆终态，MUST NOT 被 restore。
- `state != active` 时 MUST 写入 `state_changed_at`（见 §3 公共字段）。

#### 5.1 Canonical state-transition table

每个 reducer-input lifecycle event 都 MUST 校验**当前 state**(reducer 视角下的 pre-state)落在下表"合法源"集合内,否则 MUST 返回 `failed_precondition`,`reason` 取下表 `reason_code` 列。

| event family | 允许的源 state | 目标 state | `failed_precondition` reason_code |
| --- | --- | --- | --- |
| `cx.<kind>.archive` | `active` | `archived` | `<kind>_not_active` |
| `cx.<kind>.restore` | `archived` | `active` | `<kind>_not_archived` |
| `cx.<kind>.tombstone` | `active`、`archived` | `tombstoned` / `deleted`(各对象 schema 自命名) | `<kind>_already_terminal` |
| `cx.<kind>.redact` 或 cross-object `cx.redaction` 指向该对象 | `active`、`archived` | `redacted`(如对象支持),或合并到 `tombstoned` | `<kind>_already_terminal` |

`<kind>` 是 schema 类型短名(`flow`、`space`、`morph`、`message`),所有 reducer 实现 MUST 用相同 reason_code,使跨实现错误诊断一致。具体值如:`flow_not_active` / `flow_not_archived` / `flow_already_terminal`,`space_not_active` / `space_not_archived` / `space_already_terminal`,`morph_not_active` / `morph_not_archived` / `morph_already_terminal`。

附加规则:

- **未知对象容忍**:reducer 若收到的 event 指向尚未在本地物化的对象(create event 尚未通过 causal / backfill 到达),MUST 不返回 `failed_precondition` 也不改写任何状态——直接 `Ok` 跳过本次副作用。这是 causal-order 安全性,与"对已知对象的 state 校验"不冲突:校验只在物化对象存在时执行。Conformance 实现 MAY 把这种 event 标记为 `pending_causal_apply` 等内部 hint。
- **终态等价**:`tombstoned` / `deleted` 在 state-machine 中等价,都属于"不可逆终态";`redacted` 单独占一格但对 archive / restore / tombstone 而言同样是"不可逆终态"(MUST NOT 被这些 event 修改)。
- **不允许 same-state self-transition**:`cx.<kind>.archive` 在 `state == "archived"` 时 MUST 返回 `<kind>_not_active`,**不能**当作 idempotent no-op。这保证 reducer 路径上每个 state transition 都对应一次 audit-able 状态变化;客户端如果想"重新 archive"应当先 restore 再 archive,或确认目标对象 state 后跳过事件提交。
- **`state_changed_at` reducer-derived(normative)**:reducer **MUST** 忽略 wire payload 中任何 actor-supplied 的 `state_changed_at` 值。该字段的权威值是触发本次 state transition 的 Event 的 `created_at`,或 cell update 时该 Event 落在 anchor frontier 上的 `anchored_at`(两者较晚者),与 §3 字段表一致。客户端不得依赖 wire 上的 `state_changed_at` 做时序判断;若 wire 值与 reducer 派生值不一致,SDK SHOULD 报警并以 reducer 派生值为准。该规则防止 actor 通过填错时间戳干扰 retention、audit timeline、conflict tie-break(虽然 §6 已禁止 HLC / event id / actor_seq 作为 cell winner 选边,但 retention 与 audit query 仍可能 group by `state_changed_at`)。

`*.create` 与 `*.update` 永远 set state 为 `active`(或保持当前 active);对一个非 active 对象提交 update MUST 失败(`failed_precondition`,reason 同 `archive_not_active` 家族),否则编辑会偷偷复活已 archive/tombstone 的对象——这与 `*.restore` 的语义冲突。Conformance 实现 MUST 把"update on non-active object"视为 invariant 违反。

#### 5.2 Unified lifecycle event template（doc-only canonical）

任何 durable canonical object 的 lifecycle event 家族 SHOULD 按以下模板派生(实际 wire kind 仍按对象自身命名,不强制重命名;本节统一描述以便新对象注册时直接对齐,无需在 event-kind-registry 重新讨论一次):

| 模板槽 | 含义 | 已有实例 |
| --- | --- | --- |
| `cx.<kind>.create` | 创建对象,落 state=`active`,写入 `created_by` / `created_at`。 | `cx.flow.create`、`cx.space.create`、`cx.morph.create`、`cx.message.create` |
| `cx.<kind>.update` | 增量更新 active 对象字段;reducer 拒绝非 active 源。**新对象 SHOULD 沿用 `cx.patch.v1` 统一 patch 表达,不应再造单字段 update event。** | `cx.flow.update`、`cx.morph.update`、`cx.patch.v1`(unified) |
| `cx.<kind>.archive` | active → archived;写入 `state_changed_at`。 | `cx.flow.archive`、`cx.space.archive`、`cx.morph.archive` |
| `cx.<kind>.restore` | archived → active;写入 `state_changed_at`。 | `cx.flow.restore`、`cx.space.restore`、`cx.morph.restore` |
| `cx.<kind>.tombstone` 或 cross-object `cx.redaction` | active/archived → terminal(`tombstoned`/`deleted`/`redacted`);不可逆。Flow 与 Morph 的终态仅通过指向该对象的 `cx.redaction` 表达。 | `cx.space.tombstone`、`cx.relation.tombstone`、`cx.redaction`(指向 flow / space / morph / message) |
| `cx.<kind>.redact` 或 cross-object `cx.redaction` | active/archived → `redacted`(若对象支持);envelope 保留,content 清空。v1 wire 实际注册形态请以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 为准:Message 走 `cx.message.redact`;Flow / Morph / Space / Relation 等未单独注册 `cx.<kind>.redact` 的对象走 cross-object `cx.redaction`。两种 wire 形态都是 canonical (`active` status),按对象选择;reducer 不得自行折叠或互换。 | `cx.message.redact`、`cx.redaction`(用于 flow / morph / space / relation 等未单独注册的对象) |

模板使用约束:

- **不是命名 mandate**,但 **MUST 与 registry 对齐**:模板槽列出的"已有实例"必须存在于 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中;`cx.message.create`(非历史草案中的 `cx.message.send`)是 v1 标准 wire kind。新对象在注册时按模板选择需要的槽,但**不得**列出 registry 中不存在的 wire kind 当作示例。
- **不创造新槽**:新增 lifecycle 行为(例如"软隔离 / 待审 / 撤回审核")MUST 先在本节扩展模板;否则不得作为标准 lifecycle event 入 registry。
- **patch 优先**:新对象 lifecycle 中的"字段更新"槽 SHOULD 由 `cx.patch.v1` 承载(参见 [`flow-and-message.md` §4.8](./flow-and-message.md) 的 `cx.flow.tracks.update` 实例);避免出现 `cx.<kind>.set_<field>` / `cx.<kind>.toggle_<field>` 这类单点 event 膨胀。**stage 是该原则的明确例外**:`cx.<kind>.stage.set` 走专用 event 是为了 capability 切分与审计过滤(见 §5.3),而非字段膨胀。
- **stage 模板槽**:适配 §5.3 的对象 MUST 注册一条 `cx.<kind>.stage.set` event,走 `object_stage_set_payload` 形态(详见 [`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json));`cx.<kind>.update` patch 路径 MUST NOT 修改 `stage` / `stage_changed_at`(违者 `schema_violation`,单源约束)。**stage 变更不携带 reason 字段**:事件本身已经 durable 且 `created_by` / `created_at` 即审计归属;需要解释"为什么 cancel / block / supersede"时,actor SHOULD 在该对象的 discussion track 发一条 Message(`cx.message.create`),通过 `references` Relation 指向本次 `cx.<kind>.stage.set` event,而不是把 reason 藏在对象字段里。
- **state 校验来源唯一**:本节所有模板事件的状态机校验入口都是 §5.1 表,不在各对象文档重复说明转换矩阵。
- "Space 没有 redacted"：Space 不承载用户 content（仅承载结构容器元数据），无需独立 redaction 状态；title / summary 的内容清理通过 `cx.space.tombstone` 或 `cx.redaction` 一并完成。
- "Message / Relation 没有 archived"：Message timeline 是有时序流，Relation 是边——两者都不需要"软隐藏可撤销"语义；要隐藏 Message 用 redaction，要解除 Relation 用删除即可。
- "Relation 用 `tombstone` 单一终态"：删除与 redaction 在边语义上不可区分（边只有"存在"或"不存在"），故合并为单一 `tombstone`；具体 reason 在对应 `cx.relation.tombstone` / `cx.redaction` event 中保留。
- Reducer 与 projection MUST 把 `tombstoned` / `tombstone` / `deleted` 视为语义等价的"不可逆删除"状态；Flow / Morph 不使用 `deleted`，其不可逆内容清除状态是 `redacted`。UI 展示策略（隐藏 vs 显示 tombstone 占位符）由 client 根据对象类型决定。

### 5.3 Stage 轴（业务进度，与 state 正交）

`state` 表达**物理生命周期**（对象是否存在 / 是否可写 / 是否已被 redact）；`stage` 表达**业务进度**（一件事从想法走到完成的过程）。两个字段在不同 reducer 路径上独立维护，**MUST NOT 互相 implicate**：archive 不会把 `stage` 推到 cancelled，`stage=done` 不会自动 archive 对象。

#### 5.3.1 适用对象（v1）

| 对象 | 是否声明 `stage` | 必填语义 | 触发 event |
| --- | --- | --- | --- |
| `Flow` | yes | `cx.flow.create` 时 actor 必填 | `cx.flow.stage.set` |
| `Morph` | yes | `cx.morph.create` 时 actor 必填 | `cx.morph.stage.set` |
| Realm / Space / Message / Relation / View / Policy / ... | no | — | — |

适用对象自己的 schema(`flow.schema.json` / `morph.schema.json`)MUST 把 `stage` 列入 `required[]` 并显式枚举允许值;不适用对象 MUST NOT 暴露 `stage` 顶层字段。**未来如有新对象需要 stage 轴**,扩展时 MUST 同步在本节登记。

#### 5.3.2 协议级枚举（8 值，固定）

| 值 | bucket | 含义 |
| --- | --- | --- |
| `draft` | `todo` | 起草 / scoping,未对外承诺。 |
| `proposed` | `todo` | 待评审 / 决策(accept or reject)。 |
| `planned` | `todo` | 已接受,排期中,未启动。 |
| `in_progress` | `doing` | 当前正在被推进。 |
| `blocked` | `doing` | 在做但被外部依赖卡住。 |
| `done` | `closed` | 成功完成。 |
| `cancelled` | `closed` | 主动放弃,未完成,无替代品。 |
| `superseded` | `closed` | 被另一个对象取代;SHOULD 配套写 Relation `superseded_by` 指向继任。 |

`bucket`(`todo / doing / closed`)是**派生**分类,不入 wire / canonical bytes / 签名输入;projection 自行映射用于 dashboard / filter。bucket 命名刻意避开 `active`,防止与 `state=active` 撞名。

枚举值在 v1 内**固定**,profile MUST NOT 新增 stage value;细粒度业务状态(`needs_review` / `qa` / `signed_off` 等)走 per-Realm workflow profile 或 `fields.<custom_status>`,**不**在协议级 stage 表达。

#### 5.3.3 转换规则（reducer-enforced 硬约束)

`stage` 的细粒度 transition matrix 由 per-Realm workflow profile(profile-level)声明;**核心 reducer 不强制 stage 之间的方向**(`done → in_progress` 回炉、`cancelled → planned` 复活均合法)。但以下硬约束 MUST 由 core reducer 强制:

1. **物理终态优先**:对象 `state ∈ {redacted, tombstoned, deleted}` 时,`cx.<kind>.stage.set` MUST 返回 `failed_precondition`,`reason="<kind>_already_terminal"`。
2. **non-active 拒写**:对象 `state=archived` 时,`cx.<kind>.stage.set` MUST 返回 `failed_precondition`,`reason="<kind>_not_active"`(与 §5.1 update on non-active 同语义);想推进 stage 必须先 `cx.<kind>.restore`。
3. **`stage_changed_at` reducer-derived**:reducer **MUST** 忽略 wire payload 中 actor-supplied 的 `stage_changed_at`,以触发 event 的 `created_at` 覆盖。
4. **same-value self-transition no-op**:`cx.<kind>.stage.set` 把 `stage` 设为与当前相同值时,reducer **不更新** `stage_changed_at`,且不计入审计变更(与 §5.1 `cx.<kind>.archive` 在 same-state 时 fail 的规则**不同** —— stage 是软进度字段,允许 idempotent no-op)。
5. **stage 变更不携带 reason 字段**:`cx.<kind>.stage.set` payload **不**定义 reason / note / explanation 字段。需要解释时 SHOULD 在该对象的 discussion track 发 Message 并通过 Relation `references` 指向本次 stage event;事件日志本身的 `created_by` / `created_at` 已经是审计归属真源。reserved-name guard:对象顶层与 `fields.*` 上 `stage_reason` / `stage_note` / `stage_explanation` / `stage_comment` MUST 被 forbidden-wire-fields 拒绝。
6. **`cx.<kind>.update` 禁写 stage**:patch path `stage` / `stage_changed_at` MUST 被 forbidden-wire-fields 拒绝(单源:stage 变更只能走 `cx.<kind>.stage.set`)。

#### 5.3.4 与 workflow profile 的关系

未启用 workflow profile 的 Realm:actor 通过 `cx.<kind>.stage.set` 直接推进 stage,reducer 只走 §5.3.3 硬约束。

启用 workflow profile 的 Realm(profile-level,non-core):

- 每个 workflow state SHOULD 声明 `stage_category`(取上面 8 值之一);
- workflow 推进 event 在变更 `workflow_state_ref` 时,reducer SHOULD 派生写入对应 `stage`;
- 客户端直接发 `cx.<kind>.stage.set` 仍合法,但 profile MAY 收紧为只允许 workflow event 路径(profile-defined,非 core)。

如此 stage 成为 workflow 的协议级粗投影,跨 Realm dashboard 可聚合(同一个 `stage=in_progress` bucket 涵盖各 Realm 自定义的"In Dev / Reviewing / QA"等 fine-grained state)。

## 6. 通用对象 ID 约定

对象 ID SHOULD 使用带类型前缀的稳定字符串：

```text
cx:realm:<uuid>
cx:space:<uuid>
cx:flow:<uuid>
cx:message:<uuid>
cx:morph:<uuid>
cx:relation:<uuid>
cx:actor_profile:<uuid>
cx:event:<uuid>
cx:view:<uuid>
cx:policy:<uuid>
cx:grant:<uuid>
cx:invite:<uuid>
cx:applet:<uuid>
cx:blob:<hash>
cx:receipt:<uuid>
```

UUID 部分 SHOULD 使用 UUIDv7（time-ordered），便于审计与排序。完整 ID kind 注册表见 `artifacts/registry/id-kind-registry.json`。

公共字段示例：

```json
{
  "id": "cx:flow:01964137-0000-7000-8000-000000000000",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "created_by": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "updated_at": "2026-04-26T00:00:00Z",
  "schema": "cx.schema.flow.v1"
}
```

## 7. Reducer 总则

Reducer 总则的 normative 表述以 [`event-and-patch.md` §6](./event-and-patch.md) 为唯一权威；本节不再重复列出验证步骤,避免两份独立维护的清单漂移。

§5 state-transition 表与 §5.1 `failed_precondition` reason-code 族属于本节关注的"对象 lifecycle 层 reducer 行为"; 它们与 §6 (Event-level reducer 总则) 形成"对象层 ↔ 事件层"两个互补侧面,均受 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 统一约束。

## 8. 规范性引用

- 完整 ID kind registry：`artifacts/registry/id-kind-registry.json`。
- Schema registry：`artifacts/registry/schema-registry.json` 与 [`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- Canonical JSON、hash、签名、cursor、HLC、rank 编码：[`../conformance/encoding.md`](../conformance/encoding.md)。
- Reducer conformance vector：[`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md)。
