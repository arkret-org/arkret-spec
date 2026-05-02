# Standard Object Types

## 1. 目标

本文定义 Contrix 标准对象类型。标准对象是一等协议对象，不再是 `Entity` 语义标签。

核心字段类型、必填性和通用约束见 `data-structures.md`。本文定义标准对象的业务语义、常用字段、推荐关系和推荐 facets。

原则：

- 标准类型提供主语义。
- `subject` 提供薄语义中心；Card、Room、Document、Run、Memory 等通过 surface relation 围绕它协作。
- `Morph` 提供开放扩展。
- `facets` 是由 Space schema / Morph profile 声明的能力提示和查询标签，不替代对象类型，也不单独定义授权、状态机、排序或 reducer 语义。
- View 只定义如何投影对象；它拥有自己的定义状态，但不发明对象能力，也不持有被投影对象的协作事实。

## 2. Subject

`subject` 表示 Space 内被讨论、推进、引用、审阅、执行或沉淀的“东西本身”。它不是 Room、Card 或 Document 的替代品，而是这些协作 surface 的共同锚点。

Subject 适合：

- 产品/工程 initiative
- 决策或提案
- 事故、客户 case、研究主题
- 跨多个团队的任务簇
- 需要长期沉淀的知识主题
- 外部资产或业务对象的协作锚点

推荐字段：

- `title`
- `brief`
- `summary`
- `subject_kind`
- `state`
- `fields`
- `archived`

`subject_kind` 初版建议：

- `topic`
- `initiative`
- `decision`
- `incident`
- `customer_case`
- `proposal`
- `research`
- `task_cluster`
- `asset`
- `memory_subject`
- `custom`

常见关系：

- `subject --has_surface--> card`
- `subject --has_surface--> room`
- `subject --has_surface--> morph`
- `subject --has_surface--> view`
- `subject --contains--> subject`
- `subject --references--> card / room / morph / message / blob`

`has_surface` 的 `fields.surface_role` SHOULD 声明 surface 用途，例如 `status_card`、`primary_discussion`、`design_discussion`、`review_discussion`、`external_discussion`、`decision_log`、`design_doc`、`spec_doc`、`agent_run_log`、`memory`、`activity_view`、`source_message`。

权限规则：

- Subject 可见不代表 surface 内容可读。
- Room membership 不授予 Subject 更新、surface 管理或授权管理权限。
- Card 写权限不授予 Subject 更新或 Room 管理权限。
- Surface relation 不传播权限；不可读 surface 必须被裁剪为 locked stub、authorized hidden count，或完全不返回。

`Topic` 是一种 Subject 语义，不是新的核心对象类型；产品可使用 `subject_kind="topic"`。

## 3. Room

`room` 表示 Space 内的讨论容器和消息时间线入口。

Room 适合：

- 团队聊天
- 项目讨论
- Card 相关讨论
- 评审或决策会议记录
- 外部协作沟通
- agent 运行播报流

推荐字段：

- `title`
- `summary`
- `room_kind`
- `topic`
- `history_visibility`
- `membership_policy_ref`
- `encryption_profile`
- `archived`

`room_kind` 初版建议：

- `discussion`
- `announcement`
- `support`
- `activity`
- `review`
- `external`

常见关系：

- `room --contains--> message`
- `subject --has_surface--> room`
- `card --links_room--> room`
- `card --primary_room--> room`
- `board --links_room--> room`
- `room --references--> card / board / morph`

Room 权限独立于 Subject / Card / Board：

- Subject 可见不代表 Room 可见。
- Card 可见不代表 Room 可见。
- Room 可见不代表 Card 可见。
- Room membership 不授予 Subject 管理权限。
- Card 归档或删除不自动删除 Room。
- Room membership / policy / E2EE / history visibility 必须独立验证。

## 4. Board

`board` 表示可视化工作台。标准 Board 由多个 `list` 组成，`list` 中包含 `card`。

Board 适合：

- Kanban
- Scrum board
- Review queue
- Work intake
- Incident workflow

推荐字段：

- `title`
- `summary`
- `board_kind`
- `default_view_id`
- `archived`

常见关系：

- `board --contains--> list`
- `subject --has_surface--> board`
- `board --links_room--> room`
- `board --has_default_view--> view`

