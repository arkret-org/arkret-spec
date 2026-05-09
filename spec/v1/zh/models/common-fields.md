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
| `state_changed_at` | conditional | `timestamp` | 所有具有 `state` 字段的对象（Flow / Place / Message / Morph / Relation）当 `state != active` 时 MUST 写入；reducer 派生为对应 state-transition Event 的 `created_at`。MUST 不早于 `created_at`，MUST ≤ `updated_at`（当后者存在时）。 | 最近一次 state 转换时间。 |
| `labels` | no | `array<string>` | SHOULD 小写短标签。 | 用户或系统标签。 |
| `fields` | no | `object` | 字段 schema 由对象类型自身的 `schema_refs` 决定。 | 扩展字段；v1 唯一标准扩展容器。 |

对象种类由 `id` 的 typed prefix（`cx:flow:` / `cx:space:` / ...）唯一决定；扩展字段统一走 `fields`，由对象 `schema_refs` 约束。Event Envelope 不是 Materialized Object，事件类型由顶层 `kind` 表达。

## 4. 主体引用字段交叉对照

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

- 写入路径 MUST 来自对应 reducer-input event（`cx.<kind>.archive` / `cx.<kind>.tombstone` / `cx.<kind>.redact` 或等价命名）；不得直接 PATCH 对象顶层 state。
- `state != active` 时 MUST 写入 `state_changed_at`（见 §3 公共字段）。
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

Reducer MUST：

- 验证签名
- 验证 schema
- 验证 capability
- 按 causal order 处理
- 对相同 Operation 保持幂等
- 保留未知字段
- 输出可声明的 reducer profile

Reducer MUST 拒绝任何 signature、schema、capability 或 causal 校验失败的事件。具体 Move / Anchor / Lattice / state resolution 细节见 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。

## 8. 规范性引用

- 完整 ID kind registry：`artifacts/registry/id-kind-registry.json`。
- Schema registry：`artifacts/registry/schema-registry.json` 与 [`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- Canonical JSON、hash、签名、cursor、HLC、rank 编码：[`../conformance/encoding.md`](../conformance/encoding.md)。
- Reducer conformance vector：[`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md)。
