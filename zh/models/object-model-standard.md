# Standard Object Types

## 1. 目标

本文定义 Contrix 初版标准 Entity 类型。  
这些类型是语义层约定，不改变核心模型：所有对象仍然是 Entity，所有跨对象语义仍然使用 Relation。

核心字段类型、必填性和通用约束见 `data-structures.md`。本文只定义标准 `entity_type` 的业务语义、常用字段和推荐关系。

## 2. Board

`board` 表示可视化工作台。

看板列有两种标准来源：

- 字段分组列：列来自 task 的 `fields.status` 等字段枚举值。
- Collection 列：列来自 `entity_type="collection"` 的 Entity，并通过 `contains` Relation 挂到 board。

看板不会自动显示 Space 中所有对象。只有被 Kanban View 的 `query` 选中、通过权限裁剪、并符合该 View card 规则的 Entity 才显示为卡片。其他 Entity / Relation / Event 仍可作为底层数据、关系输入或审计输入存在。

具体投影规则见 `views.md` 的 Kanban 章节。

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
    "default_view_kind": "kanban"
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

## 13. Social Types

社交能力作为标准语义扩展定义，详细规则见 `social-graph.md`。

### 13.1 Social Post

`social_post` 表示个人或组织发布到 feed 的内容。它可以是公开广播、组织公告或朋友圈内容。

常用字段：

- `author`
- `content`
- `attachments`
- `audience_ref`
- `reply_policy`
- `reshare_policy`

常见关系：

- `belongs_to` -> social_feed
- `replies_to` -> social_post
- `reposts` -> social_post
- `quotes` -> social_post
- `mentions` -> actor / entity

### 13.2 Social Feed

`social_feed` 表示个人主页、组织公告、项目动态、公开时间线等发布入口或投影源。

### 13.3 Social Circle

`social_circle` 表示发布者维护的受众集合，例如朋友圈、亲友圈、内部成员圈。Circle membership 默认私有或受限可见。

## 14. Schema Evolution

标准类型演进 MUST 遵守：

- 新字段优先 optional
- 旧字段不得静默改变语义
- reducer 和客户端 MUST 保留未知字段
- UI 遇到未知 Entity type SHOULD 降级为 generic entity card
- 标准类型不得阻止 Space 定义自定义 Entity type

## 15. 规范性引用

- 标准 Relation cardinality 按本文件各类型语义、`data-structures.md` 的 Relation 字段和业务 profile 执行；未声明多重关系时，active relation MUST 以 `(relation_kind, from_ref, to_ref)` 收敛为单条。
- Content block registry 见 `content-types.md`；未知 content block 必须按降级规则保留和展示。
- Task status profile 使用 `todo`、`in_progress`、`blocked`、`review`、`done`、`archived` 作为 v1 基础集合；Space schema 可增加自定义状态，但不得改变基础状态语义。
- Poll result reducer vector 必须按 event 集合归约，不能只信任计数字段；匿名投票的明文选择不得进入未授权 Index。
- Social post / feed / circle schema 见 `social-graph.md` 和 `data-structures.md`；受众集合、转发、索引和回复权限必须由 Audience Policy 控制。
