---
title: Encryption and MLS
status: candidate
normative: true
stability: v1
updated: 2026-10-03
sidebar:
  label: Encryption & MLS
---

## 0. 规范语言

本文中的规范关键字按 [conformance/normative-language.md](../conformance/normative-language.md) 解释。

## 1. 目标

Arkret 使用 RFC 9420 MLS 为 Realm 或 Circle 的应用内容提供端到端加密。治理 Station只验证和保存公开
group transition、authority commit、recipient delivery queue 与路由 metadata；它不得取得 epoch secret、
KeyPackage init private key、Welcome plaintext、private ratchet tree、application plaintext 或成员 private state。

v1 不定义 `minimal_metadata_realm` MLS profile，也没有以 Realm `schema_refs` 激活 profile 的通道。旧实现专属的 pairwise author identity 与一小时 epoch 上限不是现行可声明的安全合同，不能由客户端私有判定重新启用或向用户宣称已由治理 Station 强制执行。带旧标记的持久 Realm 状态按 [Realm schema 集合规则](../models/realm-and-space.md) fail closed；所有现行 Realm 仍须满足本章的通用 MLS 验证与治理准入义务。

## 2. MLS 与 authority commit

### 2.1 KeyPackage 与服务发现

KeyPackage 只存在于 endpoint 与其 Account Station 的专用 publish/claim/revoke ledger，不是共享 Event。
claim 是单次使用的 durable reservation，绑定 recipient actor、device 或 Agent runtime、目标 effective scope、
package digest、有效期与 requester。Station 在 claim 时验证 endpoint current authorization、ciphersuite 与 package
signature；失败只返回不泄露库存细节的 `claim_failed`。

只有 [`mls-ciphersuite-registry.json`](../../artifacts/registry/mls-ciphersuite-registry.json) 登记且处于 active 的 MLS ciphersuite 才能
进入 wire。publish、claim 与 Commit submission MUST 各自拒绝未登记或已停用的 ciphersuite，实现 MUST NOT 依次
尝试多个 suite 后择一通过，也 MUST NOT 在本地把外部 suite 标识改写成登记值。

recipient endpoint 与 KeyPackage 的持有者身份是**完整 ActorId**：account 分支携带包含 `station_id` 的
AccountId，service 分支携带 `service_id`。claim、Welcome delivery 与 leaf credential MUST 逐字保留该完整身份，
MUST NOT 折叠为签名 principal、裸 DID、device id 或 handle。RFC 9420 `BasicCredential.identity` 的 v1
字节合同唯一固定为 `UTF8(RFC8785_JCS(actor_id))`，其中 `actor_id` 必须是
[`common-ids.schema.json#/$defs/actor_id`](../../artifacts/schemas/common-ids.schema.json) 的闭合实例；不得改用
摘要、展示串或任一分量。KeyPackage upload 与 claim record 的 `actor_id`、Welcome delivery 的
`recipient_actor_id` 和 BasicCredential 解码出的对象 MUST 逐字段相等。`device_id`、Agent verification method
及 authorization Event id 仍是独立 endpoint/authorization selector，不是 ActorId 的替代表示。两条真实
LeafNode/KeyPackage 逐字节向量见
[`mls-keypackage-endpoint-kat-fixture.json`](../../artifacts/fixtures/mls-keypackage-endpoint-kat-fixture.json)，其策略与拒绝矩阵由
`ak.vector.mls.keypackage_actor_and_ciphersuite_closure.v1` 封闭。

### 2.2 Commit 与 Welcome

`ak.mls.commit` 是 producer-signed、authority-committed 共享 Event。Welcome 是
`MlsWelcomeDelivery` recipient object，不是 Event，不进入 Realm stream，也不获得独立 finality。

Add transition 使用一个 closed `MlsCommitSubmission`：

```text
MlsCommitSubmission {
  commit_event
  welcomes[]
  idempotency_key
}
```

每条 delivery 至少包含 `welcome_id`、`realm_id`、`effective_scope`、`commit_event_ref`、
recipient actor 与 endpoint、`keypackage_claim_ref`、canonical ciphertext 和 producer proof。客户端在首次网络
副作用前原子保存 exact Commit Event、post-Commit private state 与全部 delivery material。

治理 Station MUST 在同一数据库事务中：

1. 验证 Commit Event、current membership/policy、base group revision 与 RFC 9420 public transition；
2. 验证每条 delivery 的 recipient、Commit、scope、epoch、ciphertext 与 producer proof；recipient 由本 Station 托管时
   另按本地 claim ledger 验证 claim；
3. append Commit 的 RealmCommit并更新 public group result；
4. 为本 Station 托管的 recipient durable enqueue Welcome 并在其 claim ledger 记录写入 Welcome 绑定（[`device-lifecycle.md` §9.2.3](./device-lifecycle.md)），建立 replication outbox；跨站 recipient 的 Welcome
   写入指向其 routing service 的那条 outbox intent（见下文「跨站 recipient」）。

任一 delivery 缺失、重复冲突、超限或绑定错误时事务零写入。事务 durable 后才可返回 Commit accepted；
此时 sender 立即安装 staged post-state，不等待 recipient ACK。Station 按 `welcome_id` 重试投递，recipient durable
保存并完整验证 Welcome 后幂等 ACK。response 丢失时 caller 只能重放 byte-identical submission或按 Commit EventId 查询。

**跨站 recipient（normative）**：治理 Station 对每条 delivery 以 `recipient_actor_id` 按
[`../models/common-fields.md` §4.2](../models/common-fields.md) 的封闭规则投影 routing service。投影为其它 Station 的
recipient 是 current joined 成员，其 routing service 必然属于该 Commit 的 committed-replication 目标集
（[`../sync/federation.md` §4.1.1](../sync/federation.md)）；治理 Station 没有该 recipient 的 claim ledger（claim
destination 是 recipient 的 Account Station），因此在接纳事务内只验证第 2 项中除 claim 以外的全部绑定，并把该
delivery 原样写入指向该 routing service 的 outbox intent。该 intent 的 `committed_replication` item 除 source
Event 与 `RealmCommit` 外携必填 `genesis_event_ref` 和 `welcomes[]`：前者是治理 Station 在原 Commit 接纳
cut 从该 effective scope、`mls_group_id` 的已接受 Genesis provenance 冻结的唯一 Genesis EventId，后者恰为
该 service 托管的 recipient 的全部 delivery，按 submission 中的顺序；
目标集中没有该 service 时整个 submission 以不带 reason 的 `failed_precondition` 零写入。成员 Station 是这些 claim 的
destination，它在保存该 item 的同一 replica 事务内，按
[`device-lifecycle.md` §9.2.3](./device-lifecycle.md) 对治理 Station 规定的同一组绑定以本地 ledger 复核每条 delivery 的
claim 与 destination receipt，并把通过复核的 Welcome 写入各自 recipient endpoint 的本地 queue、在本地 claim ledger 记录写入同一 Welcome 绑定；Commit replica 与这些
Welcome 同时 durable，不存在只见 Commit、有效 Welcome 仍待另行投递的窗口。复核失败的 delivery 永不入队、只进受限
audit；它不阻止 Commit replica 保存，因为该 Commit 已被治理 Station 接纳，拒绝它只会让成员站对整条 stream 失去副本。
Commit replica 已由 `ak.peer.committed_event.read.scan.v1` 或先前尝试保存时，同一 item 的重放仍在一个事务内补写
尚未入队的 Welcome 并返回 `duplicate`。复制写入的 Welcome 与本地 Welcome 同队列、同 ACK-only 删除规则；它计入该
endpoint 的容量但不因容量被拒绝：[`../sync/client-sync.md` §10.1](../sync/client-sync.md) 的容量前置限制属于首次接纳
边界，而跨站 Welcome 的数量已由成员站自己的 claim 发放（单次使用、限速）约束。

