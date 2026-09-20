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

每个 Actor `did_core_id` MAY 关联一个标准化的 `actor_profile` 对象，作为其公开身份信息。Profile 数据由 Actor 签名 Event 发布，并通过 Identity 解析或授权 Directory 被其他节点发现。对象字段以 [`../../artifacts/schemas/actor-profile.schema.json`](../../artifacts/schemas/actor-profile.schema.json) 为准；权限仍以 `principal_id` 指向的稳定主体及其DID 控制证明 / capability 为准。

```json fragment
{
  "id": "ak:actor_profile:AdP2S6y0Ms7yp9-GNvXZ3sVfvTEo8mtnV3G_RfApIOn0",
  "schema": "ak.schema.actor_profile.v1",
  "realm_id": "ak:realm:ARmJMvTcKFyiF-V_8oL4mIoHfnlqERCrcgNBONtY4HQD",
  "principal_id": "ak:did_core:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR",
  "actor_kind": "user",
  "display_name": "Alice Chen",
  "handle": "alice",
  "avatar_blob_ref": "ak:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "profile_fields": {
    "status_message": "On vacation until May 5",
    "pronouns": "she/her",
    "timezone": "Asia/Shanghai",
    "locale": "zh-CN",
    "title": "Senior Engineer",
    "organization": "Acme Corp"
  },
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "updated_at": "2026-04-26T00:01:00Z"
}
```
字段顺序与 §2.2 表 / canonical schema property ordering 一致（…`schema`、`realm_id`、`principal_id`、`actor_kind`、`display_name`、`handle`、`agent_slug`、`avatar_blob_ref`、`accountable_principal_ids`、`profile_fields`、`created_at`、`updated_by`、`updated_at`）；`realm_id`、`updated_by` / `updated_at` 为可选字段，初始 `ak.profile.create` 后尚未发生更新时 MAY 省略。

### 2.2 标准 Profile 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | id:actor_profile | MUST | Profile 对象 ID。 |
| `schema` | string | MUST | `ak.schema.actor_profile.v1`。 |
| `realm_id` | id:realm | 可选 | Profile state 所属的 principal control Realm 或 profile materialization scope。存在时 MUST 与承载该 profile create/update 的 principal control Realm 或授权 materialization scope 一致；不得被当作协作 Realm membership 或读取权限。 |
| `principal_id` | did_core_id | MUST | Actor / Principal 的稳定业务身份。 |
| `actor_kind` | enum | MUST | `user`、`organization`、`team`、`agent`、`bot`、`service` 或 `integration`；`agent` 只表示 Agent，Applet automation 使用 `bot`（不含 `device`：设备非 actor 主体，见 [`../models/actor.md` §2](../models/actor.md)）。 |
| `display_name` | string | MUST | 人类可读的显示名；按 `arkret_single_line_display_text` 验证，最大 128 个 Unicode code point，与 Contact `confirmed_display_name` 共用 `display_text_128` 机读 profile。 |
| `handle` | string | 可选 | 本地或目录展示 handle。经 Directory / projection 披露时同受 §5 handle 披露 gate 约束（不得旁路 handle 搜索披露限制）。 |
| `agent_slug` | string | 可选 | Agent 的 controller-scoped selector label projection。必须由当前有效 `ak.schema.agent_selector_claim.v1` 支撑，仅用于已获授权且已知完整 Agent AccountId 的 picker 展示/校验；不得与 controller handle 拼作自由文本寻址；不是全局 handle 或公开目录发现键。 |
| `avatar_blob_ref` | id:blob | 可选 | 头像图片的 Blob 引用。 |
| `accountable_principal_ids` | did[] | 可选 | agent / service / 托管账号的责任主体。 |
| `profile_fields` | object | 可选 | 个人简介的 canonical 落点是 `profile_fields.bio`；此外可承载代词、时区、locale、状态消息与组织自定义展示字段。`bio` 与 `status_message` 各 MUST ≤ 256 字符（Unicode code point 计），并受 §3.3 相同的 NFC / 控制字符约束。`avatar_url` 不是协议字段；头像必须先保存为 Blob，再写入顶层 `avatar_blob_ref`。 |
| `created_at` | timestamp | MUST | 创建时间。 |
| `updated_by` | ActorId | 可选 | 最近更新者；由 profile update Event actor 派生。 |
| `updated_at` | timestamp | 可选 | 最近更新时间。 |

