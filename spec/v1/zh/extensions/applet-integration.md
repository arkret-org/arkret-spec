---
title: Applet Integration
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

> **状态：extension profile（非 v1 core 互操作必需）**。Applet registry、审核 SLA 与 capability
> 注入流程仍在演进。Cokret v1 core 互操作 **不要求** 实现本 profile；声称 v1 core 的
> 实现可以完全不接 Applet，仅通过 capability + actor 模型表达 bot / bridge / agent。
> `cx.profile.applet_service.v1` 视为可选 extension（见 `artifacts/profiles/conformance-profiles.json`
> 的 `profile_tiers.extension_profile_implementation`）。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Matrix 有 Application Service / Appservice，用于桥接 IRC、Slack、Discord 等外部网络，也用于 bot 和自动化集成。Cokret 需要类似能力，但不能继承 homeserver 中心化和 user_id namespace 的假设。

Cokret 将该能力定义为 **Applet**。

Applet 是一个受注册、受授权、可审计的集成服务。它可以：

- 作为 bot 参与 Realm
- 桥接外部网络
- 创建和管理 Ghost Actor
- 管理 portal realm
- 接收 Cokret 事件交易
- 把外部事件转换为 Cokret event
- 在获得明确授权时以受托 agent / device 方式执行操作

Applet / Agent / Morph / Ghost Actor 的选择边界如下，实现 MUST 按最窄概念建模：

| 场景 | 首选模型 | 不应使用 |
| --- | --- | --- |
| 高频外部事件桥接、多用户镜像、需要 namespace / capability 撤销 / portal Realm | Applet + Ghost Actor | Morph 直接表示外部用户；Agent session 长期常驻 |
| 单次或低频外部对象导入、内容不可信、只需保留原文与映射证据 | Morph / Relation | Ghost Actor 写入协作历史 |
| AI / 自动化长任务、需要状态回流、产物归档、可取消会话 | Agent protocol session | Applet masquerading 成人类 actor |
| 外部人类用户在 Cokret 内可被 mention / 授权 / 审计 | Ghost Actor（标记 managed_by_applet） | 伪装为 native principal DID |

同一外部实体可以在不同上下文下产生 Morph 记录和 Ghost Actor，但二者 MUST 通过显式 Relation / provenance 字段连接，不能让 projection 自由猜测它们是同一主体。

## 2. 与 Matrix Appservice 的对应关系

| Matrix Appservice | Cokret Applet |
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
| appservice masquerading | delegated agent / Ghost Actor capability |

关键差异：

- Applet 不自动拥有全网权限。
- Applet 的每个写入仍需签名和 capability。
- Applet namespace 只表示“该 Applet 可声明或接收这些对象”，不等于权限通过。
- Ghost Actor 必须是可审计 Actor，不应伪装成人类 DID。

## 3. 角色

### 3.1 Applet Service

运行集成逻辑的服务端进程。它有自己的 service DID。

### 3.2 Applet Controller

管理该 Applet 的主体，通常是组织、开发者或企业管理员。

### 3.3 Bot Actor

Applet 的主要可见 Actor。Bot Actor 可以加入 Realm、被 mention、发送消息或执行自动化。

### 3.4 Ghost Actor

外部网络用户在 Cokret 中的镜像 Actor。例如 Slack 用户 `U123` 映射为一个独立 Actor DID：

```text
did:web:slack-bridge.example:ghost:u123
```

`#fragment` 只用于 DID URL 形式的 verification method（例如 `did:web:slack-bridge.example:ghost:u123#key-1`），不得作为 `actor_id` / `bot_actor_id` 的一部分。

Ghost Actor MUST 带有 `accountability`，指向 Applet controller 和外部网络来源。

#### 3.4.1 Ghost Actor vs Native Personal Agent(CXP-0008 边界)

`actor_kind` 不定义 `agent_native`、`agent_ghost` 或 `ghost` wire enum。Native personal AI agent 使用 `actor_kind="agent"`；Applet-managed Ghost Actor 使用现有 enum 中最贴合其主体类型的值：外部人类/账号镜像 SHOULD 使用 `actor_kind="integration"`，Applet 托管的 AI/automation ghost MAY 使用 `actor_kind="agent"`。二者必须通过 Applet provenance、`accountable_principal_ids` / `accountability` 和 profile/capability 约束与 native personal agent 区分，不能依赖新增 `actor_kind` 值区分。

