---
title: Applet Integration
---

> **状态：extension profile（非 v1 core 互操作必需）**。Applet registry、审核 SLA 与 capability
> 注入流程仍在演进。Contrix v1 core 互操作 **不要求** 实现本 profile；声称 v1 core 的
> 实现可以完全不接 Applet，仅通过 capability + actor 模型表达 bot / bridge / agent。
> `cx.profile.applet_service.v1` 视为可选 extension（见 `artifacts/profiles/conformance-profiles.json`
> 的 `profile_tiers.extension_profile_implementation`）。

## 1. 目标

Matrix 有 Application Service / Appservice，用于桥接 IRC、Slack、Discord 等外部网络，也用于 bot 和自动化集成。Contrix 需要类似能力，但不能继承 homeserver 中心化和 user_id namespace 的假设。

Contrix 将该能力定义为 **Applet**。

Applet 是一个受注册、受授权、可审计的集成服务。它可以：

- 作为 bot 参与 Realm
- 桥接外部网络
- 创建和管理 ghost actor
- 管理 portal realm
- 接收 Contrix 事件交易
- 把外部事件转换为 Contrix event
- 在获得明确授权时以受托 agent / device 方式执行操作

Applet / Agent / Morph / Ghost actor 的选择边界如下，实现 MUST 按最窄概念建模：

| 场景 | 首选模型 | 不应使用 |
| --- | --- | --- |
| 高频外部事件桥接、多用户镜像、需要 namespace / capability 撤销 / portal Realm | Applet + ghost actor | Morph 直接表示外部用户；Agent session 长期常驻 |
| 单次或低频外部对象导入、内容不可信、只需保留原文与映射证据 | Morph / Relation | Ghost actor 写入协作历史 |
| AI / 自动化长任务、需要状态回流、产物归档、可取消会话 | Agent protocol session | Applet masquerading 成人类 actor |
| 外部人类用户在 Contrix 内可被 mention / 授权 / 审计 | Ghost actor（标记 managed_by_applet） | 伪装为 native principal DID |

同一外部实体可以在不同上下文下产生 Morph 记录和 Ghost actor，但二者 MUST 通过显式 Relation / provenance 字段连接，不能让 projection 自由猜测它们是同一主体。

## 2. 与 Matrix Appservice 的对应关系

| Matrix Appservice | Contrix Applet |
| --- | --- |
| homeserver 本地注册文件 | signed `applet_registration` |
| sender localpart | applet controller DID / bot DID |
| user namespace regex | actor namespace claim / DID namespace |
| room namespace regex | Realm / portal namespace |
| alias namespace regex | handle / portal alias namespace |
| `/transactions/{txn_id}` | `POST /api/v1/applet/transactions` + `Idempotency-Key` header |
| `/users/{user_id}` | `/api/v1/applet/actors/{actor_id}` |
| `/rooms/{room_alias}` | `/api/v1/applet/realms/{realm_id_or_alias}` |
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

Applet 的主要可见 Actor。Bot Actor 可以加入 Realm、被 mention、发送消息或执行自动化。

### 3.4 Ghost Actor

外部网络用户在 Contrix 中的镜像 Actor。例如 Slack 用户 `U123` 映射为：

```text
did:web:slack-bridge.example#ghost-u123
```

或一个由 Applet 托管的独立 DID。

Ghost Actor MUST 带有 `accountability`，指向 Applet controller 和外部网络来源。

### 3.5 Portal Realm

外部网络 location 在 Contrix 中的镜像 Realm。例如 Slack channel、Discord guild channel、GitHub issue discussion。

## 4. Applet Registration

Applet MUST 有签名 registration。它可以由 Realm owner、组织管理员、registry 或 authz service 接受。

示例：

