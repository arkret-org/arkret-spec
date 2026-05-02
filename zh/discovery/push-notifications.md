# Push Notifications

## 1. 目标

去中心化协作协议中，用户的客户端不可能永远在线监听 Sync Service 的 Sync Stream。当用户离线时，协议需要一套标准化的**推送通知机制**，将重要事件及时送达用户的移动设备或桌面系统。

本规范定义了：
- 推送规则引擎：用户可自定义哪些事件触发推送
- 推送网关接口：标准化的第三方推送投递协议
- E2EE 场景下的隐私保护推送

## 2. 设计原则

### 2.1 推送由 Sync Service / Index 触发，不由客户端维护

客户端在离线前向 Sync Service 注册推送设备信息。此后由 Sync Service 或 Index 节点在收到匹配推送规则的事件时，向推送网关 (Push Gateway) 发送通知。

### 2.2 推送内容脱敏 (Blind Wakeup)

在 E2EE 场景下，Sync Service 无法读取消息正文。推送通知的默认行为是**脱敏唤醒 (Blind Wakeup)**：
- 推送只携带 `space_id`, `event_type`, `sender_did` 等明文元数据
- 客户端被唤醒后自行从 Sync Service 拉取并解密实际内容
- 发送者客户端 MAY 在明文元数据中附加一个可选的脱敏摘要 `push_hint`（例如 "New message from Alice"），但 MUST NOT 包含实际正文

### 2.3 用户完全控制推送规则

推送规则是 Actor-private 的配置，存储在用户自己的加密 account data 中。用户有权关闭任何 Space 的推送、设置静默时段、自定义关键词触发等。

## 3. 推送设备注册

### 3.1 注册接口

客户端在上线时 SHOULD 向 Sync Service 注册推送设备：

```
POST /api/v1/push/register-device
```

请求示例（非完整 schema）：

```json
{
  "device_id": "did:web:alice.example.com#device-phone",
  "push_gateway": "https://push.example.com/api/v1/push/notify",
  "push_key": "fcm:eJx9k2...",
  "platform": "android",
  "app_id": "com.contrix.client",
  "display_name": "Alice's Pixel 9"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `device_id` | string | MUST | 设备 DID 片段标识 |
| `push_gateway` | string | MUST | 推送网关的 URL |
| `push_key` | string | MUST | 设备在推送平台上的注册令牌 |
| `platform` | string | SHOULD | `android`, `ios`, `web`, `desktop` |
| `app_id` | string | SHOULD | 应用的包名 / Bundle ID |
| `display_name` | string | MAY | 用户可读设备名 |

响应字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ok` | boolean | required | 注册是否被接受 |
| `registration_id` | id | optional | 服务端分配的注册 ID |
| `expires_at` | datetime | optional | 注册或 push token 的过期时间 |

### 3.2 注销接口

```
POST /api/v1/push/unregister-device
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `device_id` | id | required | 要注销的设备 ID |
| `push_key` | string | optional | 指定要注销的 push token |
| `app_id` | string | optional | 指定应用包名 / Bundle ID |

响应字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ok` | boolean | required | 注销是否完成；不存在的注册 MAY 幂等返回成功 |

## 4. 推送规则引擎

### 4.1 规则结构

推送规则按优先级从高到低排列，第一条匹配的规则决定推送行为：

```json
{
  "rules": [
    {
      "rule_id": "override.mute-space-x",
      "kind": "override",
      "enabled": true,
      "conditions": [
        { "kind": "field_match", "field": "space_id", "pattern": "cx:space:mvted000000000000000000000..." }
      ],
      "actions": ["dont_notify"]
    },
    {
      "rule_id": "content.keyword-urgent",
      "kind": "content",
      "enabled": true,
      "conditions": [
        { "kind": "contains_keyword", "pattern": "urgent|紧急|P0" }
      ],
      "actions": ["notify", "sound_critical"]
    },
    {
      "rule_id": "underride.dm",
      "kind": "underride",
      "enabled": true,
      "conditions": [
        { "kind": "field_match", "field": "type", "pattern": "cx.message.create" },
        { "kind": "is_direct_message" }
      ],
      "actions": ["notify", "sound_default"]
    },
    {
      "rule_id": "underride.mention",
      "kind": "underride",
      "enabled": true,
      "conditions": [
        { "kind": "mentions_actor" }
      ],
      "actions": ["notify", "highlight"]
    }
  ]
}
```

### 4.2 规则类型 (kind)

| Kind | 优先级 | 说明 |
|------|--------|------|
| `override` | 最高 | 用户手动设置的覆盖规则（如静音某个 Space） |
| `content` | 高 | 基于消息内容的关键词匹配 |
| `underride` | 低 | 默认规则，当没有更高优先级规则匹配时生效 |

### 4.3 条件类型 (Condition Kinds)

