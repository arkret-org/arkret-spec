---
title: 安全事务资源
status: candidate
normative: true
stability: v1
updated: 2026-07-28
---

# 安全事务资源

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

Arkret v1 只定义两个跨服务安全事务：`RecoveryTransaction` 与
`SecurityRotationTransaction`。不得把它们泛化为可执行 Saga/Plan DSL。

## 1. 共享合同

```text
SecurityTransaction {
  transaction_id,
  kind,
  principal_id,
  coordinator_service_id,
  expires_at,
  created_at,
  request_digest,
  binding,
  prepared_plan,
  prepared_plan_digest,
  state,
  accepted_steps,
  next_required_step,
  terminal_result
}
```

`kind` 是 `recovery` 或 `security_rotation`。`state` 是
`pending | running | awaiting_device_attestation | completed | aborted | expired`；后三者是唯一终态。
`binding` 由 `kind` 选择闭合 shape，不能使用任意键值或通用步骤 DSL。
`prepared_plan` 是按 kind/model 判别的 closed typed public plan；`prepared_plan_digest` 必须
等于其完整 canonical bytes digest。`prepared_plan` 内不得再携带自身 digest，也没有计算时
排除某字段的隐式规则。`accepted_steps[]` 的每项固定为
`{step, prepared_material_digest, acceptor_id, output_ref, output_digest, accepted_at}`；
`step` 必须属于该 kind/model 的闭集且在 transaction 内唯一，
数组必须是下述顺序的连续前缀，不能跳步、重排或为同一步记录第二个 digest。
`next_required_step` 只能是该闭集中紧随此前缀的下一项；终态必须为 `null`。

共同不变量：

1. 第一个不可逆副作用前固定 `transaction_id`；
2. 在同一原子持久化中固定 canonical request bytes/digest、closed typed prepared plan/digest 和
   全部公开 Event/object/series/ticket id；
3. 同 id + 同 canonical bytes 返回 byte-identical 已记录 result；
4. 同 id + 不同 bytes 返回 `duplicate_conflict`；
5. store 分别保存 typed binding、prepared canonical bytes、首次 result 与每步 accepted output，
   不能只保存“见过 id”或用一个 ref 混淆 reserved/prepared/accepted；
6. coordinator restart、response lost 与重试都从 transaction resource 续跑；
7. 可按 id 权威查询，不由客户端猜进度；
8. terminal 后禁止新增副作用；
9. mnemonic、seed、device private key、plaintext keybag 与 MLS secret 不得进入服务端 transaction。

默认 `expires_at - created_at` 最大 24 hours；进入任何已接受的不可逆远端步骤后，expiry 只停止
新步骤并进入人工/自动 recovery，不得回滚已接受事实或复用 reserved id。

### 1.1 标准操作面

协调服务必须暴露同一套闭合资源操作：

| operation | HTTP | body/outcome |
| --- | --- | --- |
| `ak.self.security_transaction.command.create` | `POST /_arkret/self/security-transactions` | `security-transaction.schema.json#/$defs/create_request` → `SecurityTransaction` |
| `ak.self.security_transaction.resource.get` | `GET /_arkret/self/security-transactions/{transaction_id}` | `SecurityTransaction` |
| `ak.self.security_transaction.command.continue` | `POST /_arkret/self/security-transactions/{transaction_id}/continue` | `#/$defs/continue_request` → `SecurityTransaction` |

两种 `create` 都必须在一个 durable transaction 中保存 canonical request bytes/digest、
typed prepared plan/digest、全部 reserved ids 与初始 resource，然后才能执行第一个副作用。
Recovery create 还必须只接受属于同一 principal、已 verified 且尚未绑定其它 transaction 的
recovery session，并在同一 durable commit 中 CAS 绑定该 session；SecurityRotation create
不依赖 recovery session，必须验证当前 principal 的 high-risk action authority。`continue` 的 `request_digest`、
`prepared_plan_digest` 和 `expected_next_step` 必须与当前 resource 精确相等，否则
`duplicate_conflict` /
`failed_precondition`；它不是提交任意步骤列表的接口。

