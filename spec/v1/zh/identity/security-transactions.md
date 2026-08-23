---
title: 安全事务资源
status: candidate
normative: true
stability: v1
updated: 2026-08-11
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
必须等于 binding 中预留的 `terminal_receipt_id` / `local_commit_digest`。attestation 必须携带
typed `artifact`：前者是完整 `ak.schema.recovery_receipt.v1`，后者是
`ak.schema.security_rotation_local_commit.v1`。`attestation_digest` 必须等于
`SHA-256(JCS(artifact))`；外层 Ed25519 `auth_data.signed_fields` 必须逐字等于
`step, output_ref, transaction_id, transaction_request_digest, prepared_plan_digest,
attestation_digest` 的有序集合并签该 JCS projection。coordinator 必须重算 artifact digest，
验证 outer attestation；recovery 还必须验证 receipt 自己的 device signature transcript。其它 step
携带 client attestation 必须拒绝。`get` 是 response loss、restart 与
跨设备续跑的权威进度查询，不得从短期 HTTP idempotency cache 合成。

旧 `recovery_session.command.complete` 不属于 v1。recovery session 只负责建立 verified 证据；
完成投影只能由接受 terminal receipt 的 RecoveryTransaction coordinator 原子写入，不能存在绕过
transaction binding、prepared plan 和 accepted-step ledger 的第二个公开完成入口。

## 2. RecoveryTransaction

RecoveryTransaction 的基础 `identity_model="pcr_policy"`。binding 固定 account authority pair 与本地 PCR lineage、recovery
session/policy、replacement device、previous/result PCR generation、re-anchor/authorize Event ids 与 terminal
receipt；prepared plan 固定 ordered re-anchor unit，不含 DID publication。

基础步骤严格为：

```text
submit_reanchor_unit -> issue_terminal_receipt
```

`submit_reanchor_unit` 原样提交 policy-authorized `ak.device.reanchor` 与 replacement-device-signed
`ak.device.authorize`。Principal Server 验证 accepted recovery policy/session、proof threshold、payload digest
单向承诺、Event predecessor、candidate possession、monotonic generation CAS 与 old-device fence，再原子接受
两条 Event。Account Authority/transport signature 不构成内容 authority；coordinator 不持有 recovery/device
private key，不生成、更改或代签 Event。

DID method operation 的发布继续使用 `POST /_arkret/root/identity/submit-did-operation`，但它不是
RecoveryTransaction 的步骤，也不得进入 recovery binding、prepared plan 或 accepted-step ledger。
恢复 authority 只来自已接受的 PCR policy/session 与 unit 内闭合 proof；DID current root 不得绕过该策略。

## 3. SecurityRotationTransaction

固定绑定 revoke Event、新 secret commitment、按 `backup_kind` 闭合的两条
`backup_rotations[]`、erase confirmation digest 与 local commit digest。数组必须按
`secret_storage, mls_history` 顺序恰含两项；每项固定
`previous_series_id`、`new_series_id`、完整 `new_backups[]`、`active_series_event_id` 与完整
`old_backups[]`。两项或其任一 backup id/digest 在 create 后都不得替换。

两个预留 digest 必须使用下列非循环 JCS 投影计算；不得把
`transaction_request_digest`、`prepared_plan_digest`、digest 自身或运行时 timestamp 纳入
预留值：

- `erase_confirmation_digest = SHA-256(JCS({schema:
  "ak.backup_series_erase_confirmation_preimage.v1", transaction_id, series:
  backup_rotations}))`；
- `local_commit_digest = SHA-256(JCS({schema:
  "ak.security_rotation_local_commit_preimage.v1", transaction_id,
  new_secret_commitment, backup_rotations}))`。

complete erase confirmation 与 local commit artifact 仍必须回显最终
`transaction_request_digest`/`prepared_plan_digest`；receiver 必须分别核对这些最终引用，并按
上述投影复算预留 digest。这样 outcome 与最终 plan 逐字绑定，同时不形成 request/plan digest
的哈希不动点。

`prepared_plan.backup_rotations[]` 与 binding逐项相等，并为每项保存 encrypted material与
active-series Event prepared unit。公开transaction/checkpoint只保存该typed public plan；
staged account secret、明文keybag、MLS secret与私钥只能留在zeroizing secure-store slot，
且终态必须清除。

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

`erase_old_material` 的唯一 wire operation 是
`ak.self.keys.backup_series.command.erase`。request 必须携带 transaction/request/plan digest、
预留 `erase_confirmation_digest`、两条完整 binding、high-risk
`AuthorizationLease(action=ak.self.keys.backup_series.command.erase)` 与必要CBA bundle。服务端必须先验证：

1. transaction当前next step确为`erase_old_material`；
2. 两个new series及其各自`ak.key_backup.active_series` Event均已accepted且仍是authoritative；
3. target恰等于prepared plan的old backups，任何active、未计划、缺digest或额外backup均拒绝；
4. lease的basis/rule/actor/device/scope覆盖当前transaction且未过期。

response按backup kind返回durable `series_results[]`。storage partial failure只能把尚未擦除项标为
`pending`或`failed_retryable`；已经擦除项必须单调保持`erased`，重启或精确重试不得复活、改写
digest或重新加入remaining集合。`request_digest`是完整erase request canonical bytes的SHA-256；
相同transaction id但request digest不同必须`duplicate_conflict`。每个result的
`erased_backups ∪ remaining_backups`必须恰等于plan中该kind的`old_backups`，两集合不相交且均按
backup id canonical升序；`status=erased`当且仅当remaining为空，`reason_code`只允许
`failed_retryable`。只有两个series的全部planned objects都确认擦除时，status才可为
`complete`并返回`ak.schema.backup_series_erase_confirmation.v1`。confirmation只含create时已固定
的transaction/request/plan与series bytes；receiver 必须核对最终 request/plan 引用，并按本节
非循环 projection 重算且逐字等于预留 `erase_confirmation_digest`；这是SecurityTransaction accepted erase step
`output_digest`的唯一来源。partial outcome、单对象DELETE响应、日志或本地flag都不能推进该step。

## 4. 故障点要求

实现 conformance 必须在每个远端副作用前后注入 crash、response lost、coordinator restart、
同 id 同/不同 bytes 重试、staged secret 丢失与 terminal replay。任一故障点都只能观察到一个
transaction 和一组 reserved ids。

上述矩阵由`ak.vector.security_transaction.resilience.v1`与
`ak.vector_group.security_transaction.v1`固定；runner必须覆盖Recovery A/B与Rotation双
backup-kind，并输出canonical结果digest供第二个独立实现对拍。

正例：pointer switch 已成功但响应丢失；重试查询同一 transaction，继续 erase。

反例：response lost 后创建新 transaction 并生成第二个 revoke Event id；即使最终状态相同也
违反审计与幂等合同。
