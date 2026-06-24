---
title: "Read Receipts & Markers"
status: candidate
normative: true
stability: v1
updated: 2026-06-24
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

在即时通讯与协作中，“已读”状态是消除信息不对称的关键。Cokret 协议将“已读”分为两种机制：

1. **Read Receipt (已读回执)**：公开或共享的，让**其他人**知道某 actor 已读至哪条消息。
2. **Read Cursor (已读游标)**：私有的，用于 actor **多端设备**之间同步阅读进度。

本规范定义了这两种机制的触发与同步方式。

### 1.1 状态对象对照

| 对象 / Event | Wire scope | 持久性 | 谁可见 | 推送 / 审计关系 |
| --- | --- | --- | --- | --- |
| `ck.receipt.read` / `ck.schema.read_receipt.v1` | `ephemeral_event` | 短 TTL，不进入 durable Event history | 按 visibility 规则广播给发送者或可见成员 | Push Gateway MUST NOT 因 receipt 本身发通知；只能用于 unread / suppression 派生 |
| `ck.read_cursor.advance` / `ck.schema.read_cursor.v1` | actor-private account / durable sync object | 持久保存最新阅读位置，多端同步 | 仅该 actor 的设备和授权 account aggregate 服务 | 作为 unread count、badge 与 push suppression 输入 |
| `ck.notification` / `ck.schema.notification.v1` | derived projection / account aggregate | 派生状态，可重建 | 目标 actor 及其设备 | 不是协议真相源；必须绑定 read cursor frontier、notification rule frontier 与 source event frontier |
| `ck.audit.accessed`（schema 见 audit profile，本表不另列 `ck.schema.*`） | durable Event（审计 profile 下） | 按 audit retention 保留 | 由 Realm audit policy / capability 控制 | 记录受控读取、watch manage_others、late recovery 等访问证明；不得替代 read receipt |

## 2. Read Receipt (已读回执)

已读回执是向同一个 Strand `discussion` track 的可见成员广播“我已经看到这条消息了”。

### 2.1 临时性与高频特征

与具体的业务数据不同，已读回执变动极其频繁（用户每次滑动屏幕都会产生），并且其历史记录没有长期保留价值。
因此，Read Receipt MUST 仅作为 **Ephemeral Event** 通过 Sync Service 的 Ephemeral Channel 广播，不写入持久化 Event 因果图中。HTTP/JSON 参考 binding 为 `ck.self.ephemeral.command.send`（`POST /_cokret/self/ephemeral`），请求体使用 `ck.schema.ephemeral_envelope.v1`，其中 `kind="ck.receipt.read"`。

### 2.2 广播格式

客户端在用户视线停留或明确确认后，以 `ck.schema.ephemeral_envelope.v1` 向 Sync Service 发送；envelope 的 `payload` SHOULD 使用 read receipt object（schema：`ck.schema.read_receipt.v1`）：

```json
{
  "kind": "ck.receipt.read",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example",
  "sent_at": "2026-04-26T10:00:00Z",
  "expires_at": "2026-04-26T10:00:30Z",
  "payload": {
    "receipt_type": "read",
    "schema": "ck.schema.read_receipt.v1",
    "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
    "actor_id": "did:web:alice.example",
    "read_scope": {
      "kind": "strand",
      "ref": "ck:strand:01964200-0000-7000-8000-000000000001",
      "track_name": "discussion"
    },
    "event_id": "ck:event:01964387-7000-7000-8000-000000000000",
    "hlc": "01970e589d21-0004-a13f9c2e",
    "created_at": "2026-04-26T10:00:00Z"
  }
}
```

| 字段 | 说明 |
|------|------|
| `event_id` | 用户已读的最新那条 Event 的 ID。由于因果性，表示该 Event 及其因果前驱均已读。 |
| `actor_id` | 阅读者 DID。该字段名与协议中其它 actor-引用字段一致。 |
| `hlc` | 可选；当 Sync Service 需要按 HLC 合并 / 去重多个 receipts 时由客户端附带。 |