#### 2.2.1 MLS Group Admin 推导

Realm 与 Circle 的 committer 权限来自 current capability、membership 与 policy。管理权限不由 leaf index、首个 sender、
设备在线状态或 UI role 推导。Circle 的 group 与 Realm group 独立；一个 scope 的 committer 权限不扩张到另一个 scope。

MLS leaf 的归属与 Proposal 的 target MUST 使用完整 ActorId。两者 MUST NOT collapse 到签名 principal：同一
principal 在不同 Station 上的 Account 是不同 Actor，remove/update 的目标因此 MUST 按完整 ActorId 匹配。
v1 没有任何例外：不存在只用 `(realm_id, principal_id)` 匹配 leaf 归属或 Proposal target 的分支。

#### 2.2.2 公开握手契约

`realm` 与 `circle` 两类 effective scope 的 MLS 握手面按本节的封闭契约执行。本节与
[`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) 的
`x-arkret-public-handshake-contract` 注解逐键对应，两侧 MUST 保持一致。

1. **wire 形态**：Proposal 与 Commit 进入 wire 的输入 MUST 是完整的 RFC 9420 `PublicMessage`
   形态 `MLSMessage`。治理 Station MUST NOT 接受 `PrivateMessage` 形态的握手消息，也 MUST NOT
   接受裸 `Proposal` / `Commit` 对象、裁剪后的片段或 producer 自行摘要出的替代表示：它验证的
   public transition MUST 出自它自己解析的那份 wire bytes。
2. **membership MAC 的验证角色**：`PublicMessage` 的 membership MAC 只有持有该 epoch
   `membership_key` 的**成员**能验证。治理 Station 不是成员，它 MUST NOT 取得 `membership_key`
   或任何成员 secret，因此 MUST NOT 把 membership MAC 当作准入判据——它只验证 §2.2 列出的公开量。
   成员在本地 MUST 验证 membership MAC。
3. **被消费 Proposal 的 leaf provenance**：Station MUST 为每个 accepted Commit 持久保存它实际
   消费的 Proposal 集合，以及每条 Proposal 的精确 leaf provenance（目标 leaf、该 leaf 的完整
   ActorId 与 Proposal sender）。该 provenance MUST 只从第 1 项的公开 wire bytes 导出，
   MUST NOT 依赖任何成员 secret，也 MUST NOT 由 Station 推断或补全。
4. **Remove+Add 永远产生新 provenance**：先 Remove 再 Add 同一 ActorId 时，即使新 leaf 的
   `(完整 ActorId, credential, signature key, leaf 位置)` 元组与被移除的 leaf 逐字相同，它也是
   **一条新的 provenance**。实现 MUST NOT 以元组相等为由复用、合并或省略前一条 provenance
   记录，也 MUST NOT 据此认为该成员的密文读取能力连续：§2.4 的「只从自己的 Add/Welcome epoch
   起获得读取能力」不变。
5. **application 与 Welcome 的保护不变**：握手面公开不改变应用内容与 Welcome 的保护形态。
   应用内容仍按 §2.3 的 RFC 9420 encrypted envelope 发送，Welcome 仍是 §2.2 的加密 recipient
   object。实现 MUST NOT 以「握手已公开」为由降低这两者中任何一者的保护。
6. **握手不新增披露**：公开握手只使用本节已经列出的公开量，MUST NOT 为了让 Station 读懂
   握手而额外披露 Principal、Account、Device 或 Realm 外 locator。
7. **Sidecar 走独立契约**：`sidecar` 形态的 effective scope **不适用**本节契约，它按
   [`../models/sidecar.md`](../models/sidecar.md) §6 保持自己独立的 MLS 绑定与握手契约。
   实现 MUST NOT 把本节的 wire 形态、provenance 持久化义务或验证角色默认套到 sidecar scope 上。
   §6 显式规定 Sidecar 在自己的受限披露与参与者 authority 门内采用完整 `PublicMessage`，由非成员
   Station 验证实际公开 transition 并冻结 inline provenance，成员验证 MAC；它不继承 Realm／Circle
   committer 权限或 creator-bootstrap transaction。机器合同为独立的 `x-arkret-sidecar-handshake-contract`。

**v1 consumed Proposal 的唯一来源（normative）**：共享 Event 只有 `ak.mls.genesis` 与
`ak.mls.commit`，Proposal 仅内联于后者，见 [`authority-commit-log.md` §9](../sync/authority-commit-log.md)。
`ak.mls.commit` 的 RFC 9420 `Commit.proposals[]` 中任何 `ProposalOrRef::Reference` 均为
`unsupported_feature`、整笔零写入；治理 Station 不得从临时 Proposal store、current tree 或 Welcome
补造它的 signed source。治理 Station 从完整、已验签的 Commit `PublicMessage` 按
`Commit.proposals[]` 原 wire 次序，从零计数冻结每个内联 Proposal 的 ordinal、精确 TLS `Proposal`
body bytes、实际 Member sender 的完整 ActorId 及该 Proposal 的目标。内联 Proposal 的 sender
是该 Commit 的 sender，必须由 accepted base public tree 对照签名 leaf 解析，且等于 signed
Commit Event 的 `actor_id`；Add 的目标 ActorId 和 leaf signature key 必须由该 Add KeyPackage 与
已验 post-Commit public tree 唯一对应。Remove+Add 即使目标元组相同，仍以新的 accepted Commit
Event ref 和 ordinal 构成新 provenance。PSK 无 leaf target，不得为它伪造目标。以上冻结与
Event／RealmCommit／public group current 在同一接纳事务完成；拒绝时四者均不写入。

**Welcome 后的完整 leaf authority 取证（normative）**：接收方不得用 RFC `BasicCredential.identity`、leaf
位置或自己的 KeyPackage claim 推断其它已占用 leaf 的 endpoint 授权。治理 Station 在原 accepted Commit
事务冻结每条 Add 的 consumed Proposal、目标 ActorId、leaf signature key 与 Commit 坐标；这不改变跨站
recipient claim 由其 Account Station 在 committed-replication 事务核验的既有准入分工。该 recipient Station
只有在按 [`device-lifecycle.md` §9.2.3](./device-lifecycle.md) 核验 exact claim、destination-signed receipt、
当时 endpoint authorization、winning Commit 与 Welcome 绑定，以及已认证治理 peer body 中与该 Commit
同一 replica cut 保存的 `genesis_event_ref` 后，才能从同一 replica cut 耐久生成并签署
`mls_add_authority_attestation`，连同可幂等重发的 outbox 原子保存。recipient 不得从当前 tree、group id、
`base_group_state_ref` 或无权读取的 prejoin Genesis 猜出该 ref；缺失、非唯一、与已持有 immutable group
provenance 冲突或重放时改变 ref 均零写。same-Station recipient 在原治理接纳事务直接从相同已接受 Genesis
provenance 冻结该 ref，并与本地 Welcome／claim 原子签署同形证明，不依赖 peer row。它通过
`ak.peer.mls.command.attest_add.v1` 向治理 Station 提交；治理 Station 核对签名 Station 恰为该 Welcome
recipient ActorId 的 Account Station、exact accepted Commit／Welcome、已冻结的 Proposal provenance、
leaf key／ActorId／endpoint 与原 claim receipt 的 digest，才将这条历史 Add 证明耐久安装。治理 Station
不得因 attestation 尚未到达而回退或改写已接纳 Commit，也不得凭超时后的 claim ledger、当前设备投影或
caller 自报字段补造证明。same-Station recipient 在原 claim／Commit 同事务生成同形证明，不需要向自己发 peer 请求。
peer attestation 请求的完整 `claim_outcome` 仅供治理 Station 核验原 destination-signed
`claims_digest`、目标 `claim_record_digest` 与 attestation 字段；它不进入 roster read，也不得泄露同一
claim batch 里未加入该 group 的其它 KeyPackage。证明签名输入分别是
`UTF8("ak.mls_add_authority_attestation.v1\n") + JCS(attestation 去掉 signature)` 和
`UTF8("ak.mls_roster_authority_manifest.v1\n") + JCS(manifest 去掉 signature)`，签名 key、算法、
历史方法解析与其它 Station receipt 一致，未定义第二种签名编码。请求中的 attestation 与 claim outcome
必须核对 exact claim id、receipt 与从 KeyPackage bytes 重算的 leaf signature key；只信任
`claim_record_digest` 或 receiver 自报的 leaf key 不足以安装证明。
`claim_record_digest` 必须是 `sha256:` 加上 `SHA-256(JCS(exact keypackage_claim_record))` 的小写十六进制；
治理 Station 从传入 `claim_outcome.claims[]` 按唯一 `claim_id` 选记录，先按既有规则重算全数组
`claims_digest` 并验证原 receipt，再重算该记录 digest。重复或缺失 `claim_id`、receipt 与 outcome
非同一份首次接纳结果，均不得安装 attestation。

治理 Station 首次安装 Add attestation 时 MUST 使用已验证的 recipient Station same-core 服务路由取得完整
`AuthenticatedServiceResolution`，按原 claim `claimed_at` 与 attestation `attested_at` 分别验证历史
`assertionMethod`、Station 身份与两份签名，并把该完整 method-native resolution closure 与 exact Add
attestation 在同一持久事务冻结。`roster_add_record.attestor_resolution` 是这份已验原件；
`service_id` MUST 等于 `attestation.attestor_station_id`，`service_kind` MUST 为 `station`。
首次取证不得从裸 `attestor_station_id` 或签名 `kid` 的 DID 托管域猜测 Station URL；`kid` 只选历史
verification method，不授予当前服务路由。已冻结 resolution 是历史验签材料，MUST NOT 被客户端当作
当前业务投递 endpoint。治理 Station 对每条 Add 在受权 roster read 中原样返回该 closure，并与 Add
attestation 保留至同一历史 cut 不再可读；重放同一 attestation 不得替换旧 closure，缺失、损坏、
历史方法或任一原签名无效时整份 roster `revision_unavailable`。

`ak.self.mls.read.roster_authority.v1` 经成员的 Account Station 用
`ak.peer.mls.read.roster_authority.v1` 向治理 Station 取得同一 accepted group／epoch cut 的完整历史
provenance。两端均须在读取时 current 与目标 accepted cut 对完整 ActorId、effective scope、membership、
history 与 policy 做授权；曾经是成员但已离组者不得仅凭历史身份读取。任何本应位于该 cut 的 Add 证明
缺失、签名无效、冲突或超过保留范围，已授权请求整份结果统一 `revision_unavailable`，
不返回部分 roster、缺项数或可枚举的原因；无权或不可见目标统一 `not_found`。
每条历史 Add 的完整 attestor resolution 仅随这条受权记录披露，不提供按 Station ID 独立枚举的读面；
虽然 service resolution 本身可公开取得，该记录揭示某个 scope 的历史 attestor 拓扑，故必须服从上述
相同的 current／target cut、scope、history、policy 与 retention 门。客户端 MUST 对每条 closure
独立验证完整 method-native 历史、`service_id`／`service_kind`，并在原 `claimed_at` 与
`attested_at` 验原 receipt 与 attestation 的历史 `assertionMethod` 和签名；不允许用 manifest
签名代替 recipient 的两份历史签名，也不允许用当前 DID Document 代替原历史 key。
结果由治理 Station 对 exact scope／group／Genesis／target Commit／epoch、Genesis payload 中不变的
`group_info_ref` 与 `ratchet_tree_ref`、完整记录总数与全量 JCS digest
作 domain-separated 签名；分页只传输同一冻结集合，客户端须收齐、验签并重算 digest，拒绝重复、跳页或
不同 cut。两条 Blob ref 必须从 exact accepted Genesis payload 取出，不得从当前 epoch 的 public tree、
Welcome、调用方输入或缺证据的历史投影反推；治理 Station 在签名每页 manifest 前核对，缺原始依据时
整份 roster 为 `revision_unavailable`。epoch 0 的 `target_commit_event_ref` 与 `authority_head_commit_event_ref` 均填写该 Genesis
Event ref；其它 epoch 的目标 ref 必须是产生目标 epoch 的 accepted Commit Event，head ref 是签发时
同一 group 的最新 accepted Commit Event。冻结集合先放唯一 Genesis 记录，再按 accepted Commit 的
stream position 递增、同一 Commit 中 consumed Proposal 的 wire 顺序放每条历史 Add 记录。治理
Station 在签 manifest 前按完整 canonical JSON 响应的 2 MiB 上限确定页边界：每页取从下一个
未返回记录开始、在该上限内可容纳的最长连续前缀，记录数为 1..8；不得截断单条或跳项。
`page_count` 是按该确定性边界得到的页数，不由 `ceil(total_records/8)` 推算。计算页边界时须计入
最终签名 manifest、`page_index` 与 `next_cursor` 的编码大小；签名后若最终页超限，必须重算并
重新签名，不能发送超限响应。
`records_digest` 必须是 `sha256:` 加上 `SHA-256(JCS(上述完整有序 roster_record 数组))` 的小写
十六进制。opaque `cursor` 只标识该已签 manifest 的下一页、下一条记录位置和调用方；治理 Station 须重新检查读取权限，
并在当前 head 与 manifest 的 `authority_head_commit_event_ref` 不同时拒绝续页，不得混合两个版本。
`attestor_resolution` 是 `roster_add_record` 的必填成员，因而与 exact Proposal、attestation
一起计入上述全数组 digest，由治理 manifest 签名绑定。请求没有调用方选择的 page size；服务端
必须按最终 2 MiB 响应上限自动选择完整记录前缀。若一条完整记录连同必需的签名 manifest 与
分页 envelope 仍超限，已授权请求 MUST 整份 `revision_unavailable`，不得裁剪 closure、返回部分
roster、跳项或让客户端改用从 `kid` 推导的 URL 取证。
每条 Add record 的 `consumed_proposal_ordinal` 是该 accepted Commit `proposals[]` 中从零开始、
计入所有 Proposal kind 的原位置；`sender_actor_id` 是上述已验 Member sender 的完整 ActorId；
`proposal_wire_b64u` 是该位置**内联** RFC 9420 `Proposal` body 的精确 TLS bytes 的无填充
base64url，不是独立 `MLSMessage`、`PublicMessage` 或合成 ProposalRef。它作为已接纳 signed Commit
的派生历史证明输出，不是治理 Station 可接纳的裸 Proposal 输入。治理 Station 必须核对 record
中的 body、ordinal、sender、Commit Event ref 与冻结事实逐字相等，并核对 Add KeyPackage 的完整
ActorId／leaf signature key 与 recipient attestation 及已验 public tree 一致，才可纳入签名 manifest；
缺失、重复 ordinal、顺序更改或任何不匹配使已授权的整份 roster read 为 `revision_unavailable`。
客户端验签 governance manifest 和每个 recipient attestation，重算全量有序记录 digest，并从已验
`proposal_wire_b64u` 的 Add KeyPackage 对照 attestation 的 ActorId／leaf signature key。治理
Station 的签名 manifest 是这些 body／ordinal／sender 与已接纳 Commit 关系的历史权威证明；
它只在上述原事务冻结和签发前逐项核对后才可签署。历史 Commit Event 可能早于该成员的 `since_join`
可读范围，因此 roster 安装不要求另行获权读取每笔原 Event，也不得绕过 history policy 取得它；
若成员另有该 accepted Commit Event 原字节，则仍须与 Event 内的 Commit 对应 ordinal 对照。
客户端不得把一条 body 当作未经签名的独立治理输入，也不得从 current tree 猜取它属于哪个历史 Commit。
每条记录只携历史 provenance、完整 ActorId、endpoint／authorize Event ref、leaf signature key
及原 claim receipt 的可验证绑定，**不携 leaf index**。客户端只从经 digest 校验的 RFC GroupInfo／tree
取得 occupied index，再按 leaf key 与 provenance 一一匹配；Remove+Add 即使全部身份／key／位置相同
也必须用不同创建 Commit 识别。不得返回 private tree、MLS secret 或服务端推断的 leaf DTO。
治理 Station 须将已安装的签名历史证明及其完整 attestor resolution 保留到该 group 的 accepted history 不再可读取；recipient
Station 的原 claim outcome 仍可按 §9 的既有短期规则清理，但其签名 attestation／outbox 须至少保留至
治理 Station 确认持久安装。具体 closed wire、签名和页完整性由
`mls-roster-authority.schema.json` 定义；缺证据时 Welcome 安装保持 `decryption_pending`。

**成员读取 Genesis public material（normative）**：`ak.self.mls.read.group_state_material.v1` 是成员设备
取得同一 accepted Genesis 所承诺 RFC GroupInfo 与 ratchet tree 原字节的唯一成员端操作；它不授予设备
`ak.peer.mls.read.group_state_material.v1` 的服务身份。self 请求必带完整 `caller_actor_id`、Realm、
effective scope、group、epoch 0、Genesis Event ref、两条 content-addressed Blob ref 与可选响应字节上限。
后来加入的成员先取得并验证同一 target cut 的完整 signed roster manifest，再从其中已签名且与 exact
accepted Genesis 核对的 `group_info_ref`、`ratchet_tree_ref` 构造物料请求；这些 ref 不是设备自报的
授权依据。若 manifest 缺失、签名或 selector 不符，设备保持 `decryption_pending`，不得猜 ref、越过
`since_join` 读取 Genesis Event，也不得把当前 epoch 的 `public_tree_ref` 当作 Genesis tree。
请求另必带目标 accepted Commit Event ref 与 epoch，指明此次取证的加入／读取 cut；它们不改变物料始终
属于 epoch 0 Genesis 的事实。Account Station 必须核对 caller 为本次已认证 session 的 exact ActorId，
并在请求时 current 与该目标 cut 分别验证 joined membership、scope 可见性、history 与 policy；无权、已离组、
隐去的 scope 或未知 selector 统一 `not_found`。Circle scope 的 joined membership 在两个 cut 上都指
[`../models/circle.md` §9.1](../models/circle.md) 的 effective 判定：current 须为 Circle `join` 且其
`parent_membership_revision` 仍等于父 Realm 同 cut 的 current `member_state` revision；目标 cut 按
[`../governance/history-visibility.md` §3.1](../governance/history-visibility.md) 的 Circle 历史 cut 连续性求值——不早于当前
Circle join Commit 的目标 cut 由同一 Circle join 实例连续承载，更早的目标 cut 所属 Circle join 实例绑定的父 join 已非
current 时同样 `not_found`。父 Realm 与 Circle 的 position 数值不互认，目标 cut 与 Circle join 只在同一 Circle stream 上比较。它以已认证 Station 身份向治理 Station 转发同一请求，
不得把本地通用 Blob get 或用户自报 ref 当作授权依据。peer 请求带 `caller_actor_id` 时，治理 Station
也须在当前及目标 cut 独立核验该 ActorId 的同样读取资格。此携带 caller 的请求中，调用 Station 的
复制权必须相对于目标 accepted Commit cut 核验，不能以 epoch 0 Genesis 的 Commit 位置拒绝此后才
加入的成员 Account Station；调用者在当前及目标 cut 的资格仍须同时成立。peer 请求不带 caller 仅供
原有服务复制用途，调用 Station 的复制权仍按 Genesis 的 Commit 位置核验，不可替代 self 成员读取。
治理 Station 先从 exact accepted
Genesis 核对所有 selector，再对两份公开原字节分别按 ref 内嵌 digest suite 校验 content address、
对照 RFC GroupInfo/tree 一致性，然后整份返回；Account Station 只转发，设备还须重复 exact selector、
原字节 digest 与 RFC public tree 校验，leaf index 只从验证后的 occupied leaf 导出。任一原字节缺失、
不一致或超出请求上限时整份失败，不得返回部分材料、私有树、MLS secret 或服务端推断的 leaf DTO；
授权已通过但历史材料不可得统一 `revision_unavailable`，续读不得静默改用当前设备投影。

### 2.3 应用载荷加密

effective scope 在没有 accepted `ak.mls.genesis` 时只允许该 Event kind 的明文 payload；Genesis accepted 后 MLS
永久激活，后续应用内容必须使用 standard RFC 9420 encrypted envelope，不能 disable、replace group 或回退明文。
Realm 与每个 Circle 分别激活，父 scope 不隐式激活子 scope。

加密 envelope 是 closed `{version,content_type,encryption_context,ciphertext}`；
`encryption_context` 只含 `epoch`、`group_state_ref` 与已登记 routing context。AAD 从 outer signed Event、
effective scope、Event kind、current public group result 与 sender leaf 唯一重建。wire 不复制 scope、group id、
scheme、algorithm 或 AAD digest。

**Closed pre-encryption header（normative）**：加密前，发送方 MUST 先把上述来源装配成一个封闭的
pre-encryption header，并在加密之后视其为不可变量。该 header 是 AAD transcript 的唯一原像：成员、顺序与
canonical 编码固定，缺字段、多字段、`null` 占位或重新排序都产生不同 AAD，因此都 MUST 被拒绝。header 本身
**不上 wire**：接收方 MUST 从 outer signed Event、effective scope、Event kind、自己验证过的 current public
group result 与 sender leaf 逐字重建它，MUST NOT 采信任何随 envelope 传来的副本。

AAD digest 与 ciphertext digest 各自在固定 transcript 上计算：AAD digest 的原像是重建出的 pre-encryption
header 的 canonical bytes；ciphertext digest 的原像是 envelope 的 `ciphertext` 原始字节。任一不匹配——重建的
AAD 与解密时使用的 AAD 不同、ciphertext digest 与已签名引用不同、`encryption_context` 与 current public group
result 不一致——MUST fail closed：MUST NOT 部分接受、MUST NOT 降级为明文、MUST NOT 换一组 secret 重试，也
MUST NOT 写入任何 typed current 或 outbox 的部分结果。

### 2.4 Sync 与 MLS Epoch

encrypted Event 与 recipient delivery 可以晚于对应 Commit 被客户端观察。客户端可先缓存 ciphertext，但只有在本地
完整验证连续 RFC 9420 transition 并得到目标 epoch private state 后才进入 verified timeline。缺 epoch 时标记
`decryption_pending`；不得丢弃、重排或用 Station public result代替密码学验证。

新 member 或 endpoint 只从其 Add/Welcome epoch 获得密文读取能力。治理 Station不得发送加入前 standard MLS secret，
也不得从 public tree恢复 private state。

**晚到 epoch 材料与审计标记的边界（normative）**：密文先到、该接收端合法 Add/Welcome 与连续 MLS transition 后到，仍按本节普通 `decryption_pending` → verified timeline 路径处理；客户端必须逐项验证原 encrypted Event 的 accepted historical group binding、自己的目标 epoch private state，以及该 Event 所在 stream 的已授权历史可见范围。正常重试不得因为本地材料晚到而被废止，也不得从当前 roster、Event 到达顺序或跨 stream 的裸 `stream_position` 猜原事件时点的成员关系。若既有可验证 MLS/stream 证据不完整，继续保持密文 pending／不可见；持有密钥字节本身不构成访问权。

`ak.audit.accessed{access_kind="e2ee_late_recovery",late_recovery_original_event_id}` 仅是受授权写入的访问审计记录，不是历史成员证明、epoch-to-commit 证明、解密成功回执或客户端展示许可。v1 不登记独立晚到恢复明文展示捷径、强制“旧消息刚解密”横幅或专属 wire 拒绝码；客户端 MUST NOT 因看见此 audit Event、未登记 raw JSON 布尔标记、当前成员列表或旧 history-secret 捷径而解锁原密文。若未来要提供超出本节普通 MLS 路径的晚到恢复，必须另行闭合接收者完整 ActorId、原 Event/effective scope/epoch、跨 stream 已接纳历史基数及受限读取权限；不得借本审计字段隐式补足。

#### 2.4.1 Membership 与 Epoch 不一致窗口

治理 Station为每个 MLS scope维护单调无符号 64 位整数 `key_access_revision`，初始值为 `0`。**唯一写者**是该 scope
自己 stream 上改变 current joined 成员集合的 membership Event（Realm scope 即 Realm stream 上的 `ak.member.state` 与
`ak.invite.accept`）：它被接纳的同一事务把该 scope 的 revision 严格加一，revision 记为该 membership Commit。该字段是计数器，
不是摘要，也没有字符串形式或兼容别名。endpoint authorization（`ak.device.authorize`／`ak.device.revoke`、Agent key
授权与撤销）发生在成员自己的 PCR／Agent stream，policy 变化不改变 MLS leaf 集合，二者都不推进 revision；已撤销 endpoint
自身的发送由 §2.5.2 的 send gate 同 cut 拒绝，其 leaf 由账号拥有者其它 endpoint 以普通 Remove Commit 移除。revision
未被 current Commit覆盖时，scope 是 `epoch_update_required`，Station MUST 拒绝新的 encrypted application Event 与 Add submission。

**Circle 父资格失效与唯一写者（normative）**：父 Realm `leave`／`ban`／rejoin 在 Realm stream 提交，不是 Circle stream
的 membership Event，因此 MUST NOT 推进 Circle scope 的 `key_access_revision`，Circle canonical joined 集合也不变。治理 Station
在 Circle scope 的每次 send gate、Add submission 与 MLS Commit 接纳中，于读取 current `mls_group` 的同一耐久 cut 求出 current
public tree 中完整 ActorId 不满足 [`../models/circle.md` §9.1](../models/circle.md) effective Circle membership 的 leaf 集合。
该集合非空时，scope 同样处于 `epoch_update_required`：新的 encrypted application Event 与 Add submission 以 `failed_precondition`
+ `epoch_update_required` 零写入拒绝，任何 Add 的 target 也必须满足 effective membership；只有 post-Commit tree 不再含这些
leaf 的 winning Commit（其 `covers_key_access_revision` 仍等于未变的 current revision）才解除该状态。Station 不产生 Remove
proposal，repair Commit 按 §2.5.2 由任一 active、获权客户端构造。之后该 actor 的显式 Circle `leave` 改变 canonical joined
集合，仍由它作为唯一写者把 revision 加一，并照常要求 winning Commit 覆盖。两条门互不替代：revision 只记 Circle stream 的
membership Event，失效 leaf 集合只由同 cut 的 effective 判定求得。

**残余窗口（informative）**：endpoint 撤销到 Remove Commit 接纳之间，其它成员仍可在旧 epoch 发送；被撤销 endpoint
若另行取得这些密文，仍能解密。它的 recipient queue 读取与 ACK 在撤销时即被阻断，自身发送被 send gate 拒绝。

不存在 advisory 降级窗口。remove先 commit时旧 epoch新消息立即失败；消息先 commit时它是 remove前合法历史。

### 2.5 MLS authority binding

每个 scope 的 public current result 是：

```text
MlsGroupCurrent {
  effective_scope
  genesis_event_ref
  cipher_suite
  current_mls_commit_event_ref
  epoch
  current_key_access_revision
  covered_key_access_revision
  public_tree_ref
}
```

`cipher_suite` MUST 是 Genesis 已接纳的登记 canonical ciphersuite id，且后续 winning Commit 不得修改它。
签名 snapshot/current MUST 携带该公共值，使 since-join 成员 Station 在没有 prejoin Genesis FullView 时仍能验证 Signal 外层 cipher basis；不得推测或使用 envelope 自述作为授权来源。

#### 2.5.1 固定 GroupContext binding

RFC 9420 GroupContext extension `0xF1C0` 使用 deterministic CBOR 编码唯一固定的 v1
`MlsGroupBinding`：五个公共成员，加上仅 Sidecar scope 必需的两个成员。

```text
{
  effective_scope,
  base_group_state_ref,
  previous_epoch,
  next_epoch,
  key_access_revision,
  participant_authority_digest,   // 仅 Sidecar
  authority_stream_head           // 仅 Sidecar
}
```

`effective_scope.kind=sidecar` 时两个 Sidecar 成员 MUST 同时出现（语义见
[`../models/sidecar.md` §6](../models/sidecar.md)）；Realm／Circle 携带其中任一字段即 `schema_violation`。
`authority_stream_head` 按 UTF-8 字节序排序、去重，最多 64 项。三个整数都限于 `0..2^64-1`。外层 map 的
deterministic-CBOR key 编码字节顺序逐字等于 schema `map_key_order`：`next_epoch`、`previous_epoch`、
`effective_scope`、`key_access_revision`、`base_group_state_ref`、`authority_stream_head`、
`participant_authority_digest`，缺席成员直接跳过；嵌套 `effective_scope` 同样按 RFC 8949 的编码后 key 字节排序。未知字段、缺字段、
indefinite-length CBOR、非最短整数、重复或乱序 map key、trailing bytes、错误 major type、超出整数范围、
声明长度超过剩余输入、`authority_stream_head` 未排序或重复均拒绝，接收方不得规范化后再接受。decoder 在解析前和递归中 MUST 执行共同上限：输入最多
16384 bytes、嵌套最多 8 层、单个 map/array 最多 64 项；超过任一上限都以 `schema_violation` 拒绝，不得按声明长度
预分配无界缓冲区。

Genesis 的 epoch transition为 `0 -> 0`；Commit 必须 `next_epoch = previous_epoch + 1`。binding 的 scope、base、epoch
与 revision必须逐字段匹配 Station 的 current public state和 Commit payload。即使 GroupInfo 签名、ratchet tree、group id
与 epoch 的 RFC 9420 公共校验全部成功，内部 binding 与外层任一字段不等仍 MUST 以
`governance_binding_mismatch` 拒绝，并且不得推进 MLS epoch 或安装 Welcome。

**提案形态就是同一个 binding（normative）**：`proposed_group_genesis_binding` **不是第二套 binding 概念**。
正式 carrier 是 `event-payload.schema.json#/$defs/mls_genesis_binding_proposal_carrier` 的封闭对象：
`event_kind` 固定为 `ak.mls.genesis`，`proposal_kind` 固定为 `group_genesis_binding`，`sender_actor_id` 是完整 ActorId，
`target_scope` 是精确 effective scope，`proposed_group_genesis_binding` 直接引用同一
`#/$defs/mls_governance_binding`。`target_scope` 必须与 binding 的 `effective_scope` 逐字段相等；提案 binding 的
`base_group_state_ref` 为 null，三个整数均为 `0`。因此提案与 Event kind、发送者和目标 scope 都可结构化判定，
同时没有第二份 binding 字段表或第二条校验路径。

在尚无 accepted Genesis 时，消费该本地 carrier 的 `0 -> 0` key-access revision 计算 MUST 使用精确的提案不可变
binding。carrier 缺少 `sender_actor_id`、`proposed_group_genesis_binding` 或任何其他 required member 时，必须先以
`schema_violation` 拒绝且不进入语义校验、不产生证明或缓存条目；v1 不定义 partial/pre-validation carrier。提案与签名 Genesis binding
不一致、与并发胜出的 Genesis binding 不一致，或在已有 accepted Genesis 后仍被提交，均以
`mls_genesis_binding_proposal_mismatch` 拒绝；落败方 MUST 丢弃 proposal-bound 结果并针对胜出 binding 重新计算，
MUST NOT 复用旧请求或缓存条目。该 carrier 是 §5.1.2 客户端本地持久化意图的一部分，不新增 HTTP operation、
服务端持久化记录或对等方可信声明。

历史 replay／恢复必须把 extension 与对应 accepted Event 的历史 binding 比较，而不是与最新 revision 比较。历史
revision 小于 current revision 的材料仍可作为历史记录通过验证，但它不授予 current 发送权；当前发送 gate 仍因未被
winning Commit 覆盖而返回 `epoch_update_required`。

#### 2.5.2 Send gate 与 self-heal

encrypted application Event 携带 `epoch`、`group_state_ref` 与 `key_access_revision`。Station 仅在三者匹配
current `mls_group` result 且 producer current-authorized 时提交。治理 Station MUST 先判定 current scope 的
MLS 状态：确定没有 accepted `ak.mls.genesis`／current group 时，密文 prepare 与 self／peer authority-forward
submit 均 MUST 返回通用 `failed_precondition`（无专用 reason），且不得写入；客户端必须先激活该 scope 或改发明文，
不得 exact retry 期待该密文成功。治理 Station 暂时无法读取自身 current MLS 结果时，两入口均 MUST 返回
`temporarily_unavailable`；仅在未产生 Commit 时允许 byte-identical exact retry。已有 current group 时，
Station MUST 判定 membership／policy／key-access checkpoint 是否已被 winning Commit 覆盖；尚未覆盖时返回
`failed_precondition` + `epoch_update_required`，客户端 MUST 暂停新的 encrypted application Event，等待或由获权客户端
促成 repair Commit，不得对尚不存在的目标 epoch 盲目重新加密。

**发送 endpoint 同 cut 授权（normative）**：实际签名方由本治理 Station 托管时，send gate MUST 在读取 current
`mls_group` result 的同一耐久 cut 判定该发送 endpoint（即其 MLS 发送 leaf 所属 endpoint）的 current authorization，
不等待 Remove Commit：human 设备按 [`device-lifecycle.md` §8.2.2](./device-lifecycle.md) 同站规则读取本地 PCR，
已撤销、撤销待定、generation 被 fence 或未授权时分别以 `device_revoked`、`device_revocation_pending`、
`device_generation_fenced`、`device_unauthorized` 零写入拒绝；Agent runtime 读取本地 current `agent_key`，其
`ak.agent.key.authorize` 已撤销、被替换或过期时以 `capability_denied` 零写入拒绝。跨站实际签名方的撤销由其 account
Station 在转发前按 §8.2.2 判定。该判定先于 `epoch_update_required` 与 `epoch_mismatch`，不推进 `key_access_revision`。若 current scope 已被 winning Commit 覆盖，
但本次发送冻结的 `epoch`、`group_state_ref` 或 `key_access_revision` 与 current `mls_group` result 不符，
MUST 返回顶层 `epoch_mismatch`（HTTP 409）。客户端 MUST 获取并验证 current public group result 与连续 MLS
transition，在取得对应本地 private state 后重新加密，构造新的 prepare／submit 请求；不得把旧 ciphertext 改绑到新
epoch，也不得在原请求的 exact retry 中重新加密。`mls_governance_binding_stale` 只用于解密媒体服务的 join／token
在 current group 尚未覆盖 current `key_access_revision` 时（[`media-service-binding.md` §8.2](./media-service-binding.md)），
不表示本次请求引用了被取代的 epoch。上述 current send gate 不适用于已接受历史
Event 的重放或 peer committed replication；这些材料依其 accepted historical binding 验证。
任一 active、获权客户端可以从 current public state 和 desired roster 构造 repair Commit；同一 base 上只有第一个
合法 Commit 成功 CAS。

#### 2.5.3 GroupContext extension 与客户端验证

普通客户端信任自己 Account Station返回的 committed public current result用于发送 gate，但仍独立验证 KeyPackage、
LeafNode、credential、Commit signature、tree、confirmed transcript、confirmation tag、Welcome、AEAD 和本地 state。
Station 的 acceptance 不证明 recipient已经解密或具有正确 secret。

#### 2.5.4 跨 Station 验证

接收 Station通过 authority bundle找到 current governance Station，验证对应 Realm/Circle stream 的连续
`previous_commit_ref`、RealmCommit signature与 committed Event。缺少同 stream commit prefix或 public transition
material时 fail closed；producer提交的摘要不能补足。

### 2.6 KeyPackage Claim 生命周期

publish、claim、consume、revoke均属于 endpoint ledger。claim success冻结 exact package与 recipient；Commit submission
消费该 claim。重复 exact submission幂等，不同 Commit或recipient复用同一 claim必须拒绝。package expiry、endpoint
revoke或claim timeout只影响尚未被 accepted Commit消费的 reservation。

#### 2.6.1 Welcome producer proof

`producer_proof` 使用 `ak.mls_welcome_delivery_signature.v1`。unsigned projection 是从完整 closed Welcome delivery
删除 `producer_proof` 后的全部实际存在成员。producer 先对其 RFC 8785 JCS bytes 计算带 `sha256:` 前缀的小写
SHA-256 digest，再对 `UTF8("ak.mls_welcome_delivery_signature.v1\n")` 与五成员 signature envelope 的 RFC 8785
JCS bytes 串接值作 Ed25519 签名；`sig` 是完整 64-byte 签名的 86 字符无 padding Base64URL。接收方必须从原始
Welcome delivery 重建 projection、digest、prefix 与完整签名输入，不能信任载荷自报 digest。authority basis 必须解析
`commit_event_ref` 所指 winning `ak.mls.commit` Event 的 exact producer signing authority，并要求
`verification_method` 等于该 producer proof 已验证的方法；治理 Station、recipient 或 claim service key 均不能替代。

producer proof覆盖 delivery中除 proof 自身外的完整 canonical object，并绑定 exact Commit EventId、recipient endpoint、
claim ref与ciphertext digest。Station在 Commit transaction中验签；recipient在解密前再次验签和核对，并以
`ak.self.keys.keypackages.read.claim.v1` 从自己 Account Station 读取 `keypackage_claim_ref` 所指的 exact claim outcome
独立验证 claim 与 receipt（[`device-lifecycle.md` §9](./device-lifecycle.md)）。

#### 2.6.2 KeyPackage 使用边界

每个 package全局单次使用。实现 SHOULD短期发布并及时补充 inventory；复用 init key 或把 package当长期身份凭据均不合规。
package私钥泄露可能暴露对应 Welcome，不能靠过期时间撤销已捕获 ciphertext。

### 2.7 AAD 与 current checkpoint 的唯一性

AAD只绑定 exact signed Event与其引用的 public group revision。客户端不得以当前时间、当前UI状态或另一个 stream head
替代该 revision；同一 ciphertext在不同 scope、Event kind、sender或group state下验证必须失败。

### 2.8 Reaction routing window

encrypted reaction可携带已登记的最小 routing context，使 Station在不解密正文时路由到目标 Event。routing token必须
绑定 target、scope、MLS epoch 与有界时间窗；它不授予读取或写入权限。v1 的 key context 不含 sender：同一
MLS epoch、target、scope、routing window 和真实 emoji 的不同 sender 产生相同 tag，以便 `(target_ref, key)`
跨 actor 聚合 reaction `members[]`／`count`。Station 因此可观察同窗同 target 的等值聚类与频率，客户端与
高隐私部署 MUST NOT 宣称此 tag 按 sender 隔离或隐藏该关联性；Event 的签名 `actor_id` 与权限验证仍须
独立执行，不能从 tag 推断或授予 sender 身份。

### 2.9 内容 scheme

v1 只有 standard RFC 9420 application encryption。每个 application ciphertext由当前 epoch secret按 RFC 9420生成；
协议不保存或分发额外 epoch content root。

### 2.10 Agent Event 双绑定

Agent发送 encrypted Event时，同时验证 Agent current runtime authorization与其 MLS leaf credential。两项必须指向同一
Agent actor与current method；authorization 撤销不推进 `key_access_revision`（§2.4.1），由 §2.5.2 的发送 endpoint 同 cut
授权拒绝该 Agent 的新写入。

## 3. Station 明文边界

Station可以看到 actor、scope、时间、大小、recipient routing与group churn。E2EE不隐藏流量 metadata。任何需要处理
plaintext的服务必须由客户端显式选择并在客户端侧取得内容；base v1不向服务端发布历史 epoch secret或持续解密能力。

## 4. 受控账号与 Agent

Agent、Bot与Ghost使用自己的受限 endpoint key和KeyPackage。controller可以授权或撤销 runtime key，但不得取得或合成
Agent MLS private state。controller需要代表 Agent执行 Commit时，producer proof仍必须满足 Agent delegation合同。

### 4.1 独立 Agent 密钥

默认模式是每个 Agent runtime持有独立签名与MLS endpoint key。暂停或deactivate立即阻塞新 submission；历史 Commit与
application Event仍按原 producer proof审计。

### 4.2 多设备绑定

一个 principal的多个设备是多个 MLS leaves，各自发布KeyPackage并接收自己的Welcome。新增设备不会取得加入前secret。

### 4.3 派生密钥限制

不得从账号root、session secret或其它设备key确定性派生 MLS private key。

## 5. 组员变动与可用性

### 5.1 MLS Group Genesis

`ak.mls.genesis` 是每 effective scope唯一的 producer-signed、authority-committed Event。它创建 canonical group id、
epoch 0 public tree、Genesis Event ref与初始 `key_access_revision`。重复 Genesis、不同 group id或激活后明文写入均拒绝。

#### 5.1.1 Epoch-0 public material

Genesis携带验证 epoch 0所需的 public GroupInfo/tree material及固定 GroupContext binding；不携任何 member secret。

**leaf index 的唯一恢复来源（normative）**：epoch 0 的 leaf index MUST 只从该 accepted Genesis 所承诺的、
经 digest 校验的 RFC 9420 GroupInfo 与 `ratchet_tree` extension 原始字节中恢复，且只读取验证通过的 RFC tree
上**已占用**的 leaf 位置。取材方 MUST 先把拿到的原始字节同时对显式 digest 与 content-addressed ref 逐一哈希
核对，并校验 GroupInfo 与 tree 的一致性，任一不符即整份丢弃，MUST NOT 保留部分结果。leaf index MUST NOT 由
Add 的到达顺序、Welcome 的投递顺序、roster 展示顺序、recipient 列表下标、服务端推断出的 leaf DTO 或任何
proof-bundle leaf 得出；提供方也 MUST NOT 返回 private tree material、成员 secret 或推断出的 leaf DTO。
leaf index 不承载权限含义（§2.2.1）。

#### 5.1.2 创建 transaction

Genesis 经 `ak.self.events.command.submit.v1` 的普通 Event 分支单独提交，不使用 `MlsCommitSubmission`（其
`commit_event.kind` 固定为 `ak.mls.commit`）：epoch 0 的 RFC 9420 group 恰有创建者本人一个 leaf，因而 Genesis
不携 Welcome；其它初始 endpoint 由随后第一条带 Welcome 的 `ak.mls.commit` 加入。Station 提交前验证 creator
current authority 与「roster 恰为创建者」。

**Genesis 创建时间（normative）**：每条 `ak.mls.genesis` 的 payload `created_at` MUST 与外层 Event
`created_at` 逐字相等；两者使用同一个 canonical UTC 毫秒 timestamp，表示同一次 Genesis 创建。
本规则适用于所有 effective scope，包括保留独立握手合同的 Sidecar。创建者 MUST 在冻结 unsigned Genesis core
时只确定一次该值，并同时写入两处；签名、入队、重试与 reload MUST 保持该值和 exact Event 字节，
不得各取一次墙钟或在重试时刷新时间。它不要求 `producer_proof.created_at` 或服务器 `committed_at` 与之相等，
也不引入提交时限、时钟容差或以创建时间判断竞争赢家的规则。
治理 Station MUST 在准入事务产生任何 accepted effects 前验证两字段相等；即使只相差一毫秒，
也 MUST 以不带 `reason_code` 的 `failed_precondition` 零写入拒绝，包含不保存该事务附带的 public Blob、
不占用 Genesis 槽、不写 Event／Commit／current／outbox。跨站转发 MUST 保持原签名 Event，禁止改写任一时间。
消费者在认定 exact accepted Genesis（包括 creator-bootstrap 的竞争赢家）时 MUST 独立重验本规则；
Station 的 accepted 标签不能替代验证。时间不一致的历史 Event 不得被修补或视为合法赢家；
本地保持不可写并报告无效 accepted evidence，不得仅凭该 Event 转入 `superseded` 或再造 Genesis。
JSON Schema 仅验证两处 timestamp 的形状；跨字段相等由 canonical Event-kind registry 的
`genesis_timestamp_contract` 登记为语义准入义务，不能以 payload schema 通过代替它。

Genesis 的签名 payload 必带 `creator_leaf_authority`：声明 epoch-0 唯一 leaf 的 Ed25519 signature key、
创建者 exact endpoint 与该 endpoint 在 Genesis accepted cut 的授权 Event ref。它由 Genesis 的
`producer_proof` 连同其余 payload 一起签署，表达 producer 对该 MLS leaf key 的显式归属绑定；
**不要求** MLS leaf key 与 Event producer signing key 相等。治理 Station 必须核对 producer 自身的
历史签名／endpoint 授权、声明的 endpoint／授权 ref、唯一 public tree leaf 的完整 ActorId 与
signature key，并验证该 leaf 的 RFC 自签名；任一不符以 `failed_precondition` 零写入拒绝。
后来的成员须按 exact accepted Genesis Event／Commit 和历史签名 key 独立重验该绑定；
缺 `creator_leaf_authority` 的旧 Genesis 不得被静默推断或由 current keys lookup 补齐。

**跨站 Genesis 的 public material（normative）**：Genesis 引用的 GroupInfo 与 ratchet tree 是 creator 经
`ak.self.blob.*` 上传到自己 Account Station 的内容寻址 Blob。creator 的 Account Station 不是治理 Station 时，它在接纳
self submit 进入转发队列前从本地 Blob 存储取两份原始字节并按 `group_info_ref`／`ratchet_tree_ref` 各自的 digest suite
核对，缺失或不符以不带 reason 的 `failed_precondition` 拒绝；随后 `ak.peer.events.command.submit.v1` 的
`authority_forward` 在 `event_submission` 旁携 `mls_genesis_material`（两份 unpadded base64url 原始字节）。该成员只对
`ak.mls.genesis` 必带、对其它 kind 禁带，schema 以 Event kind 直接表达；同站 Genesis 读取本地 Blob，不经过该载体。
两个成员各自至多 5592406 个 unpadded base64url 字符，即解码后每份至多 4194304 bytes，两份合计因而不会超过
`ak.peer.mls.read.group_state_material.v1` 的 8388608 bytes 响应上限；任一成员超长或不是 canonical unpadded base64url 均为
`schema_violation`，本载体没有另外的合计上限检查。治理 Station 在任何写入前解码两份字节，按 ref 内嵌 suite 重算 digest，
与 Genesis payload 的 ref 逐字比较，不符以 `digest_mismatch` 零写入。随后按 §5.1.1 验证 RFC 9420 public state，并在接纳
事务内把两份字节作为 public Blob 保存，供其后
`ak.peer.mls.read.group_state_material.v1` 原样提供。exact 重复的 Genesis 返回原 outcome。

**MLS 准入的其它拒绝（normative）**：Genesis roster 不是恰好创建者一个 leaf、Commit 的 Welcome 与其新增 leaf 不
一一对应、`keypackage_claim_ref` 所指 claim 已不再 live、Welcome recipient 不是该 scope 的 current joined 成员等
既有前置条件不成立时，治理 Station 以不带 `reason_code` 的 `failed_precondition` 零写入拒绝；只有 §2.5.1 的
`governance_binding_mismatch` 与重复 Genesis 的 `mls_activation_irreversible` 使用专用 reason，本规范不为上列情形
另立 reason。

**客户端本地 durable transaction（normative）**：创建方在本地为一个待加密的 effective scope 维护**恰好一条**
durable 记录，其逻辑键是 `(owner_actor_id, effective_scope, operation)`，`operation` 固定为 `mls_genesis`。
`owner_actor_id` MUST 是完整 ActorId（普通人类创建者含 `station_id`），`effective_scope` MUST 是 §5.1 的
canonical typed scope，不能是页面路由、展示用 Realm 名或裸字符串别名。该 transaction 只适用于
`effective_scope.kind` 为 `realm` 或 `circle`；`sidecar` scope 按 §2.2.2 第 7 项保持独立握手契约，客户端 MUST NOT
为 sidecar scope 打开该记录。`creator_device_id` 与 `creator_signer_method` 是记录的不可变字段但**不进逻辑键**，
因此同一账号的重载或第二个窗口找到同一条记录，而另一台设备不会静默开出第二次 Genesis。

记录只沿以下已登记箭头前进：

```text
genesis_intent_persisted -> realm_accepted -> governance_result_pinned -> epoch0_state_persisted
  -> genesis_queued -> genesis_accepted -> artifacts_converged -> ready
```

终态为 `ready`（成功）、`rejected`（可回到 `realm_accepted` 重试）、`superseded` 与 `quarantined`。机读真源是
[`mls-creator-bootstrap-transaction-registry.json`](../../artifacts/registry/mls-creator-bootstrap-transaction-registry.json)，
实现 MUST 从该 registry 读取状态、箭头与持久化要求，MUST NOT 从本节散文重新推导。

**钉住的治理证据（normative）**：`governance_result_pinned` 不表示新的 Station proof RPC 或其 outcome。
客户端使用既有 authority 与授权 current 读取面，独立验证 nonce-bound current authority bundle、完整 authority
链、exact accepted scope-create Event／covering Commit，以及覆盖精确 effective scope 的完整授权 current cut。
只有经验证的完整 cut 才能证明该 scope 尚无 accepted Genesis；不完整投影的缺行、HTTP `not_found`、超时或
不可用结果都不能证明缺席。完整 owner ActorId、不可变 creator device／signer 与该 cut 的创建者和 endpoint
授权必须一致。Realm 与 Circle 都核对自身的 accepted create 与所属 scope，不能借父 Realm 或其它 Circle 的材料。

这些已验证证据与原 durable intent 中的 canonical local proposal 在一次 durable commit 中钉住；proposal binding
保持 exact scope、派生 group id、null base 和三个零，不是 Station 签发的证明，不新增 HTTP operation、wire
request／outcome 或字段。未知、未认证、不完整或不一致证据使状态保持 `realm_accepted`，禁止随机材料、上传、
签名与入队。钉住前可用原 selector 和新 transport nonce 重读既有证据；钉住后只复用原证据与 binding，不能
用刷新后的 cut 或 UI 投影静默替换。并发 accepted Genesis winner 进入 `superseded`，仍由原正式准入 CAS 裁定。

原子切点（normative）：

- selector 在 `ak.realm.create` 的**第一次网络副作用之前**、任何治理证据读取之前、任何依赖 selector 的
  随机材料生成之前落盘；
- governance binding 在任何依赖它的 MLS / HPKE 随机材料之前钉住；
- epoch-0 private state、public 原始字节与 exact unsigned Genesis core 作为**同一个恢复单元**提交，且必须早于
  public blob 上传、Genesis 签名与入队；
- exact signed Event bytes 与 outbound queue item 在同一次 durable commit 中建立；
- `ready` 与 send-gate 索引原子发布。

记录停留在 `genesis_intent_persisted` 时，整条封闭 creation intent MAY 在一次原子 durable commit 中被**整体
替换**（自转移 `genesis_intent_persisted_to_genesis_intent_persisted`）；对单个 selector 的部分 patch 不是合法
写入。从 `realm_accepted` 起，以及在任何终态中，该 intent 不可变；要换 selector 只能结束本次尝试并开启新的
attempt generation。

只有 exact accepted Event 证明完成：队列耗尽、HTTP 2xx、duplicate code、UI 效果完成或本地 emitted/submitted
标志都 MUST NOT 被当作完成信号。该记录**永不进入任何 wire**：它 MUST NOT 出现在 `ak.realm.create` payload、
任何 current result 或查询投影、Account Data key、client sync 或 federation 面，也 MUST NOT 被用来让对端相信
另一方的本地状态——Genesis 是否存在、创建者坐标、锁定的 selector 与可写状态一律只由 exact accepted Event 判定。

### 5.2 意图与生效

成员变化先推进 `key_access_revision`，随后客户端提交覆盖该revision的Commit。revision推进立即阻塞旧
epoch新密文，不等待Commit产生。设备与Agent key撤销不推进revision：被撤销 endpoint 的发送由 §2.5.2 同 cut 拒绝，其 leaf
由账号拥有者其它 endpoint 以 Remove Commit 移除。

#### 5.2.1 Commit producer

Committer从current public group state和current desired roster构造完整 RFC 9420 transition。独立 durable transition
意图不进入共享 log；committer失联时另一获权客户端直接构造新的 Commit。

### 5.3 Committer 失联与竞争

同一 base 的并发Commit只有一个authority CAS winner。loser重新读取current result并决定是否仍需transition。

#### 5.3.1 Direct Conversation

Direct Conversation 的两个 participant遵循相同规则；任何一方只在current member、current-authorized且持有可验证本地
group state时提交 Commit。

### 5.5 本地失败

客户端应用 Commit或Welcome失败时保持 `decryption_pending` 并请求重新同步public material；失败不产生共享 Event。
需要修复时提交新的合法Commit。

### 5.6 Epoch 自保推进

实现 MAY依据消息数或时间触发不改变 roster 的 self-update Commit；它仍经过同一 base CAS、GroupContext binding与
authority transaction。

## 6. 离线与延迟到达

离线客户端恢复后先取得current authority bundle、可见 stream heads、public MLS current result与tail，再顺序应用本地
缺少的Commit和recipient deliveries。它不得从snapshot或其它成员取得加入前secret。

## 7. v1 集成要求

- Realm、每个 Circle分别决定是否通过 Genesis不可逆激活MLS；
- shared MLS Event只有 `ak.mls.genesis` 与 `ak.mls.commit`；
- Welcome与Commit同一authority transaction durable enqueue；跨站 recipient 的 Welcome 随同一 Commit 的
  committed-replication item 在成员站同一 replica 事务入队；
- KeyPackage只在专用ledger；
- fixed GroupContext binding只含scope、base、epoch transition与key-access revision；
- 新member/endpoint只从Add/Welcome epoch获得密文能力；
- governance Station handoff迁移public state、claim records与Welcome outbox，不迁移member secrets。

## 持久恢复的完成条件（normative）

sender只有在exact submission已由current governance Station确认为accepted/duplicate并耐久保存post-Commit private state后，
才把本地transition标为完成。recipient只有在Welcome、producer proof、经 `ak.self.keys.keypackages.read.claim.v1` 读取并验证的
claim binding、Commit lineage与完整RFC 9420处理均成功且private state耐久保存后才ACK。任何崩溃恢复都重放相同ID和bytes，不生成平行transition。
