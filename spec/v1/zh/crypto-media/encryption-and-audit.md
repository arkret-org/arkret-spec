---
title: Encryption and MLS
status: candidate
normative: true
stability: v1
updated: 2026-09-16
sidebar:
  label: Encryption & MLS
---

## 0. 规范语言

本文中的规范关键字按 [conformance/normative-language.md](../conformance/normative-language.md) 解释。

## 1. 目标

Arkret 使用 RFC 9420 MLS 为 Realm 或 Circle 的应用内容提供端到端加密。治理 Station只验证和保存公开
group transition、authority commit、recipient delivery queue 与路由 metadata；它不得取得 epoch secret、
KeyPackage init private key、Welcome plaintext、private ratchet tree、application plaintext 或成员 private state。

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
MUST NOT 折叠为签名 principal、裸 DID 或 handle。

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
2. 验证每条 delivery 的 recipient、claim、Commit、scope、epoch、ciphertext 与 producer proof；
3. append Commit 的 RealmCommit并更新 public group result；
4. 为每个 recipient durable enqueue Welcome并建立 replication outbox。

任一 delivery 缺失、重复冲突、超限或绑定错误时事务零写入。事务 durable 后才可返回 Commit accepted；
此时 sender 立即安装 staged post-state，不等待 recipient ACK。Station 按 `welcome_id` 重试投递，recipient durable
保存并完整验证 Welcome 后幂等 ACK。response 丢失时 caller 只能重放 byte-identical submission或按 Commit EventId 查询。

#### 2.2.1 MLS Group Admin 推导

Realm 与 Circle 的 committer 权限来自 current capability、membership 与 policy。管理权限不由 leaf index、首个 sender、
设备在线状态或 UI role 推导。Circle 的 group 与 Realm group 独立；一个 scope 的 committer 权限不扩张到另一个 scope。

MLS leaf 的归属与 Proposal 的 target MUST 使用完整 ActorId。两者 MUST NOT collapse 到签名 principal：同一
principal 在不同 Station 上的 Account 是不同 Actor，remove/update 的目标因此 MUST 按完整 ActorId 匹配。
minimal-metadata Realm 的 Realm-local pairwise actor 不是例外：它在 Realm 内的状态同样以完整 ActorId 为键，
只有两处封闭的 Realm 外匹配点（consent peer 与 KeyPackage claim）使用 `(realm_id, principal_id)`，因为该分支
的 `did:key` principal 已经把这一对固定下来。

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

#### 2.4.1 Membership 与 Epoch 不一致窗口

治理 Station为每个 MLS scope维护单调 `key_access_revision`。current membership、leaf endpoint authorization、
决定未来 epoch key取得者的 policy 或 scope terminal 状态改变时 revision严格增加。revision 未被 current Commit覆盖时，
scope 是 `epoch_update_required`，Station MUST 拒绝新的 encrypted application Event 与 Add submission。

不存在 advisory 降级窗口。remove先 commit时旧 epoch新消息立即失败；消息先 commit时它是 remove前合法历史。

### 2.5 MLS authority binding

每个 scope 的 public current result 是：

```text
MlsGroupCurrent {
  effective_scope
  genesis_event_ref
  current_mls_commit_event_ref
  epoch
  current_key_access_revision
  covered_key_access_revision
  public_tree_ref
}
```

#### 2.5.1 固定 GroupContext binding

RFC 9420 GroupContext extension `0xF1C0` 使用 deterministic CBOR 编码唯一固定的 v1
`MlsGroupBinding`：

```text
{
  effective_scope,
  base_group_state_ref,
  previous_epoch,
  next_epoch,
  key_access_revision
}
```

未知字段、缺字段、indefinite-length CBOR、非最短整数、重复或乱序 map key均拒绝。Genesis 的 epoch transition为
`0 -> 0`；Commit 必须 `next_epoch = previous_epoch + 1`。binding 的 scope、base、epoch与 revision必须逐字段匹配
Station 的 current public state和 Commit payload。

**提案形态就是同一个 binding（normative）**：`proposed_group_genesis_binding` **不是第二套 binding 概念**，
它就是上面这个最小 `MlsGroupBinding` 在**尚无已接受 Genesis 时的提案形态**——同样的成员、同样的封闭编码、
同样的 `0 -> 0` transition。因此：`0 -> 0` 的 group key-access revision 查询在目标 scope 尚无 accepted Genesis
时 MUST 携带精确的提案不可变 binding，缺失以 `mls_genesis_binding_proposal_required` 拒绝且不产生 proof 或
cache 条目；提案与签名 Genesis binding 不一致、与并发胜出的 Genesis binding 不一致，或在已有 accepted Genesis
之后仍然携带，均以 `mls_genesis_binding_proposal_mismatch` 拒绝，落败方 MUST 丢弃该 proposal-bound proof，
针对胜出的不可变 binding 重新无提案查询，MUST NOT 复用旧查询或 cache 条目。实现 MUST NOT 为提案态另立
schema、另设成员或另走一条 binding 校验路径。

