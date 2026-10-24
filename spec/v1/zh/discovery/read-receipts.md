---
title: "Read Receipts & Markers"
status: candidate
normative: true
stability: v1
updated: 2026-10-19
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

在即时通讯与协作中，“已读”状态是消除信息不对称的关键。Arkret 协议将“已读”分为两种机制：

1. **Read Receipt (已读回执)**：公开或共享的，让**其他人**知道某 actor 已读至哪条消息。
2. **Read Cursor (已读游标)**：私有的，用于 actor **多端设备**之间同步阅读进度。

本规范定义了这两种机制的触发与同步方式。

### 1.1 状态对象对照

| 对象 / Event | Wire scope | 持久性 | 谁可见 | 推送 / 审计关系 |
| --- | --- | --- | --- | --- |
| Signal 密文内的 `ak.receipt.read` / `ak.schema.read_receipt.v1` | Signal Extension | 短 TTL，不进入 durable Event history | 仅能解密目标 scope 的成员 | Push Gateway MUST NOT 因 receipt 本身发通知；只能用于 unread / suppression 派生 |
| `ak.read_cursor.advance` / `ak.schema.read_cursor.v1` | actor-private account / durable sync object | 持久保存最新阅读位置，多端同步 | 仅该 actor 的设备和授权 account aggregate 服务 | 作为 unread count、badge 与 push suppression 输入 |
| `ak.notification` / `ak.schema.notification.v1` | derived projection / account aggregate | 派生状态，可重建 | 目标 actor 及其设备 | 不是协议真相源；必须绑定 read cursor checkpoint、notification rule checkpoint 与 source event checkpoint |
| `ak.audit.accessed`（schema 见 audit profile，本表不另列 `ak.schema.*`） | durable Event（审计 profile 下） | 按 audit retention 保留 | 由 Realm audit policy / capability 控制 | 记录受控读取、watch manage_others、late recovery 等访问证明；不得替代 read receipt |

## 2. Read Receipt (已读回执)

已读回执是向同一个 Strand `discussion` track 的可见成员广播“我已经看到这条消息了”。

### 2.1 实时性与加密边界

已读回执高频且没有长期保留价值，因此 MUST 作为
[`SignalEnvelope`](../sync/signal.md) 的加密 plaintext 发送，不写入 Event 因果图。
外层 `signal_class` 固定为 `session`；`ak.receipt.read`、read target、Event id、HLC 与 actor
都必须位于 `encrypted_payload` 中，Station sync surface 不得看见或按这些字段路由。

plaintext 解密后使用闭合对象 `ak.schema.read_receipt.v1`
（[`read-receipt.schema.json`](../../artifacts/schemas/read-receipt.schema.json)，
`additionalProperties: false`）：required 字段为 `kind="ak.receipt.read"`、单调
`payload_sequence`、`actor_id`、`read_scope` 与已读至的 `event_id`，唯一可选字段是 `hlc`。
`kind` 与 `payload_sequence` 按 [`../sync/signal.md` §1.1](../sync/signal.md) 的 plaintext
通用最小集必填；Realm scope、发送者与发送时间由外层已签名 envelope 承载，plaintext MUST NOT
重复 `realm_id` / `created_at`。外层 `sender_actor_id` MUST 等于 plaintext `actor_id`。

接收方只有在验证 Signal proof、RealmCommit basis、MLS epoch/AAD、TTL 并成功解密后，才能更新
UI。relay attestation 不能替代 sender device proof。任何把 receipt target 或精确 kind 放到
外层的旧明文 envelope MUST 以 `schema_violation` 或
`signal_plaintext_forbidden` 拒绝。

### 2.2 计数与呈现

Read receipt 的展示只回答"谁读到哪里"；未读计数是另一条派生链（§4），二者 MUST NOT 互相推导。

### 2.3 防雪崩与合并

Read Receipt 是高频信号。发送方客户端 MUST 支持语义合并：客户端 SHOULD debounce 可见区域滚动产生的更新，并且对同一 `(realm_id, read_scope, actor)` 在短窗口内只发送最新位置。默认建议窗口为 1 秒，交互结束、窗口失焦或显式“标为已读”时 SHOULD flush 最新位置。

