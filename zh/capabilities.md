# Capability Model Draft

## 1. 目标

Contrix New 的权限模型采用 capability 思路，而不是只依赖成员关系或模糊角色。

这样做的原因是：

- 跨组织协作很常见
- board、chat、topic、memory 的动作集不同
- agent 必须被精细授权
- 授权变化必须可审计

## 2. 基本原则

### 2.1 授权主体 SHOULD 是稳定 principal

grant 的 `issuer` 与 `subject` SHOULD 使用 DID。

### 2.2 权限必须显式表达

不要依赖以下隐式假设：

- 进入 workspace 就拥有全部能力
- 能编辑 item 就一定能撤回别人的消息
- channel owner 天然拥有全量管理权

### 2.3 权限判定基于当时有效的 capability 集

操作是否合法，应由该时点有效 grant 集决定。

## 3. Grant 对象

示例：

```json
{
  "grant_id": "cx:grant:01JS0GR000000000000000000",
  "workspace_id": "cx:ws:01JS0WS000000000000000000",
  "issuer": "did:web:acme.example.com",
  "subject": "did:web:agent.copy.example.com",
  "resource": {
    "kind": "board",
    "refs": [
      "cx:board:01JS0BD000000000000000000"
    ]
  },
  "actions": [
    "read",
    "edit_item",
    "create_run",
    "write_memory"
  ],
  "constraints": {
    "expires_at": "2026-04-30T00:00:00Z",
    "fields_write_allow": [
      "title",
      "body",
      "labels",
      "due_at"
    ],
    "max_delegation_depth": 0
  }
}
```

## 4. Resource Selector

初版建议支持以下 `kind`：

- `workspace`
- `board`
- `collection`
- `item`
- `comment`
- `channel`
- `topic`
- `message`
- `view`
- `run`
- `memory`

## 5. 动作集合

### 5.1 通用动作

- `discover`
- `read`
- `read_metadata`
- `read_content`
- `create`
- `update`
- `archive`
- `restore`

### 5.2 看板与对象动作

- `create_item`
- `edit_item`
- `move_item`
- `reorder_item`
- `assign_item`
- `comment`
- `manage_relations`
- `manage_attachments`
- `manage_views`

### 5.3 会话动作

- `read_history`
- `send_message`
- `react`
- `edit_own_message`
- `edit_any_message`
- `redact_own_message`
- `redact_any_message`
- `manage_channels`
- `manage_topics`

### 5.4 Run 与 Memory 动作

- `create_run`
- `update_run`
- `write_memory`
- `confirm_memory`
- `invalidate_memory`
- `curate_memory`

### 5.5 管理动作

- `manage_workspace`
- `manage_board`
- `manage_schema`
- `manage_capabilities`
- `manage_policy`

### 5.6 服务动作

- `relay_ops`
- `index_workspace`
- `store_blobs`

## 6. Constraints

初版建议支持：

- `expires_at`
- `not_before`
- `fields_write_allow`
- `fields_write_deny`
- `item_type_allow`
- `memory_kind_allow`
- `allowed_channel_refs`
- `message_edit_window`
- `max_delegation_depth`
- `rate_limit`
- `approval_required`

## 7. Agent 安全授权

给 agent 授权时 SHOULD 默认：

- 只授予明确 workspace / board / channel 范围
- 只授予所需动作
- 只授予有限时效
- 只授予允许的对象种类
- 尽量限制可写字段与可写 memory 类型

高风险模式包括：

- 给 agent 长期全 workspace 管理权
- 让 agent 直接继承 human owner 全权限
- 不设过期时间
- 不保留 run 审计链

## 8. Delegation

委托表示 subject 可以将其能力的一部分再授予第三方。

若 `max_delegation_depth = 0`，则不可继续委托。  
若大于 0，则：

- 每次再授权 MUST 递减深度
- 再授权不得扩大原始资源范围和动作范围
- 委托链 MUST 可验证

## 9. Revocation

撤销必须是显式操作，而不是删除 grant 记录。

示例：

```json
{
  "type": "cx.capability.revoke",
  "body": {
    "grant_ref": "cx:grant:01JS0GR000000000000000000",
    "reason": "contract ended"
  }
}
```

## 10. Role 只是 bundle

产品层可以提供：

- `workspace_admin`
- `board_manager`
- `contributor`
- `observer`
- `channel_moderator`
- `agent_writer`

但这些 role 在协议层只是 capability bundle，不是主语义。

## 11. 读权限与可发现性

读权限不只是“能不能 fetch 内容”，还包括：

- 能否发现对象存在
- 能否看到消息历史
- 能否看到被撤回消息的元信息
- 能否读取附件内容

初版至少区分：

- `discover`
- `read_metadata`
- `read_content`
- `read_history`

## 12. 会话场景下的权限建议

初版建议最少区分：

- 普通发送消息
- 编辑自己的消息
- 编辑任意消息
- 撤回自己的消息
- 撤回任意消息
- 管理 channel/topic

这能避免把“撤回别人的消息”错误地和“能发消息”混成一种权限。

## 13. 决策执行位置

权限检查不应只在客户端发生。

建议至少在以下位置执行：

- client 预检查
- repo 接收写入时
- relay 分发前
- index 返回查询前
- blob store 下发内容前

## 14. 最小权限判定算法

给定一个操作，节点至少应：

1. 解析 actor DID
2. 验证签名链
3. 查找当时有效 grant 集
4. 展开 delegation
5. 判断 resource selector 是否覆盖 target
6. 判断 action 是否匹配
7. 判断 constraints 是否满足
8. 应用 revoke 和 superseding 规则

## 15. 初版设计决定

当前草案建议固定：

- 权限采用 capability 模型
- 看板、会话、memory、run 都使用统一 grant 体系
- `edit_own_message` 与 `redact_any_message` 分开
- agent 使用窄权限、短时效、可审计授权

## 16. 后续待细化

下一轮仍需明确：

- resource selector 正式语法
- constraint schema
- moderation policy 与 capability 的配合方式
