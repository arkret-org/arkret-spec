---
title: Personal Productivity
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - private-objects.md
  - strand-and-message.md
  - ../sync/client-sync.md
  - ../../artifacts/schemas/personal-productivity.schema.json
  - ../../artifacts/schemas/draft-sync.schema.json
  - ../../artifacts/registry/account-data-type-registry.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 范围

本文定义用户个人生产力状态：提醒、定时发送、稍后处理、收藏 / 保存以及跨设备草稿。它们默认是 principal-private 或 actor-private 状态，**MUST** 通过 `ak.account_data.set` 和 `account-data-type-registry.json` 中登记的 key pattern 表达，MUST NOT 写入共享 Realm history，除非某个功能最终产生一个已授权共享 Event。

实现声明 `ak.profile.personal_productivity.v1` 时，MUST 支持本文 §2-§6 的账户私有状态。实现声明 `ak.profile.draft_sync.v1` 时，MUST 支持 §7 的草稿同步规则。

## 2. 私有 key 派生

账户数据 key 不得泄露原始目标引用、集合名称或字段路径。实现 MUST 使用 [`client-preferences.md` §2.2](../discovery/client-preferences.md) 定义的 `account_data_namespace_key` / `derive_account_data_key` 派生稳定、不透明的 key 片段：

- `target_key = derive_account_data_key(canonical_target_ref)`
- `collection_key = derive_account_data_key(normalized_collection_title)`
- saved item 的 `target_key = derive_account_data_key(collection_key || canonical_target_ref)`

`canonical_target_ref` MUST 使用 canonical JSON / typed-id 规范化后的对象引用；同一目标在同一 principal 下必须得到同一 key，不同 principal 之间不得可链接。

## 3. Reminders

提醒写入 `ak.reminders.v1:<id>`。值必须验证为 `ak.schema.personal_productivity.v1` 中的 reminder plaintext value，并在写入 account-data 前加密。提醒是 holder-private 状态：服务可以按到期时间唤醒 holder 的设备，但不得把提醒内容、目标引用或说明写入共享 Event。

提醒到期后，客户端 MAY 显示本地通知或生成后续共享动作；后续共享动作必须重新通过对应 Event.kind 的授权检查，不能继承提醒本身的私有状态。

## 4. Scheduled Send

定时发送写入 `ak.scheduled_send.v1:<planned_message_id>`。值必须验证为 `ak.schema.personal_productivity.v1` 中的 scheduled-send plaintext value，并在写入 account-data 前加密。`planned_message_id` MUST 在创建计划时固定，并在真正发送时作为 `ak.message.create.payload.message_id` 使用；value 内的 `message_payload.message_id` MUST 等于 `planned_message_id`。

同一 `planned_message_id` 的幂等规则如下：

- 相同 canonical payload digest 的重复提交 MUST 视为 no-op。
- 不同 canonical payload digest 的重复提交 MUST 返回 `duplicate_conflict`，reason 为 `message_id_conflict`。
- 冲突时 MUST NOT 产生新的发送 Event，也不得替换已接受的消息。

`message_payload_digest` MUST 是 canonical `message_payload` 的 `sha256:<hex>` digest。定时发送计划不是共享事实。只有到期并成功提交的 `ak.message.create` 才进入共享 Realm history。

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

草稿 value MUST 加密，并至少包含 `target_ref`、`kind`、`draft_slot`、`content`、`updated_hlc`、`origin_device_id` 和 `retention_expires_at`。`origin_device_id` MUST 是完整 `ak:device:<uuid>` typed ID；原始 `target_ref` MUST NOT 出现在 account-data key 中。

草稿冲突按 `(actor, target_key, draft_slot)` 做 last-writer-wins。`updated_hlc` 是比较源；设备本地时钟不可信时，客户端 SHOULD 保留本地冲突副本供用户恢复，但 shared reducer 不参与草稿合并。

草稿发布后必须产生新的共享 Event，且共享 Event 只引用必要目标，不得把草稿 account-data key、草稿密文或草稿历史泄露进 shared payload。
