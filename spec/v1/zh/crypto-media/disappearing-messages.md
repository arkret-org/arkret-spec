---
title: Disappearing Messages
status: candidate
normative: true
stability: v1
updated: 2026-06-19
see_also:
  - encryption-and-audit.md
  - ../models/strand-and-message.md
  - ../governance/history-visibility.md
  - ../../artifacts/schemas/disappearing-messages.schema.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 范围

`ck.profile.disappearing.v1` 为 Message 引入可选 expiry 语义。发送者可以在 `ck.message.create.payload.expiry` 中声明 TTL、触发点和 grace window；Realm 管理者可以通过 `ck.realm.disappearing_policy` 限制是否允许、最大 TTL 和默认处理方式。

Expiry 是 projection / retention 语义，**不是 redaction**。到期不得伪造 `ck.message.redact`，不得把 message state 设置为 `redacted`，不得生成假的 `redaction_ref`。

## 2. Message Expiry Payload

`ck.message.create.payload.expiry` 的字段顺序为 `ttl_ms`、`trigger`、`grace_ms`。`trigger` 取值为 `on_send`、`on_first_read` 或 `on_last_read`。

- `on_send`: 从 accepted Event 的 canonical send seal 起算。
- `on_first_read`: 从任一 eligible reader 首次满足 read trigger 起算；实现必须避免把 reader identity 泄露给其他成员、发送者、push provider、搜索服务或无权观察者。
- `on_last_read`: 从全部 eligible readers 满足 read trigger，或 Realm disappearing policy 定义的 read-trigger window 结束后起算。

Expiry anchor 是 reducer / projection 从 accepted send seal 或 read-trigger aggregate 派生的只读投影值，发送方 payload MUST NOT 携带 `seal_hlc`、`anchor_hlc` 或等价字段；出现此类字段 MUST `schema_violation`。`grace_ms` 只延迟本地隐藏和 key drop，不延长 Realm policy 允许的最大生命周期。

### 2.1 Read-trigger 输入

`on_first_read` / `on_last_read` 的触发输入来自两个既有 read surfaces，且二者语义分离：

1. `ck.read_cursor.advance` / `ck.schema.read_cursor.v1` 是 actor-private、多设备持久 read cursor。它是 disappearing read trigger 的首选输入；它不进入共享 Realm history，也不得被转发给其他成员。
2. `ck.receipt.read` / `ck.schema.read_receipt.v1` 是 policy 允许时的 ephemeral UI hint。只有当 effective `ck.realm.read_receipt_policy` 允许发送并且 receipt 可由 Sync Service 验证为同一 read scope 的单调前进位置时，它 MAY 作为 read trigger 输入。公开 receipt 的存在不得成为 disappearing profile 的必需条件。

客户端判定"已读"时 MUST 至少满足：目标 Event 对该 principal 在 send seal 的 effective scope 中可见；目标 Event 已投递到该 principal 的一个授权设备或该设备能通过当前 E2EE / history sharing policy 解密；该设备的可见区域、显式 mark-read 或等价用户动作已经覆盖目标 Event。预取、server-side scan、搜索命中、通知预览、未展示的 backfill、或失败解密后的占位项 MUST NOT 触发 read。

`eligible_reader_set` 在 message create 被 accepted 的 send seal 上冻结，按 message 所在 Strand effective scope、history visibility、delivery binding、capability 与 E2EE key eligibility 计算。默认排除 message 的 `actor_id` 自身；Realm policy MAY 声明包含 sender 的本地自毁语义，但不得改变其他 reader 的触发边界。send seal 之后新加入的 principal 不加入该消息的 `on_last_read` 等待集合；被移除或离线的 principal 仍按冻结集合处理，直到其贡献到达或 read-trigger window 结束。

### 2.2 匿名聚合与最小 metadata

Disappearing read trigger 是 expiry fan-in 信号，不是 read receipt。合规实现 MUST NOT 把 reader `actor_id`、`device_id`、handle、profile、IP、精确在线状态、设备数量或可跨消息关联的 reader pseudonym 放入共享 Realm Event、expiry stub、push payload、search index、notification projection、或发送者可见的状态中。

Sync / account aggregate service MAY 观察或持有执行该职责所必需的最小 metadata：

