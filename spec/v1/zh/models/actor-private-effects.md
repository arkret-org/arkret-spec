---
title: Actor-private Event 持久效果合同
status: candidate
normative: true
stability: v1
updated: 2026-09-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **MUST NOT** / **SHOULD** / **MAY**）按
[`../conformance/normative-language.md`](../conformance/normative-language.md) 解释。

## 1. 范围与 canonical 真源

本章闭合六个 `wire_scope=actor_private_event` Event 的持久效果：

- `ak.account_data.set`
- `ak.agent.action_reject`
- `ak.agent.action_request`
- `ak.agent.draft.propose`
- `ak.device.push_route`
- `ak.read_cursor.advance`

它们的 canonical owner directory 是
[`contract-registry.json#service_contracts`](../../artifacts/registry/contract-registry.json) 中的
`ak.actor_private.effects.v1`；每个 branch 必须以 `event_kind` 精确选择
`event_kind_registry.actor_private_contracts.event_writes` 的一个结构化合同。该合同的
`storage_owner`、`unique_key`、`value_projection`、`field_maintenance`、`concurrency`、
`exact_retry`、`rejection` 与 `shared_realm_effect` 是实现必须直接消费的规范字段。正文不得以
另一组 selector、owner 或 merge 规则覆盖它们。

六种效果都由所选完整 `AccountId` 的 `station_id` 承载在 account-private store。选择
`AccountId` 的字段来源因 Event 而异，必须读取各 branch 的 `storage_owner.account_id_source`，不得
把当前接收 Station、裸 principal DID、Realm governance Station 或调用端 origin 当作 owner。
成功写入可以向该账号的已授权设备同步，但 **MUST NOT** 写 Realm typed current result、推进 Realm
reducer checkpoint、进入 federation payload，或以 RealmCommit 作为其私有状态的 CAS head。

## 2. 共同事务规则

实现 **MUST** 先完成 Event envelope、payload schema、signer/owner binding、能力与领域准入，再在一个
私有事务中评估 `concurrency` 并写入 `value_projection`。`field_maintenance` 中的每个 target 都必须从
登记 source 维护；实现不得从数据库默认值、当前会话或自由推断补出 wire 决定的字段。

每个 branch 的 exact retry identity 是 `envelope.event_id` 与 canonical Event bytes 的组合。同一组合
重放 **MUST** 返回第一次保存的 outcome，不再次递增 revision、转换 workflow、fanout、生成通知、
调用 push gateway 或重算 badge。同一 Event identity 不同 bytes 必须 `duplicate_conflict`；占用同一
CAS revision / create-once key 的不同 Event 按 branch 的 `concurrency.conflict` 拒绝。

### 2.1 提交面（normative）

每个 actor-private Event 恰有一个提交 operation，均以 caller 签名的 exact Event bytes 提交，服务 MUST NOT 重建
payload 或以服务身份代签：

| Event | 提交 operation |
| --- | --- |
| `ak.account_data.set` | `ak.self.account_data.resource.replace.v1`／`.delete.v1` |
| `ak.read_cursor.advance` | `ak.self.read_cursor.command.advance.v1` |
| `ak.device.push_route`、`ak.agent.action_request`、`ak.agent.action_reject`、`ak.agent.draft.propose` | `ak.self.actor_private_events.command.submit.v1` |

`ak.self.actor_private_events.command.submit.v1`（`POST /_arkret/self/actor-private-events`）的请求是 closed
`service-operation-dtos.schema.json#/$defs/ActorPrivateEventSubmitRequestBody`，只携一个 `event`，其 `kind` 必须是
上表第三行四个 kind 之一。服务 MUST 按本章 §2 顺序验证：已认证 caller 就是 Event 的实际签名 actor；按该 kind 的
`storage_owner.account_id_source` 选出的 AccountId 其 `station_id` MUST 等于本服务，否则 `param_invalid` 零写入；
随后在一个私有事务内求值 `concurrency`、写入 `value_projection` 与 exact-retry ledger。响应是 closed
`ActorPrivateEventSubmitOutcome`：`ak.device.push_route` 返回 `{event_kind, accepted_event_id, revision}`，其余三个
kind 返回 `{event_kind, accepted_event_id}`；exact retry 返回首次保存的同一 outcome。该 operation 不产生 RealmCommit、
不进入任何 commit stream，也不返回 RealmCommit。

