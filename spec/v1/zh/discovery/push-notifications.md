---
title: Push Notifications
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

去中心化协作协议中，用户的客户端不可能永远在线监听 Sync Service 的 Sync Stream。当用户离线时，协议需要一套标准化的**推送通知机制**，将重要事件及时送达用户的移动设备或桌面系统。

本规范定义了：
- 推送规则引擎：用户可自定义哪些事件触发推送
- 推送网关接口：标准化的第三方推送投递协议
- E2EE 场景下的隐私保护推送

## 2. 设计原则

### 2.1 推送由 Sync Service 或受托通知服务触发

客户端在离线前向 Sync Service 注册推送设备信息。此后由 Sync Service 或 Realm policy 明确授权的通知服务在收到匹配推送规则的事件时，向推送网关 (Push Gateway) 发送通知。

### 2.2 推送内容脱敏 (Blind Wakeup)

Blind wakeup **不是可选 extension**，而是 push gateway 的**默认互操作安全基线**：声明 `cx.profile.push_gateway.v1` 的实现 MUST 同时声明 `cx.profile.push_gateway.blind_wakeup.v1` 并在所有 provider 出向通知上强制其约束。可见通知字段只在显式声明 `cx.profile.push_gateway.visible_notification.v1` 且满足 Realm policy + 设备 opt-in + UI 明示三项前置时才允许，且仍受最小化约束（见 [`conformance/conformance-profiles.md` §11](../conformance/conformance-profiles.md)）。Matrix 兼容部署使用 `cx.profile.push_gateway.matrix_passthrough.v1`，**MUST NOT** 与默认 v1 隐私基线在同一 `(recipient_service_did, device)` 元组上混用。

在 E2EE 场景下，Sync Service 无法读取消息正文。推送通知的默认行为是**脱敏唤醒 (Blind Wakeup)**：
- 推送上游（APNs / FCM / Push Gateway）只携带 **per-(recipient_service_did, principal, device, push_route) pairwise pseudonym** `push_target_id` 与最小唤醒提示（`wakeup_kind` 等），不得携带 principal DID、sender DID、Realm id、event id、device DID URL 或任何其它跨 Realm 稳定标识。具体规则见 [`crypto-media/device-lifecycle.md` §5a Privacy-Preserving Push](../crypto-media/device-lifecycle.md)。同一 DID 在个人 Principal Server 与组织 Principal Server 上的推送注册必须不可链接。
- `push_target_id` 派生 MUST 使用接收服务私有 secret salt / pepper：`HMAC-SHA256(service_push_secret[salt_epoch_id], canonical_json({recipient_service_did, principal_id, device_id, push_route_id, salt_epoch_id}))`，再编码为不含 DID / Realm / device 原文的 pseudonym。`service_push_secret` 原值绝不能上 wire；`cx.server.describe.privacy_derivation.push_target_id` 只发布 `derivation_profile`、`salt_epoch_id`、`salt_rotation_seconds` 和输入绑定元数据，供客户端和 conformance 工具确认不同 Principal Server / 组织 / push route 不会复用同一可链接命名空间。
- 客户端被唤醒后自行从 Sync Service 拉取并解密实际内容；本地通知文案在客户端解密后生成。
- **`push_hint` 即使在 `plaintext_visible_services` 下也 MUST 受白名单约束**：受信通知服务 MAY 附加 `push_hint` 字段，但其 wire 形态 MUST 仅限以下封闭枚举字段——`wakeup_kind`（粗粒度类别，如 `message`/`mention`/`reaction`/`call_invite`）、`badge_count`（数字徽章计数）、`unread_increment`（增量计数）、本地化字符串 token（`l10n_key`，由客户端在解密后渲染）。**MUST NOT** 携带：正文（任何形态）、sender DID 或 handle、principal_id、Realm id / 名称 / 头像、Flow id / 名称、Space id / 名称、Message id、reaction emoji 实际值、附件文件名、stable correlation key、IP / geolocation。`plaintext_visible_services` 是"允许接收明文"的授权而非"放行 metadata"的授权——push gateway 即使被授权也不得变成跨 Realm 行为追踪点。违反此约束的推送实现 MUST 在 conformance lint 中标记为不合规。