| Metadata | 可见边界 | 说明 |
| --- | --- | --- |
| `realm_id`、`source_event_id`、`read_scope`、`trigger` | 聚合服务 | 定位被触发的消息与 scope。 |
| `read_trigger_token` | 聚合服务 | 每个 `(message, principal)` 唯一、不可猜测、不可跨 message 关联的 opaque token；可由 reader account service 用 secret HMAC 派生。接收方只能用于去重和计数，不得反查 reader identity。 |
| `position_hlc`、`observed_at` | 聚合服务 | 用于单调性和重放窗口判断；不得向其他成员披露。 |
| `eligible_reader_count` 或 `delivery_set_digest` | 聚合服务 | 仅用于 `on_last_read` 完成判定；默认不得在客户端 projection 中显示。 |

对客户端和发送者可见的唯一标准结果是 message projection 在到期后降级为 expiry stub，或在到期前继续显示原消息。实现 MAY 在 sync response 中携带 metadata-only expiry hint（例如 `source_event_id`、`trigger`、`anchor_hlc`、`expires_at`），但该 hint MUST NOT 包含 reader identity、reader count、未读 reader count 或 reader token。

### 2.3 Anchor 计算

`on_send` 的 anchor 是 accepted Event 的 canonical send seal HLC。

`on_first_read` 的 anchor 是第一个有效 read trigger contribution 的 canonical 稳定 HLC。**canonical 选取规则（normative）**：anchor = `max(position_hlc, accepted_at_hlc)`，其中 `position_hlc` 是该 contribution 的 read position HLC、`accepted_at_hlc` 是聚合服务接受该 contribution 时铸造的 HLC（二者 HLC 相等时取相同值，不产生分歧）。该规则是确定性的、不依赖实现 profile：任何聚合服务 / 客户端对同一第一个有效 contribution MUST 收敛到同一 anchor，使跨实现、跨聚合服务的过期判定一致。同一 message 一旦产生 first-read anchor，后续 contribution、重复投递或 replay MUST NOT 改写 anchor。

`on_last_read` 的 anchor 是冻结 `eligible_reader_set` 中每个 principal 均有一个有效 contribution 后的最大 contribution HLC；若 read-trigger window 先结束，anchor 为该 window 的结束 HLC / timestamp。`read_trigger_window_ms` 由 effective `ck.realm.disappearing_policy` 给出；缺省时 MUST 使用 `max_ttl_ms` 作为上限窗口。`eligible_reader_set` 为空时，`on_first_read` 与 `on_last_read` MUST 退化为 `on_send` anchor，且不得暴露"无人可读"作为成员枚举信号。

`expired_at = min(anchor + ttl_ms + grace_ms, send_seal_hlc + max_ttl_ms)`；其中 `send_seal_hlc` 是该 message create 被 accepted 的 canonical send seal HLC，`max_ttl_ms` 来自同一 policy frontier 下的 effective `ck.realm.disappearing_policy`。该上限保证 `on_last_read` 的等待窗口和 `grace_ms` 都不会变成额外 plaintext lifetime：`ttl_ms + grace_ms` MUST 受 `max_ttl_ms` 约束。`expired_at` 只控制 projection、local cache 和 key shredding，不得进入 authorization、membership、history visibility 或 reducer acceptance 判定。不同副本在 wall-clock 边界附近的短暂显示差异是允许的；一旦观察到相同 anchor、send seal 和 policy，projection MUST 收敛到相同 stub。

### 2.4 幂等、重放与离线多设备

Read trigger contribution MUST 是单调且幂等的：

- 同一 `(message, principal)` 的重复 contribution 使用同一 `read_trigger_token` 去重；重复投递返回 success / already_observed 等幂等结果，不得增加计数或刷新 anchor。
- 比本地已接受 read position 更旧的 receipt / cursor MUST 被忽略；HLC 相等时按 read cursor 规范的 device tie-break 收敛，但仍只产生一个 principal-level contribution。
- replayed contribution 若 token、message、scope、trigger 或 policy frontier 不匹配，MUST fail closed；不得因攻击者重放旧 receipt 让另一条消息提前过期。
- `on_last_read` 按 principal 计数，不按设备计数。一个 principal 的任一授权设备满足 read trigger 即视为该 principal 已读；其它离线设备不得阻塞全局 anchor，但这些设备在重新上线时仍 MUST 应用已过期 stub 并删除本地 plaintext / key material。
- 离线 principal、不可达 delivery binding、丢失的 to-device 消息或被移除成员不得无限期阻塞 `on_last_read`；read-trigger window 到达时 MUST 关闭等待并计算 anchor。

