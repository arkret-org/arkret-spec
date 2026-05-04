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

注：`device_id` 不是例外字段；它的类型是 `id:device`，wire form MUST 为 `cx:device:<ulid>`。只有部分辅助标识符（如 `transaction_id`、`backup_version`、`stream_id`）使用领域特定前缀（如 `ver_`、`kb_`、`devstream_`），不遵循 `cx:<kind>:<ulid>` 格式。这些标识符的编码规则由各自所在章节定义。

字段默认规则：

- 未标记 optional 的字段为 required。
- `null` 只有在类型中明确写出时才允许。
- 实现 MUST 保留未知字段，但 MUST NOT 让未知字段绕过 capability、schema、policy 或加密约束。
- 签名和 hash 输入 MUST 使用 canonical JSON。
- `id:<kind>` 在 wire、canonical object、fixture、签名和跨服务引用中 MUST 使用完整 typed ID。数据库内部 MAY 只存 raw id，但在序列化、签名、hash、联邦、sync cursor 和审计回放前必须恢复 `cx:<kind>:` 前缀；不得把数据库主键或表名当作协议 ID 的替代品。
- 当 `id:<kind>` 出现在 JSON object key 中时，它仍然属于 wire value；例如 `messages.{principal_id}.{device_id}` 中的 `{device_id}` MUST 使用完整 `cx:device:<ulid>`，不得写成局部别名如 `dev_a` 或 `a`。

## 3. Common Object Fields

