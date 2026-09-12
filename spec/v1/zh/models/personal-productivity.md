---
title: Personal Productivity
status: candidate
normative: true
stability: v1
updated: 2026-08-07
see_also:
  - private-objects.md
  - strand-and-message.md
  - ../sync/client-sync.md
  - ../../artifacts/schemas/personal-productivity.schema.json
  - ../../artifacts/schemas/draft-sync.schema.json
  - ../../artifacts/registry/account-data-key-registry.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 范围

本文定义用户个人生产力状态：提醒、定时发送、稍后处理、收藏 / 保存以及跨设备草稿。它们默认是 principal-private 或 actor-private 状态，**MUST** 通过 `ak.account_data.set` 和 `account-data-key-registry.json` 中登记的 key pattern 表达，MUST NOT 写入共享 Realm history，除非某个功能最终产生一个已授权共享 Event。

实现声明 `ak.profile.personal_productivity.v1` 时，MUST 支持本文 §2-§6 的账户私有状态。实现声明 `ak.profile.draft_sync.v1` 时，MUST 支持 §7 的草稿同步规则。

## 2. 私有 key 派生

账户数据 key 不得泄露原始目标引用、集合名称或字段路径。实现 MUST 使用 [`account-data.md` §2](./account-data.md) 定义的 `account_data_namespace_key` / `derive_account_data_key` 派生稳定、不透明的 key 片段：

- `target_key = derive_account_data_key(canonical_target_ref)`
- `collection_key = derive_account_data_key(normalized_collection_title)`，其中 `normalized_collection_title` = 对 title 先 NFC 归一化、再按 Unicode simple case folding 折叠、再去掉首尾空白并把内部连续空白折叠为单个 `U+0020` 的结果（与 [`../conformance/encoding.md` §2.2](../conformance/encoding.md) 的显示串归一化同一算法族）。两台设备 MUST 得到逐字节相同的输入，否则同一集合会分叉成两个 key。
- saved item 的 `target_key = derive_account_data_key(collection_key || canonical_target_ref)`

`canonical_target_ref` MUST 使用 canonical JSON / typed-id 规范化后的对象引用；同一目标在同一 principal 下必须得到同一 key，不同 principal 之间不得可链接。

## 3. Reminders

提醒写入 `ak.reminders.v1:<id>`。值必须验证为 `ak.schema.personal_productivity.v1` 中的 reminder plaintext value，并在写入 account-data 前加密。提醒是 holder-private 状态：服务可以按到期时间唤醒 holder 的设备，但不得把提醒内容、目标引用或说明写入共享 Event。

提醒到期后，客户端 MAY 显示本地通知或生成后续共享动作；后续共享动作必须重新通过对应 Event.kind 的授权检查，不能继承提醒本身的私有状态。

## 4. Scheduled Send

定时发送写入 `ak.scheduled_send.v1:<scheduled_send_id>`。`scheduled_send_id` MUST 是创建计划时
分配并固定的 `ak:scheduled_send:<uuidv7>`；它只标识 principal-private 计划，MUST NOT 重类型为
Event ID 或 Message ID。值必须验证为 `ak.schema.personal_productivity.v1` 中的 scheduled-send
plaintext value，并在写入 account-data 前加密。`message_payload` MUST 同时省略 `event_id` 与
`message_id`，计划中不得预铸、缓存或暗示未来的最终 Event / Message 身份。

同一 `scheduled_send_id` 的计划更新完全沿用 encrypted account-data `server_revision_cas`：
写入方携带 `expected_revision`，revision 不匹配返回 `cas_conflict` 并由客户端解密、
合并后重试；服务端不得解密 payload，也不得为该 key 另造
`duplicate_conflict`。

到期 dispatch MUST 先完成 `ak.message.create` 除 `event_id`、`proofs` 外的全部 producer-authored envelope 字段，
再按 Event digest 规则派生完整 `EventId`，并由同一 33-byte token 派生 `MessageId`。只有此时最终
Event / Message 身份才存在。

dispatch 实现 MUST 在第一次网络提交前，持久保存 `scheduled_send_id`、最终 `event_id`、派生
`message_id` 与完整 canonical signed Event bytes；提交结果不明或网络重试时 MUST 原样复用这些
bytes 和 ID，不得从仍可编辑的计划重新 author。若完成后的 bytes 尚未 durable 保存，dispatch
MUST NOT 开始网络提交。重试时出现不同 signed Event bytes 是本地 dispatch invariant 破坏，MUST
在提交前失败；只有两个不同 digest preimage 独立重算出同一完整 Event ID 时才按 Event identity
collision 规则处理，不由 scheduled-send 另建覆盖语义。定时发送计划不是共享事实；只有成功
提交的 `ak.message.create` 才进入共享 Realm history。

## 5. Snooze

稍后处理写入 `ak.snooze.v1:<target_key>`，value 使用 `snooze_expires_at` 表达失效时间。它只影响 holder 的 inbox、提醒和本地排序投影，不得改变目标 Strand / Message / Relation / View 的共享状态。

服务端或受托投影如果持有 holder 授权，可以消费该状态为 holder 生成私有投影；对其他 actor 的 shared projection MUST NOT 暴露 snooze 命中。

## 6. Saved Items

保存 / 收藏写入 `ak.saved.v1:<collection_key>:<target_key>`。每个 item 是独立账户数据项，MUST NOT 使用一个不断增长的大列表作为唯一真相源。集合标题只在加密 value 的 `collection_title` 内出现，key 中只能出现 `collection_key`。

Saved item 与 shared pin 不同：saved item 是 holder-private collection；shared pin 使用 `ak.pin.*` 并进入共享 Realm reducer。

## 7. Draft Sync

草稿写入 `ak.draft.v1:<kind>:<target_key>:<slot_key>`。支持的 v1 key 形态：

- `kind=message` 时，`slot_key=compose`。
- `kind=strand_field` 时，`slot_key=field_<sha256(canonical_field_path)>`。

草稿 value MUST 加密，并至少包含 `target_ref`、`kind`、`draft_slot`、`content`、`updated_hlc`、`origin_device_id` 和 `retention_expires_at`。`origin_device_id` MUST 是完整 `ak:device:<uuidv7>` typed ID；原始 `target_ref` MUST NOT 出现在 account-data key 中。

草稿写入 MUST 走 [`account-data.md` §5](./account-data.md) 的 compare-and-set 循环：服务端只比较 `expected_revision`，草稿冲突规则由客户端在解密明文上执行。冲突按 `(actor, target_key, draft_slot)` 做 last-writer-wins，`updated_hlc` 是比较源；收到 `cas_conflict` 时客户端 MUST 重新解密 `current_entry`、合并后以新的 `expected_revision` 重写一次。设备本地时钟不可信时，客户端 SHOULD 保留本地冲突副本供用户恢复，但 shared reducer 不参与草稿合并。

草稿发布后必须产生新的共享 Event，且共享 Event 只引用必要目标，不得把草稿 account-data key、草稿密文或草稿历史泄露进 shared payload。
