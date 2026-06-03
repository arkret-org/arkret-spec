---
title: Profiles And Presence
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

协作协议中，用户需要有可展示的身份信息（显示名、头像、状态消息），其他参与者也需要知道对方的在线状态。本规范定义了：

- Actor Profile 的标准字段与更新机制
- 在线状态 (Presence) 的广播与隐私保护
- 自定义状态消息

## 2. Actor Profile

### 2.1 Profile 对象

每个 Actor DID MAY 关联一个标准化的 `actor_profile` 对象，作为其公开身份信息。Profile 数据由 Actor 签名 Event 发布，并通过 Identity 解析或授权 Directory 被其他节点发现。对象字段以 [`../../artifacts/schemas/actor-profile.schema.json`](../../artifacts/schemas/actor-profile.schema.json) 为准；权限仍以 `principal_id` 指向的 DID / capability 为准。

```json
{
  "id": "ck:actor_profile:019640ab-0000-7000-8000-000000000000",
  "schema": "ck.schema.actor_profile.v1",
  "principal_id": "did:web:alice.example.com",
  "actor_kind": "user",
  "display_name": "Alice Chen",
  "handle": "alice",
  "avatar_blob_ref": "ck:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "status": "active",
  "profile_fields": {
    "status_message": "On vacation until May 5",
    "pronouns": "she/her",
    "timezone": "Asia/Shanghai",
    "locale": "zh-CN",
    "title": "Senior Engineer",
    "organization": "Acme Corp"
  },
  "created_at": "2026-04-26T00:00:00Z"
}
```

### 2.2 标准 Profile 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | id:actor_profile | MUST | Profile 对象 ID。 |
| `schema` | string | MUST | `ck.schema.actor_profile.v1`。 |
| `principal_id` | did | MUST | Actor / Principal DID。 |
| `actor_kind` | enum | MUST | `user`、`org`、`team`、`agent`、`service`、`device` 或 `integration`。 |
| `display_name` | string | MUST | 人类可读的显示名（最大 128 字符）。 |
| `handle` | string | 可选 | 本地或目录展示 handle。 |
| `avatar_blob_ref` | id:blob | 可选 | 头像图片的 Blob 引用。 |
| `status` | enum | 可选 | `active`、`suspended`、`deactivated` 或 `deleted`。 |
| `accountable_principal_ids` | did[] | 可选 | agent / service / 托管账号的责任主体。 |
| `profile_fields` | object | 可选 | 代词、时区、locale、状态消息、组织自定义字段等扩展展示字段。 |
| `created_at` | timestamp | MUST | 创建时间。 |
| `updated_by` | did | 可选 | 最近更新者；由 profile update Event actor 派生。 |
| `updated_at` | timestamp | 可选 | 最近更新时间。 |

### 2.3 Profile 创建与更新

Profile 初始状态通过 `ck.profile.create` Move / compatible Event 提交到 actor 的 principal control Realm。Move 写入以 `payload.object.id` 为 subject 的 profile cell。`payload.object.principal_id` MUST 等于提交者 `actor_id`，或等于由 capability / controller policy 明确授权的目标 principal：

```json
{
  "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
  "kind": "ck.profile.create",
  "realm_id": "ck:realm:01964166-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example.com",
  "actor_seq": 1,
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0001-a13f9c2e",
  "prev_refs": [],
  "refs": [],
  "payload": {
    "object": {
      "id": "ck:actor_profile:019640ab-0000-7000-8000-000000000000",
      "schema": "ck.schema.actor_profile.v1",
      "principal_id": "did:web:alice.example.com",
      "actor_kind": "user",
      "display_name": "Alice Chen",
      "handle": "alice",
      "avatar_blob_ref": "ck:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "status": "active",
      "profile_fields": {
        "timezone": "Asia/Shanghai",
        "locale": "zh-CN"
      },
      "created_at": "2026-04-26T00:00:00Z"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example.com#key-1",
      "event_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..c2ln"
    }
  ]
}
```

