# View Product Requirements

产品级 View 协议的共同底线：

- View 只能定义投影，不得成为 Entity、Relation、Event 的 canonical truth。
- 对象职责必须由 Entity `facets` 声明；View 不得通过 kind/preset 隐式赋予对象能力。
- 每个标准 facet 必须有机器可验证的字段组、关系约束、操作语义和投影要求。
- 每个非 raw 投影响应必须带 `projection` discriminator、`view_id`、`frontier`，并支持稳定 cursor。
- 权限裁剪必须先于投影输出；hidden 对象不得通过 count、cursor、错误形态或空洞泄漏存在性。
- 排序必须有稳定 tie-break；分页 cursor 必须绑定 projection、view、frontier、actor visibility 和分组上下文。
- 图、树、时间线、会话等多对象视图必须能追溯到输入 Entity / Relation / Event。

| Entity facet | 覆盖能力 | 系统实现难点 | 产品级完善要求 |
| --- | --- | --- | --- |
| `container` | 包含、排序、移动、列/分组、树形父子。 | 独占位置、rank 稠密插入、跨容器移动、隐藏成员计数、关系可追溯。 | 必须声明 child types、relation kinds、ordering mode、exclusive scope；移动操作使用 `cx.container.move_item` / `cx.container.rebalance`。 |
| `replyable` | thread、chat、forum、评论。 | 回复排序、双向分页、redaction/tombstone、读状态、回复权限。 | 必须声明 reply entity types、reply relation kind、time field、ordering 和 redaction policy。 |
| `schedulable` | calendar、gantt、deadline、时间桶。 | timezone、重叠区间、recurrence、依赖边、拖拽排期冲突。 | 必须声明 start/end/timezone/recurrence/dependency relation fields。 |
| `assignable` | assignee、队列领取、责任人。 | Actor/Team/Agent 授权、并发领取、转交审计。 | 必须声明 assignee relation 或 field，以及允许 assignee kind。 |
| `stateful` | 工作流状态、审核状态、通知状态。 | 状态转移合法性、并发写入、隐藏对象导致的 WIP/计数差异。 | 必须声明 state field、合法 states 和 transition policy。 |
| `rankable` | card/row 顺序、手动排序。 | 多端稠密插入、rebalance、冲突 tie-break。 | 必须声明 rank field、rank profile 和 collision policy。 |
| `reviewable` | review_queue、moderation_queue、memory_review。 | 优先级、公平性、证据裁剪、审核决策审计。 | 必须声明 review state、reviewer relation、priority field 和 decision event kinds。 |
| `notifiable` | inbox、notifications、read/ack。 | 去重、设备/主体私有状态、不可跨 principal 泄漏。 | 必须声明 notification types 与 read state policy。 |
| `documentable` | document、section、修订。 | section 顺序、块内容、redaction、长文档增量。 | 必须声明 section relation/order/body/render mode。 |
| `renderable` | card/row/message/node/section 展示面。 | 展示字段权限裁剪、降级渲染、跨客户端一致性。 | 必须声明允许 renderer 和 title/summary/media 字段。 |

关键抽象：

- `preset="kanban"` 不意味着只能显示 task；任何满足 View `query.facets` / `collection.item_facets` 的 Entity 都可以作为 card 显示。
- `preset="thread"` 不意味着一个新的顶层 view kind；它是对 `replyable` anchor 的 timeline renderer。
- `preset="table"` 与 `preset="kanban"` 可以查询同一组 facets，只是 renderer、grouping 和 display fields 不同。
- `preset="tree"` 是对 `container` 或 relation graph 的树形 renderer，仍使用同一套 node/edge/cycle/lazy contract。
