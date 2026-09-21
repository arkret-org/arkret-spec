---
title: Realm State Snapshot Schema
status: candidate
normative: true
stability: v1
updated: 2026-09-16
sidebar:
  label: Realm Snapshot
---

# Realm 状态快照

规范关键字按[规范语言](./normative-language.md)解释。机器契约为
[`realm-state-snapshot.schema.json`](../../artifacts/schemas/realm-state-snapshot.schema.json)，bootstrap 与治理
Station 更换规则见[治理提交日志](../sync/authority-commit-log.md)。

## 1. 目的与边界

Snapshot 是加速恢复的派生物，不是真相源。真相源是 producer-signed Event 与当前治理 Station 签发的
RealmCommit。Snapshot 必须绑定 Realm、authority generation、签发时各个可见 stream head、内联 typed
current rows、对应 history floor、创建时间和 Station proof。closed wire 成员是 `snapshot_id`、
`realm_id`、`governance_generation`、`visible_stream_heads[]`、`current_state_entries[]`、
`retention_and_history_floor`、`created_at` 与 `signature`。v1 没有额外的 sections、chunk/chunk digest、
state root 或 Blob 引用层；不得把旧 replay 容器作为此 schema 的兼容分支。

## 2. 可见 stream heads

`visible_stream_heads[]` 对接收者获准读取的每条 Realm、Circle 或 Sidecar stream 分别记录 `stream_ref`、
`stream_position` 与 `realm_commit_id`。不同 stream 的 position 不能比较，也不能由数组顺序推导总序。

普通 joiner 的 snapshot 只列出其当前可见 stream；因此它只能验证这些 stream 的连续性，不能证明隐藏
Circle 或 Sidecar 不存在。planned authority handoff 使用单独的私有 full-stream-head manifest，不能从公开
authority bundle 或普通 join snapshot 获得隐藏 stream 列表。

## 3. Typed current rows

`current_state_entries[]` 的每个元素必须是 `typed-current-result.schema.json` 的 closed typed result；
其 selector、revision 和 value 由各 family 的 schema 决定，不额外包一层通用 row/chunk。当前治理 Station
必须从同一 durable cut 读取全部可向该请求者披露的 rows、`visible_stream_heads[]` 和 stream floors，
不得把无权 Circle/Sidecar 的 row、head 或 floor 混入；同一完整 typed subject 不得出现两个 current row。
接收方须验证 row 的来源范围可见、revision 的位置不晚于同 stream 的可见 head；可读取到
revision 所指 Commit 时还须逐字核对 commit id/position。落在获授权 history floor 之前的
row 由当前治理 Station 的这份签名 snapshot 承诺，不能要求受限接收者下载不可见前史来补证；
范围或坐标不一致时整份丢弃。
从 snapshot 边界之后的逐 stream tail 继续运行同一 typed reducer，不得用 generic patch、
typed current result merge 或 wall-clock last-write-wins 修补差异。`current_state_entries: []` 仅在该 cut
确实没有可披露 current row 时合法；它不是要求另取 chunk 的占位符，也不能证明隐藏 row 不存在。

## 4. 创建与验证

Snapshot 的 `signature` 使用 `ak.realm_snapshot_signature.v1`。unsigned projection 是从完整 closed Snapshot 删除
`signature` 后保留的全部实际存在成员；验证方对其作 RFC 8785 JCS，重算
`sha256:lowercase_hex(SHA-256(unsigned_bytes))`，先与 envelope 的 `signed_digest` 逐字比较，再验证
`UTF8("ak.realm_snapshot_signature.v1\n") || RFC8785_JCS({context,signature_algorithm,verification_method,signed_digest,created_at})`
上的 64-byte Ed25519 签名。`governance_generation` 必须等于 current authority bundle 已验证的当前治理 Station 任期，
`verification_method` 必须是该 exact Station 的 service signing key；上一 generation 的有效 key 也必须拒绝。

当前治理 Station 在同一一致性快照中读取 visible stream heads、`current_state_entries[]` 与 history floors，构造 canonical body，
计算 snapshot ID 并签名。接收方必须验证：

1. authority bundle 证明签名 Station 是该 `governance_generation` 的当前治理 Station；
2. snapshot ID 与 canonical body 匹配；
3. Station proof 的 domain separation 与 payload digest 匹配；
4. 每个 visible head 可由随后下载的同 stream tail 连续承接；
5. tail 中每个 Commit 的 Event、producer proof、authority proof 与 typed reducer 均有效。

任一项失败时必须丢弃整个 snapshot，不能部分采用 rows。Snapshot 签名使当前治理 Station 对
该 materialization 负责，但本身不提供独立 omission proof；随后 tail 的逐 stream 连续性只能
证明从各自已验证 head 起的后续 Commit 没有缺口，不能反证该 head 前被治理方隐去的 row。

## 5. Join bootstrap

邀请人服务器和 Directory 只提供候选 locator。Joiner 向候选发送 fresh nonce，取得 genesis-to-current 的
nonce-bound authority bundle，验证后只从该 current governance Station 拉取 snapshot 与自己可见的所有
stream tails。邀请中缓存的“初始 Station”或 genesis Station 不能覆盖已验证的 current authority。

## 6. Planned handoff

旧 Station 私下向新 Station 交付 snapshot、完整 stream-head manifest 及每条 stream 的缺口材料。公开
handoff certificate 只披露 Realm stream head 与 full manifest digest。新 generation 在每条既有 stream 上的
第一笔 Commit 必须以前一 generation 导入的该 stream head 为 `previous_commit_ref`，位置加一；它们彼此没有
统一的“handoff 后第一笔”顺序。

若旧 Station 丢失且未完成双签 handoff，v1 不自动选主，也不允许新 Station从成员投票或最长链自行接管。
恢复必须走 Realm 明确声明的外部恢复政策或创建新 Realm。