**`status` 不是 durable profile 成员（normative）**：它曾是本表的一行，投影
[`../identity/account-lifecycle.md` §3](../identity/account-lifecycle.md) 的 `AccountStatusRecord`
状态集，而该文明令 `AccountStatusRecord` 不进入任何 authority stream、RealmCommit、Control Proposal 或
**reducer**；于是这个成员按构造无人可写：没有任何 `result_writes[]` 能产出它，作者也不得自报
（它由 Account Authority 签发，可在本 Event 之外改变，接纳前没有任何等式能判作者自报的值）。
它已移出 durable 对象，改为读取响应
`actor-profile-operations.schema.json#/$defs/resolved_actor_profile` 的可选成员 `account_status`。
服务端 MUST 先验证其 exact `account_id`、record 自身的 proof 与 `status_seq` 相对本地单调 replica head
的有效性，再投影；没有已验证 record 时 MUST 整个省略该成员。**省略表示未知**：调用方 MUST NOT 把缺失
读成 `active`，也 MUST NOT 跨 profile revision 缓存该状态——它按 Account Authority 的时钟变，
不按 profile 的。

### 2.3 Profile 创建与更新

Profile 初始状态通过 `ak.profile.create` Event / compatible Event 提交到 actor 的 principal control Realm。物化 Profile ID 是把该 create Event 的 `event_id` 原 token 换成 `ak:actor_profile:` 前缀后的值；`payload.object.id` MUST 省略。Event 以该 Event-derived ID 为 profile typed current result subject。`payload.object.principal_id` MUST 等于提交者 `actor_id`，或等于由 capability / controller policy 明确授权的目标 principal。

`payload.object` 是 `actor-profile.schema.json#/$defs/actor_profile_definition`——**作者区域**，不是物化对象：`schema`、`realm_id`、`created_at`、`updated_by`、`updated_at` 由 reducer 按 [`../models/common-fields.md` §3.3](../models/common-fields.md) 的 `object_schema_identifier` / `object_realm_binding` / `object_create_time` / `object_update_actor` / `object_update_time` 产出，作者 MUST NOT 携带；`id` 与 `resolution` 同样不在作者区域。`principal_id` 与 `actor_kind` 仍是作者输入（没有任何派生能产出「这份 profile 属于哪个 principal」），但二者 **create-locked**：`ak.profile.update` 与 `ak.profile.realm_override` 的 patch 面以 `propertyNames` 拒绝它们，换主体或换种类 MUST 新建对象，不得借 update 原地重绑；`agent_slug` 与 `actor_kind` 的既有跨字段约束不变：

```json fragment
{
  "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
  "kind": "ak.profile.create",
  "realm_id": "ak:realm:ARmJMvTcKFyiF-V_8oL4mIoHfnlqERCrcgNBONtY4HQD",
  "actor_id": "ak:did_core:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR",
  "created_at": "2026-04-26T00:00:00Z",
  "payload": {
    "object": {
      "principal_id": "ak:did_core:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR",
      "actor_kind": "user",
      "display_name": "Alice Chen",
      "avatar_blob_ref": "ak:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "profile_fields": {
        "timezone": "Asia/Shanghai",
        "locale": "zh-CN"
      }
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "verification_method": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com#key-1",
      "event_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "eyJhbGciOiJFZDI1NTE5In0..c2ln",
      "signer_resolution_evidence_ref": "ak:signer_evidence:sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    }
  ]
}
```
Profile 后续变更通过 `ak.profile.update` Event / compatible Event 提交。该 payload 使用 `actor_profile_update_payload`；Event 使用 `payload.target_ref` 与 `ak.profile.create` 共用同一 profile typed current result。变更字段放在 `payload.patch`，不得使用顶层 `actor` / `body` 形态：

