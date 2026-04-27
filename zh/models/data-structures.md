# Data Structures

## 1. 目标

本文定义 Contrix 核心数据结构的字段级规范，包括字段名、是否必填、类型、取值约束和语义说明。

本文不替代具体业务章节。若某个字段在业务章节中有更严格规则，以更具体章节为准；若业务章节只给出示例，则以本文字段定义作为基础 schema contract。

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
| `id:<kind>` | `cx:<kind>:<ulid>` 或该 kind 的标准 ID string。 |
| `hash` | `sha256:<lowercase_hex_digest>`。 |
| `cursor` | `cx:cursor:<base64url>` opaque string。 |

字段默认规则：

- 未标记 optional 的字段为 required。
- `null` 只有在类型中明确写出时才允许。
- 实现 MUST 保留未知字段，但 MUST NOT 让未知字段绕过 capability、schema、policy 或加密约束。
- 签名和 hash 输入 MUST 使用 canonical JSON。

## 3. Common Object Fields

所有 durable canonical object SHOULD 使用以下公共字段，除非对象类型另有说明。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:*` | kind 必须匹配对象类型。 | 对象稳定 ID。 |
| `type` | yes | `enum(space, actor_profile, entity, relation, event, view, policy, invite, read_marker, notification, capability, commit, op, blob)` | 标准类型或 profile 声明的扩展类型。 | 对象种类。 |
| `space_id` | conditional | `id:space` | Space 外对象可省略。 | 所属 Space。 |
| `schema` | yes | `string` | SHOULD 是 `cx.schema.*.vN` 或反向域名 schema id。 | 验证 schema id。 |
| `created_by` | conditional | `did` | 系统派生对象可由 `derived_from` 替代。 | 创建主体。 |
| `created_at` | yes | `timestamp` | 不能作为因果真相。 | 创建时间。 |
| `updated_by` | no | `did` | 更新时 SHOULD 设置。 | 最近更新主体。 |
| `updated_at` | no | `timestamp` | MUST 不早于 `created_at`。 | 最近更新时间。 |
| `deleted_at` | no | `timestamp` | durable tombstone 可用。 | 逻辑删除时间。 |
| `labels` | no | `array<string>` | SHOULD 小写短标签。 | 用户或系统标签。 |
| `metadata` | no | `object` | 非授权关键字段。 | 扩展元数据。 |

## 4. Space

Schema id: `cx.schema.space.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:space` | 以 `cx:space:` 开头。 | Space ID。 |
| `type` | yes | `enum(space)` | 固定为 `space`。 | 对象种类。 |
| `space_version` | yes | `string` | 初版为 `1`。 | 事件授权和状态收敛版本。 |
| `title` | yes | `string` | 1..256 UTF-8 chars。 | 人类可读名称。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 简短说明。 |
| `space_kind` | yes | `enum(collaboration, direct, group, project, document, board, channel, social_feed, enclave)` | 自定义 kind SHOULD 放在 `fields`。 | Space 语义类别。 |
| `created_by_principal` | yes | `did` | 必须是 create event 授权主体。 | 创建 Principal。 |
| `owning_organizations` | no | `array<did>` | 每项必须可解析为 Organization Principal。 | 官方或治理组织。 |
| `schema_refs` | yes | `array<string>` | MUST 包含 `cx.schema.core.v1` 或兼容 profile。 | 启用 schema。 |
| `policy_ref` | no | `id:policy` | 若省略，使用 create event 默认 policy。 | Space policy 引用。 |
| `default_discoverability` | yes | `enum(public, listed, restricted, unlisted, invite_only, secret)` | 见 `discovery-directory.md`。 | 默认可发现性。 |
| `default_join_rule` | yes | `enum(public, invite, knock, restricted, knock_restricted, closed)` | 见 `event-auth-state-resolution.md`。 | 默认加入规则。 |
| `history_visibility` | yes | `enum(world_readable, shared, invited, joined, restricted)` | 加入后可见历史范围。 | 历史可见性。 |
| `encryption_profile` | yes | `enum(none, mls_rfc9420, external)` | E2EE Space SHOULD 使用 `mls_rfc9420`。 | 加密配置。 |
| `federation_policy` | no | `enum(open, restricted, closed, quarantine)` | sovereign 默认 SHOULD `closed`。 | 联邦策略。 |
| `retention_policy_ref` | no | `id:policy` | 可引用 retention policy。 | 保留策略。 |
| `avatar_blob_ref` | no | `id:blob` | 必须满足 media auth。 | 图标 Blob。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

## 5. Actor Profile

Schema id: `cx.schema.actor_profile.v1`

Actor Profile 是 Actor 在协作图中的展示镜像，不是权限主键。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:entity` | Actor Profile 作为 Entity 存储。 | Profile Entity ID。 |
| `type` | yes | `enum(actor_profile)` | 固定为 `actor_profile`。 | 对象种类。 |
| `space_id` | no | `id:space` | 全局 profile 可省略。 | 所属 Space。 |
| `principal_id` | yes | `did` | 权限仍以 DID/capability 为准。 | Principal DID。 |
| `actor_type` | yes | `enum(user, org, team, agent, service, device, integration)` |  | Actor 类型。 |
| `display_name` | yes | `string` | 1..128 chars。 | 展示名。 |
| `handle` | no | `string` | 必须通过 handle 双向验证后展示为 verified。 | 可读 handle。 |
| `avatar_blob_ref` | no | `id:blob` |  | 头像。 |
| `status` | no | `enum(active, suspended, deactivated, deleted)` | 账户生命周期见 `account-lifecycle.md`。 | 状态。 |
| `accountable_to` | no | `array<did>` | agent/托管账号 SHOULD 设置。 | 责任主体。 |
| `profile_fields` | no | `object` | 不得包含未授权披露的私密 handle。 | 扩展展示字段。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

