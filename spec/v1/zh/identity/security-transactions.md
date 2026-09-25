---
title: 安全事务资源
status: candidate
normative: true
stability: v1
updated: 2026-09-25
---

# 安全事务资源

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

Arkret v1 只定义两个 Station 内安全事务：`RecoveryTransaction` 与
`SecurityRotationTransaction`。它们是 Station 内的 durable orchestration，不得泛化为可执行 Saga/Plan DSL。

## 1. 共享合同

```text
SecurityTransaction {
  transaction_id,
  kind,
  account_id,
  expires_at,
  created_at,
  request_digest,
  prepared_plan,
  prepared_plan_digest,
  accepted_steps,
  terminal_outcome
}
```

`kind` 是 `recovery` 或 `security_rotation`。`terminal_outcome` 缺省表示事务仍活动；存在时其
`result` 是 `completed | aborted | expired`，并且是终态 kind 的唯一真相源。coordinator 是否已经开始
某一步、重试次数与 lease 只属于本地 durable step-attempt ledger 或运行遥测，不得序列化或持久化为协议
phase/state。客户端是否需要设备签名必须由 `terminal_outcome` 缺省且
`steps(kind)[accepted_steps.length]` 为 client-attested step 纯函数计算，禁止把该 readiness 再序列化或
持久化为协议状态。

顶层 `account_id` 唯一确定事务拥有者；本文所称 coordinator 是执行该事务的 Station service role，它就是
`account_id.station_id`，wire 上不存在第二个可与之不一致的 coordinator 字段。该 Station 的 service core identity
即 coordinator，不得指向任意外部协调者。部署可以把步骤执行拆为多个进程，但不得由此产生独立的公开 coordinator role。
事务中的 Event 与备份对象的完整 `ActorId` MUST 等于该 `AccountId` 对应的 account actor；只比较
只比较 `account_id.principal_id` 不足以验证归属，同一主体在另一 Station 的 Event、备份、PCR、设备与 session 均不得混入。

`prepared_plan` 是按 kind/model 判别的 closed typed public plan，也是 intent 与 reserved material 的唯一
canonical source；其中 Recovery plan 内嵌 closed `binding`，Rotation plan 的 reserved binding view 由
`revoke_unit` 与两项 `backup_rotations[].binding` 等字段纯函数投影，不能使用任意键值或通用步骤 DSL。
`prepared_plan_digest = SHA-256(RFC8785_JCS(prepared_plan))`，是 coordinator 对完整 plan canonical bytes
重算并返回的固定 SHA-256、跨 Realm CAS 坐标；它不跟随 Blob 或 KDF 等其它 typed domain 的 digest suite。create request
不得携带该值，`prepared_plan` 内也不得携带自身 digest，计算时没有排除字段的隐式规则。
每个 `prepared_event_unit` 的 wire 形态固定为 `{request,request_digest}`：`request` 必须独立满足
`EventsSubmitBatchRequestBody`，`request_digest` 必须等于其 digest suite 对 `RFC8785_JCS(request)` 的计算结果。
该 unit 的 operation 固定为 `ak.self.events.command.submit.v1`，request schema 固定为上述 DTO，destination 与 audience
都从父 transaction 的 `account_id.station_id` 取得；这四项与 canonical request bytes 是构造时的 computed view，
不得作为平行 wire 输入或 durable 真相源。coordinator 必须以同一 `JCS(request)` bytes 执行和持久化。
`accepted_steps[]` 的每项固定为 `{acceptor, accepted_at}`；数组位置按下述固定步骤表
唯一决定 step kind，整个数组必须是连续前缀，不能跳步、重排或为同一步重复记录。活动事务的下一步
等于 `steps(kind)[accepted_steps.length]`；resource 不重复序列化该派生值。
`acceptor` 是接受该步骤的稳定 participant identity，closed 为
`{kind: principal, principal_id: DidCoreId} | {kind: device, device_id: DeviceId}`；服务 participant
必须写入永久 Arkret core identity，不得写入 W3C 裸 DID、transport URI 或 mixed identifier string。
`accepted_steps` 仅记录已接受的位置和参与者，不是效果证明。Recovery terminal 必须从 plan 的
`terminal_receipt_id` 与实际 accepted Commit、completion result 核对；SecurityRotation 的
`revoke` 必须核对 closed `revoke_command_outcome`，upload 必须核对 plan 中每个已持久上传的
`new_backup_envelopes`，switch 必须核对 `active_series_unit` 的 accepted Commit 与 current pointer，
erase 必须核对完整 durable erase confirmation，local commit 必须核对客户端签署的 terminal artifact。
plan 中预留的 ID 或 digest 本身不证明效果已经执行。worker 只有在对应效果耐久完成且核对成功后，
才能原子追加该步；重启时也必须从这些原始耐久结果重新核对，不得从预留字段合成 accepted step。

