# Applet Integration

## 1. 目标

Matrix 有 Application Service / Appservice，用于桥接 IRC、Slack、Discord 等外部网络，也用于 bot 和自动化集成。Contrix 需要类似能力，但不能继承 homeserver 中心化和 user_id namespace 的假设。

Contrix 将该能力定义为 **Applet**。

Applet 是一个受注册、受授权、可审计的集成服务。它可以：

- 作为 bot 参与 Space
- 桥接外部网络
- 创建和管理 ghost actor
- 管理 portal space
- 接收 Contrix 事件交易
- 把外部事件转换为 Contrix event
- 在获得明确授权时以受托 agent / device 方式执行操作

## 2. 与 Matrix Appservice 的对应关系

| Matrix Appservice | Contrix Applet |
| --- | --- |
| homeserver 本地注册文件 | signed `applet_registration` |
| sender localpart | applet controller DID / bot DID |
| user namespace regex | actor namespace claim / DID namespace |
| room namespace regex | Space / portal namespace |
| alias namespace regex | handle / portal alias namespace |
| `/transactions/{txn_id}` | `/api/v1/applet/transactions/{txn_id}` |
| `/users/{user_id}` | `/api/v1/applet/actors/{actor_id}` |
| `/rooms/{room_alias}` | `/api/v1/applet/spaces/{space_id_or_alias}` |
| third-party protocols | external protocol metadata |
| appservice masquerading | delegated agent / ghost actor capability |

关键差异：

- Applet 不自动拥有全网权限。
- Applet 的每个写入仍需签名和 capability。
- Applet namespace 只表示“该 Applet 可声明或接收这些对象”，不等于权限通过。
- Ghost actor 必须是可审计 Actor，不应伪装成人类 DID。

## 3. 角色

### 3.1 Applet Service

运行集成逻辑的服务端进程。它有自己的 service DID。

### 3.2 Applet Controller

管理该 Applet 的主体，通常是组织、开发者或企业管理员。

### 3.3 Bot Actor

Applet 的主要可见 Actor。Bot Actor 可以加入 Space、被 mention、发送消息或执行自动化。

### 3.4 Ghost Actor

外部网络用户在 Contrix 中的镜像 Actor。例如 Slack 用户 `U123` 映射为：

```text
did:web:slack-bridge.example#ghost-u123
```

或一个由 Applet 托管的独立 DID。

Ghost Actor MUST 带有 `accountability`，指向 Applet controller 和外部网络来源。

### 3.5 Portal Space

外部网络 location 在 Contrix 中的镜像 Space。例如 Slack channel、Discord guild channel、GitHub issue discussion。

## 4. Applet Registration

Applet MUST 有签名 registration。它可以由 Space owner、组织管理员、registry 或 authz service 接受。

示例：

```json
{
  "type": "cx.applet.registration",
  "applet_id": "cx:applet:slack-bridge",
  "service_did": "did:web:slack-bridge.example",
  "controller_did": "did:web:acme.example",
  "base_url": "https://slack-bridge.example/api/v1/applet",
  "bot_actor_id": "did:web:slack-bridge.example#bot",
  "protocols": [
    "slack"
  ],
  "namespaces": {
    "actors": [
      {
        "exclusive": true,
        "pattern": "did:web:slack-bridge.example#ghost-*"
      }
    ],
    "spaces": [
      {
        "exclusive": true,
        "pattern": "cx:space:portal:slack:*"
      }
    ],
    "handles": [
      {
        "exclusive": true,
        "pattern": "slack.acme.example/*"
      }
    ]
  },
  "receive_events": true,
  "receive_ephemeral": false,
  "rate_limited": true,
  "requested_scopes": [
    "space.read",
    "space.write",
    "cx.entity.create",
    "cx.message.create",
    "cx.relation.create"
  ],
  "webhook_auth": {
    "type": "http_message_signature",
    "key_ref": "did:web:slack-bridge.example#server-key-1"
  },
  "created_at": "2026-04-26T00:00:00Z",
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:web:acme.example#admin-key-1",
    "jws": "..."
  }
}
```

### 4.1 Registration 规则

