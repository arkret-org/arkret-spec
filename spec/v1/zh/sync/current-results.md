---
title: 服务器当前结果与有界基线
status: candidate
normative: true
stability: v1
updated: 2026-09-16
sidebar:
  label: 当前结果与基线
---

本文规范用语遵循 [规范性语言](../conformance/normative-language.md)。

## 1. 权威来源

治理 Station 按目标 stream 的 RealmCommit 顺序接纳 Event，并在同一事务内更新该领域的当前结果。客户端 MUST
把 Station 返回的 typed current result 作为共享状态的当前权威视图；Event timeline 用于审计与内容读取，不要求客户端
重放 Event 来恢复共享状态。

Realm、每个 Circle、每个 Sidecar 分别拥有独立 commit stream。当前结果响应携带本次视图所覆盖 stream 的
`stream_heads[]`；不同 stream 之间不存在隐含总顺序。producer Event 不携 predecessor，只有 RealmCommit 的
`previous_commit_ref` 串联同一 stream。

机器合同为
[current-result-registry](../../artifacts/registry/current-result-registry.json)、
[typed-current-result schema](../../artifacts/schemas/typed-current-result.schema.json) 与
[account-current-result schema](../../artifacts/schemas/account-current-result.schema.json)。实现 MUST NOT 发明协议级通用状态键、
通用合并算法或客户端求值规则。

## 2. 领域 selector 与 revision

每条结果是一个 closed typed object，包含领域 `selector`、`revision` 与完整领域值。v1 登记的 selector kind 为：

- `realm_profile`：当前 Realm profile；
- `realm_policy`：当前 Realm policy；
- `member_state`：以完整 `actor_id` 选择成员状态；
- `strand`：以 `strand_id` 选择 Strand；
- `message_reactions`：以目标 `event_id` 选择 reaction 集合；
- `mls_group`：以 Realm 或 Circle `scope_ref` 选择 MLS group；
- `realm_authority_root`：singleton，值为 closed `ak.schema.realm_authority_root_value.v1`（见 [`realm-and-space.md` §2.5.1](../models/realm-and-space.md)）；
- `agent_key`：以 `(agent_id, agent_key_id)` 选择一把 Agent 签名 key 的 registered authorization 投影；
- `agent_status`：以 `agent_id` 选择该 Agent 的 lifecycle 值。

selector 的身份字段来自已接纳 Event 的 typed payload，不得由调用方另行声明或由服务端按显示名称猜测。新增领域结果
必须先扩展 registry 与 schema；未知 selector 必须拒绝，不能退化为任意 JSON。

`revision` 是 closed `{commit_id, stream_position}`。`commit_id` MUST 指向最后改变该结果的 RealmCommit，
`stream_position` MUST 等于该 commit 在所属 stream 的位置。二者共同提供可验证的当前版本；时间戳、到达顺序与
EventId 均不得替代 revision。

领域写操作需要并发保护时，payload 使用该领域定义的 `expected_revision`。Station 只在它与当前 typed revision
逐字段相等时接纳；不相等返回 `failed_precondition` 并提供调用者有权读取的 current result。首次创建可使用该领域
schema 明确允许的 `null`，不得使用字符串哨兵或通用条件表达式。

## 3. 当前结果响应

`AccountCurrentResult.current` 是 closed：

- `realm_id`：结果所属 Realm；
- `authority_generation`：当前治理 Station 任期代次；
- `stream_heads[]`：调用者获准读取的 Realm/Circle/Sidecar stream heads；
- `entries[]`：closed typed results。

同一 selector 在同一 revision 下必须具有完全相同的 canonical bytes。发现相同 revision、不同值时，客户端 MUST
拒绝整批响应并重新获取当前 authority bundle；不得任择覆盖。较新 revision 原子替换旧值；来自旧
`authority_generation` 的响应不得覆盖新任期结果。

响应只包含调用者当前有权读取的 selector。省略不表示空值、删除或权限；领域若允许显式空值，必须由其 typed value
表达。成员退出、Circle 撤权或 Station 更换后，客户端必须按新授权范围清除不可再见的缓存，但不得由响应差异推断隐藏对象。

## 4. 有界基线与续传

`AccountCurrentResult.coverage` 携带 `realm_id`、`stream_heads[]` 与 `complete_for_authorized_streams`。只有在：

1. 所有获准 stream 都已扫描到所声明 head；
2. 对应 entries 已耐久安装；
3. 本次读取期间 authority generation 未改变；

三项同时成立时，服务端才可返回 `complete_for_authorized_streams=true`。

分页 cursor 必须绑定 `realm_id`、authority generation、每个已覆盖 stream head 与最后一个稳定排序键。缺页、重复页、
generation 改变或任一 head 改变时，客户端 MUST 废止该基线并从当前 authority bundle 重新开始。Circle 与 Sidecar 的
分页进度分别绑定各自 stream；不得借 Realm stream head 声明它们已完整。

Realm join bootstrap 默认从当前治理 Station 获取 authority bundle、获准 stream heads、committed Events 与 current
results。邀请人服务器只转交邀请和当前 governance Station 定位证据；它不是 bootstrap 真相源，除非它恰好就是经验证的
current governance Station。

## 5. 预算与失败

单次响应必须遵循 transport 的 canonical 与 wire 大小上限。分页只能在完整 entry 之间切分；一个 entry 不得截断。
结果暂不可计算、依赖 commit 缺失或授权状态不完整时，服务端 MUST fail closed，并要求调用者从当前 governance Station
重新同步；不得伪造默认值、让客户端从部分 Event 猜测结果或跨 stream 拼出虚假的全局顺序。

当前结果不授予写权限。每次提交仍由治理 Station针对当前 capability、成员资格、policy、领域 revision 与 MLS 约束重新校验。