共同不变量：

1. 第一个不可逆副作用前固定 `transaction_id`；
2. 在同一原子持久化中固定 canonical request bytes/digest、closed typed prepared plan/digest 和
   全部公开 Event/object/series/ticket id；
3. 同 id + 同 canonical bytes 返回 byte-identical 已记录 result；
4. 同 id + 不同 bytes 返回 `duplicate_conflict`；
5. store 分别保存唯一 typed prepared plan/canonical bytes、首次 result 与每步实际完成的耐久结果，
   不能只保存“见过 id”或用一个 ref 混淆 reserved/prepared/accepted；
6. coordinator restart、response lost 与重试都从 transaction resource 续跑；
7. 可按 id 权威查询，不由客户端猜进度；
8. terminal 后禁止新增副作用；
9. mnemonic、seed、device private key、plaintext keybag 与 MLS secret 不得进入服务端 transaction。

默认 `expires_at - created_at` 最大 24 hours；进入任何已接受的不可逆远端步骤后，expiry 只停止
新步骤并进入人工/自动 recovery，不得回滚已接受事实或复用 reserved id。

### 1.1 标准操作面

执行 Station 必须暴露同一套闭合资源操作：

| operation | HTTP | body/outcome |
| --- | --- | --- |
| `ak.self.security_transaction.command.create.v1` | `POST /_arkret/self/security-transactions` | `security-transaction.schema.json#/$defs/create_request` → `SecurityTransaction` |
| `ak.self.security_transaction.resource.get.v1` | `GET /_arkret/self/security-transactions/{transaction_id}` | `SecurityTransaction` |
| `ak.self.security_transaction.command.continue.v1` | `POST /_arkret/self/security-transactions/{transaction_id}/continue` | `#/$defs/continue_request` → `SecurityTransaction` |

SecurityRotation `create` 只接受完整 typed plan，并且必须携带与当前高风险认证 session 中设备完全一致的
`authorizing_device_id`；Recovery `create` 只接受 closed typed `recovery_intent`，
typed prepared plan 一律由 coordinator 在 §2.1 的专用 prepare transaction 中派生，客户端不得提交一份已经填完的
`prepared_plan`。两种 `create` 都必须在一个 durable transaction 中保存 canonical request
bytes/digest、typed prepared plan、自己重算的 plan digest、全部 reserved ids 与初始 resource，然后才能执行第一个副作用。
Recovery create 还必须只接受属于同一 Station-local AccountId、已 verified 且尚未绑定其它 transaction 的
recovery session，并在同一 durable commit 中 CAS 绑定该 session；SecurityRotation create
不依赖 recovery session，而由 Account Authority 按部署的 recent login／WebAuthn／recovery key 等策略验证 fresh
high-risk action authentication，将 `authorizing_device_id` 与认证 session 逐字核对，并在任何副作用前持久化到事务。
不满足时返回 `reauthentication_required` 且零写入；该步骤不签发、不接受 `AuthorizationLease`。`continue` 的 `request_digest`、
`prepared_plan_digest` 必须与当前 resource 精确相等，`expected_accepted_step_count` 必须等于当前
`accepted_steps.length`，否则
`duplicate_conflict` / `failed_precondition`；它不是提交任意步骤列表的接口。coordinator-owned prefix 只属于
SecurityRotation 的 `revoke`、`upload_new_material`、`switch_authoritative_pointer`、`erase_old_material`——只能由
durable transaction worker 自动执行与恢复；restart、response loss 或 retry 都从同一 resource 继续，客户端只能用
`get` 观察，不能用 `continue` 驱动或重复执行这些步骤。Recovery 没有 coordinator-owned prefix：它的唯一 accepted step
就是 client-attested 的 `commit_recovery_unit`。

`continue` 只提交 client-attested terminal step，因此 request 必须携带 `client_attestation`。服务端必须先从 resource 的
`kind` 与 `accepted_steps.length` 派生下一步：Recovery 只在 terminal index 0、SecurityRotation 只在 terminal index 4
ready 时继续验证 CAS、reserved output 与 attestation；任何 coordinator-owned prefix、尚未 ready 的 terminal、错误 kind/step
或越界 prefix 都返回 `failed_precondition`，不得产生副作用。通用 request schema 不携 `kind`，所以不得把 `{0,4}` 或 kind-specific
maximum 写进 JSON Schema；无 attestation 的 POST 也不是 `get` 的 no-op 别名。