```json fragment
{
  "event_id": "ak:event:AWxu9WEa6ZSBa79XtJFqrj3WsshthqPPUDPk-cMq5gZM",
  "kind": "ak.profile.update",
  "realm_id": "ak:realm:ARmJMvTcKFyiF-V_8oL4mIoHfnlqERCrcgNBONtY4HQD",
  "actor_id": "ak:did_core:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR",
  "created_at": "2026-04-26T00:01:00Z",
  "semantic_refs": [
    {
      "id": "ak:grant:AT-1QUIBViI1bcGaLssADWkxqZ9bCtHDhnKqduYlKaQz",
      "role": "authorized_by",
      "critical": true
    }
  ],
  "payload": {
    "target_ref": "ak:actor_profile:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
    "patch": {
      "display_name": "Alice C.",
      "profile_fields.status_message": "Back at work!"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "verification_method": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com#key-1",
      "event_digest": "sha256:6b5ad6b5ad6b7ad6b5ad6b5ad6b5ad6b6b5ad6b5ad6b7ad6b5ad6b5ad6b5ad6b",
      "created_at": "2026-04-26T00:01:00Z",
      "jws": "eyJhbGciOiJFZDI1NTE5In0..c2ln",
      "signer_resolution_evidence_ref": "ak:signer_evidence:sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    }
  ]
}
```
- `ak.profile.create` 初始化完整对象；`ak.profile.update` 仅携带发生变化的字段（delta 更新）
- 其他参与者的客户端 MUST 通过授权面 `ak.self.actor_profile.read.resolve.v1` 获取该 actor 的最新全局 Profile：它以共享 Collaboration Realm 的 current effective joined membership 为授权基础，逐条返回 exact signed profile Event、接纳该 Event 的 exact RealmCommit 与该 Event 所支撑的当前显示投影。服务端 MUST 验证 Event／Commit／PCR stream／authority generation 的逐字绑定，缺少覆盖 Commit 时返回 `profile_unavailable`，不得把本地缓存或 account aggregate 冒充 accepted profile。全局 profile Event 落在其 owner 的 Principal Control Realm，因此 **MUST NOT** 通过对该 actor 做 actor-scoped `ak.self.committed_event.read.scan.v1` / `.stream.subscribe` 获取（见 [`../sync/service-http-binding.md` §3.3.1.1](../sync/service-http-binding.md)）；未知 actor、无 accepted profile、非成员 actor、缺失 committed provenance 与无权调用者一律 `profile_unavailable`，不可用于探测成员关系或账号存在性
- 客户端 MAY 缓存 Profile 并在本地查询响应中内联展示，但 MUST 自行验证返回的 exact signed Event、covering RealmCommit 及其与该 actor 和其 Principal Control Realm stream 的绑定，不得把裸 `actor_profile` 当作证据；一条 patch Event 与其 Commit 不证明完整投影、无并发或全网新鲜，证明边界见 [`../sync/service-http-binding.md` §5.1](../sync/service-http-binding.md)

`ak.profile.create` 与 `ak.profile.update` 是 principal-scoped profile state。顶层 `realm_id` MUST 是该 actor 的 `principal_control_realm_id`；不得把全局 profile 更新写入任意 Collaboration Realm history（Principal Control Realm 与 Collaboration Realm 的分类见 [`models/realm-and-space.md` §2.8](../models/realm-and-space.md)）。两 kind 共写入同一 typed current result，登记名为 **`actor_profile`**（`current-value projection`；当前值是该 stream 上最后一个被接受的写入，次序由 `stream_position` 给出），`result_selector` 由 schema registry 派生：create 把 `envelope.event_id` retype 为 `ak:actor_profile:*`，update 使用必须逐字等于该派生 ID 的 `payload.target_ref`。本段曾把它写成 `profile_create:<target_actor_profile_id>`——那是一个 create-only 的拼法，而 update 写的是同一个值；登记名只有一个，不登记别名、也不另造 create-only family。