Station sync surface 看不到加密 plaintext 中的 `read_scope` / position，因此 MUST NOT 声称按 read_scope 判断新旧或做语义合并。它 MAY 仅按外层可见的 `(sender_actor_id, sender_device_id, scope_ref)` 做短窗口批处理与粗粒度限流，但不得据此丢弃某一条并声称“只保留最新”；批内顺序与最终单调合并由接收客户端解密后完成。服务端限流维度只可使用这些外层字段，Strand 维度限流由持有明文的客户端执行。超过频率时 SHOULD 返回或广播 `rate_limited` / `retry_after_ms` 语义，客户端 MUST 按退避合并后重试。

Push Gateway MUST NOT 因 read receipt 产生通知。它只能把 receipt / marker 作为 unread count、push suppression 和 badge recompute 的输入。

### 2.4 隐私控制

用户可以随时关闭发送已读回执。此配置属于 Client Preference，按 (strand, realm, default) 顺序解析有效偏好；标准 Key 与字段定义见 [`discovery/client-preferences.md`](./client-preferences.md) §3.8。

- 该偏好同步在用户的加密 account data 中，不公开广播。
- `send=false` 只影响"是否发送 `ak.receipt.read`"，不影响 §3 私有 Read Cursor。用户若只想隐藏他人的已读头像，客户端应使用 `ak.read_receipt.preferences.display=false` 做本地渲染偏好；该偏好不得改变 Station sync surface 投递或协议状态。
- 客户端收到他人的 `ak.receipt.read` 时，SHOULD 在 UI 上更新已读头像的小图标位置；接收行为不依赖发送偏好。
- 当目标 scope 由 §2.5 声明 `disclosure="required"` 或 `disclosure="disabled"` 时，合规客户端 MUST 按该声明覆盖用户偏好（详见 §2.5）。

### 2.5 Scope 披露策略 (Disclosure Policy)

Realm-default scope 与每个 Circle scope MUST 使用同一套 read receipt policy 合同，各自独立配置、
独立存取与执行。消息所属的签名 `scope_ref` 决定唯一适用策略：Realm-default 消息只读该 Realm
scope 的策略，Circle 消息只读该 Circle 的策略。父 Realm、Realm link、`governed_by`、其它 Circle
及 source Realm 的策略 MUST NOT 参与继承、fallback、合并或“取更严格者”。Realm 的 `required`
或 `disabled` 都不锁定 Circle 的配置。Track 级策略与 Sidecar 策略不在本合同范围内。

整个 Strand 的 scope 由 `Strand.scope_circle_id` 与签名 `scope_ref` 绑定，见
[Circle](../models/circle.md) 和 [Strand §5](../models/strand-and-message.md)。
Scope 隔离是披露上限；policy 只能在该 scope 已有观察权限内约束阅读行为，不能授予成员资格、
正文访问权或跨 scope 观察权。

#### 2.5.1 唯一写者与当前状态