只有 `commit_recovery_unit` 与 `local_commit` 可以作为 `client_attestation.step`，且其 `output_ref`
必须等于 prepared plan 中预留的 `terminal_receipt_id` / `local_commit_digest`。attestation 必须携带
typed `artifact`：前者是闭合 `ak.schema.recovery_terminal_commit.v1`，后者是
`ak.schema.security_rotation_local_commit.v1`。RecoveryTerminalCommit 内的 recovery receipt 由 replacement device
以同一冻结 device key 自行签发，服务端不得伪造、代签或返回带占位签名的 draft；local commit 同样由客户端从权威
transaction resource 复制 `transaction_id`、`request_digest`、`prepared_plan_digest` 与 prepared plan 的
`local_commit_digest`，再加入本地 `device_id` / `committed_at` 构造。两类 artifact 都是 caller-authored material，
不需要也不存在第二个服务端 supply operation。wire 上不携 `attestation_digest`；外层 Ed25519 签名输入固定为
`RFC8785_JCS({step, output_ref, transaction_id, transaction_request_digest, prepared_plan_digest,
attestation_digest})`，其中投影成员 `attestation_digest := SHA-256(JCS(artifact))` 由签名方与 verifier
各自从同载体 `artifact` 重算填入，不从 wire 读取；wire 上也不携字段名清单。coordinator 必须重算 artifact
digest，验证 outer attestation；recovery 还必须验证 receipt 自己的
device signature transcript。其它 step 对应非 terminal-ready resource 的 attestation 必须拒绝。
`client_attestation.auth_data.verification_method` MUST 是当前 Account DID 加 `#<device_id>` 构成的
canonical DID URL。verifier MUST 在同一 accepted PCR cut 解析该设备的当前授权签名 key、generation、
revocation 与 pending 状态，核对 attestation 的签名设备与 typed artifact 中的设备逐字相同，
并拒绝不属于该 Account 或当前未获授权的 key。仅有调用方自报的 DID URL 不构成授权。
`get` 是 response loss、restart 与跨设备续跑的权威进度查询，不得从短期 HTTP idempotency cache 合成。
当 coordinator-owned prefix 已完成而最终 client-attested step 尚未提交时，resource 仍不携带
`terminal_outcome`；它不会被误判为 completed，因为完整 accepted prefix 与 `result=completed` 的 terminal
result 仍是成功终态的必要条件。

旧 `recovery_session.command.complete` 不属于 v1。recovery session 只负责建立 verified 证据；
完成投影只能由接受 `commit_recovery_unit` 的 RecoveryTransaction coordinator 原子写入，不能存在绕过
prepared plan binding 和 accepted-step ledger 的第二个公开完成入口。

## 2. RecoveryTransaction

RecoveryTransaction 保留为账号恢复的单一原子事务，但客户端输入不再创建或携带 RealmCommit。replacement device 只签两条 producer Event 与 `RecoveryReceipt`；当前治理 Station 独占 PCR stream 的 RealmCommit 签发权，并在 terminal admission 内签发两笔连续 Commit。

### 2.1 create 同时完成专用 prepare，但不产生恢复效果

create 请求固定 verified recovery session、replacement device、`previous_model_generation_ref` / `result_model_generation_ref`、预留 `terminal_receipt_id`、两条完整签名 Event，以及 `reanchor_commit_intent={realm_id,predecessor_ref,unit_event_digests}`。`predecessor_ref` MUST 等于当前 PCR stream head，digest 顺序 MUST 为 `[reanchor, authorize]`。

Station 在一个 durable prepare transaction 中重验 session、policy/proof snapshot、device PoP、generation CAS、当前治理 authority、stream head 与两条 Event；随后冻结 canonical request 和 prepared plan。prepare 不插入 Event、不生成 RealmCommit、不推进 generation、不激活设备、不消费 session。

### 2.2 唯一终态载体

唯一 client-attested step 仍为 `commit_recovery_unit`。其 artifact 是 closed `RecoveryTerminalCommit`，但该名称只表示“恢复事务的终态客户端载体”；wire 内容只有 replacement-device-signed `recovery_receipt`，不含 RealmCommit、authority signature 或预先计算的 commit id。

