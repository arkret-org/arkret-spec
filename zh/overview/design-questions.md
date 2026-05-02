# Design Questions and Current Decisions

## 1. 目标

本文件记录当前协议设计已经收敛的关键决策，避免读者继续按旧的 `Subject + Room + Card` 三实体模型理解 Contrix v1。

## 2. Flow 是统一协作载体

当前模型使用 `Flow` 作为承载“同一事项的正式表达与讨论过程”的唯一标准对象：

- `Flow.kind="card"`：默认主入口是 `synthesis`。
- `Flow.kind="room"`：默认主入口是 `discussion`。
- `Flow.semantic_kind`：表达业务语义，例如 `initiative`、`decision`、`incident`、`task_cluster`。

`Room` 和 `Card` 不再是独立标准对象，也不再通过 `Subject --has_surface--> ...` 进行聚合。

## 3. Flow 的两个 branch

`Flow.branches` 当前标准化为两个能力分支：

- `synthesis`：正式表达、结构化字段、状态推进、标题、摘要、正文。
- `discussion`：成员、消息、历史可见性、通知和可选 E2EE。

规则：

- `discussion` 可以独立启用或关闭。
- `cx.flow.convert` 在 `card` / `room` 模式间切换同一个 Flow，不改变 `flow_id`。
- `cx.flow.branch.enable`、`cx.flow.branch.disable`、`cx.flow.branch.set_primary` 管理 branch 生命周期和默认入口。

## 4. Board / List 是 Space.kind，不是 View.kind

工作流容器仍然存在，但它们属于 `Space` 的形态，而不是独立对象家族：

- `Space.kind="board"`
- `Space.kind="list"`

Flow 在 Board/List 中的位置通过 `contains` relation 与 `cx.flow.move` / `cx.flow.reorder` 维护。`board` / `list` 不再进入 `View.kind` 枚举。

## 5. View 只负责投影

`View` 负责查询和渲染，不持有工作流真相源：

- 看板/列表使用 `View.kind="collection"`，再通过 renderer 表达 `board` / `list` 样式。
- 改 View filter/columns/layout 写入 `cx.view.update`。
- 拖拽 Flow、切换 List、修改 rank 写入真实对象事件：`cx.flow.move` / `cx.flow.reorder` / `cx.space.update`。

## 6. 权限与成员边界

Space membership、Flow 更新权限和 discussion membership 分离：

- `cx.member.state` 控制 Space membership。
- `cx.flow.*` 控制 Flow 自身与 workflow 位置。
- `cx.flow.branch.member` 控制 discussion 成员状态。
- Flow synthesis 可见不代表 discussion 可读。
- discussion 可读不代表 Flow synthesis 可写。

旧的 `has_surface`、`links_room`、`primary_room` 不再是标准关系。若需要表达“某条 synthesis 结论来自 discussion”，使用 `promoted_from_discussion` 等沉淀关系，而不是对象聚合关系。

## 7. E2EE 边界

MLS 加密可以绑定到两个层级：

- Space 级：整个 Space 共用加密边界。
- Flow discussion branch 级：某个 Flow 的 `discussion` 独立作为 MLS group。

当 `discussion` branch 独立启用 `encryption_profile="mls_rfc9420"` 时，成员、history visibility、key sharing 和审计边界都以该 branch 为准，不隐式扩大到整个 Space。

## 8. Agent 结果落点

Agent 的执行不再假定必须产出 Card 或 Subject surface。标准落点为：

- `Flow`：长期任务、决策、方案、研究等可持续对象。
- `Message`：discussion 中的即时沟通或补充结论。
- `Morph` / `Blob`：长报告、代码包、外部 transcript 或二进制成果。

推荐做法是让 agent 结果首先沉淀到 `Flow.semantic_kind` 明确的 Flow，再按需要附加 Message/Morph/Blob 引用。

## 9. 当前结论

Contrix v1 当前的统一读法是：

1. `Space` 是协作边界。
2. `Flow` 是统一协作对象。
3. `synthesis` / `discussion` 是 Flow 的两个标准 branch。
4. `board` / `list` 是 `Space.kind`。
5. `View` 只做投影，不持有真实对象语义。