- **Sync Service 转发也必须执行同一白名单**：Sync / notification service 在调用 `/api/v1/push/notify` 前 MUST 校验将要转发给 Push Gateway 的字段集合。默认 `blind_wakeup` profile 下，超出 §5.1 枚举字段的 metadata MUST 被 strip，并写入最小化 audit 记录；若字段属于 event / realm / sender 识别字段且未满足 `visible_notification` profile gate，服务 MUST 拒绝该通知或降级为 blind wakeup，不得原样转发。

### 2.3 用户完全控制推送规则

推送规则是 Actor-private 的配置，存储在用户自己的加密 account data 中。用户有权关闭任何 Realm 的推送、设置静默时段、自定义关键词触发等。

### 2.4 多订阅信道去重与 presence timing

同一事件可能同时命中显式 watch、隐式参与订阅、mention rule、read-cursor badge recompute、presence-triggered foreground wakeup 或 notification projection。Sync Service / notification service 在调用 Push Gateway 前 MUST 在出口做去重：同一 `(recipient_service_did, device_id, push_route_id, source_event_digest)` 在一个 delivery window 内最多产生一条 push wakeup。默认 `blind_wakeup` profile 下，去重 key 是服务端内部状态，MUST NOT 出现在 push payload、日志导出、provider custom data 或客户端可见的 stable correlation key 中。

Presence 不得作为精确 push timing oracle。服务端把 presence update、watch recompute 与 push activation 组合使用时，MUST 至少按 Realm policy 声明的 bucket 粒度（默认不小于 60s；高隐私部署 SHOULD 使用 5min 或更粗）批处理或延迟；不得在用户刚上线 / 刚离线的瞬间立即发出可被 provider 观察到的 per-event push burst。该规则不阻止本地客户端在已在线连接上立即显示通知；它只约束第三方 push provider 可见的出向时序。

## 3. 推送设备注册

### 3.1 注册接口

客户端在上线时 SHOULD 向 Sync Service 注册推送设备：

```
POST /api/v1/push/register-device
```

请求示例（非完整 schema）：

```json
{
  "device_id": "did:web:alice.example.com#device-phone",
  "push_gateway": "https://push.example.com/api/v1/push/notify",
  "push_key": "fcm:eJx9k2...",
  "platform": "android",
  "app_id": "com.contrix.client",
  "display_name": "Alice's Pixel 9"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `device_id` | string | MUST | 设备 DID 片段标识 |
| `push_gateway` | string | MUST | 推送网关的 URL |
| `push_key` | string | MUST | 设备在推送平台上的注册令牌 |
| `platform` | string | SHOULD | `android`, `ios`, `web`, `desktop` |
| `app_id` | string | SHOULD | 应用的包名 / Bundle ID |
| `display_name` | string | MAY | 用户可读设备名 |
| `client_rule_digest` | `sha256:<hex>` | optional | 客户端本地通知规则 canonical digest。Sync Service 不读取规则明文，只可把该 digest 与 Realm policy 允许的 server-side hint 组合，用于减少无差别 wakeup。 |

Push registration 的作用域是接收该请求的 Sync Service / Principal Server service DID。客户端在个人 Principal Server 与组织 Principal Server 上同时登录同一 DID 时，MUST 分别注册互不相关的 push route / `push_target_id`；服务端不得把一个上下文中的 push token 或伪名复制到另一个上下文。实现若在请求中扩展携带 `recipient_service_did`，其值 MUST 与目标服务的 `cx.server.describe.service_did` 一致。

响应字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ok` | boolean | required | 注册是否被接受 |
| `registration_id` | id | optional | 服务端分配的注册 ID |
| `expires_at` | datetime | optional | 注册或 push token 的过期时间 |

### 3.2 注销接口

```
POST /api/v1/push/unregister-device
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `device_id` | id | required | 要注销的设备 ID |
| `push_key` | string | optional | 指定要注销的 push token |
| `app_id` | string | optional | 指定应用包名 / Bundle ID |

响应字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ok` | boolean | required | 注销是否完成；不存在的注册 MAY 幂等返回成功 |

## 4. 推送规则引擎

### 4.1 规则结构

推送规则按优先级从高到低排列，第一条匹配的规则决定推送行为：

