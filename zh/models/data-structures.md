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
| `id:<kind>` | `cx:<kind>:<ulid>` typed ID，或该 kind 在 `id-kind-registry.json` 声明的特殊 wire form。 |
| `hash` | `sha256:<lowercase_hex_digest>`。 |
| `cursor` | `cx:cursor:<base64url>` opaque string。 |

字段默认规则：

- 未标记 optional 的字段为 required。
- `null` 只有在类型中明确写出时才允许。
- 实现 MUST 保留未知字段，但 MUST NOT 让未知字段绕过 capability、schema、policy 或加密约束。
- 签名和 hash 输入 MUST 使用 canonical JSON。
- `id:<kind>` 在 wire、canonical object、fixture、签名和跨服务引用中 MUST 使用完整 typed ID。数据库内部 MAY 只存 raw id，但在序列化、签名、hash、联邦、sync cursor 和审计回放前必须恢复 `cx:<kind>:` 前缀；不得把数据库主键或表名当作协议 ID 的替代品。

## 3. Common Object Fields

所有 durable canonical object SHOULD 使用以下公共字段，除非对象类型另有说明。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:*` | kind 必须匹配对象类型。 | 对象稳定 ID。 |
| `type` | yes | `enum(space, actor_profile, room, board, list, card, message, morph, relation, event, view, policy, invite, read_marker, notification, capability, operation, event_batch_receipt, blob)` | 标准类型或 profile 声明的扩展类型。 | 对象种类。 |
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
| `space_kind` | yes | `enum(collaboration, personal, project, organization, social_feed, enclave)` | Room / Board / Card 不再作为 Space kind。自定义 kind SHOULD 放在 `fields`。 | Space 语义类别。 |
| `created_by_principal` | yes | `did` | 必须是 create event 授权主体。 | 创建 Principal。 |
| `owning_organizations` | no | `array<did>` | 每项必须可解析为 Organization Principal。 | 官方或治理组织。 |
| `schema_refs` | yes | `array<string>` | MUST 包含 `cx.schema.core.v1` 或兼容 profile。 | 启用 schema。 |
| `policy_ref` | no | `id:policy` | 若省略，使用 create event 默认 policy。 | Space policy 引用。 |
| `default_discoverability` | yes | `enum(public, listed, restricted, unlisted, invite_only, secret)` | 见 `discovery-directory.md`。 | 默认可发现性。 |
| `default_join_rule` | yes | `enum(public, invite, knock, restricted, knock_restricted, closed)` | `invite` 表示只允许邀请加入；旧草案中的 `private` MUST 映射为 `invite` 后再进入 v1 canonical state。 | 默认加入规则。 |
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
| `id` | yes | `id:actor_profile` | Actor Profile 是标准对象，不作为 Morph/Entity 存储。 | Profile 对象 ID。 |
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

## 6. Standard Objects

Room、Board、List、Card 和 Message 是标准对象，不再通过 `entity_type` 表达。

### 6.1 Room

Schema id: `cx.schema.room.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:room` | 以 `cx:room:` 开头。 | Room ID。 |
| `type` | yes | `enum(room)` | 固定为 `room`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `title` | yes | `string` | 1..256 chars。 | 名称。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 简介 / 公告。 |
| `room_kind` | yes | `enum(discussion, announcement, support, activity, review, external)` | 自定义 kind 放入 `fields`。 | Room 类型。 |
| `membership_policy_ref` | no | `id:policy` | Room 独立 membership / access policy。 | 成员策略。 |
| `history_visibility` | yes | `enum(world_readable, shared, invited, joined, restricted)` | 见 `conversation-model.md`。 | 历史可见性。 |
| `encryption_profile` | no | `enum(none, mls_rfc9420, external)` | 可与 Space 不同，但必须被 Space policy 允许。 | 加密配置。 |
| `fields` | no | `object` |  | 扩展字段。 |
| `state` | no | `enum(active, archived, deleted)` |  | 状态。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

### 6.2 Board

Schema id: `cx.schema.board.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:board` | 以 `cx:board:` 开头。 | Board ID。 |
| `type` | yes | `enum(board)` | 固定为 `board`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `title` | yes | `string` | 1..256 chars。 | 名称。 |
| `summary` | no | `string` |  | 说明。 |
| `board_kind` | yes | `enum(kanban, scrum, review_queue, intake, custom)` |  | Board 类型。 |
| `default_view_id` | no | `id:view` |  | 默认 View。 |
| `fields` | no | `object` |  | 扩展字段。 |
| `state` | no | `enum(active, archived, deleted)` |  | 状态。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

### 6.3 List

Schema id: `cx.schema.list.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:list` | 以 `cx:list:` 开头。 | List ID。 |
| `type` | yes | `enum(list)` | 固定为 `list`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `board_id` | no | `id:board` | 仅作为创建/投影提示；canonical containment 由 `board --contains--> list` Relation 表达。 | 所属 Board。 |
| `title` | yes | `string` | 1..256 chars。 | 名称。 |
| `summary` | no | `string` |  | 说明。 |
| `rank` | no | `string` | Fractional indexing rank；Board 内 canonical rank SHOULD 放在 contains Relation fields。 | Board 内顺序。 |
| `wip_limit` | no | `integer` |  | WIP 限制。 |
| `fields` | no | `object` |  | 扩展字段。 |
| `state` | no | `enum(active, archived, deleted)` |  | 状态。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

### 6.4 Card

Schema id: `cx.schema.card.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:card` | 以 `cx:card:` 开头。 | Card ID。 |
| `type` | yes | `enum(card)` | 固定为 `card`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `title` | yes | `string` | 1..512 chars。 | 标题。 |
| `body` | no | `object` | 富文本/blocks 见 `content-types.md`。 | 内容。 |
| `fields` | no | `object` | 字段 schema 由 `schema_refs` 决定。 | 状态、优先级、截止时间等属性。 |
| `facets` | no | `map<FacetConfig>` | 标准 facet 见 7 节。 | 已声明能力的可选 hint / 查询标签。 |
| `state` | no | `enum(active, archived, deleted, redacted)` | 删除/撤回必须有事件来源。 | 物化状态。 |
| `version` | no | `integer` | SHOULD 单调递增，不能替代 event order。 | 物化版本。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

Card canonical object 不包含 `board_id` 或 `list_id` 必填字段。Card 在 Board/List 中的主位置由 active `contains` Relation / position edge 归约得到；Index 或 View projection MAY 返回派生的 `board_id`、`list_id` 和 `rank` 方便客户端渲染，但这些派生字段不得成为签名 Card 对象的唯一真相源。

### 6.5 Message

Schema id: `cx.schema.message.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:message` | 以 `cx:message:` 开头。 | Message ID。 |
| `type` | yes | `enum(message)` | 固定为 `message`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `room_id` | yes | `id:room` |  | 所属 Room。 |
| `content` | yes | `object` | 富文本/blocks 见 `content-types.md`。 | 消息正文。 |
| `fields` | no | `object` | 可放 revision、visibility、client metadata。 | 扩展字段。 |
| `created_by` | yes | `did` |  | 发送者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

## 7. Morph and Facets

Schema id: `cx.schema.morph.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:morph` | 以 `cx:morph:` 开头。 | Morph ID。 |
| `type` | yes | `enum(morph)` | 固定为 `morph`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `morph_type` | yes | `string` | 标准值见业务 profile，扩展不得使用未注册 `cx.` 前缀。 | 开放类型。 |
| `facets` | no | `map<FacetConfig>` | 未知 facet 必须由 Space schema / Morph profile 声明。 | Morph 暴露哪些已声明能力 hint。 |
| `title` | no | `string` | SHOULD <= 512 chars。 | 标题。 |
| `summary` | no | `string` |  | 摘要。 |
| `content` | no | `object` | 富文本/blocks 见 `content-types.md`。 | 正文内容。 |
| `fields` | no | `object` | 字段 schema 由 `schema_refs` 决定。 | 自身属性。 |
| `state` | no | `enum(active, archived, deleted, redacted)` | 删除/撤回必须有事件来源。 | 物化状态。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

标准 `facets` 名称作为 schema/profile 声明后的 hint / 查询标签使用：

| Facet | 说明 | 典型字段/关系 |
| --- | --- | --- |
| `container` | 提示对象可按显式 relation/profile 作为容器投影。 | `child_object_types`, `relation_kinds`, `ordering`, `exclusive_scope`。 |
| `replyable` | 提示对象可按声明的 reply relation 被回复，形成 thread/discussion。 | `reply_object_types`, `reply_relation_kind`, `time_field`, `redaction_policy`。 |
| `schedulable` | 提示对象有声明的时间窗口，可进入 calendar/gantt 投影。 | `start_field`, `end_field`, `timezone_field`, `dependency_relation_kinds`。 |
| `assignable` | 提示对象有声明的分配字段或关系。 | `assignee_relation_kind` 或 `assignee_field`。 |
| `stateful` | 提示对象有显式 profile 定义的受控状态机。 | `state_field`, `states`, `transition_policy`。 |
| `rankable` | 提示对象有声明的稳定手动排序 rank。 | `rank_field`, `rank_profile`, `collision_policy`。 |
| `reviewable` | 提示对象有声明的审核/审阅状态。 | `review_state_field`, `reviewer_relation_kind`, `priority_field`。 |
| `notifiable` | 提示对象可按声明的 notification profile 派生 notification/inbox/read state。 | `notification_types`, `read_state_policy`。 |
| `documentable` | 提示对象可按声明的 document profile 作为文档或 section root。 | `section_relation_kind`, `section_order_field`, `body_field`。 |
| `renderable` | 提示对象声明允许的默认展示面。 | `renderers`, `title_field`, `summary_field`, `media_field`。 |

`query.facets`、`collection.item_facets` 和 `graph.node_facets` 的数组语义为 AND：候选对象 MUST 同时具备列出的全部 facet。`container.child_facets` 与 `replyable.reply_facets` 使用 `{all?, any?, none?}` 选择器。

Facet 配置 MUST NOT 成为授权、状态机、排序语义、reducer 行为、event kind 接受规则或 wire 互操作的唯一规范来源。这些语义必须由 Space schema / Morph profile / event registry / capability action 明确定义。

## 8. Relation

Schema id: `cx.schema.relation.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:relation` | 以 `cx:relation:` 开头。 | Relation ID。 |
| `type` | yes | `enum(relation)` | 固定为 `relation`。 | 对象种类。 |
| `space_id` | yes | `id:space` | Relation 所在 Space。 | 所属 Space。 |
| `relation_kind` | yes | `string` | 标准值见下方。 | 关系语义。 |
| `from_ref` | yes | `string` | MUST 是 `cx:<kind>:...` 或 DID。 | 起点对象/Actor/Space 引用。 |
| `to_ref` | yes | `string` | MUST 是 `cx:<kind>:...` 或 DID。 | 终点对象/Actor/Space 引用。 |
| `fields` | no | `object` | 可放 rank、role、edge metadata。 | 关系属性。 |
| `state` | no | `enum(active, deleted, redacted)` |  | 关系状态。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

标准 `relation_kind`：

```text
contains, belongs_to, replies_to, depends_on, blocks, mentions,
assigned_to, references, derived_from, attached_to, links_room,
primary_room, has_default_view, produced, used, triggered_by, has_log,
summarized_from, promoted_from_room,
reposts, quotes,
follows, contact, circle_member, blocks_social, likes
```

## 9. Event Envelope

Schema id: `cx.schema.event.v1`

Event 是 reducer 输入。它不是当前态对象。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `event_id` | yes | `id:event` | 事件稳定 typed ID。事件 canonical digest / proof hash 见 `encoding-conformance-vectors.md`。 | 事件 ID。 |
| `kind` | yes | `string` | 标准 event kind SHOULD 使用 `cx.` 前缀。 | 事件 kind。 |
| `space_id` | yes | `id:space` | Space create 可在 payload 中建立。 | 所属 Space。 |
| `space_version` | yes | `string` | 初版 `1`。 | 授权/状态版本。 |
| `actor_id` | yes | `did` | 必须匹配 proof 控制链。 | 发送 Actor。 |
| `actor_seq` | yes | `integer` | 同一 actor event chain 内严格单调。 | Actor 发布序列。 |
| `created_at` | yes | `timestamp` | 不能单独决定因果。 | 创建时间。 |
| `hlc` | yes | `string` | `<unix_ms_hex>-<logical_hex>-<node_id_hash>`。 | HLC。 |
| `prev_refs` | yes | `array<id:event>` | 可为空。 | Actor event chain 前序。 |
| `auth_refs` | yes | `array<id:event>` | create event 可为空；必须引用授权状态事件，不能直接引用 grant / policy object ID。 | 授权依赖。 |
| `schema_profile_refs` | no | `array<string>` | MUST 进入 event digest。 | 事件声明依赖的 schema profile。 |
| `reducer_profile_ref` | no | `string` | MUST 进入 event digest。 | 事件声明依赖的 reducer profile。 |
| `required_features` | no | `array<string>` | 未支持时 MUST fail closed。 | 事件依赖的 feature/profile。 |
| `critical_extensions` | no | `array<object>` | 每项必须有 `id`、`scope`、`fail_closed=true`。 | 事件内 critical extension 声明。 |
| `redacts` | no | `id:event` 或 `hash` | 仅 redaction event 使用。 | 被撤回事件。 |
| `content` | yes | `object` | 由 event kind schema 定义。 | 事件内容。 |
| `unsigned` | no | `object` | MUST NOT 进入 event digest。 | 本地/传输附加信息。 |
| `proofs` | yes | `array<Proof>` | 至少一个有效 proof。 | 签名证明。 |

## 10. Proof

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

## 11. View

Schema id: `cx.schema.view.v1`

View 是投影定义对象。它的 canonical state 只覆盖“如何看”：query、kind、renderer、typed config、visible fields、layout 和共享配置。它不得作为被投影对象的状态、位置、关系、权限或消息历史的唯一来源。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:view` |  | View ID。 |
| `type` | yes | `enum(view)` | 固定为 `view`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `kind` | yes | `enum(collection, timeline, graph, document, composite)` |  | 核心投影原语。 |
| `renderer` | no | `enum(board, card, row, table, calendar, gantt, timeline, thread, chat, forum, graph, tree, document, dashboard, custom)` | 不参与真相归约。 | 展示面提示；交互能力仍由对象类型、显式 schema/profile、capability 与 typed config 决定。 |
| `title` | no | `string` |  | View 名称。 |
| `query` | yes | `Query` | 见 `query-schema.md`。 | 数据查询。 |
| `visible_fields` | no | `array<string>` | dot path。 | 展示字段。 |
| `layout` | no | `object` | UI hint，不是权限。 | 布局配置。 |
| `collection` | conditional | `CollectionConfig` | `kind="collection"` 时 MUST 设置。 | 集合投影配置；看板、表格、日历、甘特、队列、矩阵都由该配置表达。 |
| `timeline` | conditional | `TimelineConfig` | `kind="timeline"` 时 MUST 设置。 | 时间线配置。 |
| `conversation` | conditional | `ConversationConfig` | 会话/讨论类 renderer SHOULD 设置，或 query 必须提供 anchor/relation。 | 会话配置。 |
| `graph` | conditional | `GraphConfig` | `kind="graph"` 时 MUST 设置。 | 图/树遍历配置。 |
| `document` | conditional | `DocumentConfig` | `kind="document"` 时 MUST 设置。 | 文档 section 配置。 |
| `dashboard` | conditional | `DashboardConfig` | `kind="composite"` 时 MUST 设置。 | 仪表盘 widget 配置。 |
| `sort` | no | `array<SortSpec>` | 与 query sort 等价或补充。 | 排序。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