RecoveryReceipt 签入 transaction/request/plan、两条 producer EventId、previous/result generation、session/policy/proof snapshot、backup/welcome 结果与 authoring time。它在 authority admission 前生成，因此 MUST NOT 携 `reanchor_commit_id` 或 `CommittedEventRef`。outer client attestation 绑定该 exact receipt artifact。

### 2.3 唯一原子提交与可观察性

接受 terminal step 时，治理 Station 在同一数据库事务与同一 stream-head/generation CAS 下：

1. 重验 transaction、session、plan、receipt、outer attestation 与两条 Event；
2. 以 `[reanchor, authorize]` 顺序为 PCR stream 生成并签署**两笔 position 连续的 RealmCommit**，每条 Event 各一笔；
3. 原子保存 Event、RealmCommit、stream head、generation advance、replacement device active state、session consumption 与 terminal result；
4. 生成 `RecoveryCompletionAttestation`。

任一步失败都不得留下可见 Event、RealmCommit 或部分 generation state。成功后两条 Event 的 `CommittedEventRef` MUST 具有相同 `stream_ref`、**不同 `commit_id`** 与不同 `event_id`，`stream_position` 按上述顺序严格加一。一条 RealmCommit 恰好接纳一条 Event（[`realm-commit.schema.json`](../../artifacts/schemas/realm-commit.schema.json) 的 `event_ref` 与 `stream_position` 都是单值必填），因此「两条 Event 落在同一个 `commit_id` 上」不是一种可实现的形态：同一个 `commit_id` 就是同一个 `stream_position`。unit 的原子性是**事务级**的，由上述第 3 步的同事务 stream-head/generation CAS 保证，不由共享一笔 Commit 保证。

### 2.4 operation 与 grant 边界

`RecoveryCompletionAttestation` 是 Account Authority 签发恢复后 Standard grant 的唯一离线完成证据。其签名投影包含 transaction/request/plan、account/session/receipt、`reanchor_event_ref`、`device_authorization_event_ref`、`result_model_generation_ref` 与 `completed_at`。不再存在 `reanchor_commit_id` 或 `terminal_commit_digest`；RealmCommitId 已绑定 authority-signed commit bytes，不能再叠加一个旧 terminal artifact digest 作为治理根。

### 2.5 幂等、竞争与失败终局

同一 canonical terminal request 重放返回已保存的 receipt、两条 CommittedEventRef 与 completion attestation。相同 transaction id 的不同 bytes 返回 conflict。stream head、generation、session 或 policy 已改变时 fail closed，并且客户端必须创建新的 recovery session/transaction；服务不得改写旧 Event、把它们移到另一 RealmCommit、或由 inviter/旧治理 Station 代签。

## 3. SecurityRotationTransaction

固定绑定 revoke Event、新 secret commitment、唯一 `secret_storage`
`backup_rotations[]`、erase confirmation digest 与 local commit digest。数组恰有一项并必须包含
`previous_series_id`、`new_series_id`、完整 `new_backups[]`、`active_series_event_id` 与完整
`old_backups[]`。该项或其任一 backup id/digest 在 create 后都不得替换。

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

`prepared_plan.backup_rotations[]` 的内嵌 binding 是每项 reserved series/object refs 的唯一 source，并同时保存
closed `new_backup_envelopes: [KeyBackup]` 与 active-series Event prepared unit。envelope 数组必须按
`backup_id` canonical 升序排列且互异；每项的 `{backup_id,ciphertext_digest}` 必须与
`binding.new_backups[]` 逐项相等。coordinator 必须验证每份完整 envelope 的签名、归属和 ciphertext digest，
不得接受开放材料包装或只验证 binding 摘要。公开 transaction/checkpoint 只保存该 typed public plan；
staged account secret、明文keybag、MLS secret与私钥只能留在zeroizing secure-store slot，
且终态必须清除。

```text
revoke
→ upload_new_material
→ switch_authoritative_pointer
→ erase_old_material
→ local_commit
```

每一步必须以 reserved id、前一步已核实的耐久结果和当前 authoritative state 为 precondition。新 pointer 未成为权威状态前
不得 erase；erase 已接受后不得切回旧 pointer。客户端本地 commit 丢失时只能查询并重放相同
terminal result，不能重新上传或重新 erase。

