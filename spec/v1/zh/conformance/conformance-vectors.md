---
title: Conformance Vectors
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - normative-language.md
  - ../sync/authority-commit-log.md
---

# 一致性向量

规范关键字按[规范语言](./normative-language.md)解释。

## 1. 当前基线

Authority-commit 基线由 `ak.vector.authority_commit.independent_streams.v1` 覆盖，机器样例位于
`artifacts/fixtures/authority-commit-fixture.json`，并由 `tools/test_authority_commit_protocol.py` 执行。

该向量必须证明：

1. Realm、每个 Circle、每个 Sidecar 各自从 position 0 开始，分别维护连续
   `previous_commit_ref`；不得存在跨 stream position 或 predecessor。
2. Event 不携带 `previous_commit_ref`，最终 predecessor 只属于治理 Station 签署的 `RealmCommit`。
3. 私有 handoff manifest 覆盖所有 stream heads；公开 authority bundle 只公开 Realm stream head。
4. join locator 只是提示；snapshot 与获准 stream tails 来自验证后的当前治理 Station。
5. MLS Add Commit 与全部 Welcome deliveries 在同一 authority transaction 全成或全败。

## 2. 领域向量

Typed reducer、身份、能力、媒体与扩展领域的向量必须使用本规范定义的 Event/RealmCommit 边界，并由 vector registry 登记。

### 2.5.7 领域加密向量

领域加密向量必须使用 current MLS group state、key-access revision 与对应 stream 的 committed Event reference。

### 2.5.8 审计与媒体向量

审计对象和媒体引用仍必须验证 producer proof、typed ID 与内容摘要；接纳性另由 RealmCommit 表达。

### 5.9 Read receipt

Read receipt 的隐私与合并向量改为 typed reducer 输入，不使用 OR-set dot。

### 5.10 Account data

Account-private 数据不进入 RealmCommit；当它引用 Realm 事实时必须绑定 exact committed ref。

### 5.11 View 与 client preference

View/preference 向量必须明确区分 Account-private 状态和 authority-committed Realm 状态。

### 5.12 Client sync

同步向量按每条获准 Realm/Circle/Sidecar stream 分别检查连续 position 和 predecessor。

### 5.13 Preference conflict

Account-private preference 冲突由其自身 CAS 合同处理，不得借用 Realm stream 的位置。

### 5.14 Bootstrap

Bootstrap 向量验证 nonce-bound current authority bundle、typed snapshot 和获准 stream tails，不从邀请人 Station 或 genesis Station 拉取全历史。

### 10.12.1 Push envelope

Push 只提供不可信通知提示；客户端仍从自己的 Account Station 验证 Commit/current。

### 10.12.3 Push 重放

重复通知不得产生第二个 Commit；幂等键是 Event ID 和已验证 commit ID。

### 11.10.3 Private object 存在性

未授权请求对隐藏 scope 的 absent/forbidden 使用不可枚举的统一结果。

### 11.10.4 Private object revision

获权读取返回 typed revision 和所属 stream position，不返回其它隐藏 stream 的 head。

### 22.5 DID handoff

DID route 只是 authority locator 信号；权威身份仍由 genesis 和 old→new 双签 handoff chain 证明。

### 22.6 DID freshness

解析结果必须满足调用点登记的 freshness，但不得把更新 route 当作已完成的 authority handoff。
