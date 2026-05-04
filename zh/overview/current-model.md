# 当前模型说明

## 1. 目标

本文给出 Contrix v1 的统一对象模型读法，确保实现、文档和交互层对同一套协作语义采用一致解释。

## 2. Flow 是统一协作对象

`Flow` 承载同一事项的正式表达与讨论过程：

- `branches[].name`：定义 Flow 当前启用的能力分支
- `branches[].is_primary=true`：可显式定义默认主入口；若未显式设置且存在 `synthesis`，默认主入口派生为 `synthesis`
- 业务语义通过 Space schema/profile、`fields`、Relation、labels、Morph type 或 facet 表达

## 3. Flow 的标准 Branch

`Flow.branches` 是 branch 定义数组。v1 标准化两个 branch name：

- `synthesis`：正式表达、结构化字段、状态推进、标题、摘要、正文
- `discussion`：成员、消息、历史可见性、通知与可选 E2EE

分支规则：

- `discussion` 可独立启用或关闭
- `cx.flow.convert` 切换显式 primary branch，不改变 `flow_id`
- `cx.flow.branch.enable`、`cx.flow.branch.disable`、`cx.flow.branch.set_primary` 管理 branch 生命周期与默认入口

## 4. 工作流容器

工作流容器由 `Space` 的形态承担：

- `Space(kind=board)`
- `Space(kind=list)`

Flow 在 `Space(kind=board)` / `Space(kind=list)` 中的位置通过 `contains` relation 与 `cx.flow.move` / `cx.flow.reorder` 维护。

## 5. View 的职责

`View` 只负责查询和渲染：

- 看板/列表使用 `View.kind="collection"`，再通过 renderer 表达 `board` / `list` 视图样式
- View filter / columns / layout 变化写入 `cx.view.update`
- 拖拽 Flow、切换 List、修改 rank 写入真实对象事件：`cx.flow.move` / `cx.flow.reorder` / `cx.space.update`

## 6. 权限与成员边界

Space membership、Flow 更新权限与 discussion access 使用统一授权模型裁剪：

- `cx.member.state` 控制 Space membership
- `cx.flow.*` 控制 Flow 自身与工作流位置
- branch 默认继承 Flow / Space access
- `cx.flow.branch.member` 只在 branch-scoped override 生效时控制 discussion 成员状态
- Flow synthesis 可见只有在有效 access policy 继承或授予 discussion 读取时，才代表 discussion 可读
- discussion 可读不代表 Flow synthesis 可写

## 7. E2EE 边界

MLS 加密可绑定到两个层级：

- Space 级：整个 Space 共用加密边界
- Flow discussion branch 级：某个 Flow 的 `discussion` 通过 branch-scoped override 独立作为 MLS group

当 `discussion` branch 通过 `branches[].access` 或等价 policy 使用 `encryption_profile="mls_rfc9420"` 时，成员、`history_visibility`、key sharing 和审计边界均以该 branch 为准。

## 8. Agent 结果落点

Agent 的标准落点为：

- `Flow`：长期任务、决策、方案、研究等可持续对象
- `Message`：discussion 中的即时沟通或补充结论
- `Morph` / `Blob`：长报告、代码包、外部 transcript 或二进制成果

推荐做法是先将 agent 结果沉淀到带有明确 Space schema/profile 或业务 `fields` 的 Flow，再按需要附加 Message / Morph / Blob 引用。

## 9. 统一读法

Contrix v1 的统一读法是：

1. `Space` 是协作边界。
2. `Flow` 是统一协作对象。
3. `synthesis` / `discussion` 是 Flow 的两个标准 branch。
4. `Space(kind=board)` / `Space(kind=list)` 是工作流形态。
5. `View` 只做投影，不持有真实对象语义。