#### 2.5.2 Send gate 与 self-heal

encrypted application Event携带 `epoch`、`group_state_ref` 与 `key_access_revision`。Station 仅在三者匹配
current `mls_group` result且 producer current-authorized时提交。revision不一致返回
`epoch_update_required`。任一 active、获权客户端可以从 current public state和 desired roster构造 repair Commit；
同一 base 上只有第一个合法 Commit成功 CAS。

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

producer proof覆盖 delivery中除 proof 自身外的完整 canonical object，并绑定 exact Commit EventId、recipient endpoint、
claim ref与ciphertext digest。Station在 Commit transaction中验签；recipient在解密前再次验签和核对。

#### 2.6.2 KeyPackage 使用边界

每个 package全局单次使用。实现 SHOULD短期发布并及时补充 inventory；复用 init key 或把 package当长期身份凭据均不合规。
package私钥泄露可能暴露对应 Welcome，不能靠过期时间撤销已捕获 ciphertext。

### 2.7 Minimal-Metadata E2EE Realm

minimal-metadata scope可使用 Realm-local pairwise Actor与method，但不得为了 public tracker额外披露 Principal、Account、
Device或Realm外 locator。pairwise identity、credential与leaf必须由该 profile既有证明验证；这不改变 Commit/Welcome
原子事务与 key-access revision。

### 2.8 AAD 与 current checkpoint 的唯一性

AAD只绑定 exact signed Event与其引用的 public group revision。客户端不得以当前时间、当前UI状态或另一个 stream head
替代该 revision；同一 ciphertext在不同 scope、Event kind、sender或group state下验证必须失败。

### 2.9 Reaction routing window

encrypted reaction可携带已登记的最小 routing context，使 Station在不解密正文时路由到目标 Event。routing token必须
绑定 target、scope、sender与有界时间窗；它不授予读取或写入权限。

### 2.10 内容 scheme

v1 只有 standard RFC 9420 application encryption。每个 application ciphertext由当前 epoch secret按 RFC 9420生成；
协议不保存或分发额外 epoch content root。

### 2.11 Agent Event 双绑定

Agent发送 encrypted Event时，同时验证 Agent current runtime authorization与其 MLS leaf credential。两项必须指向同一
Agent actor与current method；任一撤销都会推进相关 scope的 `key_access_revision` 并阻塞旧 epoch新写入。

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

#### 5.1.2 创建 transaction

Genesis 与需要加入的初始 endpoint deliveries 使用同一 `MlsCommitSubmission` transaction 语义；没有 recipient 时
`welcomes=[]`。Station 提交前验证 creator current authority 与初始 roster。

**客户端本地 durable transaction（normative）**：创建方在本地为一个待加密的 effective scope 维护**恰好一条**
durable 记录，其逻辑键是 `(owner_actor_id, effective_scope, operation)`，`operation` 固定为 `mls_genesis`。
`owner_actor_id` MUST 是完整 ActorId（普通人类创建者含 `station_id`），`effective_scope` MUST 是 §5.1 的
canonical typed scope，不能是页面路由、展示用 Realm 名或裸字符串别名。该 transaction 只适用于
`effective_scope.kind` 为 `realm` 或 `circle`；`sidecar` scope 保持 §2.5.1 的独立握手契约，客户端 MUST NOT
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

原子切点（normative）：

- selector 在 `ak.realm.create` 的**第一次网络副作用之前**、任何 `0 -> 0` 治理查询之前、任何依赖 selector 的
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

成员、设备或policy变化先推进 `key_access_revision`，随后客户端提交覆盖该revision的Commit。revision推进立即阻塞旧
epoch新密文，不等待Commit产生。

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
- Welcome与Commit同一authority transaction durable enqueue；
- KeyPackage只在专用ledger；
- fixed GroupContext binding只含scope、base、epoch transition与key-access revision；
- 新member/endpoint只从Add/Welcome epoch获得密文能力；
- governance Station handoff迁移public state、claim records与Welcome outbox，不迁移member secrets。

## 持久恢复的完成条件（normative）

sender只有在exact submission已由current governance Station确认为accepted/duplicate并耐久保存post-Commit private state后，
才把本地transition标为完成。recipient只有在Welcome、producer proof、claim binding、Commit lineage与完整RFC 9420处理均
成功且private state耐久保存后才ACK。任何崩溃恢复都重放相同ID和bytes，不生成平行transition。