若某个 UI 操作改变 Card 所属 List、Card rank、List rank、Room message、Relation 或对象字段，必须使用对应对象 Event；只有改变共享 filter、sort、grouping、visible fields、renderer 或 layout 时才修改 View。个人偏好、临时排序、列宽、折叠状态和本地 pin MUST 使用 actor-private account data 或等价私有 Event。

`CollectionConfig` 字段：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `item_object_types` | conditional | `array<string>` | 可由 `item_facets` 替代；至少 1 项。 | 按对象类型过滤可投影为 item/card/row/message 的对象。 |
| `item_facets` | conditional | `array<FacetName>` | 可替代 `item_object_types`；至少 1 项。 | 按声明 hint 选择 item，例如 `rankable`、`reviewable`、`replyable`。 |
| `item_render` | yes | `enum(card, row, tile, compact, badge, message)` | 看板式展示 SHOULD 为 `card`。 | 默认展示面。 |
| `item_order_by` | yes | `array<SortSpec>` | 至少 1 项。 | item 稳定排序；拖拽类 collection SHOULD 使用 rank。 |
| `display_fields` | no | `array<DisplayColumn>` | dot path。 | 展示字段与格式。 |
| `grouping` | yes | `CollectionGrouping` |  | 分组/列/时间桶/矩阵配置。 |
| `selection_policy` | no | `enum(none, single, multiple)` | 默认 `multiple`。 | UI 选择策略。 |
| `count_policy` | no | `enum(omit, authorized_estimate, authorized_exact)` | 默认 `omit`。 | 集合级计数策略。 |
| `page_size` | no | `integer` | 1..1000。 | 默认分页大小。 |