- `applet_id` MUST 稳定。
- `service_did` MUST 可解析，并声明 Applet endpoint。
- `controller_did` MUST 对 registration 签名。
- `namespaces` MUST 明确声明，不能默认为全网。
- exclusive namespace 冲突时，registry / authz service MUST 拒绝后注册者。
- `requested_scopes` 只是请求权限，不是实际授权。
- 实际权限 MUST 通过 capability grant 授予。

## 5. Namespace

Namespace 用于决定：

- 哪些未知 actor 可以向 Applet 查询
- 哪些 Space / portal alias 属于 Applet
- 哪些事件应推送给 Applet
- Applet 可以为哪些 ghost actor 申请或声明身份

Namespace 不等于 capability。  
Namespace 命中只表示“这个 Applet 是该名称空间的处理方”。

### 5.1 Actor Namespace

Actor namespace 适用于 ghost actor 和 bot actor。

```json
{
  "exclusive": true,
  "pattern": "did:web:slack-bridge.example#ghost-*"
}
```

### 5.2 Space Namespace

Space namespace 适用于 portal Space。

```json
{
  "exclusive": true,
  "pattern": "cx:space:portal:slack:*"
}
```

### 5.3 Handle Namespace

Handle namespace 适用于外部用户或 location 的人类入口。

```json
{
  "exclusive": false,
  "pattern": "slack.acme.example/*"
}
```

## 6. Applet Capability

注册 Applet 后，Space owner 或组织管理员 MUST 显式授予 capability。

示例：

```json
{
  "type": "capability",
  "issuer": "did:web:acme.example",
  "subject": "did:web:slack-bridge.example#bot",
  "scope": {
    "space_ids": [
      "cx:space:01JS0SP000000000000000000"
    ],
    "actions": [
      "cx.entity.create",
      "cx.message.create",
      "cx.relation.create"
    ]
  },
  "constraints": {
    "via_applet_id": "cx:applet:slack-bridge",
    "allowed_actor_namespace": "did:web:slack-bridge.example#ghost-*"
  },
  "expires_at": "2026-07-26T00:00:00Z"
}
```

Applet MUST NOT write into a Space unless it has an effective grant or is explicitly acting as an already-authorized actor through delegated authority.

## 7. Applet API

Applet API 是 Contrix 节点调用 Applet 的接口。  
Applet 调用 Contrix 节点时使用常规 repo / sync service / index / authz API。

Base URL 来自 registration 的 `base_url`。

字段级接口索引：

| operation_id | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `cx.applet.ping` | 无 | 无 | `ok: boolean`; `applet_id: id`; `service_did: did`; `protocol_version: string` | 可公开，但不得泄露 private namespace。 |
| `cx.applet.describe` | 无 | 无 | `applet_id: id`; `service_did: did`; `protocols: string[]`; `namespaces: object`; `limits: object`; `auth: object` | public mode 只返回公开 capabilities。 |
| `cx.applet.transaction` | `path.txn_id: id`; `source_service_did: did`; `events: object[]` | `ephemeral: object[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | Applet MUST 验证来源 service DID、HTTP signature、event signature、namespace 和 capability。 |
| `cx.applet.query_actor` | `path.actor_id: did` | 无 | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | actor_id 必须命中 Applet actor namespace。 |
| `cx.applet.query_space` | `path.space_id_or_alias: string` | 无 | `exists: boolean`; `space_id: id?`; `title: string?`; `external_ref: object?` | 必须命中 portal namespace 或授权查询。 |
| `cx.applet.protocol_metadata` | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob: string?`; `field_types: object`; `instances: object[]?` | instance list 可要求授权。 |
| `cx.applet.third_party_users` | `query.protocol: string`; 外部 ID query 字段 | 无 | `actor_id: did?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 registration namespace 内。 |
| `cx.applet.third_party_locations` | `query.protocol: string`; 外部 ID query 字段 | 无 | `space_id: id?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 portal namespace 内。 |

### 7.1 Ping

```text
GET /api/v1/applet/ping
```

返回：

```json
{
  "ok": true,
  "applet_id": "cx:applet:slack-bridge",
  "service_did": "did:web:slack-bridge.example",
  "protocol_version": "1.0"
}
```

### 7.2 Describe

```text
GET /api/v1/applet/describe
```

返回 Applet 支持的协议、profile、namespace、最大交易大小和认证方式。

### 7.3 Transaction Push

