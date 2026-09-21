---
title: Operations And Sync
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - authority-commit-log.md
  - service-http-binding.md
  - federation.md
---

## 0. 规范语言

本文关键字按 [normative-language.md](../conformance/normative-language.md) 解释。

## 1. 目标

本文件定义producer Event从本地authoring到authority commit、复制、snapshot和客户端sync的统一路径。Realm、每个Circle、每个Sidecar各有独立stream。

## 2. 事件类型与 wire 边界

### 2.1 Realm Event

所有共享持久 Realm Event 都使用同一 producer-signed envelope 和 authority commit 路径。

### 2.2 敏感 Event

敏感操作通过 typed payload、required signer、current authz 和可选 `expected_revision` 表达。

### 2.3 actor-private 与 ephemeral 边界

Account-private数据、DeviceMessage、Signal、draft和recipient delivery不进入RealmCommit。它们引用Realm事实时绑定exact committed ref。

## 3. 接收与验证

Account Station先验证session、Event canonical ID和producer proof，再定位current governance Station并转发exact bytes。只有current authority执行最终admission。

### 3.1 Event 验证

现行统一验证包括closed schema、Event ID、producer proof、target stream派生、current capability/policy、typed domain invariants和idempotency。

### 3.2 敏感 Event 验证

敏感 typed Event 还验证 required controller/device/recovery signer 和 target revision。Realm genesis 是 position 0 的单个 closed create Event 与对应 RealmCommit。

### 3.3 RealmCommit 验证

消费方验证 RealmCommit 的 authority generation、signature、stream_ref、position、previous_commit_ref、event_id 和 Event digest/proof。

## 4. Event-first 发布模型

客户端离线生成producer-signed draft；own Station排队并转发；current authority在实际commit位置求值。排队不冻结旧授权，撤销在先时旧draft可以被拒绝。

## 5. MLS 原子提交

每个普通 Event 单独获得结果。MLS 使用专用原子请求：一个 `ak.mls.commit` 与全部新增 recipient Welcome deliveries 全成或全败。

## 6. Receipt 与完整性证明

RealmCommit是唯一accepted receipt；transport/queue receipt只能说明已收到或已排队。

### 6.1 读己之所写屏障

客户端read-your-writes以返回Commit和own Station barrier/cursor实现；cursor不是authority proof。

### 6.2 历史完整性边界（normative）

同一获准stream的position必须连续且predecessor唯一。History/retention floor之前的裁剪不是gap；之后无法解释的跳跃必须停止该stream并重取snapshot/authority bundle。

## 7. 同步面

低延迟subscribe只是提示；可靠恢复使用逐stream scan。不同stream不能共享position或predecessor，隐藏stream不能通过gap泄露。

## 8. 查询响应证据

Own Station 返回 typed current result 和 source committed ref。Directory 只发布当前治理 Station 直接签写的 closed public Realm metadata，不提供 source-ref callback 或通用历史解析面。

## 9. 冲突与收敛

单authority顺序消除通用CRDT/deterministic projection合流。并发请求由stream-head CAS和typed expected revision裁决；loser收到conflict并基于新current重试。

## 10. Snapshot

Snapshot 由 current authority 签名，按 closed `realm-state-snapshot.schema.json` 内联 `current_state_entries[]` typed current rows、每条获准 `visible_stream_heads[]` 与 `retention_and_history_floor`；三者来自同一 durable cut。v1 没有额外 sections、state root 或 chunk digests wire 字段。

## 11. 首次加入 Realm

Invite/Directory/邀请人只给locator。申请人own Station验证nonce-bound authority bundle，把join Event转发current authority；成功后从current authority取得snapshot和获准tails，不默认下载全历史。

## 12. 幂等、去重与重放

Event ID、Commit ID、MLS submission idempotency key和Welcome ID分别去重。响应丢失时重放exact request；不得重新claim KeyPackage或生成另一Commit/Welcome。

## 13. 授权时序

授权按authority实际commit位置的current state求值。Producer时间、排队时间、到达其它Station时间都不能保留已撤销权限。

## 14. 可见性、密文负载与 E2EE 索引

Visibility决定可读stream和snapshot section。MLS ciphertext仍是committed Event payload；治理 Station验证公开epoch/group-state/revision但不解密。新endpoint只从有效Add/Welcome起获得secret。

## 15. 设计决定

v1用单治理Station和逐scope线性Commit stream换取简单顺序、即时撤销与可判定恢复；接受authority写可用性、审查和admission信任风险。

## 16. 规范性引用

- [authority-commit-log.md](./authority-commit-log.md)
- [service-http-binding.md](./service-http-binding.md)
- [federation.md](./federation.md)
- [client-sync.md](./client-sync.md)
- [current-results.md](./current-results.md)