## 6. Entity

Schema id: `cx.schema.entity.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:entity` | 以 `cx:entity:` 开头。 | Entity ID。 |
| `type` | yes | `enum(entity)` | 固定为 `entity`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `entity_type` | yes | `string` | 标准值见 `object-model-standard.md`，扩展不得使用未注册 `cx.` 前缀。 | 语义类型。 |
| `title` | no | `string` | SHOULD <= 512 chars。 | 标题。 |
| `content` | no | `object` | 富文本/blocks 见 `content-types.md`。 | 正文内容。 |
| `fields` | no | `object` | 字段 schema 由 `schema_refs` 决定。 | 自身属性。 |
| `state` | no | `enum(active, archived, deleted, redacted)` | 删除/撤回必须有事件来源。 | 物化状态。 |
| `version` | no | `integer` | SHOULD 单调递增，不能替代 event order。 | 物化版本。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

标准 `entity_type`：

```text
board, collection, task, message, topic, channel, document, file,
memory, run, actor_profile, poll, social_post, social_feed, social_circle
```

## 7. Relation

Schema id: `cx.schema.relation.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:relation` | 以 `cx:relation:` 开头。 | Relation ID。 |
| `type` | yes | `enum(relation)` | 固定为 `relation`。 | 对象种类。 |
| `space_id` | yes | `id:space` | Relation 所在 Space。 | 所属 Space。 |
| `relation_kind` | yes | `string` | 标准值见下方。 | 关系语义。 |
| `from_entity_id` | conditional | `id:entity` | `from_*` 必须恰好一个。 | 起点 Entity。 |
| `from_actor_id` | conditional | `did` | `from_*` 必须恰好一个。 | 起点 Actor。 |
| `from_space_id` | conditional | `id:space` | `from_*` 必须恰好一个。 | 起点 Space。 |
| `to_entity_id` | conditional | `id:entity` | `to_*` 必须恰好一个。 | 终点 Entity。 |
| `to_actor_id` | conditional | `did` | `to_*` 必须恰好一个。 | 终点 Actor。 |
| `to_space_id` | conditional | `id:space` | `to_*` 必须恰好一个。 | 终点 Space。 |
| `fields` | no | `object` | 可放 rank、role、edge metadata。 | 关系属性。 |
| `state` | no | `enum(active, deleted, redacted)` |  | 关系状态。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

