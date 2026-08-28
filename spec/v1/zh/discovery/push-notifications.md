---
title: Push Notifications
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

去中心化协作协议中，用户的客户端不可能永远在线监听 Principal Server sync surface 的 Sync Stream。当用户离线时，协议需要一套标准化的**推送通知机制**，将重要事件及时送达用户的移动设备或桌面系统。

本规范定义了：
- 推送规则引擎：用户可自定义哪些事件触发推送
- 推送网关接口：标准化的第三方推送投递协议
- E2EE 场景下的隐私保护推送

## 2. 设计原则

### 2.1 推送由 Principal Server sync surface 或受托通知服务触发

客户端在离线前向 Principal Server sync surface 注册推送设备信息。此后由 Principal Server sync surface 或 Realm policy 明确授权的通知服务按服务端内置的 membership、watch/mute、blocklist、route 与 `wakeup_default` gate 产生 blind / batch wakeup；设备被唤醒并解密后，在客户端执行用户的完整 push-rule chain，再决定是否进入用户可感知的通知 surface。

### 2.2 推送内容脱敏 (Blind Wakeup)

Blind wakeup **不是可选 extension**，而是 push gateway 的**默认互操作安全基线**：声明 `ak.profile.push_gateway.v1` 的实现 MUST 同时声明 `ak.profile.push_gateway.blind_wakeup.v1` 并在所有 provider 出向通知上强制其约束。可见通知字段只在显式声明 `ak.profile.push_gateway.visible_notification.v1` 且满足 Realm policy + 设备 opt-in + UI 明示三项前置时才允许，且仍受最小化约束（见 [`conformance/conformance-profiles.md` §11](../conformance/conformance-profiles.md)）。Matrix 兼容部署使用 `ak.profile.push_gateway.matrix_passthrough.v1`，**MUST NOT** 与默认 v1 隐私基线在同一 `(recipient_id, device)` 元组上混用。

在 E2EE 场景下，Principal Server sync surface 无法读取消息正文。推送通知的默认行为是**脱敏唤醒 (Blind Wakeup)**：
- 推送上游（APNs / FCM / Push Gateway）只携带 **per-(recipient_id, principal, device, push_route) pairwise pseudonym** `push_target_id` 与最小唤醒提示（`wakeup_kind` 等），不得携带 principal DID、sender DID、Realm id、event id、device verification-method DID URL 或任何其它跨 Realm 稳定标识。设备自身没有 DID。具体规则见 [`crypto-media/device-lifecycle.md` §5.6 Privacy-Preserving Push](../crypto-media/device-lifecycle.md)。同一 DID 在个人 Principal Server 与组织 Principal Server 上的推送注册必须不可链接。
- `push_target_id` 派生 MUST 使用接收服务私有 secret salt / pepper：`tag = HMAC-SHA256(service_push_secret[salt_epoch_id], canonical_json({recipient_id, principal_id, device_id, push_route_id, salt_epoch_id}))`，并把完整 32-octet `tag` 编码为 `ak:pseudonym:push:<canonical unpadded Base64URL(tag)>`。不得截断 HMAC，不得输出 raw Base64URL 或其它长度。接收方 MUST 解码恰好 32 octets 并执行 canonical 重编码校验；唯一 schema 是 `common-ids.schema.json#/$defs/push_target_id`。`service_push_secret` 原值绝不能上 wire；`ak.server.read.describe.v1.privacy_derivation.push_target_id_derivation` 只发布 `derivation_profile`、`salt_epoch_id`、`salt_rotation_seconds` 和输入绑定元数据，供客户端和 conformance 工具确认不同 Principal Server / 组织 / push route 不会复用同一可链接命名空间。
- 客户端被唤醒后自行从 Principal Server sync surface 拉取并解密实际内容；本地通知文案在客户端解密后生成。
- **`push_hint` 即使在 `plaintext_visible_services` 下也 MUST 受白名单约束**：受信通知服务 MAY 附加 `push_hint` 字段，其封闭枚举的**权威定义在 §5.1**（取值 `new_message` / `incoming_call` / `mention_self`，或哨兵值 `l10n_key`——后者为「形态选择器」，实际本地化键由独立字段 `push_hint_l10n_key` 承载，由客户端在解密后渲染）；本节及 §4.5 一律交叉引用 §5.1，不另列重复枚举。`push_hint` 与 `wakeup_kind` 是**两个独立字段**：`wakeup_kind`（封闭枚举 `message` / `mention` / `assignment` / `schedule` / `reaction` / `call_invite` / `reminder` / `scheduled_send` / `expiry_invalidation`，后三者为 Phase-P2 生产力唤醒类别，同为粗粒度、不带 Realm / sender 信息）是独立的粗粒度唤醒类别字段，**不是** `push_hint` 的子内容，二者 MUST NOT 互相替代或嵌套。`push_hint` **MUST NOT** 携带：正文（任何形态）、sender DID 或 handle、principal_id、Realm id / 名称 / 头像、Strand id / 名称、Space id / 名称、Message id、reaction emoji 实际值、附件文件名、badge / 未读绝对计数明文（计数走 `notification.counts`，且按 §5.1 / §6.2 最小化约束）、stable correlation key、IP / geolocation。`plaintext_visible_services` 是"允许接收明文"的授权而非"放行 metadata"的授权——push gateway 即使被授权也不得变成跨 Realm 行为追踪点。违反此约束的推送实现 MUST 在 conformance lint 中标记为不合规。

- **Principal Server sync surface 转发也必须执行同一白名单**：Sync / notification service 在调用 `/_arkret/edge/push/notify` 前 MUST 校验将要转发给 Push Gateway 的字段集合。默认 `blind_wakeup` profile 下，超出 §5.1 枚举字段的 metadata MUST 被 strip，并写入最小化 audit 记录；若字段属于 event / realm / sender 识别字段且未满足 `visible_notification` profile gate，服务 MUST 拒绝该通知或降级为 blind wakeup，不得原样转发。

### 2.3 用户完全控制推送规则

推送规则是 Actor-private 的配置，存储在用户自己的加密 account data 中。用户有权关闭任何 Realm 的推送、设置静默时段、自定义关键词触发等。

### 2.4 多订阅信道去重与 presence timing

同一事件可能同时命中显式 watch、隐式参与订阅、mention rule、read-cursor badge recompute、presence-triggered foreground wakeup 或 notification projection。Principal Server sync surface / notification service 在调用 Push Gateway 前 MUST 在出口做去重：同一 `(recipient_id, device_id, push_route_id, source_event_digest)` 在一个 delivery window 内最多产生一条 push wakeup。默认 `blind_wakeup` profile 下，去重 key 是服务端内部状态，MUST NOT 出现在 push payload、日志导出、provider custom data 或客户端可见的 stable correlation key 中。

**Provider 侧 collapse / dedup key 约束（normative）**：部分 provider（APNs `apns-collapse-id`、FCM `collapse_key`）需要服务端在 push 请求里附带一个 collapse / dedup key 以折叠同一目标的连续 wakeup。该 key 对 provider 可见，因此 MUST NOT 泄露稳定 correlation：

