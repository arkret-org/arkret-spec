---
title: Offline Event Queueing
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../conformance/normative-language.md
  - ../sync/authority-commit-log.md
  - ../sync/service-http-binding.md
---

# 离线 Event 排队

规范关键字按[规范语言](../conformance/normative-language.md)解释。

离线客户端可以构造并签名 exact Event，但不能预获得未来的接纳权。Event 只在 current governance
Station 按提交位置的 current authorization、typed revision 和 MLS gate 验证通过，并签发 RealmCommit 后成为共享事实。

## 1. 本地耐久化

在首次网络副作用前，客户端或 Account Station 必须原子保存 exact canonical Event bytes、producer proof、
目标 Realm/scope 和本地幂等记录。重试必须逐字节重放；不得因时间、route 或 stream head 变化而修改已签 Event。

## 2. 授权语义

v1 不提供可在未来抵消撤销的离线 authorization lease。在 Event 提交前发生的成员移除、device/runtime
撤销、capability 撤销、policy 变更或 MLS key-access revision 推进，都对接纳判断立即有效。

需要并发保护的领域写入在 typed payload 中携带 `expected_revision`。排队期间 revision 变化时，治理
Station 返回 `cas_conflict`，客户端必须获取新 current、要求用户确认语义变化，并生成新 Event。

## 3. 状态机

本地可见状态只有 `queued`、`forwarding`、`committed`、`rejected` 和 `temporarily_unavailable`。
`queued/forwarding` 不得进入共享 current、共享 timeline 或其它成员的 fanout。收到有效 RealmCommit 后才转为
`committed`。明确拒绝不占 stream position，不能通过更换 Account Station 绕过；暂时失败使用 `temporarily_unavailable`。

## 4. MLS

MLS Add Commit 必须把 staged post-state 和全部 exact Welcome deliveries 一并耐久保存，再发送原子
MlsCommitSubmission。Commit 被接纳后安装 staged state，不等待 recipient ACK。若请求结果不明，重放同一
submission，不得重新 claim KeyPackage 或重新生成 Commit/Welcome。
