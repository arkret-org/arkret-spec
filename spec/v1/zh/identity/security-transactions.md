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
  state,
  accepted_steps,
  next_required_step,
  terminal_result
}
```

`kind` 是 `recovery` 或 `security_rotation`。`state` 是
`pending | running | completed | aborted | expired`；后三者是唯一终态。
`binding` 由 `kind` 选择闭合 shape，不能使用任意键值或通用步骤 DSL。
`accepted_steps[]` 的每项固定为
`{step, output_ref, output_digest}`；`step` 必须属于该 kind 的闭集且在 transaction 内唯一，
数组必须是下述顺序的连续前缀，不能跳步、重排或为同一步记录第二个 digest。
`next_required_step` 只能是该闭集中紧随此前缀的下一项；终态必须为 `null`。

共同不变量：

1. 第一个不可逆副作用前固定 `transaction_id`；
2. 在同一原子持久化中固定 canonical request bytes/digest 和全部公开 Event/object/series id；
3. 同 id + 同 canonical bytes 返回 byte-identical 已记录 result；
4. 同 id + 不同 bytes 返回 `duplicate_conflict`；
5. store 保存 typed binding、首次 result 与每步 accepted output ref，不能只保存“见过 id”；
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

`create` 必须在一个 durable transaction 中保存 canonical request bytes/digest、typed intent、全部
reserved ids 与初始 resource，然后才能执行第一个副作用。`continue` 的 `request_digest` 和
`expected_next_step` 必须与当前 resource 精确相等，否则 `duplicate_conflict` /
`failed_precondition`；它不是提交任意步骤列表的接口。

只有 `issue_terminal_receipt` 与 `local_commit` 可以携带 `client_attestation`，且其 `output_ref`
必须等于 binding 中预留的 `terminal_receipt_id` / `local_commit_digest`，proof 必须由当前
replacement/local device 验证。其它 step 携带 client attestation 必须拒绝。`get` 是 response loss、restart 与
跨设备续跑的权威进度查询，不得从短期 HTTP idempotency cache 合成。

## 2. RecoveryTransaction

RecoveryTransaction 固定绑定：

- recovery session；
- DID/WebVH entry；
- replacement device；
- authorize/reanchor Event ids；
- authority ticket；
- terminal device-attested receipt id。

这些字段必须逐项出现在 `binding`：
`recovery_session_id`、`did_entry_ref`、`replacement_device_id`、`authorize_event_id`、
`reanchor_event_id`、`authority_ticket_ref`、`terminal_receipt_id`。它们在首个不可逆副作用前
全部固定；不得退化为任意键值的 reserved-id map。

WebVH entry 已接受而 re-anchor response 丢失时，transaction 保持 `running` 并从相同 reserved
ids 续跑，不得创建第二 entry 或判为 request mismatch。

Recovery 的闭合步骤顺序是：

```text
open_recovery_session
→ validate_authority_ticket
→ publish_did_entry
→ submit_reanchor_unit
→ issue_terminal_receipt
```

`submit_reanchor_unit` 原子覆盖 `reanchor_event_id` 与 `authorize_event_id`，不得拆成两个可独立
重试并产生不同 Event id 的通用步骤。

terminal receipt 只证明设备对 transaction digest、refs 和 result 的签名声明。服务端可以验证
签名、引用、digest 与 release state，不能声称观察到设备完成解密或 MLS secret 导入。

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
