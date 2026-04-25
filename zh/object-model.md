# Object Model Draft

## 1. 目标

Contrix New 的对象模型必须同时支持：

- 人类团队协作
- 多组织协作
- 看板工作流
- 聊天与话题讨论
- AI agent 执行轨迹
- AI agent 长期记忆

因此协议必须围绕 **工作对象图** 来设计，而不是围绕“房间事件”或“列和卡片”这样的单一 UI 模式。

## 2. 设计原则

### 2.1 稳定 ID 与显示名称分离

对象引用 MUST 使用稳定 ID，不得使用：

- 标题
- 显示名称
- Handle
- URL 路径

### 2.2 对象属于 workspace，而不是属于某个 UI

同一个对象可以同时进入多个 view，也可以同时被人类和 agent 使用。

### 2.3 当前态来自 reducer，而不是中心库覆盖

对象当前态是从授权操作集合归约得到的，而不是靠单一中心数据库静默覆盖。

### 2.4 看板与聊天共用同一对象图

看板、thread、chat、forum 都应该是同一对象图的标准投影，而不是两套互不兼容的数据模型。

## 3. ID 规范

初版建议对象 ID 使用带前缀的稳定字符串，随机部分建议使用 ULID。

示例：

- `cx:ws:<ulid>`
- `cx:board:<ulid>`
- `cx:col:<ulid>`
- `cx:item:<ulid>`
- `cx:comment:<ulid>`
- `cx:rel:<ulid>`
- `cx:blob:<ulid>`
- `cx:channel:<ulid>`
- `cx:topic:<ulid>`
- `cx:message:<ulid>`
- `cx:view:<ulid>`
- `cx:run:<ulid>`
- `cx:mem:<ulid>`
- `cx:schema:<ulid>`
- `cx:policy:<ulid>`
- `cx:invite:<ulid>`
- `cx:read:<ulid>`

## 4. 通用对象元数据

所有对象 SHOULD 共享以下基础字段：

```json
{
  "id": "cx:item:01JS0000000000000000000000",
  "kind": "item",
  "workspace_id": "cx:ws:01JS0000000000000000000000",
  "created_at": "2026-04-22T08:00:00Z",
  "created_by": "did:web:alice.example.com",
  "updated_at": "2026-04-22T08:05:00Z",
  "updated_by": "did:web:agent.example.com",
  "archived": false,
  "tombstoned": false,
  "version": 7
}
```

## 5. 核心对象集合

当前草案的首批核心对象为：

- workspace
- board
- collection
- item
- comment
- relation
- attachment
- channel
- topic
- message
- view
- run
- memory
- schema
- policy
- invite
- read_marker

其中：

- `item` 是主要工作对象
- `comment` 是对象级 durable note
- `channel/topic/message` 是会话对象
- `view` 是投影
- `run` 是执行轨迹
- `memory` 是长期知识沉淀
- `schema` 是字段与对象类型约束
- `policy` 是保留、可见性、加密与 moderation 默认策略
- `invite` 是加入 workspace 的显式引导对象
- `read_marker` 是 actor 私有但可同步的已读状态

## 6. Workspace

Workspace 是复制与权限边界。

它定义：

- 默认复制范围
- 默认权限范围
- 默认 relay/index/blob
- 默认 schema/policy

示例：

```json
{
  "id": "cx:ws:01JS0WS000000000000000000",
  "kind": "workspace",
  "owner": "did:web:acme.example.com",
  "name": "Acme Delivery Workspace",
  "description": "Cross-org product delivery and agent automation workspace",
  "visibility": "private",
  "default_policy_ref": "cx:policy:01JS...",
  "default_schema_ref": "cx:schema:01JS..."
}
```

## 7. Board

Board 是共享工作上下文，不是协议最顶层对象。

它适合表达：

- 产品项目
- 交付流
- Incident 响应板
- agent review queue

示例：

