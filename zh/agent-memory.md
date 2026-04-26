# Agent Memory Draft

## 1. 目标

Contrix New 不只是协作协议，也希望成为 AI agent 的长期记忆底座。

但这里的“记忆”不是：

- LLM 当前上下文窗口
- 模型参数
- 某家产品私有向量数据库

Contrix 所说的记忆是：

- 可签名
- 可授权
- 可审计
- 可检索
- 可被人类查看和修订

的协作知识对象。

## 2. 设计原则

### 2.1 协议真相源必须是结构化对象与操作

记忆的 canonical source SHOULD 是：

- item
- comment
- relation
- run
- memory
- attachment

而不是 embedding 或缓存摘要。

### 2.2 记忆必须带来源

任何高价值 memory 都 SHOULD 记录：

- 来源对象
- 来源 run
- 创建者或提取者
- 置信度
- 状态

### 2.3 记忆必须可审阅

如果一个 agent 能写 memory，人类 MUST 能：

- 查看到它
- 审核它
- 驳回它
- 标记过期
- 用新的 memory supersede 它

## 3. 记忆分层

Contrix 建议把 agent 记忆拆成四层。

### 3.1 Working Memory

工作记忆是一次运行中的临时上下文。

它通常：

- 局部
- 短时
- 不稳定
- 不必进入协议

例如：

- 当前 prompt 拼接结果
- 本次工具调用缓存
- 临时计划草稿

### 3.2 Episodic Memory

情景记忆记录“发生了什么”。

在 Contrix 中通常由以下对象表达：

- `run`
- `comment`
- `activity` 投影

### 3.3 Semantic Memory

语义记忆记录“已经知道什么”。

在 Contrix 中由 `memory` 对象承载，尤其适合：

- fact
- decision
- summary
- procedure
- preference

### 3.4 Task Memory

任务记忆记录“接下来要做什么”。

在 Contrix 中通常由以下对象承载：

- `item`
- checklist
- relation
- due dates / assignees

## 4. 为什么不把 memory 简化为向量库

仅靠向量库存在四个问题：

1. 无法稳定表达来源与权限
2. 不适合做审计
3. 难以被人类直接理解和修订
4. 跨实现可移植性差

因此 Contrix 的原则是：

- 向量索引可以存在
- 但只能是 `memory` 的派生检索层

## 5. Memory 生命周期与后置审核队列

如果强制要求所有 Agent 提取的 Memory 都必须由人类手动确认，系统极易陷入扩展性灾难（审批积压或全量盲批）。因此，协议采用**基于置信度的混合流转策略**与**后置审核队列 (After-Commit Audit Queue)**。

建议的标准流程如下：

1. agent 或 human 产生 run / comment / item 更新
2. 某个 agent 或 rule engine 从事件中提取候选知识，评估其置信度 (Confidence)，并生成初始 Memory
3. 节点基于 Policy 评估该 Memory 的流转：
   - 若置信度低于特定阈值或属于高风险知识域，进入 `memory(status=candidate)`，阻塞等待显式确认。
   - 若置信度高且提取自受信任链路，自动流转为 `memory(status=confirmed)`，立即在系统中生效并可被检索。
4. **后置审核**：自动生效的 `confirmed` Memory 会被投递到人类管理者的“审阅队列 (Audit Queue / Review View)”。人类可以如同查阅“未读通知”般进行流览。
5. 若人类在审阅中发现知识偏误，可通过发出 `invalidate` 或 `supersede` 操作直接予以否决或更正。
6. 若事实随着时间推移自然变化，也可由后续的新 `run` 通过 `supersede` 产生版本更迭。

## 6. Memory 状态

初版建议 `memory.status` 至少支持：

- `candidate`
- `confirmed`
- `rejected`
- `invalidated`
- `superseded`

### 6.1 `candidate`

候选记忆，尚未被正式确认。

### 6.2 `confirmed`

可被检索与引用的有效知识。

### 6.3 `rejected`

候选记忆被判定不应进入长期知识。

### 6.4 `invalidated`

曾经有效，但现在已不成立。

### 6.5 `superseded`

被更新版本替代。

## 7. Memory 对象建议字段

示例见 [object-model.md](./object-model.md)。

初版建议重点字段为：

- `memory_kind`
- `subject_ref`
- `source_refs`
- `confidence`
- `status`
- `valid_from`
- `valid_until`
- `supersedes`

## 8. Memory 与 Run 的关系

`run` 用于表达：

- 谁执行了什么
- 过程怎样
- 结果产生了哪些对象

`memory` 用于表达：

- 从这些过程里沉淀出了什么知识

一个合理的结构是：

- `run` 指向 `output_refs`
- `memory.source_refs` 指回 `run`

这样人类可以沿着链路追到知识来源。

## 9. Memory 与人类界面

Contrix 把 memory 当成“人类可审阅对象”，因此 SHOULD 至少支持以下默认投影：

- memory review table
- subject timeline
- knowledge graph
- item side panel memory list

这使得人类能够像管理任务一样管理知识沉淀。

## 10. Memory 查询模式

初版建议至少支持以下查询维度：

- 按 `subject_ref`
- 按 `memory_kind`
- 按 `status`
- 按 `source_refs`
- 按 `created_by`
- 按 `valid_from / valid_until`
- 按 relation graph 扩展检索

## 11. 检索增强与向量库定位

Embedding、reranking、全文索引都可以作为增强层。

但在分布式协议中，实现应遵循：

- 派生索引可重建
- 派生索引不作为唯一真相
- 派生索引必须服从相同 ACL
- **异步物化 (Async Materialization)**：向量数据库 (Vector Store) 在架构中应被视为一种“受信任的 Index 节点”。它通过订阅协议层中处于 `confirmed` 状态的 Op 增量，在本地异步计算 Embedding，从而对外提供高效的高维空间相似度检索。这种架构确保了即使更换向量库技术栈，基于 `memory` Entity 的知识真相源依然稳固。

## 12. 忘记与保留

Contrix 不要求“记住一切直到永远”。

memory 应支持：

- 归档
- 失效
- 被替代
- retention policy

但不应静默物理删除已经进入审计链的知识对象。

## 13. 隐私与最小暴露

Agent memory 往往比普通任务更敏感，因此实现 SHOULD 支持：

- Space 范围隔离
- object 范围隔离
- memory 类型限制
- 对 candidate memory 的更严格读权限

## 14. 初版设计决定

当前草案建议固定：

- run 与 memory 是一等对象
- episodic / semantic / task memory 共存
- embedding 是派生层
- memory 必须带来源
- memory 必须可审阅、可失效、可替代

## 15. 后续待细化

下一轮仍需补充：

- memory 提取标准流程
- candidate -> confirmed 审批状态机
- 向量检索兼容面
- retention / legal hold / export 语义