```text
PUT /api/v1/applet/transactions/{txn_id}
```

Contrix sync service / index / repo 向 Applet 推送事件批次。

请求示例（非完整 schema）：

```json
{
  "txn_id": "cx:txn:01JS0TX000000000000000000",
  "source_service_did": "did:web:server.example",
  "events": [
    {
      "event_id": "cx:event:01JS0EV000000000000000000",
      "space_id": "cx:space:01JS0SP000000000000000000",
      "type": "cx.message.create",
      "actor_id": "did:web:alice.example",
      "payload": {}
    }
  ],
  "ephemeral": [
    {
      "type": "typing",
      "space_id": "cx:space:01JS0SP000000000000000000",
      "actor_id": "did:web:alice.example"
    }
  ]
}
```

响应示例（非完整 schema）：

```json
{
  "ok": true
}
```

规则：

- `txn_id` MUST 幂等。
- 相同 `txn_id` 和相同 body 重复投递 MUST 成功。
- 相同 `txn_id` 但 body 不同 MUST 返回 `duplicate_conflict`。
- Applet SHOULD 先持久化 txn，再执行外部副作用。
- Applet MUST 验证 source service DID 和 HTTP message signature。
- Applet MUST 独立验证 event signature，不得只信任推送方。

### 7.4 Query Actor

```text
GET /api/v1/applet/actors/{actor_id}
```

用于 Contrix 节点发现 namespace 内的未知 ghost actor 是否存在。

返回：

```json
{
  "exists": true,
  "actor_id": "did:web:slack-bridge.example#ghost-u123",
  "display_name": "Alice on Slack",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "user_id": "U123"
  }
}
```

若不存在，返回 `404 not_found`。

### 7.5 Query Space

```text
GET /api/v1/applet/spaces/{space_id_or_alias}
```

用于查询 portal Space 是否存在或可创建。

返回：

```json
{
  "exists": true,
  "space_id": "cx:space:portal:slack:T123:C456",
  "title": "#release on Slack",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "location_id": "C456"
  }
}
```

### 7.6 Protocol Metadata

```text
GET /api/v1/applet/protocols/{protocol}
```

返回：

```json
{
  "protocol": "slack",
  "display_name": "Slack",
  "icon_blob": "cx:blob:sha256:...",
  "field_types": {
    "team": {
      "label": "Workspace",
      "type": "string"
    },
    "channel": {
      "label": "Channel",
      "type": "string"
    }
  },
  "instances": [
    {
      "instance_id": "T123",
      "description": "Acme Slack"
    }
  ]
}
```

### 7.7 Third-Party Lookup

```text
GET /api/v1/applet/third_party/users?protocol=slack&team=T123&user=U123
```

```text
GET /api/v1/applet/third_party/locations?protocol=slack&team=T123&channel=C456
```

用于把外部用户或 location 映射到 Contrix actor / portal Space。

## 8. Applet 写入 Contrix

Applet 写入 Contrix MUST 使用常规 repo submit 接口。

每个写入 Event MUST 包含：

- `actor_id`
- `applet_id`
- `external_ref`，若来自外部网络
- `authorization_ref`
- `proof`

示例：

```json
{
  "event_id": "cx:event:01JS0EV000000000000000000",
  "space_id": "cx:space:portal:slack:T123:C456",
  "actor_id": "did:web:slack-bridge.example#ghost-u123",
  "type": "cx.message.create",
  "applet_id": "cx:applet:slack-bridge",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "event_id": "1714040000.000100"
  },
  "payload": {
    "entity_type": "message",
    "content": {
      "body": "hello from Slack"
    }
  },
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:web:slack-bridge.example#ghost-u123-key",
    "jws": "..."
  }
}
```

## 9. Ghost Actor

Ghost Actor MUST be distinguishable from native human Actor.

Ghost Actor profile SHOULD include:

```json
{
  "actor_id": "did:web:slack-bridge.example#ghost-u123",
  "actor_type": "ghost",
  "display_name": "Alice on Slack",
  "managed_by_applet": "cx:applet:slack-bridge",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "user_id": "U123"
  },
  "accountability": {
    "mode": "applet_managed",
    "responsible_actor_id": "did:web:acme.example",
    "operator_actor_ids": [
      "did:web:slack-bridge.example"
    ]
  }
}
```

