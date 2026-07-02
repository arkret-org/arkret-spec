---
title: Profiles And Presence
status: candidate
normative: true
stability: v1
updated: 2026-07-03
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

协作协议中，用户需要有可展示的身份信息（显示名、头像、状态消息），其他参与者也需要知道对方的在线状态。本规范定义了：

- Actor Profile 的标准字段与更新机制
- 在线状态 (Presence) 的广播与隐私保护
- 自定义状态消息
- 手动状态偏好（用户主动固定状态）、状态过期与多设备聚合

## 2. Actor Profile

### 2.1 Profile 对象

每个 Actor DID MAY 关联一个标准化的 `actor_profile` 对象，作为其公开身份信息。Profile 数据由 Actor 签名 Event 发布，并通过 Identity 解析或授权 Directory 被其他节点发现。对象字段以 [`../../artifacts/schemas/actor-profile.schema.json`](../../artifacts/schemas/actor-profile.schema.json) 为准；权限仍以 `principal_id` 指向的 DID / capability 为准。

```json
{
  "id": "ck:actor_profile:019640ab-0000-7000-8000-000000000000",
  "schema": "ck.schema.actor_profile.v1",
  "realm_id": "ck:realm:01964166-0000-7000-8000-000000000000",
  "principal_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
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
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
  "updated_at": "2026-04-26T00:01:00Z"
}
```

字段顺序与 §2.2 表 / canonical schema property ordering 一致（…`schema`、`realm_id`、`principal_id`、`actor_kind`、`display_name`、`handle`、`agent_slug`、`avatar_blob_ref`、`status`、`accountable_principal_ids`、`profile_fields`、`created_at`、`updated_by`、`updated_at`）；`realm_id`、`updated_by` / `updated_at` 为可选字段，初始 `ck.profile.create` 后尚未发生更新时 MAY 省略。