标准 `relation_kind`：

```text
contains, belongs_to, replies_to, depends_on, blocks, mentions,
assigned_to, references, derived_from, attached_to, has_topic,
has_default_view, produced, used, triggered_by, has_log,
reposts, quotes
```

## 8. Event Envelope

Schema id: `cx.schema.event.v1`

Event 是 reducer 输入。它不是当前态对象。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `event_id` | yes | `id:event` 或 `hash` | 派生规则见 `encoding-conformance-vectors.md`。 | 事件 ID。 |
| `kind` | yes | `string` | 标准 event kind SHOULD 使用 `cx.` 前缀。 | 事件 kind。 |
| `space_id` | yes | `id:space` | Space create 可在 payload 中建立。 | 所属 Space。 |
| `space_version` | yes | `string` | 初版 `1`。 | 授权/状态版本。 |
| `actor_id` | yes | `did` | 必须匹配 proof 控制链。 | 发送 Actor。 |
| `actor_seq` | yes | `integer` | 同一 actor repo 内严格单调。 | Actor repo 序列。 |
| `created_at` | yes | `timestamp` | 不能单独决定因果。 | 创建时间。 |
| `hlc` | yes | `string` | `<unix_ms_hex>-<logical_hex>-<node_id_hash>`。 | HLC。 |
| `prev_refs` | yes | `array<id:event \| hash>` | 可为空。 | Actor repo 前序。 |
| `auth_refs` | yes | `array<id:event \| hash>` | create event 可为空。 | 授权依赖。 |
| `redacts` | no | `id:event` 或 `hash` | 仅 redaction event 使用。 | 被撤回事件。 |
| `content` | yes | `object` | 由 event kind schema 定义。 | 事件内容。 |
| `unsigned` | no | `object` | MUST NOT 进入 event digest。 | 本地/传输附加信息。 |
| `proofs` | yes | `array<Proof>` | 至少一个有效 proof。 | 签名证明。 |

## 9. Proof

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | yes | `enum(detached_jws)` | 初版必须支持。 | 证明类型。 |
| `alg` | yes | `string` | 初版默认 `EdDSA`。 | 签名算法。 |
| `verification_method` | yes | `string` | DID URL。 | 公钥/设备方法。 |
| `payload_hash` | yes | `hash` | 必须绑定 canonical payload。 | 被签名 payload hash。 |
| `created_at` | yes | `timestamp` |  | 签名时间。 |
| `domain` | no | `string` | 跨服务 SHOULD 设置。 | 域绑定。 |
| `audience` | no | `string` 或 `array<string>` | 跨域/服务调用 SHOULD 设置。 | 受众绑定。 |
| `jws` | yes | `string` | detached JWS。 | 签名值。 |

## 10. View

Schema id: `cx.schema.view.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:view` |  | View ID。 |
| `type` | yes | `enum(view)` | 固定为 `view`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `kind` | yes | `enum(kanban, list, table, calendar, gantt, chat, thread, forum, tree, graph, timeline, review_queue)` |  | 投影形态。 |
| `title` | no | `string` |  | View 名称。 |
| `query` | yes | `Query` | 见 `query-schema.md`。 | 数据查询。 |
| `visible_fields` | no | `array<string>` | dot path。 | 展示字段。 |
| `layout` | no | `object` | UI hint，不是权限。 | 布局配置。 |
| `kanban` | no | `KanbanConfig` | `kind="kanban"` 时 SHOULD 设置。 | 看板投影配置。 |
| `sort` | no | `array<SortSpec>` | 与 query sort 等价或补充。 | 排序。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