- 若需要向 provider 提供 collapse key，服务端 MUST 使用对 `push_target_id` 与当前 delivery window 派生的、**跨 window 不可链接**的随机值（例如 `HMAC-SHA256(service_push_secret[salt_epoch_id], canonical_json({push_target_id, delivery_window_id}))` 截断编码），使同一 `push_target_id` 在不同 delivery window 得到互不关联的 collapse key。
- collapse / dedup key **MUST NOT** 直接使用 `source_event_digest`、其前缀、event id、Realm id、Strand id 或任何跨 window 稳定的事件 / 资源派生值；上述出口 `source_event_digest` 仅作为服务端内部去重状态，不得离开服务端进入 provider 可见字段。

Presence 不得作为精确 push timing oracle。服务端把 presence update、watch recompute 与 push activation 组合使用时，MUST 至少按 Realm policy 声明的 bucket 粒度（默认不小于 60s；高隐私部署 SHOULD 使用 5min 或更粗）批处理或延迟；不得在用户刚上线 / 刚离线的瞬间立即发出可被 provider 观察到的 per-event push burst。该规则不阻止本地客户端在已在线连接上立即显示通知；它只约束第三方 push provider 可见的出向时序。

## 3. 推送设备注册

### 3.1 注册接口

客户端在上线时 SHOULD 向 Principal Server sync surface 注册推送设备：

```
POST /_arkret/edge/push/register-device
```

请求示例（非完整 schema）：

```json
{
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "push_gateway_uri": "https://push.example.com/_arkret/edge/push/notify",
  "push_key": "fcm:eJx9k2...",
  "platform": "android",
  "app_id": "com.arkret.client",
  "display_name": "Alice's Pixel 9"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `device_id` | id:device | MUST | 设备的 typed id,形态为 `ak:device:<uuidv7>`(与 push-operations.schema.json `device_id` pattern 一致) |
| `push_gateway_uri` | string | MUST | 推送网关的 URL |
| `push_key` | string | MUST | 设备在推送平台上的注册令牌 |
| `platform` | string | SHOULD | `android`, `ios`, `web`, `desktop` |
| `app_id` | string | SHOULD | 应用的包名 / Bundle ID |
| `display_name` | string | MAY | 用户可读设备名 |

Push registration 的作用域是接收该请求的 Principal Server sync surface / Principal Server service DID。客户端在个人 Principal Server 与组织 Principal Server 上同时登录同一 DID 时，MUST 分别注册互不相关的 push route / `push_target_id`；服务端不得把一个上下文中的 push token 或伪名复制到另一个上下文。实现若在请求中扩展携带 `recipient_id`，其值 MUST 与目标服务的 `ak.server.read.describe.v1.service_id` 一致。

响应字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `push_target_id` | `PushTargetId` | required | 服务端按 §2.2 派生的完整 32-octet HMAC-SHA256 typed pairwise pseudonym；见下方 normative 约束 |
| `registration_id` | id | optional | 服务端分配的注册 ID |
| `expires_at` | datetime | optional | 本 Sync / Principal Service 上该 push registration 记录的服务端有效期；不表示 APNs / FCM / WebPush provider token 自身过期时间 |

**`push_target_id` 响应约束（normative）**：注册成功响应 MUST 携带服务端按 §2.2 派生的 `push_target_id`，这是调用方取得该伪名的唯一契约通路。`/_arkret/edge/push/notify` 的调用方 MUST 使用该值作为 `notification.push_target_id`，MUST NOT 自行推导、改造或复用其它标识；设备 MUST 以该值为准写入 / 核对 `ak.device.push_route` actor-private state（见 [`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §5.6）。