Native personal AI agent(由 controller 通过 `cx.agent.provision` 创建，见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md))与 Applet-managed Ghost Actor(本节)是两类不同 actor,生命周期与治理路径完全分离:

| 维度 | Native personal agent | Applet-managed Ghost Actor |
| --- | --- | --- |
| 创建路径 | `cx.agent.provision` operation,fan-out `cx.profile.create` / `cx.identity.accountability_grant` / `cx.agent.key.authorize` / `cx.capability.grant` | `cx.applet.registration` + Applet bot/Ghost Actor 注册 |
| `accountable_principal_ids` | 指向 controller principal,显式 `cx.identity.accountability_grant` | 指向 Applet controller / 外部系统 |
| Runtime credential | 通过 `POST /auth/account/agent-key-pair` pairing 得到 `cx.agent.key.authorize` 绑定的 key | Applet 管辖，通常是 Applet service DID + HTTP signature |
| Session 路径 | `POST /auth/account/session-grants` + `proof.proof_kind="agent_key_proof"` | Applet `cx.applet.transaction` 与 Applet 的 delegated session |
| 撤销 | `cx.agent.pause` / `cx.agent.deactivate` + fan-out key/grant revoke | Applet registration 撤销;Ghost Actor 跟随 Applet 生命周期 |
| Realm policy | Realm policy MUST 单独允许 native personal agent(`cx.profile.personal_agent_provisioning.v1`) | Realm policy MUST 单独允许 Applet + Ghost Actor(`cx.profile.applet_service.v1`) |

**Realm policy MUST 至少能分别控制 native personal agent 与 Applet / Ghost Actor**:部署可以禁止普通用户创建或使用 personal agents 同时允许管理员安装的 Applet + Ghost Actor,也可以反向配置;**二者不得被合并为一个不可区分的 "automation allowed" 开关**。

CXP-0008 / CXP-0009 只覆盖 native personal agent 路径;Ghost Actor / Applet Bot Actor 不走 CXP-0008 provisioning 或 CXP-0009 sidecar thread profile。

### 3.5 Portal Realm

外部网络 location 在 Cokret 中的镜像 Realm。例如 Slack channel、Discord guild channel、GitHub issue discussion。

## 4. Applet Registration

Applet MUST 有签名 registration。它可以由 Realm owner、组织管理员、registry 或 authz service 接受。

Applet 进入某个 Realm 的 capability MUST 由该 Realm owner、Realm admin 或 Realm policy 明确授权的 registry/authz service 签发。仅凭 Applet 自签 registration、namespace claim 或外部 registry 收录不得写入 Realm；缺少该 grant 时，任何 `cx.applet.registration` / `cx.applet.transaction` 引入的 Realm 写入 MUST 拒绝，reason=`applet_registration_unauthorized`。

示例：