```json
{
  "kind": "cx.applet.registration",
  "applet_id": "cx:applet:21532600-0000-7000-8000-000000000000",
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
    "realms": [
      {
        "exclusive": true,
        "pattern": "slack:team:*:channel:*"
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
    "cx.realm.discover",
    "cx.object.read",
    "cx.flow.create",
    "cx.morph.create",
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
    "alg": "EdDSA",
    "verification_method": "did:web:acme.example#admin-key-1",
    "payload_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "created_at": "2026-04-26T00:00:00Z",
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
- 哪些 Realm / portal alias 属于 Applet
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

### 5.2 Realm Namespace

Realm namespace 适用于 portal Realm。

```json
{
  "exclusive": true,
  "pattern": "slack:team:*:channel:*"
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

注册 Applet 后，Realm owner 或组织管理员 MUST 显式授予 capability。

示例：

```json
{
  "issuer": "did:web:acme.example",
  "subject": "did:web:slack-bridge.example#bot",
  "scope": {
    "realm_ids": [
      "cx:realm:0196419b-0000-7000-8000-000000000000"
    ],
    "actions": [
      "cx.flow.create",
      "cx.morph.create",
      "cx.message.create",
      "cx.relation.create"
    ]
  },
  "constraints": [
    {
      "constraint_type": "scope_limitation",
      "effect": "allow",
      "via_applet_id": "cx:applet:21532600-0000-7000-8000-000000000000",
      "allowed_actor_namespace": "did:web:slack-bridge.example#ghost-*"
    }
  ],
  "expires_at": "2026-07-26T00:00:00Z"
}
```

除非 Applet 拥有 effective grant，或以委托授权身份显式代表已授权 actor 行事，否则 Applet MUST NOT 向 Realm 写入。

## 7. Applet API

Applet API 是 Contrix 节点调用 Applet 的接口。  
Applet 调用 Contrix 节点时使用常规 Events API / sync service / authz API。

Base URL 来自 registration 的 `base_url`。

字段级接口索引：

| operation_id | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `cx.applet.ping` | 无 | 无 | `ok: boolean`; `applet_id: id`; `service_did: did`; `protocol_version: string` | 可公开，但不得泄露 private namespace。 |
| `cx.applet.describe` | 无 | 无 | `applet_id: id`; `service_did: did`; `protocols: string[]`; `namespaces: object`; `limits: object`; `auth: object` | public mode 只返回公开 capabilities。 |
| `cx.applet.transaction` | `header.Idempotency-Key: string`; `source_service_did: did`; `events: EventEnvelope[]` | `ephemeral: object[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | Applet MUST 验证来源 service DID、HTTP signature、event signature、namespace 和 capability。 |
| `cx.applet.query_actor` | `path.actor_id: did` | 无 | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | actor_id 必须命中 Applet actor namespace。 |
| `cx.applet.query_space` | `path.realm_id_or_alias: string` | 无 | `exists: boolean`; `realm_id: id?`; `title: string?`; `external_ref: object?` | 必须命中 portal namespace 或授权查询。 |
| `cx.applet.protocol_metadata` | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob: string?`; `field_types: object`; `instances: object[]?` | instance list 可要求授权。 |
| `cx.applet.third_party_users` | `query.protocol: string`; 外部 ID query 字段 | 无 | `actor_id: did?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 registration namespace 内。 |
| `cx.applet.third_party_locations` | `query.protocol: string`; 外部 ID query 字段 | 无 | `realm_id: id?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 portal namespace 内。 |

### 7.1 Ping

```text
GET /api/v1/applet/ping
```

返回：

```json
{
  "ok": true,
  "applet_id": "cx:applet:21532600-0000-7000-8000-000000000000",
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
POST /api/v1/applet/transactions
Idempotency-Key: <opaque-string>
```

Contrix sync service / Events API 向 Applet 推送事件批次。

请求示例（非完整 schema）：

```json
{
  "source_service_did": "did:web:server.example",
  "events": [
    {
      "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
      "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
      "kind": "cx.message.create",
      "actor_id": "did:web:alice.example",
      "payload": {}
    }
  ],
  "ephemeral": [
    {
      "type": "typing",
      "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
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

- `Idempotency-Key` MUST 幂等。
- 相同 `(source_service_did, Idempotency-Key)` 和相同 body canonical hash 重复投递 MUST 成功。
- 相同 `(source_service_did, Idempotency-Key)` 但 body 不同 MUST 返回 `duplicate_conflict`。
- 单事件级别仍以 `event_id` 去重；重复 `event_id` 且内容一致 MUST `accepted`，内容不一致 MUST 拒绝。
- Applet SHOULD 先持久化幂等记录，再执行外部副作用。
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

### 7.5 Query Realm

```text
GET /api/v1/applet/realms/{realm_id_or_alias}
```

用于查询 portal Realm 是否存在或可创建。

返回：

```json
{
  "exists": true,
  "realm_id": "cx:realm:c0c69410-0000-7000-8000-000000000000",
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

用于把外部用户或 location 映射到 Contrix actor / portal Realm。

## 8. Applet 写入 Contrix

Applet 写入 Contrix MUST 使用常规 `/events` submit 接口。

每个写入 Event MUST 包含：

- `actor_id`
- `applet_id`
- `external_ref`，若来自外部网络
- `authorization_ref`
- `proof`

示例：

```json
{
  "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "cx:realm:c0c69410-0000-7000-8000-000000000000",
  "actor_id": "did:web:slack-bridge.example#ghost-u123",
  "kind": "cx.message.create",
  "applet_id": "cx:applet:21532600-0000-7000-8000-000000000000",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "event_id": "1714040000.000100"
  },
  "payload": {
    "flow_id": "cx:flow:c0c69410-0000-7000-8000-000000000001",
    "content": {
      "body": "hello from Slack"
    }
  },
  "proof": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:web:slack-bridge.example#ghost-u123-key",
    "payload_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "created_at": "2026-04-26T00:00:01Z",
    "jws": "..."
  }
}
```

## 9. Ghost Actor

Ghost Actor MUST 与原生人类 Actor 在协议层可区分。

Ghost Actor profile SHOULD 包含：

```json
{
  "actor_id": "did:web:slack-bridge.example#ghost-u123",
  "actor_kind": "ghost",
  "display_name": "Alice on Slack",
  "managed_by_applet": "cx:applet:21532600-0000-7000-8000-000000000000",
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

Ghost Actor MUST NOT 被静默合并到 native DID，除非 native holder 显式声明并完成绑定。

## 10. Portal Realm

Portal Realm 把外部 location 映射到 Contrix。

Portal Realm SHOULD 记录：

- 外部协议
- 外部网络 id
- 外部 location id
- bridge Applet id
- 创建者 / 控制者
- 可见性
- 成员映射策略

Portal Realm MUST 仍然执行常规的 Realm policy 与 capability 规则。

## 11. Masquerading 与 Delegated Agent

只有当用户或组织显式授予委托权限时，Applet MAY 代表 native 用户行事。

由此产生的 Event MUST 同时呈现：

- accountable actor：native actor
- executing applet / 委托密钥

示例 UI 语义：

```text
Alice via Calendar Applet
```

协议字段 **MUST** include:

```json
{
  "actor_id": "did:web:alice.example",
  "executed_by": "did:web:calendar-applet.example#agent",
  "authorization_ref": "cx:grant:0196410c-0000-7000-8000-000000000000",
  "applet_id": "cx:applet:8a0baad5-6000-7000-8000-000000000000"
}
```

**Reducer normative**:

- 当 Event 的 envelope signature 由 applet / delegated agent key 签发但 `actor_id` 指向 native principal DID 时（即 actor_id ≠ signing key 所属 DID），reducer MUST 校验：
  1. `executed_by` 必填,指向实际签发该 Event 的 applet / agent DID;`executed_by` 与 envelope signing key 的 DID 一致;
  2. `authorization_ref` 必填,指向已 accepted 的 `cx.capability.grant`(或等价 delegation event), 该 grant 把 actor_id 主体的某个 action 委托给 executed_by;
  3. `applet_id` 必填(在 Applet 模式下), 指向已注册的 applet;
  4. grant constraint MUST 绑定 `applet_id`、`executed_by` DID、`executed_by` DID Document canonical hash / method-specific version（若 DID method 提供）和 registration epoch hash。Applet key rotate、DID Document endpoint 变化或 registration 更新后，旧 grant 不得继续授权新 key，除非 grant 明确声明可接受的 epoch range 并由 reducer 验证。
- 缺少 `executed_by`、`authorization_ref` 或 `applet_id` 中任一字段时,reducer MUST `schema_violation` 拒绝。该规则适用于所有 `cx.profile.applet_*` profile,客户端 / SDK 不得退回到 SHOULD 形态。

Applet MUST NOT use masquerading to hide automation. 客户端 MUST 明确展示 `via applet`：UI 在渲染 mention、notification、audit log、moderation queue 等任何"who did this"上下文时,MUST 同时显示 native actor 与 `executed_by` 双重署名,不得仅显示 native actor 而隐藏 applet 身份。

`requested_scopes` 只服务 consent / audit UI：registration 接受时，reviewer 可据此决定是否签发 capability grant；一旦 grant 写入，后续 reducer 只看 grant `actions[]` / selector / constraint，不再从 `requested_scopes` 推断权限。实现 MUST 在 audit log 中把最终 grant 与 registration `requested_scopes` 的差异显示给 reviewer，避免 Applet 请求 A、实际被授予 B 时无人可见。

## 12. E2EE

Applet 参与 E2EE Realm 时有三种模式：

1. Bot 作为正式成员加入 MLS group。
2. Ghost Actor 作为正式成员加入 portal Realm 的 MLS group。
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
- 绕过 Realm encryption policy
- 泄露未授权 Realm 内容到外部网络

## 14. 失败与重试

Transaction push 失败时：

- 5xx / timeout：发送方 SHOULD 重试相同 `Idempotency-Key`
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
- query realm
- protocol metadata
- ghost actor accountability
- capability enforcement
- duplicate external event handling
- E2EE boundary warning metadata

## 16. v1 互操作要求

- `applet_registration` JSON Schema 由 `applet-schema.md` 和 `schema-registry.md` 固定，必须包含 service DID、endpoint、namespace、protocol、capability refs、signing method 和 expiry。
- Namespace pattern grammar MUST 明确 actor、realm、handle、external protocol id 的匹配边界；namespace 命中不授予写权限。
- Transaction schema MUST 包含 source network、external event id、mapped actor、target Realm、operation refs、`Idempotency-Key`、signature 和 received_at。
- Protocol metadata schema MUST 声明外部系统、identity mapping、permission mapping、E2EE boundary、rate limit 和 supported media types。
- Bridge error event 使用 `cx.applet.bridge_error`，必须绑定 failed transaction、外部错误类别、是否可重试和可见范围；不得泄露未授权外部正文。
- External event deduplication key MUST 至少包含 protocol、tenant/workspace、external channel/location、external event id 和 normalized sender；不得只依赖时间戳或正文 hash。
- Applet UI widget sandbox MUST 与 Realm capability、origin isolation、CSP、token scoping 和 user consent 绑定；widget 不得直接获得 Contrix session token 或未授权 Event history access。