`expires_at` 若出现，MUST 只约束本次 Arkret push registration 记录。Provider token 的平台生命周期、撤销或轮换由 provider adapter 在实现内部处理，或通过新的注册请求提交新的 `push_key`；不得把 provider token 过期时间塞入 `expires_at`。客户端 SHOULD 在 `expires_at` 前主动重注册；到期后服务端 MUST 停止使用该 registration 投递 push，并在下一次注册 / describe / sync 投影中以等价的 `push_registration_expired` 状态或重新注册要求暴露给该 holder。`ak.device.push_route` 的轮换周期仍由 [`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §5.6.2 约束；若两者都存在，较早失效者控制实际投递。

### 3.2 注销接口

```
POST /_arkret/edge/push/unregister-device
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `device_id` | id:device | required | 要注销的设备标识；形态与 §3.1 register 的 `device_id` 一致（typed id `ak:device:<uuidv7>`，如 `ak:device:01964137-0000-7000-8000-000000000000`），MUST byte-for-byte 等于注册时提交的值 |
| `push_key` | string | optional | 指定要注销的 push token |
| `app_id` | string | optional | 指定应用包名 / Bundle ID |

成功响应固定为 HTTP 204 且没有 entity body；注册不存在也必须按同一幂等成功处理。不得返回 JSON 占位对象。

## 4. 推送规则引擎

### 4.1 规则结构

推送规则按优先级从高到低排列，由客户端在解密后对**完整有序规则链**求值，第一条匹配的规则决定推送行为。服务端内置 dispatch gate 不属于这条用户规则链，不能截断或代替客户端 first-match 求值：

```json
{
  "rules": [
    {
      "rule_id": "override.mute-realm-x",
      "kind": "override",
      "enabled": true,
      "conditions": [
        { "kind": "field_match", "field": "realm_id", "pattern": "ak:realm:AUXJQDk6Ju_WYm3B2b23k1q5DEwVlFMwJ0UqCPVJz58U..." }
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
        { "kind": "field_match", "field": "kind", "pattern": "ak.message.create" },
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
| `override` | 最高 | 用户手动设置的覆盖规则（如静音某个 Realm） |
| `content` | 高 | 基于消息内容的关键词匹配 |
| `underride` | 低 | 默认规则，当没有更高优先级规则匹配时生效 |

### 4.3 条件类型 (Condition Kinds)

| Condition Kind | 用户规则评估位置 | 说明 |
|---------------|---------|------|
| `field_match` | client | 客户端对已授权可见的 Event metadata / payload 字段匹配给定 pattern（支持 glob）。 |
| `contains_keyword` | client | 解密后的消息 `body` 包含指定关键词。 |
| `mentions_actor` | client | 解密后的 direct mention 或 audience 展开结果包含当前 Actor。 |
| `is_direct_message` | client | 当前 Realm 是已验证的 1 对 1 Direct Conversation Realm。 |
| `member_count` | client | 客户端在当前授权 roster projection 上评估成员数条件。 |
| `strand_track` | client | Event 关联的 Strand track 名匹配给定 pattern（支持 glob）。 |
| `watch_state` | client | receiver-side watch level 匹配给定 pattern；服务端对 `muted` 的强制 dispatch gate 另见 §4.3.2。 |

`ak.push_rules` 存在 encrypted account data 中，v1 每条用户 rule 的 `evaluation_locus`
MUST 为 `client`；`server` 值保留给未来显式注册的明文 projection profile，v1 receiver
MUST 以 `unsupported_feature` 拒绝，不能读取 account-data ciphertext 后猜测规则。
Principal Server sync surface 只执行本文件明确列出的内置 dispatch gate 与 coarse wakeup policy，不匹配用户规则。

**`is_direct_message` / `member_count` 的侧信道收口（normative）**：Principal Server sync surface 不得为匹配用户规则取得精确成员数或“是否双人私聊”投影。客户端只能使用自己在正常授权读取中已经获得的 roster / Direct Conversation binding；minimal-metadata Realm 若不向该客户端披露精确值，则该条件求值为 indeterminate 并继续检查下一条规则，不得触发 allow/notify。

对 bucket 值求比较时，注册方 MUST 先把数值谓词映射为整数集合，并逐 bucket 检查：与 bucket 区间无交集则该 bucket 求值 `false`；bucket 全部落入谓词集合则求值 `true`；只部分相交属于不确定规则，MUST 在规则注册 / 更新时以 `param_invalid` 拒绝，不能按精确成员数补算。开放上界 bucket 同样按区间集合处理。因此 E2EE / 高隐私 Realm 的 `member_count` 阈值 MUST 对齐 bucket 边界；示例 `<= 5` 在默认 `1-10` grid 上非法，调用方应改用 `<= 10` 或 client-side 评估。

#### 4.3.1 `strand_track` 与 per-track 通知

Track 不持有独立 membership / 权限（见 [`../models/strand-and-message.md` §4](../models/strand-and-message.md)），但用户对不同 track 的关注度不同——例如想接收某个 Strand 的 `synthesis` 全部更新，但 `discussion` 只关心 @ 自己。`strand_track` condition 用于在通知层表达这种偏好，不影响访问控制。

**`track_name` 的派生**：客户端从已验证 Event 与 Strand state 确定性推导；Principal Server sync surface MAY 为内置粗粒度 batching / route gate 推导同一值，但不得据此匹配 holder 的加密用户规则。它不是客户端在 wire 上自由设置的字段：

- Event payload 显式引用 Strand（如 `ak.message.create` 携带 `strand_id`，或 `ak.strand.update` 直接作用于 Strand）→ 按 Event 类型映射：
  - `ak.message.create` / `ak.message.revise` / `ak.message.redact` / `ak.reaction.add` / `ak.reaction.remove` 在 Strand 的 discussion timeline 中产生 → `track_name = "discussion"`
  - `ak.strand.update` 的 patch 触及 `tracks.synthesis.content` / `tracks.synthesis.encrypted_content` → `track_name = "synthesis"`；同时必须通过该 track 的 active gate
  - `ak.strand.update` 只修改 `content` / `encrypted_content`（Description）、metadata、状态、标题等 Strand 基础字段 → 不派生 `track_name`；这些字段不属于任一 track
  - `ak.strand.create` / `ak.strand.archive` / `ak.strand.restore` / `ak.strand.move` / `ak.strand.reorder` → 不派生 `track_name`（生命周期与位置是 Strand 基础面，不得冒充 synthesis 更新）
  - `ak.strand.tracks.update`（track 配置 / primary / enabled 变更）→ patch 影响的每个 track key 各派生一条 `track_name`；同时影响多个 track 时 server 派生 set，`strand_track` pattern 匹配任一即匹配
  - `ak.strand.watch.set` → `track_name` 不派生（watch 是个人偏好，不属于任一 track 时间线）；`strand_track` condition 视为不匹配
- Event 不属于任何 Strand（普通 Realm 消息）→ `strand_track` condition 视为不匹配（既不为真，也不报错）；用户希望覆盖普通 Realm 消息时应使用 `field_match` on `realm_id` 而非 `strand_track`
- Strand 设置了 `scope_circle_id` 指向 Circle → Strand 的所有 track（含 discussion）的 `ak.message.*` 落在该 [Circle](../models/circle.md) scope；server MUST 校验通知 receiver 属于该 Circle 成员集合，否则 MUST `dont_notify` 并不暴露该 Strand 的存在性（与 [`../models/circle.md` §9.3](../models/circle.md) 一致）。

`strand_track` MUST NOT 携带任何正文或 mention 信息进入推送 payload；它只在客户端完整规则链中影响 `notify` / `dont_notify` 的最终决定。

示例（synthesis 全收，discussion 仅 mention 自己）：

```json
[
  {
    "rule_id": "underride.strand-synthesis-all",
    "kind": "underride",
    "enabled": true,
    "evaluation_locus": "client",
    "conditions": [
      { "kind": "strand_track", "pattern": "synthesis" }
    ],
    "actions": ["notify"]
  },
  {
    "rule_id": "underride.strand-discussion-mention-only",
    "kind": "underride",
    "enabled": true,
    "evaluation_locus": "client",
    "conditions": [
      { "kind": "strand_track", "pattern": "discussion" },
      { "kind": "mentions_actor" }
    ],
    "actions": ["notify", "highlight"]
  }
]
```

两条规则都由客户端在解密并验证 Event 后按同一有序链求值。服务端只按 Realm 级 `wakeup_default` 与设备注册状态选择是否 blind / batch wakeup。

#### 4.3.2 `watch_state` 与订阅偏好

`watch_state` condition 由客户端用 receiver 的 watch level（[`../models/strand-and-message.md` §8](../models/strand-and-message.md)）匹配。Principal Server sync surface 可直接读取 receiver 的 canonical watch cell，并把 `muted` 作为独立于用户规则链的强制 dispatch gate；它不得因此读取或执行 encrypted `ak.push_rules`。

**两层职责**：

- **服务端 dispatch gate 决定是否发 coarse wakeup**：Principal Server sync surface 在派发前解析 receiver effective level；`muted` 必须抑制 wakeup。无法从 opaque E2EE Event 判断 `mentions_only` 是否命中时，按 §4.5 的 `wakeup_default` 批量/盲唤醒，不得猜测用户规则结果。
- **客户端 push rule 决定用户可感知通知**：客户端被唤醒、同步并解密后，对完整链 first-match，决定提示音、高亮、DND 例外或 `dont_notify`。

**`muted` 强约束的实现自由度**：`watch_state=muted` MUST 收敛到 `dont_notify`，但实现可以在以下下列等价路径中任选：

- (a) **Dispatch short-circuit**：在产生 wakeup 前直接判定 `dont_notify`；
- (b) **Built-in dispatch deny**：在服务端内置 gate 链最高优先级位置注入不可写、不可禁用的 deny gate。

两种路径在 dispatch 输出上**不可区分**。实现 SHOULD 在 dispatch decision log 中标注 `muted_short_circuit=true` 便于排错。Principal Server sync surface 即使没有任何用户规则也 MUST 保证 muted 收敛。用户 MAY 另写冗余的 client-side `override.respect-mute`，但它不替代服务端 gate。

补充约束：

- 用户希望"被 @ 仍然提醒但不要其他通知"应使用 `mentions_only`（默认即此），不要用 `muted`。
- 隐含订阅（如 assigned_to=self）在 `watch_state` 评估时折算为 `participating`；用户可通过显式写 `muted` watch cell 屏蔽。

示例（user-declared override 路径 + 显式 `all` underride）：

```json
[
  {
    "rule_id": "override.respect-mute",
    "kind": "override",
    "enabled": true,
    "evaluation_locus": "client",
    "conditions": [
      { "kind": "watch_state", "pattern": "muted" }
    ],
    "actions": ["dont_notify"]
  },
  {
    "rule_id": "underride.watching-all",
    "kind": "underride",
    "enabled": true,
    "evaluation_locus": "client",
    "conditions": [
      { "kind": "watch_state", "pattern": ["participating", "all"] }
    ],
    "actions": ["notify"]
  }
]
```

`override.respect-mute` 对服务端 dispatch gate 是冗余声明，但 wire 上合法，可让客户端本地通知 trace 记录 `matched_rule="override.respect-mute"`。服务端不得声称匹配了该 encrypted rule。

#### 4.3.3 Audience mention fanout

Audience mention（例如 `@all` / `@here`）的规范性节点形态、允许的 audience 集合和授权规则定义在 [`../models/strand-and-message.md` §9.4.3-§9.4.4](../models/strand-and-message.md)。Push rule 引擎只看到 receiver-side 结果：若当前 receiver 是该 audience mention 在 source event causal frontier 下展开后的合法接收者，则 `mentions_actor` 为 true；否则为 false。

Dispatcher 在把 audience mention 转换为 notification / push 前 MUST 先完成以下 gate，且任一失败都不得产生 push wakeup：

- sender 同时持有普通消息写入授权和 `ak.message.mention.broadcast` 授权；
- effective Realm / Circle policy 允许该 `audience`，并声明有限 `max_recipients` 与 quota；
- 展开后的 receiver 通过 Message effective scope、history visibility、Circle membership 和 target policy；
- receiver 的 `level=muted`、个人 blocklist、DND 或更高优先级 `dont_notify` rule 没有抑制该通知。

`@here` 在 v1 中映射为 `audience="strand_engaged"`，即当前 Strand discussion 的历史参与者与当前有效 watchers 的并集；它不使用 presence / online 状态。`strand_watchers` 和 `strand_engaged` 的 watch 命中原因只在 receiver-side dispatcher 内部可见，MUST NOT 反向暴露给 sender 或普通 Realm 成员。

Audience expansion 是 dispatcher 内部计算结果，MUST NOT 进入 push payload、provider custom data、公开日志导出或可被发送者枚举的 delivery response。默认 `blind_wakeup` 下，即使 wakeup kind 是 `mention`，payload 也不得包含 `@all` / `@here`、audience 名称、recipient count、成员列表、watch level、watcher 列表或 source Event / Realm / Strand 识别字段。

E2EE Realm 中，server 不能读取 audience mention AST，也没有可放宽此边界的 routing-hint policy。Principal Server sync surface MUST 按 §4.5 的 client-side rule fallback 处理，不得从消息大小、发送者文本或客户端上传的额外字段推断 `@all` / `@here`。

### 4.4 动作类型 (Actions)

| Action | 说明 |
|--------|------|
| `notify` | 发送推送通知 |
| `dont_notify` | 不发送推送（静音） |
| `sound_default` | 使用默认提示音 |
| `sound_critical` | 使用紧急提示音 |
| `highlight` | 在客户端标记为高亮 |

### 4.5 E2EE Realm 中的规则降级

Principal Server sync surface 不读取 encrypted `ak.push_rules`，在 E2EE Realm 中也不持有正文密钥，因此不能预判用户完整规则链。**实现 MUST NOT** 把尚未在客户端求值的规则静默视为不匹配（这会漏掉通知），也 MUST NOT 把它视为匹配（这会变成无差别可感知通知）。服务端只产生受 coarse gate 约束的 blind / batch wakeup，降级路径如下：

1. **完整链客户端求值**：v1 每条 push rule 都 MUST 声明 `evaluation_locus="client"`。客户端被唤醒并同步后，必须从最高优先级开始对**完整有序链**重新求值，直到第一条匹配；不得只评估某个“未解析子集”，也不得把服务端 coarse gate 的结果当作链中已匹配规则。客户端在本地决定是否触发系统 banner、桌面提示或声音；Principal Server sync surface 不参与用户规则匹配。
2. **Server fallback notify**：E2EE Realm 中，针对 client-side rule，Principal Server sync surface MUST 走 Realm policy 声明的保守 wakeup 策略。`wakeup_default` 取值为 `wakeup_for_all_messages` / `batch_wakeup` / `no_notification`，缺省为 `batch_wakeup`。**术语区分（normative）**：此处 Realm policy 字段 `wakeup_default`（决定 server 在无法解密 client-side rule 时**是否 / 以何种频次唤醒**的策略枚举）与 [`../overview/glossary.md`](../overview/glossary.md) "Push terminology layering" 中作为 **payload disclosure class** 的 Wakeup（即 `ak.profile.push_gateway.blind_wakeup.v1` 等 wakeup 信封 profile，决定 payload 可见性等级）处于**两个不同语义轴**，不得互换：`wakeup_default` 不改变 payload disclosure class，blind_wakeup 信封约束（§2.2 / §5.1）在任何 `wakeup_default` 取值下仍然适用。高隐私、minimal-metadata 与 audited Realm SHOULD 使用 `no_notification` 或 `batch_wakeup`。服务部署对某 route 应用 `ak.profile.traffic_metadata_hardened.v1` 时，该 route MUST 使用 `batch_wakeup` 或 `no_notification`，并按该 profile 的 `push_wakeup_mode` 与 retry cadence padding 参数执行；这不构成 Realm profile activation。客户端被唤醒后本地解密、本地评估 client-side rule，再决定显示哪个通知 surface（普通 banner / 高亮 banner / 静默处理）。若 `wakeup_default=no_notification`，server 不得因为无法解密 client-side rule 而单独唤醒，只能等待客户端下次 sync 或命中 server-side opaque routing token。
3. **降级标记**：Principal Server sync surface 在 push payload 中携带 `evaluation_locus_unresolved=true`，让客户端知道"我已经被 wakeup 但匹配尚未在 server 端确定"。客户端 MUST 完成本地评估后才决定是否进入用户感知的通知 surface；不得仅凭 wakeup 就在 system tray 弹出。
4. **明文 hint 限制**：E2EE Realm 中，`push_hint` MUST NOT 包含会让 push gateway 间接获得规则匹配信息的字段（例如 "matched_keyword: 'urgent'"）。默认 `blind_wakeup` 下，hint 只能携带固定枚举字段（`new_message` / `incoming_call` / `mention_self`）或 `l10n_key`，不能携带匹配到的具体内容。即使 Realm policy 把 push gateway 列入 `plaintext_visible_services`，也只允许进入 §5.1 的 `visible_notification` profile；不得把该授权解释为放宽 `blind_wakeup` 的 metadata 限制。
5. **限速降级**：E2EE Realm + client-side rule 多的 client 在高消息量场景会被持续 wakeup，电池负担显著。客户端 MUST 暴露 `aggressive_wakeup_threshold`（默认每 60 秒 ≤ 30 次）；超过阈值后切换到批量 wakeup 模式，Principal Server sync surface 把多个 wakeup 合并为单个 batch wakeup（仍携带 `evaluation_locus_unresolved=true`），客户端醒来一次评估全部待处理 Event。
6. **Mention 保持端到端加密**：v1 不定义专用 mention recipient token、routing sidecar、注册表或服务端等值比较。E2EE mention 只能留在 ciphertext 中；Principal Server 一律按第 1-5 步 blind / batch wakeup，客户端同步、解密后本地判断 mention 与展示。任何专用 mention routing wire 输入均必须 schema reject。

明确禁止：

- 实现 MUST NOT 在 E2EE Realm 中把 `contains_keyword` rule 提示让 Principal Server sync surface 持有 keyword 列表（即使加 hash）。Keyword 比 mention 高熵——hash 可被字典爆破。
- 实现 MUST NOT 通过"让客户端把解密结果回传 Principal Server sync surface 完成匹配后再发推送"的形式实现 server-side rule。这条路径等于把客户端解密能力委托给 Principal Server sync surface，违反 E2EE 边界。

## 5. 推送网关接口 (Push Gateway API)

### 5.1 通知推送

Principal Server sync surface 在触发推送规则后，向推送网关发送通知：

```
POST /_arkret/edge/push/notify
```

请求字段（默认 `blind_wakeup` profile；该 profile 永远不得携带 Realm / sender / event 识别字段）：

| 字段 | 类型 | 必填 | 说明与约束 |
|------|------|------|------|
| `notification` | object | required | 推送通知对象。 |
| `notification.push_target_id` | `PushTargetId` | required | per-(recipient_id, principal, device, push_route) pairwise pseudonym（见 [`crypto-media/device-lifecycle.md` §5.6](../crypto-media/device-lifecycle.md)）。MUST NOT 是 principal DID、device verification-method DID URL、handle 或可跨 Realm / Principal Server 上下文关联的稳定 ID。 |
| `notification.wakeup_kind` | string | required | 粗粒度唤醒类别，封闭枚举 `message` / `mention` / `assignment` / `schedule` / `reaction` / `call_invite` / `reminder` / `scheduled_send` / `expiry_invalidation`（与 §2.2 一致；后三者为 Phase-P2 生产力唤醒）；只是粗粒度提示，不带 Realm / sender 信息。 |
| `notification.push_hint` | string | optional | 受信通知服务提供的脱敏提示形态选择器，与 `wakeup_kind` 是不同字段：`blind_wakeup` 下其封闭枚举为 `new_message` / `incoming_call` / `mention_self`（见 §4.5），或哨兵值 `l10n_key`。**`l10n_key` 是「形态选择器」而非字面展示 token**：当 `push_hint == "l10n_key"` 时，实际本地化键 MUST 由独立字段 `push_hint_l10n_key` 承载（不得把 l10n key 直接塞进 `push_hint` 值）。不得包含正文、sender DID / handle、Realm id / 名称、Strand / Message id、reaction 实际值或 stable correlation key。 |
| `notification.push_hint_l10n_key` | string | conditional | 仅当 `push_hint == "l10n_key"` 时出现且 MUST 提供；承载实际本地化键 token（如 `push.new_message`），由客户端在解密后用于本地渲染。MUST NOT 携带正文或任何识别性 metadata。 |
| `notification.evaluation_locus_unresolved` | boolean | optional | 客户端规则待求值信号（见 §4.5 第 3 步）：为 `true` 表示设备已被唤醒，但完整用户规则链尚未在客户端求值。纯本地评估信号，不携带 metadata。 |
| `notification.timing_profile_hint` | string | required | Principal Server sync surface 提供的闭合时序 / profile hint，封闭枚举 `default` / `traffic_metadata_hardened`。当值为 `traffic_metadata_hardened` 时，表示来源服务已在 ServiceDescribe 声明支持并由部署配置对该 route 应用 `ak.profile.traffic_metadata_hardened.v1`；Push Gateway MUST 对 provider 可见出向 push 使用 300s 或更粗 timing bucket。该字段只驱动 gateway 内部时序，不得转发给 provider，也不得替代 `wakeup_default`、Realm policy 或 payload disclosure profile。 |
| `notification.counts` | object | optional | 未读数、未接来电数等计数。**`blind_wakeup` 下约束（normative）**：绝对未读数是活动侧信道，会让 provider 推断用户的累计活跃度，且 §2.2 已将"未读绝对计数明文"列入 `push_hint` MUST NOT 清单；为避免该 MUST NOT 被本字段架空，`blind_wakeup` 下 counts **MUST NOT** 携带明文绝对未读数。counts MUST 改用以下形态之一：粗粒度布尔 badge（如"有/无新内容"）、`unread_increment` 增量，或按 Realm policy 声明粒度 **bucket 化**的未读数。**封闭默认 bucket grid（normative）**：采用 bucket 化形态时，未声明 policy grid 的实现 MUST 使用封闭默认 grid `1` / `2-5` / `6-20` / `21+`（与 [`discovery-directory.md` §3](./discovery-directory.md) member_count bucket 同为协议固定枚举，使迟滞带宽有可计算基准）。policy MAY 声明更细或更粗的自定义 grid，但 MUST 是封闭枚举（请求方收到不在 grid 内的 bucket 字符串 MUST 视作不合规并丢弃），不得使用开放 / 无界粒度——否则下方迟滞带宽公式（依赖"相邻有限 bucket 跨度"）无可计算基准。无论何种形态，counts MUST NOT 跨 `push_target_id` 关联，也不得用于在 provider 侧重建跨 Realm 累计活动画像。**边界振荡侧信道（normative）**：与 [`discovery-directory.md` §3](./discovery-directory.md) member_count bucket 同理，真实未读数在两个 bucket 边界附近抖动时，provider 反复观察 bucket 翻转可逼近精确计数。因此采用 bucket 化形态时，bucket 输出 MUST 带迟滞（hysteresis）且最小驻留时间：bucket 一旦切换，MUST 在 policy 声明或本段默认的最小驻留窗口内保持稳定，不得在边界两侧逐次 notify 即翻转；实现 MUST 仅在真实计数越过 bucket 边界并持续超过 policy 声明或本段默认的迟滞带宽后才切换输出 bucket。默认最小驻留窗口与默认迟滞带宽复用 [`discovery-directory.md` §3](./discovery-directory.md) member_count bucket 口径：最小驻留窗口 MUST ≥ max(当前通知聚合窗口、provider 可观察刷新间隔)；默认迟滞带宽 = max(2, ceil(相邻有限 bucket 跨度较小者 × 0.10))，其中 bucket"跨度"按**含端点计数**（`upper − lower + 1`）计算，与 [`discovery-directory.md` §3](./discovery-directory.md) 同口径（如 `501-2000` 跨度 = 1500）；开放上界 bucket（如 `21+`）以前一个有限 bucket 的跨度为参照基数（默认 grid 下 `6-20` 跨度 = 15，故 `21+` 参照基数 = 15）。policy MAY 声明更大的绝对值或比例，但不得低于该默认值；声明 0 或更小值 MUST 按不合规处理。`unread_increment` 与布尔 badge 形态不受 bucket 迟滞约束（前者只传增量、后者不暴露绝对量级）。 |
| `notification.devices` | object[] | required | 目标设备路由数组，`minItems=1`。**`device_id` MUST 在数组内唯一（normative）**：输入是集合而非多重集。schema 的 `uniqueItems` 只能拒绝逐字节相同的条目，因此 gateway MUST 另行拒绝仅 `push_key` 或其它字段不同、但 `device_id` 重复的请求（`schema_violation`）。该唯一性是 §5.2 响应能对输入逐项守恒的前提，也使 `gateway_status=duplicate` 只表示"此前请求已接管"，不与请求内重复混淆。 |
| `notification.devices[].device_id` | id:device | required | 目标设备的 typed device id，与 `ak.edge.push.command.register_device.v1` 注册时使用的同一 id。它与 `notification.push_target_id` 组成本次 notify 的逐项身份，§5.2 响应即以此定址；协议不存在第三套 route identity。 |
| `notification.devices[].push_key` | string | optional | 目标平台 push token。Push Gateway 已在 register_device 时持有该设备的 route，正常情况下 SHOULD 省略本字段，由 gateway 依 `device_id` 解析已注册 route；携带它只会把原始 provider token 多复制一份到 wire 上。本字段 MUST NOT 出现在任何响应中（见 §5.2）。 |
| `notification.devices[].app_id` | string | optional | 目标应用标识。 |
| `notification.devices[].platform` | string | optional | 目标平台标识，供 gateway 选择 provider adapter。 |
| `notification.devices[].visible_notification_opt_in` | boolean | optional（默认 `false`；routing-stripped） | 接收设备授权状态中的 `visible_notification` opt-in 投影。仅当 Realm policy、调用服务 visible profile 与该字段三者同时允许时，Push Gateway 才可处理本表 visible-only 字段；缺失或 `false` 时该设备 MUST 回退到 `blind_wakeup`，不得接收明文标题、发送者显示名或 typed-id preview。MUST NOT 转发给 provider。 |
| `notification.route_tokens` | object | optional（routing-stripped） | gateway-internal opaque token 集合，blind 与 visible 通知共有。第三方 Push Gateway 只可把 token 用作路由、去重、熔断和等值比较输入；token 由接收 Sync / Principal Service 生成，并绑定 `recipient_id`、Push Gateway service DID、用途、scope 与 salt epoch。其下所有字段 **MUST 在出 provider 前 strip，MUST NOT 转发给 provider**。 |
| `notification.route_tokens.realm_route_token` | string | optional（routing-stripped） | Realm 级路由 / 去重 / 熔断 token；不得是 Realm id 或可逆 Realm id 编码。 |
| `notification.route_tokens.scope_route_token` | string | optional（routing-stripped） | effective Realm / Circle scope 的 opaque token；不得携带 Circle id、`effective_scope` 对象或其它可识别 scope 原文。 |
| `notification.route_tokens.delivery_binding_frontier_token` | string | optional（routing-stripped） | federation hop 来源 notify 的 stale-route 检测 token；不得携带 raw Realm frontier。 |
| `notification.event_id` | id:event | visible-only required | profile-gated Event id。仅 visible notification 形态必填，绝不进 blind 或 provider 出向 payload。 |
| `notification.realm_id` | id:realm | visible-only required | profile-gated Realm id。仅 visible notification 形态必填，绝不进 blind 或 provider 出向 payload。 |
| `notification.sender_actor_id` | did_core_id | visible-only required | profile-gated 发送者 actor 的稳定业务身份。仅 visible notification 形态必填，绝不进 blind 或 provider 出向 payload。 |
| `notification.strand_id` | id:strand | visible-only | profile-gated Strand id。绝不进 blind。 |
| `notification.message_id` | id:message | visible-only | profile-gated Message id。绝不进 blind。 |
| `notification.sender_actor_display_name` | string | visible-only | profile-gated 发送者显示名。绝不进 blind（§2.2 已列入 MUST NOT 清单）。 |
| `notification.strand_title` | string | visible-only | profile-gated Strand 标题。绝不进 blind。 |
| `notification.realm_title` | string | visible-only | profile-gated Realm 安全边界可读标签。绝不进 blind。 |
| `notification.user_is_target` | boolean | visible-only | profile-gated：当前接收用户是否为定向目标。绝不进 blind。 |
| `notification.priority` | string | visible-only | profile-gated 优先级提示（如 `low`）。绝不进 blind。 |
| `notification.membership` | string | visible-only | profile-gated 接收用户的成员关系状态。绝不进 blind。 |
| `event_kind` | string | optional | 顶层（与 `notification` 并列）：源 Event kind（如 `ak.message.create`），供 gateway 将 Phase-P2 `ak.agent.*` 生命周期 / actor-private kind 路由为 no-fanout ack。粗粒度路由选择器，不带 Realm / sender / event 识别字段。 |
| `reason_code` | string | optional | 顶层：caller 提供的 wire-safe reason code。well-known 值 `historical_only` 标记诊断重放（非新事件），**MUST NOT** 触发新 push fanout。gateway 仍返回 200，且响应 **MUST 满足 §5.2 的逐项守恒**：`notification.devices[]` 的每个 `device_id` 恰好对应一条 `outcomes[]` 项，其 `gateway_status="duplicate"`（未产生新投递的幂等 ack），MUST NOT 返回空 `outcomes[]`。其它取值仅在操作显式定义处被接受。 |
| `audit_envelope` | object | optional | 顶层：`ak.audit.accessed` 信封路由片段（`{access_kind, late_recovery_original_event_id?}`）。present 时该请求是审计管线事件（如 `e2ee_late_recovery` 访问通知）而非 push notify：gateway 写审计事件、回 200、跳过整条 push 管线。 |

`blind_wakeup` 下上述最小化义务覆盖 `counts` 内的所有绝对活动计数，包括未读数与未接来电数；`badge` 与 `missed_call` 均只能使用布尔存在标志或 policy 声明的封闭 bucket 字符串，MUST NOT 发送明文绝对计数。`unread_increment` 是唯一允许的有界增量形态，不得被解释为累计总数。

> **传输层 header（非 body 字段）**：notify MUST 携带 exact selector `Arkret-Operation: ak.edge.push.command.notify.v1`；即使 endpoint family 当前只有该候选也不得省略。`idempotency_key`→`Idempotency-Key` header；来源服务 DID→`Source-Service-ID` header；目标服务 DID 与 `recipient_id` 复用→`Destination-Service-ID` header（均为 `httpMessageSignature` 伴随项，见 [`../sync/service-http-binding.md` §3](../sync/service-http-binding.md) 与 OpenAPI securitySchemes）。这些字段都不在 body 重复承载，且 **MUST NOT** 出现在请求体内。

**Notify body / product-private body / provider payload 三层边界（normative）**：

1. `/_arkret/edge/push/notify` 请求体只承载本节表中定义的协议字段，且由 `push-operations.schema.json#/$defs/push_notify_request_body` 的闭合 schema 约束。产品内部 UI 草稿、DND/snooze 状态、push rule 明文、provider adapter 原始字段、APNs/FCM/WebPush 私有 body、`provider_payload`、`content` 或 `content_*` preview 字段 **MUST NOT** 进入该协议 body；实现需要这些信息时，只能在调用方产品私有进程内完成求值，并把结果压缩成本节定义的 `wakeup_kind` / `push_hint` / `reason_code` / `route_tokens` 等最小协议字段。
2. Product-private body 是调用方服务内部状态，不是 Arkret v1 wire surface。它 MAY 包含本地化资源键、UI 文案模板、静默时段、snooze target 或 provider adapter 配置，但这些字段 MUST 在进入 `ak.edge.push.command.notify.v1` 前被消费或丢弃。不得通过 `notification.extra`、`content`、`payload`、`data`、`provider_payload` 或任何自由对象把 product-private body 透传给 Push Gateway。
3. Provider payload 是 Push Gateway 对 APNs / FCM / WebPush / OEM provider 的出向请求；它由 gateway 根据已验证的 notify body 重新构造。默认 `blind_wakeup` 下 provider payload 的允许集合是 `push_target_id`、`wakeup_kind`、合规的 `push_hint` / `push_hint_l10n_key`、最小化 counts 以及 provider 必需的不可链接 collapse key；`timing_profile_hint`、`route_tokens`、`reason_code`、`event_kind`、`audit_envelope` 和任何 Realm / sender / event / content 字段 MUST 在出 provider 前 strip。
4. `ak.profile.push_gateway.visible_notification.v1` 只放宽本表列出的 profile-gated 标题/标签/typed-id 字段，不引入自由正文容器。即使 Realm policy 和设备 opt-in 允许 visible notification，`notification.content`、`body`、`preview`、`summary`、provider-specific `data` 或任意 `content_*` 字段仍不属于 v1 notify body；需要完整标题与正文的客户端 SHOULD 由 blind wakeup 唤醒后本地拉取、解密并渲染。

`notification.event_id`、`notification.realm_id`（client-visible 顶层）、`notification.kind`、`notification.sender_actor_id`、`notification.sender_actor_display_name`、`notification.realm_title`、`notification.strand_title` 等识别字段 **MUST NOT** 出现在 `ak.profile.push_gateway.blind_wakeup.v1`（默认互操作隐私基线）的 payload 中。独立第三方 Push Gateway 的路由输入只能使用顶层 pairwise `push_target_id` 与 `route_tokens`；raw Realm id、Circle id、`effective_scope`、actor DID allow-list 或其它可识别路由原文不得进入 `/_arkret/edge/push/notify` wire。若某部署确实需要让受信 Push Gateway 承载可见通知，必须声明独立的 `ak.profile.push_gateway.visible_notification.v1` profile，并满足全部条件：

1. Realm policy 显式把该 Push Gateway 列入 `plaintext_visible_services`，且声明允许 `visible_notification`。
2. 接收设备在其授权状态中显式记录 `visible_notification` opt-in；未 opt-in 的设备 MUST 回退到 `ak.profile.push_gateway.blind_wakeup.v1`。
3. 客户端 UI MUST 显式向用户标示当前会话处于可见通知模式。
4. payload 不得标记为 `blind_wakeup`，conformance suite 必须按较高隐私风险 profile 测试。
5. 可见字段仍受最小化约束，不得包含正文、DID URL、跨 Realm stable correlation key、IP / geolocation 或未列入 profile 的自由文本。
6. E2EE 默认实现不得依赖该 profile；完整通知标题与正文 SHOULD 由客户端被唤醒、拉取并本地解密后渲染。
7. `visible_notification` 只放宽本表列出的展示字段，不放宽路由元数据边界；独立第三方 Push Gateway 仍只能接收 opaque route token。与 Sync / Principal Service 同一运营、日志、审计和信任边界内的 co-resident gateway 可以在实现内部使用 raw id，但这些 raw id 不属于 Arkret edge notify wire。

Matrix 互通部署 MAY 声明 `ak.profile.push_gateway.matrix_passthrough.v1` 用于桥接遗留 Matrix push gateway 形态。该 profile 与 `ak.profile.push_gateway.blind_wakeup.v1` **不兼容**：bridge MUST 把流量分区，确保任一基于默认 v1 baseline 协商的 `(recipient_id, device)` 元组永远不会收到 matrix_passthrough payload。

默认 blind wakeup 请求示例：

```json schema=schemas/push-operations.schema.json#/$defs/push_notify_request_body
{
  "notification": {
    "push_target_id": "ak:pseudonym:push:kosc9iQ4gVct1OB-b6X364WIFIsJFVbVzn7BMBs1sm8",
    "wakeup_kind": "message",
    "timing_profile_hint": "default",
    "counts": {
      "badge": "2-5",
      "missed_call": false
    },
    "devices": [
      {
        "device_id": "ak:device:0192f3a1-4c2b-7d5e-9f10-2a3b4c5d6e7f",
        "app_id": "com.arkret.client"
      },
      {
        "device_id": "ak:device:0192f3a1-4c2b-7d5e-b021-3c4d5e6f7a8b",
        "app_id": "com.arkret.client"
      }
    ]
  }
}
```

### 5.2 响应

响应对 `notification.devices[]` **逐项守恒**：每个输入 `device_id` 在 `outcomes[]` 中恰好出现一次。

```json schema=schemas/push-operations.schema.json#/$defs/push_notify_outcome
{
  "push_target_id": "ak:pseudonym:push:kosc9iQ4gVct1OB-b6X364WIFIsJFVbVzn7BMBs1sm8",
  "outcomes": [
    {
      "device_id": "ak:device:0192f3a1-4c2b-7d5e-9f10-2a3b4c5d6e7f",
      "gateway_status": "accepted"
    },
    {
      "device_id": "ak:device:0192f3a1-4c2b-7d5e-b021-3c4d5e6f7a8b",
      "gateway_status": "rejected",
      "reason_code": "push_token_unknown"
    }
  ]
}
```

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
|------|------|------|------|
| `push_target_id` | `PushTargetId` | required | 回显 `notification.push_target_id`，MUST 与请求一致。 |
| `outcomes` | object[] | required | 逐 device 的 gateway 接管结论，`minItems=1`。 |
| `outcomes[].device_id` | id:device | required | 对应 `notification.devices[].device_id`。逐项身份是 `(push_target_id, device_id)` 复合键——请求侧已经承载它，响应不引入第三套 route identity。 |
| `outcomes[].gateway_status` | string | required | 封闭枚举 `accepted` / `duplicate` / `rejected`。`accepted`=本次请求 durable 接管该 device route；`duplicate`=此前请求已接管，本次不产生新投递；`rejected`=未接管。 |
| `outcomes[].reason_code` | string | conditional | 封闭枚举，`gateway_status=rejected` 时 MUST 出现，否则 MUST 缺席。取值见下表，全部登记于 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)。 |
| `outcomes[].retry_after_ms` | integer | optional | caller 退避毫秒数。仅当 gateway 未接管且 `reason_code` 属 caller-retryable 子集时出现；它的出现是"下一次尝试归调用方"的唯一 wire 信号。 |

