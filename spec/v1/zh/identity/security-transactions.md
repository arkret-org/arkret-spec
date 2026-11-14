---
title: 安全事务资源
status: candidate
normative: true
stability: v1
updated: 2026-11-09
---

# 安全事务资源

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

Arkret v1 只定义两个 Station 内安全事务：`RecoveryTransaction` 与
`SecurityRotationTransaction`。它们是 Station 内的 durable orchestration，不得泛化为可执行 Saga/Plan DSL。

`authority-commit-log` §5.1 的登记式 Event 原子单元可以复用请求固定、事务内持久化、重放与恢复机制，
但本资源仍是固定 durable workflow。已完成的不可逆步骤不会因后续失败整体回滚；不得将它加入 `atomic_unit_registry` 或执行 caller 自选原子步骤。

## 1. 两类资源与共同边界

Human coordinator、PCR接纳与设备终局属于完整 AccountId 的 owning Station，不存在独立Human PCR governor。部署拆进程/拆库必须保持公开原子终局与exact replay；不得共享Coauth/Coland数据库、私钥、配置或业务crate。内部journal/outbox/恢复属于既有部署私有通道，不新增公开RPC、role或通用Saga/Plan DSL。

`SecurityTransaction` 是 closed union：Recovery仅有已完成结果 `{transaction_id,kind:"recovery",account_id,created_at,recovery_receipt,completion_attestation}`；SecurityRotation保留 durable prepared_plan/digest、accepted_steps连续前缀与terminal_outcome。Recovery没有公开prepared/pending/readiness资源，也没有accepted_steps；确定性失败沿operation Problem，临时不可用保留exact重试。

### 1.1 标准操作面

| operation | HTTP | 精确职责 |
| --- | --- | --- |
| `ak.self.security_transaction.command.create.v1` | `POST /_arkret/self/security-transactions` | recovery分支只携 `{kind,recovery_receipt}`，一次完整原子提交；rotation分支冻结原typed plan |
| `ak.self.security_transaction.resource.get.v1` | `GET /_arkret/self/security-transactions/{transaction_id}` | 取原Recovery完成结果/原Problem或Rotation进度；不以缓存猜终局 |
| `ak.self.security_transaction.command.continue.v1` | `POST /_arkret/self/security-transactions/{transaction_id}/continue` | 仅SecurityRotation的local_commit，拒绝Recovery且零副作用 |

每个首次业务副作用前 MUST 固定 caller 分配的 transaction_id、完整 canonical请求与全部Event/object身份；同完整账号/ID同bytes精确重放，异bytes duplicate_conflict。mnemonic、seed、设备私钥、明文keybag和MLS secret不得进入资源。终态不得新增副作用。

SecurityRotation独立保留：完整typed prepared_plan、`prepared_plan_digest=SHA-256(JCS(prepared_plan))`、accepted_steps连续前缀及每步真实耐久效果。prepared_event_unit只用于Rotation，固定operation/request/route/audience的computed view；其request_digest按原已登记suite对exact JCS(request)计算。worker拥有revoke/upload/switch/erase四步，客户端只观察，不能用continue驱动。下一步只由kind与prefix长度推导，不增加phase/state/readiness字段。create需fresh高风险Account认证，冻结authorizing_device_id；continue只在local_commit就绪时核request/plan摘要、expected_accepted_step_count及唯一client_attestation。该outer signature仍绑定step、output_ref、transaction/request/plan及从artifact重算的digest；local_commit verifier在同一accepted PCR cut使用当前已授权设备key。任何不可逆步骤后expiry只能停新步骤并继续原恢复规则，不能回滚或换ID。

## 2. RecoveryTransaction 单次提交

### 2.1 唯一完整原签意图

Recovery create MUST 只接受schema定义的完整 `RecoveryReceipt`。receipt按closed shape携transaction/receipt ID、完整Account、expires_at、recovery_session_id、原session_grant_ref/JKT、policy/version、trust_domain、replacement Device、identity model、previous/new generation、原proof_summary、`recovery_unit={predecessor_ref,events:[reanchor,authorize]}`和原本地恢复结果。两slot MUST 是已有EventAdmissionSubmission：完整producer Event及适用approval_signatures。不得丢弃原审批、注入任意步骤或把receipt proof替代独立producer proof。

receipt是唯一canonical意图，不另携recovery_intent、prepared_plan、session snapshot digest或terminal outer wrapper。EventId直接来自两slot，不重复携镜像。客户端 MUST 先本地耐久保存完整冻结receipt与candidate私钥再发网络；未知结果不得改签、重加密、换Event、换transaction或恢复旧checkpoint。

producer Event先依现有规则构造和签名，只能用其已登记payload的预分配ID；不得依赖receipt摘要/签名或后发Commit。随后replacement key签receipt：`UTF8("ak.identity.recovery_receipt.signature.v1\n") || JCS(receipt excluding signature_proof)`，所有实际存在optional字段和原审批证据自动签入。`receipt_digest=sha256:lowercase_hex(SHA-256(JCS(full signed receipt)))`只在签后计算，不放回receipt。没有transaction_request_digest/prepared_plan_digest或未定义session摘要。