| Condition Kind | 说明 |
|---------------|------|
| `field_match` | Operation 的指定字段匹配给定 pattern（支持 glob） |
| `contains_keyword` | 消息 `body` 中包含指定关键词（仅限明文部分） |
| `mentions_actor` | 消息中提及当前 Actor |
| `is_direct_message` | 来自 1 对 1 私聊 Space |
| `member_count` | Space 成员数满足条件（如 `<= 5`） |

### 4.4 动作类型 (Actions)

| Action | 说明 |
|--------|------|
| `notify` | 发送推送通知 |
| `dont_notify` | 不发送推送（静音） |
| `sound_default` | 使用默认提示音 |
| `sound_critical` | 使用紧急提示音 |
| `highlight` | 在客户端标记为高亮 |

## 5. 推送网关接口 (Push Gateway API)

### 5.1 通知推送

Sync Service 在触发推送规则后，向推送网关发送通知：

```
POST /api/v1/push/notify
```

请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
|------|------|------|------|
| `notification` | object | required | 推送通知对象。 |
| `notification.event_id` | id | optional | 触发通知的事件或 Operation ID。 |
| `notification.space_id` | id | optional | 相关 Space ID；不得泄露不可见 Space。 |
| `notification.type` | string | required | 通知类型或事件类型。 |
| `notification.sender` | did | optional | 发送者 DID；E2EE 场景可省略或脱敏。 |
| `notification.sender_display_name` | string | optional | 可显示名称；E2EE 默认不应由服务端生成。 |
| `notification.space_name` | string | optional | Space 显示名；只有在服务端有明文可见授权时可返回。 |
| `notification.push_hint` | string | optional | 发送方提供的脱敏提示；不得包含正文。 |
| `notification.counts` | object | optional | 未读数、未接来电数等计数。 |
| `notification.devices` | object[] | required | 目标设备数组。 |
| `notification.devices[].push_key` | string | required | 目标平台 push token。 |
| `notification.devices[].app_id` | string | optional | 目标应用标识。 |

请求示例（非完整 schema）：

```json
{
  "notification": {
    "event_id": "cx:event:01js0ev0000000000000000000",
    "space_id": "cx:space:01js0sp0000000000000000000",
    "type": "cx.message.create",
    "sender": "did:web:bob.example.com",
    "sender_display_name": "Bob",
    "space_name": "Engineering",
    "push_hint": "New message",
    "counts": {
      "unread": 5,
      "missed_calls": 0
    },
    "devices": [
      {
        "push_key": "fcm:eJx9k2...",
        "app_id": "com.contrix.client"
      }
    ]
  }
}
```

### 5.2 响应

```json
{
  "rejected": []
}
```

响应字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `rejected` | object[] | required | 已失效、无权限或无法投递的 push token 摘要。 |

`rejected` 数组包含已失效的 `push_key`，Sync Service SHOULD 移除这些设备的注册。

## 6. E2EE 场景下的推送

### 6.1 脱敏推送流程

1. Alice 发送加密消息到 Space S
2. Alice 的客户端在 Operation 的明文元数据中附加 `push_hint: "New message from Alice"`
3. Sync Service 收到 Operation，匹配推送规则
4. Sync Service 向 Bob 的推送网关发送脱敏通知（只含 `space_id`, `type`, `push_hint`）
5. Bob 的设备收到推送，唤醒客户端
6. 客户端从 Sync Service 拉取加密 Operation 并解密
7. 客户端在本地展示完整的消息内容

### 6.2 安全约束

- Sync Service MUST NOT 在推送中包含 `encrypted_payload` 的任何部分
- `push_hint` 是发送方自愿提供的可选字段，接收方不应完全信任其内容
- 推送网关应被视为不可信第三方，推送内容应尽量最小化

## 7. 静默时段 (Do Not Disturb)

用户可以配置静默时段：

```json
{
  "dnd": {
    "enabled": true,
    "schedule": {
      "timezone": "Asia/Shanghai",
      "periods": [
        { "start": "22:00", "end": "08:00" }
      ]
    },
    "exceptions": ["override.keyword-urgent"]
  }
}
```

在静默时段内，只有 `exceptions` 列表中的规则可以触发推送。

## 8. v1 互操作要求

- 推送规则的跨设备同步使用私有加密 Account Data；规则变更 MUST 由 holder device 签名，未授权服务不得读取敏感关键词或联系人规则。
- Delivery Receipt 只能表示推送网关或平台尝试投递，不等于用户已读。已读状态仍由 read marker / read receipt profile 表达。
- 语音/视频通话推送使用 `cx.call.signal` 的 invite hint；payload MUST NOT 包含 SDP、ICE candidate、TURN credential 或明文会议标题，除非 Space policy 明确允许。
- Push Gateway 高可用不得通过共享长期 device token 实现。多网关部署 MUST 使用 service DID、短期授权、token 分片或 per-gateway registration，并支持撤销。