只有 `issue_terminal_receipt` 与 `local_commit` 可以携带 `client_attestation`，且其 `output_ref`
必须等于 binding 中预留的 `terminal_receipt_id` / `local_commit_digest`，proof 必须由当前
replacement/local device 验证。其它 step 携带 client attestation 必须拒绝。`get` 是 response loss、restart 与
跨设备续跑的权威进度查询，不得从短期 HTTP idempotency cache 合成。

旧 `recovery_session.command.complete` 不属于 v1。recovery session 只负责建立 verified 证据；
完成投影只能由接受 terminal receipt 的 RecoveryTransaction coordinator 原子写入，不能存在绕过
transaction binding、prepared plan 和 accepted-step ledger 的第二个公开完成入口。

## 2. RecoveryTransaction

RecoveryTransaction 必须由 `identity_model` 判别为下面两个且仅两个 closed shape。

### 2.1 A 模型：`cross_signing`

binding 必填：

`identity_model`、`recovery_session_id`、`replacement_device_id`、`authorize_event_id`、
`device_list_update_event_id`、`terminal_receipt_id`。

prepared plan 必须保存 session snapshot/proof digest、previous/result SSK generation、
包含固定 `ak.device.authorize` 与 `ak.device.list_update` 的完整
`EventsSubmitBatchRequestBody` typed value及其 canonical bytes/digest、目标 Principal Server/
audience。terminal receipt 只在设备观察 accepted outputs 后生成，不属于 prepared plan。
batch Event ids必须逐项等于
binding。

唯一连续步骤是：

```text
submit_authorize_unit
→ issue_terminal_receipt
```

`submit_authorize_unit` 是固定双 Event batch，不得拆成两个可生成新 Event id 的通用 submit。

### 2.2 B 模型：`enrollment_authority`

binding 必填：

`identity_model`、`recovery_session_id`、`replacement_device_id`、`authority_ticket_id`、
`did_entry_ref`、`reanchor_event_id`、`authorize_event_id`、`terminal_receipt_id`。

`authority_ticket_id` 必须在 create 时作为 UUIDv7 typed id 预留；ticket 的签名 bytes 只能在
transaction durable 后由 `issue_authority_ticket` 产生。create 不得要求一个已经存在的 ticket
digest，否则 ticket issuance 会落到 transaction 固定之前。

prepared plan 必须保存 session snapshot/proof digest、显式 `account_authority_id`、
从已验证 recovery session/grant 固定的 `recovery_holder_jkt` 与 Account Authority authorization
preimage、replacement device possession proof、planned DID entry canonical bytes/
digest/previous head/ref、prebuilt reanchor Event submission、authority-produced authorize Event 的
publication evidence。Account Authority 签名与 terminal receipt 都是 create 后的 accepted
output，不属于 prepared material。

authorization preimage 必须内嵌 `did_entry_preimage`，其 canonical JSON bytes/digest 必须与
`prepared_plan.did_publication` 的 candidate entry byte-identical，且 digest 等于
`did_entry_digest`。这是 Account Authority 在 entry 尚未发布时验证新 delegation 的必要证据，
不是第二份可独立修改的 DID entry。

ticket issue request 不得嵌入 create 的 prepared plan，因为它绑定 create `request_digest`；
coordinator 必须在 transaction durable 后从已保存的 `transaction_id + request_digest +
prepared_plan_digest + authority_ticket_id + expected_next_step` 确定性构造它。

唯一连续步骤是：

```text
issue_authority_ticket
→ authorize_recovery_device
→ publish_did_entry
→ submit_reanchor_unit
→ issue_terminal_receipt
```