所有 durable canonical object SHOULD 使用以下公共字段，除非对象类型另有说明。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:*` | kind 必须匹配对象类型。 | 对象稳定 ID。 |
| `type` | yes | `enum(space, actor_profile, flow, message, morph, relation, event, view, policy, invite, read_marker, notification, capability, operation, event_batch_receipt, blob)` | 标准类型或 profile 声明的扩展类型。`operation` 与 `event_batch_receipt` 为 SDK 内部或辅助对象，非持久化 canonical 对象。`schema` 通过 `schema_refs` 引用，不作为独立 `type`。 | 对象种类。 |
| `space_id` | conditional | `id:space` | Space 外对象可省略。 | 所属 Space。 |
| `schema` | yes | `string` | SHOULD 是 `cx.schema.*.vN` 或反向域名 schema id。 | 验证 schema id。 |
| `created_by` | conditional | `did` | 系统派生对象可由 `derived_from` 替代。 | 创建主体。 |
| `created_at` | yes | `timestamp` | 不能作为因果真相。 | 创建时间。 |
| `updated_by` | no | `did` | 更新时 SHOULD 设置。 | 最近更新主体。 |
| `updated_at` | no | `timestamp` | MUST 不早于 `created_at`。 | 最近更新时间。 |
| `deleted_at` | no | `timestamp` | durable tombstone 可用。 | 逻辑删除时间。 |
| `labels` | no | `array<string>` | SHOULD 小写短标签。 | 用户或系统标签。 |
| `metadata` | no | `object` | 非授权关键字段。 | 扩展元数据。 |

说明：`operation` 与 `event_batch_receipt` 非 v1 的标准持久化 canonical object；前者是 SDK 内部可寻址中间对象，后者为可选加速/审计对象，协议事实与 reducer 真相仍由 Event Envelope 与 Materialized State 决定。`space_id` / `schema` 字段在这些类型上仍保留可扩展性。

Event Envelope 不是 Materialized Object，不继承本节 Common Object Fields 的 `type` / `schema` 语义。Event 的标准事件类型由顶层 `kind` 表达；`type` 只用于物化对象、外部标准文档或 payload schema 明确声明的对象 discriminator。

## 4. Space

Schema id: `cx.schema.space.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:space` | 以 `cx:space:` 开头。 | Space ID。 |
| `type` | yes | `enum(space)` | 固定为 `space`。 | 对象种类。 |
| `space_version` | yes | `string` | 初版为 `1`。 | 事件授权和状态收敛版本。 |
| `title` | yes | `string` | 1..256 UTF-8 chars。 | 人类可读名称。 |
| `summary` | no | `string` | SHOULD <= 2048 chars。 | 简短说明。 |
| `kind` | yes | `enum(collaboration, personal, project, organization, enclave, board, list)` | `collaboration/personal/project/organization/enclave` 表示通用 Space，`board/list` 表示 Work container space。自定义 kind SHOULD 放在 `fields`。 | Space 语义类别。 |
| `boundary_profile` | no | `enum(security_boundary, container)` | 省略时由 `kind` 派生：`board/list` 为 `container`，其他标准 kind 为 `security_boundary`。 | 是否形成独立 membership / policy / history / E2EE 边界。 |
| `created_by_principal` | yes | `did` | 必须是 create event 授权主体。 | 创建 Principal。 |
| `owning_organizations` | no | `array<did>` | 每项必须可解析为 Organization Principal。 | 官方或治理组织。 |
| `schema_refs` | yes | `array<string>` | MUST 包含 registry 中的对象 schema，例如 `cx.schema.space.v1`，或实现 profile。 | 启用 schema。 |
| `policy_ref` | no | `id:policy` | 若省略，使用 create event 默认 policy。 | Space policy 引用。 |
| `default_discoverability` | yes | `enum(public, listed, restricted, unlisted, invite_only, secret)` | 见 `discovery-directory.md`。 | 默认可发现性。 |
| `default_join_rule` | yes | `enum(public, invite, knock, restricted, knock_restricted, closed)` | `invite` 表示只允许邀请加入；canonical state MUST 使用本枚举值。 | 默认加入规则。 |
| `history_visibility` | yes | `enum(world_readable, shared, invited, joined, restricted)` | 加入后可见历史范围。 | 历史可见性。 |
| `encryption_profile` | yes | `enum(none, mls_rfc9420, external)` | E2EE Space SHOULD 使用 `mls_rfc9420`。 | 加密配置。 |
| `federation_policy` | no | `enum(open, restricted, closed, quarantine)` | sovereign 默认 SHOULD `closed`。 | 联邦策略。 |
| `retention_policy_ref` | no | `id:policy` | 可引用 retention policy。 | 保留策略。 |
| `avatar_blob_ref` | no | `id:blob` | 必须满足 media auth。 | 图标 Blob。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

Space kind 语义：

| kind | 语义 |
| --- | --- |
| `collaboration` | 默认协作 Space，适合普通团队或项目上下文。 |
| `personal` | 个人 Space，通常由单个 principal 控制。 |
| `project` | 项目 Space，常由组织或项目治理策略管理。 |
| `organization` | 组织级 Space，承载组织治理、目录或跨项目协作入口。 |
| `enclave` | 高隔离 Space，通常要求更严格的 resolver、E2EE、审计或 federation policy。 |
| `board` | 工作流容器 Space，用于组织 list 与 item 位置；默认 `boundary_profile=container`。 |
| `list` | Board 下的列/泳道容器 Space，用于承载 Flow 的位置关系；默认 `boundary_profile=container`。 |

`boundary_profile=security_boundary` 的 Space 是复制、授权、schema、policy、membership、history visibility、E2EE 和索引边界。`boundary_profile=container` 的 Space 只提供容器 ID、排序、View / Relation anchor 和局部工作流元数据；它不得隐式创建独立 membership、join rule、history visibility、MLS group、federation topology、retention policy 或 plaintext-visible service。Profile 若允许自定义 kind 成为容器，必须显式声明 `boundary_profile=container`，并说明父安全边界如何解析。

## 5. Actor Profile

Schema id: `cx.schema.actor_profile.v1`

Actor Profile 是 Actor 在协作图中的展示镜像，不是权限主键。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:actor_profile` | Actor Profile 是标准对象。 | Profile 对象 ID。 |
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

Flow、Space 和 Message 是标准对象。Space (kind=board)/Space (kind=list) 表达工作流容器；Flow (kind=card)/Flow (kind=room) 表达协作主对象的默认交互形态。

### 6.1 Flow