`CollectionGrouping` 字段：

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | yes | `enum(none, field, relation_container, time_bucket, matrix)` |  | 分组模型。 |
| `field` | conditional | `string` | `mode="field"` 时必填。 | 字段分组路径。 |
| `lanes` | conditional | `array<object>` | `mode="field"` 时必填。 | 字段值列/泳道定义。 |
| `board_id` | conditional | `id:board` | `mode="relation_container"` 时必填。 | Board。 |
| `container_relation_kind` | no | `string` | 默认 `contains`。 | root 到 collection/container 的关系。 |
| `item_relation_kind` | conditional | `string` | `mode="relation_container"` 时必填；不得隐式推断。 | container 到 item 的关系。 |
| `start_field` | conditional | `string` | `mode="time_bucket"` 时必填。 | 时间窗口起点字段。 |
| `end_field` | no | `string` |  | 时间窗口终点字段。 |
| `rows_by` / `columns_by` | conditional | `string` | `mode="matrix"` 时必填。 | 矩阵双轴字段。 |
| `hidden_count_policy` | no | `enum(omit, authorized_estimate, authorized_exact)` | 默认 `omit`。 | 分组计数授权策略。 |
| `wip_limit_enforcement` | no | `enum(warn, reject, require_review)` | 默认 `warn`。 | 分组 WIP enforcement；只影响 reducer / review policy，不由 renderer 决定。 |

