# Design Questions And Decisions

## 1. 目的

这份文档先把协议必须回答的问题列出来，再给出统一决策。

原因很简单：  
如果不先把“协议到底要解决哪些问题”列清楚，后面的对象模型、同步、权限、视图都会各说各话，最终会退回到“像看板，又像聊天，又不像协议”的状态。

## 2. 问题清单与统一决策

### 2.1 协议的根模型到底是什么？

问题：

- 是 chat-first？
- 是 board-first？
- 是 database-first？

决策：

- Contrix 采用 **space-first + entity-graph-first + event-first**。
- chat、topic、kanban、tree、graph、gantt 都是同一协作图上的标准投影。
- 协议根对象不是房间、消息、任务或看板，而是 `Space + Actor + Entity + Relation + Event + View`。

### 2.2 如果要展示成看板，底层数据应该怎么设计？

问题：

- 看板的数据是“列和卡片”吗？
- 还是有更稳定的底层模型？

决策：

- 看板底层不是“列数组 + 卡片数组”。
- 底层应是 `Entity + Relation + View`。
- `board`、`collection`、`task/card` 都是标准 `entity_type`。
- board 包含 collection、collection 包含 task/card，使用 `contains` Relation。
- Kanban 只是 `kind = "kanban"` 的一种标准投影。

### 2.3 如果要支持聊天模式或话题模式，应该怎么设计？

问题：

- 是复用 comment 就够了？
- 还是需要正式的会话对象？

决策：

- 协议将 `channel/topic/message` 定义为标准 `entity_type`，而不是新的协议根。
- `channel` 表示长期会话空间。
- `topic` 表示线程或话题，可通过 Relation 挂在 `space / board / task / run / memory` 上。
- `message` 表示时间线消息。
- `comment` 仍然保留为标准 Entity 类型，但定位为对象上的 durable review/note，而不是通用聊天时间线。
- 归属、回复、引用、提及必须落成结构化 Relation。

### 2.4 看板和聊天如何打通？

问题：

- item 的讨论是 comment 还是 chat thread？
- board 和 topic 是什么关系？

决策：

- task Entity 可以通过 Relation 关联自己的默认 `topic`。
- board 可以通过 Relation 关联一个或多个 `channel` 和 `topic`。
- 一个 `topic` 可以锚定到 `task / run / memory / board / document`。
- 人类可以在 kanban view 里看 task，同时点进同一个 task 的 thread/chat view。

### 2.5 支持 `@user` 吗？

问题：

- 只靠正文文本里的 `@alice` 行不行？
- Handle 改了怎么办？

决策：

- 支持 `@user`，也支持 `@object`。
- UI 可以使用 `@handle` 或 `@title` 输入。
- 协议层 canonical 存储必须落为结构化 `mentions` Relation。
- principal mention 一律引用 DID。
- object mention 一律引用 stable entity ID。
- 即使 handle 后续迁移，历史 mention 仍指向原 DID。

### 2.6 支持消息编辑吗？

问题：

- 用户发错了能改吗？

决策：

- 支持编辑。
- 编辑不覆盖原始历史，而是通过 `message.revise` 形成 revision chain。
- 默认视图展示最新可见 revision。
- 审计视图可追溯原始 revision。

### 2.7 支持撤回吗？

问题：

- 去中心化系统里能不能真的撤回？

决策：

- 支持“逻辑撤回”，通过 `redact / withdraw` 语义实现。
- 默认人类视图里应显示“消息已撤回”或等效 tombstone。
- 协议不承诺已传播副本在全球范围内被物理抹除。
- 如需更强删除效果，应依赖 retention policy、附件 key 撤销或存储端 GC。

### 2.8 信息如何同步？

问题：

- 看板同步和聊天同步是一套还是两套？

决策：

- 一套协议，多种同步 profile。
- actor 先写自己的 repo。
- Principal Server / Sync Service 同步 Space 范围授权操作。
- index 物化当前态和查询。
- board、chat、topic、tree、graph 模式只是订阅过滤和投影方式不同。

### 2.9 历史如何回补？

问题：

- 聊天要最近消息窗口
- 看板要当前态
- 话题要可回溯

决策：

- 首次恢复优先走 snapshot + op 增量。
- message/topic 支持 cursor + backfill。
- board 默认同步当前态 + 最近相关讨论摘要。
- chat 默认同步频道元数据 + 最近窗口 + live 增量。

### 2.10 冲突如何解决？

问题：

- 两个人同时改标题怎么办？
- 同时拖动卡片怎么办？
- 同时编辑消息和撤回消息怎么办？

决策：

- 统一基于固定 reducer 规则收敛。
- 标量字段采用 LWW by causal order。
- 集合字段采用 OR-Set。
- 排序采用 fractional indexing。
- message 是 append-only timeline。
- `message.revise` 形成 revision chain。
- `message.redact` 在默认视图中优先于 revision。

### 2.11 权限如何统一？

问题：

- 看板编辑权、消息发送权、撤回权、频道管理权是不是同一个东西？

决策：

- 一律归入 capability。
- 至少区分：
  - board/item actions
  - channel/topic/message actions
  - moderation/redaction actions
  - run/memory actions
- `edit_own_message` 与 `redact_any_message` 必须分开。

### 2.12 AI agent 在这里扮演什么角色？

问题：

- agent 只是插件，还是协议参与者？

决策：

- agent 是一等 principal。
- agent 可以被授予有限 board/message/memory 权限。
- agent 产生的对话、输出、决策摘要可以沉淀为 `run` 与 `memory`。
- message、comment、topic 都可以成为 memory 提取来源。

## 3. 最优解的整体规划

综合以上问题，当前协议采用如下整体方案：

1. 根模型固定为 `Space + Actor + Entity + Relation + Event + View`。
2. 看板采用标准 Entity 类型 `board/collection/task` + `contains/belongs_to` Relation + `kanban` View。
3. 聊天/话题采用标准 Entity 类型 `channel/topic/message` + `belongs_to/replies_to/mentions` Relation + `chat/thread` View。
4. `comment` 继续保留为对象级 durable 说明；`message` 负责时间线会话。
5. `@mention` 统一采用结构化 DID/entity ref，并落成 `mentions` Relation。
6. 编辑采用 revision chain；撤回采用 redaction/tombstone。
7. 同步统一走 repo-first + Principal Server sync + index，只是 profile 不同。
8. 冲突统一由 reducer 固定规则解决，而不是让客户端自由发挥。
9. 权限统一收敛进 capability，不再靠隐式角色猜测。

## 4. 写回协议的范围

基于这份问题清单，后续文档应当明确覆盖：

- [object-model-core.md](../models/object-model-core.md) 与 [object-model-standard.md](../models/object-model-standard.md)  
  固定 `Space/Actor/Entity/Relation/Event/View`，并定义 board/chat/task/message/run/memory 的语义层映射。
- [conversation-model.md](../models/conversation-model.md)  
  补 mention/edit/redaction/reaction 的交互层定义。
- [operations-sync.md](../sync/operations-sync.md)  
  补 board/chat/topic 的同步模式与冲突收敛。
- [capabilities.md](../authz/capabilities.md)  
  补消息、话题、频道、撤回、moderation 动作。
- [views.md](../models/views.md)  
  补 `chat/forum/thread/inbox` 等标准视图。

## 5. 当前结论

Contrix 最合理的方向不是在“看板协议”和“聊天协议”之间二选一。  
最合理的方向是：

- 用统一 Entity/Relation/Event 图表达工作与沟通
- 用统一同步模型分发它们
- 用统一权限模型控制它们
- 用多种视图把它们展示给人和 agent