`KanbanConfig` 字段：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `column_model` | yes | `enum(field_value, collection)` |  | 列来源模型。 |
| `group_by` | conditional | `string` | `field_value` 模型必填，dot path。 | 分组字段，例如 `fields.status`。 |
| `columns` | conditional | `array<object>` | `field_value` 模型 SHOULD 设置。 | 字段值列定义。 |
| `board_entity_id` | conditional | `id:entity` | `collection` 模型必填。 | 看板 Entity。 |
| `column_relation_kind` | no | `string` | 默认 `contains`。 | board 到 column 的关系语义。 |
| `card_relation_kind` | no | `string` | 默认 `contains` 或 `belongs_to`。 | column/board 到 card 的关系语义。 |
| `card_order_by` | yes | `array<SortSpec>` | SHOULD 使用 `fields.rank` 或 Relation `fields.rank`。 | 卡片排序。 |
| `uncategorized_policy` | no | `enum(show, hide, reject)` | 默认 `show`。 | 未分类卡片处理。 |

`columns` item 字段：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `key` | yes | `string` | 必须匹配 `group_by` 字段值。 | 列 key。 |
| `title` | yes | `string` | 1..128 chars。 | 列标题。 |
| `rank` | no | `string` | Fractional rank。 | 列顺序。 |
| `wip_limit` | no | `integer` | >= 0。 | WIP 限制。 |

## 11. Policy

Schema id: `cx.schema.policy.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:policy` |  | Policy ID。 |
| `type` | yes | `enum(policy)` | 固定为 `policy`。 | 对象种类。 |
| `space_id` | no | `id:space` | 组织级 policy 可省略。 | 适用 Space。 |
| `policy_type` | yes | `enum(access, encryption, retention, federation, moderation, discoverability, join, history_visibility, plaintext_visibility, media, applet, agent, social)` |  | 策略类型。 |
| `rules` | yes | `array<object>` | 每条规则必须有 `effect`。 | 策略规则。 |
| `default_effect` | yes | `enum(allow, deny, quarantine, require_review)` |  | 默认效果。 |
| `priority` | no | `integer` | 数值大者优先。 | 策略优先级。 |
| `valid_from` | no | `timestamp` |  | 生效时间。 |
| `valid_until` | no | `timestamp` |  | 过期时间。 |
| `created_by` | yes | `did` | 必须有 policy/admin capability。 | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

## 12. Capability Grant

Schema id: `cx.schema.capability.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:grant` |  | Grant ID。 |
| `type` | yes | `enum(capability)` | 固定为 `capability`。 | 对象种类。 |
| `space_id` | no | `id:space` | 全局 grant 可省略但 SHOULD 避免。 | 作用域。 |
| `issuer` | yes | `did` | 必须持有授予权限。 | 授权方。 |
| `subject` | yes | `did` 或 `object` | 可为 DID 或 condition selector。 | 被授权主体。 |
| `actions` | yes | `array<string>` | 例如 `entity.update`。 | 允许动作。 |
| `resources` | yes | `array<object>` | 资源 selector。 | 资源范围。 |
| `constraints` | no | `array<object>` | 见 `grant-constraint-schema.md`。 | 约束条件。 |
| `delegable` | no | `boolean` | 默认 false。 | 是否可转授。 |
| `parent_grant_id` | no | `id:grant` | derived grant 必填。 | 父授权。 |
| `valid_from` | no | `timestamp` |  | 生效时间。 |
| `valid_until` | no | `timestamp` |  | 过期时间。 |
| `revoked_by` | no | `did` | 撤销后设置。 | 撤销者。 |
| `revoked_at` | no | `timestamp` |  | 撤销时间。 |
| `proofs` | yes | `array<Proof>` |  | 授权签名。 |

## 13. Invite