**守恒规则（normative）**：

- 对 `notification.devices[]` 中每个 `device_id`，`outcomes[]` 中恰有一项同 `device_id`；
- `outcomes[]` MUST NOT 出现请求中不存在的 `device_id`，MUST NOT 重复；
- **target 级失败 MUST 展开**：未知 `push_target_id`、target 级 policy 拒绝、payload 超限或 profile 不匹配等整体性失败，MUST 为请求中每个 device 各产出一条 `gateway_status=rejected` 且 `reason_code` 相同的 outcome。请求已携带完整 `devices[]`，展开总是可计算，因此协议不定义第二种响应形状，也不设可选定址字段。

**两阶段责任（normative）**：

1. `gateway_status ∈ {accepted, duplicate}` 表示 Push Gateway 已 durable 接管该 device route。此后 provider 侧的 429、临时失败与重试**由 gateway 负责**，调用方 MUST NOT 因 provider 失败重发该 device。
2. `gateway_status=rejected` 表示未接管。只有登记为 caller-retryable 的 reason 才可携带 `retry_after_ms`；其余 rejection 是 terminal，重发同一请求不会改变结果。
3. provider 侧的 pending / accepted / rejected / expired 属于接管之后的 delivery state，由 gateway 内部推进，**不进入本同步响应**。
4. provider 状态更新 MUST NOT 反向改写首次 gateway 接管结论。