```json
{
  "rules": [
    {
      "rule_id": "override.mute-realm-x",
      "kind": "override",
      "enabled": true,
      "conditions": [
        { "kind": "field_match", "field": "realm_id", "pattern": "cx:realm:9bd39a00-0000-7000-8000-000000000000..." }
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
        { "kind": "field_match", "field": "type", "pattern": "cx.message.create" },
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

| Condition Kind | 评估位置 | 说明 |
|---------------|---------|------|
| `field_match` | server-side | Event 明文元数据或授权可见 payload 字段匹配给定 pattern（支持 glob） |
| `contains_keyword` | client-side（E2EE）/ server-side（cleartext Realm）| 消息 `body` 中包含指定关键词。E2EE Realm 中 server 不能解密正文 → 必须降级，见 §4.5 |
| `mentions_actor` | client-side（E2EE）/ server-side（cleartext Realm）| 消息中提及当前 Actor。E2EE Realm 中 mention relation 通常嵌入密文 → 见 §4.5 |
| `is_direct_message` | server-side | 来自 1 对 1 私聊 Realm（可由 Realm metadata 或成员数判断，不需要解密）|
| `member_count` | server-side | Realm 成员数满足条件（如 `<= 5`），可由 metadata 判断 |
| `flow_track` | server-side | Event 关联的 Flow track 名匹配给定 pattern（如 `synthesis`、`discussion`，支持 glob）。Track 名是 Flow 的公开配置 metadata，不属于 E2EE 正文 → server 端可在不解密内容的前提下评估 |
| `watch_state` | server-side | Event 关联 Flow 的 receiver-side watch level 匹配给定 pattern（取值 `mentions_only` / `participating` / `all` / `muted`，支持 glob 与多值数组）。watch level 来自 receiver 自己的 watch cell + 隐含订阅（[`../models/flow-and-message.md` §8.7](../models/flow-and-message.md)）；cell value 由 server 直接读取，无 E2EE 降级。`muted` MUST 收敛到 `dont_notify`，实现路径见 §4.3.2 |

每条 rule MUST 在 wire 上声明其 `evaluation_locus` 为 `server` 或 `client`。Sync Service 只在 `server` rule 上做匹配；`client` rule 的语义由本节 §4.5 定义的降级流程承担。

#### 4.3.1 `flow_track` 与 per-track 通知

Track 不持有独立 membership / 权限（见 [`../models/flow-and-message.md` §4](../models/flow-and-message.md)），但用户对不同 track 的关注度不同——例如想接收某个 Flow 的 `synthesis` 全部更新，但 `discussion` 只关心 @ 自己。`flow_track` condition 用于在通知层表达这种偏好，不影响访问控制。

**`track_name` 的派生**（server-side，由 Sync Service 在规则匹配前从 Event 推导，**不是** 一个客户端在 wire 上自由设置的字段）：

- Event payload 显式引用 Flow（如 `cx.message.create` 携带 `flow_id`，或 `cx.flow.update` 直接作用于 Flow）→ 按 Event 类型映射：
  - `cx.message.create` / `cx.message.revise` / `cx.message.redact` / `cx.reaction.add` / `cx.reaction.remove` 在 Flow 的 discussion timeline 中产生 → `track_name = "discussion"`
  - `cx.flow.update`（修改 Flow synthesis 字段、状态、标题等）→ `track_name = "synthesis"`
  - `cx.flow.create` / `cx.flow.archive` / `cx.flow.restore` / `cx.flow.move` / `cx.flow.reorder` → `track_name = "synthesis"`（生命周期与位置变更归入 synthesis 视角，便于过滤）
  - `cx.flow.tracks.update`（track 配置 / primary / enabled 变更）→ patch 影响的每个 track key 各派生一条 `track_name`；同时影响多个 track 时 server 派生 set，`flow_track` pattern 匹配任一即匹配
  - `cx.flow.watch.set` → `track_name` 不派生（watch 是个人偏好，不属于任一 track 时间线）；`flow_track` condition 视为不匹配
- Event 不属于任何 Flow（普通 Realm 消息）→ `flow_track` condition 视为不匹配（既不为真，也不报错）；用户希望覆盖普通 Realm 消息时应使用 `field_match` on `realm_id` 而非 `flow_track`
- Flow 设置了 `scope_circle_id` 指向 Circle → Flow 的所有 track（含 discussion）的 `cx.message.*` 落在该 [Circle](../models/circle.md) scope；server MUST 按 §3.8 投递不变量校验通知 receiver 属于该 Circle 成员集合，否则 MUST `dont_notify` 并不暴露该 Flow 的存在性（与 [`../models/circle.md` §9.3](../models/circle.md) 一致）。

`flow_track` MUST NOT 携带任何正文或 mention 信息进入推送 payload；它只参与 server-side 规则匹配并影响 `notify` / `dont_notify` 的最终决定。在 E2EE Realm 中，由于 track name 是公开 Flow 配置（非密文），此条件不需要 §4.5 的降级流程，仍按 `evaluation_locus: server` 评估。

示例（synthesis 全收，discussion 仅 mention 自己）：

```json
[
  {
    "rule_id": "underride.flow-synthesis-all",
    "kind": "underride",
    "enabled": true,
    "evaluation_locus": "server",
    "conditions": [
      { "kind": "flow_track", "pattern": "synthesis" }
    ],
    "actions": ["notify"]
  },
  {
    "rule_id": "underride.flow-discussion-mention-only",
    "kind": "underride",
    "enabled": true,
    "evaluation_locus": "client",
    "conditions": [
      { "kind": "flow_track", "pattern": "discussion" },
      { "kind": "mentions_actor" }
    ],
    "actions": ["notify", "highlight"]
  }
]
```

第二条规则把 `mentions_actor` 与 `flow_track` 复合：在 cleartext Realm 中 server 直接评估；在 E2EE Realm 中 server 看到 `flow_track=discussion` 但无法解密 mention，按 §4.5 走 client-side 降级——即按 Realm 级 `wakeup_default` 与设备 `client_rule_digest` 选择是否 blind wakeup，client 解密后再决定是否进入用户感知通知 surface。规则书写者无需手动区分两种 Realm，`evaluation_locus: client` 已经声明了降级路径。

#### 4.3.2 `watch_state` 与订阅偏好

`watch_state` condition 用 receiver 的 watch level（[`../models/flow-and-message.md` §8](../models/flow-and-message.md)）做 server-side 匹配。Watch level 由 Sync Service 直接读取 receiver 在该 Flow 的 watch cell + 隐含订阅集合（assigned_to / self-posted），不需要解密正文，因此即使在 E2EE Realm 也是 `evaluation_locus: server`。

**两层职责**：

- **Watch level 决定"通知是否发生"**：Sync Service 在派发前解析 receiver effective level（含 §8.7 隐含订阅、`muted` 覆盖）。effective level 为 `mentions_only` 且当前 Event 不是 mention / assigned / reply 等定向事件时，结果为 `dont_notify`。
- **Push rule 决定"通知如何投递"**：在 watch level 允许通知发生的前提下，push rule 决定提示音、是否高亮、是否进 DND 例外等。

**`muted` 强约束的实现自由度**：`watch_state=muted` MUST 收敛到 `dont_notify`，但实现可以在以下三种等价路径中任选：

- (a) **Pre-engine short-circuit**：在引擎评估前直接判定 `dont_notify`，跳过整条 rule chain；
- (b) **Built-in deny rule**：在 rule chain 最高优先级位置注入系统内置 deny rule（actor 不可写、不可禁用），由引擎匹配；
- (c) **User-declared override rule**：用户手动写一条 `override.respect-mute` 规则，由引擎匹配。

三种路径在 dispatch 输出上**不可区分**。实现 SHOULD 在 dispatch decision log 中标注 `muted_short_circuit=true` 便于排错。Sync Service 即使没有任何用户规则也 MUST 保证 muted 收敛——(a) 或 (b) 是默认实现路径，(c) 仅为可选的"可见性增强"。

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
    "evaluation_locus": "server",
    "conditions": [
      { "kind": "watch_state", "pattern": "muted" }
    ],
    "actions": ["dont_notify"]
  },
  {
    "rule_id": "underride.watching-all",
    "kind": "underride",
    "enabled": true,
    "evaluation_locus": "server",
    "conditions": [
      { "kind": "watch_state", "pattern": ["participating", "all"] }
    ],
    "actions": ["notify"]
  }
]
```