### 2.3 防雪崩与合并

Read Receipt 是高频信号，发送方和 Sync Service 都 MUST 支持合并。客户端 SHOULD debounce 可见区域滚动产生的更新，并且对同一 `(realm_id, read_scope, actor)` 在短窗口内只发送最新位置。默认建议窗口为 1 秒，交互结束、窗口失焦或显式“标为已读”时 SHOULD flush 最新位置。

Sync Service MAY 丢弃同一 read_scope 下较旧的 receipt，只向订阅方广播单调前进的最新位置；不得把每一次滚动增量都 fanout 成独立推送。公开或共享 receipt 的服务端限流维度至少应包含 actor、device、Realm 和 Strand。超过频率时 SHOULD 返回或广播 `rate_limited` / `retry_after_ms` 语义，客户端 MUST 按退避合并后重试。

Push Gateway MUST NOT 因 read receipt 产生通知。它只能把 receipt / marker 作为 unread count、push suppression 和 badge recompute 的输入。

### 2.4 隐私控制

用户可以随时关闭发送已读回执。此配置属于 Client Preference，按 (strand, realm, default) 顺序解析有效偏好；标准 Key 与字段定义见 [`discovery/client-preferences.md`](./client-preferences.md) §3.8。

- 该偏好同步在用户的加密 account data 中，不公开广播。
- `send=false` 只影响"是否发送 `ck.receipt.read`"，不影响 §3 私有 Read Cursor。用户若只想隐藏他人的已读头像，客户端应使用 `ck.read_receipt.preferences.display=false` 做本地渲染偏好；该偏好不得改变 Sync Service 投递或协议状态。
- 客户端收到他人的 `ck.receipt.read` 时，SHOULD 在 UI 上更新已读头像的小图标位置；接收行为不依赖发送偏好。
- 当目标 scope 由 §2.5 声明 `disclosure="required"` 或 `disclosure="disabled"` 时，合规客户端 MUST 按该声明覆盖用户偏好（详见 §2.5）。

### 2.5 Realm 披露策略 (Disclosure Policy)

Realm MAY 通过 `ck.realm.read_receipt_policy` 组件 cell 声明本 Realm 内 `ck.receipt.read` 的披露要求。需要让 Strand 时间线与父 Realm 在 read receipt policy 上分离时，整个 Strand 通过 `Strand.scope_circle_id` 落在一个 [Circle](../models/circle.md)（参见 [`../models/strand-and-message.md` §5](../models/strand-and-message.md)）；effective policy 由父 Realm `ck.realm.read_receipt_policy` 与 Circle 自身策略取更严格者。Track 级别 override 不在 v1 范围内。该 policy SHOULD 由 `ck.realm.policy_components.components.read_receipt` 引用；在 MLS-backed scope 中还必须纳入 MLS-bound `policy_root`。

> **Realm 作用域** 由 enclosing Event envelope 的 `realm_id` 决定；payload 本身不重复 `realm_id`。Payload schema 在 [`event-payload.schema.json#/$defs/read_receipt_policy_payload`](../../artifacts/schemas/event-payload.schema.json) 为闭合对象（`additionalProperties: false`），任何未识别字段或字段名拼写错误（包括 §2.5 中的合规旁路 `allow_child_privacy_tightening_against_required`）在 wire 解析阶段就会以 `schema_violation` 拒绝。Payload **MUST 至少包含一个字段**（schema `minProperties: 1`）：空 `{}` 在语义上与"从不写该 event"等价（cell 保持 null，effective defaults 由 §2.5 字段表给出），因此 wire 上 `payload: {}` MUST 被拒绝；想要"用默认值"的 Realm 直接省略该 event 即可。该约束与 `event-envelope.schema.json` 通用 `ck.realm.*` policy 分支的 `state_payload` `minProperties: 1` 保持一致，避免同一 Event 在两个 schema 分支上得出不同结果。