## 12. Policy

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

## 13. Capability Grant

Schema id: `cx.schema.capability.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:grant` |  | Grant ID。 |
| `type` | yes | `enum(capability)` | 固定为 `capability`。 | 对象种类。 |
| `space_id` | no | `id:space` | 全局 grant 可省略但 SHOULD 避免。 | 作用域。 |
| `issuer` | yes | `did` | 必须持有授予权限。 | 授权方。 |
| `subject` | yes | `did` 或 `object` | 可为 DID 或 condition selector。 | 被授权主体。 |
| `actions` | yes | `array<string>` | 例如 `cx.card.update`、`cx.message.create`。 | 允许动作。 |
| `resources` | yes | `array<object>` | 资源 selector。 | 资源范围。 |
| `constraints` | no | `array<object>` | 见 `grant-constraint-schema.md`。 | 约束条件。 |
| `delegable` | no | `boolean` | 默认 false。 | 是否可转授。 |
| `parent_grant_id` | no | `id:grant` | derived grant 必填。 | 父授权。 |
| `valid_from` | no | `timestamp` |  | 生效时间。 |
| `valid_until` | no | `timestamp` |  | 过期时间。 |
| `revoked_by` | no | `did` | 撤销后设置。 | 撤销者。 |
| `revoked_at` | no | `timestamp` |  | 撤销时间。 |
| `proofs` | yes | `array<Proof>` |  | 授权签名。 |