`reason_code` 取值与责任归属：

| `reason_code` | 层级 | 调用方动作 |
|---|---|---|
| `push_target_unknown` | target（展开到全部 device） | terminal；停止对该 target 的 notify。 |
| `push_payload_too_large` | target（展开到全部 device） | terminal；缩减 payload 后才可重试。 |
| `unsupported_profile` | device | terminal；该设备未 opt-in 所请求的通知 profile，改用 blind 形态。 |
| `delivery_binding_stale` | device | terminal；接收方 delivery-binding frontier 已推进，route 过期，需重新解析。 |
| `push_token_unknown` | device | terminal；**SHOULD 移除该设备注册**。 |
| `push_token_invalid` | device | terminal；**SHOULD 移除该设备注册**。 |
| `push_gateway_unreachable` | device | **caller-retryable**，按 `retry_after_ms` 重试。 |
| `rate_limited` | device | **caller-retryable**，按 `retry_after_ms` 重试。 |

注册清理由 `(push_target_id, device_id)` 定址。响应 **MUST NOT** 回传 `push_key`、`app_id`、provider message id、provider 私有 body 或原始 push token 的任何 hash——把原始 provider token 回送给调用方与 §5.1 / §6.2 对路由输入必须 opaque 的约束方向相反，且逐项身份已足以定位注册。

