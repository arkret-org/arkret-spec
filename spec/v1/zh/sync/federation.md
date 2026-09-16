---
title: Station Federation and Authority Replication
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../conformance/normative-language.md
  - authority-commit-log.md
  - service-http-binding.md
---

# Station 联邦与权威复制

规范关键字按[规范语言](../conformance/normative-language.md)解释。

Arkret v1 不再让多个 Station 独立接纳同一 Realm 的共享 Event，也不通过 causal frontier、sibling set、
RealmCommit closure 或 CRDT/Lattice 合并 accepted 结果。每个 Realm 在某一 authority generation 只有一个 current governance
Station。

## 1. 信任边界

Peer request 使用 service-to-service authentication，绑定 source/destination service DID、operation、body digest、
created/expires 和 nonce。Transport authentication 只证明请求来源；Event producer proof、RealmCommit proof、authority
handoff proof 必须分别验证。

## 2. 设计原则

成员的 Account Station 可耐久排队 exact producer-signed Event，然后转发给已验证的 current governance Station。
转发方不得修改 Event、补签、先行 accepted 或向其它成员 fanout。只有 authority 签发的 RealmCommit
才能产生共享 finality。

## 3. 复制

复制单元是一条具体 Realm、Circle 或 Sidecar stream 中连续的 `(RealmCommit, Event)` 序列。调用方对
每条 stream 单独授权和分页，必须验证：

1. authority generation 与已验证的 genesis/handoff chain 一致；
2. position 从请求起点严格递增；
3. `previous_commit_ref` 只引用同 stream 的直接前驱；
4. Commit/Event ID 、治理签名和 producer proof 均有效；
5. response 不携带调用方不可见的其它 stream head。

消费 Station 可以投影和缓存 current state，但不能用本地重放产生另一种 accepted 判决。

## 4. 完整性与故障

消费方可以证明自己获准的某条 stream 从已知 head 到新 head 连续，但不能证明 authority 在接纳前
没有审查或扣留 Event。同一 `(realm, stream, generation, position)` 出现两个不同且有效的 authority
signature 是 equivocation evidence；消费方必须冻结该 stream 并进入人工审计，base v1 不自动选择 winner。

Authority 离线时可继续读已缓存字节，但整个 Realm 不能生成新 committed Event。

## 5. Authority discovery 与 handoff

Invite、Directory、DID route 和缓存 endpoint 只提供 locator candidate。治理身份由 Realm genesis 和连续的 old→new
双签 handoff chain 证明。

计划 handoff 前，new Station 必须导入 typed snapshot、所有 stream heads/tails、idempotency index、outbox 和公开
MLS state。Handoff transition 绑定私有 full-stream-head manifest digest，但公开 bundle 只暴露 Realm stream head。
旧方在 cut 后永久拒写，新方从每条 stream 的各自直接后继位置开始。

没有完成 handoff 且旧方永久丢失时，同一 Realm 不允许自动选主或备份 takeover；只能保持可验证只读，
或创建新 successor Realm。

## 6. 隐私

Circle 和 Sidecar 使用独立 stream，Realm 成员身份不自动授权这些 stream。复制 API 不返回隐藏
stream 的存在、head、position 或 timing 差异。治理 Station 仍可见全部 scope metadata；这是单 authority 模型的明确信任代价。

## 7. 稳定引用锚点

下列章节号保留给领域页引用，全部按上述单 authority、逐 stream 复制语义解释。

### 3.2 服务签名验证

服务签名先于任何内层对象处理，但不替代 Event/Commit proof。

### 3.4 Peer policy

Peer allow/deny 只控制转发与复制入口，不能授予 governance authority。

### 4.1 Event forwarding

Event forwarding 始终保留 exact producer bytes，并只将 current authority 的 Commit 视为 accepted。

### 4.5 Stream replication

复制请求一次只覆盖一条获准 stream。

#### 4.5.1 查询抗枚举

未知、未授权、隐藏 stream 和超出 retention 的起点使用统一最小披露失败。

#### 4.5.3 有界分页

每页同时受 item count 和 canonical byte 上限约束，cursor 绑定 exact stream 与 caller。

### 5.0 Authority locator

Locator 是候选网络位置，不是 authority proof。

### 5.3 Authority bundle

Bundle 从 genesis 起返回连续 generation chain 和 current Station。

#### 5.3.1 有界加入引导（normative）

Invite 和 Directory 只携带 locator candidate；客户端必须自行请求并验证 nonce-bound bundle。

### 6.3 DID route privacy

DID route 更新不得泄露隐藏 stream inventory，也不得取代已签 handoff。

### 8.5 Failure normalization

错误响应必须避免区分 hidden/nonexistent/unauthorized Realm、Circle 或 Sidecar。