`override.respect-mute` 在实现走 (a) / (b) 路径时是冗余声明（引擎前已短路 / 已被系统规则匹配），但 wire 上合法，用于让 dispatch trace 在审计视图中显式记录 `matched_rule="override.respect-mute"`。两种写法 dispatcher 输出一致。

### 4.4 动作类型 (Actions)

| Action | 说明 |
|--------|------|
| `notify` | 发送推送通知 |
| `dont_notify` | 不发送推送（静音） |
| `sound_default` | 使用默认提示音 |
| `sound_critical` | 使用紧急提示音 |
| `highlight` | 在客户端标记为高亮 |

### 4.5 E2EE Realm 中的规则降级

E2EE Realm 中，Sync Service 不持有正文密钥，无法在 server 端评估 `contains_keyword` 或基于 mention 文本 / mention relation 嵌入密文时的 `mentions_actor`。**实现 MUST NOT** 在 E2EE Realm 静默把这类规则视为不匹配（这会让被 mention 的人收不到推送，造成 UX 退化），也 MUST NOT 把它视为匹配（这会变成无差别推送，泄露元数据）。降级路径如下：

1. **明确分类**：每条 push rule 在创建时 MUST 通过 `evaluation_locus ∈ {server, client}` 声明评估位置。client-side rule 在 E2EE Realm 中由本机已解密 Event 的 client 评估，并在本地决定是否触发本机通知通道（系统 banner、桌面提示、声音）。Sync Service 不参与 client-side rule 的匹配。
2. **Server fallback notify**：E2EE Realm 中，针对 client-side rule，Sync Service MUST 走 Realm policy 声明的保守 wakeup 策略。`wakeup_default` 取值为 `wakeup_for_all_messages` / `batch_wakeup` / `no_notification`，缺省为 `batch_wakeup`；高隐私、minimal-metadata 与 audited Realm SHOULD 使用 `no_notification` 或 `batch_wakeup`。客户端被唤醒后本地解密、本地评估 client-side rule，再决定显示哪个通知 surface（普通 banner / 高亮 banner / 静默处理）。若 `wakeup_default=no_notification`，server 不得因为无法解密 client-side rule 而单独唤醒，只能等待客户端下次 sync 或命中 server-side opaque routing token。
3. **降级标记**：Sync Service 在 push payload 中携带 `evaluation_locus_unresolved=true`，让客户端知道"我已经被 wakeup 但匹配尚未在 server 端确定"。客户端 MUST 完成本地评估后才决定是否进入用户感知的通知 surface；不得仅凭 wakeup 就在 system tray 弹出。
4. **明文 hint 限制**：E2EE Realm 中，`push_hint` MUST NOT 包含会让 push gateway 间接获得规则匹配信息的字段（例如 "matched_keyword: 'urgent'"）。默认 `blind_wakeup` 下，hint 只能携带固定枚举字段（`new_message` / `incoming_call` / `mention_self`）或 `l10n_key`，不能携带匹配到的具体内容。即使 Realm policy 把 push gateway 列入 `plaintext_visible_services`，也只允许进入 §5.1 的 `visible_notification` profile；不得把该授权解释为放宽 `blind_wakeup` 的 metadata 限制。
5. **限速降级**：E2EE Realm + client-side rule 多的 client 在高消息量场景会被持续 wakeup，电池负担显著。客户端 MUST 暴露 `aggressive_wakeup_threshold`（默认每 60 秒 ≤ 30 次）；超过阈值后切换到批量 wakeup 模式，Sync Service 把多个 wakeup 合并为单个 batch wakeup（仍携带 `evaluation_locus_unresolved=true`），客户端醒来一次评估全部待处理 Event。Realm policy MAY 要求所有设备注册 `client_rule_digest`；digest 不匹配或缺失时，server 只能按 `wakeup_default` 的更保守结果处理，不得猜测规则内容。
6. **`mentions_actor` 通过 mention sidecar 提示**（可选，使用 keyed HMAC 形态）：严格 E2EE 默认走第 1-5 步 blind / batch wakeup。若 Realm policy 允许 `mention_routing_hint="recipient_registered_token"`，且被提及接收方已经为当前 `(realm_id, mls_group_id, epoch, pairwise_or_principal_id)` 向 Sync Service 注册 opaque routing token，发送者的客户端 MAY 把 mention 列表的 keyed HMAC 标签作为明文 sidecar 字段附在 Event 元数据上，定义为:

    ```text
    mention_routing_hmac_v2 =
        HMAC-SHA256(
            key   = MLS-Exporter("contrix-mention-routing-v2", context = realm_id, length = 32),
            data  = utf8(mentioned_did)
        )
    ```

    其中 `MLS-Exporter` 即 MLS RFC9420 §8.5 `MLS-Exporter(label, context, length)`,使用当前 group epoch 的 exporter secret 派生。**Sync Service MUST NOT 派生、接收或持久化 MLS exporter secret**。接收方设备在本地按相同公式为自己的 DID 派生 token，并只把 opaque token、epoch、过期时间和目标推送通道注册给 Sync Service；服务端只做 sidecar tag 与已注册 opaque token 的等值比较。未注册 token、token 过期或 Realm policy 未允许时，服务端 MUST 回退到第 1-5 步 blind / batch wakeup。

    **安全属性**:
    - key 取自 MLS exporter secret,**不在群外可知**;Sync Service 即便获得 `realm_id` / `mls_group_id` / `epoch` / 完整成员名单也无法离线枚举 `mentioned_did → tag` 的字典(没有 exporter secret 即无 key)——关闭了对该字段的 server-side 字典枚举侧信道。
    - 服务端可见的剩余信息仅限于"某个已注册 opaque token 在该 epoch 命中 N 次"。这是接收方 opt-in 的通知路由泄露，不是发送方单方开启的能力；minimal-metadata Realm 与 audited E2EE Realm MUST 默认关闭。
    - tag 仍随 epoch 自然失效(exporter secret 跨 commit 必变);跨 epoch 重放无法命中。
    - 同一 epoch 内同一 mentioned_did 的 tag 仍恒定 — 是 opaque token 等值比较能工作的前提；若部署不能接受该频次泄露，MUST 关闭 token 注册并使用 blind wakeup。
    - 非 E2EE Realm 不使用 routing tag(直接看 plaintext mention 列表)。

    启用与否由 Realm policy 中 `mention_routing_hint` 与接收方 token 注册共同决定。minimal-metadata Realm 与 audited E2EE Realm 默认关闭；其他 E2EE Realm 未声明时默认关闭，除非接收方显式 opt-in 注册 token。关闭时 mention 走 §4.5 第 1-5 步降级,Sync Service 不做 `mentions_actor` server-side 匹配。

