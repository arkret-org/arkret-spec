# View Product Requirements

产品级 View 协议的共同底线：

- View 只能定义投影，不得成为 Entity、Relation、Event 的 canonical truth。
- 顶层核心类型必须少而稳定；产品形态通过 `preset` 表达。
- 每个核心 `kind` 必须有机器可验证的配置 profile，不能只靠自然语言解释。
- 每个非 raw 投影响应必须带 `projection` discriminator、`view_id`、`frontier`，并支持稳定 cursor。
- 权限裁剪必须先于投影输出；hidden 对象不得通过 count、cursor、错误形态或空洞泄漏存在性。
- 排序必须有稳定 tie-break；分页 cursor 必须绑定 projection、view、frontier、actor visibility 和分组上下文。
- 图、树、时间线、会话等多对象视图必须能追溯到输入 Entity / Relation / Event。

| Core kind | 覆盖的 preset | 系统实现难点 | 产品级完善要求 |
| --- | --- | --- | --- |
| `collection` | `kanban`, `list`, `table`, `calendar`, `gantt`, `review_queue`, `matrix`, `inbox`, `notifications`, `memory_review`, `agent_runs`, `moderation_queue` | 大集合分页、稳定排序、字段裁剪、分组、拖拽位置、WIP、隐藏计数、二维/时间桶/关系容器、多 render surface。 | 必须声明 `collection.item_entity_types`、`item_render`、`item_order_by`、`grouping`；响应使用 `CollectionProjectionResponse`；group cursor、item position、count policy、relation-backed position 必须可验证。 |
| `timeline` | `timeline`, `chat`, `thread`, `forum`, `activity`, `context_timeline` | 消息/事件全序、redaction/tombstone、双向分页、read state、reply/thread anchor、跨对象上下文权限裁剪。 | 必须声明 `timeline` config；聊天/线程类 preset 还必须声明 `conversation` 或 anchor/relation；响应使用 `TimelineProjectionResponse`，entry `sort_key`、redaction、frontier 和 cursor 必须可验证。 |
| `graph` | `graph`, `tree` | 大图遍历、循环检测、深度限制、lazy link、跨 Space 截断、边权限裁剪、布局非真相。 | 必须声明 `graph` config 且 query 有 relation；响应使用 `GraphProjectionResponse`，node depth/lazy/truncated 和 edge relation 来源必须可验证。 |
| `document` | `document` | section 顺序、嵌套块、评论/修订、权限裁剪、长文档增量加载。 | 必须声明 `document` config；响应使用 `DocumentProjectionResponse`，section relation、sort_key、redaction 和 frontier 必须可验证。 |
| `composite` | `dashboard` | 多 widget 查询、一致性 frontier、局部失败、聚合泄漏、刷新节流。 | 必须声明 `dashboard.widgets`；响应使用 `CompositeProjectionResponse`，每个 widget 必须有 projection、frontier、result 或标准 error。 |

关键抽象：

- `preset="kanban"` 不意味着只能显示 task；任何满足 `collection.item_entity_types` 的 Entity 都可以作为 card 显示，包括 thread、topic、message、run、memory。
- `preset="thread"` 不意味着一个新的顶层 view kind；它是 `timeline` 的会话/回复排序模板。
- `preset="table"` 与 `preset="kanban"` 共享 `collection.items[*]`，只是 render surface、grouping 和 display fields 不同。
- `preset="tree"` 是 `graph` 的树形约束模板，仍使用同一套 node/edge/cycle/lazy contract。
