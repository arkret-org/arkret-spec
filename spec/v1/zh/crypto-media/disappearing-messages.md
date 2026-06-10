---
title: Disappearing Messages
status: candidate
normative: true
stability: v1
updated: 2026-06-10
see_also:
  - encryption-and-audit.md
  - ../models/flow-and-message.md
  - ../governance/history-visibility.md
  - ../../artifacts/schemas/disappearing-messages.schema.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 范围

`ck.profile.disappearing.v1` 为 Message 引入可选 expiry 语义。发送者可以在 `ck.message.create.payload.expiry` 中声明 TTL、触发点和 grace window；Realm 管理者可以通过 `ck.realm.disappearing_policy` 限制是否允许、最大 TTL 和默认处理方式。

Expiry 是 projection / retention 语义，**不是 redaction**。到期不得伪造 `ck.message.redact`，不得把 message state 设置为 `redacted`，不得生成假的 `redaction_ref`。

## 2. Message Expiry Payload

`ck.message.create.payload.expiry` 的字段顺序为 `ttl_ms`、`trigger`、`anchor_hlc`、`grace_ms`。`trigger` 取值为 `on_send`、`on_first_read` 或 `on_last_read`。

- `on_send`: 从 accepted Event 的 canonical send anchor 起算。
- `on_first_read`: 从任一授权 reader 首次满足 read trigger 起算；实现必须避免把 reader identity 泄露给无权观察者。
- `on_last_read`: 从所有当前可投递目标满足 read trigger 或策略定义的 delivery window 结束后起算。

`anchor_hlc` 是 reducer / projection 固定后的锚点；发送方不得用它绕过最大 TTL。`grace_ms` 只延迟本地隐藏和 key drop，不延长 Realm policy 允许的最大生命周期。

## 3. Projection Stub

到期后，projection MUST 输出固定形态的 expiry stub。Stub MAY 包含 message id、flow id、track name、expiry reason、expired_at 和最小审计引用；MUST NOT 包含 plaintext content、附件预览、可逆 search token、push snippet 或 reaction/comment 摘要。

到期 stub 与 redaction stub 必须可区分，以便审计者知道内容是按 TTL 隐藏，而不是被撤回或 moderation 移除。

## 4. Crypto Shredding

E2EE Realm 中，disappearing message SHOULD 使用 per-message temporary content key 或短 MLS epoch 派生 key。到期后，持有服务和客户端 MUST 删除可删除的本地 key material；无法保证删除的归档或备份 MUST 在 UI / audit 中标记为 retention risk。

Saved items、pins、replies、search index、push snippet 和 blob preview MUST NOT 复活已过期 plaintext。任何派生内容若包含明文或可逆摘要，必须跟随最早的 message expiry 失效。

Late key recovery 也不得复活已过期 plaintext。若目标消息已超过 `expired_at + grace`，或 retention policy 已要求销毁内容 key，客户端和 key recovery source MUST 按 [`encryption-and-audit.md` §2.3.5](./encryption-and-audit.md) 拒绝 late recovery，保留 expiry stub / metadata-only 状态，并记录 `late_recovery_rejected_expired`。

## 5. Realm Policy

`ck.realm.disappearing_policy` 写入 Realm policy cell。策略至少定义 enablement、最大 TTL、允许 trigger、默认 grace window 和是否允许 plaintext realms 使用该 profile。

不支持 `ck.profile.disappearing.v1` 的实现 MUST fail closed：可以显示无法解密 / 不支持提示，但不得把带 expiry 的消息当作普通永久消息处理。