Board 不自动显示 Space 中所有 Card。只有通过 `board --contains--> list --contains--> card` 或 View 明确 query 选中的 Card 才属于该 Board 的投影范围。即使通过 View 呈现，Board/List/Card 的包含关系、位置和排序仍由标准对象与 active `contains` Relation 归约得到，不属于 View layout 或缓存，也不是 Card canonical object 的 `board_id` / `list_id` 字段。

## 5. List

`list` 表示 Board 内的有序列、泳道或阶段。

推荐字段：

- `title`
- `summary`
- `rank`
- `wip_limit`
- `state`
- `color`

常见关系：

- `board --contains--> list`
- `list --contains--> card`
- `list --links_room--> room`

List 的权限默认不独立于 Board；若实现需要列级权限、列级讨论或列级归档，必须在 schema / policy 中显式声明。

## 6. Card

`card` 表示可执行、可跟踪、可沉淀的工作对象。Card 是 Board/List 里的主要工作单元，也可以是 Subject 的状态推进 surface。独立 Card 可以存在于 Space 中；进入 Board 时由 `list --contains--> card` position edge 表达其主位置。

Card 和 Room 严格区分：

- Card 是工作状态对象或推进 surface。
- Room 是讨论容器。
- Subject 是语义中心。
- Card 可关联 0..N 个 Room。
- 关联 Room 独立管理 membership、policy、history visibility 和 E2EE。

推荐字段：

- `title`
- `body`
- `status`
- `priority`
- `rank`
- `due_at`
- `labels`
- `acceptance_criteria`
- `decision_summary`
- `archived`

推荐 facets：

- `assignable`
- `schedulable`
- `stateful`
- `rankable`
- `reviewable`
- `notifiable`
- `renderable`

常见关系：

- `list --contains--> card`
- `subject --has_surface--> card`
- `card --assigned_to--> actor`
- `card --depends_on--> card`
- `card --blocks--> card`
- `card --links_room--> room`
- `card --primary_room--> room`
- `card --references--> morph / document / run / memory`
- `card --summarized_from--> room`
- `card --promoted_from_room--> room`

`primary_room` 是 UI 默认入口，不是权限继承。一个 Card MAY 有一个 primary Room 和多个 linked Room。新写入 SHOULD 优先使用共同 Subject 聚合 Card 与 Room；Card-Room link 保留为兼容或局部上下文关系。

## 7. Message

`message` 表示 Room 时间线中的原子消息。

推荐字段：

- `room_id`
- `content`
- `format`
- `attachments`
- `revision_root`
- `edited_at`
- `visible_state`
- `redaction_ref`

常见关系：

- `room --contains--> message`
- `subject --has_surface--> message`
- `message --replies_to--> message`
- `message --mentions--> actor / subject / card / room / morph`
- `message --references--> subject / card / board / morph / blob`

Message 创建是 append-only。编辑通过 revision chain；撤回通过 redaction/tombstone。

## 8. Morph

`morph` 是开放形态对象。它替代旧模型中承担所有业务类型的 `Entity`。

Morph 适合：

- 自定义业务对象
- 插件对象
- 外部系统镜像对象
- 未来标准类型的试验对象
- 不要求强互操作的弱结构数据

Morph 是扩展缓冲层，不是标准对象的替代品。Subject、Room、Board、List、Card、Message 的主语义已经由标准对象类型定义；实现不得为了复用字段、renderer 或插件机制而把这些对象退化为 Morph。

推荐字段：

- `morph_type`
- `title`
- `summary`
- `content`
- `fields`
- `facets`

推荐 facets：

- `container`
- `replyable`
- `schedulable`
- `assignable`
- `stateful`
- `rankable`
- `reviewable`
- `notifiable`
- `documentable`
- `renderable`

实现遇到未知 `morph_type` SHOULD 降级为 generic Morph 展示。未知 facet 必须保留，但不得绕过 schema、capability、policy 或 encryption 约束。

任何影响授权、状态机、排序、reducer、事件类型或 wire 互操作的 Morph 语义，MUST 由明确的 Space schema、Morph profile、event kind 和 capability action 定义。实现不得只因为看到 `facets.container`、`facets.stateful`、`facets.rankable` 或其他 facet 字符串，就接受移动、排序、状态转换、授权扩大或 reducer 特例。

## 9. Document