## 14. Invite

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

## 15. Read Marker

Schema id: `cx.schema.read_marker.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `string` | SHOULD 派生自 actor + space/view。 | 私有状态 ID。 |
| `type` | yes | `enum(read_marker)` | 固定为 `read_marker`。 | 对象种类。 |
| `actor_id` | yes | `did` | 只对该 actor 生效。 | 读取主体。 |
| `space_id` | yes | `id:space` |  | Space。 |
| `scope` | yes | `enum(space, room, thread, view, card, message, morph)` |  | 已读范围。 |
| `scope_id` | no | `string` | scope 不是 space 时必填。 | 范围对象。 |
| `event_id` | yes | `id:event` |  | 已读到的事件。 |
| `timeline_order_key` | no | `object` | 可加速比较。 | 已读排序键。 |
| `updated_at` | yes | `timestamp` |  | 更新时间。 |

## 16. Notification

Schema id: `cx.schema.notification.v1`

Notification 是派生 inbox projection，不是 canonical truth。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `string` | SHOULD content-addressed 或 stable derivation。 | 通知 ID。 |
| `type` | yes | `enum(notification)` | 固定为 `notification`。 | 对象种类。 |
| `actor_id` | yes | `did` | 接收者。 | 通知主体。 |
| `space_id` | no | `id:space` |  | 来源 Space。 |
| `source_event_id` | yes | `id:event` |  | 来源事件。 |
| `notification_type` | yes | `enum(mention, reply, assignment, invite, reaction, policy, call, applet, agent, moderation, system)` |  | 通知类型。 |
| `priority` | yes | `enum(low, normal, high, urgent)` |  | 优先级。 |
| `state` | yes | `enum(unread, read, dismissed, archived)` |  | 通知状态。 |
| `preview` | no | `object` | E2EE 场景必须脱敏。 | 展示摘要。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

## 17. Event Batch Receipt

Schema id: `cx.schema.event_batch_receipt.v1`

Event Batch Receipt 是可选审计/同步加速对象，不是 canonical history，也不是 reducer input。缺少 receipt 不得导致格式、签名、授权和因果均有效的 Event 被拒绝，除非 deployment profile 额外要求 witness。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `receipt_id` | yes | `id:receipt` |  | Receipt ID。 |
| `type` | yes | `enum(event_batch_receipt)` | 固定为 `event_batch_receipt`。 | 对象种类。 |
| `issuer` | yes | `did` | 必须控制签名 key。 | 签发者，可以是 principal、Principal Server 或 witness。 |
| `scope` | yes | `object` | SHOULD 包含 `actor_id`、`space_id` 或查询范围 hash。 | receipt 覆盖范围。 |
| `frontier` | yes | `object` | SHOULD 包含 `actor_seq`、`event_id` / event hash、HLC 或 Space frontier。 | 签发时前沿。 |
| `events` | yes | `array<id:event \| hash>` | 数组顺序参与 hash。 | 被 receipt 覆盖的 Event Envelope 引用。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `proofs` | yes | `array<Proof>` |  | Receipt proof。 |

## 18. Canonical Operation Object

Schema id: `cx.schema.operation.v1`

本节定义 SDK 内部可内容寻址的 canonical Operation object。它使用固定 `type="operation"` 与独立的 `operation_type`，适合作为 builder 输出、离线草稿或 Event Envelope 生成前的中间对象。

v1 的规范性 wire fact 是 **Event Envelope**，见第 9 节和 `../sync/operations-sync.md`。Events API、Sync、Federation、Client write 和 reducer MUST 使用 Event Envelope，不得要求对端直接接收本节的 Canonical Operation Object。实现可以用 Canonical Operation Object 生成 Event Envelope，但不得把两者合并成一个含糊结构。

三层边界：

| 层 | 用途 | 是否 wire format | 是否 reducer input |
| --- | --- | --- | --- |
| Canonical Operation Object | SDK builder 输出、离线草稿或本地内容寻址对象。 | 否，除非 profile 明确声明私有传输。 | 否，必须先包入 Event Envelope。 |
| Event Envelope | Events API、Sync、Federation、Client write 的签名承载，也是唯一规范事实。 | 是。 | 是，reducer 读取其 `kind`、`content`、`auth_refs`、`prev_refs`、proof 和 causal metadata。 |
| Materialized Object | reducer 输出的当前态对象，例如 Card、Relation、View。 | 否。 | 否，不能反向替代事件历史。 |

字段映射：

| Canonical Operation | Event Envelope |
| --- | --- |
| `operation_id` | `event_id` 或本地幂等别名；进入 wire 后必须能稳定映射到 `event_id`。 |
| `semantic_kind` | `kind`。 |
| `object_id` | `content` 内的目标对象字段，例如 `card_id`、`room_id`、`target_ref`。 |
| `payload` | `content`。 |
| `created_at` | `created_at`，但 envelope 还必须包含 `hlc`、`actor_seq`、`prev_refs` 和 `auth_refs`。 |
| `idempotency_key` | 传输请求 idempotency metadata；不得进入 event digest，除非 profile 明确声明。 |

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `operation_id` | yes | `id:operation` 或 `hash` |  | Operation ID。 |
| `type` | yes | `enum(operation)` | 固定为 `operation`。 | 对象种类。 |
| `operation_type` | yes | `enum(create, update, delete, redact, grant, revoke, snapshot_ref, move, reorder, rebalance, link, unlink)` |  | operation 类型。 |
| `semantic_kind` | no | `string` | 标准事件 kind，例如 `cx.card.move`。`move/reorder/rebalance/link/unlink` 必填。 | 语义操作类型，用于校验 payload。 |
| `space_id` | yes | `id:space` |  | 目标 Space。 |
| `object_id` | no | `string` | create 可由 payload 指定。 | 目标对象。 |
| `object_type` | yes | `string` | `room`、`board`、`list`、`card`、`message`、`morph`、`relation` 等。 | 目标对象类型。 |
| `payload` | yes | `object` | 由 operation_type 决定。 | 操作内容。 |
| `idempotency_key` | no | `string` | 重试写入 SHOULD 设置。 | 幂等键。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

Canonical Operation 与 Event Envelope 的映射：

- `semantic_kind="cx.card.move"` MUST 使用 `operation_type="move"`、`object_type="card"`，并使用 card move payload schema。
- `semantic_kind="cx.container.move_item"` MUST 使用 `operation_type="move"`、`object_type="relation"`，并使用容器 item move payload schema。
- `semantic_kind="cx.card.reorder"` MUST 使用 `operation_type="reorder"`、`object_type="card"`，并使用 card reorder payload schema。
- `semantic_kind="cx.card.link_room"` MUST 使用 `operation_type="link"`、`object_type="card"`，并创建或更新 `links_room` Relation。
- `semantic_kind="cx.container.rebalance"` MUST 使用 `operation_type="rebalance"`、`object_type="relation"`，并使用容器 rebalance payload schema。
- `operation_type` 为 `move`、`reorder` 或 `rebalance` 时，`semantic_kind` MUST 存在且属于本 schema 声明的有序操作语义白名单；实现不得把有序集合操作塞进无语义的 generic `update`，也不得使用未知 `semantic_kind` 绕过 payload validation。

## 19. Blob Metadata

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

## 20. MLS Encrypted Payload Envelope

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

## 21. Client Sync Response

Schema id: `cx.schema.client_sync_response.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `next_batch` | yes | `cursor` 或 `string` | opaque。 | 下一次 sync token。 |
| `spaces` | no | `map<SyncSpace>` | key 为 `space_id`。 | Space 增量。 |
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

## 22. 最小 JSON Schema 生成规则

机器可验证 JSON Schema SHOULD 从本文表格生成，并遵守：

- `required` 来自“必填”列。
- `type` 来自“类型”列。
- `enum` 来自 `enum(...)`。
- `pattern` 用于 DID、ID、hash、cursor、timestamp。
- `additionalProperties` SHOULD 默认为 `true`，但未知字段仍必须通过 policy 和 schema evolution 规则处理。
- 对安全关键 envelope，JSON Schema 只做结构检查；签名、hash、capability、MLS transcript 和 DID 控制链必须由协议验证器执行。