### 2.4 Per-Realm Profile 覆写

用户 MAY 为特定 Realm 设置不同的显示名或头像（例如在公司 Realm 用真名，在开源项目 Realm 用昵称）：

`ak.profile.realm_override` 是 Realm-scoped profile override 事件 kind，目标 Realm 由 `payload.target_realm_id` 唯一指定，不指向 `ak:space:` 容器，也不创建 Space 级访问边界。

该 Event 写 `actor_profile_realm_override` typed current result：目标 Realm 是结果作用域，selector 只取
`payload.target_ref`；value 是 canonical Event dot 标记的完整 override payload assertion set。读取方按
accepted commit 顺序折叠 patch，所得当前值仅含 `display_name`、`handle`、`agent_slug`、`avatar_blob_ref`、
`accountable_principal_ids`、`profile_fields` 六条展示路径。集合从空集开始，首条 patch 不依赖隐式空对象；
`expected_state_digest`（若存在）绑定折叠后的前态，失配必须零写入拒绝。

```json fragment
{
  "event_id": "ak:event:AcWdky_9bM7PKl17K1UxMcj72H3_Ny9PoMhexJ2S-sK0",
  "kind": "ak.profile.realm_override",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "actor_id": "ak:did_core:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR",
  "created_at": "2026-04-26T00:02:00Z",
  "semantic_refs": [
    {
      "id": "ak:grant:AT-1QUIBViI1bcGaLssADWkxqZ9bCtHDhnKqduYlKaQz",
      "role": "authorized_by",
      "critical": true
    }
  ],
  "payload": {
    "target_ref": "ak:actor_profile:AdP2S6y0Ms7yp9-GNvXZ3sVfvTEo8mtnV3G_RfApIOn0",
    "target_realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
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
      "verification_method": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com#key-1",
      "event_digest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "created_at": "2026-04-26T00:02:00Z",
      "jws": "eyJhbGciOiJFZDI1NTE5In0..c2ln",
      "signer_resolution_evidence_ref": "ak:signer_evidence:sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    }
  ]
}
```
- Realm 覆写的优先级高于全局 Profile
- `null` 值表示使用全局 Profile 的对应字段
- `ak.profile.realm_override` MUST 同时绑定 actor DID 与目标 Realm。若作为共享 Realm history 传播，顶层 `realm_id` 是目标 Realm，事件必须通过目标 Realm 的 membership / visibility / policy 校验；若作为 actor-private 或 principal control profile state 传播，content MUST 显式包含目标 Realm id，projection 服务只可向有权读取该 Realm profile override 的请求方披露。
  - _Informative._ `ak.profile.realm_override` 是显示层 per-Realm 覆写，绑定同一 `principal_id`,**不提供跨 Realm 不可关联性(unlinkability)**:能同时读取同一 principal 在多个 Realm override 的请求方可关联这些化名。需要跨 Realm 不可关联的化名时，应使用 Realm-scoped pairwise DID(见 [`../overview/glossary.md`](../overview/glossary.md) 的 pairwise DID 词条),而非依赖 realm_override。

## 3. 在线状态 (Presence)

### 3.1 Presence 是 Signal 状态

在线状态属于高频变动的临时数据，MUST NOT 作为 durable Event 写入 history。它只通过 encrypted-only Signal Extension 发送。

### 3.2 Presence 状态值