明确禁止：

- 实现 MUST NOT 在 E2EE Realm 中把 `contains_keyword` rule 提示让 Sync Service 持有 keyword 列表（即使加 hash）。Keyword 比 mention 高熵——hash 可被字典爆破。
- 实现 MUST NOT 通过"让客户端把解密结果回传 Sync Service 完成匹配后再发推送"的形式实现 server-side rule。这条路径等于把客户端解密能力委托给 Sync Service，违反 E2EE 边界。

## 5. 推送网关接口 (Push Gateway API)

### 5.1 通知推送

Sync Service 在触发推送规则后，向推送网关发送通知：

```
POST /api/v1/push/notify
```

请求字段（默认 `blind_wakeup` profile；该 profile 永远不得携带 Realm / sender / event 识别字段）：

| 字段 | 类型 | 必填 | 说明与约束 |
|------|------|------|------|
| `notification` | object | required | 推送通知对象。 |
| `notification.push_target_id` | string | required | per-(recipient_service_did, principal, device, push_route) pairwise pseudonym（见 [`crypto-media/device-lifecycle.md` §5a](../crypto-media/device-lifecycle.md)）。MUST NOT 是 principal DID、device DID URL、handle 或可跨 Realm / Principal Server 上下文关联的稳定 ID。 |
| `notification.wakeup_kind` | string | required | 粗粒度唤醒类别，封闭枚举 `message` / `mention` / `reaction` / `call_invite`（与 §2.2 一致）；只是粗粒度提示，不带 Realm / sender 信息。 |
| `notification.push_hint` | string | optional | 受信通知服务提供的脱敏提示，与 `wakeup_kind` 是不同字段：`blind_wakeup` 下其封闭枚举为 `new_message` / `incoming_call` / `mention_self`（见 §4.5），或 `l10n_key` token；不得包含正文、sender DID / handle、Realm id / 名称、Flow / Message id、reaction 实际值或 stable correlation key。 |
| `notification.counts` | object | optional | 未读数、未接来电数等计数。 |
| `notification.devices` | object[] | required | 目标设备数组。 |
| `notification.devices[].push_key` | string | required | 目标平台 push token。 |
| `notification.devices[].app_id` | string | optional | 目标应用标识。 |