**幂等（normative）**：

- exact replay MUST 返回与首次相同的 `outcomes[]`（同 `device_id` 同 `gateway_status`）；
- 同一 `Idempotency-Key` 配不同 body MUST 返回 `duplicate_conflict`；
- 已 durable 接管的 device MUST NOT 因 provider 仍 pending 而要求调用方再次提交。

守恒、展开、责任分层与幂等的可执行向量为 `ak.vector.push.notify_outcome_conservation.v1`（见 [`../conformance/conformance-vectors.md` §10.12.1](../conformance/conformance-vectors.md) 与 [`push-notify-outcome-fixture.json`](../../artifacts/fixtures/push-notify-outcome-fixture.json)）。其中"遗漏 / 重复 / 未请求 device / 回显不符"四条负例通过 JSON Schema 但 MUST 被 verifier 判为 `schema_violation`——守恒是 JSON Schema 无法表达的跨字段不变式。

## 6. E2EE 场景下的推送

### 6.1 脱敏推送流程

1. Alice 发送加密消息到 Realm S
2. Alice 的客户端不在 Event 明文元数据中附加 sender / Realm 可识别 `push_hint`；若需要提示，只能使用 `push_hint: "new_message"` 或 `l10n_key`
3. Principal Server sync surface 收到 Event，匹配推送规则
4. Principal Server sync surface 向 Bob 的推送网关发送 `blind_wakeup` 通知（只含 `push_target_id`、`wakeup_kind`、`timing_profile_hint`、可选计数和 opaque route token）
5. Bob 的设备收到推送，唤醒客户端
6. 客户端从 Principal Server sync surface 拉取加密 Event 并解密
7. 客户端在本地展示完整的消息内容