```json
{
  "id": "cx:board:01JS0BD000000000000000000",
  "kind": "board",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "name": "Release Readiness",
  "description": "Shared launch board for human and agent coordination",
  "status_field": "status",
  "rank_field": "rank",
  "default_view_id": "cx:view:01JS0VW000000000000000000",
  "default_channel_id": "cx:channel:01JS1000000000000000000000",
  "field_schema_ref": "cx:schema:01JS0SC000000000000000000"
}
```

## 8. Collection

Collection 是通用分组对象，不等于 Kanban 专属列。

它可以表达：

- lane
- list group
- folder
- query segment

示例：

```json
{
  "id": "cx:col:01JS0CL000000000000000000",
  "kind": "collection",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "board_id": "cx:board:01JS0BD000000000000000000",
  "name": "Needs Review",
  "collection_kind": "lane",
  "rank": "m",
  "state_token": "needs_review"
}
```

## 9. Item

Item 是协议中最重要的业务对象。

### 9.1 语义

它代表“可协作处理的工作单元”，而不是单纯的 UI 卡片。

### 9.2 建议字段

```json
{
  "id": "cx:item:01JS0IT000000000000000000",
  "kind": "item",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "board_id": "cx:board:01JS0BD000000000000000000",
  "container_id": "cx:col:01JS0CL000000000000000000",
  "item_type": "task",
  "title": "Finalize onboarding copy review",
  "body": "Coordinate product, design, legal, and agent-generated suggestions.",
  "status": "in_progress",
  "rank": "mV",
  "priority": "high",
  "assignees": [
    "did:web:bob.example.com",
    "did:web:agent.copy.example.com"
  ],
  "discussion_topic_id": "cx:topic:01JS1000000000000000000001",
  "labels": [
    "launch",
    "copy"
  ],
  "due_at": "2026-04-28T00:00:00Z",
  "visibility": "workspace"
}
```

### 9.3 `item_type`

初版建议至少支持：

- `task`
- `issue`
- `goal`
- `request`
- `decision`
- `note`

## 10. Comment

Comment 是对象上的 durable 说明对象，不应只被视为 message 的别名。

它适合：

- 审批意见
- 变更说明
- 审计性注释
- review note

示例：

```json
{
  "id": "cx:comment:01JS0CM000000000000000000",
  "kind": "comment",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "target_ref": "cx:item:01JS0IT000000000000000000",
  "thread_root_ref": "cx:comment:01JS0CM000000000000000000",
  "reply_to_ref": null,
  "body": "Agent proposed three alternative copy variants. Human review pending."
}
```

## 11. Relation

Relation 表达对象之间的语义链接。

建议字段：

```json
{
  "id": "cx:rel:01JS0RL000000000000000000",
  "kind": "relation",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "from_ref": "cx:item:01JS0IT000000000000000000",
  "to_ref": "cx:mem:01JS0ME000000000000000000",
  "relation_type": "derived_from",
  "directed": true
}
```

## 12. Attachment

Attachment 分为元数据对象和 blob 内容。

示例：

```json
{
  "id": "cx:blob:01JS0AT000000000000000000",
  "kind": "attachment",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "target_ref": "cx:item:01JS0IT000000000000000000",
  "blob_cid": "bafy...",
  "name": "review-notes.pdf",
  "mime_type": "application/pdf",
  "size": 129034,
  "sha256": "base64url..."
}
```

## 13. Channel

Channel 是长期会话空间。

它适合：

- 团队聊天
- board 讨论区
- agent 广播流
- 公告流

示例：

```json
{
  "id": "cx:channel:01JS1000000000000000000000",
  "kind": "channel",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "name": "release-chat",
  "description": "General release coordination chat",
  "channel_kind": "chat",
  "visibility": "workspace",
  "default_topic_mode": "inline"
}
```

## 14. Topic

Topic 是线程或话题对象。

它可以：

- 属于某个 channel
- 或直接锚定到某个协作对象

示例：