```json
{
  "kind": "ck.realm.read_receipt_policy",
  "payload": {
    "disclosure": "optional",
    "visibility": "members",
    "scope_overrides_allowed": true
  }
}
```

字段：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `disclosure` | `enum(required, optional, disabled)` | `optional` | 披露要求级别。该字段同时影响隐私上限与合规义务：`required` = 合规客户端 MUST 在该 scope 发送 receipt；`optional` = 完全交给 Client Preference；`disabled` = 客户端与 Sync Service MUST NOT 在该 scope 转发 `ck.receipt.read`。 |
| `visibility` | `enum(public, members, private)` | `members` | receipt 可见性。`public` = Strand 的 effective scope 可见性允许的全部观察者；`members` = Strand effective scope 的可见成员（`scope_circle_id=null` 时为父 Realm 成员，`scope_circle_id` 指向 Circle 时为该 Circle 成员）；`private` = 仅消息发送者本人（Sync Service 按发送者 fanout，不广播给其他成员）。**警告**：在 `history_visibility=world_readable` 的 Realm/Strand 下，`visibility=public` 允许外部观察者读取 actor 的已读位置；若用于 metadata-private 场景，receipt-policy MUST 收紧 `visibility` 为 `members` 或 `private`。该组合的 reducer 级强制判定见 §2.5.1。 |
| `scope_overrides_allowed` | `bool` | `true` | 是否允许 Realm 内的 [Circle](../models/circle.md) 声明独立、**收紧**（不放宽）的 read receipt policy。visibility 的收紧方向固定为 `private` > `members` > `public`。disclosure 必须同时满足两条规则：隐私上限允许 `optional -> disabled`，但合规下限禁止从父 `required` 降到 `optional` 或 `disabled`，除非父 policy 显式声明 `allow_child_privacy_tightening_against_required=true`。父 Realm `scope_overrides_allowed=true` 仅允许 Circle 在满足上述两条规则时进一步收紧；`scope_overrides_allowed=false` 要求 Circle 完全继承父 Realm 策略。任何放宽方向或违反合规下限的 child policy 声明 MUST reducer 拒绝。 |
| `allow_child_privacy_tightening_against_required` | `bool` | `false` | 父 Realm 显式同意 child Realm 把 `disclosure=required` 进一步收紧为 `optional` 或 `disabled` 的合规例外开关。**仅当父 policy 把该字段显式声明为 `true` 时** child policy 才允许 `optional → disabled` 方向跨越合规下限；否则（字段缺省、为 `false` 或字段名拼写错误）reducer MUST 以 `read_receipt_compliance_floor_violated` 拒绝相应 child policy Move。该字段为 prose-defined 合规旁路，schema 必须 `additionalProperties=false` 防止"未识别字段被静默忽略"，writer 必须在该 cell 的 wire JSON 中按字面拼写出现该字段。 |

规则：

