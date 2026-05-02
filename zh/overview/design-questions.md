# Design Questions

## 1. 目标

本文记录 Contrix v1 当前已经收敛的关键设计问题。旧的“所有对象都是 Entity + facets”路线已经废弃；现行模型以标准对象和 Morph 并行组成协作图。

## 2. 根模型是什么？

决策：

- Contrix 采用 **space-first + standard-object-first + event-first**。
- 协议根模型固定为 `Space + Actor + Room + Board + List + Card + Message + Morph + Relation + Event + View`。
- Room、Board、List、Card、Message 是标准对象，拥有明确主语义、授权和 reducer。
- Morph 是开放对象，用于扩展业务类型和实验类型；facets 是能力 mixin，不是对象身份。
- View 只负责投影定义。View 拥有 query / renderer / layout 等定义真相，但不拥有被投影对象的协作事实。

理由：

- 把 Board、Card、Room、Message 都压成通用 Entity 会损失真实结构语义。
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
- 一个 Organization 可以委托一个或多个 Principal Server / Index / Policy Server。
- 服务器托管关系不自动证明 Organization ownership；官方性必须由 Organization DID 或 `cx.space.organization` 背书。

## 4. Board / List / Card 如何建模？

决策：

- Board 是标准对象。
- List 是 Board 下的标准有序分组对象。
- Card 是 List 下的标准工作项、主题项或推进项。
- 看板拖拽使用 `cx.card.move`、`cx.card.reorder`、`cx.list.reorder` 等标准操作。

关系：

- `board --contains--> list`
- `list --contains--> card`
- Card 的状态、标题、负责人、标签、截止时间等属于 Card 自身或其 facets/profile。

View 只负责把 Board/List/Card 投影成 kanban、table、calendar、gantt 等展示。Board/List/Card 的存在、包含关系、rank 和字段状态仍由标准对象、Relation 与对应 operation 维护。

View 仍然保留为一层独立抽象，因为同一组 Card / Room / Morph 需要被多个团队或个人以不同方式观察，例如 board、table、calendar、timeline、dashboard、review queue。改变观察方式写入 View；改变协作对象事实写入对象或 Relation。

## 5. Card 与 Room 是一个概念吗？

决策：不是。Card 和 Room 严格区分。

Card：

- 面向工作推进、状态、排序、归档、负责人、字段和依赖。
- 可以出现在 Board/List 中。
- 适合表达“一个需要被组织、推进、总结和落地的主题”。

Room：

- 面向持续会话、消息历史、成员、通知、E2EE epoch 和 moderation。
- 不属于 Board/List。
- 适合表达“围绕某个上下文发生的讨论流”。

## 6. Card 如何关联讨论？

决策：

- 一个 Card 可以链接零到多个 Room。
- `links_room` 表示 Card 与 Room 有上下文关联。
- `primary_room` 只表示默认打开或 UI 首选讨论入口。
- Card-to-Room link 不传播权限。

规则：

- Card 可见不代表 linked Room timeline 可读。
- Room 可读不代表 linked Card 可写。
- Room membership、history visibility、E2EE epoch、moderation 和 notification 独立计算。
- 不引入 bound room / inherited room membership 作为 v1 基础语义。

理由：

- 独立 Room 避免复杂的受控 Room 继承模型。
- 一个 Card 可能需要多个讨论 Room，例如设计、法律、客户沟通、事故复盘。
- 权限独立让外部协作和局部讨论更容易组合。

## 7. Morph + facets 的边界是什么？

决策：

- Morph 是开放对象类型。
- facets 是能力 mixin，例如 `assignable`、`schedulable`、`reviewable`、`documentable`。
- Morph 不替代 Room、Board、List、Card、Message。

适合 Morph 的对象：

- memory
- run
- document
- file profile
- poll
- social post
- call
- 外部集成对象
- 领域专用业务对象

不适合 Morph 的对象：

- Room
- Board
- List
- Card
- Message

## 8. Message 是什么？

决策：

- Message 是 Room 内的一等标准对象。
- Message 归属一个 Room。
- Message 的回复、reaction、mention、redaction 通过 Message 事件和 Relation 表达。

Message 不再是通用 Entity 语义标签，也不是协议唯一事实根。

## 9. 授权如何拆分？

决策：

- Space membership 只说明 actor 在 Space 中的基础参与状态。
- Room membership 是局部参与状态，不授予 Space-wide、Board 或 Card 权限。
- Capability action 使用对象域命名，例如 `cx.card.update`、`cx.room.member`、`cx.message.create`、`cx.morph.update`。
- Resource selector 使用 `room`、`board`、`list`、`card`、`message`、`morph`、`object`，不再使用 `entity`。

## 10. 同步和索引如何表达？

决策：

- Event 仍是审计和归约输入；Operation 只作为 SDK / API 语义名称或兼容别名。
- Sync 以 Space 为主要范围，同时支持 Room、Board、Card、Morph 等过滤。
- Index 查询使用 `object_types`、`morph_types`、`facets`。
- `/index/object` 替代 `/index/entity`。
- Relation 使用 `from_ref` / `to_ref`，可连接标准对象、Morph、Actor 和 Space。

## 11. 与 Matrix 的关系

决策：

- Contrix 吸收 Matrix 的 state resolution、auth refs、E2EE、client sync 和 federation 经验。
- Contrix 不继承 Matrix 的 room-first 抽象根。
- Room 在 Contrix 中是一等会话对象，但 Space 才是协作边界，Board/Card/Morph 也是协议一等图节点。

## 12. 当前结论

Contrix v1 当前固定：

1. Space 是协作边界。
2. Room、Board、List、Card、Message 是标准对象。
3. Morph + facets 承担开放扩展。
4. Card 与 Room 严格区分，但可通过 Relation 关联多个 Room。
5. Card-Room link 不传播权限。
6. View 是投影定义，拥有自己的定义真相，但不拥有被投影对象的协作事实。
7. Capability、resource selector、query、sync 和 schema 全部按标准对象 / Morph 模型命名。