| 状态 | 含义 |
|------|------|
| `online` | 用户当前活跃在线 |
| `idle` | 用户在线但一段时间无操作 |
| `offline` | 用户离线 |
| `dnd` | 勿扰模式（在线但不希望被打扰） |

`state` 是 v1 闭集：仅上表四值合法。接收方遇到未知 `state` 值 MUST 丢弃该 presence update 或按 `schema_violation` fail closed，MUST NOT 猜测映射为近似状态（历史实现遗留的 `unavailable`、`busy` 等值不是 v1 wire 值）。

- _Informative._ "忙碌 / 会议中 / 请勿打扰"一类用户主动设置的繁忙态统一映射为 `dnd`，更细的语义（例如"开会中"、"烦躁"）通过 `status_message`（§3.3）表达；v1 不为具体情绪 / 场景扩充 `state` 枚举。"隐身"（自己在线但对他人显示离线）也不是 `state` 值，通过 `ak.presence.visibility="nobody"`（§3.4）实现，从而把状态语义与可见性策略分离。
- `state` 可以由客户端自动判定（前台活跃 → `online`、无操作超时 → `idle`），也可以由用户通过手动状态偏好固定（§3.6）；两者的仲裁规则见 §3.6。

### 3.3 Presence plaintext 与聚合

Presence 使用 [`SignalEnvelope`](../sync/signal.md)，外层 `signal_class=session`。解密后的
plaintext MUST 通过闭合 schema `ak.schema.signal_presence.v1`
（[`signal-presence.schema.json`](../../artifacts/schemas/signal-presence.schema.json)，
`additionalProperties: false`）：required 字段为 `kind="ak.presence"`、`payload_sequence`、
`actor_id`、`state` 与 `ttl_ms`，可选字段只有 `status_message` 和 `last_active_at`。
`kind` 与 `payload_sequence` 按 [`../sync/signal.md` §1.1](../sync/signal.md) 的 plaintext
通用最小集必填。精确 kind、actor、状态与活动时间不得出现在外层。

`status_message` MUST 不超过 256 Unicode code points，NFC 规范化，且不得含除 U+0009 /
U+000A 外的 C0/C1 control。`last_active_at` 默认省略；policy 允许时只能使用 RFC 3339 UTC
timestamp 或对齐 Unix epoch UTC、duration 不小于 PT60S 的 ISO 8601 interval bucket。接收方
独立验证 bucket 边界、fixed-duration 与 policy 粒度，畸形值 fail closed。

同一 actor 的 verified endpoint presence 由接收端确定性聚合：ordinary 可有多个设备；Agent
只接受唯一 current runtime key。已知 runtime replacement 后旧 key 的记录立即退出聚合，不等待 TTL：

1. 只考虑外层与 plaintext TTL 都未过期且 sequence 未回退的信号；
2. `state` 优先级为 `dnd > online > idle`，没有有效信号即 `offline`；
3. `status_message` 取 `sent_at` 最新的非空值；
4. `last_active_at` 取通过校验后的最新值。

Station sync surface 不得解密、聚合或投影 presence 内容。

**持续在线刷新（normative）。** 声明自己当前可达并选择广播 presence 的发送端（包括前台客户端、后台常驻客户端与 Agent runtime）MUST 在上一条 `ak.presence` 的 effective expiry 之前发送同一 scope 的后继信号；每个后继信号 MUST 使用 [`signal.md` §2](../sync/signal.md) 对相应 verified endpoint 规定的严格递增 `payload_sequence`、新的 Signal nonce，并重新绑定发送时的 accepted `commit_ref` / MLS epoch。对 v1 `session` class 的 30 秒上限，实现 SHOULD 使用 20–25 秒的刷新周期，并 MUST 为调度、网络抖动与 session refresh 预留至少 5 秒余量；不得把进程健康检查、WebSocket / account stream keepalive 或最后一次 durable Message 当作 presence 刷新。运行时一旦不能取得当前授权、accepted RealmCommit、可持久化的 MLS Signal nonce state，或不能在 expiry 前完成加密提交，MUST 停止宣称 online；接收端继续按上面的 TTL 规则自然聚合为 `offline`，不得延长旧信号。