`revoke` 第一步的 proposal 接纳和命令终局是两个边界。治理 Station 接纳计划中的完整 `ak.device.revoke` Event 与 covering RealmCommit 时，必须在同一 durable commit 保存 `revoke_proposal{proposal_event_id,covering_commit_id}`；此时只形成不可变 pending proposal，不得据此计入 `accepted_steps` 或当成 revoked。worker 对 exact proposal 的效果作终局裁决时，必须将 closed `revoke_command_outcome` 与 `accepted_steps[0]`（accepted）或 `terminal_outcome=aborted|expired`（rejected）原子提交。已有 proposal 的 abort/expiry 不得省略 rejected 结果；尚未接纳 proposal 的 abort/expiry 不得制造结果。相同终局精确重放读取首次保存的资源，不同终局或不同 Commit 引用为冲突。该结果只在完整事务、Event、Commit、PCR current 与本地结果 ledger 的同一快照连接核对后进入 [`device-lifecycle.md` §5.5.3](../crypto-media/device-lifecycle.md) 的 `device_status` 折叠；RealmCommit 的十成员签名对象保持不变。

`erase_old_material` 只由 durable transaction worker 执行，没有公开 self HTTP operation；外部客户端
不得调用、驱动或重放 erase。worker 从已保存 plan 构造内部请求，包含 transaction/request/plan digest、
预留 `erase_confirmation_digest`、一条完整 `secret_storage` binding 与当前 `authority_commit_id`，
不携带也不接受 `AuthorizationLease`。worker 必须先验证：

1. transaction当前next step确为`erase_old_material`；
2. 唯一new series及其`ak.key_backup.active_series` Event已accepted且仍是authoritative；
3. target恰等于prepared plan的old backups，任何active、未计划、缺digest或额外backup均拒绝；
4. transaction 未过期、Account 仍 active、`authorizing_device_id` 仍是该 Account 的 current non-revoked device，且
   请求所冻结 basis 确认的 `secret_storage` pointer（new series 与 `series_pointer_version`）仍逐字是当前 authoritative
   pointer、current `current_device_generation_ref` 未变。任一检查失败都必须在擦除前停线；不得用 create 时的普通
   session 快照绕过执行时 current/revocation 检查。

请求中的 `authority_commit_id` 是首次判定所在 cut 的 provenance，随请求字节冻结，**不**要求等于续跑时的 PCR head：
按 [`key-management.md` §7.6](./key-management.md) 的陈旧判据，同一 PCR stream 上此后出现的无关 Commit 不使已冻结
的 old-backup 清单陈旧，worker 续跑 MUST 复用首次请求字节；只有 pointer 或 generation 改变才在擦除前停线。

worker 的内部 durable 执行结果按 backup kind 保存 `series_records[]`。storage partial failure只能把尚未擦除项标为
`pending`或`failed_retryable`；已经擦除项必须单调保持`erased`，重启或精确重试不得复活、改写
digest或重新加入remaining集合。`request_digest`是完整erase request canonical bytes的SHA-256；
相同transaction id但request digest不同必须`duplicate_conflict`。每个result的
`erased_backups ∪ remaining_backups`必须恰等于plan中该kind的`old_backups`，两集合不相交且均按
backup id canonical升序；`status=erased`当且仅当remaining为空，`reason_code`只允许
`failed_retryable`。只有该series的全部planned objects都确认擦除时，status才可为
`complete`并返回`ak.schema.backup_series_erase_confirmation.v1`。confirmation只含create时已固定
的transaction/request/plan与series bytes；receiver 必须核对最终 request/plan 引用，并按本节
非循环 projection 重算且逐字等于预留 `erase_confirmation_digest`；只有完整 durable confirmation
核对成功后才可原子追加 accepted erase step。partial outcome、单对象 DELETE 响应、日志或本地 flag
都不能推进该 step。

## 4. 故障点要求

实现 conformance 必须在每个远端副作用前后注入 crash、response lost、coordinator restart、
同 id 同/不同 bytes 重试、staged secret 丢失与 terminal replay。任一故障点都只能观察到一个
transaction 和一组 reserved ids。

上述矩阵由`ak.vector.security_transaction.resilience.v1`、
`ak.vector.security_transaction.recovery_terminal_commit.v1`与
`ak.vector_group.security_transaction.v1`固定；runner必须覆盖Recovery A/B与Rotation唯一 `secret_storage`
backup kind，并输出canonical结果digest供第二个独立实现对拍。Recovery 分支还必须证明提交前无任何权威结果可观察、
提交后全部结果同时可观察，且不存在 completed 但未 RealmCommit 或 pending 但已 verified 的中间状态。

正例：pointer switch 已成功但响应丢失；重试查询同一 transaction，继续 erase。

反例：response lost 后创建新 transaction 并生成第二个 revoke Event id；即使最终状态相同也
违反审计与幂等合同。
