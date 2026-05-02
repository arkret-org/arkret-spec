# Design Questions

## 1. 目标

本文记录 Contrix v1 当前已经收敛的关键设计问题。旧的“所有对象都是 Entity + facets”路线已经废弃；现行模型以标准对象和 Morph 并行组成协作图。

## 2. 根模型是什么？

决策：

- Contrix 采用 **space-first + standard-object-first + event-first**。
- 协议根模型固定为 `Space + Actor + Subject + Room + Board + List + Card + Message + Morph + Relation + Event + View`。
- Subject、Room、Board、List、Card、Message 是标准对象，拥有明确主语义、授权和 reducer。
- Subject 是薄语义中心：它回答“这组讨论、推进和文档共同围绕的那个东西是什么”。Card、Room、Document 等是围绕 Subject 的协作 surface。
- Morph 是开放对象，用于扩展业务类型和实验类型；facets 是 Space schema / Morph profile 声明能力的 hint / 查询标签，不是对象身份，也不是授权、状态机或 reducer 语义来源。
- View 只负责投影定义。View 拥有 query / renderer / layout 等定义真相，但不拥有被投影对象的协作事实。

理由：

- 把 Subject、Board、Card、Room、Message 都压成通用 Entity 会损失真实结构语义。
- 标准对象能让授权、同步、索引和 UI 行为更直接、更可测试。
- Morph 保留扩展性，但不再吞掉核心协议概念。

## 3. Space 与跨服务器协作的边界是什么？

决策：

- Space 是复制、授权、schema、policy、membership、history visibility 和 E2EE 的边界。
- 跨服务器协作以 Space 为主要同步单位。
- 用户 join / invite 进入的是 Space 或 Room，而不是某台服务器。
- Principal Server 是 principal 控制或委托的服务入口，不是协作成员边界。

规则：

- 一个 Organization 可以创建、拥有、托管或背书多个 Space。
- 一个 Organization 可以委托一个或多个 Principal Server / Policy Server，以及可选受托 search / projection 服务。
- 服务器托管关系不自动证明 Organization ownership；官方性必须由 Organization DID 或 `cx.space.organization` 背书。

## 4. Board / List / Card 如何建模？

决策：

- Board 是标准对象。
- List 是 Board 下的标准有序分组对象。
- Card 是 List 下的标准工作项、推进项或 Subject 的状态 surface。
- 看板拖拽使用 `cx.card.move`、`cx.card.reorder`、`cx.space.update`（更新 List-Space rank）等标准操作。

关系：

- `board --contains--> list`
- `list --contains--> card`
- Card 的状态、标题、负责人、标签、截止时间等属于 Card 自身或显式 profile/schema；如果 Card 作为某个 Subject 的推进面，二者通过 `subject --has_surface--> card` Relation 关联。facets 只可作为已声明能力的查询和投影 hint。

View 只负责把 Board/List/Card 投影成 kanban、table、calendar、gantt 等展示。Board/List/Card 的存在、包含关系、rank 和字段状态仍由标准对象、Relation 与对应 operation 维护。

View 仍然保留为一层独立抽象，因为同一组 Card / Room / Morph 需要被多个团队或个人以不同方式观察，例如 board、table、calendar、timeline、dashboard、review queue。改变观察方式写入 View；改变协作对象事实写入对象或 Relation。

## 5. Subject 如何整合 Card / Room / Morph？

决策：引入 **Subject** 作为一等标准对象，但保持非常薄。

Subject：

- 面向“东西本身”：事项、议题、决策、事故、客户 case、研究主题或资产。
- 拥有稳定 ID、标题、brief、summary、kind、生命周期和少量自身字段。
- 可以被搜索、引用、归档、总结，也可以作为 tree/graph/document/timeline View 的 anchor。
- 不承载 Room timeline、Room membership、E2EE epoch、Card 排序、Board/List 位置或 Message thread。

Surface：

- `subject --has_surface--> card`：Card 负责状态推进、看板位置、负责人、优先级、截止时间等 workflow 语义。
- `subject --has_surface--> room`：Room 负责讨论时间线、成员、历史、通知、moderation 和 E2EE。
- `subject --has_surface--> morph`：Document、Poll、外部系统对象等作为扩展 surface。
- `subject --has_surface--> view`：可选地表达某个默认 activity / graph / document / dashboard projection。

规则：

- Subject 可见不代表 surface 内容可读。不可读 surface 必须裁剪为 locked stub、authorized hidden count，或完全不返回。
- Room membership 不授予 Subject 更新、surface 管理或 capability 管理权限。
- Card 写权限不授予 Room 管理或 Subject 管理权限。
- Surface link 只表达语义聚合，不传递权限；授权仍由 capability、policy、membership 和对象自身规则计算。
- `Topic` 不是新的协议根。若产品需要 topic，可使用 `subject_kind="topic"`。

理由：

- Subject 让协议有一个“真正的东西”，避免 Card 和 Room 只能互相硬连。
- Subject 足够薄，不会退回旧的万能 Entity，也不会吞掉 Room/Card/Message/Morph 的 reducer 和授权边界。
- 多个 Card、多个 Room、Document 可自然围绕同一 Subject 聚合，适合真实协作中的设计、评审、外部沟通、执行和沉淀。

## 6. Card 与 Room 是一个概念吗？

决策：不是。Card 和 Room 严格区分。

Card：

