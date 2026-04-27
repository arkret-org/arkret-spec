# Push Notifications Draft

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

推送规则是 Actor-private 的配置，存储在用户自己的 Repo 中。用户有权关闭任何 Space 的推送、设置静默时段、自定义关键词触发等。

## 3. 推送设备注册

### 3.1 注册接口

客户端在上线时 SHOULD 向 Sync Service 注册推送设备：

```
POST /api/v1/push/register-device
```

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

### 3.2 注销接口

```
POST /api/v1/push/unregister-device
```

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
        { "kind": "field_match", "field": "space_id", "pattern": "cx:space:muted..." }
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
| `field_match` | Op 的指定字段匹配给定 pattern（支持 glob） |
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

```json
{
  "notification": {
    "event_id": "cx:op:01JS0OP000000000000000000",
    "space_id": "cx:space:01JS0SP000000000000000000",
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

`rejected` 数组包含已失效的 `push_key`，Sync Service SHOULD 移除这些设备的注册。

## 6. E2EE 场景下的推送

### 6.1 脱敏推送流程

1. Alice 发送加密消息到 Space S
2. Alice 的客户端在 Op 的明文元数据中附加 `push_hint: "New message from Alice"`
3. Sync Service 收到 Op，匹配推送规则
4. Sync Service 向 Bob 的推送网关发送脱敏通知（只含 `space_id`, `type`, `push_hint`）
5. Bob 的设备收到推送，唤醒客户端
6. 客户端从 Sync Service 拉取加密 Op 并解密
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

## 8. 后续待细化

- 推送规则的跨设备同步
- 推送统计与 Delivery Receipt
- 语音/视频通话推送的特殊处理
- 推送网关的高可用与容错