```json
{
  "id": "cx:topic:01JS1000000000000000000001",
  "kind": "topic",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "channel_id": "cx:channel:01JS1000000000000000000000",
  "anchor_ref": "cx:item:01JS0IT000000000000000000",
  "topic_kind": "thread",
  "title": "Legal review follow-up",
  "status": "open"
}
```

## 15. Message

Message 是 channel 或 topic 时间线里的原子消息。

示例：

```json
{
  "id": "cx:message:01JS1000000000000000000002",
  "kind": "message",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "channel_id": "cx:channel:01JS1000000000000000000000",
  "topic_id": "cx:topic:01JS1000000000000000000001",
  "sender": "did:web:alice.example.com",
  "reply_to_ref": null,
  "body": {
    "format": "markdown",
    "text": "@bob 请确认这个 item 的 legal 风险。"
  },
  "mentions": [
    {
      "kind": "principal",
      "ref": "did:web:bob.example.com"
    },
    {
      "kind": "object",
      "ref": "cx:item:01JS0IT000000000000000000"
    }
  ],
  "revision_root": "cx:message:01JS1000000000000000000002",
  "visible_state": "active"
}
```

协议层的 `mentions` 必须使用 DID 或 stable object ref，而不是只存裸文本 `@xxx`。

## 16. View

View 是独立对象，但它的详细行为见 [views.md](./views.md)。

它定义：

- 查询范围
- 分组逻辑
- 排序规则
- 展示字段
- 布局建议

View 是投影，不是真相。

## 17. Run

Run 是 agent 或自动化执行轨迹对象。

示例：

```json
{
  "id": "cx:run:01JS0RN000000000000000000",
  "kind": "run",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "board_id": "cx:board:01JS0BD000000000000000000",
  "agent_id": "did:web:agent.copy.example.com",
  "triggered_by": "did:web:alice.example.com",
  "goal_ref": "cx:item:01JS0IT000000000000000000",
  "status": "running",
  "input_refs": [
    "cx:item:01JS0IT000000000000000000"
  ],
  "output_refs": [],
  "summary": null
}
```

## 18. Memory

Memory 是长期知识对象，不等于 comment，也不等于向量块。

示例：

```json
{
  "id": "cx:mem:01JS0ME000000000000000000",
  "kind": "memory",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "subject_ref": "cx:item:01JS0IT000000000000000000",
  "memory_kind": "decision",
  "title": "Copy variants require legal approval before publishing",
  "body": "Team decided that all onboarding copy touching billing must be reviewed by legal.",
  "source_refs": [
    "cx:comment:01JS0CM000000000000000000",
    "cx:message:01JS1000000000000000000002",
    "cx:run:01JS0RN000000000000000000"
  ],
  "confidence": 0.92,
  "status": "confirmed"
}
```

## 19. Schema 与自定义字段

Contrix 必须支持自定义字段，但不建议允许完全无约束 JSON 扩展。

建议引入：

- `cx:schema:<id>`

由 workspace 或 board 引用。

示例：

```json
{
  "id": "cx:schema:01JS0SC000000000000000000",
  "kind": "schema",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "name": "default-item-schema",
  "applies_to": [
    "item"
  ],
  "version": 3,
  "fields": [
    {
      "name": "priority",
      "type": "enum",
      "required": false,
      "options": ["low", "medium", "high"]
    },
    {
      "name": "due_at",
      "type": "datetime",
      "required": false
    }
  ]
}
```

建议字段类型：

- `text`
- `number`
- `bool`
- `date`
- `datetime`
- `enum`
- `multi_enum`
- `principal_ref`
- `object_ref`
- `url`

Schema SHOULD 显式声明：

- `applies_to`
- `version`
- `fields`
- `migration_notes`

这样 reducer、view 与导入导出逻辑在 schema 升级时才可解释。

## 20. Policy

协议中已经引用 `policy`，因此它必须是正式对象，而不是实现私货。

示例：

