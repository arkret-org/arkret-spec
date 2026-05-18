---
title: Common Fields
---

## 1. 目标

本文定义 Contrix 协作图所有 canonical object 共享的字段、lifecycle 状态机、主体引用语义与 reducer 总则。每个对象自己的字段表（Space / Flow / Message / ...）放在该对象的专属文件中；本文只承载"所有对象都遵循"的内容。

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

注：`device_id` 不是例外字段；它的类型是 `id:device`，wire form MUST 为 `cx:device:<uuid>`。只有部分辅助标识符（如 `transaction_id`、`backup_version`、`stream_id`）使用领域特定前缀（如 `ver_`、`kb_`、`devstream_`），不遵循 `cx:<kind>:<uuid>` 格式。这些标识符的编码规则由各自所在章节定义。

字段默认规则：

- 未标记 optional 的字段为 required。
- `null` 只有在类型中明确写出时才允许。
- 实现 MUST 保留未知字段，但 MUST NOT 让未知字段绕过 capability、schema、policy 或加密约束。
- 签名和 hash 输入 MUST 使用 canonical JSON。
- `id:<kind>` 在 wire、canonical object、fixture、签名和跨服务引用中 MUST 使用完整 typed ID。数据库内部 MAY 只存 raw id，但在序列化、签名、hash、联邦、sync cursor 和审计回放前必须恢复 `cx:<kind>:` 前缀；不得把数据库主键或表名当作协议 ID 的替代品。
- 当 `id:<kind>` 出现在 JSON object key 中时，它仍然属于 wire value；例如 `messages.{principal_id}.{device_id}` 中的 `{device_id}` MUST 使用完整 `cx:device:<uuid>`，不得写成局部别名如 `dev_a` 或 `a`。

## 3. Common Object Fields