- 该策略是**软声明 / 合规承诺**，不是密码学强制。`ck.receipt.read` 由客户端自愿生成，恶意或不合规客户端始终可以"看了不报"，与 audited E2EE 的 RYW receipt（[`crypto-media/audited-e2ee.md`](../crypto-media/audited-e2ee.md) §4）不同。Realm policy MUST NOT 把 `ck.receipt.read` 当作密码学审计回执使用。
- 客户端 MUST 在 join Realm / 进入 Strand 时明示当前生效 `disclosure` 与 `visibility`，并在用户偏好 UI 中标注该 scope 的开关是否被 policy 锁定。
- `disclosure="required"`：合规客户端 MUST NOT 允许用户在该 scope 把 `ck.read_receipt.preferences` 设为 `send=false`，并 SHOULD 在每次进入 track 时按 §2.2 发送至少一条覆盖当前可见 head 的 receipt。
- `disclosure="disabled"`：合规客户端 MUST NOT 生成该 scope 的 `ck.receipt.read`；Sync Service 收到时 SHOULD 丢弃并返回或广播 `policy_violation` 语义。Read Cursor 不受影响。
- `visibility="private"`：Sync Service MUST 仅向 receipt 引用的 `event_id` 的发送者 fanout，不得广播给其他成员。Push Gateway 同样不得据此产生通知。
- Child Realm policy MUST 等于或更严格于父策略，同时不得破坏父策略声明的合规下限。visibility 仅允许 `public→members→private` 方向收紧。disclosure 的隐私收紧方向是 `optional→disabled`；父策略为 `required` 时，child 不得降到 `optional` 或 `disabled`，除非父 policy 显式声明 `allow_child_privacy_tightening_against_required=true`。放宽方向（例如父 `disabled` → 子 `required`、父 `private` → 子 `public`）MUST 被 reducer 拒绝，与 `scope_overrides_allowed` 取值无关——`scope_overrides_allowed=true` 仅允许 child 在上述限制内进一步收紧，`scope_overrides_allowed=false` 要求 child 完全继承父策略。
- 与 §2.3 防雪崩规则共存：即便 `disclosure="required"`，客户端仍 MUST 按 debounce / merge 规则发送，不得为合规绕开限流。

#### 2.5.1 `visibility × history_visibility` 组合约束（normative）

`visibility` 与 Strand effective scope 的 `history_visibility` 的组合按下表判定，采用与 [`discovery-directory.md` §3.1](./discovery-directory.md) 兼容矩阵相近的记号约定（`✓` / `!` / `✗*` / `✗`），但各记号在本表的强度与时点以下方定义为准（与 directory §3.1 的 `!` = "SHOULD 在 Realm create 时显示警告"不同）：`✓` = 允许；`!` = 允许但 reducer MUST 在 accept 时附带警告诊断，客户端 SHOULD 在进入 scope 时显式提示；`✗*` = **默认拒绝、仅在显式 opt-in 后才允许**（reducer MUST 拒绝该组合，除非 policy payload 显式声明对应 opt-in 标记；opt-in 后降级为 `!` 的"允许 + 警告诊断"语义，详见表下说明）；`✗` = reducer MUST 拒绝：

| visibility ↓ \ history_visibility → | `world_readable` | `shared` / `invited` / `joined` / `restricted` |
| --- | --- | --- |
| `private` | ✓ | ✓ |
| `members` | ✓ | ✓ |
| `public` | `✗*`（默认拒绝，opt-in 后降级为 `!`，见下） | ✓ |