- 面向工作推进、状态、排序、归档、负责人、字段和依赖。
- 可以出现在 Board/List 中。
- 适合表达“一个需要被组织、推进、总结和落地的工作面”。当需要表达“主题/事项本身”时，SHOULD 使用 Subject，并把 Card 作为 surface。

Room：

- 面向持续会话、消息历史、成员、通知、E2EE epoch 和 moderation。
- 不属于 Board/List。
- 适合表达“围绕某个 Subject、Card、Board 或外部上下文发生的讨论流”。

## 7. Card 如何关联讨论？

决策：

- 新模型 SHOULD 优先通过 `Subject --has_surface--> Card` 和 `Subject --has_surface--> Room` 组织同一事项的推进面和讨论面。
- 一个 Card 仍可以链接零到多个 Room，用于历史兼容、局部上下文或没有显式 Subject 的轻量场景。
- `links_room` 表示 Card 与 Room 有上下文关联。
- `primary_room` 只表示默认打开或 UI 首选讨论入口。
- Card-to-Room link 不传播权限。

规则：

- Card 可见不代表 linked Room timeline 可读。
- Room 可读不代表 linked Card 可写。
- Room membership、history visibility、E2EE epoch、moderation 和 notification 独立计算。
- 不引入 bound room / inherited room membership 作为 v1 基础语义。
- 当 Card 与 Room 共享 Subject 时，也不得从 Subject 或 surface relation 传播权限。

理由：

- 独立 Room 避免复杂的受控 Room 继承模型。
- 一个 Card 可能需要多个讨论 Room，例如设计、法律、客户沟通、事故复盘。
- 权限独立让外部协作和局部讨论更容易组合。
- Subject-centered surface 模型提供有机聚合，Card-Room link 只保留为兼容或快捷关系。

## 8. Morph / facets 的边界是什么？

决策：

- Morph 是开放对象类型。
- Morph 的领域能力由 Space schema / Morph profile 显式声明。
- facets 是已声明能力的 hint / 查询标签，例如 `assignable`、`schedulable`、`reviewable`、`documentable`，不得单独决定授权、状态机、排序语义、reducer 行为、event kind 接受规则或 wire 互操作。
- Morph 不替代 Subject、Room、Board、List、Card、Message。

适合 Morph 的对象：

- document
- file profile
- poll
- call
- 外部集成对象
- 领域专用业务对象

不适合 Morph 的对象：

- Room
- Board
- List
- Card
- Message
- Subject

## 9. Message 是什么？

决策：

- Message 是 Room 内的一等标准对象。
- Message 归属一个 Room。
- Message 的回复、reaction、mention、redaction 通过 Message 事件和 Relation 表达。

Message 不再是通用 Entity 语义标签，也不是协议唯一事实根。

## 10. 授权如何拆分？

决策：

- Space membership 只说明 actor 在 Space 中的基础参与状态。
- Subject 权限只控制 Subject 自身字段和 surface 关系。
- Room membership 是局部参与状态，不授予 Space-wide、Board 或 Card 权限。
- Room membership 不授予 Subject 更新、surface 管理、Card 更新或 grant 管理权限。
- Capability action 使用对象域命名，例如 `cx.subject.update`、`cx.subject.link_surface`、`cx.card.update`、`cx.room.member`、`cx.message.create`、`cx.morph.update`。
- Resource selector 使用 `subject`、`room`、`board`、`list`、`card`、`message`、`morph`、`object`，不再使用 `entity`。

## 11. 同步和索引如何表达？

决策：

- Event 仍是审计和归约输入；Operation 只作为 SDK / API 语义名称或兼容别名。
- Sync 以 Space 为主要范围，同时支持 Subject、Room、Board、Card、Morph 等过滤。
- Query shape 使用 `object_types`、`subject_kinds`、`morph_types`、`facets`；其中 `facets` 只筛选 schema/profile 已声明的 hint / 查询标签。
- 对象当前态查询默认由客户端本地 reducer / projection 实现。
- Relation 使用 `from_ref` / `to_ref`，可连接标准对象、Morph、Actor 和 Space。
- Subject activity / timeline 是投影：它聚合 Subject 自身事件、surface relation 变化、Card 状态变化、可见 Room 消息摘要和 Document 更新，不是新的 canonical message log。

## 12. 与 Matrix 的关系

决策：

- Contrix 吸收 Matrix 的 state resolution、auth refs、E2EE、client sync 和 federation 经验。
- Contrix 不继承 Matrix 的 room-first 抽象根。
- Room 在 Contrix 中是一等会话对象，但 Space 才是协作边界，Subject 是语义中心，Board/Card/Morph 也是协议一等图节点。

## 13. 当前结论

Contrix v1 当前固定：

1. Space 是协作边界。
2. Subject、Room、Board、List、Card、Message 是标准对象。
3. Subject 是薄语义中心；Card、Room、Document 等通过 `has_surface` Relation 成为围绕它的协作 surface。
4. Morph 承担开放扩展；facets 只表达 schema/profile 已声明能力的 hint / 查询标签。
5. Card 与 Room 严格区分，但可通过共同 Subject 聚合，也可通过兼容 Relation 关联多个 Room。
6. Subject-surface、Card-Room link 均不传播权限。
7. View 是投影定义，拥有自己的定义真相，但不拥有被投影对象的协作事实。
8. Capability、resource selector、query、sync 和 schema 全部按标准对象 / Morph 模型命名。