Schema id: `cx.schema.invite.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:invite` |  | Invite ID。 |
| `type` | yes | `enum(invite)` | 固定为 `invite`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 目标 Space。 |
| `inviter` | yes | `did` | 必须持有 invite capability。 | 邀请者。 |
| `invitee` | no | `did` | 3PID 邀请可为空。 | 被邀请 DID。 |
| `third_party_id` | no | `object` | 见 `third-party-invites.md`。 | 邮箱/手机号等外部标识证明。 |
| `join_rule_snapshot` | yes | `object` | 防止邀请后规则混淆。 | 邀请时 join rule。 |
| `capability_grant_refs` | no | `array<id:grant>` | 接受后才生效。 | 关联授权。 |
| `expires_at` | no | `timestamp` |  | 过期时间。 |
| `state` | yes | `enum(pending, accepted, rejected, revoked, expired)` |  | 邀请状态。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

## 14. Read Marker

Schema id: `cx.schema.read_marker.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `string` | SHOULD 派生自 actor + space/view。 | 私有状态 ID。 |
| `type` | yes | `enum(read_marker)` | 固定为 `read_marker`。 | 对象种类。 |
| `actor_id` | yes | `did` | 只对该 actor 生效。 | 读取主体。 |
| `space_id` | yes | `id:space` |  | Space。 |
| `scope` | yes | `enum(space, channel, topic, thread, view, entity)` |  | 已读范围。 |
| `scope_id` | no | `string` | scope 不是 space 时必填。 | 范围对象。 |
| `event_id` | yes | `id:event` 或 `hash` |  | 已读到的事件。 |
| `timeline_order_key` | no | `object` | 可加速比较。 | 已读排序键。 |
| `updated_at` | yes | `timestamp` |  | 更新时间。 |

## 15. Notification

Schema id: `cx.schema.notification.v1`

Notification 是派生 inbox projection，不是 canonical truth。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `string` | SHOULD content-addressed 或 stable derivation。 | 通知 ID。 |
| `type` | yes | `enum(notification)` | 固定为 `notification`。 | 对象种类。 |
| `actor_id` | yes | `did` | 接收者。 | 通知主体。 |
| `space_id` | no | `id:space` |  | 来源 Space。 |
| `source_event_id` | yes | `id:event` 或 `hash` |  | 来源事件。 |
| `notification_type` | yes | `enum(mention, reply, assignment, invite, reaction, policy, call, applet, agent, moderation, system)` |  | 通知类型。 |
| `priority` | yes | `enum(low, normal, high, urgent)` |  | 优先级。 |
| `state` | yes | `enum(unread, read, dismissed, archived)` |  | 通知状态。 |
| `preview` | no | `object` | E2EE 场景必须脱敏。 | 展示摘要。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

## 16. Repo Commit

Schema id: `cx.schema.commit.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `commit_id` | yes | `id:commit` |  | Commit ID。 |
| `type` | yes | `enum(commit)` | 固定为 `commit`。 | 对象种类。 |
| `repo_id` | yes | `did` 或 `id:space` | Actor repo 或 Space repo。 | Repo ID。 |
| `author` | yes | `did` | 必须控制签名 key。 | 作者。 |
| `author_seq` | yes | `integer` | repo 内严格单调。 | 作者序列。 |
| `prev_commit` | no | `hash` | genesis commit 可空。 | 前一 commit hash。 |
| `ops` | yes | `array<hash>` | 数组顺序参与 hash。 | op hash 列表。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `proofs` | yes | `array<Proof>` |  | Commit proof。 |

## 17. Operation