- `visibility="public"` + `history_visibility="world_readable"` 会让任意外部 world-readable 观察者读取 actor 的已读位置（活动侧信道）。该组合 MUST 是**显式 opt-in**：reducer MUST 拒绝（`read_receipt_visibility_combination_invalid`）该组合，**除非** receipt policy payload 显式声明 opt-in 标记 `allow_public_receipts_on_world_readable=true`；显式 opt-in 时 reducer MUST 仍附带警告诊断并要求客户端按 §2.4 / §2.5 在 UI 明示。该字段与 `allow_child_privacy_tightening_against_required` 同纪律，是 prose-defined 合规旁路：read_receipt_policy payload schema MUST `additionalProperties=false` 收录该字段，writer 必须在 wire JSON 中按字面拼写出现它，字段缺省 / 为 `false` / 拼写错误时 reducer MUST 按拒绝处理。
- metadata-private 场景下 receipt policy MUST 收紧 `visibility` 为 `members` 或 `private`，不得依赖上述显式 opt-in 旁路。
- **强制公开去匿名组合 fail-closed(normative)**:有效 policy 同时满足 `disclosure="required"`(强制每个成员发送已读位置、用户 MUST NOT 关闭，见 §2.5 字段表)+ `visibility="public"` + `history_visibility="world_readable"` 时，等于**强制**每个成员发出对任意外部观察者可拉取的已读位置且无任何 opt-out——这是无法关闭的强制去匿名活动追踪。reducer MUST 拒绝该有效组合(`read_receipt_forced_public_world_readable_forbidden`),**除非** receipt policy payload 显式声明第二道 opt-in `allow_forced_public_world_readable_receipts=true`。该字段与 `allow_public_receipts_on_world_readable` 同纪律(payload schema `additionalProperties=false` 收录、writer 必须字面拼写出现、缺省/`false`/拼写错误时按拒绝处理)，且它是在前者之上的**第二道**门:`allow_public_receipts_on_world_readable=true` 只解除 `visibility=public`+`world_readable` 本身的拒绝，不解除"叠加 `disclosure=required`"这层强制去匿名。
- **fanout 收口(normative)**:即便已显式 opt-in `allow_public_receipts_on_world_readable=true`,Sync Service **SHOULD** 仍把 `ck.receipt.read` 的 fanout 限制在该 Strand effective scope 的 active member 集合，而**不**把 receipt 主动广播给非成员的 world-readable 外部观察者——即把"历史 world-readable"(读取已落库历史)与"receipt world-readable"(主动 fanout 实时已读位置)解耦。**当上一条的强制组合经第二道 opt-in 被允许时，该 fanout 收口对该组合升为 MUST**:Sync Service MUST 把 fanout 限制在 active member 集合，MUST NOT 主动把 receipt 推送给非成员的 world-readable 外部观察者(外部观察者仍可经历史拉取已落库 receipt，但不得被主动推送)。opt-in 只解除 reducer 的 accept 拒绝，不构成"必须向全网外部观察者主动推送 receipt"的义务；高隐私部署 SHOULD 默认采用该收口。实现者 MUST 向用户明示:public receipt 在 world-readable scope 下，actor 的已读位置对该 scope 的任意外部观察者实际可读，是活动侧信道。
- 该表只约束 receipt `visibility` 与 history visibility 的组合，不替代 §2.5 字段表与 child-policy 收紧规则；冲突时更严格者优先。

## 3. Read Cursor (私有游标)

Read Cursor 用于同一 actor 多设备之间的进度同步（例如手机端已读后，桌面端不再显示未读红点）。它是 actor 的**私有状态**。

### 3.1 存储位置

Read Cursor 作为一种持久化的个人状态，MUST 作为加密 account data 或 actor-private Event 保存，而不是提交到发生协作的共享 Realm Event history。

### 3.2 格式

Read cursor schema：`ck.schema.read_cursor.v1`。Read Cursor 是 actor-private 持久状态，存放在加密 account data 或 actor-private stream 中；wire 对象的 `id` MUST 使用 `ck:read_cursor:<uuid7>` typed ID。实现 MAY 为 account data 使用本地存储 key，但该 key 不得替代 wire 对象 `id`。Read Cursor 按 §6.1 / §6.6 绑定 `(actor_id, realm_id, read_scope, position, hlc, device_id)`：

```json
{
  "id": "ck:read_cursor:01964137-0000-7000-8000-000000000001",
  "schema": "ck.schema.read_cursor.v1",
  "actor_id": "did:web:alice.example",
  "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "read_scope": {
    "kind": "strand",
    "ref": "ck:strand:01964200-0000-7000-8000-000000000001",
    "track_name": "discussion"
  },
  "position": {
    "event_id": "ck:event:01964386-8000-7000-8000-000000000000",
    "hlc": "01970e589d21-0004-a13f9c2e"
  },
  "updated_at": "2026-04-26T10:00:00Z"
}
```

- 该状态被加密存储在用户的 account data 中或单独 actor-private stream 中。
- 用户的其他设备通过同步 account data 的变更，获取最新的游标位置，从而清除本地未读红点。
- 多设备并发 read cursor 收敛 = HLC 取大；HLC 相等时按 device_id 字典序确定的顺序作为 actor-internal tiebreaker。