### 2.2 标准 Profile 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | id:actor_profile | MUST | Profile 对象 ID。 |
| `schema` | string | MUST | `ck.schema.actor_profile.v1`。 |
| `realm_id` | id:realm | 可选 | Profile state 所属的 principal control Realm 或 profile materialization scope。存在时 MUST 与承载该 profile create/update 的 principal control Realm 或授权 materialization scope 一致；不得被当作协作 Realm membership 或读取权限。 |
| `principal_id` | did | MUST | Actor / Principal DID。 |
| `actor_kind` | enum | MUST | `user`、`org`、`team`、`agent`、`service` 或 `integration`（不含 `device`：设备非 actor 主体，见 [`../models/actor.md` §2](../models/actor.md)）。 |
| `display_name` | string | MUST | 人类可读的显示名（最大 128 字符）。 |
| `handle` | string | 可选 | 本地或目录展示 handle。经 Directory / projection 披露时同受 §5 handle 披露 gate 约束（不得旁路 handle 搜索披露限制）。 |
| `agent_slug` | string | 可选 | native personal agent 的 controller-scoped selector projection。必须由当前有效 `ck.schema.agent_selector_claim.v1` 支撑；只与 controller handle 组合为 `@<controller-handle>/<agent_slug>` 输入别名；不是全局 handle 或公开目录发现键。 |
| `avatar_blob_ref` | id:blob | 可选 | 头像图片的 Blob 引用。 |
| `status` | enum | 可选 | `active`、`suspended`、`deactivated` 或 `deleted`。 |
| `accountable_principal_ids` | did[] | 可选 | agent / service / 托管账号的责任主体。 |
| `profile_fields` | object | 可选 | 代词、时区、locale、状态消息、组织自定义字段等扩展展示字段。其中子字段 `status_message` MUST ≤ 256 字符（Unicode code point 计），与 presence 广播的 `status_message`（§3.3）受同一长度与规范化约束。 |
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
  "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
  "actor_seq": 1,
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0001-a13f9c2e",
  "prev_refs": [],
  "refs": [],
  "payload": {
    "object": {
      "id": "ck:actor_profile:019640ab-0000-7000-8000-000000000000",
      "schema": "ck.schema.actor_profile.v1",
      "realm_id": "ck:realm:01964166-0000-7000-8000-000000000000",
      "principal_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
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
      "verification_method": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com#key-1",
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
  "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
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
      "verification_method": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com#key-1",
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

`ck.profile.create` 与 `ck.profile.update` 是 principal-scoped profile state。顶层 `realm_id` MUST 是该 actor 的 `principal_control_realm_id`；不得把全局 profile 更新写入任意 Collaboration Realm history（Principal Control Realm 与 Collaboration Realm 的分类见 [`models/realm-and-space.md` §2.8](../models/realm-and-space.md)）。两 kind 共写入同一 cell `ck:cell:ck.component.profile.create.v1:<target_actor_profile_id>`（mv_register, bottom=expose），`cell_subject` 由 schema registry 派生（create 用 `payload.object.id`，update 用 `payload.target_ref`，必须等值）。

### 2.4 Per-Realm Profile 覆写

用户 MAY 为特定 Realm 设置不同的显示名或头像（例如在公司 Realm 用真名，在开源项目 Realm 用昵称）：

`ck.profile.realm_override` 是 Realm-scoped profile override 事件 kind，目标 Realm 由 `payload.target_realm_id` 唯一指定，不指向 `ck:space:` 容器，也不创建 Space 级访问边界。

```json
{
  "event_id": "ck:event:019640ed-8800-7000-8000-000000000000",
  "kind": "ck.profile.realm_override",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
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
      "verification_method": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com#key-1",
      "event_digest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "created_at": "2026-04-26T00:02:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..c2ln"
    }
  ]
}
```

- Realm 覆写的优先级高于全局 Profile
- `null` 值表示使用全局 Profile 的对应字段
- `ck.profile.realm_override` MUST 同时绑定 actor DID 与目标 Realm。若作为共享 Realm history 传播，顶层 `realm_id` 是目标 Realm，事件必须通过目标 Realm 的 membership / visibility / policy 校验；若作为 actor-private 或 principal control profile state 传播，content MUST 显式包含目标 Realm id，projection 服务只可向有权读取该 Realm profile override 的请求方披露。
  - _Informative._ `ck.profile.realm_override` 是显示层 per-Realm 覆写，绑定同一 `principal_id`,**不提供跨 Realm 不可关联性(unlinkability)**:能同时读取同一 principal 在多个 Realm override 的请求方可关联这些化名。需要跨 Realm 不可关联的化名时，应使用 Realm-scoped pairwise DID(见 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) minimal-metadata / pairwise 身份),而非依赖 realm_override。

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

`state` 是 v1 闭集：仅上表四值合法。接收方遇到未知 `state` 值 MUST 丢弃该 presence update 或按 `schema_violation` fail closed，MUST NOT 猜测映射为近似状态（历史实现遗留的 `unavailable`、`busy` 等值不是 v1 wire 值）。

- _Informative._ "忙碌 / 会议中 / 请勿打扰"一类用户主动设置的繁忙态统一映射为 `dnd`，更细的语义（例如"开会中"、"烦躁"）通过 `status_message`（§3.3）表达；v1 不为具体情绪 / 场景扩充 `state` 枚举。"隐身"（自己在线但对他人显示离线）也不是 `state` 值，通过 `ck.presence.visibility="nobody"`（§3.4）实现，从而把状态语义与可见性策略分离。
- `state` 可以由客户端自动判定（前台活跃 → `online`、无操作超时 → `idle`），也可以由用户通过手动状态偏好固定（§3.6）；两者的仲裁规则见 §3.6。

### 3.3 Presence 广播格式

通过 Sync Service 的 Ephemeral Channel 广播：

```json
{
  "kind": "ck.presence",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
  "device_id": "ck:device:019640dd-8000-7000-8000-000000000000",
  "sent_at": "2026-04-26T10:00:00Z",
  "expires_at": "2026-04-26T10:01:00Z",
  "payload": {
    "state": "online",
    "status_message": "On vacation until May 5",
    "ttl_ms": 60000
  },
  "proof": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com#ck:device:019640dd-8000-7000-8000-000000000000",
    "event_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "created_at": "2026-04-26T10:00:00Z",
    "jws": "eyJhbGciOiJFZERTQSJ9..c2ln"
  }
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `state` | string | MUST | 状态值 |
| `actor_id` | did | MUST | 发送 presence 的 actor DID。 |
| `device_id` / `proof` | id:device / object | MUST | 所有 `ck.presence` 广播 MUST 携带来源设备与 detached proof；`proof.verification_method` 的 controller DID MUST 等于 `actor_id`，fragment MUST 等于 `device_id`。 |
| `last_active_at` | string | 可选 | 最后活跃时间，承载两种互斥 wire 形态，由值中是否含 `/` 判别：（1）精确形态为 RFC 3339 UTC timestamp（如 `2026-04-26T10:00:00Z`，不含 `/`）；（2）bucket 形态为 ISO 8601 interval `<start>/<duration>`（如 `2026-04-26T10:00:00Z/PT1H`，含 `/`）。接收方 MUST 据是否含 `/` 选择解析路径。默认 MUST 省略，或按 policy bucket 化为粗粒度（例如分钟 / 小时级）；**仅当** presence policy 显式允许精确披露时才发送精确（秒级）timestamp。精确秒级值会成为活动 timing 侧信道，因此不得作为默认行为。 |
| `status_message` | string | 可选 | 当前状态消息（来自 Profile）。MUST ≤ 256 字符（Unicode code point 计），按 [`conformance/encoding.md` §2.1](../conformance/encoding.md) NFC 规范化，MUST NOT 含除 `U+0009`/`U+000A` 外的 C0/C1 控制字符。presence 广播的 `status_message` MAY 与 Profile 的 `profile_fields.status_message` 不同（presence 可为临时覆盖值），但两者受同一长度与规范化约束。 |
| `ttl_ms` | integer | SHOULD | 存活时间（毫秒），超时后客户端应将该用户视为 offline |

当 presence policy 未显式允许精确披露时，`last_active_at` 默认省略；若 policy 要求携带粗粒度活跃度，MUST 以 bucket 化形态发送，bucket 边界（分钟 / 小时级）按 policy 声明，确定性编码，不得发送秒级精确 timestamp。bucket 化广播示例：

`last_active_at` 解析必须是确定性的：若值中包含 `/`，接收方 MUST 按 ISO 8601 interval `<start>/<duration>` 解析，且值中必须恰好一个 `/`，`start` 必须是 RFC 3339 UTC timestamp，`duration` 必须是正 ISO 8601 fixed-duration，且 `duration >= PT60S`；`P1M` / `P1Y` 等日历长度不固定的 duration 不得用于 presence bucket。bucket 对齐以 Unix epoch UTC 为唯一原点：`aligned_start = floor(unix_seconds(start) / seconds(duration)) * seconds(duration)`。若值中不包含 `/`，接收方 MUST 按 RFC 3339 UTC timestamp 解析。解析失败、本地时区表示、缺少 `Z`、duration 为零或负数、duration 小于 `PT60S`、非 fixed-duration、额外 `/`、**`start` 未对齐到 `duration` 边界**（接收方据上述 Unix epoch UTC 算法独立重算 `start` 应有的对齐值并比对，未对齐即视为畸形）、或试图修补 / 猜测畸形值时，接收方 MUST 丢弃该 presence update 或按 `schema_violation` fail closed，不得降级为更精确或更宽松的活跃度显示。该接收方对齐与下界校验闭合"发送方（buggy 或恶意）以未对齐或过细 duration 的值把 bucket 退化为秒级活动 timing 侧信道"——发送方对齐（见下）是单侧 MUST，接收方独立复核构成两侧闭合。

```json
{
  "kind": "ck.presence",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
  "device_id": "ck:device:019640dd-8000-7000-8000-000000000000",
  "sent_at": "2026-04-26T10:00:00Z",
  "expires_at": "2026-04-26T10:01:00Z",
  "payload": {
    "state": "idle",
    "last_active_at": "2026-04-26T10:00:00Z/PT1H",
    "ttl_ms": 60000
  },
  "proof": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com#ck:device:019640dd-8000-7000-8000-000000000000",
    "event_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "created_at": "2026-04-26T10:00:00Z",
    "jws": "eyJhbGciOiJFZERTQSJ9..c2ln"
  }
}
```

该 wire 值表示"最后活跃落在以 `2026-04-26T10:00:00Z` 为起点、粒度 `PT1H`（1 小时）的 bucket 内"，bucket 起点 MUST 按 policy 声明的粒度向下取整对齐（同一 bucket 内任意精确时间映射到同一 wire 值），使接收方无法据此还原秒级活动 timing。bucket 粒度（`duration`）MUST NOT 细于 policy 声明的最小粒度下限，且协议绝对下界为 `PT60S`：过细的 bucket 会使边界采样退化为接近秒级的活动 timing 侧信道，与"不还原秒级 timing"的目的相悖。

**多设备聚合（normative）**：同一 `actor_id` 的多个设备 MAY 并发广播 `ck.presence`（各自携带自己的 `device_id` / `proof`）。观察者（客户端，或做服务端投影聚合的 Sync Service）MUST 把该 actor 全部未过期（`expires_at` 未到且 `ttl_ms` 未超时）的广播聚合为单一 actor presence，聚合规则必须确定性：

1. `state` 取未过期信号中优先级最高者，优先级为 `dnd > online > idle`；没有任何未过期信号时该 actor 视为 `offline`。
2. `status_message` 取未过期信号中 `sent_at` 最新的非空 `status_message`；均无时客户端 SHOULD 回退展示 Profile 的 `profile_fields.status_message`（§2.2）。
3. `last_active_at`（若按 policy 披露）取未过期信号中最新的值；比较前 MUST 先按本节解析校验，畸形值 fail closed 丢弃、不参与聚合。

手动状态偏好（§3.6）的跨设备一致性由发送侧保证（各设备读取同一份 account data），接收方不区分某个 `state` 是自动判定还是手动固定，聚合规则不变。

presence 广播内的 `status_message` 是临时覆盖值，展示优先级高于 Profile 的持久 `profile_fields.status_message`；presence 信号全部过期后，客户端 SHOULD 回退展示持久值。

### 3.4 隐私控制

用户可以控制 Presence 的可见范围：

该策略的标准存储位置是 actor-private Account Data key `ck.presence.visibility`（见 [`account-data-type-registry.json`](../../artifacts/registry/account-data-type-registry.json)）。写入通过 `ck.account_data.set` 完成，payload MUST 是下列形态；缺省等价于 `{ "presence_visibility": "public" }`。

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

`ck.presence.visibility` 是 principal-private policy projection：Principal / Sync Service MAY 读取并投影其中的 `presence_visibility` enum，用于执行 `ck.presence` 与 `ck.typing` 的提交、读取和 fanout gate；服务端不得借此读取或披露 Profile 字段、`status_message`、联系人备注、精确 `last_active_at` 或其它 account data 明文。若服务端无法读取该最小 policy projection（例如部署选择端到端 opaque account data 且没有受托投影服务），它 MUST 对跨设备 / 跨接收方 fanout fail closed：不得把 presence 或 typing 转发给不能在本地证明属于允许集合的接收方。

**来源真实性（normative）**：Sync Service 接收 `ck.presence` / `ck.typing` 时 MUST 同时校验提交会话的 authenticated principal 与 envelope `actor_id` 一致、`proof` 验证通过、`proof.verification_method` 控制者等于 `actor_id` 且 fragment 等于 `device_id`。跨服务、联邦或 relay 转发的 presence / typing 若无法验证该 proof，接收方 MUST 丢弃；服务端签名的转发断言只能作为传输层 provenance，不能替代 actor device proof。携带自由文本 `status_message` 的 presence 不得走 unsigned 路径。

**`contacts_only` 的"联系人"集合真源与 fail-closed（normative）**：`contacts_only` 中的"明确联系人"集合 MUST 取自 [`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md) 的 `ck.contact.*` accepted-contact fact log，**不是** `ck.presence.visibility` 的 enum，也不是 client-preferences 的本地联系人备注（备注不打开 presence gate）。服务端执行 `contacts_only` gate 需要可读的 accepted-contact 投影；当服务端无法读取该 contacts 集合（未托管该投影 / 端到端 opaque）时，`contacts_only` MUST 与上一段一致 fail closed——退化为客户端本地 gate、MUST NOT 退化为 `public`，即对不能在本地证明属于 accepted-contact 集合的接收方不转发。