Profile 后续变更通过 `ck.profile.update` Move / compatible Event 提交。该 payload 使用 `object_patch_payload`；Move 使用 `payload.target_ref` 与 `ck.profile.create` 共用同一 profile cell。变更字段放在 `payload.patch`，不得使用旧的顶层 `actor` / `body` 形态：

```json
{
  "event_id": "ck:event:019640ed-8400-7000-8000-000000000000",
  "kind": "ck.profile.update",
  "realm_id": "ck:realm:01964166-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example.com",
  "actor_seq": 2,
  "created_at": "2026-04-26T00:01:00Z",
  "hlc": "01970e598d21-0001-a13f9c2e",
  "prev_refs": ["ck:event:019640ed-8000-7000-8000-000000000000"],
  "refs": [
    { "id": "ck:event:019640ed-8000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "payload": {
    "target_ref": "ck:actor_profile:019640ab-0000-7000-8000-000000000000",
    "patch": {
      "display_name": "Alice C.",
      "profile_fields.status_message": "Back at work!"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example.com#key-1",
      "event_digest": "sha256:6b5ad6b5ad6b7ad6b5ad6b5ad6b5ad6b6b5ad6b5ad6b7ad6b5ad6b5ad6b5ad6b",
      "created_at": "2026-04-26T00:01:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..c2ln"
    }
  ]
}
```

- `ck.profile.create` 初始化完整对象；`ck.profile.update` 仅携带发生变化的字段（delta 更新）
- 其他参与者的客户端通过 Sync Service 的 Sync Stream 或 Actor Events API 同步获取最新 Profile
- 客户端 MAY 缓存 Profile 并在本地查询响应中内联展示

`ck.profile.create` 与 `ck.profile.update` 是 principal-scoped profile state。顶层 `realm_id` MUST 是该 actor 的 `principal_control_realm_id`；不得把全局 profile 更新写入任意 Collaboration Realm history（Principal Control Realm 与 Collaboration Realm 的分类见 [`models/realm-and-space.md` §2.7](../models/realm-and-space.md)）。两 kind 共写入同一 cell `ck:cell:ck.component.profile.v1:<target_actor_profile_id>`（cas_register, bottom=reject），`cell_subject` 由 schema registry 派生（create 用 `payload.object.id`，update 用 `payload.target_ref`，必须等值）。

### 2.4 Per-Realm Profile 覆写

用户 MAY 为特定 Realm 设置不同的显示名或头像（例如在公司 Realm 用真名，在开源项目 Realm 用昵称）：

`ck.profile.space_override` 是保留的 wire kind 名称；其语义是 Realm-scoped profile override，目标 Realm 由 `payload.target_realm_id` 唯一指定，不指向 `ck:space:` 容器，也不创建 Space 级访问边界。

```json
{
  "event_id": "ck:event:019640ed-8800-7000-8000-000000000000",
  "kind": "ck.profile.space_override",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example.com",
  "actor_seq": 3,
  "created_at": "2026-04-26T00:02:00Z",
  "hlc": "01970e5a8d21-0001-a13f9c2e",
  "prev_refs": ["ck:event:019640ed-8400-7000-8000-000000000000"],
  "refs": [
    { "id": "ck:event:019640ed-8400-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "payload": {
    "target_ref": "ck:actor_profile:019640ab-0000-7000-8000-000000000000",
    "target_realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
    "patch": {
      "display_name": "alice-oss",
      "avatar_blob_ref": {
        "$op": "unset"
      }
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example.com#key-1",
      "event_digest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "created_at": "2026-04-26T00:02:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..c2ln"
    }
  ]
}
```

- Realm 覆写的优先级高于全局 Profile
- `null` 值表示使用全局 Profile 的对应字段
- `ck.profile.space_override` MUST 同时绑定 actor DID 与目标 Realm。若作为共享 Realm history 传播，顶层 `realm_id` 是目标 Realm，事件必须通过目标 Realm 的 membership / visibility / policy 校验；若作为 actor-private 或 principal control profile state 传播，content MUST 显式包含目标 Realm id，projection 服务只可向有权读取该 Realm profile override 的请求方披露。