### 3.3 写入合并

Read Cursor 是 actor-private 持久状态，但仍然是高频更新。客户端 MUST 按 read_scope 合并，只提交相对本地已知 read cursor 单调前进的位置；在同一 `(actor_id, device_id, realm_id, read_scope)` 上的连续滚动 SHOULD 以最新位置覆盖待发送更新。默认建议将活跃阅读期间的持久写入 debounce 到 1 秒以上，或在离开 Strand、应用进入后台、手动标记已读时立即 flush。

服务端接收 actor-private `ck.read_cursor.advance` 时 SHOULD 按第 5 节合并，而不是保留不可见的全量游标历史。若实现需要审计，可保留最小 device、old/new position 和时间摘要；不得把共享 Realm timeline 当作 read cursor 的压缩日志。

## 4. 未读计数 (Unread Notification Count)

未读计数是客户端本地或受托 notification service 维护的派生数据。

1. 客户端同步用户的 account data 拿到最新的 `ck.read_cursor.advance`。
2. 客户端计算 `ck.read_cursor.advance` 指向的 `event_id` 之后，该 Strand discussion track 内产生了多少条新的、应该触发提醒的 Message 或对象事件。
3. 若部署使用受托 notification service，该服务必须按调用者权限和 `plaintext_visible_services` 规则生成最小化结果。

Notification / unread count 是派生状态。服务 MAY 在一个 sync response 中合并多次 read cursor、receipt 和 notification rule 变化，只返回最终 count 与必要 frontier；客户端不得把中间 badge 抖动当作协议事件缺失。

## 5. Thread (子线程) 的已读隔离

在 Thread 模式下，Strand discussion timeline 和子 Thread 的阅读进度是分离的。
如果 `ck.receipt.read` 或 `ck.read_cursor.advance` 的目标 `event_id` 是一个 Thread 内的回复，它只更新该 Thread 的已读游标，**不**更新父 Strand discussion timeline 的游标，反之亦然。

Thread 在 read scope 中的 wire 表达（normative）：Thread **不是一等协议对象**，没有独立 id kind、membership 或生命周期；它是某条 root message 的回复子时间线（`replies_to` 链）的投影选择器。Read Receipt 与 Read Cursor 的 Thread 范围都使用 `read_scope.kind="thread"`、`ref` = Thread 根消息的 `id:message`（见 `ck.schema.read_receipt.v1` / `ck.schema.read_cursor.v1` 与 [`../models/private-objects.md` §2.2](../models/private-objects.md)）。两份 schema 的 `read_scope` 共享同一 discriminator 族，但各自声明支持子集，以各自 schema 为权威源。

## 6. Schema 与 Notification Projection

### 6.1 Read Cursor 字段

Read Cursor 是 actor-private 状态。最小结构示例：

```json
{
  "actor_id": "did:web:alice.example",
  "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "read_scope": {
    "kind": "strand",
    "ref": "ck:strand:01964180-0280-7000-8000-000000000000",
    "track_name": "discussion"
  },
  "position": {
    "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
    "hlc": "01970e589d21-0004-a13f9c2e"
  },
  "updated_at": "2026-04-26T00:00:00Z"
}
```

字段层级约束以 [`../models/private-objects.md` §2](../models/private-objects.md) 为准。

### 6.2 Receipt 公开形态

Receipt 可以公开或私有，取决于 Realm policy。schema：`ck.schema.read_receipt.v1`：

```json
{
  "receipt_type": "read",
  "schema": "ck.schema.read_receipt.v1",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example",
  "read_scope": {
    "kind": "strand",
    "ref": "ck:strand:01964200-0000-7000-8000-000000000001",
    "track_name": "discussion"
  },
  "event_id": "ck:event:01964387-7000-7000-8000-000000000000",
  "created_at": "2026-04-26T00:00:00Z"
}
```

