---
title: Protocol Journey Contract Map
status: candidate
normative: true
stability: v1
updated: 2026-08-03
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [`normative-language.md`](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 边界

本文只定义协议旅程到既有正文唯一真源的静态路由，不重复定义wire、authority或状态机。实现与测试必须沿表中章节读取合同；若本文摘要与被引用章节冲突，以被引用章节为准并使traceability lint失败。本文不得被执行报告、后续问题清单或SDK私有DTO替代。

Spec机器层只允许一份顶层`artifacts/registry/protocol-journey-traceability.json`，它静态映射本文ID到prose、schema JSON Pointer、OpenAPI/operation、Event/action/profile/authority、positive/negative/crash vector、lint与consumer。registry不得包含自身ref、Spec/Cotest SHA、protocol/coverage/execution status、runner result或运行时间。固定`spec_sha/cotest_sha/runner_sha/command/result/artifact_digests/issuer`的执行证明属于Spec外部Cotest/CI detached-JWS attestation；`artifact_digests`不得包含attestation自身。Work release ledger只引用attestation，不能把静态matrix变成自证发布真相。

## 2. Cross Journey（CJ01–CJ22）

| ID | 唯一正文合同 |
| --- | --- |
| CJ01 | [`key-management.md §5.0.0`](../identity/key-management.md)：founding `device_bootstrap`四项closed allowlist、双expiry、renew/cancel状态机与exact enroll replay。 |
| CJ02 | [`key-management.md §5.0.0/§5.1`](../identity/key-management.md)：sibling pairing allowlist、transaction-filtered verification message与standard sibling final pair。 |
| CJ03 | [`api-conventions.md §3.3`](../sync/api-conventions.md)：`standard.holder_binding` human/Agent closed XOR及current lifecycle admission。 |
| CJ04 | [`contact-and-direct-conversation.md §1–§2`](../identity/contact-and-direct-conversation.md)：Contact peer closed XOR、holder signer、private reservation与source receipt。 |
| CJ05 | [同文 §2–§4](../identity/contact-and-direct-conversation.md)：normal/glare/reject的request-ref消费互斥、causal completeness与独立`ak.self.contact.command.reject`终态面。 |
| CJ06 | [同文 §3](../identity/contact-and-direct-conversation.md)：issuer-local lineage、full-set scope replacement、tombstone/recontact。 |
| CJ07 | [同文 §2–§4](../identity/contact-and-direct-conversation.md)：`ak.peer.contacts.command.submit` closed XOR carrier、mirror current lease与exact replay。 |
| CJ08 | [`api-conventions.md §3.2–§3.3`](../sync/api-conventions.md)：全部non-public `ak.self.*` bearer+DPoP AND。 |
| CJ09 | [`device-lifecycle.md §9.3`](../crypto-media/device-lifecycle.md)：ordinary MLS join admission receipt、journal/committer commitment与`ak.authority.membership_compensation.v1`。 |
| CJ10 | [`history-visibility.md §2.1`](../governance/history-visibility.md)：T0/T1/T2与receiver eligibility closed union。 |
| CJ11 | [同文 §3/§6](../governance/history-visibility.md)：visibility/range、removed/current policy与E2EE key-share边界。 |
| CJ12 | [`sidecar.md §3.1`](../models/sidecar.md)：parent-Realm bootstrap exception、minimal create与context attach staged atomic admission。 |
| CJ13 | [同文 §4](../models/sidecar.md)：`ak.sidecar.access.replace` full-set versioned selection与effective access交集。 |
| CJ14 | [同文 §4.1/§5.2](../models/sidecar.md)：唯一control frontier；MLS security digest独立按Seal+leaf/proof重算。 |
| CJ15 | [同文 §3.3](../models/sidecar.md)：suspend/reconcile与仅principal/Realm/Sidecar irreversible terminal/erase tombstone。 |
| CJ16 | [`contact-and-direct-conversation.md §5`](../identity/contact-and-direct-conversation.md)：binding/operation discovery、creation admission与opaque unavailable。 |
| CJ17 | [同文 §5](../identity/contact-and-direct-conversation.md)：`found.send_blockers[]`、canonical suspended与personal blocklist隐私。 |
| CJ18 | [同文 §6](../identity/contact-and-direct-conversation.md)：permanent pair slot、attempt advance-before-claim与唯一materialization顺序。 |
| CJ19 | [同文 §7–§8](../identity/contact-and-direct-conversation.md)：PBFT/qDA/qCOMMIT/host fence、stable identity与exact-pair repair。 |
| CJ20 | [`offline-publication.md §2`](../authz/offline-publication.md)：causal IngressReceipt四分判定与dependency backfill。 |
| CJ21 | [`device-lifecycle.md §9.1`](../crypto-media/device-lifecycle.md)及[`account-lifecycle.md §7.1`](../identity/account-lifecycle.md)：KeyPackage terminal CAS与owner-account fanout。 |
| CJ22 | [`contact-and-direct-conversation.md §9`](../identity/contact-and-direct-conversation.md)：endpoint-local outcome与SDK typed-fact local DAG；无server ActivationPlan。 |

## 3. Personal Agent A–J

| ID | 唯一正文合同 |
| --- | --- |
| A0/A | [`conformance-profiles.md §18.1`](./conformance-profiles.md)：private durable provision reservation、单Event、三个最小projection、独立Profile UI Event。 |
| B | [`key-management.md §3.6.1`](../identity/key-management.md)：generic三轴、四runtime角色与poll最小披露。 |
| C | [`contact-and-direct-conversation.md §6/§8`](../identity/contact-and-direct-conversation.md)与[`device-lifecycle.md §9.3`](../crypto-media/device-lifecycle.md)：two-Event founding、journal、补偿authority、ordinary join与stable repair。 |
| D | [`contact-and-direct-conversation.md §5`](../identity/contact-and-direct-conversation.md)：binding/operation discovery、creation gate、found/suspended。 |
| E | [`conformance-profiles.md §18.5`](./conformance-profiles.md)：target scope、scope evidence prepare/relay、五位ceiling、atomic signed replacement与destination receipt。 |
| F | [`account-lifecycle.md §9.1`](../identity/account-lifecycle.md)：单terminal Agent lifecycle Event与Agent/controller parent gates。 |
| G | [`contact-and-direct-conversation.md §5`](../identity/contact-and-direct-conversation.md)：body operation/idempotency、pair-slot CAS与temporarily unavailable恢复。 |
| H | [`key-management.md §3.6.1`](../identity/key-management.md)：minimal signer binding、互斥digest domains与current/historical双lifecycle witness。 |
| I | [`contact-and-direct-conversation.md §7`](../identity/contact-and-direct-conversation.md)：immutable pair registry、PBFT view/lock、immutable effect value、qDA/qCOMMIT、transfer/read fence。 |
| J | [`contact-and-direct-conversation.md §9`](../identity/contact-and-direct-conversation.md)：四fact classes、四runtime roles、可认证service journal与privacy/staleness。 |

## 4. 客户端与consumer DAG边界

SDK只消费typed facts并输出可并行`ready_actions[]`/`blockers[]`；它不创建global workflow identity，也不把local timer/session提升为authority。下游实现顺序是Spec → SDK；SDK固定后按真实依赖展开。consumer DAG与执行状态不进入Spec registry，仓库SHA与测试结果由外部attestation固定。任何consumer不得在Schema尚未登记时私自增加兼容shape、raw JSON fallback、版本升级或第二authority source。