Schema id: `cx.schema.flow.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:flow` | 以 `cx:flow:` 开头。 | Flow ID。 |
| `type` | yes | `enum(flow)` | 固定为 `flow`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `kind` | yes | `enum(card, room)` | 决定默认主分支与默认交互面。 | Flow 形态。 |
| `semantic_kind` | no | `enum(topic, initiative, decision, incident, customer_case, proposal, research, task_cluster, asset, custom)` | 用于表达业务语义分类。 | Flow 语义分类。 |
| `title` | yes | `string` | 1..512 chars。 | 标题。 |
| `description` | no | `string` | SHOULD <= 8192 chars。 | 较完整说明。 |
| `brief` | no | `string` | SHOULD <= 2048 chars。 | 简短说明。 |
| `primary_branch` | yes | `enum(synthesis, discussion)` | `card` 默认 `synthesis`，`room` 默认 `discussion`。 | 默认入口分支。 |
| `branches` | yes | `object` | 至少包含 `synthesis`；`discussion` 可选。 | 分支状态。 |
| `access` | no | `object` | branch 默认访问规则与显式 override。 | 统一授权/成员/E2EE 继承配置。 |
| `fields` | no | `object` |  | 扩展字段。 |
| `state` | no | `enum(active, archived, deleted, redacted)` | 删除/撤回必须有事件来源。 | 物化状态。 |
| `version` | no | `integer` | SHOULD 单调递增，不能替代 event order。 | 物化版本。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

`branches.synthesis` 承载标题、摘要、正文、结构化字段和状态等正式表达。`branches.discussion` 在启用时承载房间式讨论能力，例如 `room_kind`、timeline profile 与 branch-local fields。Branch 的成员、权限和 E2EE 默认使用 `access.defaults` 继承 Flow / Space 的有效访问规则；只有 `access.branch_overrides.<branch>` 或对应 policy/capability state event 明确声明时，才形成 branch-scoped membership、history visibility 或 E2EE 边界。`assigned_to`、watchers 或其他业务关系不会自动成为 discussion 成员，除非有效 access policy 明确把它们映射为授权条件。

### 6.2 Space (kind=board)

Space (kind=board) 是 `Space` 的工作流容器形态，ID 使用 `cx:space:` 格式。Space (kind=board) 的视图样式通过 `fields`、schema profile 或 `View.renderer` 表达。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:space` | 以 `cx:space:` 开头。 | Space ID。 |
| `type` | yes | `enum(space)` | 固定为 `space`。 | 对象种类。 |
| `kind` | yes | `enum(board)` | 固定为 `board`。 | Space 形态。 |
| `boundary_profile` | no | `enum(container)` | 默认为 `container`。 | 不形成独立安全边界。 |
| `space_id` | yes | `id:space` |  | 父 Space ID。 |
| `title` | yes | `string` | 1..256 chars。 | 名称。 |
| `summary` | no | `string` |  | 说明。 |
| `default_view_id` | no | `id:view` |  | 默认 View。 |
| `fields` | no | `object` |  | 扩展字段。 |
| `state` | no | `enum(active, archived, deleted)` |  | 状态。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

Space (kind=board/list) 是工作流容器，不是新的 membership、history visibility、policy、federation 或加密边界。除非明确 profile 另有规定，它们的成员、history visibility、E2EE、federation、retention 和 plaintext-visible service 规则 MUST 继承最近的 `boundary_profile=security_boundary` 祖先 Space 的有效 policy；不得仅因为创建了 Board/List 就隐式创建独立 MLS group、join rule 或 federation topology。

### 6.3 Space (kind=list)

Space (kind=list) 是 `Space` 的列/泳道形态，ID 使用 `cx:space:` 格式。Space (kind=list) 通过 `cx.space.child`/`cx.space.parent` 层级关系挂载到 Space (kind=board) 下。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:space` | 以 `cx:space:` 开头。 | Space ID。 |
| `type` | yes | `enum(space)` | 固定为 `space`。 | 对象种类。 |
| `kind` | yes | `enum(list)` | 固定为 `list`。 | Space 形态。 |
| `boundary_profile` | no | `enum(container)` | 默认为 `container`。 | 不形成独立安全边界。 |
| `space_id` | yes | `id:space` |  | 父 Space ID（Space (kind=board)）。 |
| `title` | yes | `string` | 1..256 chars。 | 名称。 |
| `summary` | no | `string` |  | 说明。 |
| `rank` | no | `string` | Fractional indexing rank。 | Space (kind=board) 内顺序。 |
| `wip_limit` | no | `integer` |  | WIP 限制。 |
| `fields` | no | `object` |  | 扩展字段。 |
| `state` | no | `enum(active, archived, deleted)` |  | 状态。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