所有 durable canonical object SHOULD 使用以下公共字段，除非对象类型另有说明。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:*` | typed ID 前缀决定对象种类（`cx:flow:` 即 flow 对象，依此类推）。 | 对象稳定 ID；前缀就是 type，不再单独写 `type` 字段。 |
| `space_id` | conditional | `id:space` | Space 外对象可省略。 | 所属 Space。 |
| `schema` | yes | `string` | SHOULD 是 `cx.schema.*.vN` 或反向域名 schema id。 | 验证 schema id。 |
| `created_by` | conditional | `did` | 系统派生对象可由 `derived_from` 替代。 | 创建主体（创建该对象的 Event 的 `actor_id`）。 |
| `created_at` | yes | `timestamp` | 不能作为因果真相。 | 创建时间。 |
| `updated_by` | no | `did` | 更新时 SHOULD 设置。 | 最近更新主体。 |
| `updated_at` | no | `timestamp` | MUST 不早于 `created_at`。 | 最近更新时间。 |
| `deleted_at` | no | `timestamp` | durable tombstone 可用。 | 逻辑删除时间。 |
| `state_changed_at` | conditional | `timestamp` | **Reducer-derived,actor 不可信:** 所有具有 `state` 字段的对象（Flow / Place / Message / Morph / Relation）当 `state != active` 时 MUST 写入;reducer **MUST** 忽略任何 wire payload 中 actor-supplied 的 `state_changed_at` 值,以触发该 state transition 的 Event 的 `created_at`(或对应 anchor 的 `anchored_at`,以两者中较晚者为准)覆盖写入。MUST 不早于 `created_at`,MUST ≤ `updated_at`(当后者存在时)。 | 最近一次 state 转换时间。 |
| `labels` | no | `array<string>` | SHOULD 小写短标签。 | 用户或系统标签。 |
| `fields` | no | `object` | 字段 schema 由对象类型自身的 `schema_refs` 决定。 | 扩展字段；v1 唯一标准扩展容器。 |

对象种类由 `id` 的 typed prefix（`cx:flow:` / `cx:space:` / ...）唯一决定；扩展字段统一走 `fields`，由对象 `schema_refs` 约束。Event Envelope 不是 Materialized Object，事件类型由顶层 `kind` 表达。

## 4. 主体引用字段交叉对照

### 4.1 DID 适用边界

DID 是 Contrix 的主体标识，不是普通协作对象 ID。标准协作对象（Space / Place / Flow / Message / Morph / Relation / View / Policy / Grant / Invite / Blob 等）MUST 使用 `cx:<kind>:` typed ID 作为对象 ID；只有当字段表达 actor / principal / issuer / subject / service / device / controller / accountable party 时，才使用 DID 或 DID URL。

因此，"需要有 DID"的对象与结构按下表理解：

| 对象 / 结构 | 必须包含的 DID 字段 | 说明 |
| --- | --- | --- |
| Actor identity（user / org / team / agent / service / device / integration） | DID 本身 | Actor 的身份根就是 DID；若需要在协作图中展示，则用 Actor Profile 承载展示字段。 |
| Actor Profile (`cx:actor_profile:`) | `principal_id` | Profile 只是展示镜像；`principal_id` 才是授权、签名和审计归属的主体 DID。 |
| Event Envelope (`cx:event:`) | `actor_id`; Proof 中的 `verification_method` 为 DID URL | `actor_id` 是签署并提交事件的 actor DID，MUST 匹配 proof 控制链。 |
| Space (`cx:space:`) | `created_by_principal` | Space create event 的授权 principal；`owning_organizations[]` 可选使用组织 DID。 |
| Place / Flow / Message / Morph / Relation / View / Policy / Blob metadata | `created_by`; 更新时可有 `updated_by` | 这些对象自身不使用 DID 做 `id`；DID 只记录创建 / 更新主体。协作图对象的创建 / 更新主体由 reducer 从对应 Event 的 `actor_id` 派生；Blob metadata 的 `created_by` 来自 authenticated media 写入主体。 |
| Capability Grant (`cx:grant:`) | `issuer`; `subject` 为具体主体时必须是 DID | `subject` 也可以是条件 selector；handle、邮箱、域名用户名等不得作为权限主体主键。 |
| Invite (`cx:invite:`) | `inviter`; `invitee` 在直接 DID 邀请时使用 DID | 3PID 邀请可没有 `invitee`，但认领后必须绑定可验证主体。 |
| Read Marker / Notification | `actor_id` | actor-private 或派生对象，`actor_id` 表示该私有状态所属主体。 |
| Event Batch Receipt / Identity Receipt / Audit Receipt | `issuer` 或 schema 声明的签发 / 主体 DID 字段 | receipt 的签发、覆盖范围和验证必须回到可解析 DID。 |
| Relation endpoint | 当 endpoint 是 Actor 时，`from_ref` / `to_ref` 使用 DID | 指向普通对象时仍使用 `cx:<kind>:` typed ID；Relation 不把对象 ID 转换为 DID。 |

任何可签名、可被授予 capability、可作为审计责任主体或可被 Space / service policy allowlist 的实体，MUST 有可解析 DID。仅作为内容、容器、投影或关系事实存在的对象，不需要也不得发明独立 DID；它们通过 typed ID 被引用，通过 `created_by` / `updated_by` 等字段关联到 DID 主体。

### 4.2 主体引用字段

| 字段 | 出现对象 | 含义 |
| --- | --- | --- |
| `actor_id` | Event Envelope、Read Marker、Notification | 直接执行该 Event / 拥有该私有状态的 actor DID（`actor_kind` 决定它是 user / agent / service 等）。 |
| `principal_id` | Actor Profile | Profile 对应的 principal DID；权限根。 |
| `created_by` / `updated_by` | 所有 Materialized Object | 创建 / 最近更新该对象的 Event 的 `actor_id`，由 reducer 派生。 |
| `issuer` | Capability Grant、Identity Receipt | 签发授权或 receipt 的 DID；必须持有签发权限。 |
| `subject` | Capability Grant | 被授权 DID 或 selector condition。 |
| `inviter` / `invitee` | Invite | 邀请方 DID / 被邀请 DID。 |
| `created_by_principal` | Space | Space create event 的授权 principal（与该事件 `actor_id` 一致）。 |

这些不是同一字段的别名，每条都有独立语义角色；该表用于读 spec 时快速建立对应关系。

## 5. State 枚举对齐

各对象的 `state` 字段值不完全相同（部分名字承载了已稳定的 `cx.*.tombstone` event 命名约定），但在 reducer / projection 语义层等价于以下规范状态机：

| 规范状态 | 语义 | Flow | Place | Message | Morph | Relation | Space |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `active` | 当前可用 | `active` | `active` | `active` | `active` | `active` | `active` |
| `archived` | 软隐藏，UI 默认不展示，可撤销 | `archived` | `archived` | — | `archived` | — | `archived` |
| `redacted` | 内容已根据 redaction policy 清除，envelope 与审计元数据保留 | `redacted` | — | `redacted` | `redacted` | `tombstone`（合并 deleted+redacted） | — |
| `deleted` | 不可逆删除：content / encrypted_payload 清空，仅保留 envelope 用于审计 | `deleted` | `tombstoned` | `deleted` | `deleted` | `tombstone` | `tombstoned` |

约定：

- 写入路径 MUST 来自对应 reducer-input event（`cx.<kind>.archive` / `cx.<kind>.restore` / `cx.<kind>.tombstone` / `cx.<kind>.redact` 或等价命名）；不得直接 PATCH 对象顶层 state。`archived -> active` 是显式的可逆转换，由 `cx.<kind>.restore`（Flow、Place、Morph 均已注册对应 restore event）承担；`tombstoned` / `deleted` / `redacted` 是不可逆终态，MUST NOT 被 restore。
- `state != active` 时 MUST 写入 `state_changed_at`（见 §3 公共字段）。

#### 5.1 Canonical state-transition table

每个 reducer-input lifecycle event 都 MUST 校验**当前 state**(reducer 视角下的 pre-state)落在下表"合法源"集合内,否则 MUST 返回 `failed_precondition`,`reason` 取下表 `reason_code` 列。

| event family | 允许的源 state | 目标 state | `failed_precondition` reason_code |
| --- | --- | --- | --- |
| `cx.<kind>.archive` | `active` | `archived` | `<kind>_not_active` |
| `cx.<kind>.restore` | `archived` | `active` | `<kind>_not_archived` |
| `cx.<kind>.tombstone` | `active`、`archived` | `tombstoned` / `deleted`(各对象 schema 自命名) | `<kind>_already_terminal` |
| `cx.<kind>.redact` 或 cross-object `cx.redaction` 指向该对象 | `active`、`archived` | `redacted`(如对象支持),或合并到 `tombstoned` | `<kind>_already_terminal` |

`<kind>` 是 schema 类型短名(`flow`、`place`、`morph`、`message`),所有 reducer 实现 MUST 用相同 reason_code,使跨实现错误诊断一致。具体值如:`flow_not_active` / `flow_not_archived` / `flow_already_terminal`,`place_not_active` / `place_not_archived` / `place_already_terminal`,`morph_not_active` / `morph_not_archived` / `morph_already_terminal`。

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
| `cx.<kind>.create` | 创建对象,落 state=`active`,写入 `created_by` / `created_at`。 | `cx.flow.create`、`cx.place.create`、`cx.morph.create`、`cx.message.create` |
| `cx.<kind>.update` | 增量更新 active 对象字段;reducer 拒绝非 active 源。**新对象 SHOULD 沿用 `cx.patch.v1` 统一 patch 表达,不应再造单字段 update event。** | `cx.flow.update`、`cx.morph.update`、`cx.patch.v1`(unified) |
| `cx.<kind>.archive` | active → archived;写入 `state_changed_at`。 | `cx.flow.archive`、`cx.place.archive`、`cx.morph.archive` |
| `cx.<kind>.restore` | archived → active;写入 `state_changed_at`。 | `cx.flow.restore`、`cx.place.restore`、`cx.morph.restore` |
| `cx.<kind>.tombstone` 或 cross-object `cx.redaction` | active/archived → terminal(`tombstoned`/`deleted`);不可逆。当对象未单独注册 `cx.<kind>.tombstone` 时(例如 Flow),终态通过指向该对象的 `cx.redaction` 表达。 | `cx.place.tombstone`、`cx.morph.tombstone`、`cx.relation.delete`、`cx.redaction`(指向 flow / place / morph / message) |
| `cx.<kind>.redact` 或 cross-object `cx.redaction` | active/archived → `redacted`(若对象支持);envelope 保留,content 清空。v1 wire 实际注册形态请以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 为准:Message 走 `cx.message.redact`;Flow / Morph / Place / Relation 等未单独注册 `cx.<kind>.redact` 的对象走 cross-object `cx.redaction`。两种 wire 形态都是 canonical (`active` status),按对象选择;reducer 不得自行折叠或互换。 | `cx.message.redact`、`cx.redaction`(用于 flow / morph / place / relation 等未单独注册的对象) |

模板使用约束:

- **不是命名 mandate**,但 **MUST 与 registry 对齐**:模板槽列出的"已有实例"必须存在于 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中;`cx.message.create`(非历史草案中的 `cx.message.send`)是 v1 标准 wire kind。新对象在注册时按模板选择需要的槽,但**不得**列出 registry 中不存在的 wire kind 当作示例。
- **不创造新槽**:新增 lifecycle 行为(例如"软隔离 / 待审 / 撤回审核")MUST 先在本节扩展模板;否则不得作为标准 lifecycle event 入 registry。
- **patch 优先**:新对象 lifecycle 中的"字段更新"槽 SHOULD 由 `cx.patch.v1` 承载(参见 [`flow-and-message.md` §4.8](./flow-and-message.md) 的 `cx.flow.tracks.update` 实例);避免出现 `cx.<kind>.set_<field>` / `cx.<kind>.toggle_<field>` 这类单点 event 膨胀。
- **state 校验来源唯一**:本节所有模板事件的状态机校验入口都是 §5.1 表,不在各对象文档重复说明转换矩阵。
- "Place 没有 redacted"：Place 不承载用户 content（仅承载结构容器元数据），无需独立 redaction 状态；title / summary 的内容清理通过 `cx.place.tombstone` 或 `cx.redaction` 一并完成。
- "Message / Relation 没有 archived"：Message timeline 是有时序流，Relation 是边——两者都不需要"软隐藏可撤销"语义；要隐藏 Message 用 redaction，要解除 Relation 用删除即可。
- "Relation 用 `tombstone` 单一终态"：删除与 redaction 在边语义上不可区分（边只有"存在"或"不存在"），故合并为单一 `tombstone`；具体 reason 在对应 `cx.relation.delete` / `cx.redaction` event 中保留。
- Reducer 与 projection MUST 把 `tombstoned` / `tombstone` / `deleted` 视为语义等价的"不可逆删除"状态；UI 展示策略（隐藏 vs 显示 tombstone 占位符）由 client 根据对象类型决定。

## 6. 通用对象 ID 约定

对象 ID SHOULD 使用带类型前缀的稳定字符串：

```text
cx:space:<uuid>
cx:place:<uuid>
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
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
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
