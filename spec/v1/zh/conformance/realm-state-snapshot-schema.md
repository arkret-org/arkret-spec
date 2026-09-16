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
RealmCommit。Snapshot 必须绑定 Realm、authority generation、签发时各个可见 stream head、typed current
rows 的 commitment、创建时间和 Station proof。

Snapshot 不使用 chunk-level 通用状态格式，不携带 typed current result、actor frontier、CRDT tombstone 或 caller 定义的
state root。大对象可经 Blob surface 传输，但 snapshot schema 中每个引用必须内容寻址。

## 2. 可见 stream heads

`visible_stream_heads[]` 对接收者获准读取的每条 Realm、Circle 或 Sidecar stream 分别记录 `stream_ref`、
`stream_position` 与 `realm_commit_id`。不同 stream 的 position 不能比较，也不能由数组顺序推导总序。

普通 joiner 的 snapshot 只列出其当前可见 stream；因此它只能验证这些 stream 的连续性，不能证明隐藏
Circle 或 Sidecar 不存在。planned authority handoff 使用单独的私有 full-stream-head manifest，不能从公开
authority bundle 或普通 join snapshot 获得隐藏 stream 列表。

## 3. Typed current rows

`typed_current_rows[]` 是 closed typed union。每个 row 必须包含 reducer kind、业务主键、revision 及最后接受
该 revision 的 Commit reference。相同主键只能出现一次。接收方须从 snapshot 边界之后的逐 stream tail
继续运行相同 reducer；不得用 generic patch、typed current result merge 或 wall-clock last-write-wins 修补差异。

## 4. 创建与验证

当前治理 Station 在同一一致性快照中读取 visible stream heads 与 typed current rows，构造 canonical body，
计算 snapshot ID 并签名。接收方必须验证：

1. authority bundle 证明签名 Station 是该 `authority_generation` 的当前治理 Station；
2. snapshot ID 与 canonical body 匹配；
3. Station proof 的 domain separation 与 payload digest 匹配；
4. 每个 visible head 可由随后下载的同 stream tail 连续承接；
5. tail 中每个 Commit 的 Event、producer proof、authority proof 与 typed reducer 均有效。

任一项失败时必须丢弃整个 snapshot，不能部分采用 rows。

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