刷新生命周期 MUST 与该 runtime 的可达生命周期一致：启动并完成 session、scope 与 MLS readiness 后 SHOULD 立即首发；正常运行期间按上述周期刷新；pause / deactivate / unbind、授权或 session 无法恢复、网络断开且不能提交、进程关闭时停止刷新。发送端 MAY 在可用且不会拖延关闭时发送显式 `state="offline"`，但接收端不得依赖该 best-effort 信号，TTL expiry 始终是权威离线边界。对同时接入 durable Event 流的 Agent，presence 发送失败不得阻塞或伪造 Message 接收/回复成功；两条链路必须分别暴露可诊断状态。

### 3.4 隐私控制

用户可以控制 Presence 的可见范围：

该策略的标准存储位置是 actor-private Account Data key `ak.presence.visibility`（见 [`account-data-key-registry.json`](../../artifacts/registry/account-data-key-registry.json)）。写入通过 `ak.account_data.set` 完成；解密后的 payload MUST 通过闭合的 [`presence-visibility.schema.json`](../../artifacts/schemas/presence-visibility.schema.json)，缺省等价于 `{ "presence_visibility": "public" }`。

```json schema=schemas/presence-visibility.schema.json
{
  "presence_visibility": "contacts_only"
}
```

| 值 | 含义 |
|----|------|
| `public` | 所有共同 Realm 的成员可见 |
| `contacts_only` | 仅对明确的联系人可见 |
| `nobody` | 完全隐藏在线状态（对所有人显示为 offline） |

`ak.presence.visibility` 是发送侧的 principal-private policy，不得成为 Station sync surface 的明文
projection。Signal 使用 scope group key，因此发送方只能向整个 signed scope 加密：

- `public` 表示目标 scope 的全部 active members；
- `contacts_only` 仅当发送方已验证该 scope 的全部 active members 都属于 accepted-contact
  fact log 时才可发送；否则必须对该 scope 抑制 presence，不能把联系人集合泄露给服务端做筛选；
- `nobody` 时客户端不得发送 presence。

接收方必须验证外层 sender device proof，并要求 plaintext `actor_id == sender_actor_id`。
relay attestation 不能替代 sender proof。`dnd` / `idle` 等细分只在成功解密后可见；不存在
服务端降级或重写状态的 plaintext 路径。

`dnd` / `idle` 会泄露"用户在线但勿扰 / 空闲"，可被用于推断作息，属与 `last_active_at` 同类的活动侧信道。对不在 presence 可见集合内（不满足 `presence_visibility` 授权）的观察者，`dnd` / `idle` MUST 降级为 `offline` 或与 `online` 不可区分，不得向其暴露细分的勿扰 / 空闲状态；该降级与 `presence_visibility="nobody"` 的 MUST 隐藏同强度，避免 dnd/idle 成为绕过授权的活动侧信道。满足 `presence_visibility` 授权的观察者（授权集内）MAY 保留 `dnd` / `idle` 细分。

### 3.5 Typing 指示器

Typing 使用 [`SignalEnvelope`](../sync/signal.md)，外层 `signal_class=session`。解密后的
plaintext MUST 通过闭合 schema `ak.schema.signal_typing.v1`
（[`signal-typing.schema.json`](../../artifacts/schemas/signal-typing.schema.json)，
`additionalProperties: false`）：required 字段为 `kind="ak.typing"`、`payload_sequence`、
`strand_id` 与 `typing`，可选字段只有 `ttl_ms`。全部字段位于 ciphertext
plaintext 内；不得把目标 Strand 或精确 kind 暴露给 Station sync surface。