### 6.3 Notification 派生 projection

Notification 是派生 projection，不是 canonical truth。schema：`ck.schema.notification.v1`：

```json
{
  "id": "ck:notification:01964157-8000-7000-8000-000000000000",
  "schema": "ck.schema.notification.v1",
  "actor_id": "did:web:alice.example",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "source_event_id": "ck:event:0196434a-8000-7000-8000-000000000000",
  "source_ref": "ck:message:0196434c-c000-7000-8000-000000000000",
  "strand_id": "ck:strand:01964200-0000-7000-8000-000000000001",
  "track_name": "discussion",
  "notification_type": "mention",
  "priority": "normal",
  "state": "unread",
  "created_at": "2026-04-26T00:00:00Z"
}
```

`notification_type` 是封闭枚举，其权威取值集合以 [`notification.schema.json`](../../artifacts/schemas/notification.schema.json) 为准:`message` / `mention` / `reply` / `assignment` / `invite` / `reaction` / `policy` / `call` / `applet` / `agent` / `moderation` / `system`(共 12 值);取未列值的 notification MUST 视为非法。

notification / read scope 的 track 字段统一为 `track_name`，`track` 在 schema 层被拒绝（notification.schema.json 顶层 `not.required:["track"]`）。

### 6.4 Query 形状

客户端本地 notification query：

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

```json
{
  "notifications": [],
  "next_cursor": null,
  "counts": {}
}
```

### 6.5 多设备合并

多设备 read cursor 合并规则：

- 同一 read_scope 取 causally latest read cursor
- 并发 read cursor 取 HLC 最大
- HLC 相同按 device id tie-break

通知状态 SHOULD 由 read cursor 与 notification rule 共同推导而来。

同一 actor / scope 的 read cursor 更新 MAY 在传输层批处理；接收端只需要观察最终单调位置。服务端 SHOULD 合并短窗口内的 read cursor、receipt 和 notification projection 更新，并在 sync response 中携带覆盖这些输入的 frontier 或 sync token。Push / notification 服务不得为每个 read cursor 变化生成独立通知；它只能重新计算 unread count、badge 和 push suppression。

### 6.6 跨设备同步语义

`ck.read_cursor.advance` 是 actor-private event，默认进入 principal 的 encrypted account data / actor-private stream，不进入共享 Realm timeline，也不推进 Realm reducer frontier。其 payload MUST 使用 `ck.schema.read_cursor.v1` 的 Read Cursor 对象形态；该对象仍然必须由当前 actor 或授权 device/session 签名，并绑定 `actor_id`、`realm_id`、read_scope、position、HLC 和 device id。

跨设备已读同步流程：

1. 设备本地读到某个 read_scope 的位置后，提交或更新 actor-private `ck.read_cursor.advance`。
2. Principal Server / Sync Service 只向同一 principal 的授权设备返回该 read cursor，可通过 `account_data` 或 `receipts` stream 增量同步。
3. 每个设备按 §6.5 规则合并同一 read_scope 的 marker，重新派生本地 notification state、unread count 和 push suppression state。
4. 派生 notification 的 `state=read/unread` 不得作为共享 Realm 事实写回；需要公开已读回执时，必须使用 Realm policy 允许的 `ck.receipt.read` ephemeral / receipt stream，并与 private read cursor 分开授权。
5. 当 read cursor 指向的 target event 对某设备不可见、缺失或被 redacted，客户端 MUST 保留 read cursor 但把对应 projection 标记为 `target_missing` / `redacted`，不得回退到更早 read cursor 造成未读计数反弹。

Notification projection MUST 绑定 read cursor frontier、notification rule frontier 和 source event frontier。服务端返回 unread count 时 SHOULD 附带这些 frontier 或 sync token；客户端发现 frontier 落后时必须重新派生或请求增量，而不是把 push provider 的角标当作协议真相。
