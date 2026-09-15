---
title: Authority-Attested Results
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../conformance/normative-language.md
  - authority-commit-log.md
  - service-http-binding.md
---

# Authority-attested 结果

规范关键字按[规范语言](../conformance/normative-language.md)解释。

用户已经信任自己的 Account Station 进行会话、账号和本地可见性处理，但 Realm 共享事实的 finality
只能来自 current governance Station 的 RealmCommit 或绑定该 authority generation 的 typed snapshot。

## 1. 信任方与角色

v1 保留三类可被 Account Station 转达的权威结果：

- `RealmCommit`：证明 exact Event 已在某一 Realm/Circle/Sidecar stream 的唯一 position 被接纳；
- `RealmStateSnapshot`：证明指定 authority generation 下的 typed current sections 和调用者获准 stream heads；
- `TypedCurrentResult`：返回封闭 selector 的 current value 及最后影响它的 Commit revision。

服务不得返回一个既无 RealmCommit 又无 typed snapshot/current signature 绑定的 `accepted=true`。

## 2. 消费方验证

消费 Station 必须：

1. 从 Realm genesis 开始验证连续 handoff chain；
2. 确认签名者是该 generation 的 current governance Station；
3. 验证 object ID、detached signature 投影和 nonce/audience；
4. 对 Commit 验证同 stream 的 position/predecessor 连续性；
5. 对 snapshot/current 验证 selector 和可见性没有扩张到其它 Circle/Sidecar。

客户端仍独立验证 Event producer proof、MLS/attachment 密码学和用户意图。Authority signature 不能替代 producer signature。

## 3. 转发与缓存

Account Station 可以缓存已验证结果并对自己账号开放，但必须保留 exact authority bytes 和验证状态。
它不得改变 revision、合并多个 stream 为一个伪全局序，或用本地接收时间作为 finality。

Authority handoff 后，旧 generation 的历史 Commit 仍可验，但旧 Station 签发的新 position 无效。缓存在每次写入前
必须刷新 authority bundle。

## 4. 服务器验证复用

MLS current 只包含 public group state、epoch、group-state ref、`current_key_access_revision` 和
`covered_key_access_revision`。两个 revision 不等时，治理 Station 拒绝新 encrypted application Event 和 Welcome admission，
直到有效 MLS Commit 覆盖 current revision。

Welcome 是 producer-signed recipient delivery object，与 Add Commit 原子入队。它不是 Realm Event，不产生独立
RealmCommit。接收者按 `welcome_id` 幂等 ACK；ACK 不改变已接纳 Commit 的 finality。

## 5. MLS 绑定结果

单 authority 模型不证明治理 Station 没有审查、扣留或错误接纳一个真实 producer Event。它只提供统一顺序、
即时 current authorization 判断和获准 stream 的连续性。需要 Byzantine transparency 的部署必须使用未来的独立 witness
profile，不得恢复 CBS/Seal/Cell 双平面。

## 6. 稳定引用锚点

下列章节号供既有领域页引用，不恢复已退役的专用 Seal 查询。

### 1.1 攻击者与责任矩阵

Account Station 只对 session、本地可见性与缓存负责，不产生 Realm finality。

### 1.2 普通客户端的 Station 接入（normative）

Realm finality 信任锨是 genesis + handoff chain 确定的 current governance Station。

### 5.2 已知 MLS artifact 的接纳结果

MLS public state 由 accepted Genesis/Commit Event 及其 RealmCommit 投影。

#### 5.2.1 认证收件人的 Welcome 引用发现

调用方通过 Commit Event ref 与 typed MLS current 判断 winning transition，不通过独立 Seal proof。

### 5.6 按次 current 与精确历史签名公钥

授权结果绑定 exact selector、authority generation、current revision 与 caller audience。

### 5.8 DID result

DID 解析证据可以作为 producer/service proof 验证输入，但不代表 Event 已提交。

### 5.9 Media result

Media 内容完整性由 blob ref 和 producer-signed 引用证明；可见性和接纳位置由 RealmCommit/current result 证明。
