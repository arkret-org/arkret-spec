# Client Preferences & Account Data

## 1. 目标

在 Contrix 网络中，绝大部分数据是跨节点共享的协作对象（Space、Subject、Room、Board、List、Card、Message、Morph）。但每个用户（Actor）也有大量的**私有状态**需要在其各个设备之间同步，但不应该对网络中的其他人可见。

本规范定义了这些**客户端偏好与账户数据 (Account Data)** 的存储、同步与标准 Schema。

## 2. 存储模型

### 2.1 存储在私有 Account Data

由于 Contrix 采用 signed Event 和 per-actor event chain 作为信任根，账户私有数据 SHOULD 作为加密 account data 或 actor-private Event 保存。

这些私有数据只有用户本人的受信任设备有权限读写。Sync Service 节点仅负责存储加密或不透明的二进制块，并不解析其中的明文。

### 2.2 数据寻址

所有的偏好数据以 Key-Value 字典的形式组织。每次修改是对某个 Key 的全量覆盖（使用 `cx.account_data.set` 操作）。

```json
{
  "kind": "cx.account_data.set",
  "key": "cx.client.theme",
  "body": {
    "mode": "dark",
    "accent_color": "#FF5733"
  }
}
```

## 3. 标准账户数据类型

为了保证不同客户端间的互操作性，本规范定义了以下标准 Key 命名空间：

### 3.1 空间标签与分类 (Space Tags)

用户可以给加入的 Space 打上私有标签（例如“收藏”、“低优先级”、“公司项目”）。

**Key:** `cx.tags.space.<space_id>`

```json
{
  "tags": {
    "cx.favorite": { "order": 0.5 },
    "cx.low_priority": {},
    "org.example.work": {}
  }
}
```

客户端 SHOULD 根据这些标签将 Space 在 UI 上分组或排序。`order` 是一种用于自定义排序的浮点数指示器。

### 3.2 勿扰与通知设置 (Notification Settings)

控制各个 Space 或全局的通知覆盖行为（详见 `push-notifications.md`）。

**Key:** `cx.push_rules` 和 `cx.dnd_schedule`

### 3.3 自定义 Emoji 与 Sticker (Custom Emojis)

用户个人收藏的表情包或贴纸集。

**Key:** `cx.collections.stickers`

```json
{
  "images": {
    "party_parrot": {
      "blob_ref": "cx:blob:sha256:abcd...",
      "mime_type": "image/gif"
    }
  }
}
```

### 3.4 客户端 UI 偏好 (UI State)

用于保存用户的视图偏好，以便在新设备登录时恢复熟悉的界面。

**Key:** `cx.client.ui_state`

```json
{
  "sidebar_collapsed": false,
  "recent_spaces": [
    "cx:space:01js0sa0000000000000000000",
    "cx:space:01js0sb0000000000000000000"
  ],
  "language": "zh-CN"
}
```

### 3.5 个人屏蔽与过滤 (Personal Blocklist)

用户可以在私有 account data 中保存个人 blocklist。该数据只影响用户自己的客户端、本地搜索/投影、通知规则和联系请求处理，不改变 Space 的共享事实。

**Key:** `cx.account.blocklist`

```json
{
  "version": 1,
  "entries": [
    {
      "entry_id": "cx:block:01js0b7k000000000000000000",
      "target": {
        "kind": "actor",
        "did": "did:web:spammer.example.com"
      },
      "mode": "block",
      "applies_to": [
        "messages",
        "mentions",
        "dm",
        "calls",
        "presence",
        "notifications",
        "directory"
      ],
      "reason_code": "harassment",
      "created_at": "2026-04-26T10:00:00Z",
      "expires_at": null
    }
  ]
}
```

`target.kind` MAY be:

- `actor`
- `device`
- `service`
- `handle`
- `domain`
- `organization`
- `applet`
- `keyword`

Rules:

- Account blocklist MUST be encrypted for the holder's own devices when synchronized through untrusted services.
- Clients SHOULD suppress notifications, contact requests, call invites and DM requests from blocked targets.
- Clients MAY hide or collapse blocked content in shared Space views.
- Clients MUST NOT publish the blocklist to public Space state or directory services.
- Blocking an organization or domain MUST be evaluated through verified DID / claim bindings when possible; clients SHOULD warn when only a weak string match is available.

## 4. 与本地投影的交互

虽然 account data 对外不公开，但用户自己的客户端或可信端侧节点会拉取并解密这些数据，并合并到本地查询结果中。

例如：当客户端以 `object_types=["space"]` 查询加入的 Space 列表时，本地 projection 可以将 `cx.tags.space.*` 数据 Join 进去，得到带私有标签的 Space 列表。

## 5. 安全与隐私

- 涉及用户敏感信息的 Account Data（例如访问第三方服务的私钥、密码管理器的 Vault），MUST 另外进行客户端加密（Client-Side Encryption），使用类似 Matrix 4S (Secret Storage) 的机制，通过单独的 Recovery Key 保护。
- 普通的 UI 偏好和标签可以直接由用户的 Device Key 签名写入加密 account data。

## 6. v1 规则

- 4S / Secret Storage 与 Key Backup 的存储格式必须使用客户端加密 envelope，绑定 principal DID、device / recovery key、algorithm、KDF parameters、created_at、version 和 payload hash。服务端不得获得解锁材料。
- 跨端排序字段 MUST 使用稳定 rank string 或 HLC + tie-break 组合，不得使用非确定性 float 作为唯一排序真相。客户端可在 UI 内使用 float 计算临时位置，但写回必须归一为规范 rank。