Space (kind=list) 的排序、WIP、item membership 和 card 位置必须通过 Relation / Flow move / rank 事件表达。List 本身不得被当作 Message timeline、成员房间或权限主键。

### 6.4 Message

Schema id: `cx.schema.message.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:message` | 以 `cx:message:` 开头。 | Message ID。 |
| `type` | yes | `enum(message)` | 固定为 `message`。 | 对象种类。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `flow_id` | yes | `id:flow` |  | 所属 Flow。 |
| `branch` | yes | `enum(discussion)` | v1 标准 Message 只位于 discussion branch。 | 所属 Flow 分支。 |
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
assigned_to, references, derived_from, attached_to, has_default_view,
produced, used, triggered_by, has_log, summarized_from, promoted_from_discussion
```

未声明为 multi-edge 的 Relation MUST 由 reducer 按 `(space_id, relation_kind, from_ref, to_ref)` 去重。Events API MAY 拒绝同一 frontier 下显然重复的写入，但不能作为唯一去重机制；两个离线设备并发创建同一关系时，reducer 必须确定性选择一个 active winner，并把 loser 记录为 conflict 或 tombstone。声明为 multi-edge 的 relation profile MUST 显式定义去重 key、排序字段和 conflict 处理。

## 9. Event Envelope

Schema id: `cx.schema.event.v1`

Event 是 reducer 输入。它不是当前态对象。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `event_id` | yes | `id:event` | 事件稳定 typed ID。事件 canonical digest / proof hash 见 `encoding-conformance-vectors.md`。 | 事件 ID。 |
| `kind` | yes | `string` | 标准 event kind SHOULD 使用 `cx.` 前缀。 | 事件 kind。 |
| `schema` | no | `string` | 若存在，MUST 为 `cx.schema.event.v1` 并进入 canonical bytes；不得替代 `kind` 或 payload schema selection。 | Envelope schema 标记。 |
| `space_id` | yes | `id:space` | Space create 可在 payload 中建立。 | 所属 Space。 |
| `space_version` | yes | `string` | 初版 `1`。 | 授权/状态版本。 |
| `actor_id` | yes | `did` | 必须匹配 proof 控制链。 | 发送 Actor。 |
| `actor_seq` | yes | `integer` | 同一 actor 因果路径上严格递增；并发 sibling fork 可出现相同高度。 | Actor 链高度 / 防回退索引。 |
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

Event Envelope 的顶层 `kind` 是唯一事件类型 discriminator。`content.type` 不得重复写入 `cx.*` Event kind；若 payload 需要引用被创建对象，使用 `content.object.type` 等对象字段。`actor_id` 是签署并提交该 Event 的 DID；物化对象的 `created_by` / `updated_by` 是 reducer 输出字段，通常来自对应 create/update Event 的 `actor_id`，但不得替代 Event proof、capability 或 auth_refs 校验。启用 minimal-metadata E2EE profile 时，`actor_id` MAY 是 Space / Flow branch scoped pairwise DID；真实 principal DID 的映射必须通过加密的 `cx.identity_link`、claim disclosure 或 policy 声明验证，不得把非 DID pseudonym 写入 `actor_id`。

`required_features` 与 `critical_extensions[].id` 必须使用可发现的 feature/profile 标识，并通过 service describe、profile registry 或 Space schema/policy 指向可验证定义。接收方不支持 critical feature 时 MUST fail closed；不得把未知 critical 语义当作普通未知字段保留后继续 accepted。

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

若某个 UI 操作改变 Flow(kind=card) 所属 List、Flow rank、List rank、Flow discussion Message、Relation 或对象字段，必须使用对应对象 Event；只有改变共享 filter、sort、grouping、visible fields、renderer 或 layout 时才修改 View。个人偏好、临时排序、列宽、折叠状态和本地 pin MUST 使用 actor-private account data 或等价私有 Event。

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
| `board_id` | conditional | `id:space` | `mode="relation_container"` 时必填。 | Space (kind=board)。 |
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
| `policy_type` | yes | `enum(access, encryption, retention, federation, moderation, discoverability, join, history_visibility, plaintext_visibility, media, applet, agent)` |  | 策略类型。 |
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
| `actions` | yes | `array<string>` | 例如 `cx.flow.update`、`cx.message.create`。 | 允许动作。 |
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
| `scope` | yes | `enum(space, flow, discussion, thread, view, message, morph)` |  | 已读范围。 |
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
| Materialized Object | reducer 输出的当前态对象，例如 Flow、Relation、View。 | 否。 | 否，不能反向替代事件历史。 |

字段映射：

| Canonical Operation | Event Envelope |
| --- | --- |
| `id` | 本地草稿 / builder 对象 ID；进入 wire 后必须能稳定映射到 `event_id` 或被 `event_id` 取代。 |
| `semantic_kind` | `kind`。 |
| `object_id` | `content` 内的目标对象字段，例如 `flow_id`、`space_id`、`target_ref`。 |
| `payload` | `content`。 |
| `created_at` | `created_at`，但 envelope 还必须包含 `hlc`、`actor_seq`、`prev_refs` 和 `auth_refs`。 |
| `idempotency_key` | 传输请求 idempotency metadata；不得进入 event digest，除非 profile 明确声明。 |

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:operation` 或 `hash` | 不得命名为 `operation_id`；`operation_id` 保留给服务 API canonical operation。 | Canonical Operation Object ID。 |
| `type` | yes | `enum(operation)` | 固定为 `operation`。 | 对象种类。 |
| `operation_type` | yes | `enum(create, update, delete, redact, grant, revoke, snapshot_ref, move, reorder, rebalance, link, unlink)` |  | operation 类型。 |
| `semantic_kind` | no | `string` | 标准事件 kind，例如 `cx.flow.move`。`move/reorder/rebalance/link/unlink` 必填。 | 语义操作类型，用于校验 payload。 |
| `space_id` | yes | `id:space` |  | 目标 Space。 |
| `object_id` | no | `string` | create 可由 payload 指定。 | 目标对象。 |
| `object_type` | yes | `string` | `flow`、`space`、`message`、`morph`、`relation` 等。 | 目标对象类型。 |
| `payload` | yes | `object` | 由 operation_type 决定。 | 操作内容。 |
| `idempotency_key` | no | `string` | 重试写入 SHOULD 设置。 | 幂等键。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |

Canonical Operation 与 Event Envelope 的映射：

- `semantic_kind="cx.flow.move"` MUST 使用 `operation_type="move"`、`object_type="flow"`，并使用 flow move payload schema。
- `semantic_kind="cx.container.move_item"` MUST 使用 `operation_type="move"`、`object_type="relation"`，并使用容器 item move payload schema。
- `semantic_kind="cx.flow.reorder"` MUST 使用 `operation_type="reorder"`、`object_type="flow"`，并使用 flow reorder payload schema。
- `semantic_kind="cx.flow.branch.enable"` MUST 使用 `operation_type="update"`、`object_type="flow"`，并使用 flow branch enable payload schema。
- `semantic_kind="cx.flow.branch.disable"` MUST 使用 `operation_type="update"`、`object_type="flow"`，并使用 flow branch disable payload schema。
- `semantic_kind="cx.flow.convert"` MUST 使用 `operation_type="update"`、`object_type="flow"`，并使用 flow convert payload schema。

## 19. Field Patch (cx.patch.v1)

非 create 类更新建议使用 `cx.patch.v1` 做字段增量；客户端不得自行定义私有 dot-path 语义替代该标准。

`cx.patch.v1` 为 map 类型：

- `key`: patch path（字段路径）。
- `value`: patch 操作，支持两种表达：
  - 直接值：等价于 `{"$op":"set","value":...}`。
  - 对象：`{"$op":"set|unset|add|remove","value":...}`。

patch path 规则：

- path 由 `snake_case` 标识符或反引号转义字段名组成；
- 仅支持对象路径，不支持数组下标；
- `unset` 不允许带 `value`；
- `set`、`add`、`remove` 必须带 `value`。

客户端不能把数组下标写入 path；如需列表元素更新，必须将对象重建为具名集合项或使用明确的 API 约束字段表示更新目标。