唯一写入 Event 为 `ak.scope.read_receipt_policy`。它的签名 envelope `scope_ref` MUST 是闭合的
Realm 或 Circle 分支（[read_receipt_policy_scope_ref](../../artifacts/schemas/event-envelope.schema.json#/$defs/read_receipt_policy_scope_ref)），
其中 `realm_id` MUST 等于 envelope `realm_id`；Circle MUST 属于该 Realm。Event 进入该 scope
自己的 authority commit stream，covering RealmCommit 的 `stream_ref` MUST 标识同一 scope。
准入 MUST 在同一事务 cut 检查目标 scope 的 `ak.policy.manage` 授权、scope/lifecycle 与有效成员资格；
Circle 范围的 grant 不能授权父 Realm 或兄弟 Circle，聚合 admin/owner 权限也不跳过 scope 校验。
拒绝时 MUST 零 accepted effects；成功时 Event、RealmCommit 与 current 替换 MUST 原子提交。

Payload 为 [read_receipt_policy_payload](../../artifacts/schemas/event-payload.schema.json#/$defs/read_receipt_policy_payload)
闭合非空对象，只包含 `disclosure`、`visibility`；两字段都可省略，但不可显式为 `null`。
Payload MUST NOT 重复 `scope_ref`、`realm_id` 或 `circle_id`。

```json fragment
{
  "kind": "ak.scope.read_receipt_policy",
  "scope_ref": {"kind": "circle", "realm_id": "<realm_id>", "circle_id": "<circle_id>"},
  "payload": {"disclosure": "optional", "visibility": "members"}
}
```

唯一 current family 为 `scope_read_receipt_policy`；closed selector 是
`{kind:"scope_read_receipt_policy",scope_ref:<exact signed scope_ref>}`。
Subject 是签名 `envelope.scope_ref` 的 canonical JSON 单组件；source stream 与 selector scope MUST
逐字段一致，revision 为接受该 Event 的同 scope RealmCommit `{commit_id,stream_position}`。
每次写入完整置换 payload，MUST NOT 把旧值的省略字段补回；默认值仅在读侧解释。
策略不属于 `ak.realm.policy_bundle`、Circle 对象或 `ak.circle.update` patch，不能产生第二份写者。
现行 v1 不再登记 `ak.realm.read_receipt_policy`、`realm_read_receipt_policy` 或
`scope_overrides_allowed`；它们 MUST NOT 被当作兼容写入、selector 或 fallback。

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `disclosure` | `enum(required, optional, disabled)` | `optional` | `required`：合规客户端 MUST 发送；`optional`：按 Client Preference；`disabled`：MUST NOT 生成，接收端 MUST 丢弃且不呈现。三者是本 scope 的选择，不构成跨 scope 严格度排序。 |
| `visibility` | `enum(public, members, private)` | `members` | `public`：本 scope 已有权限观察目标 Strand 的全部观察者；`members`：Realm-default scope 的有效 Realm 成员或该 Circle 的有效成员；`private`：仅目标消息的原作者，且仍须具备该 scope 的访问资格。任何值都不得把 Circle 回执披露到 Realm-default scope 或兄弟 Circle。 |

#### 2.5.2 同 cut 读取、缺席与更新

发送与呈现前，客户端 MUST 从已验证的 scope current 基线取得策略；基线须证明 exact Realm、scope、
治理 generation、覆盖的 stream head 与 revision。Strand scope、目标 Event/作者和调用者的有效成员／
观察资格 MUST 在同一授权读取 cut 重验。不同 stream 无隐含总序，不得拼接两个时刻的裸缓存。

- `present`：只消费 selector-identical、source-stream-identical 且 revision 被该基线覆盖的 current。
- 从未配置：只有已验证的完整 scope Snapshot/current 披露及其连续 replica tail 能证明该 selector
  在覆盖 cut 上从未写入时，才采用 `optional` / `members`。该缺席证明只对这个 scope 有效。
- 请求失败、不可见、未知 scope、不完整 Snapshot、未验证 tail 或页面缓存缺项不构成缺席证明；
  MUST fail closed：不发送、不呈现，不借用 Realm 或兄弟策略。不得臆造 exact-current 读取分支。
- 已有策略恢复默认仍由唯一写者显式写入默认值；空 `{}`、`null`、删除 current 或漏行不能表达重置。
- 策略或资格更新后，客户端 MUST 重新检查待发回执与已有展示；`disabled` 清除已有 hint，
  `members` / `private` 收窄或资格失效时撤下不再允许的头像。不得只过滤新回执，亦不得自动复活已丢弃信息。

#### 2.5.3 发送、呈现与隔离执行

- 策略是软声明／合规承诺，不是密码学审计证明；恶意客户端可不发送或检查自己能解密的 Signal。
  任何 actor/service/relay/peer MUST NOT 伪造他人回执或转发不可验证来源 proof 的回执。
- 客户端 MUST 在进入 scope/Strand 时明示该 scope 的 disclosure/visibility 与锁定开关。
  `required` 禁止 `send=false`，并 SHOULD 在每次进入 track 时按 §2.1 至少发送覆盖当前可见 head 的回执；
  debounce、合并与限流仍适用。`disabled` 覆盖用户 `send=true`，Read Cursor 不受影响。
- 回执 target Event、Strand/track、签名 Signal `scope_ref` 和 policy selector MUST 对应同一 scope。
  错 Realm、错 Circle、兄弟 scope 或只有父 Realm 成员资格的接收者 MUST NOT 获得 Circle 的回执展示。
- Station sync surface MUST 按签名 scope 与该 scope 的投递授权裁剪 fanout。它看不到加密的 kind/event_id，
  MUST NOT 通过新增明文产品 selector 识别回执或按消息作者定向路由。
- 接收端解密后检查 policy 与目标作者；`private` 只允许原消息作者看到，使用完整 ActorId（含 Station）
  比较，MUST NOT 比较 reader 本人或只比较 principal。缺 target/作者/当前授权证明时 MUST 丢弃且不呈现。
  Push Gateway MUST NOT 因回执本身产生通知。
- 此策略不改变 MLS key access，MUST NOT 推进 `key_access_revision`。`history_access` 只决定正文历史
  范围，不扩大回执观察者，不允许匿名或跨 scope 读取；metadata-private 场景 MUST 使用 `members` 或 `private`。

具名合同向量为 `ak.vector.read_receipt.scope_policy.schema.v1`、
`ak.vector.read_receipt.scope_policy.independent.v1`、
`ak.vector.read_receipt.scope_policy.isolation.v1` 与
`ak.vector.read_receipt.scope_policy.updates.v1`，正反向案例见
[scope policy fixture](../../artifacts/fixtures/read-receipt-scope-policy-fixture.json)。
这些规范向量不代表 Station、SDK consumer、客户端或实际联合链路已经完成产品验收。

## 3. Read Cursor (私有游标)

Read Cursor 用于同一 actor 多设备之间的进度同步（例如手机端已读后，桌面端不再显示未读红点）。它是 actor 的**私有状态**。

### 3.1 存储位置

Read Cursor 作为一种持久化的个人状态，MUST 作为加密 account data 或 actor-private Event 保存，而不是提交到发生协作的共享 Realm Event history。

### 3.2 格式

Read cursor schema：`ak.schema.read_cursor.v1`。Read Cursor 是 actor-private 持久状态，存放在加密 account data 或 actor-private stream 中。wire 对象**没有 typed ID 也没有 `updated_at`**：它不是可原地更新的对象，身份是 `(actor_id, realm_id, read_scope)` 三元组，更新时间是承载它的 `ak.read_cursor.advance` 信封 `created_at`（§6.1）。实现 MAY 为本地存储自选 key，该 key 不进入 wire。Read Cursor 按 §6.1 / §6.6 绑定 `(actor_id, realm_id, read_scope, position, hlc, device_id)`：

```json fragment
{
  "schema": "ak.schema.read_cursor.v1",
  "actor_id": "ak:did_core:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw",
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "read_scope": {
    "kind": "strand",
    "container_ref": "ak:strand:AaalePlTK6W4ZKrbKyKzlmmcdhXVx-InxeWY4ul69tiN",
    "track_name": "discussion"
  },
  "position": {
    "event_id": "ak:event:AXrw54_r8iPVFSBGJhTZduzx5vRg62wu8bdDrUhCm9hR",
    "hlc": "01970e589d21-0004-a13f9c2e"
  }
}
```
- 该状态被加密存储在用户的 account data 中或单独 actor-private stream 中。
- 用户的其他设备通过同步 account data 的变更，获取最新的游标位置，从而清除本地未读红点。
- 多设备 read cursor MUST 按 §6.5 的三段式收敛：同一 commit stream 上 position 更大者胜出；
  仅当两者互不支配时才取 HLC 较大者，HLC 全等才按 `device_id`
  字典序作 actor-internal tiebreaker。Station 不持有 position 的已提交坐标时不得直接用 HLC 决出
  持久 winner。

### 3.3 写入合并

Read Cursor 是 actor-private 持久状态，但仍然是高频更新。客户端 MUST 按 read_scope 合并，只提交相对本地已知 read cursor 单调前进的位置；在同一 `(actor_id, device_id, realm_id, read_scope)` 上的连续滚动 SHOULD 以最新位置覆盖待发送更新。默认建议将活跃阅读期间的持久写入 debounce 到 1 秒以上，或在离开 Strand、应用进入后台、手动标记已读时立即 flush。

服务端接收 actor-private `ak.read_cursor.advance` 时 SHOULD 按 §6.5 的多设备合并规则合并，而不是保留不可见的全量游标历史。若实现需要审计，可保留最小 device、old/new position 和时间摘要；不得把共享 Realm timeline 当作 read cursor 的压缩日志。

## 4. 未读计数 (Unread Notification Count)

未读计数是客户端本地或受托 notification service 维护的派生数据。

1. 客户端同步用户的 account data 拿到最新的 `ak.read_cursor.advance`。
2. 客户端计算 `ak.read_cursor.advance` 指向的 `event_id` 之后，该 Strand discussion track 内产生了多少条新的、应该触发提醒的 Message 或对象事件。
3. 若部署使用受托 notification service，该服务必须按调用者权限和 `plaintext_visible_services` 规则生成最小化结果。

Notification / unread count 是派生状态。服务 MAY 在一个 sync response 中合并多次 read cursor、receipt 和 notification rule 变化，只返回最终 count 与必要 checkpoint；客户端不得把中间 badge 抖动当作协议事件缺失。

## 5. Thread (子线程) 的已读隔离

在 Thread 模式下，Strand discussion timeline 和子 Thread 的阅读进度是分离的。
如果 `ak.receipt.read` 或 `ak.read_cursor.advance` 的目标 `event_id` 是一个 Thread 内的回复，它只更新该 Thread 的已读游标，**不**更新父 Strand discussion timeline 的游标，反之亦然。

Thread 在 read scope 中的 wire 表达（normative）：Thread **不是一等协议对象**，没有独立 id kind、membership 或生命周期；它是某条 root message 的回复子时间线（`replies_to` 链）的投影选择器。Thread 根消息的 `id:message` 在 Read Receipt 中使用 `read_scope.object_ref`，在 Read Cursor 中使用 `read_scope.container_ref`（见 `ak.schema.read_receipt.v1` / `ak.schema.read_cursor.v1` 与 [`../models/private-objects.md` §2.2](../models/private-objects.md)）。两份 schema 的 `read_scope` 共享同一 discriminator 族，但各自声明支持子集，以各自 schema 为权威源。

## 6. Schema 与 Notification Projection

### 6.1 Read Cursor 字段

Read Cursor 是 actor-private 状态。最小结构示例：

```json fragment
{
  "actor_id": "ak:did_core:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw",
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "read_scope": {
    "kind": "strand",
    "container_ref": "ak:strand:Aa-h0nYxlvhQk1U9H0yQTY4hZEVTz0be75pj6U70n7qy",
    "track_name": "discussion"
  },
  "position": {
    "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
    "hlc": "01970e589d21-0004-a13f9c2e"
  }
}
```
字段层级约束以 [`../models/private-objects.md` §2](../models/private-objects.md) 为准。

Read Cursor 对象 MUST NOT 携带 `id`，也 MUST NOT 携带 `updated_at`。没有 read cursor typed ID（id-kind-registry 中不存在 `read_cursor` kind）：对象身份是 `(actor_id, realm_id, read_scope)` 三元组，`ak.read_cursor.advance` 的 `id_source` 是 `not_an_object_id`。它不是可原地更新的对象（没有 revision / CAS），一次「更新」就是 author 一条新的 `ak.read_cursor.advance`，因此该次更新的时间就是那条 Event 信封的 `created_at`。`ak.self.read_cursor.command.advance.v1` 的响应 `read_marker_response_body.updated_at` 与跨设备下发的 actor-private read cursor 更新都是**派生视图**，其 `updated_at` MUST 取当前按 §6.5 胜出的那条 advance 的信封 `created_at`；服务端 MUST NOT 由此反推或要求 payload 携带任何时间字段。

### 6.2 Receipt 公开形态

Receipt 对谁可见取决于 Realm policy，但它始终只作为 §2.1 的 Signal plaintext 出现。
schema：`ak.schema.read_receipt.v1`：

```json fragment
{
  "kind": "ak.receipt.read",
  "payload_sequence": 41,
  "actor_id": "ak:did_core:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw",
  "event_id": "ak:event:AZycRHG_Vh7FL6x4SaV77pX-yi8nr5VSwwO3wMWsBEja",
  "read_scope": {
    "kind": "strand",
    "object_ref": "ak:strand:AaalePlTK6W4ZKrbKyKzlmmcdhXVx-InxeWY4ul69tiN",
    "track_name": "discussion"
  }
}
```
### 6.3 Notification 派生 projection

普通源 Event 通知的身份为 `ak:notification_projection:<token>`。`token` 是 `0x01 || SHA-256(UTF8("ak.notification-projection.v1\n") || RFC8785_JCS(preimage))` 的无填充 base64url 编码，共 44 字符，保留完整 32 字节摘要；域分隔字符串末尾是单个 LF 字节。`preimage` 是 [`notification.schema.json#/$defs/projection_preimage`](../../artifacts/schemas/notification.schema.json#/$defs/projection_preimage) 定义的封闭对象：完整 `recipient_account_id`、`realm_id`、原始 `source_event_id`、`notification_kind`。不得截断摘要形成 UUID，不得重定型 Event ID。

同一源、账户、Realm 和类别在所有设备上 MUST 得到相同身份。规则 ID、revision、read cursor、preview、语言、设备与时间不参与身份。关闭后重新启用规则或清缓存重建 MUST 复用身份；修改源 Event 或类别则必须重新派生。每个源 Event 对每个接收账户、每个类别至多产生一个身份。

普通分支的 `actor_id` MUST 是接收账户的完整 account ActorId，`realm_id` 必填；接收方 MUST 重算并比较身份。摘要本身不证明来源、不授予读取权限。客户端必须先验证原始源 Event 及其适用接受证据，再依据当前访问权和规则本地派生。不得改写源 Event 的作者、payload 或 producer_proof 来承载通知，不得把普通通知装入 `account_data.events[]`，也不得新增第二套通知 HTTP 读取面；普通当前行的唯一交付通道是 account subscribe `notifications.items` 的普通分支（[`../sync/client-sync.md` §3.1.2](../sync/client-sync.md)），其行内容不含 `state`。源缺失、redaction 或撤权时必须清除旧 preview；保留的 inbox 处置状态不能用于恢复正文。

`ak:notification:<uuidv7>` 仅用于 Agent approval 专用分支，继续要求原 producer authority 合同；普通投影摘要不得替代该 UUID。Invite 使用独立的 InviteDeliveryEntry，不属于普通源 Event Notification 分支。共享 inbox 的 key 尾部及解密 value 的 `notification_id` 必须同属一个身份分支且完全相等；archive/dismiss 沿用 encrypted account-data CAS、HLC/device 合并与冲突后重读合并，read/unread 仍独立由 read cursor 派生。

Notification 是派生 projection，不是 canonical truth。schema：`ak.schema.notification.v1`：

```json fragment
{
  "id": "ak:notification_projection:AcDdfcnJk6U1tjvzQvBEKrNJ6zDKlNhVFeh22cy8n_2V",
  "schema": "ak.schema.notification.v1",
  "actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:web:alice.example",
      "station_id": "ak:did_core:web:ps.example"
    }
  },
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "source_event_id": "ak:event:AU_oCPn_WTIYBhptsMI1qfZ28EaYvJo6qGTYZmYG4u7J",
  "source_ref": "ak:message:Ac4grCTeSnv86UIA0vyN5mjzADSkwSSFvGCYIwTHoXqb",
  "strand_id": "ak:strand:AaalePlTK6W4ZKrbKyKzlmmcdhXVx-InxeWY4ul69tiN",
  "track_name": "discussion",
  "notification_kind": "mention",
  "priority": "normal",
  "state": "unread",
  "created_at": "2026-04-26T00:00:00Z"
}
```
`notification_kind` 是封闭枚举，其权威取值集合以 [`notification.schema.json`](../../artifacts/schemas/notification.schema.json) 为准:`message` / `mention` / `reply` / `assignment` / `schedule` / `invite` / `reaction` / `policy` / `call` / `applet` / `agent` / `moderation` / `system`(共 13 值);取未列值的 notification MUST 视为非法。

普通源 Event 的类别判定必须使用 [`../models/private-objects.md` §3.3–§3.6](../models/private-objects.md) 及对应业务对象章节登记的 receiver-side 规则；枚举成员的存在本身不登记 producer，也不允许实现按 Event kind 名称、UI 文案或未验证 preview 猜测类别。当前 source Event、完整 recipient AccountId、effective scope / access、actor-private watch / block / DND / notification rule 与适用 accepted evidence 共同决定是否生成 projection；其中规则只影响生成与展示，不进入 §6.3 的身份前像。缺少任一必需事实时 MUST fail closed，且不得以服务端缓存的 Notification 行或 account-data 包装补成来源证据。

notification / read scope 的 track 字段统一为 `track_name`，`track` 在 schema 层被拒绝（notification.schema.json 顶层 `not.required:["track"]`）。

### 6.4 Query 形状

本节只描述客户端在本地已安装 inbox 上的查询形状；v1 没有对应的 HTTP operation，服务端当前行只经 account subscribe
`notifications.items` 交付（[`../sync/client-sync.md` §3.1.2](../sync/client-sync.md)）。客户端本地 notification query：

```text
state=unread, cursor=<cursor>, limit=<int>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `state` | query | `string` | optional | 通知状态过滤，例如 `unread`。 |
| `cursor` | query | `cursor` | optional | 分页 cursor。 |
| `limit` | query | `int` | optional | 返回数量上限；服务端 MUST enforce 最大值。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `notifications` | `object[]` | required | 当前 principal/device 可见通知。 |
| `counts` | `object` | optional | 未读数等聚合计数。 |
| `next_cursor` | `cursor` | optional | 下一页 cursor。 |

响应示例（非完整 schema）：

```json fragment
{
  "notifications": [],
  "next_cursor": null,
  "counts": {}
}
```
### 6.5 多设备合并

多设备 read cursor 合并规则（按下列优先级,normative）：

1. **支配优先**：position Event 在单权威模型下的唯一顺序是其已提交坐标 `(CommitStreamRef, stream_position)`（[`../sync/authority-commit-log.md` §3](../sync/authority-commit-log.md)）。cursor A 支配 cursor B，当且仅当两者的 position Event 提交在**同一** `CommitStreamRef` 上且 A 的 `stream_position` 更大；此时取 A，**与 HLC / device_id 无关**。合并结果 MUST NOT 回退到任何被它支配的更早 cursor 之前（即不得造成未读计数反弹，与 §6.6 流程第 5 条一致）。
2. **互不支配才比 HLC**：两个 position 提交在不同 stream（Realm／Circle／Sidecar 之间不存在总序），或指向同一 Event 时，二者互不支配，取 HLC 最大者。
3. **HLC 相等才用 device_id**：仅当互不支配且 HLC 全等时，才按 device id 字典序作确定性 tie-break；MUST NOT 用它选中一个被另一方支配的更早 position。

该三段式规则是唯一算法：schema description、operation notes 与 transport binding 表 MUST NOT 把它压缩成无条件 "HLC max"。可执行覆盖见 [`../conformance/conformance-vectors.md` §5.9](../conformance/conformance-vectors.md) 的 `ak.vector.read_cursor.multi_device_merge.v1`。

position 的准入只看已提交坐标，不看 `read_scope` 容器：position Event MUST 是提交在 `realm_id` 内、且位于 owner 在该 stream 可读区间（[`../governance/history-visibility.md` §3.1](../governance/history-visibility.md)）内的 Event，否则以 `param_invalid` 零写入拒绝；协议不要求 position 属于 `read_scope.container_ref` 所指容器，容器归属只影响 owner 自己的未读派生。owner 的 Station 尚未持有该 Event 的已提交坐标时无法判定支配关系，MUST 以 universal `temporarily_unavailable` 零写入拒绝，MUST NOT 用 HLC 选出 winner 或写入 provisional 值；客户端以相同 Event bytes 重试。

通知状态 SHOULD 由 read cursor 与 notification rule 共同推导而来。

同一 actor / scope 的 read cursor 更新 MAY 在传输层批处理；接收端只需要观察最终单调位置。服务端 SHOULD 合并短窗口内的 read cursor、receipt 和 notification projection 更新，并在 sync response 中携带覆盖这些输入的 checkpoint 或 sync token。Push / notification 服务不得为每个 read cursor 变化生成独立通知；它只能重新计算 unread count、badge 和 push suppression。

### 6.6 跨设备同步语义

`ak.read_cursor.advance` 是 actor-private event，默认进入 principal 的 encrypted account data / actor-private stream，不进入共享 Realm timeline，也不推进 Realm reducer checkpoint。其 payload MUST 使用 `ak.schema.read_cursor.v1` 的 Read Cursor 对象形态；该对象仍然必须由当前 actor 或授权 device/session 签名，并绑定 `actor_id`、`realm_id`、read_scope、position、HLC 和 device id；该对象不含 `updated_at`（§6.1）。

其 storage owner、唯一键、winner projection、exact retry 与拒绝事务由
[`../models/actor-private-effects.md` §3.4](../models/actor-private-effects.md#34-read-cursor) 统一闭合；§6.5 只定义 merge 比较顺序。

跨设备已读同步流程：

1. 设备本地读到某个 read_scope 的位置后，author 并签名完整 actor-private `ak.read_cursor.advance`，通过 `ak.self.read_cursor.command.advance.v1` 的 `advance_event: EventAdmissionSubmission` 原样提交；服务端不得从旧 DTO 重建或代签。设备读到该位置的时间由信封 `created_at` 承载（§6.1），payload 内不存在第二份时间字段。
2. Station / Station sync surface 只向同一 principal 的授权设备返回该 read cursor，可通过 `account_data` 或 `receipts` stream 增量同步。下发形态是 `ak.read_cursor.update` device message，其 content MUST 是 `ak.schema.read_cursor_update.v1`（`device-message.schema.json#/$defs/read_cursor_update_content`）：按 §6.5 胜出的 advance 的派生投影，`updated_at` 取该 advance 的信封 `created_at`；它不是 `ak.schema.read_cursor.v1` 对象，MUST NOT 以该 schema id 自述。
3. 每个设备按 §6.5 规则合并同一 read_scope 的 marker，重新派生本地 notification state、unread count 和 push suppression state。
4. 派生 notification 的 `state=read/unread` 不得作为共享 Realm 事实写回；需要公开已读回执时，必须使用 Realm policy 允许的 `ak.receipt.read` ephemeral / receipt stream，并与 private read cursor 分开授权。
5. 当 read cursor 指向的 target event 对某设备不可见、缺失或被 redacted，客户端 MUST 保留 read cursor 但把对应 projection 标记为 `target_missing` / `redacted`，不得回退到更早 read cursor 造成未读计数反弹。

Notification projection MUST 绑定 read cursor checkpoint、notification rule checkpoint 和 source event checkpoint。服务端返回 unread count 时 SHOULD 附带这些 checkpoint 或 sync token；客户端发现 checkpoint 落后时必须重新派生或请求增量，而不是把 push provider 的角标当作协议真相。
