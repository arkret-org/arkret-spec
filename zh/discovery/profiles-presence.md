# Profiles And Presence Draft

## 1. 目标

协作协议中，用户需要有可展示的身份信息（显示名、头像、状态消息），其他参与者也需要知道对方的在线状态。本规范定义了：

- Actor Profile 的标准字段与更新机制
- 在线状态 (Presence) 的广播与隐私保护
- 自定义状态消息

## 2. Actor Profile

### 2.1 Profile 对象

每个 Actor DID 关联一个标准化的 Profile，作为其公开身份信息。Profile 数据存储在 Actor 的 Repo 中，并通过 Identity 解析可被其他节点发现。

```json
{
  "did": "did:web:alice.example.com",
  "display_name": "Alice Chen",
  "avatar": {
    "blob_ref": "cx:blob:sha256:a1b2c3...",
    "mimetype": "image/webp",
    "width": 256,
    "height": 256
  },
  "status_message": "On vacation until May 5th 🏖️",
  "pronouns": "she/her",
  "timezone": "Asia/Shanghai",
  "locale": "zh-CN",
  "custom_fields": {
    "title": "Senior Engineer",
    "organization": "Acme Corp"
  }
}
```

### 2.2 标准 Profile 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `did` | string | MUST | Actor 的 DID |
| `display_name` | string | SHOULD | 人类可读的显示名（最大 128 字符） |
| `avatar` | object | 可选 | 头像图片的 Blob 引用 |
| `status_message` | string | 可选 | 自定义状态消息（最大 256 字符） |
| `pronouns` | string | 可选 | 代词偏好 |
| `timezone` | string | 可选 | IANA 时区标识 |
| `locale` | string | 可选 | 语言偏好 (BCP 47) |
| `custom_fields` | object | 可选 | 自定义键值对（用于组织特有的字段如职位、部门等） |

### 2.3 Profile 更新

Profile 的变更通过 `cx.profile.update` 操作提交到 Actor 的 Repo：

```json
{
  "type": "cx.profile.update",
  "actor": "did:web:alice.example.com",
  "body": {
    "display_name": "Alice C.",
    "status_message": "Back at work!"
  }
}
```

- 仅携带发生变化的字段（delta 更新）
- 其他参与者的客户端通过 Relay 的 Firehose 或 Actor Repo 同步获取最新 Profile
- Index 节点 SHOULD 缓存 Profile 并在查询响应中内联展示

### 2.4 Per-Space Profile 覆写

用户 MAY 为特定 Space 设置不同的显示名或头像（例如在公司 Space 用真名，在开源项目 Space 用昵称）：

```json
{
  "type": "cx.profile.space_override",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "body": {
    "display_name": "alice-oss",
    "avatar": null
  }
}
```

- Space 覆写的优先级高于全局 Profile
- `null` 值表示使用全局 Profile 的对应字段

## 3. 在线状态 (Presence)

### 3.1 Presence 是 Ephemeral 状态

在线状态属于高频变动的临时数据，MUST NOT 作为 Durable Op 写入 Repo。它通过 Relay 的 Ephemeral Channel 广播。

### 3.2 Presence 状态值

| 状态 | 含义 |
|------|------|
| `online` | 用户当前活跃在线 |
| `idle` | 用户在线但一段时间无操作 |
| `offline` | 用户离线 |
| `dnd` | 勿扰模式（在线但不希望被打扰） |

### 3.3 Presence 广播格式

通过 Relay 的 Ephemeral Channel 广播：

```json
{
  "type": "cx.presence",
  "actor": "did:web:alice.example.com",
  "state": "online",
  "last_active_at": "2026-04-26T08:30:00Z",
  "status_message": "On vacation until May 5th 🏖️",
  "ttl_ms": 60000
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `state` | string | MUST | 状态值 |
| `last_active_at` | string | SHOULD | 最后活跃时间 |
| `status_message` | string | 可选 | 当前状态消息（来自 Profile） |
| `ttl_ms` | integer | SHOULD | 存活时间（毫秒），超时后客户端应将该用户视为 offline |

### 3.4 隐私控制

用户可以控制 Presence 的可见范围：

```json
{
  "presence_visibility": "contacts_only"
}
```

| 值 | 含义 |
|----|------|
| `public` | 所有共同 Space 的成员可见 |
| `contacts_only` | 仅对明确的联系人可见 |
| `nobody` | 完全隐藏在线状态（对所有人显示为 offline） |

### 3.5 Typing 指示器

正在输入状态通过 Relay 的 Ephemeral Channel 广播，格式极度轻量：

```json
{
  "type": "cx.typing",
  "actor": "did:web:alice.example.com",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "topic_id": "cx:topic:01JS1000000000000000000001",
  "typing": true,
  "ttl_ms": 5000
}
```

- `ttl_ms` 到期后客户端应自动清除 Typing 指示
- 客户端 SHOULD 限制 Typing 广播频率（建议每 3 秒最多一次）
- 客户端 SHOULD 在用户停止输入后主动发送 `typing: false`

## 4. 用户目录 (User Directory)

### 4.1 搜索接口

Index 节点 SHOULD 提供用户搜索功能，用于 `@mention` 自动完成和联系人发现：

```
GET /api/v1/directory/search-users?q=alice&space_id=cx:space:...&limit=10
```

```json
{
  "results": [
    {
      "did": "did:web:alice.example.com",
      "display_name": "Alice Chen",
      "avatar": {
        "blob_ref": "cx:blob:sha256:a1b2c3..."
      },
      "membership": "joined"
    }
  ],
  "limited": false
}
```

### 4.2 搜索范围

- 默认搜索当前 Space 的成员
- 可选扩展到同一组织域下的所有已知用户
- 不应跨域搜索未授权的外部用户

## 5. 后续待细化

- 头像的 E2EE 场景处理（公开 vs 加密头像）
- Profile 字段的 Schema 验证（组织可以限定 custom_fields 的格式）
- Presence 的跨域联邦传播
- 群组 Profile（Space 的名称、图标、描述等）