- `ak.schema.signal_typing.v1` identity 固定 discussion family，plaintext 不携 `track_name`；
- plaintext TTL 不得放宽外层 Signal TTL，客户端到期后自动清除指示；
- 客户端 SHOULD 每 3 秒至多发送一次，并在停止输入后发送 `typing=false`；
- 接收方 MUST 在验证 Signal proof、scope、RealmCommit/MLS basis、AAD 并解密后，才应用单调
  `payload_sequence`；
- fanout 只能面向目标 effective scope 的 active members，world-readable 历史不赋予外部观察者
  接收 typing 的资格；
- personal blocklist、membership 与 target track 可见性在端侧解密后继续 fail closed。无法对目标
  成员集合安全加密时不得发送，不能降级为服务端可读的明文筛选。

### 3.6 手动状态偏好 (Manual Presence Preference)

自动状态判定（前台活跃 → `online`、无操作超时 → `idle`、断连 / TTL 过期 → `offline`）覆盖大多数场景，但用户还需要能把自己的状态主动固定为某个值（例如切到 `dnd` 开会），且该选择要跨设备、跨重连生效。presence 广播本身是 Signal（§3.1），不承担持久化；手动偏好的标准存储位置是 actor-private Account Data key `ak.presence.preference`（见 [`account-data-key-registry.json`](../../artifacts/registry/account-data-key-registry.json)），通过 `ak.account_data.set` 写入。解密后的 payload MUST 通过闭合的 [`presence-preference.schema.json`](../../artifacts/schemas/presence-preference.schema.json)：

```json schema=schemas/presence-preference.schema.json
{
  "manual_state": "dnd",
  "status_message": "开会中，稍后回复",
  "clears_at": "2026-07-03T12:00:00.000Z"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `manual_state` | enum | 可选 | `online`、`idle` 或 `dnd`（§3.2 闭集去掉 `offline`）。缺省表示恢复自动判定。"隐身"不是 `manual_state` 值，MUST 通过 `ak.presence.visibility="nobody"`（§3.4）实现；`offline` 由停止广播 / TTL 过期自然表达，不作为可固定值。 |
| `status_message` | string | 可选 | 临时状态消息覆盖值，作为该 principal 各设备广播 `ak.presence` 时 payload `status_message` 的来源；长度与规范化约束同 §3.3（≤256 字符、NFC、控制字符限制）。 |
| `clears_at` | timestamp | 可选 | 过期时间（canonical RFC 3339 UTC，固定三位毫秒）。到期后整份偏好等价于缺省：客户端 MUST 恢复自动状态判定并停止广播其中的临时 `status_message`。缺省表示手动偏好持续生效，直到被显式改写或清除。 |

规则（normative）：

- 存在未过期 `manual_state` 时，该 principal 的**所有**设备广播 `ak.presence` 的 `state` MUST 等于 `manual_state`；本地自动 idle 检测 MUST NOT 覆盖它。设备离线仍由广播缺失 / TTL 过期自然表现为 `offline`（§3.3 多设备聚合）。
- `ak.presence.preference` 是**发送侧执行**的端侧偏好：执行主体是该 principal 自己的客户端。服务端 MUST NOT 要求读取该 key 的明文或投影；`ak.presence.visibility` 同样是发送侧私有输入，不进入任何服务端 policy projection。presence 隐私 gate 由发送客户端按 §3.4 执行。
- `clears_at` 的到期判定在发送侧完成；客户端 SHOULD 在到期后的下一次广播周期内恢复自动状态，不要求毫秒级精确。客户端 SHOULD 在设置临时状态时提供常见过期档位（如 30 分钟 / 1 小时 / 今天）。
- 手动 `dnd` 只改变 presence 展示语义，MUST NOT 被服务端隐式解释为通知抑制；通知抑制由 `ak.push_rules` / `ak.dnd_schedule`（[client-preferences.md §3.2](./client-preferences.md)）独立控制。客户端 SHOULD 在用户手动切换 `dnd` 时提供联动写入通知抑制的选项（informative UX 建议）。
- 该 key 属于用户自身偏好，接收方无从（也无需）区分手动与自动状态；因此它不引入新的可见性面，§3.4 的全部隐私 gate 原样适用。

## 4. 用户目录 (User Directory)

### 4.1 搜索接口

Directory Service 或客户端本地联系人索引 MAY 提供用户搜索功能，用于 `@mention` 自动完成和联系人发现。


```