```json
{
  "kind": "cx.applet.registration",
  "applet_id": "ck:applet:21532600-0000-7000-8000-000000000000",
  "service_did": "did:web:slack-bridge.example",
  "controller_did": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
  "base_url": "https://slack-bridge.example/api/v1/applet",
  "bot_actor_id": "did:web:slack-bridge.example:bot",
  "protocols": [
    "slack"
  ],
  "namespaces": {
    "actors": [
      {
        "exclusive": true,
        "pattern": "did:web:slack-bridge.example:ghost:*"
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
    "verification_method": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#admin-key-1",
    "payload_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
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
- Applet 可以为哪些 Ghost Actor 申请或声明身份

Namespace 不等于 capability。  
Namespace 命中只表示“这个 Applet 是该名称空间的处理方”。

### 5.1 Actor Namespace

Actor namespace 适用于 Ghost Actor 和 Bot Actor。

```json
{
  "exclusive": true,
  "pattern": "did:web:slack-bridge.example:ghost:*"
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
  "issuer": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
  "subject": "did:web:slack-bridge.example:bot",
  "claim_scope": {
    "realm_ids": [
      "ck:realm:0196419b-0000-7000-8000-000000000000"
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
      "via_applet_id": "ck:applet:21532600-0000-7000-8000-000000000000",
      "allowed_actor_namespace": "did:web:slack-bridge.example:ghost:*"
    }
  ],
  "expires_at": "2026-07-26T00:00:00Z"
}
```

除非 Applet 拥有 effective grant，或以委托授权身份显式代表已授权 actor 行事（此时 MUST 满足 [§11](#11-masquerading-与-delegated-agent) delegated agent 的全部字段 `executed_by` / `authorization_ref` / `applet_id` 与对应 reducer 校验），否则 Applet MUST NOT 向 Realm 写入。

## 7. Applet API

Applet API 是 Cokret 节点调用 Applet 的接口。  
Applet 调用 Cokret 节点时使用常规 Events API / sync service / authz API。

Base URL 来自 registration 的 `base_url`。

**`cx.applet.*` 标识符的两类用途（normative 区分）**：`cx.applet.*` 前缀的标识符根据上下文分属两个互不混淆的命名空间，实现不得把二者当作同一对象：

- **Event kind（进 Realm history）**：`cx.applet.registration`、`cx.applet.transaction`（指其作为 wire `Event.kind` 的语义，例如 §4 的 registration event、§8 写入的 transaction-origin event）、`cx.applet.bridge_error`（见 `applet-schema.md` §7）。这些是 durable Cokret Event，进入 Realm history，由 reducer 按 schema 校验。
- **operation_id（HTTP，不进 history）**：本节表中的 `cx.applet.ping`、`cx.applet.describe`、`cx.applet.transaction`、`cx.applet.resolve_actor`、`cx.applet.resolve_realm`、`cx.applet.protocol_metadata`、`cx.applet.third_party_users`、`cx.applet.third_party_locations` 是 HTTP API operation 标识符，只描述 Cokret 节点 ↔ Applet 的请求/响应绑定，本身不是 wire Event，不进入 Realm history。

注意 `cx.applet.transaction` 同时出现在两类用途：作 operation_id 时指 §7.3 的 transaction push HTTP 调用；作 Event kind 概念时指该 push 携带 / 触发的 durable Event。二者通过本说明显式区分（与 [`agent-protocol-interop.md` §7](./agent-protocol-interop.md) 对 capability action 与 `cx.agent.protocol_session.*` event kind 的区分写法一致）。

字段级接口索引：

| operation_id | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `cx.applet.ping` | 无 | 无 | `ok: boolean`; `applet_id: id`; `service_did: did`; `protocol_version: string` | 可公开，但不得泄露 private namespace。 |
| `cx.applet.describe` | 无 | 无 | `applet_id: id`; `service_did: did`; `protocols: string[]`; `namespaces: object`; `limits: object`; `auth: object` | public mode 只返回公开 capabilities。 |
| `cx.applet.transaction` | `header.Idempotency-Key: string`; `source_service_did: did`; `events: EventEnvelope[]` | `ephemeral: object[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | Applet MUST 验证来源 service DID、HTTP signature、event signature、namespace 和 capability。 |
| `cx.applet.resolve_actor` | `path.actor_id: did` | 无 | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | actor_id 必须命中 Applet actor namespace。 |
| `cx.applet.resolve_realm` | `path.realm_id_or_alias: string` | 无 | `exists: boolean`; `realm_id: id?`; `title: string?`; `external_ref: object?` | 必须命中 portal namespace 或授权查询。 |
| `cx.applet.protocol_metadata` | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob_ref: string?`; `field_types: object`; `instances: object[]?`（entry: `instance_id`, `display_name`） | instance list 可要求授权。 |
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
  "applet_id": "ck:applet:21532600-0000-7000-8000-000000000000",
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

Cokret sync service / Events API 向 Applet 推送事件批次。

请求示例（非完整 schema）：

```json
{
  "source_service_did": "did:web:server.example",
  "events": [
    {
      "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
      "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
      "kind": "cx.message.create",
      "actor_id": "did:web:alice.example",
      "payload": {}
    }
  ],
  "ephemeral": [
    {
      "type": "typing",
      "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
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

用于 Cokret 节点发现 namespace 内的未知 Ghost Actor 是否存在。

返回：

```json
{
  "exists": true,
  "actor_id": "did:web:slack-bridge.example:ghost:u123",
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
  "realm_id": "ck:realm:c0c69410-0000-7000-8000-000000000000",
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
  "icon_blob_ref": "ck:blob:sha256:...",
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
      "display_name": "Acme Slack"
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

用于把外部用户或 location 映射到 Cokret actor / portal Realm。

## 8. Applet 写入 Cokret

Applet 写入 Cokret MUST 使用常规 `/events` submit 接口。

每个写入 Event MUST 包含：

- `actor_id`
- `applet_id`
- `external_ref`，若来自外部网络
- `authorization_ref`
- `proof`

示例：

```json
{
  "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "ck:realm:c0c69410-0000-7000-8000-000000000000",
  "actor_id": "did:web:slack-bridge.example:ghost:u123",
  "kind": "cx.message.create",
  "applet_id": "ck:applet:21532600-0000-7000-8000-000000000000",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "event_id": "1714040000.000100"
  },
  "payload": {
    "flow_id": "ck:flow:c0c69410-0000-7000-8000-000000000001",
    "content": {
      "body": "hello from Slack"
    }
  },
  "proof": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:web:slack-bridge.example:ghost:u123#key-1",
    "payload_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
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
  "schema": "cx.schema.actor_profile.v1",
  "principal_id": "did:web:slack-bridge.example:ghost:u123",
  "actor_kind": "integration",
  "display_name": "Alice on Slack",
  "managed_by_applet": "ck:applet:21532600-0000-7000-8000-000000000000",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "user_id": "U123"
  },
  "accountability": {
    "mode": "applet_managed",
    "responsible_actor_id": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
    "operator_actor_ids": [
      "did:web:slack-bridge.example"
    ]
  }
}
```

Ghost Actor MUST NOT 被静默合并到 native DID，除非 native holder 显式声明并完成绑定。

## 10. Portal Realm

Portal Realm 把外部 location 映射到 Cokret。

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
  "authorization_ref": "ck:grant:0196410c-0000-7000-8000-000000000000",
  "applet_id": "ck:applet:8a0baad5-6000-7000-8000-000000000000"
}
```

**Reducer normative**:

- 当 Event 的 envelope signature 由 applet / delegated agent key 签发但 `actor_id` 指向 native principal DID 时（即 actor_id ≠ signing key 所属 DID），reducer MUST 校验：
  1. `executed_by` 必填，指向实际签发该 Event 的 applet / agent DID;`executed_by` 与 envelope signing key 的 DID 一致;
  2. `authorization_ref` 必填，指向已 accepted 的 `cx.capability.grant`(或等价 delegation event), 该 grant 把 actor_id 主体的某个 action 委托给 executed_by;
  3. `applet_id` 必填(在 Applet 模式下), 指向已注册的 applet;
  4. grant constraint MUST 绑定 `applet_id`、`executed_by` DID、`executed_by` DID Document epoch 证据和 registration epoch hash。对支持版本化的 DID method，epoch 证据 MUST 包含 method-specific version / log entry id；对**无版本化的 DID method（如部分 `did:web` 部署）**，grant MUST 绑定 service DID Document 的 **fetch-time digest**（canonical document hash）外加 **registration epoch hash**，reducer MUST 以 fetch-time digest 或 registration epoch 不匹配作为拒绝条件，不得因为 method 不提供显式版本号而豁免该绑定。Applet key rotate、DID Document endpoint 变化或 registration 更新后，旧 grant 不得继续授权新 key，除非 grant 明确声明可接受的 epoch range 并由 reducer 验证。
- 缺少 `executed_by`、`authorization_ref` 或 `applet_id` 中任一字段时,reducer MUST `schema_violation` 拒绝。该规则适用于所有 `cx.profile.applet_*` profile,客户端 / SDK 不得退回到 SHOULD 形态。

Applet MUST NOT use masquerading to hide automation. 客户端 MUST 明确展示 `via applet`：UI 在渲染 mention、notification、audit log、moderation queue 等任何"who did this"上下文时,MUST 同时显示 native actor 与 `executed_by` 双重署名，不得仅显示 native actor 而隐藏 applet 身份。

`requested_scopes` 只服务 consent / audit UI：registration 接受时，reviewer 可据此决定是否签发 capability grant；一旦 grant 写入，后续 reducer 只看 grant `actions[]` / selector / constraint，不再从 `requested_scopes` 推断权限。实现 MUST 在 audit log 中把最终 grant 与 registration `requested_scopes` 的差异显示给 reviewer，避免 Applet 请求 A、实际被授予 B 时无人可见。

## 12. E2EE

Applet 参与 E2EE Realm 时有三种模式：

1. Bot 作为正式成员加入 MLS group。
2. Ghost Actor 作为正式成员加入 portal Realm 的 MLS group。
3. Applet 不解密，只转发外部密文或桥接 metadata。

规则：

- Applet 没有加入 MLS group 时 MUST NOT 获得明文。
- Bridge 到不支持 E2EE 的外部网络时，客户端 MUST 明确提示加密边界在 bridge 处终止。
- Applet 托管 Ghost Actor MLS state 时，必须将其视为高敏感密钥材料。

**E2EE 加入授权（normative）**：Bot Actor 或 Applet-managed Ghost Actor 加入 E2EE Realm 的 MLS group（上文模式 1、2）MUST 经过独立的 **E2EE 加入授权**，该授权与普通的 capability grant（如 `cx.flow.create` / `cx.message.create` 等写入权限）**分立**：持有写入 capability 不自动授予把 applet / ghost 成员加入 MLS group 的权利。

- 该 E2EE 加入授权 MUST 由 Realm owner、Realm admin 或 Realm policy 明确授权的 authz service 签发（参照 §4 的 `applet_registration_unauthorized` 门槛），并落为可审计的 Cokret Event（如 `cx.member.state` 加入 effect 携带 applet provenance），不得仅凭 Applet 自身 Welcome 入组。
- 缺少该独立 E2EE 加入授权时，Cokret 客户端 MUST NOT 把 applet / ghost 成员加入 MLS group，并 MUST 以 `applet_e2ee_join_unauthorized` 拒绝该加入。
- 成员加入后，客户端在 MLS group 的成员 roster（成员列表 UI 与 audit 视图）中 MUST 显式标注该成员为 **applet-managed**（区别于 native 人类成员），不得让 applet / ghost 成员在 roster 中表现为普通 native 成员。该标注与 §9 的 Ghost Actor 协议层可区分要求一致。

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
- resolve actor
- resolve realm
- protocol metadata
- Ghost Actor accountability
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
- Applet UI widget sandbox MUST 与 Realm capability、origin isolation、CSP、token scoping 和 user consent 绑定；widget 不得直接获得 Cokret session token 或未授权 Event history access。该 sandbox 的字段与约束在 [§17 Applet UI Widget](#17-applet-ui-widget) 定义。

## 17. Applet UI Widget

部分 Applet 在 Cokret 客户端内嵌入 UI widget（如 Slack-style 交互卡片、配置面板）。Widget 在 host 客户端的信任边界内渲染，因此 MUST 被沙箱隔离。本节定义 §16 引用的 widget sandbox 的最小 normative 形态。

Widget 声明（registration 或 describe 响应内）SHOULD 包含：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `widget_origin` | `string`（origin） | required | Widget 内容来源 origin（scheme + host + port）。host 客户端 MUST 在隔离 origin（iframe sandbox 或等价机制）内加载 widget，MUST NOT 在 host 客户端自身 origin 下执行 widget 代码。 |
| `csp` | `string` | required | 适用于 widget 文档的 Content-Security-Policy。host 客户端 MUST 强制该 CSP，并 MUST NOT 放宽到允许 widget 访问 host 客户端的 DOM、storage 或 session。 |
| `token_scope` | `object` | required | Widget 可用 token 的 capability scope（action / resource selector / realm_ids / expiry）。该 token MUST 是为 widget 单独签发的 scoped token，scope MUST NOT 超出本字段声明的范围。 |
| `requires_consent` | `boolean` | required | 是否需要在加载前向用户展示 consent / capability 摘要。 |

约束（normative）：

- **Origin 隔离**：widget MUST 在与 host 客户端隔离的 origin 中运行；host 客户端 MUST NOT 把自身 origin 的 cookie、localStorage、IndexedDB 或 in-memory session 暴露给 widget。
- **Token scoping**：host 客户端 MUST NOT 把 Cokret 用户的 session token 或 device key 传给 widget；widget 只能拿到为其单独签发、scope 收敛到 `token_scope` 的短期 capability token，且该 token MUST NOT 超出 widget 声明的 scope。
- **History 读取不可越权**：widget MUST NOT 通过任何接口读取超出其 capability scope 的 Event history；host 客户端 MUST 以 widget 的 scoped capability 为准做 history 访问授权，未授权范围 MUST 拒绝。
- **Consent**：`requires_consent=true` 时，host 客户端 MUST 在加载 widget 前向用户展示其 origin 与请求 scope，未获 consent MUST NOT 加载。