先取得 byte-stable authority Event，再发布不可回滚的 WebVH entry。WebVH entry 已接受而
re-anchor response 丢失时，transaction 保持 `running` 并从相同 reserved ids、prepared bytes
和 authority accepted output续跑，不得创建第二 entry。

`submit_reanchor_unit` 原子覆盖固定 `reanchor_event_id` 与 authority output 中的
`authorize_event_id`，不得拆成两个可独立重试并产生不同 Event id 的通用步骤。

### 2.3 Terminal attestation

terminal receipt 必须签名绑定 `transaction_id`、该 transaction 的稳定 `request_digest`、
`prepared_plan_digest`，以及 A/B binding 的全部 artifact refs，并证明设备对 accepted outputs
和 result 的签名声明。服务端可以验证签名、引用、digest 与 release state，不能声称观察到设备
完成解密或 MLS secret 导入。

设备必须在观察到 accepted refs 后签名，因此 coordinator 完成全部服务端步骤但客户端离线时，
resource 必须进入 `awaiting_device_attestation`，`next_required_step=issue_terminal_receipt`。
它不得预签 receipt 或把该状态声明为 completed。

### 2.4 Recovery authority 与 grant promotion 操作

| operation | HTTP | 合同 |
| --- | --- | --- |
| `ak.self.recovery_authority_ticket.command.issue` | `POST /_arkret/self/recovery-authority-tickets` | 只为当前 durable transaction 的下一步签发 ticket |
| `ak.gate.account.command.authorize_recovery_device` | `POST /_arkret/gate/account/recovery-device-authorizations` | 消费 ticket，幂等返回固定 authority-signed Event |
| `ak.gate.account.command.promote_recovery_session_grant` | `POST /_arkret/gate/account/recovery-session-grants/promote` | 以 completed transaction/receipt 与 DPoP holder proof 轮换受限 grant |

`authorization_preimage.account_authority_id` 与 `authorization_preimage.recovery_holder_jkt`
必须在 create 前固定，并由 `prepared_plan_digest` 覆盖；前者必须是目标 Account Authority
service DID，后者必须来自 Principal Server 已验证 recovery session/grant 的 `cnf.jkt`。
ticket 必须逐字复制这两个 typed 字段，不得从 generic Event JSON、部署配置、调用方自报 JKT
或事后 delegation 查询推导。

`authorize_recovery_device` 与 `promote_recovery_session_grant` 的
`canonical_request_digest` 统一等于
`SHA-256(JCS(request object with canonical_request_digest and
holder_proof.proof_jwt omitted))`。`holder_proof.dpop_jkt` 与所有业务字段仍在摘要投影内；
只排除摘要字段本身与将签署该摘要的 JWT，避免签名自引用。

`holder_proof.proof_jwt` 必须是 RFC 9449 EdDSA DPoP proof：protected header 必须为
`typ=dpop+jwt`、`alg=EdDSA` 并携带 public `jwk`；claims 必须携带 fresh `iat`、single-use
`jti`、精确 `htm=POST`、精确到无 query/fragment endpoint 的 `htu`，且 `nonce` 必须逐字等于
`canonical_request_digest`。header JWK 的 RFC 7638 thumbprint 必须等于
`holder_proof.dpop_jkt`。authorization 时该 JKT 还必须等于 ticket/preimage 的
`recovery_holder_jkt`；promotion 时必须等于 durable old grant 的 `cnf.jkt`。只比较请求体中
两个调用方自报字段不构成验证。

Account Authority 必须先查 durable exact-request outcome：已经 accepted 的 byte-identical
request 即使复用了同一 DPoP `jti` 或 proof 已超过 freshness window，也返回首次 canonical
outcome；不存在 accepted outcome 时才验证 proof freshness并原子消费 JTI。相同幂等 identity
但 bytes 不同始终返回 `duplicate_conflict`。