当 `presence_visibility="nobody"` 时，客户端 MUST NOT 发送 `ck.presence`，Sync Service MUST NOT 转发既有或缓存的 `ck.presence`；接收方看到的结果必须与从未收到 presence 一致。

`dnd` / `idle` 会泄露"用户在线但勿扰 / 空闲"，可被用于推断作息，属与 `last_active_at` 同类的活动侧信道。对不在 presence 可见集合内（不满足 `presence_visibility` 授权）的观察者，`dnd` / `idle` MUST 降级为 `offline` 或与 `online` 不可区分，不得向其暴露细分的勿扰 / 空闲状态；该降级与 `presence_visibility="nobody"` 的 MUST 隐藏同强度，避免 dnd/idle 成为绕过授权的活动侧信道。满足 `presence_visibility` 授权的观察者（授权集内）MAY 保留 `dnd` / `idle` 细分。

### 3.5 Typing 指示器

正在输入状态通过 Sync Service 的 Ephemeral Channel 广播，格式极度轻量：

```json
{
  "kind": "ck.typing",
  "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "device_id": "ck:device:019640dd-8000-7000-8000-000000000000",
  "sent_at": "2026-04-26T10:00:00Z",
  "expires_at": "2026-04-26T10:00:05Z",
  "payload": {
    "strand_id": "ck:strand:01964200-0000-7000-8000-000000000001",
    "track_name": "discussion",
    "typing": true,
    "ttl_ms": 5000
  },
  "proof": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com#ck:device:019640dd-8000-7000-8000-000000000000",
    "event_digest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "created_at": "2026-04-26T10:00:00Z",
    "jws": "eyJhbGciOiJFZERTQSJ9..c2ln"
  }
}
```

