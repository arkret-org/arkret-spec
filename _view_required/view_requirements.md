# View Product Requirements

产品级 View 协议的共同底线：

- View 只能定义投影，不得成为 Entity、Relation、Event 的 canonical truth。
- 每个 View kind 必须有机器可验证的配置 profile，不能只靠自然语言解释。
- 每个投影响应必须带 `projection` discriminator、`view_id`、`frontier`，并支持稳定 cursor。
- 权限裁剪必须先于投影输出；hidden 对象不得通过 count、cursor、错误形态或空洞泄漏存在性。
- 排序必须有稳定 tie-break；分页 cursor 必须绑定 projection、view、frontier、actor visibility 和列/分组上下文。
- 图、树、时间线、会话等多对象视图必须能追溯到输入 Entity / Relation / Event。

| View kind | 系统实现难点 | 产品级完善要求 |
| --- | --- | --- |
| `kanban` | 离线拖拽、rank 稠密插入、列权限、WIP、隐藏计数、字段列与 collection 列两种模型。 | 已有专用 `kanban` config；move/reorder/rebalance payload、projection column/card、rank、hidden count、WIP 和 conformance fixture 必须机器可验证。 |
| `list` | 大结果集分页、稳定排序、字段裁剪、批量选择。 | 必须声明 tabular columns、row sort、page size；响应使用 row projection。 |
| `table` | 列 schema、类型格式化、排序/filter 一致性、宽表字段权限裁剪。 | 必须声明 tabular columns；每列 field/title/format 可验证；响应 item 必须可追溯 entity。 |
| `calendar` | 时间区间重叠、timezone、全天事件、recurrence、权限裁剪。 | 必须声明 start/end field、timezone、bucket/overlap policy；响应使用 row projection 且 position 可表达时间窗口。 |
| `gantt` | 依赖边、持续时间、关键路径、跨项目权限、拖拽调度冲突。 | 必须声明 time window config，并用 relation query 表达依赖边；响应至少可验证 task item 与时间位置。 |
| `chat` | 消息顺序、编辑/撤回、read marker、线程、成员可见性、E2EE epoch。 | 必须声明 conversation config；响应使用 timeline projection，消息 tombstone/redaction 可验证。 |
| `thread` | root anchor、回复树、分页方向、引用对象权限。 | 必须声明 conversation config 和 anchor；响应使用 timeline projection，thread_id/reply order 稳定。 |
| `forum` | topic 列表与回复摘要、未读状态、置顶/关闭、权限裁剪。 | 必须声明 conversation config；topic row 与 message timeline 可组合。 |
| `tree` | 深度限制、循环检测、孤儿节点、lazy link、跨 Space 截断。 | 必须声明 graph config；响应使用 graph projection，node depth/lazy/truncated 和 edge 来源可验证。 |
| `graph` | 大图遍历、循环、边方向、多关系类型、跨 Space lazy link、布局非真相。 | 必须声明 graph config；响应 nodes/edges/frontier 可验证，layout 只能是 hint。 |
| `timeline` | 全局排序、HLC 与 created_at 回退、分页 gap、redaction、混合 Entity/Event。 | 必须声明 timeline config；响应 entry sort_key 和 frontier 可验证。 |
| `review_queue` | 分配、优先级、状态转移、并发领取、可见计数。 | 必须声明 queue config；响应使用 row projection，state/priority/assignee 字段可验证。 |
| `matrix` | 双轴分组、稀疏 cell、聚合权限泄漏、分页二维化。 | 必须声明 matrix config；聚合默认只对 visible set 生效。 |
| `document` | section 顺序、嵌套块、评论/修订、权限裁剪。 | 必须声明 document config；section relation 和 order 可验证。 |
| `dashboard` | 多 widget 查询、刷新一致性、局部失败、聚合泄漏。 | 必须声明 dashboard widget 列表；每个 widget 有 query/projection/frontier。 |
| `activity` | 多事件源合并、因果顺序、去重、审计可追溯。 | 必须声明 timeline config；响应使用 timeline projection。 |
| `inbox` | 个人化派生状态、跨 principal 泄漏、去重、ack/read。 | 必须声明 queue config；holder-private projection 不得跨 principal。 |
| `notifications` | 通知规则派生、已读/未读、去重、隐私。 | 必须声明 queue config；只返回当前 principal/device 可见通知。 |
| `memory_review` | spaced repetition、私有 memory、评分状态、队列公平性。 | 必须声明 queue config；review state 和 next_due 字段可验证。 |
| `agent_runs` | run 状态流、日志/trace 大对象、权限、实时增量。 | 必须声明 queue config 或 timeline config；默认用 queue config 管 run 列表。 |
| `context_timeline` | 围绕 anchor 聚合事件、关系、消息、审阅；跨对象权限裁剪。 | 必须声明 timeline config 且 query 必须有 anchor/context。 |
| `moderation_queue` | 安全审核、优先级、证据裁剪、审计、不可泄漏举报人。 | 必须声明 queue config；response 只暴露授权 evidence summary。 |