`notification.event_id`、`notification.realm_id`、`notification.kind`、`notification.sender_actor_id`、`notification.sender_actor_display_name`、`notification.realm_title`、`notification.flow_title` 等识别字段 **MUST NOT** 出现在 `cx.profile.push_gateway.blind_wakeup.v1`（默认互操作隐私基线）的 payload 中。若某部署确实需要让受信 Push Gateway 承载可见通知，必须声明独立的 `cx.profile.push_gateway.visible_notification.v1` profile，并满足全部条件：

1. Realm policy 显式把该 Push Gateway 列入 `plaintext_visible_services`，且声明允许 `visible_notification`。
2. 接收设备在其授权状态中显式记录 `visible_notification` opt-in；未 opt-in 的设备 MUST 回退到 `cx.profile.push_gateway.blind_wakeup.v1`。
3. 客户端 UI MUST 显式向用户标示当前会话处于可见通知模式。
4. payload 不得标记为 `blind_wakeup`，conformance suite 必须按较高隐私风险 profile 测试。
5. 可见字段仍受最小化约束，不得包含正文、DID URL、跨 Realm stable correlation key、IP / geolocation 或未列入 profile 的自由文本。
6. E2EE 默认实现不得依赖该 profile；完整通知标题与正文 SHOULD 由客户端被唤醒、拉取并本地解密后渲染。