payload 形状由 [`ephemeral-envelope.schema.json`](../../artifacts/schemas/ephemeral-envelope.schema.json) 的 `ck.typing` 分支约束：`strand_id` 与 `typing` 必填，`track_name` / `ttl_ms` 可选。

- `track_name` 标识正在输入的目标 track，口径与 `ck.message.create` payload 的 `track_name` 一致（[`message.schema.json`](../../artifacts/schemas/message.schema.json)）：v1 Message 时间线限定在 `discussion` track，因此 present 时 MUST 为 `"discussion"`；省略时接收方 MUST 解析为 `discussion`。携带其他值的信号 MUST 被拒收（`schema_violation`）。该字段为未来声明多可写时间线的 profile 预留定位维度，届时放宽枚举即可，不需要改信封结构。
- `ttl_ms` 到期后客户端应自动清除 Typing 指示
- 客户端 SHOULD 限制 Typing 广播频率（建议每 3 秒最多一次）
- 客户端 SHOULD 在用户停止输入后主动发送 `typing: false`
- Typing 指示器 MUST 遵循与 Presence 至少同等严格的可见性策略：当 `presence_visibility="nobody"` 或接收方不在允许集合内时，不得发送或转发 `ck.typing`；`contacts_only` 时只可发给明确联系人且仍需满足 Realm membership / history visibility。
- Sync Service 转发 typing 前 MUST 同时检查发送者与接收者在目标 Strand effective scope（Realm-default 或 Circle）的可见性、personal blocklist 过滤结果和目标 track（payload `track_name`，省略解析为 `discussion`）的启用状态。被屏蔽、无权读取目标 track、或不可枚举的接收方 MUST 看到与未发生 typing 一致的空结果，不得收到可区分的拒绝。
- **world_readable scope fail-closed（normative）**：typing 是逐键级实时活动信号，比 presence `last_active_at` 更细。在 `history_visibility=world_readable` 的 Realm / Strand 且对外可见的 scope 下，Sync Service MUST NOT 主动把 `ck.typing` fanout 给非成员的外部 world-readable 观察者；typing 的 fanout 目标 MUST 限制在该 Strand effective scope 的 active member 集合内（`scope_circle_id` 指向 Circle 时为该 Circle 成员）。该口径与 [read-receipts.md §2.5.1](./read-receipts.md) 的 receipt fanout 收口对齐——"历史 world-readable"（读取已落库历史）不等于"实时活动信号 world-readable"（主动广播逐键 typing），二者解耦：world-readable 历史可见性不构成把 typing 主动推送给非成员外部观察者的义务。