Schema id: `cx.schema.op.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `op_id` | yes | `id:op` 或 `hash` |  | Operation ID。 |
| `type` | yes | `enum(op)` | 固定为 `op`。 | 对象种类。 |
| `op_type` | yes | `enum(create, update, delete, redact, grant, revoke, snapshot_ref)` |  | 操作类型。 |
| `space_id` | yes | `id:space` |  | 目标 Space。 |
| `object_id` | no | `string` | create 可由 payload 指定。 | 目标对象。 |
| `object_type` | yes | `string` | `entity`、`relation` 等。 | 目标对象类型。 |
| `payload` | yes | `object` | 由 op_type 决定。 | 操作内容。 |
| `idempotency_key` | no | `string` | 重试写入 SHOULD 设置。 | 幂等键。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

## 18. Blob Metadata

Schema id: `cx.schema.blob.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `blob_ref` | yes | `id:blob` | SHOULD 包含 content hash。 | Blob 引用。 |
| `type` | yes | `enum(blob)` | 固定为 `blob`。 | 对象种类。 |
| `sha256` | yes | `string` | lowercase hex。 | 内容 hash。 |
| `size` | yes | `integer` | >= 0。 | 字节数。 |
| `media_type` | yes | `string` | MIME type。 | 媒体类型。 |
| `filename` | no | `string` | 展示用，不参与安全判断。 | 文件名。 |
| `encryption` | no | `object` | 见 `media-and-blob.md`。 | 附件加密 envelope。 |
| `thumbnail_ref` | no | `id:blob` |  | 缩略图。 |
| `created_by` | yes | `did` |  | 上传者。 |
| `created_at` | yes | `timestamp` |  | 上传时间。 |

## 19. MLS Encrypted Payload Envelope

Schema id: `cx.schema.encrypted_payload.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `scheme` | yes | `enum(mls-rfc9420)` | 初版 E2EE profile。 | 加密方案。 |
| `group_id` | yes | `string` | MLS group id。 | MLS 群组。 |
| `epoch` | yes | `integer` | >= 0。 | MLS epoch。 |
| `content_type` | yes | `string` | 明文类型提示。 | 解密后内容类型。 |
| `ciphertext` | yes | `string` | base64url。 | 密文。 |
| `aad` | no | `object` | MUST 进入 envelope digest。 | 附加认证数据。 |
| `payload_digest` | yes | `hash` | 见 `encoding-conformance-vectors.md`。 | 密文 envelope digest。 |
| `key_ref` | no | `string` | 不得泄露 secret。 | 密钥引用。 |

## 20. Client Sync Response

Schema id: `cx.schema.client_sync_response.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `next_batch` | yes | `cursor` 或 `string` | opaque。 | 下一次 sync token。 |
| `rooms` | no | `map<SyncSpace>` | key 为 `space_id`。 | Space 增量。 |
| `to_device` | no | `array<object>` | E2EE / device channel。 | 设备消息。 |
| `device_lists` | no | `object` | 设备变更。 | 设备列表增量。 |
| `account_data` | no | `array<object>` | 私有账号数据。 | 私有状态。 |
| `presence` | no | `array<object>` | 可选临场状态。 | Presence。 |
| `partial` | no | `boolean` | true 表示仍有未加载状态。 | 部分同步。 |

`SyncSpace` 字段：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `timeline` | no | `object` | 见下方。 | timeline 增量。 |
| `state` | no | `array<Event>` |  | 状态事件。 |
| `summary` | no | `object` |  | Space 摘要。 |
| `ephemeral` | no | `array<object>` | 不进 durable log。 | typing 等短暂事件。 |
| `unread` | no | `object` | 派生状态。 | 未读摘要。 |

`timeline` 字段：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `events` | yes | `array<Event>` | MUST 按 timeline order。 | 事件列表。 |
| `limited` | yes | `boolean` | true 表示存在 gap。 | 是否截断。 |
| `prev_batch` | no | `cursor` 或 `string` | opaque。 | 反向 backfill token。 |

## 21. 最小 JSON Schema 生成规则

机器可验证 JSON Schema SHOULD 从本文表格生成，并遵守：

- `required` 来自“必填”列。
- `type` 来自“类型”列。
- `enum` 来自 `enum(...)`。
- `pattern` 用于 DID、ID、hash、cursor、timestamp。
- `additionalProperties` SHOULD 默认为 `true`，但未知字段仍必须通过 policy 和 schema evolution 规则处理。
- 对安全关键 envelope，JSON Schema 只做结构检查；签名、hash、capability、MLS transcript 和 DID 控制链必须由协议验证器执行。