`ak.self.events.command.submit.v1` 与 peer Event ingress 只接纳 shared durable Event：收到任一 `wire_scope=actor_private_event`
的 kind MUST 以 `unsupported_event_kind` 零写入拒绝，不得把它写入 RealmCommit coverage。

所有 `rejection.conditions` 都是写前条件。任一条件失败时 `side_effects="zero"`：不得写值、revision
high-water、tombstone、workflow state、幂等 outcome、queue/gateway effect、device fanout 或 shared
Realm 状态。只有 exact retry 命中已经存在的相同 outcome 时可以读取并返回它；这不是新副作用。

## 3. 六个 branch 的闭合语义

| Event | owner AccountId 来源 | 唯一键摘要 | 并发 / merge |
| --- | --- | --- | --- |
| `ak.account_data.set` | `envelope.actor_id.account_id` | `(AccountId, payload.key)` | `expected_server_revision` CAS |
| `ak.agent.draft.propose` | `payload.controller_account_id` | `(controller AccountId, agent_id, draft_id)` | pending-intent create-once；holder CAS 原子消费 |
| `ak.agent.action_request` | `payload.controller_account_id` | `(controller AccountId, agent_id, request_id)` | canonical Event digest create-once |
| `ak.agent.action_reject` | `envelope.actor_id.account_id` | `(controller AccountId, agent_id, rejection_id)` | rejection-id create-once + target-state CAS |
| `ak.device.push_route` | `payload.account_id` | `(AccountId, device_id, push_route)` | `expected_server_revision` CAS |
| `ak.read_cursor.advance` | `payload.actor_id.account_id` | `(AccountId, realm_id, canonical read_scope)` | causal → concurrent HLC → equal-HLC device id |

### 3.1 Account Data（含个人 blocklist）

个人 blocklist 不是独立 Event kind：它只是 account-data key `ak.account.blocklist` 的加密值，唯一写入方是
`ak.account_data.set`，按下文 server-revision CAS 整值替换；明文形状见
[`../discovery/client-preferences.md` §3.5](../discovery/client-preferences.md)。`entries=[]` 是有效的空列表，不是删除共享事实。

`ak.account_data.set` 在 `body`、`encrypted_payload`、`tombstone` 中恰选一支；接受后 revision 等于
`expected_server_revision + 1`。`updated_at` 投影取 payload 中已签名的值，省略时取已签名 Event
envelope 的 `created_at`。服务端不得合并 opaque encrypted bytes。tombstone GC 后仍必须保留 revision
high-water。

### 3.2 Agent draft、request 与 rejection

`ak.agent.draft.propose` 与 `ak.agent.action_request` 是两个不同身份空间。前者由 `draft_id` 定址；后者
始终由 `request_id` 定址，`draft_id` 仅是可选关联，省略它仍是合法 request，也不得改用它作为唯一键。
二者只有在 controller/agent binding、capability、policy、accountability、risk 与 expiry
校验全部通过后才可 materialize 到 controller-private store。`ak.agent.action_request` 的
`request_canonical_digest` 的 original input 是等待批准的**完整预写 Event**（含其 producer proof），与
[`../authz/constraint-schema.md` §9.2.3](../authz/constraint-schema.md) 的 `event` 支相同：
`sha256:` + SHA-256(JCS(该 Event))。Station 不持有该 Event，只按 `digest` 形状校验并逐字保存，
MUST NOT 重算或据此拒绝；controller 在以 `ak.agent.action_approve` 批准 exact `approved_event_id` 之前，
MUST 用它批准的那份 Event 重算并逐字比对。`ak.agent.draft.propose` 的 materialization
严格是 `ak.schema.agent_draft_pending_intent.v1` 的 **Station-private pending intent**，不是
`ak.agent.draft.v1:<agent_id_sha256_b64u43>:<draft_id_sha256_b64u43>` encrypted account data，也不得作为
后者的 current value 返回。