Ghost Actor MUST NOT be silently merged with a native DID unless the native holder explicitly claims and links it.

## 10. Portal Space

Portal Space maps an external location to Contrix.

Portal Space SHOULD record:

- external protocol
- external network id
- external location id
- bridge Applet id
- creator / controller
- visibility
- membership mapping policy

Portal Space MUST still enforce normal Space policy and capability rules.

## 11. Masquerading 与 Delegated Agent

Applet MAY act on behalf of a native user only when the user or organization has granted explicit delegated authority.

The resulting Event MUST show both:

- accountable actor: the native actor
- executing applet / delegated key

示例 UI 语义：

```text
Alice via Calendar Applet
```

协议字段 SHOULD include:

```json
{
  "actor_id": "did:web:alice.example",
  "executed_by": "did:web:calendar-applet.example#agent",
  "authorization_ref": "cx:grant:01JS0GR000000000000000000",
  "applet_id": "cx:applet:calendar"
}
```

Applet MUST NOT use masquerading to hide automation. 客户端 SHOULD 明确展示 `via applet`。

## 12. E2EE

Applet 参与 E2EE Space 时有三种模式：

1. Bot 作为正式成员加入 MLS group。
2. Ghost Actor 作为正式成员加入 portal Space 的 MLS group。
3. Applet 不解密，只转发外部密文或桥接 metadata。

规则：

- Applet 没有加入 MLS group 时 MUST NOT 获得明文。
- Bridge 到不支持 E2EE 的外部网络时，客户端 MUST 明确提示加密边界在 bridge 处终止。
- Applet 托管 ghost actor MLS state 时，必须将其视为高敏感密钥材料。

## 13. 安全要求

Applet 实现 MUST：

- 验证所有入站 HTTP message signature
- 验证所有 Event signature
- 持久化 transaction id，保证幂等
- 对外部事件做去重
- 限制 namespace 范围
- 遵守 capability grant
- 记录可审计 bridge mapping
- 对 secret / token 使用安全存储
- 支持管理员 revoke

Applet 实现 MUST NOT：

- 接收全网 sync stream，除非明确授权
- 把 namespace 当作写权限
- 静默 impersonate native user
- 绕过 Space encryption policy
- 泄露未授权 Space 内容到外部网络

## 14. 失败与重试

Transaction push 失败时：

- 5xx / timeout：发送方 SHOULD 重试相同 `txn_id`
- 4xx：发送方 SHOULD 停止重试，除非错误是 `rate_limited`
- `rate_limited`：发送方 MUST 优先遵守 `Retry-After`，非 HTTP binding 或无 header 时再使用 `retry_after_ms`
- `duplicate_conflict`：发送方 MUST 停止并告警

Applet 处理外部网络写入失败时 SHOULD 生成 bridge error event，而不是静默丢弃。

## 15. Conformance

`cx.profile.applet_service.v1` MUST 测试：

- registration signature
- namespace matching
- transaction idempotency
- query actor
- query space
- protocol metadata
- ghost actor accountability
- capability enforcement
- duplicate external event handling
- E2EE boundary warning metadata

## 16. v1 互操作要求

- `applet_registration` JSON Schema 由 `applet-schema.md` 和 `schema-registry.md` 固定，必须包含 service DID、endpoint、namespace、protocol、capability refs、signing method 和 expiry。
- Namespace pattern grammar MUST 明确 actor、space、handle、external protocol id 的匹配边界；namespace 命中不授予写权限。
- Transaction schema MUST 包含 `txn_id`、source network、external event id、mapped actor、target Space、operation refs、idempotency key、signature 和 received_at。
- Protocol metadata schema MUST 声明外部系统、identity mapping、permission mapping、E2EE boundary、rate limit 和 supported media types。
- Bridge error event 使用 `cx.applet.bridge_error`，必须绑定 failed transaction、外部错误类别、是否可重试和可见范围；不得泄露未授权外部正文。
- External event deduplication key MUST 至少包含 protocol、tenant/workspace、external channel/location、external event id 和 normalized sender；不得只依赖时间戳或正文 hash。
- Applet UI widget sandbox MUST 与 Space capability、origin isolation、CSP、token scoping 和 user consent 绑定；widget 不得直接获得 Contrix session token 或未授权 repo access。