{ "query": "alice", "realm_id": "ak:realm:...", "limit": 10 }
```

Presence / mention 语义补充：

- mention autocomplete SHOULD 在 body 中携带 `realm_id` 与 `intent="mention"`，使 Directory 能按共同 Realm / directory policy 裁剪结果。
- 普通 mention autocomplete MUST NOT 请求或依赖完整账号身份；只有 contact request / invite / member-add 流程可按 directory §9 的 disclosure 规则请求 exact AccountId。
- `results[].membership` 若返回，只是与 `realm_id` 相关的展示 hint，不得作为授权、加入资格或投递绑定依据。

响应示例（非完整 schema）：

```json fragment
{
  "users": [
    {
      "handle": "alice:example.com",
      "display_name": "Alice Chen",
      "avatar_blob_ref": "ak:blob:sha256:a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
      "membership": "joined"
    }
  ],
  "has_more": false
}
```
数组字段名是 `users`，不是 `results`（[`api-conventions.md` §7.1](../sync/api-conventions.md) 禁止 `results[]`）；
每条 user 的字段集以
[`directory-operations.schema.json#/$defs/user_search_outcome`](../../artifacts/schemas/directory-operations.schema.json)
为准。`next_cursor` 是 optional，缺省即表示已到末尾，MUST NOT 写成 `null`。

### 4.2 搜索范围

- 默认搜索当前 Realm 的成员
- 可选扩展到同一组织域下的所有已知用户
- MUST NOT 跨域搜索未授权的外部用户
- `search-users` 是候选发现接口，不是身份解析接口；需要得到 exact AccountId 时，客户端 MUST 调用 `resolve-handle` 并满足其 claim / audience / requester policy。

## 5. v1 规则

- 头像若公开可见，必须使用公开 blob 或公开缩略图；私有或 E2EE Realm 的头像/图标应使用 authenticated media 或加密 blob，服务端不得因头像请求泄露 Realm 存在性。对隐藏（`unlisted` / `invite_only` / `secret` 等不可发现）Realm 的头像 / 图标请求，其失败 MUST 与"资源不存在"**不可区分（含响应形态与时延等同）**，口径对齐 [`../security/server-threat-model.md` §4.4](../security/server-threat-model.md) 的目录防枚举与统一错误形态、[`discovery-directory.md` §3](./discovery-directory.md) 的 `not_found` blinding；不得因头像请求走 authenticated media 完整校验失败与早退不存在产生可观测时序差，从而把媒体请求变成 Realm 存在性枚举侧信道（与 server-threat-model §2 #22 媒体侧信道探测同口径）。
- Profile 字段 MUST 受 schema 验证。组织可通过 Organization policy 限定 `profile_fields` 的字段名、类型、最大长度、敏感性和披露范围。
- profile 内 `handle`（§2.2）经 Directory / projection 披露时 MUST 同受 handle 披露 gate 约束——只能披露公开或调用方已获授权的 handle，不得借 profile 投影旁路 handle 搜索（§4.1 与 `discovery-directory.md` §5）的披露限制。
- Presence 跨域联邦默认 opt-in，必须短 TTL、最小字段、按关系或 Realm policy 授权；不得用 presence 推断 pairwise DID、私有组织成员资格或隐藏 Realm 拓扑。
- 群组 Profile 是 Realm metadata 的投影；Realm 名称、图标、描述、公告和可发现性必须受 Realm policy、history visibility 和 directory filtering 控制。
