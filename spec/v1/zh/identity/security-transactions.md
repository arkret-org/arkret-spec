---
title: 安全事务资源
status: candidate
normative: true
stability: v1
updated: 2026-09-15
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
  terminal_result
}
```

`kind` 是 `recovery` 或 `security_rotation`。`terminal_result` 缺省表示事务仍活动；存在时其
`result` 是 `completed | aborted | expired`，并且是终态 kind 的唯一真相源。coordinator 是否已经开始
某一步、重试次数与 lease 只属于本地 durable step-attempt ledger 或运行遥测，不得序列化或持久化为协议
phase/state。客户端是否需要设备签名必须由 `terminal_result` 缺省且
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
重算并返回的固定 SHA-256、跨 Realm CAS 坐标；它不跟随任何 Realm 的 `digest_algorithm`。create request
不得携带该值，`prepared_plan` 内也不得携带自身 digest，计算时没有排除字段的隐式规则。
每个 `prepared_event_unit` 的 wire 形态固定为 `{request,request_digest}`：`request` 必须独立满足
`EventsSubmitBatchRequestBody`，`request_digest` 必须等于其 digest suite 对 `RFC8785_JCS(request)` 的计算结果。
该 unit 的 operation 固定为 `ak.self.events.command.submit.v1`，request schema 固定为上述 DTO，destination 与 audience
都从父 transaction 的 `account_id.station_id` 取得；这四项与 canonical request bytes 是构造时的 computed view，
不得作为平行 wire 输入或 durable 真相源。coordinator 必须以同一 `JCS(request)` bytes 执行和持久化。
`accepted_steps[]` 的每项固定为
`{prepared_material_digest, acceptor, output_ref, output_digest, accepted_at}`；数组位置按下述固定步骤表
唯一决定 step kind，整个数组必须是连续前缀，不能跳步、重排或为同一步记录第二个 digest。活动事务的下一步
等于 `steps(kind)[accepted_steps.length]`；resource 不重复序列化该派生值。
`acceptor` 是接受该步骤的稳定 participant identity，closed 为
`{kind: principal, principal_id: DidCoreId} | {kind: device, device_id: DeviceId}`；服务 participant
必须写入永久 Arkret core identity，不得写入 W3C 裸 DID、transport URI 或 mixed identifier string。

共同不变量：

1. 第一个不可逆副作用前固定 `transaction_id`；
2. 在同一原子持久化中固定 canonical request bytes/digest、closed typed prepared plan/digest 和
   全部公开 Event/object/series/ticket id；
3. 同 id + 同 canonical bytes 返回 byte-identical 已记录 result；
4. 同 id + 不同 bytes 返回 `duplicate_conflict`；
5. store 分别保存唯一 typed prepared plan/canonical bytes、首次 result 与每步 accepted output，
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

SecurityRotation `create` 只接受完整 typed plan；Recovery `create` 只接受 closed typed `recovery_intent`，
typed prepared plan 一律由 coordinator 在 §2.1 的专用 prepare transaction 中派生，客户端不得提交一份已经填完的
`prepared_plan`。两种 `create` 都必须在一个 durable transaction 中保存 canonical request
bytes/digest、typed prepared plan、自己重算的 plan digest、全部 reserved ids 与初始 resource，然后才能执行第一个副作用。
Recovery create 还必须只接受属于同一 Station-local AccountId、已 verified 且尚未绑定其它 transaction 的
recovery session，并在同一 durable commit 中 CAS 绑定该 session；SecurityRotation create
不依赖 recovery session，必须验证当前 AccountId 的 high-risk action authority。`continue` 的 `request_digest`、
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
`ak.schema.security_rotation_local_commit.v1`。RecoveryTerminalCommit 内的 Seal 与 receipt 都由 replacement device
以同一冻结 device key 自行签发，服务端不得伪造、代签或返回带占位签名的 draft；local commit 同样由客户端从权威
transaction resource 复制 `transaction_id`、`request_digest`、`prepared_plan_digest` 与 prepared plan 的
`local_commit_digest`，再加入本地 `device_id` / `committed_at` 构造。两类 artifact 都是 caller-authored material，
不需要也不存在第二个服务端 supply operation。wire 上不携 `attestation_digest`；外层 Ed25519 签名输入固定为
`RFC8785_JCS({step, output_ref, transaction_id, transaction_request_digest, prepared_plan_digest,
attestation_digest})`，其中投影成员 `attestation_digest := SHA-256(JCS(artifact))` 由签名方与 verifier
各自从同载体 `artifact` 重算填入，不从 wire 读取；wire 上也不携字段名清单。coordinator 必须重算 artifact
digest，验证 outer attestation；recovery 还必须分别验证 Seal 的 notary signature transcript 与 receipt 自己的
device signature transcript。其它 step 对应非 terminal-ready resource 的 attestation 必须拒绝。`get` 是
response loss、restart 与跨设备续跑的权威进度查询，不得从短期 HTTP idempotency cache 合成。
当 coordinator-owned prefix 已完成而最终 client-attested step 尚未提交时，resource 仍不携带
`terminal_result`；它不会被误判为 completed，因为完整 accepted prefix 与 `result=completed` 的 terminal
result 仍是成功终态的必要条件。

旧 `recovery_session.command.complete` 不属于 v1。recovery session 只负责建立 verified 证据；
完成投影只能由接受 `commit_recovery_unit` 的 RecoveryTransaction coordinator 原子写入，不能存在绕过
prepared plan binding 和 accepted-step ledger 的第二个公开完成入口。

## 2. RecoveryTransaction

RecoveryTransaction 的基础 `identity_model="pcr_policy"`。它是一次有条件的最终成交：coordinator 先冻结“若本次恢复成功，
唯一允许签署的材料是什么”，replacement device 在本地签好首个新 generation Seal 与 recovery receipt，再由唯一终态请求
一次交齐；服务器要么把 Seal、两条 Event、generation、设备、session 与 transaction 全部提交，要么一个都不提交。
`prepared_plan.binding` 固定 account authority pair 与本地 PCR lineage、recovery session/policy、replacement device、
re-anchor/authorize Event ids、re-anchor batch receipt id、首枚 Seal id 与 terminal receipt id；plan 其余字段固定
previous/result PCR generation、ordered re-anchor unit、首枚 Seal 的 closed intent 与 exact `UnsignedSeal` body，
不含 DID publication。`identity_model` 只在内嵌 binding 出现一次。

基础步骤严格为：

```text
create/prepare -> commit_recovery_unit
```

`commit_recovery_unit` 位于 accepted-step index 0，是唯一 client-attested step，也是本事务唯一的 accepted step。
两条 Event 的提交不构成独立 accepted-step：它们只作为 transaction-private prepared material 保存，在最终原子提交前
MUST NOT 进入 canonical accepted Event store、outbox 或任何 current projection。Recovery 因此没有 coordinator-owned
prefix，也不存在第二个可独立接受的 Seal 提交步骤。

Account Authority / transport signature 不构成内容 authority；coordinator 不持有 recovery/device private key，
不生成、更改或代签 Event 与 Seal。

### 2.1 create 同时完成专用 prepare，但不产生恢复效果

Recovery create request 是 closed typed `recovery_intent`，固定本事务的 `transaction_id` / `account_id` /
`expires_at`、verified recovery session、replacement device、previous/result generation、预留 `terminal_receipt_id`、
两条完整已签 Event 的 `reanchor_unit`，以及首枚 Seal 的 closed intent：`realm_id`、exact non-null `predecessor_ref`、
按 `[reanchor, authorize]` 顺序的 `unit_event_digests` 与冻结 `hlc`。create request MUST NOT 伪装成已由客户端填完的
最终 `prepared_plan`。

coordinator 必须在同一个 durable prepare transaction 中：

1. 锁定并验证 exact AccountId、verified recovery session、policy/proof snapshot、PCR predecessor/frontier、
   generation CAS、candidate key/PoP 与两条 Event；
2. 用专用 recovery execution mode 重放完整历史与 recovery unit，生成 exact `UnsignedSeal`，其唯一 committed
   `command_result.unit_event_digests` 必须恰为 `[reanchor_digest, authorize_digest]`；
3. 固定 derived `first_generation_seal_id`、完整 unsigned body、`reanchor_batch_receipt_id`、`terminal_receipt_id`、
   canonical create request bytes/digest、closed typed prepared plan/digest，以及
   `(realm_id, replacement signer slot, predecessor_ref)` 的耐久 signing-slot fence；
4. 原子持久化 transaction 与 session-to-transaction binding 之后才返回 resource。

该提交只是冻结唯一可签材料。它 MUST NOT 插入 accepted Event、提交 Seal、推进 generation、激活设备、消费 session
或写 terminal result。签名 body 一旦对客户端可见，fence MUST NOT 因超时、重启或失败而释放去准备同一 signer slot 的
另一份正文；过期事务只能永久拒绝该旧 prepared body，重新恢复必须使用新的 session 与新的 replacement device/key slot，
不得复用或改写旧 plan。该 fence 与普通 PCR `ak.self.seals.command.prepare.v1` 的 signing-slot fence 同规则，见
[`../authz/event-auth-state-resolution.md` §8](../authz/event-auth-state-resolution.md)；但 recovery 的 prepare 是
transaction create 的内部合同，不经由普通 seal prepare operation。

`prepared_plan_digest = SHA-256(RFC8785_JCS(prepared_plan))` 因而覆盖完整 unsigned Seal。`request_digest` 只覆盖
caller 的 canonical create intent；二者职责分开，不形成哈希自引用。

`ak.root.identity.recovery_session.command.submit_proof.v1` 与新 RecoveryTransaction 的 session 绑定都以
session FSM 为准：目标 session 不在 `pending` 状态——无论已 `verified` 还是已 terminal
（`completed` / `rejected` / `expired`）——MUST 以顶层 `recovery_session_not_pending`（409）拒绝并零副作用。
terminal session 不可变；该判定是 session 状态门，不携带独立 reason code。

### 2.2 唯一终态载体

`ClientStepAttestation.artifact` 的 Recovery 分支是闭合 `ak.schema.recovery_terminal_commit.v1`：

```text
RecoveryTerminalCommit {
  first_generation_seal,
  recovery_receipt
}
```

其中 Seal 的 unsigned body MUST 与 prepared plan 中冻结的 `first_generation_seal_body` 逐字节相等，只允许补上由
replacement device method/key 生成的 canonical `id` 与 `notary_signature`，且该 `id` MUST 等于
`binding.first_generation_seal_id`。该 `notary_signature` 的签名输入是 `ak.seal.commit.v1` commit transcript，
其 `view` 由 PCR 的 f=0 唯一确定为 `0`，见
[`../authz/event-auth-state-resolution.md` §8](../authz/event-auth-state-resolution.md)。recovery 的专用 prepare
不经普通 seal prepare operation，因此不存在返回 `view` 的响应；签名方与 coordinator MUST 各自按该规则取 `0`，
MUST NOT 另行猜测，也 MUST NOT 为携带这一可派生量新增 wire 字段。

RecoveryReceipt 继续由同一 replacement device 签名，并 MUST 新增并签入
`first_generation_seal_id`，同时保持对 `transaction_id`、`transaction_request_digest`、`prepared_plan_digest`、
两条 Event、re-anchor batch receipt、generation 与 session/policy/proof 的既有绑定。

外层 `ClientStepAttestation.step` 固定为 `commit_recovery_unit`，`output_ref` 仍为预留的 `terminal_receipt_id`，
派生 `attestation_digest` 因此等于 `SHA-256(RFC8785_JCS(RecoveryTerminalCommit))`，同时覆盖 Seal 签名与 receipt。
这里没有循环：plan 只含 unsigned Seal；Seal id 由 unsigned body 派生；receipt 在取得 request/plan digest 与 Seal id
后签署；外层最后签完整 terminal artifact。

RecoveryReceipt 的 `completed_at` 是 replacement device 签署“若全部校验通过则完成”的作者化时间，不是数据库已经提交
的证明。它只有与同一原子提交生成的 `ak.schema.recovery_completion_attestation.v1` 配对后，才是可消费的 completed
receipt。

“若全部校验通过则完成”意味着该时刻 MUST NOT 晚于 Station 的实际提交时刻。Station 在 `commit_recovery_unit` 的重验阶段
以自身线性化提交时刻比较 `recovery_receipt.completed_at`：晚于该时刻时 MUST 以确定性 reason
`recovery_receipt_completed_at_after_commit` 拒绝整笔提交并执行零权威写入。规范不定义任何 skew 上界；Station MUST NOT
签发未来时间戳的 attestation，也 MUST NOT 阻塞等待客户端时钟追上。该拒绝与其它重验失败同属“未曾接受的请求”：它不推进
`accepted_steps`、不写 `terminal_result`、不消费 session、不冻结任何 step outcome，修正时钟后可用**新的** receipt 重新提交。
已冻结为 step outcome 的异 bytes 仍按共同不变量 4 返回 `duplicate_conflict`。因此 attestation 的
`completed_at` MUST NOT 早于 receipt 的 `completed_at` 是自动满足的不变量，而不是需要服务端迁就客户端时钟的约束。

coordinator 在 `commit_recovery_unit` 接受与完成 ledger 同一原子提交中生成
`ak.schema.recovery_completion_attestation.v1`。其 Ed25519 签名输入固定为
`RFC8785_JCS({schema, transaction_id, transaction_request_digest, prepared_plan_digest, account_id,
recovery_session_id, terminal_receipt_id, terminal_receipt_digest, terminal_commit_digest,
replacement_device_id, device_authorization_event_id, first_generation_seal_id, result_model_generation_ref,
completed_at})`，wire 上不携字段名清单。`terminal_commit_digest` 等于上述完整 `RecoveryTerminalCommit` 的 SHA-256
digest；`completed_at` 是服务端线性化提交时间，MUST NOT 早于 receipt 的 `completed_at`。
其中签发 attestation 的 coordinator 就是 `account_id.station_id`；transaction 资源与 attestation
均携同一完整 `account_id`，两者都不携独立 coordinator 字段，coordinator 只能从该 `account_id` 取得，不得再由两个值拼装账号。
Event digest 必须由 suite-bearing `device_authorization_event_id` 解码；修改该 ID 会同时修改派生 digest 并使签名失败。

### 2.3 唯一原子提交与可观察性

`commit_recovery_unit` MUST 在同一个本地数据库事务、同一组行锁与同一 generation/predecessor CAS 下完成全部动作：

1. 重验 transaction/request/plan、session binding、live expiry/policy、historical PCR、Event signatures、
   Seal predecessor/delta/body/id/signature 与 terminal receipt/outer attestation，并按 §2.2 比较
   `recovery_receipt.completed_at` 与本次线性化提交时刻；
2. 插入并确认两条 Event 及其唯一 committed command result；
3. 接受并发布 exact first-generation Seal；
4. 推进 generation、fence 旧 generation，并把 replacement device 投影为 `active + verified + current generation`；
5. 消费 recovery session；
6. 追加唯一 accepted terminal step，生成并保存 completion attestation，把 RecoveryTransaction 写成 completed；
7. 写入同事务 outbox/audit/receipt 结果。

数据库提交前，任何普通读面 MUST NOT 观察到上述任一权威结果；提交后 MUST 同时观察到全部结果。任一步失败或进程在
commit 前崩溃都整体回滚。MUST NOT 先调用现有 Event/Seal store 提交、再用补偿事务更新 recovery rows；这些属于同一个
本地 Station 权威边界，不适用 Saga 补偿。

### 2.4 operation 与 grant 边界

verified recovery session 的 post-proof closed operation set 不变；完成 RecoveryTransaction 本身继续只使用
`ak.self.security_transaction.command.create.v1`、`ak.self.security_transaction.resource.get.v1` 与
`ak.self.security_transaction.command.continue.v1`，其余既有 read/unlock operation 不变，见
[`../sync/service-http-binding.md` §2.1.2a](../sync/service-http-binding.md)。普通
`ak.self.seals.command.prepare.v1` / `ak.self.seals.command.submit.v1` 继续要求 current accepted device，
MUST NOT 加入 recovery grant。Recovery 的专用 prepare 是 transaction create 的内部合同，完整 Seal 只允许通过 terminal
`continue` 的 `RecoveryTerminalCommit` 进入原子提交；普通 Seal submit、私有 endpoint、第二个 transaction 或 closed DTO
扩展字段均 MUST NOT 成为旁路。

DID method operation 的发布继续使用 `POST /_arkret/root/identity/submit-did-operation`，但它不是
RecoveryTransaction 的步骤，也不得进入 recovery binding、prepared plan 或 accepted-step ledger。
恢复 authority 只来自已接受的 PCR policy/session 与 unit 内闭合 proof；DID current root 不得绕过该策略。

### 2.5 幂等、竞争与失败终局

- 同 transaction id + byte-identical intent 的 create MUST 返回相同 request digest、prepared plan、unsigned Seal
  body/id 与 plan digest；异 bytes 为 `duplicate_conflict`。
- terminal response 丢失或服务重启后，同一 canonical `continue` MUST 返回首次保存的 completed resource、receipt 与
  completion attestation；检查 stored outcome MUST 先于“session 已消费”这类 live-state 拒绝。
- 同 transaction 的 forged/changed Seal、receipt、outer signature 或 plan binding 零权威写入；未曾被接受的请求修正
  后仍可提交，已经冻结为 step outcome 的异 bytes MUST `duplicate_conflict`。
- 两个 recovery unit 竞争同一 previous generation 时，只有在同一原子 CAS 中提交 Seal 的 transaction 是 winner；
  loser MUST NOT 留下 accepted Event、verified device、consumed session 或 completed transaction，也 MUST NOT
  quarantine 或撤销 winner。
- commit 后到达的 winner exact retry 只重放原结果；rival unit MUST 取得确定性的 generation/predecessor conflict 或
  terminal aborted 结果，不得生成第二个 committed Seal。
- raw signed recovery Seal 在没有 matching completed RecoveryTransaction 与 completion attestation 时，MUST NOT 经
  普通 Seal submit、federation 或 history replay 取得 accepted finality。

上述矩阵由 `ak.vector.security_transaction.recovery_terminal_commit.v1` 固定。

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

`prepared_plan.backup_rotations[]` 的内嵌 binding 是每项 reserved series/object refs 的唯一 source，并同时保存 encrypted material与
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
`ak.self.keys.backup_series.command.erase.v1`。request 必须携带 transaction/request/plan digest、
预留 `erase_confirmation_digest`、两条完整 binding、high-risk
`AuthorizationLease(action=ak.self.keys.backup_series.command.erase.v1)` 与必要CBS bundle。服务端必须先验证：

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

上述矩阵由`ak.vector.security_transaction.resilience.v1`、
`ak.vector.security_transaction.recovery_terminal_commit.v1`与
`ak.vector_group.security_transaction.v1`固定；runner必须覆盖Recovery A/B与Rotation双
backup-kind，并输出canonical结果digest供第二个独立实现对拍。Recovery 分支还必须证明提交前无任何权威结果可观察、
提交后全部结果同时可观察，且不存在 completed 但未 Seal 或 pending 但已 verified 的中间状态。

正例：pointer switch 已成功但响应丢失；重试查询同一 transaction，继续 erase。

反例：response lost 后创建新 transaction 并生成第二个 revoke Event id；即使最终状态相同也
违反审计与幂等合同。