`document` 表示可协作编辑或引用的文档对象。v1 Core 中 Document 是 Morph profile，不是标准对象。后续版本若提升为标准对象，必须通过新的 schema/profile 版本声明迁移规则。

文档正文 MAY 存储为：

- inline structured content
- blob reference
- CRDT snapshot
- external document binding

## 10. File

`file` 表示 blob 的协作元数据。v1 Core 中 File 是 Morph profile，不是标准对象。后续版本若提升为标准对象，必须通过新的 schema/profile 版本声明迁移规则。

内容本身 SHOULD 使用 blob service 存储，并通过 content hash 校验。

## 11. Memory

`memory` 表示可由人或 agent 读取、引用、更新的长期记忆。v1 Core 中 Memory 是 Morph profile；高级生命周期由 `cx.profile.agent_runtime.v1` 扩展声明。

Memory MUST 记录来源：

- `source_event_id`
- `source_object_ref`
- `extracted_by`
- `confidence`
- `expires_at`
- `subject_ref`

## 12. Run

`run` 表示 agent、automation 或 CI 的一次执行。v1 Core 中 Run 是 Morph profile；A2A/ACP/MCP bridge 等执行语义由扩展 profile 声明。

Run SHOULD 记录：

- input
- output
- tool calls
- approval refs
- error state
- responsible actor

常用关系：

- `run --produced--> card / morph / memory`
- `run --used--> tool / input`
- `run --triggered_by--> actor / event / card`
- `subject --has_surface--> run`
- `run --links_room--> room`

## 13. Actor Profile

`actor_profile` 是 Actor 在协作图中的展示镜像。

它用于：

- mention
- assignment
- display
- team membership view

Actor Profile 不替代 DID，也不成为权限主键。

## 14. Poll

`poll` 表示投票或决策收集。Poll MAY 是 Morph profile。

应支持：

- single choice
- multiple choice
- deadline
- visibility policy
- anonymous result policy

投票结果 SHOULD 作为 event 集合归约，而不是只更新单一计数字段。

## 15. 标准 Facets

Facets 是 schema-declared capability hints，不是对象身份。标准对象 MAY 暴露 schema/profile 已声明的 facets 来辅助展示或查询，但标准对象的核心语义不依赖 facets 才成立；Morph MAY 使用 facets 帮助 View、本地搜索、UI 和插件做过滤、降级展示和默认 renderer 选择。

Facets MUST NOT 成为授权、状态机、排序语义、reducer 行为、event kind 接受规则或 wire 互操作的唯一规范来源。这些语义必须由 Space schema / Morph profile / event registry / capability action 明确定义。Facet 配置可以引用这些 profile 或暴露 UI hints，但不能替代它们。

| Facet | 说明 |
| --- | --- |
| `container` | 可包含、排序或移动其他对象。 |
| `replyable` | 可被回复，形成 thread / discussion。 |
| `schedulable` | 有时间窗口，可进入 calendar / gantt。 |
| `assignable` | 可分配给 actor / team / agent。 |
| `stateful` | 有受控状态机。 |
| `rankable` | 有稳定手动排序 rank。 |
| `reviewable` | 可进入审核/审阅队列。 |
| `notifiable` | 可派生 notification / inbox / read state。 |
| `documentable` | 可作为文档或 section root。 |
| `renderable` | 声明允许的默认展示面。 |

## 16. Schema Evolution

标准类型演进 MUST 遵守：

- 新字段优先 optional
- 旧字段不得静默改变语义
- reducer 和客户端 MUST 保留未知字段
- UI 遇到未知 Morph type SHOULD 降级为 generic Morph card
- 标准对象不得阻止 Space 定义自定义 Morph type

## 17. 规范性引用

- 标准 Relation cardinality 按本文件各类型语义、`data-structures.md` 的 Relation 字段和业务 profile 执行；未声明多重关系时，active relation MUST 以 `(relation_kind, from_ref, to_ref)` 收敛为单条。
- Content block registry 见 `content-types.md`；未知 content block 必须按降级规则保留和展示。
- Card status profile 使用 `todo`、`in_progress`、`blocked`、`review`、`done`、`archived` 作为 v1 基础集合；Space schema 可增加自定义状态，但不得改变基础状态语义。
- Poll result reducer vector 必须按 event 集合归约，不能只信任计数字段；匿名投票的明文选择不得进入未授权受托 search / projection 服务。