## 3. 在线状态 (Presence)

### 3.1 Presence 是 Ephemeral 状态

在线状态属于高频变动的临时数据，MUST NOT 作为 Durable Event 写入 Event history。它通过 Sync Service 的 Ephemeral Channel 广播。

### 3.2 Presence 状态值

| 状态 | 含义 |
|------|------|
| `online` | 用户当前活跃在线 |
| `idle` | 用户在线但一段时间无操作 |
| `offline` | 用户离线 |
| `dnd` | 勿扰模式（在线但不希望被打扰） |

### 3.3 Presence 广播格式

通过 Sync Service 的 Ephemeral Channel 广播：

```json
{
  "kind": "ck.presence",
  "actor_id": "did:web:alice.example.com",
  "state": "online",
  "status_message": "On vacation until May 5",
  "ttl_ms": 60000
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `state` | string | MUST | 状态值 |
| `actor_id` | did | MUST | 发送 presence 的 actor DID。 |
| `last_active_at` | string | 可选 | 最后活跃时间。默认 MUST 省略，或按 policy bucket 化为粗粒度（例如分钟 / 小时级）；**仅当** presence policy 显式允许精确披露时才发送精确（秒级）timestamp。精确秒级值会成为活动 timing 侧信道，因此不得作为默认行为。 |
| `status_message` | string | 可选 | 当前状态消息（来自 Profile）。MUST ≤ 256 字符（Unicode code point 计），按 [`conformance/encoding.md` §2.1](../conformance/encoding.md) NFC 规范化，MUST NOT 含除 `U+0009`/`U+000A` 外的 C0/C1 控制字符。presence 广播的 `status_message` MAY 与 Profile 的 `profile_fields.status_message` 不同（presence 可为临时覆盖值），但两者受同一长度与规范化约束。 |
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
| `public` | 所有共同 Realm 的成员可见 |
| `contacts_only` | 仅对明确的联系人可见 |
| `nobody` | 完全隐藏在线状态（对所有人显示为 offline） |

当 `presence_visibility="nobody"` 时，客户端 MUST NOT 发送 `ck.presence`，Sync Service MUST NOT 转发既有或缓存的 `ck.presence`；接收方看到的结果必须与从未收到 presence 一致。

### 3.5 Typing 指示器

正在输入状态通过 Sync Service 的 Ephemeral Channel 广播，格式极度轻量：

```json
{
  "kind": "ck.typing",
  "actor_id": "did:web:alice.example.com",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "flow_id": "ck:flow:01964200-0000-7000-8000-000000000001",
  "typing": true,
  "ttl_ms": 5000
}
```

- `ttl_ms` 到期后客户端应自动清除 Typing 指示
- 客户端 SHOULD 限制 Typing 广播频率（建议每 3 秒最多一次）
- 客户端 SHOULD 在用户停止输入后主动发送 `typing: false`
- Typing 指示器 MUST 遵循与 Presence 至少同等严格的可见性策略：当 `presence_visibility="nobody"` 或接收方不在允许集合内时，不得发送或转发 `ck.typing`；`contacts_only` 时只可发给明确联系人且仍需满足 Realm membership / history visibility。
- Sync Service 转发 typing 前 MUST 同时检查发送者与接收者在目标 Flow effective scope（Realm-default 或 Circle）的可见性、personal blocklist 过滤结果和 `discussion` track 状态。被屏蔽、无权读取 discussion、或不可枚举的接收方 MUST 看到与未发生 typing 一致的空结果，不得收到可区分的拒绝。

## 4. 用户目录 (User Directory)

### 4.1 搜索接口

Directory Service 或客户端本地联系人索引 MAY 提供用户搜索功能，用于 `@mention` 自动完成和联系人发现。

> **Normative 源（normative）**：`search-users` 的 operation 形态、授权过滤、分页字段（`has_more` / `next_cursor`）以 [`discovery-directory.md` §9](./discovery-directory.md) `ck.directory.search_users` 为**唯一规范源**；本节只补充 presence / mention 特有的 UI 语义（`results[].membership`、autocomplete intent 等）。下表字段与 directory §9 冲突时以 directory §9 为准。

```
POST /_cokret/find/directory/search-users

