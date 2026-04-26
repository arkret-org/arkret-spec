# Standard Object Types Draft

## 1. 目标

本文定义 Contrix 初版标准 Entity 类型。  
这些类型是语义层约定，不改变核心模型：所有对象仍然是 Entity，所有跨对象语义仍然使用 Relation。

## 2. Board

`board` 表示可视化工作台。

常见关系：

- `contains` -> `task`
- `contains` -> `collection`
- `has_default_view` -> `view`

示例：

```json
{
  "entity_type": "board",
  "title": "Product Launch",
  "fields": {
    "default_view_type": "kanban"
  }
}
```

## 3. Task

`task` 表示可分配、可排期、可完成的工作项。

常用字段：

- `status`
- `priority`
- `rank`
- `due_at`
- `labels`

常见关系：

- `assigned_to` -> actor
- `depends_on` -> task
- `blocks` -> task
- `belongs_to` -> board / collection
- `has_topic` -> topic

## 4. Message

`message` 表示一条可讨论内容。  
Message 可以存在于 channel、topic、thread 或 task discussion 中。

常用字段：

- `content`
- `format`
- `attachments`
- `edited_at`
- `redacted`

常见关系：

- `belongs_to` -> channel / topic
- `replies_to` -> message
- `mentions` -> actor / entity
- `references` -> entity

## 5. Topic

`topic` 表示讨论线索。

Topic 可挂接到：

- channel
- task
- document
- run
- memory

常见关系：

- `contains` -> message
- `attached_to` -> entity

## 6. Channel

`channel` 表示持续会话容器。

Channel 不拥有消息真相，只是 topic / message 的组织入口。

## 7. Document

`document` 表示可协作编辑或引用的文档对象。

文档正文 MAY 存储为：

- inline structured content
- blob reference
- CRDT snapshot
- external document binding

## 8. File

`file` 表示 blob 的协作元数据。

内容本身 SHOULD 使用 blob service 存储，并通过 content hash 校验。

## 9. Memory

`memory` 表示可由人或 agent 读取、引用、更新的长期记忆。

Memory MUST 记录来源：

- `source_event_id`
- `source_entity_id`
- `extracted_by`
- `confidence`
- `expires_at`

## 10. Run

`run` 表示 agent、automation 或 CI 的一次执行。

常用关系：

- `produced` -> entity / memory
- `used` -> tool / input
- `triggered_by` -> actor / event
- `has_log` -> message / document

Run SHOULD 记录：

- input
- output
- tool calls
- approval refs
- error state
- responsible actor

## 11. Actor Profile

`actor_profile` 是 Actor 在协作图中的 Entity 镜像。

它用于：

- mention
- assignment
- display
- team membership view

Actor Profile 不替代 DID，也不成为权限主键。

## 12. Poll

`poll` 表示投票或决策收集。

应支持：

- single choice
- multiple choice
- deadline
- visibility policy
- anonymous result policy

投票结果 SHOULD 作为 event 集合归约，而不是只更新单一计数字段。

## 13. Schema Evolution

标准类型演进 MUST 遵守：

- 新字段优先 optional
- 旧字段不得静默改变语义
- reducer 和客户端 MUST 保留未知字段
- UI 遇到未知 Entity type SHOULD 降级为 generic entity card
- 标准类型不得阻止 Space 定义自定义 Entity type

## 14. 待细化

- 每个标准 Entity 的 JSON Schema
- 标准 Relation cardinality
- content block registry
- task status profile
- poll result reducer vector