Agent MUST 把候选 `content` 按 `agent-draft-private.schema.json#/$defs/content_handoff` 用 active controller
AccountId 的当前 accepted device `hpke_key` 分别 HPKE 加密。每个 recipient 使用新 ephemeral key；RFC 9180
`info` 与单次 AEAD `aad` 都是下列对象的 RFC 8785 JCS bytes：

`{schema:"ak.agent_draft_content_handoff.v1",controller_account_id,agent_id,draft_id,proposed_action,target,content_digest,created_at,expires_at,recipient_device_id,recipient_hpke_key_digest}`。

Station MUST 校验 recipient device 去重、属于 exact controller AccountId、仍 accepted，且
`recipient_hpke_key_digest` 等于该 device 当前 HPKE key 的 digest；它只能保存和交付 ciphertext，MUST NOT
取得 holder account secret、解密 content、生成 account-data ciphertext 或代 controller 重加密。

proposal 接受时，服务在同一 private transaction 保存 canonical Event、exact-retry ledger 行（含首次 outcome）
与 `state=available` pending intent；该事务不产生 RealmCommit。controller 的 active devices 只能通过 account subscribe 顶层独立
`agent_draft_pending_intents` controller-private projection（五项 global baseline 之一 + cursor-covered
catch-up）读取该记录；该 carrier 不得复用 `account_data.events`、`account_data.station_cas`、notification、
to-device 或 storage-private API。每一 baseline page／delta 都必须重验 exact controller AccountId 的 active
device；不得向 Agent、目标 Realm 成员、federation peer 或其它 AccountId 暴露。recipient device 解密 handoff 后 MUST 校验 plaintext draft 坐标和
`content_digest == digest(RFC8785-JCS(content))`，再用 controller account secret 生成
`ak.schema.account_data_encrypted_value.v1`，其解密 plaintext验证为 `ak.schema.agent_draft.v1`。

Agent draft Account Data key 的唯一 builder 使用下列两个不可逆 component；通用 construction 是
`UTF8(domain + "\n") || UTF8(canonical_literal)`，不做 JCS、Unicode normalization、截断、salt 或 fallback：

```text
agent_domain = "ak.agent-draft.account-data-key.agent-id.v1"
draft_domain = "ak.agent-draft.account-data-key.draft-id.v1"
agent_id_sha256_b64u43 = BASE64URL_NOPAD(SHA-256(
  UTF8(agent_domain + "\n") || UTF8(canonical agent_id)
))
draft_id_sha256_b64u43 = BASE64URL_NOPAD(SHA-256(
  UTF8(draft_domain + "\n") || UTF8(draft_id)
))
account_data_key = "ak.agent.draft.v1:" || agent_id_sha256_b64u43 || ":" || draft_id_sha256_b64u43
```

`agent_id` 与 `draft_id` 必须先分别通过 `did_core_id` 与 proposal `draft_id` schema，再把其完整 literal 的
UTF-8 bytes 输入 transcript。两段都是完整 32-byte SHA-256 digest 的 43 字符 unpadded base64url；总 key
固定 105 ASCII 字符。SDK MUST 只提供这一 builder。parser MUST 要求 exact prefix、其后恰好一个分隔符、
两段各 43 字符、解码为 32 bytes 且 decode/re-encode 逐字相等；它只返回 opaque digest components，MUST NOT
声称反解 agent/draft literal。padding、错长度、非 canonical trailing bits、错误 prefix、额外分隔符与旧
literal key 均必须在验签／写入前拒绝；不存在 percent-escape、literal split、兼容别名或调用方 selector。

首次写
`ak.agent.draft.v1:<agent_id_sha256_b64u43>:<draft_id_sha256_b64u43>` 时，controller holder 提交唯一的
`ak.account_data.set` CAS：`expected_server_revision=0`、`encrypted_payload`、
`source_pending_event_id=<proposal Event.event_id>`。Station 在**同一事务**验证 holder/owner、agent/draft/key、
source、未过期和 available 状态。Station 必须仅从 `source_pending_event_id` 定位的 accepted pending row 取得
exact `agent_id` / `draft_id`，按上式重算两段并把完整结果与 signed `payload.key` 逐字比较；MUST NOT 反解、
猜测、规范化 payload key，或接受调用方另传的 decoded selector。成功时仅创建 account-data `revision=1`，并把 pending intent 转为
`consumed`，记录 consuming Event id/key/revision/time。这里没有第二个 draft revision counter。
CAS conflict、authority-commit 失败、存储中断或任一校验失败都必须同时回滚两侧，pending intent 保持
`available`；byte-identical `ak.account_data.set` retry 返回第一次的 revision-1/consumed outcome。相同 Event id
不同 bytes 或另一 consumer 返回 conflict 且零写入。后续 draft revision 不再携带 source，也不重复消费。

