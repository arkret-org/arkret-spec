---
title: CRDT Text Extension Reservation
status: candidate
normative: true
stability: v1
updated: 2026-07-17
---

## 0. 规范语言

本文中的 **MUST** / **MUST NOT** 按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释。

## 1. Profile 状态

`ak.profile.crdt.text.v1` 是实时协同文本/富文本的 reserved interoperability slot，不是 active v1 wire。未激活前，producer MUST NOT 发出以该 profile 标记的 CRDT operation；receiver MUST fail closed 为 `unsupported_feature`，不得把未知 op 当作 opaque 可合并内容。

默认编辑面仍是 `ak.schema.patch.v1` 整值字段更新与 Strand/Message revision chain；二者语义不变。实现 MAY 在本地使用任意 CRDT，但不得声称其私有编码与本 profile 互操作。

## 2. 激活前置条件

profile 只有在一次显式 registry release 同时完成以下事项后才可激活：

1. 钉定唯一算法与版本、canonical operation/batch 编码、actor/sequence/dependency 标识和重复 op 处理规则；候选评估至少覆盖 Eg-walker、Automerge 与 Loro 的可独立实现性和长期编码稳定性。
2. 定义 plain text 与块/富文本的封闭数据模型；若只激活 plain text，富文本 op MUST 继续 fail closed。
3. 定义 ordinary Event payload、单 op/批量 op 上限、compaction/snapshot 证明，以及 E2EE Realm 中作为 MLS application message 的承载与 AAD 绑定。
4. 定义与 revision chain 的互斥声明：同一字段/文档实例不得同时接受 CRDT op 与整值 revision 作为两个并行真相源。
5. 发布至少两个独立实现通过的收敛、乱序、重复、并发格式化、恶意依赖膨胀和 snapshot 恢复向量，并把相应 vector 行、fixture 和 runner 纳入认证闭包。

激活不得通过扩宽既有 frozen schema enum 完成；必须使用 profile negotiation 与显式新 schema/kind 契约。
