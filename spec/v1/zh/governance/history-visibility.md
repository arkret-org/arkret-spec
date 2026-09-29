---
title: History Visibility and Bootstrap
status: candidate
normative: true
stability: v1
updated: 2026-09-25
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

明文 scope 按 typed `history_access` 和 retention 规则返回。`history_access` 的权威取值是封闭二态枚举，与
[`realm.schema.json`](../../artifacts/schemas/realm.schema.json)、[`circle.schema.json`](../../artifacts/schemas/circle.schema.json)
和 `event-payload.schema.json#/$defs/history_access_value` 逐字一致：

- `since_join`：只从该 actor 当前有效 join Commit 的位置（含该 Commit）开始；
- `all_history_for_current_members`：可在权限允许时分页拉取该 stream 的早期 Commit。

不存在第三个取值。"只返回建立当前状态所需的 typed snapshot"不是一个 `history_access` 值，而是 retention /
history floor 与 bootstrap 策略的结果：即使取值为 `all_history_for_current_members`，bootstrap 也默认 snapshot +
recent tail；全历史是后续按需分页，不是 join 的前置条件。

### 3.1 floor 必须可验证（normative）

floor 不只是"更早的数据取不到"，它是该 caller 允许区间的下端，必须能被绑定到已接受的链上验证：
`ak.self.committed_event.read.scan.v1` 的 `stream_scan_outcome.readable_floor` 给出 `oldest_position`、该位置的
`floor_commit_id` 与 `floor_reason`（`stream_start` / `membership_join` / `history_access_policy`）。窗口侧没有 floor 之前的状态锚点：起点恰为 floor（> 0）的逐流窗口不携带 `window_start_basis`、按 [`../sync/client-sync.md` §5.2](../sync/client-sync.md) 为 `preview_only=true`，起点在 floor 之后的窗口以已向该 caller 签发、head 不早于 floor 的 snapshot 作 committed-prefix basis。
`since_join` 的成员因此**不必**拿到 position 0 才能验证其获准前缀完整；floor 处的 Commit 是唯一允许
携带该 caller 无法解析的 `previous_commit_ref` 的可读行。

`since_join` 的 floor 唯一确定如下，scan、Snapshot `retention_and_history_floor`、窗口 `limited` 判定与客户端校验
MUST 使用同一数值：

1. 一般成员：`oldest_position` 是该 actor **当前有效** join Commit 自身的 position，`floor_reason=membership_join`，
   `floor_commit_id` 是该 join Commit。join Commit 本身可读，caller 由此验证自己的 membership。
2. 该 actor 的有效 join Commit 与该 stream 的 position 0 由同一个已登记原子接纳单元接纳（普通 Realm bootstrap
   的创建者、Direct Conversation founding 的成员）时，floor 是 position 0，`floor_reason=stream_start`，
   `floor_commit_id` 是 position 0 的 Commit；原子单元内先于 join 的 Commit 与 join 同属一次接纳，不构成加入前历史。
3. 离开后重新加入的成员只以当前有效 join Commit 为 floor；此前在册期间的区间在 `since_join` 下不可读。
   `readable_floor` 是单一下界，协议不表达多段可读区间。

Circle stream 上「当前有效 join」只指 [`../models/circle.md` §9.1](../models/circle.md) effective Circle membership 成立的
current Circle join：其 `parent_membership_revision` 仍等于父 Realm 同 cut 的 current `member_state` revision。父 Realm
`leave`／`ban` 之后，或父 rejoin 之后尚未写入携新 revision 的 Circle join 时，旧 Circle join 不构成有效 join，该 actor 在
该 Circle stream 没有可读 Commit，`readable_floor` 按下文省略；新的 Circle join 被接纳后以它为 floor，不恢复旧区间。

**Circle 历史 cut 的成员连续性（normative）**：要求在某个 Circle stream 的目标 accepted cut 验证 caller joined
membership 的读取（例如 [`../crypto-media/encryption-and-audit.md` §2.2](../crypto-media/encryption-and-audit.md) 的 Genesis
public material 读取），先要求请求 cut 的 effective Circle membership 成立，再在同一 Circle stream 上比较目标 Commit 与
current Circle join Commit：目标不早于该 join 时，该区间由同一 Circle join 实例连续承载，其父 join 实例仍为 current，成员
连续性成立；目标早于该 join 时，按目标 cut 上生效的 Circle join 实例求值，该实例在目标 cut 不是 `join`，或其
`parent_membership_revision` 已不等于父 Realm 当前 current revision，MUST 失败关闭。两种情形都仍须通过上文单一
`readable_floor` 与 history policy；协议不因旧实例当时有效而表达多段可读区间。比较只在同一 Circle stream 内进行，Realm
stream 与 Circle stream 的 position 数值不互认。

更严的 history policy 使下界更高时取更严者并使用 `history_access_policy`。

分页与扫描的所有边界都按允许区间解释：floor 以下取不到不构成 gap，也不得据此推断隐藏活动、成员或存在性；
`truncated` 只表示该方向还有该 caller 获准读取的 Commit，空结果不表示物理流不存在。
只有该 caller 在该流一条 Commit 都不获准读取时才省略 `readable_floor`。

v1 的历史可读区间只能由 current governance Station 对已接受 RealmCommit 链、current membership 与 history-access policy 求得，并通过本节已登记的 stream discovery／snapshot／scan 结果呈现。旧 Seal／CellRef closure 形式的独立 history-authority HTTP oracle 不属于 v1：服务 MUST NOT 暴露它作为另一条历史权限或可枚举查询路径，客户端 MUST NOT 将其旧结果当作 `readable_floor`、Commit provenance 或 MLS 历史密钥的替代证明。此限制不移除现行获准 stream 发现、scan/floor、历史策略与 §4 的 MLS 密钥边界。

### 3.2 retention 不裁剪 Commit 链（normative）

v1 治理 Station MUST NOT 物理删除已接受的 RealmCommit，也不产生由 retention 决定的 floor。retention 到期只作用于
Event 披露与 Station 对该 Event canonical bytes 的保留：到期位置在 scan、单项读取与窗口中仍返回同一 Commit 槽位，
使用 `CommittedEventView` 的 withheld 分支（[`../sync/service-http-binding.md`](../sync/service-http-binding.md)），
链保持连续，floor 不因 retention 移动。Realm genesis Event 与 `ak.realm.governance_station.change` Event 是
authority bundle 的必需成员，MUST NOT 因 retention 删除；handoff 导入完整 Commit 链。Snapshot
`retention_and_history_floor` 只承载 history／join floor。

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