receipt的completed_at仍是设备签署意图时间，不证明实际完成；本地backup/Welcome/outcome声明不证明普通群或PCR内容history-ready。

### 2.2 资格、原子接纳与终局

verifier MUST 从原已verified RecoverySession冻结的candidate key验receipt和两producer proof，不能先要求新key已在accepted设备目录。receipt/session/本次exact内省之间的完整Account/Station/PCR lineage、SessionGrantRef/JKT、policy/proof/context、candidate key/Device、generation、challenge及时间 MUST 逐项相等。签名method按原account binding和candidate overlay核验，不能从caller自报DID URL授权，也不要求基础policy恢复发布DID。

历史proof冻结不能替代首提交时当前policy显式撤销、session/grant有效性、Account允许恢复状态、generation/head与原授权payload digest等门。new generation MUST 为当前previous的checked successor；predecessor MUST 为原session允许的当前PCR head，不得自动把旧Event移到新head。

owning Station MUST 在唯一安全接纳点以完整Account/transaction/session锁及generation/head CAS，验证完整原签和审批，然后逻辑原子地保存两Event、同PCR stream位置连续且不同的两RealmCommit、generation advance、replacement active state、session consumption/transaction绑定、outbox、完成结果与CompletionAttestation。公开边界上全部同时可见，任一步失败均无部分恢复效果。两Event各一Commit，不得共享commit_id。

RecoverySession和该终局只有owning Station一个durable owner；Account Authority不得另建可写session副本。部署私有拆分不以共享数据库或跨库事务为前提，不得把未知内部状态当成功。启用内容恢复时，原authorize Commit同切点建立content-history §11.3的episode/fence意图；后续库存和客户端解密不改变该身份终态，也不借旧session续期。

同ID的exact canonical signed receipt（包括signature bytes）只接受一次，返回相同Commit/C/receipt；只比较不含签名的业务字段不充分。未认证或无效签名不得替别人占ID。首次确定性领域失败可固定原请求/Problem以拒同ID换意图；临时依赖失败不制造accepted或永久失败终局。已完成原结果的读取先核当前reader资格，不重跑首次expiry/政策或改写历史；尚未accepted而原窗口过期仍拒绝。

### 2.3 Completion 原件与独立 Standard 签发

CompletionAttestation保留原service Ed25519证明，签名输入为`JCS(complete attestation excluding signature_proof)`。它绑定完整已签receipt的terminal_receipt_digest、transaction/account/session/receipt/Device/generation、真实连续CommittedEventRef和actual completed_at；删除request/plan摘要。签发方必须为原account.station_id，不能凭caller公钥或裸accepted布尔成立。

`ak.gate.account.command.issue_recovery_completion_grant.v1` 只接受 `{terminal_receipt,initial_session,accepted_device_possession_proof,canonical_request_digest}`；事务、Account、Device及generation从receipt推导。C由Account Authority经同Station既有部署内认证通道向原Station一跳承运并独立核验，不要求客户端先拿到C，不能借此新增公开发现/operation或读取对方数据库。

首次completion需fresh Bound AccountHandoff和HTTP DPoP。允许新短期holder key不同于原recovery grant，但原receipt/session的历史ref/JKT不变。原replacement identity key必须在current-device判定点对本次新holder作AcceptedDevicePossessionProof，purpose=`recovery_completion_grant_issue`，保留issue分支request/account-handoff字段和≤300秒窗口。`session_intent_digest=SHA-256(JCS({receipt_digest,initial_session}))`；proof签完整closed对象仅省signature；最后`canonical_request_digest=SHA-256(JCS(request excluding canonical_request_digest))`，无自引用。fresh handoff/HTTP DPoP/initial_session/proof holder JKT必须一致，Device/audience/current generation/revocation必须全部成立。

issuer业务主键 MUST 为`(issuer_id,operation_id,完整AccountId,receipt.transaction_id)`，原fullsigned receipt摘要、首次成功请求bytes、允许的原账号deactivated→active和独立Standard outcome在其自身事务中原子固定。request_id不能被用来重发同一completion；资格未验不能占位，临时取材失败不永久占用。PCR事务与issuer事务分别完成，不共享Coauth/Coland数据库。

exact replay重验fresh handoff同Account/同holder和当前replacement资格，返回相同U/ref；原body中的PoP窗口/旧handoff digest是已验历史，不与新handoff强行逐字匹配。原issuer链已expired/revoked/superseded沿既有session_grant_replay_*终态，不补发或重复reactivate。若原issuer成功但旧DPoP私钥丢失，AA账号已active，走普通accepted-device issue而非改写原transaction。

PCR成功而response丢失，即使旧recovery grant已到期、AA账号仍deactivated，仍可fresh认证并重交本地冻结receipt，让服务取原C完成原账号恢复；不得要求先Standard后GET C，不延长/升级旧recovery grant。已active且有Standard的用户可exact self GET。尚未accepted且旧session过期必须新恢复，历史C不授现在资格。

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