### 6.2 安全约束

- Principal Server sync surface MUST NOT 在推送中包含 `encrypted_content` / `encrypted_metadata` / `encrypted_payload` 的任何部分
- 推送网关被视为不可信第三方：`push_hint` 的白名单约束与 payload 最小化约束见 §2.2 与 §5.1，均为 MUST / MUST NOT，本节不重复其规范内容
- 独立 Push Gateway 的路由输入 MUST 是 opaque token：`route_tokens` 不得包含、编码或可逆推出 DID、Realm id、Circle id、Event id、Message id、Strand id、handle、平台 push token 或长期稳定 correlation key。v1 不存在 mention redirect token；mention 走 blind/batch wakeup 并由客户端解密判断。

## 7. 静默时段 (Do Not Disturb)

用户可以配置静默时段：

```json
{
  "dnd": {
    "enabled": true,
    "schedule": {
      "timezone": "Asia/Shanghai",
      "tzdb_version": "2025b",
      "all_day": false,
      "periods": [
        { "start": "22:00", "end": "08:00" }
      ]
    },
    "exceptions": ["content.keyword-urgent"]
  }
}
```

在静默时段内，只有 `exceptions` 列表中的规则可以触发推送。

`ak.dnd_schedule` 解密后的 plaintext MUST 通过
`dnd-schedule.schema.json`（schema id `ak.schema.dnd_schedule.v1`）及下列语义校验：