{ "query": "alice", "realm_id": "ck:realm:...", "limit": 10 }
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `query` | body | `string` | required | 搜索关键词；不得进入 URL、Referer 或未脱敏 access log。 |
| `realm_id` | body | `id` | optional | 限定共同 Realm；mention autocomplete SHOULD 提供。 |
| `limit` | body | `int` | optional | 返回数量上限；服务端 MUST enforce 最大值。 |
| `intent` | body | `enum(mention,invite,member_add)` | optional | 调用意图；影响是否允许返回 `member_delivery_binding`。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `results` | `object[]` | required | 授权可发现的用户结果。 |
| `results[].handle` | `string` | optional | 可展示 / 可再次 resolve 的 handle。未满足 claim / audience / requester policy 时，结果 SHOULD 只返回 handle 或 display preview，不返回 DID。 |
| `results[].did` | `did` | conditional | 用户 DID。仅当请求方已通过 `resolve-handle` 所需的 claim / presentation / audience / Realm intent 验证，或结果来自调用方本地联系人索引且 DID 已由用户本地持有时才可返回。共同 Realm membership 不得单独授权披露。 |
| `results[].member_delivery_binding` | `object` | conditional | 仅在 `intent ∈ {invite, member_add}` 且 claim 明确授权该 Realm / requester 获取投递上下文时返回；不得用于普通 mention autocomplete。 |
| `results[].display_name` | `string` | optional | 显示名。 |
| `results[].avatar_blob_ref` | `id:blob` | optional | 头像 Blob 引用；字段名与 Actor Profile canonical 字段保持一致。 |
| `results[].membership` | `string` | optional | 与 `realm_id` 相关的成员状态。 |
| `next_cursor` | `cursor` | optional | 下一页 cursor；分页语义与 [`discovery-directory.md` §9](./discovery-directory.md) `ck.directory.search_*` 一致。 |
| `has_more` | `boolean` | optional | 是否还有更多结果（取代旧 `limited` 字段，统一对齐 directory §9 的 `has_more` 约定）。 |

响应示例（非完整 schema）：

```json
{
  "results": [
    {
      "handle": "alice@example.com",
      "display_name": "Alice Chen",
      "avatar_blob_ref": "ck:blob:sha256:a1b2c3...",
      "membership": "joined"
    }
  ],
  "has_more": false,
  "next_cursor": null
}
```

### 4.2 搜索范围

- 默认搜索当前 Realm 的成员
- 可选扩展到同一组织域下的所有已知用户
- 不应跨域搜索未授权的外部用户
- `search-users` 是候选发现接口，不是身份解析接口；需要得到 `subject` DID 或 `member_delivery_binding` 时，客户端 MUST 调用 `resolve-handle` 并满足其 claim / audience / requester policy。

## 5. v1 规则

- 头像若公开可见，必须使用公开 blob 或公开缩略图；私有或 E2EE Realm 的头像/图标应使用 authenticated media 或加密 blob，服务端不得因头像请求泄露 Realm 存在性。
- Profile 字段 MUST 受 schema 验证。组织可通过 Organization policy 限定 `profile_fields` 的字段名、类型、最大长度、敏感性和披露范围。
- Presence 跨域联邦默认 opt-in，必须短 TTL、最小字段、按关系或 Realm policy 授权；不得用 presence 推断 pairwise DID、私有组织成员资格或隐藏 Realm 拓扑。
- 群组 Profile 是 Realm metadata 的投影；Realm 名称、图标、描述、公告和可发现性必须受 Realm policy、history visibility 和 directory filtering 控制。