当 Station protocol time 不再严格早于 `expires_at`，available intent 单向转成 `expired`；consumed 不得再
过期。`ak.schema.agent_draft_pending_intent.v1` 是封闭的 `live | terminal-redacted` union：live 只允许
`state=available` 且必须携 `content_handoff`；terminal-redacted 只允许 `consumed|expired`，禁止
`content_handoff`／ciphertext，同时必须保留 controller/agent/draft、source Event id、canonical/content digest、
created/expiry 与对应 consumption／expired metadata。终态 metadata 与 exact-retry outcome 按部署 retention
保留；随后可发出携上述 terminal summary 的 removal，但必须保留已占用 create-once key digest，防止不同
proposal 或旧 available delta 复活同一 key。独立 channel 的 frozen baseline、offset、completion、position 与
权限规则见 [`../sync/client-sync.md` §3.3](../sync/client-sync.md)。

`ak.agent.action_reject` 只以必填的 `request_id` 为目标：该 request 必须属于同一 controller/agent 对、存在且
仍是 `requested`。服务必须在同一事务写 rejection record 并把该 request 转为 `rejected`；该终态清除 publish
eligibility 且不得复活。draft 不是 Station 侧的拒绝目标：`available` pending intent 只允许 controller holder
消费，未被消费即按 `expires_at` 单向转为 `expired`；已消费 draft 的 `workflow_state`（含 `rejected`）位于
controller 加密的 Account Data 中，只由 controller 以 `ak.account_data.set` 改写，Station 不可读也不可写。
拒绝 Event 自身不会撤回、删除或伪造任何 shared Realm Event。

### 3.3 Push route

`ak.device.push_route` 的 active 与 revoked 是互斥 whole-value。其唯一 CAS 字段是
`expected_server_revision`；接受后 revision 加一。revoked tombstone 必须移除 target、gateway、
encryption key、capabilities 与 expiry。任何 route queue / gateway 可见动作都必须发生在私有 CAS
成功之后；CAS 或 owner binding 失败时不得先行注册或撤销 provider route。

### 3.4 Read cursor

`ak.read_cursor.advance` 不使用 revision CAS。服务先比较 position 的支配关系：两个 position Event 提交在
同一 `CommitStreamRef` 上时 `stream_position` 大者支配；不同 stream 或同一 Event 互不支配，才比较 HLC，HLC
相等才以 `device_id` 字典序决胜（[`../discovery/read-receipts.md` §6.5](../discovery/read-receipts.md)）。
Station 不持有 position 的已提交坐标时以 universal `temporarily_unavailable` 零写入拒绝，不能改变 durable
winner。winner 保存原 payload、winning Event identity 与其
envelope `created_at`；后者只投影为 read-marker / device-message 的 `updated_at`，不得写回
`ak.schema.read_cursor.v1` payload。

## 4. 门禁要求

一致性向量 `ak.vector.agent.draft_pending_intent.v1` 必须覆盖 create、exact replay、冲突、controller-only
读取、HPKE handoff、到期、消费、CAS rollback、失败恢复、禁止 plaintext/account-data 冒充与禁止 shared reducer。

`tools/artifact_lint:result_effect_ownership` 必须拒绝：未知或 inactive Event kind、漏 branch、重复或孤儿
branch、`result_effect_ownership` 指向错误 service、错误 account owner source、shared/private scope
混用、不可解析 value schema、未知 merge kind，以及任一结构字段缺失或开放。实现声称支持这些 Event
前，必须能按 registry 逐字段重建同一 key、projection、write condition 与 rejection outcome。