```json
{
  "id": "cx:policy:01JS0PL000000000000000000",
  "kind": "policy",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "name": "workspace-default-policy",
  "retention": {
    "messages_days": 3650,
    "candidate_memories_days": 90
  },
  "default_visibility": "workspace",
  "redaction_mode": "tombstone",
  "encryption_profile": "workspace-envelope-v1",
  "allow_external_relays": true
}
```

`policy` SHOULD 至少覆盖：

- retention
- default visibility
- redaction display
- encryption profile
- relay / blob / export defaults

## 21. Invite

去中心化协作里，“别人如何加入 workspace”不能只靠产品私有链接。

Contrix 应支持显式 `invite` 对象：

```json
{
  "id": "cx:invite:01JS0IV000000000000000000",
  "kind": "invite",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "issuer": "did:web:acme.example.com",
  "subject_did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "subject_handle": "alice.example.com",
  "proposed_role": "contributor",
  "proposed_grant_refs": [
    "cx:grant:01JS0GR000000000000000000"
  ],
  "expires_at": "2026-05-01T00:00:00Z",
  "status": "pending"
}
```

`invite` 的语义应是：

- 它是加入引导对象
- 它本身不等于 capability grant
- 接受 invite 后，相关 grant 才进入生效集合

## 22. Read Marker

人类友好的协作系统必须有 durable 的已读状态，否则 inbox / thread / chat 都无法稳定收敛。

建议引入 actor-private 的 `read_marker`：

```json
{
  "id": "cx:read:01JS0RD000000000000000000",
  "kind": "read_marker",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "owner": "did:web:alice.example.com",
  "scope_kind": "channel",
  "scope_ref": "cx:channel:01JS1000000000000000000000",
  "last_seen_message_ref": "cx:message:01JS1000000000000000000002",
  "last_seen_hlc": "2026-04-22T08:31:03.221Z-0007-did:web:alice.example.com",
  "updated_at": "2026-04-22T08:40:00Z"
}
```

`read_marker` SHOULD：

- 默认只对 owner 可见
- 可按 channel / topic / inbox / view 设 scope
- 作为 durable state 在多设备间同步

## 23. Notification

通知对人类界面是必需的，但不应成为协议真相源对象。

因此初版建议：

- `notification` 是派生 inbox 对象
- 它由 message mention、assignment、invite、run failure、memory review 等事件派生
- 它可以被 index 或 relay 物化，但 canonical truth 仍是底层 source object 与 op

示例：

```json
{
  "id": "cx:notif:01JS0NF000000000000000000",
  "actor": "did:web:alice.example.com",
  "notification_kind": "mention",
  "source_ref": "cx:message:01JS1000000000000000000002",
  "target_ref": "cx:topic:01JS1000000000000000000001",
  "delivery_state": "unread",
  "created_at": "2026-04-22T08:31:05Z"
}
```

## 24. 派生数据

以下内容不应作为 canonical truth object 保存：

- embedding 向量
- 搜索倒排索引
- UI 本地布局缓存
- 临时排序缓存
- LLM 上下文窗口
- typing/presence 瞬时状态

这些都属于派生层或临时信号层。

## 25. 初版设计决定

当前草案建议固定：

- 所有对象显式归属 workspace
- `item` 是主业务对象
- `channel/topic/message` 是正式会话对象
- `comment` 是 durable 对象级说明
- `view` 是投影定义
- `run` 是执行轨迹对象
- `memory` 是长期知识对象
- `schema/policy` 是正式对象
- `invite` 是显式加入引导
- `read_marker` 是 durable actor-private state
- `notification` 是派生对象，不是 canonical truth

## 26. 后续待细化

下一轮仍需明确：

- schema object 正式格式
- policy object 的正式 schema
- invite / join / leave 状态机
- read marker 与 notification 的正式查询面
- checklist 标准结构
- message 富文本 block 结构
- topic/channel 的历史可见性规则
- memory supersession / invalidation 语义