不支持 private read trigger contribution 的客户端或服务，MUST 对带 `trigger=on_first_read` / `on_last_read` 的消息 fail closed：可以显示不支持 / metadata-only stub，但不得把消息当作永久消息，也不得退化为公开 `ck.receipt.read` 泄露身份。

## 3. Projection Stub

到期后，projection MUST 输出固定形态的 expiry stub。Stub MAY 包含 message id、strand id、track name、expiry reason、expired_at 和最小审计引用；MUST NOT 包含 plaintext content、附件预览、可逆 search token、push snippet 或 reaction/comment 摘要。

到期 stub 与 redaction stub 必须可区分，以便审计者知道内容是按 TTL 隐藏，而不是被撤回或 moderation 移除。

## 4. Crypto Shredding

E2EE Realm 中，disappearing message SHOULD 使用 per-message temporary content key 或短 MLS epoch 派生 key。到期后，持有服务和客户端 MUST 删除可删除的本地 key material；无法保证删除的归档或备份 MUST 在 UI / audit 中标记为 retention risk。

Saved items、pins、replies、search index、push snippet 和 blob preview MUST NOT 复活已过期 plaintext。任何派生内容若包含明文或可逆摘要，必须跟随最早的 message expiry 失效。

每个设备在观察到本地或聚合 expiry anchor 后 MUST 排程删除 per-message content key、短 epoch exporter secret、解密 cache、plaintext render cache、附件 preview key 与 search / notification derived plaintext。重复收到同一 anchor 或较旧 anchor MUST 幂等处理；收到更晚 anchor 只有在本地从未接受过 anchor 且该 anchor 能由当前 policy frontier 验证时才可采用，已经过期并 shred 的 key 不得因迟到 anchor 被恢复。

到期后保留的 encrypted envelope、Event、Seal、batch receipt、message id、strand id、track name、expiry metadata 和最小审计引用仍可存在。它们是 append-only history 的一部分，但不得包含可解密正文或可逆摘要。

Late key recovery 也不得复活已过期 plaintext。该 expiry / retention guard 的权威规则单一定义于 [`encryption-and-audit.md` §2.3.5（条 e）](./encryption-and-audit.md)（含拒绝条件、`late_recovery_rejected_expired` 记录与 key recovery source 侧义务）；本节不复述该规则，以避免双份维护漂移，客户端与 key recovery source MUST 直接以 §2.3.5(e) 为准。

## 5. Realm Policy

`ck.realm.disappearing_policy` 写入 Realm policy cell。策略至少定义 enablement、最大 TTL、允许 trigger、默认 grace window 和是否允许 plaintext realms 使用该 profile。

`ck.realm.disappearing_policy.read_trigger_window_ms` 是 `on_last_read` 等待 read contributions 的最大窗口；若省略，effective value MUST 等于 `max_ttl_ms`，且显式配置时 MUST 满足 `read_trigger_window_ms <= max_ttl_ms`。该窗口不是额外 plaintext lifetime：最终过期按 §2.3 的 `min(anchor + ttl_ms + grace_ms, send_seal_hlc + max_ttl_ms)` 计算，且 `ttl_ms + grace_ms` MUST 受 `max_ttl_ms` 约束。Realm 若允许 `on_first_read` 或 `on_last_read`，MUST 在加入 / 进入 scope 时向用户披露：客户端会发送 private read trigger contribution；该 contribution 不显示 reader identity，但发送者可能从最终过期时刻推断粗粒度读取时序，因此它不等同于公开 read receipt。

不支持 `ck.profile.disappearing.v1` 的实现 MUST fail closed：可以显示无法解密 / 不支持提示，但不得把带 expiry 的消息当作普通永久消息处理。

## 6. Conformance Vectors

实现声明 `ck.profile.disappearing.v1` 时 MUST 覆盖以下向量：

- `ck.vector.disappearing.read_trigger_anonymous_aggregate.v1`：`on_first_read` / `on_last_read` 只能输出 aggregate expiry anchor / stub；发送者和其他成员不得观察 reader identity、reader count 或可跨消息关联 token。
- `ck.vector.disappearing.read_trigger_idempotent_replay.v1`：重复 read cursor、重复 receipt、跨消息 replay 和乱序 delivery 不得刷新 anchor、重复计数或提前过期错误消息。
- `ck.vector.disappearing.on_last_read_offline_window.v1`：离线 principal / 多设备场景按 principal-level contribution 和 `read_trigger_window_ms` 收敛；离线设备上线后必须看到 stub 并 shred key。