Matrix 互通部署 MAY 声明 `cx.profile.push_gateway.matrix_passthrough.v1` 用于桥接遗留 Matrix push gateway 形态。该 profile 与 `cx.profile.push_gateway.blind_wakeup.v1` **不兼容**：bridge MUST 把流量分区，确保任一基于默认 v1 baseline 协商的 `(recipient_service_did, device)` 元组永远不会收到 matrix_passthrough payload。

默认 blind wakeup 请求示例：

```json
{
  "notification": {
    "push_target_id": "cx_push_pseudo_01js0pt0000000000000000000",
    "wakeup_kind": "message",
    "counts": {
      "unread": 5,
      "missed_calls": 0
    },
    "devices": [
      {
        "push_key": "fcm:eJx9k2...",
        "app_id": "com.contrix.client"
      }
    ]
  }
}
```

### 5.2 响应

```json
{
  "rejected": []
}
```

响应字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `rejected` | object[] | required | 已失效、无权限或无法投递的 push token 摘要。 |

`rejected` 数组包含已失效的 `push_key`，Sync Service SHOULD 移除这些设备的注册。

## 6. E2EE 场景下的推送

### 6.1 脱敏推送流程

1. Alice 发送加密消息到 Realm S
2. Alice 的客户端不在 Event 明文元数据中附加 sender / Realm 可识别 `push_hint`；若需要提示，只能使用 `push_hint: "new_message"` 或 `l10n_key`
3. Sync Service 收到 Event，匹配推送规则
4. Sync Service 向 Bob 的推送网关发送 `blind_wakeup` 通知（只含 `push_target_id`、`wakeup_kind`、可选计数和设备路由字段）
5. Bob 的设备收到推送，唤醒客户端
6. 客户端从 Sync Service 拉取加密 Event 并解密
7. 客户端在本地展示完整的消息内容

### 6.2 安全约束

- Sync Service MUST NOT 在推送中包含 `encrypted_payload` 的任何部分
- `push_hint` 是发送方自愿提供的可选字段，接收方不应完全信任其内容
- 推送网关应被视为不可信第三方，推送内容应尽量最小化

## 7. 静默时段 (Do Not Disturb)

用户可以配置静默时段：

```json
{
  "dnd": {
    "enabled": true,
    "schedule": {
      "timezone": "Asia/Shanghai",
      "periods": [
        { "start": "22:00", "end": "08:00" }
      ]
    },
    "exceptions": ["override.keyword-urgent"]
  }
}
```

在静默时段内，只有 `exceptions` 列表中的规则可以触发推送。

## 8. v1 互操作要求

- 推送规则的跨设备同步使用私有加密 Account Data；规则变更 MUST 由 holder device 签名，未授权服务不得读取敏感关键词或联系人规则。
- Delivery Receipt 只能表示推送网关或平台尝试投递，不等于用户已读。已读状态仍由 read cursor / read receipt profile 表达。
- 语音/视频通话推送使用 `cx.call.signal` 的 invite hint；payload MUST NOT 包含 SDP、ICE candidate、TURN credential 或明文会议标题，除非 Realm policy 明确允许。
- Push Gateway 高可用不得通过共享长期 device token 实现。多网关部署 MUST 使用 service DID、短期授权、token 分片或 per-gateway registration，并支持撤销。
