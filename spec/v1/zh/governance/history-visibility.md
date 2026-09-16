---
title: History Visibility and Bootstrap
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../conformance/normative-language.md
  - ../sync/authority-commit-log.md
  - ../sync/client-sync.md
  - ../crypto-media/device-lifecycle.md
---

# 历史可见性与 Bootstrap

规范关键字按[规范语言](../conformance/normative-language.md)解释。

历史可见性同时受 scope membership、join 时刻、Realm/Circle policy、retention 与 MLS 密钥实际可得性约束。
它不是可转授的通用历史密钥能力。

## 1. 初始来源

用户被邀请加入时，Invite、邀请人 Station 和 Directory 只提供 authority locator candidate。申请人
验证 Realm genesis 与连续 handoff chain 得到 current governance Station，完成 join 后再由自己的 Account
Station 向该 current authority 拉取 nonce-bound typed snapshot 和获准 stream tails。

不得默认从邀请人 Station、genesis 时的初始 governance Station 或任意缓存副本获取初始状态。

## 2. 独立 stream

Realm-wide Event、每个 Circle 和每个 Sidecar 各自使用独立 RealmCommit stream。用户只获得其可见
stream 的 snapshot section、head 和连续 tail。协议不存在 Realm 全局 position，也不允许通过 position gap
推断隐藏 Circle/Sidecar 活动。

## 3. 明文历史

明文 scope 按 typed `history_access` 和 retention 规则返回：

- `since_join`：只从该 actor 有效 join Commit 之后的位置开始；
- `full`：可在权限允许时分页拉取该 stream 的早期 Commit；
- `none`：只返回建立当前状态必须的 typed snapshot，不返回早期 timeline。

即使 policy 为 `full`，bootstrap 也默认 snapshot + recent tail；全历史是后续按需分页，不是 join 的前置条件。

## 4. MLS 历史

v1 只保留 standard RFC 9420 密钥语义。新 member 或新 endpoint 只从其有效 Add/Welcome epoch 起取得
解密能力。治理 Station 不持有、不导出、不补发加入前 MLS secrets；历史 Event 的读取资格只由 history-access policy
决定，与 MLS 密钥分发无关。

同 principal 的设备备份可以作为 account-private 功能迁移该 principal 本来已持有的本地 MLS state，但不得
扩张到加入前 epoch。私钥丢失时，public tree 和 governance snapshot 不能恢复私密 group state。

## 5. Authority handoff

Handoff 迁移公开 MLS state、accepted Commit Events、RealmCommits、pending Welcome ciphertext queues 与幂等索引，
不迁移成员私密 MLS state。更换 governance Station 本身不会使新 Station 成为 MLS participant。

## 6. 隐私与强制上限

返回的 snapshot/tail 必须同时满足 membership、scope visibility、history policy 和 retention；任一条件更严时以更严者为准。

### 6.1 恢复与新设备

新设备不因属于同一 principal 而自动获得历史 MLS secret；只能使用安全的 account-private 备份或当前 group 的新 Add/Welcome。