### 3.6 手动状态偏好 (Manual Presence Preference)

自动状态判定（前台活跃 → `online`、无操作超时 → `idle`、断连 / TTL 过期 → `offline`）覆盖大多数场景，但用户还需要能把自己的状态主动固定为某个值（例如切到 `dnd` 开会），且该选择要跨设备、跨重连生效。presence 广播本身是 ephemeral（§3.1），不承担持久化；手动偏好的标准存储位置是 actor-private Account Data key `ck.presence.preference`（见 [`account-data-type-registry.json`](../../artifacts/registry/account-data-type-registry.json)），通过 `ck.account_data.set` 写入，payload 形态：

```json
{
  "manual_state": "dnd",
  "status_message": "开会中，稍后回复",
  "clears_at": "2026-07-03T12:00:00Z"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `manual_state` | enum | 可选 | `online`、`idle` 或 `dnd`（§3.2 闭集去掉 `offline`）。缺省表示恢复自动判定。"隐身"不是 `manual_state` 值，MUST 通过 `ck.presence.visibility="nobody"`（§3.4）实现；`offline` 由停止广播 / TTL 过期自然表达，不作为可固定值。 |
| `status_message` | string | 可选 | 临时状态消息覆盖值，作为该 principal 各设备广播 `ck.presence` 时 payload `status_message` 的来源；长度与规范化约束同 §3.3（≤256 字符、NFC、控制字符限制）。 |
| `clears_at` | timestamp | 可选 | 过期时间（RFC 3339 UTC）。到期后整份偏好等价于缺省：客户端 MUST 恢复自动状态判定并停止广播其中的临时 `status_message`。缺省表示手动偏好持续生效，直到被显式改写或清除。 |

规则（normative）：

- 存在未过期 `manual_state` 时，该 principal 的**所有**设备广播 `ck.presence` 的 `state` MUST 等于 `manual_state`；本地自动 idle 检测 MUST NOT 覆盖它。设备离线仍由广播缺失 / TTL 过期自然表现为 `offline`（§3.3 多设备聚合）。
- `ck.presence.preference` 是**发送侧执行**的端侧偏好：执行主体是该 principal 自己的客户端。服务端 MUST NOT 要求读取该 key 的明文或投影（区别于 `ck.presence.visibility` 的最小 policy projection，§3.4），也不得把它纳入任何 policy projection 面；presence 隐私 gate 只以 `ck.presence.visibility` 为服务端可见输入。
- `clears_at` 的到期判定在发送侧完成；客户端 SHOULD 在到期后的下一次广播周期内恢复自动状态，不要求毫秒级精确。客户端 SHOULD 在设置临时状态时提供常见过期档位（如 30 分钟 / 1 小时 / 今天）。
- 手动 `dnd` 只改变 presence 展示语义，MUST NOT 被服务端隐式解释为通知抑制；通知抑制由 `ck.push_rules` / `ck.dnd_schedule`（[client-preferences.md §3.2](./client-preferences.md)）独立控制。客户端 SHOULD 在用户手动切换 `dnd` 时提供联动写入通知抑制的选项（informative UX 建议）。
- 该 key 属于用户自身偏好，接收方无从（也无需）区分手动与自动状态；因此它不引入新的可见性面，§3.4 的全部隐私 gate 原样适用。

## 4. 用户目录 (User Directory)

### 4.1 搜索接口

Directory Service 或客户端本地联系人索引 MAY 提供用户搜索功能，用于 `@mention` 自动完成和联系人发现。

> **Normative 源（normative）**：`search-users` 的 request / response 字段、授权过滤、分页字段（`has_more` / `next_cursor`）以 [`discovery-directory.md` §9](./discovery-directory.md) `ck.find.directory.query.search_users` 为**唯一规范源**；本节只补充 presence / mention 特有的 UI 语义（例如 autocomplete intent、普通 mention 不得请求投递上下文、以及 `results[].membership` 仅作本地展示 hint）。字段名、必填性或分页语义与 directory §9 冲突时，MUST 以 directory §9 为准。

```
POST /_cokret/find/directory/search-users