ticket 必须绑定 transaction/request/plan、principal/session/policy/domain、两端 service audience、
recovery holder JKT、replacement device、generation、DID head/entry、Event ids、
authorization preimage 与 possession
proof digest。Account Authority 必须按 `(ticket_id, transaction_id, request_digest)` 一次性消费；
同 bytes replay 返回 byte-identical outcome，不同 bytes 返回 `duplicate_conflict`。

v1 ticket 必须满足 `0 < expires_at - issued_at <= 300 seconds`。`auth_data.signed_fields` 必须
逐字等于 schema 登记的 25 个顶层字段，不能添加实现私有字段；签名输入是只投影这 25 个键后
的 `JCS` object bytes，不包含 `auth_data`，因此不形成 signature 自引用。`EdDSA` 直接对该
projection 签名；其它 schema-admitted service signature algorithm 也必须签同一 projection。

`replacement_device_possession_proof` 不是第二套 transaction-specific possession transcript。
它必须逐字等于 fixed `authorize_event_preimage.payload.device_signature`，其签名输入唯一复用
[`device-lifecycle.md` §5.2](../crypto-media/device-lifecycle.md) 的
`ak.device-authorize-possession-v1`。ticket 对 closed preimage/proof digest 的签名负责把这份
设备持有证明绑定到 transaction、generation、frontier 与 planned Event ids。

`authorize_event_preimage` 必须是 canonical JSON 编码、尚未带 Account Authority Event proof 的
完整 `ak.schema.event.v1` Event；reserved event id、scope、actor sequence、HLC、time、prev refs、
payload、`executed_by` 与 `authorization_ref` 都在 persisted canonical bytes 中固定。
Account Authority 必须解析并逐项验证，只能追加自己的 Event proof；不得重建 Event、生成新 id/
time/HLC 或改写任何 preimage 字段。

Account Authority 验证 delegation 时不得只查询已发布的 entry N-1，也不得把 Principal Server
对 `did_entry_digest` 的签名当作 DID controller 授权。它必须从可信 resolver 取得 entry N-1 的
完整已验证 WebVH history/head，在内存中追加 `did_entry_preimage` 后运行共享 SDK 的完整
candidate-chain/proof verifier，再从验证后的 candidate DID document state 精确解析
`authorization_ref`：delegation 必须覆盖 `ak.device.authorize`，目标 authority DID 必须等于
当前 service，且 Event 的 `executed_by` / `authorization_ref` /
`enrollment_authority_binding` 必须逐字匹配。该验证不得发布 candidate entry。

旧 recovery grant 不得原地扩大 scope。promotion 必须签发新 device/current-generation-bound
grant，并把旧 grant chain 置于 consumed 终态。

## 3. SecurityRotationTransaction

固定绑定 revoke Event、新 secret commitment、backup series/envelope、active-series Event、
erase confirmation digest 与 local commit digest。步骤顺序唯一：

对应 `binding` 必填 `revoke_event_id`、`new_secret_commitment`、`series_id`、`backup_id`、
`active_series_event_id`、`erase_confirmation_digest`、`local_commit_digest`。

```text
revoke
→ upload_new_material
→ switch_authoritative_pointer
→ erase_old_material
→ local_commit
```

每一步必须以 reserved id 和前一步 accepted ref 为 precondition。新 pointer 未成为权威状态前
不得 erase；erase 已接受后不得切回旧 pointer。客户端本地 commit 丢失时只能查询并重放相同
terminal result，不能重新上传或重新 erase。

## 4. 故障点要求

实现 conformance 必须在每个远端副作用前后注入 crash、response lost、coordinator restart、
同 id 同/不同 bytes 重试、staged secret 丢失与 terminal replay。任一故障点都只能观察到一个
transaction 和一组 reserved ids。

正例：pointer switch 已成功但响应丢失；重试查询同一 transaction，继续 erase。

反例：response lost 后创建新 transaction 并生成第二个 revoke Event id；即使最终状态相同也
违反审计与幂等合同。