- 根对象必须且只能含 `dnd`；`enabled`、`schedule`、`exceptions` 与 schedule 的四个字段均为必填，
  consumer 不得接受省略字段、未知字段或直接把内层 `dnd` 当根对象的旧写法。
- `timezone` MUST 是大小写精确的 canonical IANA zone name；`local`、缩写和 alias 均非法。v1 的
  `tzdb_version` 固定为 `2025b`，producer 与 consumer 必须使用相同版本；版本不匹配按整个值非法处理，
  不得用系统时区数据库猜测。
- period 时间只能是零填充 `HH:MM`，表示该 timezone 下的 recurring wall-clock minute。每段采用半开
  `[start,end)`；`start > end` 表示跨午夜，`start == end` 非法。全天静默只能写
  `all_day=true, periods=[]`；`all_day=true` 与非空 periods 不得并存。
- `periods` MUST 按 `start` 的分钟值严格升序，任意两段不得相交、重复或相邻；producer MUST 先合并
  相邻/相交段后再写入。consumer 必须拒绝非 canonical 列表，不得按输入顺序覆盖或静默归一化。
- 求值先把当前 instant 按声明的 timezone/tzdb 转为本地 wall-clock minute，再测试半开区间。DST gap
  中不存在的分钟不触发；fold 中重复出现的分钟在两次出现时都按同一 period 结果求值。
- 收到无法解密、schema 非法、tzdb 不匹配或语义非法的新值时，客户端 MUST 保留最近一次已经验证的值，
  并向用户暴露可修复错误；首次读取即非法且没有历史有效值时，按“未配置 DND”求值。DND 是可用性偏好而非
  授权边界，v1 不允许损坏数据造成无限期全局静默。

`exceptions` MUST 按 code-point 升序排列且不得重复；仅与最终命中的 `rule_id` 精确相等时例外生效。
上述正例、边界、DST 与异常恢复由 `ak.vector.dnd.schedule_boundary_validation.v1` 覆盖。

## 8. v1 互操作要求

- 推送规则的跨设备同步使用私有加密 Account Data；规则变更 MUST 由 holder device 签名，未授权服务不得读取敏感关键词或联系人规则。
- Delivery Receipt 只能表示推送网关或平台尝试投递，不等于用户已读。已读状态仍由 read cursor / read receipt profile 表达。Delivery Receipt 属于 gateway 接管**之后**的 provider 投递阶段，**MUST NOT** 出现在 `ak.edge.push.command.notify.v1` 的同步响应中（见 §5.2）；v1 也未定义把它暴露给调用方的 canonical rail。若某部署需要该能力，MUST 另行定义独立的 query/stream operation 并裁决其定址、保留期、可见性与不可枚举要求，不得借 notify 响应或私有扩展字段承载。
- 语音/视频通话推送使用 `ak.call.signal` 的 invite hint；payload MUST NOT 包含 SDP、ICE candidate、TURN credential 或明文会议标题，除非 Realm policy 明确允许。
- Push Gateway 高可用不得通过共享长期 device token 实现。多网关部署 MUST 使用 service DID、短期授权、token 分片或 per-gateway registration，并支持撤销。