{ "query": "alice", "realm_id": "ck:realm:...", "limit": 10 }
```

Presence / mention 语义补充：

- mention autocomplete SHOULD 在 body 中携带 `realm_id` 与 `intent="mention"`，使 Directory 能按共同 Realm / directory policy 裁剪结果。
- 普通 mention autocomplete MUST NOT 请求或依赖 `member_delivery_binding`；只有 contact request / invite / member-add 流程可按 directory §9 的 `intent ∈ {contact_request, invite, member_add}` 规则请求投递上下文。
- `results[].membership` 若返回，只是与 `realm_id` 相关的展示 hint，不得作为授权、加入资格或投递绑定依据。

响应示例（非完整 schema）：

```json
{
  "results": [
    {
      "handle": "alice:example.com",
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
- MUST NOT 跨域搜索未授权的外部用户
- `search-users` 是候选发现接口，不是身份解析接口；需要得到 `subject` DID 或 `member_delivery_binding` 时，客户端 MUST 调用 `resolve-handle` 并满足其 claim / audience / requester policy。

## 5. v1 规则

- 头像若公开可见，必须使用公开 blob 或公开缩略图；私有或 E2EE Realm 的头像/图标应使用 authenticated media 或加密 blob，服务端不得因头像请求泄露 Realm 存在性。对隐藏（`unlisted` / `invite_only` / `secret` 等不可发现）Realm 的头像 / 图标请求，其失败 MUST 与"资源不存在"**不可区分（含响应形态与时延等同）**，口径对齐 [`../security/server-threat-model.md` §4.4](../security/server-threat-model.md) 的目录防枚举与统一错误形态、[`discovery-directory.md` §3](./discovery-directory.md) 的 `not_found` blinding；不得因头像请求走 authenticated media 完整校验失败与早退不存在产生可观测时序差，从而把媒体请求变成 Realm 存在性枚举侧信道（与 server-threat-model §2 #22 媒体侧信道探测同口径）。
- Profile 字段 MUST 受 schema 验证。组织可通过 Organization policy 限定 `profile_fields` 的字段名、类型、最大长度、敏感性和披露范围。
- profile 内 `handle`（§2.2）经 Directory / projection 披露时 MUST 同受 handle 披露 gate 约束——只能披露公开或调用方已获授权的 handle，不得借 profile 投影旁路 handle 搜索（§4.1 与 `discovery-directory.md` §5）的披露限制。
- Presence 跨域联邦默认 opt-in，必须短 TTL、最小字段、按关系或 Realm policy 授权；不得用 presence 推断 pairwise DID、私有组织成员资格或隐藏 Realm 拓扑。
- 群组 Profile 是 Realm metadata 的投影；Realm 名称、图标、描述、公告和可发现性必须受 Realm policy、history visibility 和 directory filtering 控制。
