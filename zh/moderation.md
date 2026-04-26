# Moderation Draft

## 1. 目标

去中心化协作协议不能仅依赖"好人不会来捣乱"的假设。协议必须提供标准化的**内容审核与用户管理**机制，包括：

- 用户举报不当内容
- 忽略/屏蔽其他用户
- Space 级别的审核策略
- 服务器级别的访问控制

## 2. 设计原则

### 2.1 审核权由 Space Owner 行使

去中心化环境中没有"全网管理员"。内容审核的权限由 Space 的 Capability 体系决定。只有拥有 `space.moderate` 权限的 Actor 才能执行审核操作。

### 2.2 屏蔽是本地行为

用户屏蔽另一个用户是纯本地的客户端行为，不需要广播到网络。协议不应强制"告诉全世界我屏蔽了谁"。

### 2.3 举报留痕但不公开

举报记录应被安全送达 Space 管理员，但不应暴露给被举报人或其他普通成员。

## 3. 内容举报 (Report)

### 3.1 举报操作

用户可以举报 Space 中的任何 Entity（消息、任务、评论等）：

```
POST /api/v1/moderation/report
```

```json
{
  "space_id": "cx:space:01JS0SP000000000000000000",
  "target_ref": "cx:message:01JS1000000000000000000002",
  "reason": "harassment",
  "description": "This message contains targeted personal attacks.",
  "reporter": "did:web:alice.example.com"
}
```

### 3.2 举报原因枚举

| Reason | 说明 |
|--------|------|
| `spam` | 垃圾信息 / 广告 |
| `harassment` | 骚扰 / 人身攻击 |
| `hate_speech` | 仇恨言论 |
| `nsfw` | 不适当的成人内容 |
| `illegal` | 违法内容 |
| `misinformation` | 虚假信息 |
| `other` | 其他原因（需要 `description` 补充说明） |

### 3.3 举报的处理

- 举报会生成一个 `event.moderation.report` 事件，写入 Space Repo
- 该事件仅对拥有 `space.moderate` 权限的 Actor 可见
- 被举报人不会收到通知
- 管理员可以基于举报决定后续行动（警告、删除内容、封禁用户等）

## 4. 用户屏蔽 (Ignore/Block)

### 4.1 屏蔽是 Actor-Private 状态

用户可以屏蔽任意 Actor，屏蔽列表存储在本地或用户的私有 Repo 中：

```json
{
  "ignored_users": {
    "did:web:spammer.example.com": {
      "ignored_at": "2026-04-26T10:00:00Z"
    }
  }
}
```

### 4.2 屏蔽行为

客户端在渲染时：
- SHOULD 隐藏被屏蔽用户的消息
- SHOULD 不显示被屏蔽用户的 Typing 和 Presence 状态
- SHOULD 不为被屏蔽用户的消息生成通知
- MUST NOT 从网络层面丢弃被屏蔽用户的 Op（这些 Op 对其他成员仍然有效）

## 5. Space 审核工具

### 5.1 内容删除

管理员可以通过 `cx.message.redact` 操作撤回任意成员的消息：
- 需要 `space.moderate` 权限
- 撤回会产生 tombstone，不可逆
- 审计视图中仍可看到撤回记录

### 5.2 用户封禁

管理员通过 `cx.membership.ban` 操作封禁用户（详见 `object-model-core.md` 的成员与 policy 语义）。封禁后：
- 被封禁用户无法重新加入该 Space
- 其未来的 Op 提交将被 Relay 拒绝
- 是否隐藏其历史内容由 Space Policy 决定

### 5.3 消息审核队列

Space SHOULD 支持审核队列 (Moderation Queue) 视图，汇集所有举报记录。建议使用标准 View 机制：

```json
{
  "view_type": "moderation_queue",
  "query": {
    "entity_types": ["moderation_report"],
    "filter": [
      { "field": "fields.status", "op": "eq", "value": "pending" }
    ]
  }
}
```

## 6. 服务器级访问控制

### 6.1 Server ACL

Relay 和 Index 节点可以配置服务器级别的 ACL，控制哪些域的联邦请求被接受或拒绝：

```json
{
  "server_acl": {
    "allow": ["*"],
    "deny": [
      "spam-node.example.com",
      "*.malicious.example.net"
    ]
  }
}
```

规则评估顺序：先检查 `deny` 列表，再检查 `allow` 列表。支持 glob 通配符。

### 6.2 与联邦协议的关系

Server ACL 在联邦层（参见 `federation.md`）起作用。当 Relay 收到来自被 deny 的域的 `push-ops` 请求时，SHOULD 立即返回 `403 CapabilityDenied`。

## 7. 后续待细化

- 自动化审核（基于 AI 的内容分类与标记）
- 上诉流程（被封禁用户的申诉机制）
- 跨 Space 的全局封禁列表（联邦级黑名单共享）
- 审核操作的不可抵赖性日志
