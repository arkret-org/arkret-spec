---
title: Contact & Direct Conversation Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-10-21
see_also:
  - consent-model.md
  - ../crypto-media/device-lifecycle.md
  - ../models/realm-and-space.md
  - ../models/strand-and-message.md
  - ../sync/api-conventions.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按
[`../conformance/normative-language.md`](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

本文定义 principal-scoped Contact 事实、1:1 Direct Conversation 的稳定身份与故障恢复。本文是这些语义的
唯一正文真源；测试矩阵或执行报告只能引用本文，不得建立另一套 authority、wire 或状态机。

## 1. Contact 真相源与主体身份

Contact 与 holder-private 备注、Realm 内 `ak.relation.*`、非 Contact Consent、Direct Conversation binding
互不替代。Contact-based create/send **MUST** 只读取双方各自签发的 directional Contact lineage；
`ak.consent.*` 只服务不以 Contact 为授权依据的路径，**MUST NOT** 为 Contact 或 Personal DM 补授权。

Contact wire 中的 `peer` **MUST** 是 closed discriminated XOR：human、Agent 与其它已登记
principal kind 分支分别携带该分支的完整 stable subject/binding 字段；裸 `peer_id`、未知 kind、分支字段混用
或仅靠显示 handle 推断主体均 **MUST** fail closed。Contact Event 的 signer **MUST** 是 holder-authorized
long-term signer；v1 Contact command 只接受与 authenticated holder 相同的 active human device 或 active Agent runtime。
controller 代 owned Agent 签 Contact Event 的 delegated producer 形态虽有结构定义，但五个 prepare command 无 exact Agent holder 选择载体，v1 MUST fail closed 且零写入；不得从 controller 拥有的 Agent 集合猜测 holder，也不得绕过 reservation 直接提交 Event。session DPoP key、Station key 与 relay key 不得签 Contact Event。

每个完整 holder 对完整 peer 在同一 trust domain 内独立维护跨轮单调的本方操作 `version`，五种 holder 操作均推进它。源 Station **MUST** 在真实确认事务中检查本方前态并严格 +1；接收方 **MAY** 承接本节定义的来源认证完整 current 而跳过中间版本。`issuer_id` 是签证明的 Station，不是 holder，也不是双向去重键。不存在双方共享 CAS、第二签发 authority 或服务器代签 holder Event。

成立依据、对端关闭和 proof 刷新 **MUST NOT** 推进本方操作 version。固定首次身份决定 founder，本轮成立决定本次同意，当前逐 scope 实例决定权限；三者互不替代。缺失安全材料不是从未建立，已关闭请求／round 不复活。

### 1.1 陌生人首次接触的 new-source quota（normative）

Contact request 与 invite delivery、`ak.self.consent.command.request.v1` 一样，是**陌生人向 holder
发起的首次接触**，因此同样是"换一个 principal 就能重新骚扰"的放大面。这三条面 **MUST** 汇聚到
[`consent-model.md`](./consent-model.md) §6.1.1.3 定义的**同一个 holder admission chokepoint**，共用
[`../sync/invite-addressing.md`](../sync/invite-addressing.md) §5.2 的 quota carrier 与 effective 值、
[`consent-model.md`](./consent-model.md) §6.1.1 的 identity key
`(holder 完整 AccountId, source_peer_principal_id)`，以及该 chokepoint 同一事务边界内的 seen-source ledger 与线性化要求。
Contact 首次接触照常计费；被计费的是**发起方 principal 首次向该 holder 接触**这件事，与该请求最终落在
哪个 carrier 无关。

但 **Contact 的 carrier 不是 holder quarantine**：Contact 的待审状态是本文 §3 的 directional
`pending_incoming` head，由 Contact 状态机独占。因此：

- Contact request 通过 chokepoint 时，写入的是 `pending_incoming`，**MUST NOT** 在 holder quarantine 中
  产生 entry——那会给同一事实造出第二个平行待审 carrier；
- Contact request 命中 quota 上限时，被静默丢弃的对象是 **`pending_incoming` row 的建立**，不是
  quarantine entry。丢弃 **MUST** 对 requester 不可区分：与 `pending` 建立成功、holder 不存在、
  holder policy deny 返回逐字节相同的响应并落在同一 timing bucket，理由与
  [`consent-model.md` §6.1.1](./consent-model.md) 的五元等价类完全相同；
- Contact 的重复判定由本文 §3 的 directional current head 决定：同一 issuer 对同一 peer 已有未终态的
  request 或 lineage head 时即为重复，重复不进入 quota 评估、零新计费。本节不新增第二个去重键；
  §1 的完整 holder／peer／trust-domain 方向 current 与 exact 请求消费仍是唯一真源。

Contact 路径**仍然不读写 Consent**（本节开头条与
[`../sync/service-http-binding.md`](../sync/service-http-binding.md) 的 `POST /_arkret/self/contacts/request`
行）。共用 chokepoint 只共享反滥用计数，不引入任何 consent 授权语义。

## 2. Contact 写链、回执与 Contact round

五类 Contact 操作 **MUST** 经过同一写链：durable prepare → holder 签 exact canonical draft → 当前 authority 确认并签发 RealmCommit → 同事务安装私有 Contact effect、操作 current、终局和 outbox → 原 source receipt／lineage → peer 验证并保存 mirror。未确认 Event、HTTP 已接收或内存预折叠均不产生 authorizing receipt。`rejected` command unit 不产生 Contact 授权效果。

prepare **MUST** 冻结 operation/idempotency/phase、完整 request digest、exact peer、配置的 `trust_domain_id`、本方操作前态、新 `version`、适用的固定身份／round／scope、expiry 和 canonical unsigned bytes。客户端 **MUST** 解码并核对 exact kind／actor／peer／意图，仅追加原 holder proof。commit 去掉 holder proof 后 **MUST** 与 reservation bytes 逐字相同；源确认事务重查前态、slot、known closure 和当前授权。caller 不得选 root、改 draft 或自行分配第二 Event 身份。

新操作 `version` 从 1 开始，覆盖 requested／accepted／rejected／scope.update／tombstone；新本方 Event 严格 current+1，非首次操作的 `predecessor_event_ref` 精确引用本方上一操作。首次操作省略 predecessor；后续必有。request／reject **MUST NOT** 携 future `contact_round_id`。首次尚未成立时省略 `initial_contact_round_id`；已固定后每个新操作及 source 证明 **MUST** 绑定真实固定值。首次 normal accepted 可以由本次请求确定 round，但不接受 caller 自选另一首次身份。PCR typed `expected_revision` 与 Commit position 保留独立职责，不能当方向 version。

只有 exact Event 的真实 command unit committed 且全部 effects 原子安装后，source 才能固定 receipt／lineage、接受时刻、producer descriptor 和耐久投递。已保存 Event 但终局未明返回既有 `503 temporarily_unavailable`，不是永久 failed 或 accepted。客户端保持 operation/idempotency/phase 与原 signed bytes 查询／重试，不因 reservation 到期重新 author。human 既有 pending Control／确切 RealmCommit prepare/sign/submit 续跑不得等待 Contact accepted，否则形成循环等待。这个安全流程不进入普通聊天前置。

同 operation/idempotency/phase 和相同完整 bytes **MUST** 回放首个耐久终局；不同 bytes 冲突。历史 accepted 响应只恢复旧结果，不能重新执行或安装为当前授权。临时未决不固定为永久 HTTP 终局；真实失败保持登记的 reason／Problem 映射，不统一改为 lineage conflict。对端离线或解析失败不能使本地 request prepare 伪造 not_found；投递沿 outbox 重试。

### 2.1 有界 admission slot 与成立

source **MUST** 在 holder／peer／trust-domain 的锁定 slot 内串行选择 normal、glare 或 reject，exact request 只消费一次。当前 slot 保存本方操作 head/version、当前 exact 请求及消费选择；**MUST NOT** 构造或读取历轮 Contact Event 前缀。旧 exact 请求终局与审计独立索引，重试可查原结果，不逐轮扫描。slot 消费状态不另建双方共享序号。

normal 接受的线性化点必须证明 responder 无 outgoing request，并消费 exact incoming request／source receipt。glare 仍需两个确认请求及双方各自的确切并发观察，不能只凭两个 receipt、到达先后或墙钟。每张 glare attestation 签发时，source **MUST** 在同一事务耐久固定对同一对请求选择 glare；以后不得改 normal/reject。单方 attestation 不授权，双向齐备且匹配才成立。原 `glare_finalize` 是唯一相应 carrier，无新跨站两阶段提交／超时 winner。

normal 已消费后的迟到 reverse request 不改判 glare。glare 未齐时本方仍 pending_outgoing，不改成可 respond/reject 的 pending_incoming；双向成立不合成 holder accepted Event。normal requester 取得接受依据也不合成新本方操作，其当前操作 head 仍是自己的 request。

### 2.2 唯一摘要前像

本文 `H(label,x)` 固定为 `"sha256:" + lowerhex(SHA256(UTF8(label + "\n") || RFC8785_JCS(x)))`。domain label 不作为 object 成员插入。closed transcript 中以 `?` 标注的成员仅按适用条件整体省略，禁止以 null／空串替代；其它成员必需。原始 EventId 自含 suite/digest，不传平行同源 digest。

```text
request_acceptance_receipt_core = {
  trust_domain_id, holder, peer,
  initial_contact_round_id?, version, predecessor_event_ref?,
  request_event_ref, producer_signer, source_checkpoint, accepted_at, issuer_id
}
receipt_digest = H("ak.contact.request_acceptance_core.v1", core)
request_acceptance_receipt_digest = SHA256(JCS(exact_signed_receipt))
request_source_checkpoint_transcript = { event_ref, event_digest }
source_checkpoint = H("ak.contact.request_source_checkpoint.v1", transcript)
```

`version` 对应本方 request 的生命周期版本，Event／receipt 字段逐字一致。`event_digest` 只从同一 typed EventId 解码并与 exact Event preimage 重算交叉核对。source_checkpoint 是 exact fact commitment，**不是**连续性 checkpoint、Merkle root 或 RealmCommit ref，仍保留本用途。receipt core digest 与整张 signed receipt digest 不可互换。

```text
normal = {kind:"normal", sorted_pair_member_ids,
          request_event_ref, request_acceptance_receipt_digest}
glare = {kind:"glare", sorted_pair_member_ids,
         requests:[{request_event_ref,request_acceptance_receipt_digest}, ...]}
contact_round_id = H("ak.contact.round.v1", contact_round)
```

`sorted_pair_member_ids` 恰含两个不同完整 ActorId，按 unsigned RFC8785 JCS bytes 严格升序。glare 恰含两项，按完整 typed request_event_ref 的 UTF-8 unsigned bytes 严格升序，**不得**解码 digest 后比较、按 receipt digest 或 object JCS 排序。接收端 **MUST** 拒绝乱序／重复输入，不先排序修补。normal founder 取 responder，glare 取 requests[0] 的原完整 author。

```text
outgoing_slot_absence_transcript = {
  trust_domain_id, sorted_pair_member_ids, request_slot_owner,
  contact_round_id, request_event_ref, version,
  predecessor_event_ref?, observed_at, outgoing_request_state:"absent"
}
outgoing_slot_absence_digest = H("ak.contact.no_outgoing_slot.v1", transcript)
glare_unconsumed_slot_transcript = {
  trust_domain_id, subject_id, peer_id, contact_round_id,
  request_event_ref, version, request_receipt_digests,
  observed_at, slot_state:"glare_selected"
}
unconsumed_slot_checkpoint = H("ak.contact.glare_unconsumed_slot.v1", transcript)
```

normal version/predecessor 指 responder 本次已确认接受操作，观察与 receipt accepted_at 相同；source 在该事务保存 exact core。glare version/request_event_ref 指 subject 已确认的原 request，证明选取时不增加本方操作版本。两张 glare 分别 subject→peer，issuer 是该 subject 合法 Station，request_receipt_digests 顺序与 round 的 requests 一致；同站两账号也不能按 issuer 集合去重。两种观察均无累计 Event 数组；known-answer vectors 见 [Contact KAT](../../artifacts/fixtures/contact-round-kat.json)。

### 2.3 原 producer、历史来源和窄确认

所有 source proof／receipt 使用独立确定的合法 holder Station 在相应 evidence time 的历史 assertionMethod 验签；原 holder producer 使用 source 冻结的 exact key／method 独立验原签。接收者不重放 source 私有 PCR，不以 receipt 自报 issuer 自钉信任，也不因此获得通用 PCR／设备目录读取权。下列 exact producer projection 合同保持。

**Contact producer projection（normative）**：`request_acceptance_receipt_core`、
`normal_response_acceptance_receipt`、`reject_acceptance_receipt` 与 `contact_lineage` 必须在各自原始
`request_event_ref` / `response_event_ref` / `reject_event_ref` / `event_ref` 后携带 required
`producer_signer` 的闭合 direct 分支为 `{verification_method, public_key_b64u}`，delegated 分支为
`{verification_method, public_key_b64u, delegated_actor_did}`；没有新增 `kind` 标签。只有合法 Agent
controller-device 原 Event 含 `executed_by` 时 MUST 使用 delegated，human 与 Agent runtime 分支 MUST
使用 direct 并禁止 `delegated_actor_did`。各分支都是原 source-signed core/transcript 的成员，
按原 digest/signature 算法完整覆盖，不另加签名、签名 context 或 key digest。`public_key_b64u` 为 canonical
unpadded base64url 的 Ed25519 raw32；算法固定为既有 Contact Event Ed25519 profile，不携带重复的
algorithm/key-kind。source 只能冻结该确切已确认 Event 实际通过 producer 验证的 key 与 method，不能从
稍后的当前设备目录替换旧 key，也不能用自己的 service key 代替。同一 Event 同时出现在 receipt、
lineage 或 self outcome 时，各处 descriptor 必须逐字相同。

接收方先验证 expected source 的历史签名及 receipt/lineage 对 exact Event 的绑定，再要求唯一原 Event proof
的 `verification_method` 与 descriptor 逐字一致。实际 producer 唯一取 `executed_by`（若有），否则取
`actor_id`；method DID 经已登记 adapter 验证后必须投影为该 producer 的 principal。原 JWS 的 binding actor
始终为 `Event.actor_id`，禁止改成 executor。human 不得携 `executed_by`；Agent runtime 必须由 Agent 自己
签名；controller-device 分支的 executor 必须逐字等于该 Agent 的完整 controller AccountId。每个分支均以
source 认证的 exact key 验原签名，拒绝算法替换、同 key 跨 Account、method 替换、未确认 source 事实和把
另一 Event 的 descriptor 移用到此 Event。

Agent participant 必须先固定其完整 account ActorId；其 Station 与 controller AccountId 的 Station 相同，
再从完整已验证 Agent DID native history 确认 controller principal 与 create-locked PCR/delegation tuple。
runtime method 定位 Agent DID。controller-device 分支从原 source-signed `producer_signer.delegated_actor_did`
取得完整公开 Agent DID locator，再使用既有 DID method history 读取/验证，重算其 core 必须等于原
`Event.actor_id` 的 principal；不得把它解释为 executor DID、授权断言或私有 PCR 材料。source MUST 在
原 Event admission 时从其已验证 Agent native identity/create-locked binding 取得并与 producer key 一同
耐久冻结该 locator；不得由 core 拼 host/path、使用调用方未经验证的字符串、或在 completion 时从稍后的
当前目录替换。所有 enclosing carrier 与只读/恢复消费者 MUST 复核上述分支 iff 条件，以及 actor、executor、
controller 完整 Account/Station 与公开历史的绑定；同一 Event 的各个 descriptor 必须逐字相同。
没有这些独立材料时保持非授权 pending；不得从
待验 receipt 的 issuer 或未认证 peer 的 controller 反过来选择受信 source。公开 DID 的 requested-scope
commitment 不是业务许可：完整私有 grant/key/scope 的本地执行校验由源 Station 在该 exact command 确认时
完成；此处只消费它对该 Event 的窄投影，不要求向 Contact 接收方公开 Agent PCR、governance-Station history 或完整私有 scope。
接收方以原 Event 的 `created_at` 验证公开 Agent/controller/PCR 的历史身份绑定；完整 native history 仍须认证，
但该历史点之后的 binding 变更不得追溯抹除此前已确认事实。源 Station 独立负责真实 command 确认时的完整
授权有效性，producer 自填的旧 `created_at` 不产生新 live 许可。后续失效与收窄按已知 fence/关闭证据处理。
lineage 的签名时刻只定位 source assertion key，不充当未携带的 command 确认时间，也不要求延后签发时
原 holder 仍有当前授权；保留旧事实不等于允许它绕过当前撤销。

该材料只在上述五类 Contact 历史 carrier 中补全原 producer 验签，不授权另一 Event、generic Control
admission、DID 更新、governance-Station handoff 或普通消息新 live。必须保留原 Event bytes 与正常 `expected_revision`，不得改签 Event，
不得把普通消息或其它 Control Event 放进此例外。已签的 source
receipt/lineage 同时绑定该 Event 与其 key，是此 carrier 的取材合同，不要求先有 Contact 或共同 Realm，
不触发关系门控设备查询，也不扩张 `account_device` 历史响应分支的权限。同站与跨站均耐久保留完整原件，
重放只重验原证据，不以新的查询 TTL 取代历史授权关闭规则。

`accepted_at` 是源业务 slot 的真实确认线性化时刻，不是稍后 completion 签发时刻，也不机械复制任意 RealmCommit
时间。源事务必须在同一确切 slot 观察点固定 receipt core；normal 分支的 absence core `observed_at`、其
commitment 与 receipt 的 `accepted_at` 一致。延后签名按该历史时点的已授权 assertion key 签发，旧 key
缺失时等待恢复实际 custody，不能改 timestamp、重判 normal/glare 或用新 key 倒签。lineage 与 current proof
各自按真实签发时点验证 key，且 current head 必须是该方向实际已确认 current，不要求接收者重放全部中间后继。首次耐久终局一经固定，所有
重试返回相同 receipt/round/bytes。

`glare_concurrency_attestation` 同理签 `subject_id: ActorId`、`peer_id: ActorId` 与
`issuer_id: DidCoreId`。两张 attestation 必须分别是 `p0 -> p1` 与 `p1 -> p0`，issuer 必须是 subject 在
`observed_at` 已接受的 Station service authority；同 core 异 Station与同 Station双账号均按完整 ActorId 独立判定，
必须按完整 ActorId 判定，不接受只含 `did_core_id` 的形态。


### 2.4 peer carrier 与只读 current_refresh

`ak.peer.contacts.command.submit.v1` 是唯一闭合 carrier：五类原 signed Event＋对应 receipt／lineage、glare_finalize，以及 current_refresh。它 **MUST NOT** 承载 Realm Event 或 DM binding。原件保持原 bytes，peer Message Signature 只认证传输。成功事件结果使用 Event mirror receipt；glare/current_refresh 使用 request-kind 绑定的 control receipt，不能伪造另一 Event mirror receipt。其 result_digest 为 `H("ak.peer-contact.control-result.v1",{request_digest,result_kind,glare_concurrency_attestation?,current_proof?,material?})`，覆盖实际返回的全部相应成员，省略的成员整体缺席。

current_refresh 的身份、输入／输出、预算与安装合同见 §3.2。旧 proof_refresh、prior_mirror_receipt 前置、continuity_checkpoint 分支及其操作不再定义。request introduction_evidence 仍按 `H("ak.contact.introduction-evidence.v1", exact_introduction_evidence)` 匹配签入 Event 的 digest；缺件不生成可回应或授权投影。

contact_address 唯一 recipient 为完整 ContactPeer；human 用完整 AccountId，Agent 用完整 actor／controller Account。目标 Station 从该身份独立派生并与 transport destination 一致，service_resolution／route_assistance 仅供传输，不改变长期身份；不开放任意 Service／RealmActor participant。

## 3. Directional scope、current head 与终态

`contact_lineage` 是确切本方操作的 source 认证，保留原 Event／producer／accepted_at 与本方 version。`contact_current_proof` 另认证同一 durable cut 的完整 holder／peer／domain、本方 head/version、固定首次身份、适用的 round、逐 scope 原实例、原源关闭及 issued_at/fresh_until。**MUST** 独立验证合法 source、原签、真实确认和所有引用，不能只比较序号或 accepted 布尔。

scope 是 `granted_to_peer_scopes[]` 的完整替换；首次 request／normal acceptance 中的 scope 只有在确切 round 成立后才授权。每个连续 scope 以原 grant Event 作为实例，source proof 的 `scope_instances` **MUST** 与当前 full-set 和真实确认事实一致。连续保留不换实例；移除关闭原实例；重加以该次 scope.update 开新实例。不增加独立 generation 计数器。空集合仍为非 terminal accepted，tombstone 则关闭整轮，原轮不得 widen 复活。

接收端 **MAY** 安装完整 current 跳过同轮或跨轮中间操作，明确依赖 source 对实例连续性的窄认证，不宣称独立重放全部略过历史。新 live 可验证当前实例；旧消息资格必须取 exact 实例的授予／成立／必要关闭区间。缺旧材料仅使该历史资格未知，不延长旧实例、不追溯撤销原已合法消息，也不要求新 live 补齐无关全史。到达时间、自填 created_at、first_verified_at 和今天同值 scope 均不能代替区间证据；原 RealmCommit 的接受事实不改写为 rejected。

同 version 的冲突只比较同方向 immutable 已确认操作；时间／签名刷新、取得成立或对端关闭依据不是另一操作。收到 B tombstone 时 A **MUST** 保留自己的操作 head/version，另保存 B 的原确认关闭，不共享 B tombstone 作为 A head，不合成 A tombstone。旧操作不覆盖新 head，但其合法关闭仍按 exact round／实例安装。新包省略已知 fence 不清除它；旧轮关闭不关闭合法新轮。有效矛盾拒绝并留原件，不按到达顺序或 digest 选 winner。

source 本人拒绝／撤回／纯收窄从真实本地 current 确认，不等待对端 fresh 或同意；扩大或接受及新 DM founding 仍核当次所需 fresh current，混合收窄和扩大按扩大要求。已有 binding 的 ordinary send 可用已验证实例与已知关闭，不因查询 lease 过期强制 source 在线或伪造 revoke。初次缺必要证据仍不能授权；membership／device／MLS／实际 action gates 保持。离线未知方沿耐久投递与恢复收敛，不保证全球瞬时撤回。

self list 的 accepted row **MUST** 带 next_prepare_input `{contact_round_id,version,predecessor_event_ref}`：version 为下一次本方生命周期操作版本，predecessor 为本方真实 head，客户端原样回传。pending／rejected／expired／tombstoned 不带该 cursor。normal requester 与 glare 的首个后继从其原 request head 接续，不合成 version 1 accepted。pending_incoming 只对 exact holder 提供原 request_event_ref 和 exact message；respond/reject 逐字绑定该 incoming proposal。陈旧输入拒绝且零新增效果，客户端重读，不猜版本／前驱。

profile 沿既有共享 Realm 授权查询，不因 Contact accepted 获得 PCR 或任意 profile 读取权。客户端核本人 draft 意图，Station 核 mirror 原签／源确认并 CAS 耐久保存；镜像不进入 receiver canonical Realm Event store。移出 pending_incoming 后不再在列表展示申请附言，无权主体保持 opaque failure。

向量：`ak.vector.contact.next_prepare_input.v1`、`ak.vector.contact.pending_incoming_prepare.v1`、`ak.vector.contact.current_state.v1`。

### 3.1 Contact 耐久效果的归属（normative）

Contact 的 admission slot、contact round、每条完整 holder／peer／domain 的操作 current、已验证的对端 mirror 与列表折叠，
全部是 **holder Station 的私有服务状态**，不是靠重放本 Realm 已提交 Event 得到的 Realm typed current result。
理由是结构性的：§2 的 `contact_round_id` 由 source-signed acceptance receipt 的摘要决定，而该 receipt 的 core
成员（`source_checkpoint`、`accepted_at`、`issuer_id`）没有一个进入 Event 流；glare 分支还需要
对端的 request 与 receipt，而本节已规定 mirror **MUST NOT** 推进 reducer。

因此 `ak.contact.requested` / `rejected` / `accepted` / `scope.update` / `tombstone` 五条 kind 在
`contract-registry.json` 中 `reducer_input` 为 `false`，其真实耐久效果登记在 canonical `service_contracts` 的
`ak.contact.admission.v1`：每个分支的效果、唯一键、前态 CAS、exact retry 与零副作用拒绝逐条列出，本节与 §2 是
它的 `defined_in`。这只收窄 Realm typed-result 分派，**不**削减这些 Event 既有的 admission、签名、提交证据与
私有事务效果；`wire_scope` 仍是 `durable_event`。

- 实现 **MUST NOT** 仅把 carrier 收进内存就宣称列表“可折叠”：耐久 founding evidence、私有 slot 与已接纳的 Event
  事实必须足以在重启后重建同一份列表。
- 这些材料依旧 **MUST NOT** 进入接收方 canonical Event store，也 **MUST NOT** 推进 reducer、RealmCommit 或
  authority-commit checkpoint。
- `glare_finalize` 与 `current_refresh` 没有 signed Event，它们是 carrier operation；实现 **MUST NOT** 为此新增
  non-Event 的 Realm reducer producer，也不扩 `result_writes[]`。
- 不得为提高登记覆盖率而给这五条 kind 造一个正文从未命名的 typed current result family。

### 3.2 完整 current 取材和安全恢复（normative）

current_refresh 是只读分支，required 输入为 kind、fresh idempotency_key、完整 requester、trust_domain_id、known_version（0表示未知）、grant_event_refs（至多5个 exact grant EventRef）与 contact_address；initial_contact_round_id 仅在已知时携带以核对，不是允许 caller 改 root。不得要求旧 mirror receipt。请求 Message Signature 的 Station **MUST** 实际托管 requester；目标是 exact peer，不能查询第三方 pair。

来源从同一真实 durable cut 返回 `contact_current_material`：本方 exact head_operation、current_proof、最多5项当前 scope_grants、至多5项请求的 exact historical_intervals，以及已存在的 initial_identity／round_evidence。current proof refs、原 producer、source receipt 和实例逐项匹配；历史 interval 由本次 source result 认证其在 cut 的完整关闭边界。未首次成立时不得伪造 root，pending/reject 不携未来 round；新 pending 附旧轮成立／关闭时仍只属于旧轮。可授权结果须有完整本轮，关闭或明确非授权事实可以独立安装，不得把缺字段解释为 accepted。

当前 root basis 含原首次 Event(s)／receipts／normal或glare依据，是 unsigned deterministic 对象，不另签新 root 证书。来源只能刷新自己方向；转交另一方向必须保留原 issuer／原有效期，不能用本次 response 时间续期。所需双方 fresh 分别认证；固定历史凭据无需首次 lease 至今 fresh。

完整请求与响应的 canonical JSON 各 **MUST NOT** 超过 2 MiB，历史实例最多5个；current scope 恰属于既有5值 enum，唯一按 scope 排序且不重复。超限使用现有 too_large 语义，缺件保持既有 deferred／暂不可用，不截断成可授权成功。无全轮枚举、continuity export、通用 snapshot 或第二恢复 authority。

返回的 control receipt **MUST** 签本次 request_digest 和完整 material 的 result_digest。相同 key／请求返回第一次冻结结果，不能因此续期；需 fresh 查询用新 key。接收者验证身份／原件／所有绑定后，锁本地状态重核固定身份、方向进度和已知关闭，再原子安装；有效关闭可独立先保存，不能用等待中的旧响应覆盖本地撤回。

只披露已允许给 exact peer 的原事实／必要历史，不披露 quota、seen-source、policy 或私有 pending_incoming。无合法可披露事实时，目标不存在、policy deny、quota drop、隐藏待审均使用既有相同 opaque deferred bucket，不能探测接纳结果。曾成立关系的合法关闭／历史恢复不以今天仍 accepted 为前提。缺失记录不证明 never-written；不能从不完整备份重置 root、version、消费事实或 founding slot。

## 4. Contact operation surface

所有非 public `ak.self.*` operation 的同一个 OpenAPI security object **MUST** 同时要求 bearer 与 DPoP；HTTP
Message Signature只能额外叠加，不能替代其中任一项。实现 **MUST** 登记并实现下列 closed operation：

| operation | 语义 |
| --- | --- |
| `ak.self.contact.command.request.v1` | prepare/commit 原始 signed request与 request acceptance receipt |
| `ak.self.contact.command.respond.v1` | 只执行 normal accept；要求 responder slot 无 outgoing，不接受 reject action |
| `ak.self.contact.command.reject.v1` | 独立 proposal terminal reject与 rejection receipt；不得复用 respond body |
| `ak.self.contact.command.scope_update.v1` | issuer-local full-set replacement |
| `ak.self.contact.command.tombstone.v1` | accepted round terminal，已接受的 predecessor refs 永久消费 |
| `ak.self.contact.read.list.v1` | 从 verified Contact round evidence 与双方 directional current heads 投影；accepted row 另携 §3 的 `next_prepare_input` 游标，`pending_incoming` row 携带 §3 的 exact request 引用及申请附言；不导出跨轮历史连续性包 |
| `ak.peer.contacts.command.submit.v1` | closed XOR peer carrier；原 bytes + exact receipt/current proof |
| `ak.self.direct_conversation.read.resolve.v1` | §9.1 的唯一 DM 查询入口；closed outcome，不携 create phase 分支 |
| `ak.self.events.command.submit.v1` | 其 `direct_conversation_founding` branch 是 §5.5 的唯一 DM founding 提交入口 |
| `ak.peer.events.command.submit.v1` | 其 `direct_conversation_founding` branch 是 §5.6 的唯一 DM founding 联邦入口 |

创建由 §5 的 `ak.realm.create` founding admission 承担，查询由上表的
`ak.self.direct_conversation.read.resolve.v1` 承担，二者 **MUST NOT** 合并为一个带 `create=true` 的 operation。

所有 transport binding **MUST** 逐字段等值，不能自行增加 `accepted`、兼容 consent shape、unsigned service row
或第二轮 assignment。

**首次接触 message 的封闭约束（normative）**：`ak.contact.requested` 的 `message` 是未获同意文本，本条约束的是
**投递面**，不是 exact target holder 的可见性。接受前它 **MUST NOT** 进入任何 Strand、message timeline、未读
计数、消息搜索索引或推送正文；跨服务器投递与一切 non-Contact projection **MUST** 以 stub 替换。它 **只**能经
`ak.self.contact.read.list.v1` 的 `pending_incoming.request_message` 向 **exact target holder** 呈现完整内容。附言与 `request_event_ref` 必须来自同一已验证 Event；服务器不得用其它内容替换。

stub 不是加密措施：`message` 是 digest-covered 明文，requester Station 持有它。Contact 建立前没有共享密钥，v1 不将该字段改为密文。客户端信任自己 Station 的申请投影，并核对回应草稿绑定其所见申请。

## 5. Direct Conversation founder 派生与创建授权

### 5.1 pair identity

同 trust domain 下两个 exact `ActorId` 先分别序列化为 RFC 8785 JCS，再按 unsigned JCS bytes 排序为 `[p0, p1]`。`pair_key` **MUST** 在任何 Realm 存在前即可计算，因此固定使用 SHA-256 与 RFC 8785 JCS，**MUST NOT** 读取任何 Realm 自报的 digest suite：

```text
pair_key = sha256(UTF8("ak.direct-conversation.pair-key.v1\n") ||
                  JCS({"trust_domain_id": <id>, "participants": [p0, p1]}))
```

handle、display name、设备 ID、endpoint、Realm ID、Strand ID 与 Contact Event ID **MUST NOT** 进入前像。裸 `principal_id`、裸 DID 与 unresolved pairwise DID 也不是参与者身份；账号参与者必须使用内含 `station_id` 的完整 `AccountId` 分支。双方 **MUST** 从 Event 中的 exact participants 与 trust domain 重算 `pair_key`，**MUST NOT** 采信 caller 自报值。实现 **MUST** 执行 [`ak.vector.direct_conversation.pair_key.v1`](../../artifacts/registry/vector-registry.json) 的逐字节 KAT；无 domain separator 或把 `trust_domain_id` 改名为 `trust_domain` 的旧前像均不是 v1 `pair_key`。

### 5.2 founder 派生（normative）

同一 pair 的 Direct Conversation Realm **MUST** 由且仅由从该 pair 的 **固定首次 Contact round** 确定性派生出的 `founder` 创建。派生只读 §2 已定义的 `contact_round` core，不引入新字段：

```text
founder(contact_round) =
    normal 分支 -> sorted_pair_member_ids 中不等于 request_event_ref 之 author/requester 的那一方（即 responder）
    glare  分支 -> requests[0].request_event_ref 之 author/requester
```

**normal 分支取 responder 而非 requester 是 normative 选择**：Contact round 由 responder 的 `normal_response_acceptance_receipt` 点亮，该 receipt 证明 responder 在该 round 成立时在线且刚完成签名；requester 可能在数日前发出请求后即长期离线。base v1 不定义 fallback（§5.7），因此把 founder 定为可能不在场的一方会使该 pair 永久无法创建。

glare 分支不存在 responder；`requests[0]` 是 §2 按完整 `request_event_ref` wire 字符串的 UTF-8 unsigned bytes 严格升序排列后的第一项。founder 是该项引用的 signed request Event 的完整 author `ActorId`，不是 receipt 的 Station `issuer_id`，也不是 `sorted_pair_member_ids[0]`。到达顺序、墙钟时间、请求发起先后及收据摘要都不参与选择，**MUST NOT** 另立排序规则。

以上两条 Contact founder 规则用于 human↔human 和需要 Contact consent 的 Agent↔第三方分支。controller↔自己的 owned Agent 不走 Contact 邀请／接受／glare，按 §5.4 从已接受且 current 的 provision/controller binding 固定 `founder=controller`；Agent 配对只建立 runtime 授权，不创建聊天 Realm。

双方只有各自 outgoing request、尚未取得完整有效 round evidence 时均没有 DM 创建权。normal accept 的本地 slot CAS 必须证明不存在 outgoing request；glare 的双方 causal/completeness evidence 未齐时只可等待，不得按本地可见请求分别建立 normal round。网络超时不得授予另一方 fallback/takeover 创建权。完整证据确定同一 founder 后，才由其 current Station 按 §5.5 原子关闭唯一 founding slot；本地数据库锁本身不承担跨 Station 选择 founder 的职责。

`sorted_pair_member_ids` 不恰为二、request Event author/requester 不属于该 pair、glare requests 未按登记顺序或两个 requester 不构成该 pair 时，founder 派生 **MUST** 失败并整组拒绝，**MUST NOT** 以补集或本地偏好猜测。这里的 author/requester 是 signed Event 的完整 `ActorId`，不是 service-signed proof/receipt 的 `issuer_id`。

### 5.3 固定首次 Contact 身份与 recontact

同 trust domain 与 exact pair 的 founder **MUST** 从 `contact_initial_identity` 保存的首次真实成立 round 派生。该 unsigned identity 包含 trust_domain_id、immutable contact_round_basis 和1～3个原 signed Event；request／receipt／normal response 或双方 glare attestation 与原 producer／source 确认逐字匹配。首次由真实本地成立事务安装，对端核原件后安装同一值；不签第二张 root 证书。

后续新请求／接受／current 绑定首次 `contact_round_id` 为 initial_contact_round_id，不沿前轮求根。当前 evidence bundle 含固定 initial_identity、本轮原件、exact 两方向 current 与各自 current_operations 原签／确认，以及当前 scope grants；固定凭据只决定身份，新 founding 另验当前双方 direct_message。terminal 后用新请求／新同意建立新 round，不复活旧请求，不重置方向 version、不换 founder、不释放 founding slot。

缺固定原件先从保存原件或合法对端窄 current 取材恢复并核本地确认事实；省略不能变初次。冲突／缺件拒绝相关新建授权，已有坐标保留。全部受信保存点共同回滚／隐瞒不在此模型可独立检测的保证内；已见矛盾仍拒绝并留证。

本规范不要求跨轮 previous-terminal 指针、逐轮 continuity chain、尾段上限、prefix accumulator、双签连续性 checkpoint、共签操作、连续性导入导出或专用永久 fork 状态。也不要求 normal/glare 构造累计 Event 前缀。原始操作、必要历史区间、普通幂等／投递原件仍按独立安全用途保存，不宣称总存储恒定。

### 5.4 create 判别与授权

`ak.realm.create` 的 conditional admission **MUST** 登记两个结构互斥的 Direct Conversation variant，判别器为 critical ref role：

| ref role | admission variant | 适用分支 |
| --- | --- | --- |
| `direct_conversation_contact_round` | `direct_conversation_genesis` | human↔human、Agent↔第三方 |
| `direct_conversation_agent_provision` | `direct_conversation_agent_genesis` | controller↔自己的 owned Agent |

两个 role **MUST** exact XOR。Agent PCR genesis 只按 `payload.object.purpose="agent_control"` 选择 `delegated_pcr_genesis`，并在准入时反查 accepted `ak.agent.provision` 的前向声明（见 [`./key-management.md` §3.6.3](./key-management.md)）；它没有 ref role 判别，因此这里的两个 DM role **MUST NOT** 与之混用。DM variants、PCR variants 与 ordinary Realm 的 `when` 条件 **MUST** 结构互斥；零命中或多命中 **MUST** `schema_violation`，**MUST NOT** 按 registry 顺序取第一条。

`direct_conversation_genesis` **MUST** 逐项验证，任一不符整组零写入：

1. 该 ref 指向完整 portable Contact round evidence bundle，首次固定身份、本轮 normal/glare 原件、双方 current scope 实例与原源关闭均可验证；
2. 按 §5.2/§5.3 求出 `founder`；
3. `created_by == actor_id == founder`（追加约束，**不**放松既有 `created_by == actor_id`）；
4. payload 的 `pair_key` 等于从 round 的 `sorted_pair_member_ids` 与 trust domain 重算之值；
5. Realm profile 为 `ak.profile.direct_conversation_realm.v1`，`collaboration_role="direct_conversation"`，effective participants 恰为该 pair；
6. §6.2 的固定 baseline 投影全部命中；
7. 该 `realm_id` 无对象身份冲突。

**accepted-at 与 current gate MUST 分开求值**：source self admission 在 slot commit 线性化点要求两条 directional current heads 共同引用该 current round、授予 `direct_message` 且 fresh；peer replay 以第四条 source RealmCommit 的 `committed_at` 作为 founding acceptance time，并验证 bounded authority evidence 在该时点有效。因此即使 Event 到达时 Contact 已撤回，peer 仍 **MUST** 接受该历史 Realm identity，并以 current gate 投影 `suspended`；否则 Event 有效性会依赖投递顺序。

`direct_conversation_agent_genesis` 改验 participants 恰为该 controller/Agent、profile 为 DM 而非 PCR、`ak.agent.provision` 已 accepted 且 controller binding current，并令 `founder = controller`。Agent 与第三方之间的 DM 仍 **MUST** 使用该 pair 的 current Contact round，**MUST NOT** 以 provision 绕过第三方 consent。

controller-Agent founding material 的 `controller_binding_digest` MUST 为 accepted `ak.agent.provision` 的完整 typed payload 的 RFC 8785 JCS 字节的 SHA-256（`sha256:<lowercase hex>`）。该 payload 绑定 Agent、controller、PCR、delegation、accountability 与 scope；不得对本地数据库记录、完整 Event envelope 或运行时状态计算该值。resolver 与 admission MUST 使用同一共享 SDK 算法；admission MUST 从本地 accepted provision 重算并比较，不能信任 caller 回传的摘要。current controller binding 仍独立验证，不得用摘要相等代替。

### 5.5 caller-authored founding unit、source 唯一 slot 与 RealmCommit finality

四条 Event 的 ID 都是各自 canonical Event preimage 的完整 digest（[`../conformance/encoding.md` §4.0](../conformance/encoding.md)），`realm_id` 与 `main_strand_id` 又分别是第一条与第四条 Event ID 的重类型（[`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md)、[`../models/common-fields.md` §6.0](../models/common-fields.md)）。因此在 canonical preimage 完成之前**没有任何主体能"分配"这两个 ID**：服务端预分配、reserved/materializing draft、coordinator 选举与 caller 自选 ID 全部 **MUST NOT** 出现在本流程。founding **MUST** 采用 caller-authored first-valid unit：

1. founder caller author `ak.realm.create`（envelope 省略 `realm_id`、`scope_ref` 为 `{"kind":"realm_genesis"}`，payload 省略 object id），完成 canonical preimage 后派生其 Event ID，并重类型得到 `realm_id`；
2. 以该 `realm_id` author founder 自己的 `ak.member.state{join}`（§6.1 的 bootstrap no-basis shape，不携 `expected_revision`；founder 行在新 Realm 上天然不存在）；
3. author 另一 participant 的 `ak.member.state{join}`；controller/Agent 分支显式携带绑定第 2 条的 `agent_controller_binding`；
4. author `ak.strand.create`（payload 不携 `strand_id`），由其 Event ID 重类型得到 `main_strand_id`；
5. 四条全部由 founder 签名，按该 wire 顺序构成 exact ordered unit 一次提交；不存在 server-created draft、reserved Event ID 或第二次 authoring 机会；
6. 网络结果不明时 caller **MUST** 重放逐字节相同的 signed bytes，**MUST NOT** 重新 author 另一组 Event。

`founding_unit_digest` 是该 unit 的唯一稳定标识，按 §2 的 `H` 定义为：

```text
founding_unit_digest = H("ak.direct-conversation.founding-unit.v1",
                         {"event_ids": [realm_create_event_id,
                                        founder_member_join_event_id,
                                        peer_member_join_event_id,
                                        strand_create_event_id]})
```

四个 Event ID **MUST** 按 §6.1 的 wire 顺序列出，**MUST NOT** 排序、去重或替换为 digest。该值不进入任一 unit Event 的 preimage，因此不存在自指；founding outcome 与 `ak.direct_conversation.bound` 只引用或重算它。实现 **MUST** 执行 [`ak.vector.direct_conversation.founding_unit.v1`](../../artifacts/registry/vector-registry.json) 的逐字节 KAT。

founder 的 current Station **MUST** 以本地唯一约束保证同一 `(founder_id, trust_domain_id, pair_key)` 至多一组 founding unit 被 accepted。self admission **MUST** 在同一事务内完成：确认该 pair 尚无 accepted DM Realm、CAS 占用 slot、按 §5.4 与 §6 完整验证四条 Event、round 与派生坐标、零项或四项原子接受、签发四条连续 RealmCommit、写入 peer-delivery outbox。acceptance **只固定 caller 已派生的坐标**，**MUST NOT** 分配、替换或重新协商任一 ID。

founding 不再定义第二张 acceptance receipt。peer verifier 所需事实全部来自四个 Event、四个 source RealmCommit 与同一 peer carrier 的 `founding_authority_evidence`，逐字段推导如下：

- `pair_key` 由 exact two-member Actor pair 与 trust domain 重算；founder 由 固定首次 Contact round／controller-Agent 规则重算；
- `realm_id` 与 `main_strand_id` 分别由第一、第四 Event ID 重类型；`founding_unit_digest` 由四个有序 Event ID 重算；
- issuer、generation、stream continuity 与 finality 来自四个 source RealmCommit；第四个 Commit 的 `committed_at` 是唯一 founding acceptance time；
- human current/固定首次 Contact round 或 controller-Agent provision/binding 来自 closed `founding_authority_evidence`，不得镜像进第二个 authorization core；
- 本地 slot 唯一性由 source transaction 的唯一约束保证，不存在能让远端从同一 signer 的第二个签名额外验证该数据库约束的 wire 字段。

旧 `accepted_contact_evidence_digest` 没有登记可重算的前像、domain 或算法，**MUST NOT** 保留为 opaque commitment；
`direct_conversation_founding_acceptance_receipt`、`source_acceptance_receipt`、founding `receipt` outcome 字段及同义
compatibility alias 均为禁止成员。`ak.direct_conversation.bound` binding fact 的 `pair_key`、authorization basis、
Realm role、exact two-member set、main Strand、`founding_unit_digest` 或 founding MLS 引用任一无效时，verifier
**MUST** 拒绝该 binding（reason `direct_conversation_binding_invalid`）。

carrier 是 `ak.self.events.command.submit.v1` 的 endpoint-specific
`self_submit_request` union 中显式登记的 `direct_conversation_founding_unit_submission`
（`unit_kind="direct_conversation_founding"`）：它精确要求恰好四条按 §6.1 顺序排列的
`EventAdmissionSubmission` 与 `idempotency_key`，不携带 `founding_authority_evidence`——founder 的 current
Station 在同一 admission 事务内以自己 current 的 Contact round / Agent provision 证据校验该 unit（§9.1.1），
并在 `self_submit_outcome` 中返回 `direct_conversation_founding_acceptance_outcome`。每条 Event 的实际 author
`ActorId` 必须路由到接收服务，服务端只在完整本地准入后追加 admission proof。实现 **MUST NOT** 新增私有
endpoint、复用普通 batch 分支或让服务端代签 producer Event；
`ak.self.direct_conversation.read.resolve.v1` 继续 query-only，**MUST NOT** 承载 create。

幂等与 crash/restart 语义 **MUST** 如下封闭：

- 同 `idempotency_key` 且同 `founding_unit_digest` 的 exact retry 返回相同四个 byte-identical source-signed `RealmCommit`（Event ID 由各 `commit.event_ref` 唯一取得），且 **MUST NOT** 改写第四个 Commit 的 `committed_at`；
- 同 `idempotency_key` 但不同 `founding_unit_digest` 返回 `duplicate_conflict` 且零写入；
- 本地 slot 已被同 pair 的另一组 unit 关闭时返回 `conflict` 与 `direct_conversation_slot_already_committed` 且零写入，caller **MUST** 改用 §9.1 resolver 取回既有坐标；服务 **MUST NOT** 接受第二组 unit，也 **MUST NOT** 把它降级为 partial 或 quarantine；
- 客户端已派生 ID、unit 已提交、四 Event／Commit 已落库、outbox 已入队与响应丢失这些崩溃点，重放同一 signed bytes **MUST** 收敛到同一四个 Commit、同一坐标与同一 outbox 条目，**MUST NOT** 产生第二组 Event、第二套 finality 或第二个 slot。

相同 pair/founder 下两组均通过验证、但 Event ID 不同的四-Commit unit 本身就是 §5.7 equivocation／冲突证据；不需要第二张 receipt。

**founding 拒绝的载体（normative）**：self 与 §5.6 peer 两条路径使用同一组载体，均整组零写入：unit 结构或
固定 baseline 不符为 `failed_precondition` + `direct_conversation_founding_unit_invalid`；slot 已被另一组 unit 关闭为
`conflict` + `direct_conversation_slot_already_committed`；提交者不是 §5.2 派生的 founder 为 universal
`capability_denied`；Contact round 已非 current、authoring material 陈旧，或 controller-Agent 分支读不到 accepted
`ak.agent.provision` 与 current controller binding，为不带 `reason_code` 的 `failed_precondition`。后两类不另立
reason，避免把 Contact 状态经 reason 暴露给非参与者；§5.6 的 dependency 不足仍是 top-level `dependency_missing`。

### 5.6 联邦例外

Realm 尚不存在时无法取得普通 member federation authority，因此 Direct Conversation founding exception 只允许 Contact round 中完整 founder `ActorId` 所路由的服务向 invitee 自己的 Station 投递该 source-committed atomic unit 与 bounded founding-authority dependencies。接收方必须验证 transport source、四条 Event actual author 的 route、producer proof、四条连续 source RealmCommit、原子 bootstrap 授权和 exact participant pair 一致，并要求目标 pair 命中本地 Contact round；不得要求或比较 PCR id/genesis receipt。

该例外的 carrier **MUST** 是 `ak.peer.events.command.submit.v1` 的
`branch="registered_atomic_unit"`，其 `unit` 命中
`direct_conversation_founding_federation_submission`（`unit_kind="direct_conversation_founding"`）。它承载恰好
四条按 §6.1 顺序排列的 `committed_event_submission`；每项都是完整 `EventAdmissionSubmission` 与 source-signed
`RealmCommit`，四个 Commit 同 Realm／generation／stream、position 连续且 `previous_commit_ref` 严格衔接。
unit 另携 closed `DirectConversationFoundingAuthorityEvidence`，不存在 source acceptance receipt 或任意
dependency bag。接收方验证后只 materialize exact
source facts，**MUST NOT** 重签第二套 Commit 或创建第二轮 fanout。实现 **MUST NOT** 新增私有 peer endpoint，
也 **MUST NOT** 用普通 replication batch 夹带该 unit。dependency 不足时 **MUST** 用 top-level HTTP 409
`dependency_missing` 与 `direct_conversation_founding_missing_dependency_list` 的有界 typed set 并零写入，
**MUST NOT** 退化为 per-item partial，也 **MUST NOT** 只接受其中一或两条。

Realm 在对端 accepted 后立即回落普通 federation 规则。因 §5.4 第 3 条已钉死作者，该例外不需要方向性约束。

### 5.7 无 fallback 与 pair materialization conflict

base v1 **MUST NOT** 定义 timeout fallback、takeover lease 或 `founder_fallback_window`。仅凭"本地与对端当前都没看到 Realm"不能证明 founder 没有 accepted 但尚未送达的 Realm；旧 founder 创建权未被全局可验证且不可逆的 fence 关闭前，non-founder 创建可能与迟到的 founder 创建同时合法。因此 timeout、HLC、到达顺序、Realm token 的词法大小与一次 negative query **MUST NOT** 改变 founder authority。

base v1 同样 **MUST NOT** 定义 Direct Conversation 专用的 founder succession、root-committed
recovery authority、recovery generation 或 versioned successor pair coordinate。设备、恢复材料或
Station 暂时/永久不可用都不会把 founder authority 转移给另一 participant、第三方或双方事后
共同指定的 successor：

- 若既有账号、设备与 Station 恢复机制让**同一**
  `(principal_id, station_id)` 重新满足 current authority proof，原 founder 只是恢复了控制，
  仍可按原 slot 创建；这不是 succession，也不产生新的 DC 状态或 Event kind。
- 若该 exact authority pair 始终无法恢复，同一 stable participant pair 的 resolver 继续返回
  `awaiting_founder`。该状态对 non-founder 是协议终局：等待、重试、双方事后双签、第三方 attestation
  与 recovery capability 都不能推进 slot。由于“永久丢失”不可由一次网络观测证明，wire **MUST NOT**
  新增 `founder_unrecoverable` 或把本地放弃判断伪装成共识事实。
- v1 中新的 Direct Conversation 只能来自实际不同的 stable participant pair（或不同 trust domain），
  因而按 §5.1 自然得到不同 `pair_key`。实现 **MUST NOT** 给同一 pair 添加 salt/generation 来制造
  successor coordinate，也 **MUST NOT** 把新 pair 的 history、MLS state、keys、audit identity 或
  founding finality 表述为旧 lineage 的继承。

Realm 已 accepted 后，founder 身份按 §5.3 不再参与日常 authority。后续 signer/device/material 丢失只走
§8.2 与通用 principal/device 恢复；它 **MUST NOT** 重新开启 founder succession。若未来定义跨
`principal_id` 或 `station_id` 的连续性，必须先登记通用 principal/service succession 合同，再由
所有 domain 统一消费；v1 不为 Direct Conversation 局部预埋该能力。

本节的规范执行向量是 `ak.vector.direct_conversation.founder_loss_terminality.v1`；runner 必须覆盖
exact authority 恢复、四类替代 authority 零写入拒绝，以及新 stable identity 导出不同 pair 且不继承
旧 lineage 三条路径。

若仍观察到同 pair 第二个 **accepted** Realm：

1. 先判定是否只是非 founder、旧 round 或旧 service 产生的无效 bytes；无效对象 **MUST NOT** 进入 discovery、binding 或 Message authority，也 **MUST NOT** 被称为 candidate；
2. 若两组四-Commit unit 都有合法 founder admission、source RealmCommit 与 authority evidence，则受信 service 的 slot、cutover fence 或签名发生 equivocation。pair **MUST** 进入 `direct_conversation_pair_materialization_conflict`，冻结两边新的 Message/membership/policy/MLS/binding；
3. **MUST** 保留两组 founding unit、source RealmCommit、authority evidence、service-binding/cutover proofs 与本地 slot 证据；**MUST NOT** 自动取 min、tombstone 任一 Realm、搬移历史或让 UI 选择一边继续；
4. 只有另行登记、能证明唯一 canonical founding unit 且不复活已终结历史的 recovery 协议可以解除。本规范不提供该协议。

## 6. Founding unit 与固定 baseline

§5.4 critical semantic ref 只由本 unit 第一条 `ak.realm.create` 携带，role 按 Contact round / owned Agent provision 分支 exact XOR；第 2–4 条 MUST NOT 再携带这两个 genesis role。四条共同使用已登记分支 proof context，并由 exact atomic unit 的 staged authority-root proof 绑定；同一 context 不表示重复 genesis semantic refs。

### 6.1 四 Event atomic unit

founder **MUST** 一次提交恰好四条 Event：

```text
1. ak.realm.create        携 §5.4 的 critical ref；不承载 membership 边
2. ak.member.state{join}  subject 为 founder 自身；bootstrap no-basis shape
3. ak.member.state{join}  subject 为另一 participant 的显式 canonical membership
4. ak.strand.create       main Strand，scope_circle_id=null，primary discussion track
```

四条注册为 `ak.profile.direct_conversation_realm.v1` 的 closed atomic founding unit：按 wire 顺序验证，同一事务零项或四项接受。create-alone、缺 peer join、缺 Strand、缺 founder join、乱序、不同 actor/pair/profile/Realm 或出现第五条 Event **MUST** 拒绝整组。四条 **MUST** 由 founder author，并使用同一分支 context（`direct_conversation_contact_round` 或 `direct_conversation_agent_provision`，exact XOR），叠加同批 staged authority-root proof。

该顺序同时是 §5.5 的派生顺序，不是可选排版：第 2、3、4 条的 `envelope.realm_id` **MUST** 逐字等于
`retype(第 1 条 event_id, "realm")`，`main_strand_id` **MUST** 逐字等于 `retype(第 4 条 event_id, "strand")`，
unit 内没有任何一条 Event 指向它的前一条：Event 不携带 `domain_refs`，四条的相对次序**只**由这份 wire 顺序给出，并由下文治理 Station 在同一事务内按该顺序签发的 position 连续的四笔 RealmCommit 落定。验证方 **MUST** 从 unit 自身 bytes
重算这两个坐标，**MUST NOT** 采信请求中另行携带的坐标字段，也 **MUST NOT** 接受任何声称先分配后签名的
提交形态。本段任一条件不成立 **MUST** 以 `direct_conversation_founding_unit_invalid` 整组零写入拒绝。

四条的 authority-commit basis 形态是封闭的：`ak.realm.create` 用 genesis bootstrap shape；两条 `ak.member.state{join}` 与
`ak.strand.create` 在**且仅在**该 exact unit 内使用 bootstrap no-basis shape（既不携 `expected_revision`，也不要求
治理 Station 解析出既有授权实例），并叠加同批 staged authority-root proof。两者的免 basis 落点分别登记在
[`../models/realm-and-space.md` §2.5](../models/realm-and-space.md) 与
[`../authz/event-auth-state-resolution.md` §5](../authz/event-auth-state-resolution.md) 的封闭列表。
`ak.strand.create` 平时由治理 Station 解析出既有授权实例后才被接纳，batch admission **MUST** 在本 unit 之外
拒绝它的 no-basis 形态。

一条 RealmCommit 恰好接纳一条 Event。founding unit 的原子性是**事务级**的：治理 Station 在同一个接纳事务内接纳全部四条 Event，为每条各自签发同一 Realm stream 上**连续**的 RealmCommit（position n, n+1, n+2, n+3），并一并落下普通 Realm create 的全部 required founding writes 与 §6.2 的固定投影；**MUST NOT** 先提交 create 再补任一 member join 与 Strand，也 **MUST NOT** 只接纳其中一部分。这也是 `ak.strand.create` 必须免 basis 的原因：它与前三条在同一个事务内被接纳，无法引用那些尚未签发的 RealmCommit。

controller/Agent 分支的第 3 条 Agent join **MUST** 显式携带 `agent_controller_binding`，其 controller AccountId 必须逐字等于 founder，generation ref 必须逐字等于第 2 条 controller join Event ID，且不得携 terminal ref。仅此完整原子 unit 的 admission 可使用同批前序 staged controller join；不得要求第 2 条预先独立 accepted，也不得在整批 accepted 前授予成员资格。receiver **MUST NOT** 推导、补写或替换缺失的 binding。普通 Agent join 仍引用已经 accepted 的 controller join。后续 controller rejoin 不得更新旧绑定或复活旧 Agent join。

### 6.2 固定 baseline 投影

本 profile **MUST NOT** 让 producer 选择"是否追加 policy Event"。`direct_conversation_genesis` contract **MUST** 从 create 与 round 机械投影下列 baseline：

- genesis 的 `initial_join_rule=closed`、`initial_discoverability=invite_only`、`initial_history_access=since_join` 是
  三项 create-locked 常量：producer 不选择，任一取其它值 **MUST** 以 `direct_conversation_founding_unit_invalid`
  整组零写入拒绝（该 Realm 因而不可公开发现或枚举）；
- founding unit 后必须提交该 scope 唯一的 `ak.mls.genesis`，其 accepted RealmCommit 将 scope 不可逆激活为 standard RFC 9420；
- exact-two active participants 是独立 membership/profile 约束。

Agent participation 的 Realm ceiling 读取 MUST 使用该 accepted founding unit 的固定 baseline。
本 profile 不要求也不允许为此追加 `ak.realm.policies`；缺少普通 Realm 的 policy-bundle current
不代表本 Direct 的 baseline 未知。验证 create-locked genesis current 的 covering Commit 与完整
四-Commit founding unit 后，未声明的 Agent participation Realm component 继承部署 ceiling；
这不是默认放行未知治理状态。controller current selection、Strand component、普通 participant
authority、membership、lifecycle 与 MLS gates 仍逐项独立成立，source current／unit 不完整或
坐标不匹配时仍 MUST fail closed。

DC 的 `history_access` 由 create 条件写原子初始化并永久固定为 `since_join`；任何 update 或 `all_history_for_current_members` materialized state 都必须拒绝。

DC 不存在第二套 profile-fixed history sharing 对象。Exact-peer-only 来自 immutable exact-two participant binding 与 current
membership gate，不来自 key-source allowlist。DC 的 `history_access` 永久为 `since_join` 且不存在 update/widen 分支。新 endpoint 只从自己的 Add/Welcome 获得加入后的 standard MLS state；协议不提供加入前历史密钥或群组私态恢复。

`governance_station_id` **MUST** 从 trust domain 已接受的 DM deployment policy 与 founder current service binding 确定性派生，caller **MUST NOT** 自选。founder 把已验证的 current Station service identity 逐字写入 genesis；接收方通过 generation-0 authority bundle 验证该身份与 service DID method history。单侧创建不依赖 peer 设备与 peer Station；只有该治理 Station 完成 admission 并签发 genesis RealmCommit 后，创建才达到 finality。

## 7. 首次物化：bootstrap authority 与唯一 MLS group

### 7.1 三种离线必须分开

任何网络、KeyPackage 或 round 失败 **MUST NOT** 触发自动明文降级。

### 7.2 bootstrap participant authority

binding 尚不存在时普通 DM participant authority 未激活，因此 **MUST NOT** 以 founder、`created_by` 或技术 root owner 身份暗中放行 Message。本规范登记封闭 authority source `ak.authority.direct_conversation_bootstrap_participant.v1`，只含两个由 verifier 从 accepted facts 重算、producer 不可自选的互斥 phase：

1. `provisional_history_send`：founding unit 与唯一 scope-derived group Genesis RealmCommit 已 accepted、对应 current authorization 与 endpoint gates 通过时，仅 founder 可管理自身 leaf、发送 standard MLS Message、claim exact peer KeyPackage 并 author 同组 Add/Welcome；不得放行 policy、grant、第三 participant、其它 Strand 或普通 membership 写。
2. `exact_pair_founding_completion`：该同一 group 的 accepted winning state 已含 exact pair authorized leaves、joiner 已 durable 接受 Welcome、current gates 通过且 binding 尚无合法 endorsement 时，只允许提交 `ak.direct_conversation.bound` endorsement；不得创建第二组、重建 Genesis 或扩大成员。

每条 Event **MUST** 使用该 source 的 registered `authorization_ref`/proof context 并携 action-specific critical refs；owned Agent 分支仍叠加 controller delegation。wire 承载是 `authorization_ref` 的封闭常量
`direct_conversation_bootstrap_authority_ref`（值为 `ak.authority.direct_conversation_bootstrap_participant.v1`），
**MUST** 恰好配一条 critical `semantic_refs[role=direct_conversation_founding_unit]` 指向该 unit 的 accepted
`ak.realm.create`；binding 尚不存在，因此该阶段 **MUST NOT** 使用 `direct_conversation_binding` ref role 或
`ak.authority.direct_conversation_participant.v1`。phase 由 verifier 从 accepted facts 重算，producer 不得在 wire
上声明。首个合法 binding endorsement accepted 后两 phase **MUST** 永久退出，后续业务动作只走
`ak.authority.direct_conversation_participant.v1`。

该退出规则不把 §8.3 的等价背书变成冲突：针对已成立的同一 `binding_digest`，验证方仍 **MUST**
按原 founding completion 证据检查并接纳兼容 endorsement，包括并发提交的后到者与同 participant 的重复背书。
这只是既有 binding 的证明累积，不重新激活 bootstrap phase，也不赋予 Message、MLS 写或新 binding 的权限；
任一语义字段改变的 endorsement **MUST** 在 effect projection 前拒绝。背书继续携原 registered bootstrap
source 与 exact founding-unit ref，不得为重复背书发明新的 authority source 或兼容 wire 分支。

首次 completion 的 durable Welcome **MUST** 属于当前仍 occupied 的 peer leaf 的创建 Add；验证方按 accepted consumed-proposal provenance 的 leaf index 与 Commit 位置判定创建 Add。同一 Commit 的 Remove 针对 before-state leaf，不得因 wire consumed-proposal ordinal 排在 Add 后而移除该 Commit 新创建的 Add 来源，后续 Update 不改变创建来源，Remove 使该来源失效，重新 Add 即使复用相同 actor、endpoint 或 signature key 也必须使用新来源。已移除 leaf 的旧 consumed claim **MUST NOT** 证明新 leaf 已 durable。至少一个当前 authorized peer leaf 的 exact Add/Welcome claim 已 consumed，才满足 joiner durable 条件；其余 current gates 与 exact-pair roster 检查不变。

首次 Add 的 claim terminal 后，founder 在 `provisional_history_send` 内 **MAY** 通过同组 ordinary Remove/re-add 替换该 exact peer endpoint，使用 fresh claim 与 fresh Welcome；不得迟到 consume、复活旧 claim、扩大 pair 或重建 Genesis。`initial_exact_pair_group_state_ref` 永久指向首个 accepted exact-pair winning state；repair completion 只更新当前 occupied leaf 的 durable 证据，不改变该 immutable ref、founding basis、binding digest 输入或坐标。



既有 holder-authenticated `ak.self.contact.read.list.v1` 的 accepted human row MAY 携闭合
`peer_endpoint{contact_event_ref,device_id}`，其它状态与 Agent row MUST NOT 携带。自己的 Station MUST
从所选当前 accepted round 的已验签并耐久保存的 source receipt producer 机械导出：normal round 的
requester 端取 peer response producer，target 端取 peer request producer；glare 取 peer 的原 request producer。
来源必须逐字绑定 row 的完整 peer AccountId、当前 round、原 request/response Event ref、issuer Station
与 human device method（principal DID 的 exact DeviceId fragment）。缺来源或任一绑定不成立时省略。
投影不要求客户端读取 peer PCR，也不依赖瞬时缓存或显式 continuity export；重载、重试及另一 holder
设备重新读取同一投影。contact_event_ref 是所选 round 的 exact peer 来源；glare 的两条 request 可不同于 row 的单一 request 摘要，客户端不得据摘要重建或替换该引用。

它只提供 exact KeyPackage claim selector，不证明持续 Device/MLS authority。客户端仍须每次使用现有
current KeyPackage claim、设备 generation/revocation gate 与 Realm governance 验证后才能 Add/Welcome；
撤销、轮换、无可用 package 或缺投影时失败关闭，不猜设备、不枚举全设备、不以 Contact producer 替代
当前签名者证据。既有 Contact 当前授权及 scope gates 不变。

### 7.3 唯一 group 与 repair

DM Realm 与所有其它 MLS-backed effective scope 使用同一规则：
`mls_group_id` 按 [`../models/realm-and-space.md` §2.2](../models/realm-and-space.md) 的唯一派生式从该 scope 算出，每个 scope 恰有一个 immutable group 与从零开始且永不重置的 epoch lineage。
首次 `ak.mls.genesis` 是 create-once；不存在第二个 group、候选 group、epoch reset 或额外 group selector。

Founding、peer Add 和以后 repair 都只通过该 group 的 ordinary winning Commit 推进。只要至少一个 current authorized live member
持有 private state，它可 author Remove/re-add Commit 和 Welcome；所有 reducer、authority-commit 与 key-access-revision 规则与普通 MLS Commit 相同，
不得为 DC 新增 winner、barrier 或 quorum。Message 必须引用 event-time exact winning group state，后续 Commit 不追溯否定旧 Message。

若所有成员均丢失该 group 的 private state，则旧 encrypted DC scope 永久终结：不得用同一 derived group id 重放 Genesis、把 epoch
归零或激活第二组。同一 stable participant pair 与同一 trust domain 下也不得创建 successor DC Realm；resolver 保持 `suspended`，服务端只能返回已登记且可由当前状态证明的 `state_mismatch`，不得把设备私态丢失猜测成新的 wire 共识状态。只有实际不同的 stable participant pair 或不同 trust domain 才会按 §5.1 自然得到不同 `pair_key`
并进入新的普通建联流程；该新会话不是旧 lineage 的恢复，旧 Realm 的历史、backup、proof 与 epoch namespace 不与其合并。

### 7.4 standard MLS 私态边界

客户端按 RFC 9420 保存并演进本地 group state。Arkret operation、Event、portable backup 与治理 Station均不得导出或恢复成员的 epoch secret；新 endpoint 只通过自己的 Add/Welcome 进入当前 epoch。

## 8. Stable identity、repair 与 participant authority

### 8.1 稳定坐标

同 pair 只有一个 immutable Realm 与 main Strand。leave、block、tombstone、scope 撤回、Agent pause、erasure 或恢复 **MUST NOT** 创建替换 canonical main 的 successor Strand、successor Realm 或 binding；这不禁止在稳定 binding 后显式创建同 Realm 的额外普通 discussion Strand。

canonical DM Realm **MUST** 拒绝 `ak.realm.destroy` 与任何 `ak.realm.tombstone`（`direct_conversation_terminal_forbidden`）。`ak.realm.archive` 与 `ak.realm.freeze` 是普通可逆 facet：具备合法 authority 与 CAS basis 时可设置，且 **MUST** 保留普通 unarchive/unfreeze 路径；它们只令 resolver 附带 send blocker，**MUST NOT** 产生 successor 或新坐标。

若错误实现或对象冲突仍使 canonical Realm 进入 terminal 或不可判定状态，pair **MUST** 按 §5.7 `suspended` 并等待显式 recovery；本地 slot **MUST NOT** 回到可创建状态。自动重开会再次允许第二个 Realm，正好破坏 founder-only 唯一性。

### 8.2 rejoin 后的 MLS 收敛

标准 `ak.member.state{join}` / `ak.member.rejoin.own` 被 accepted 后本身就是 durable 收敛触发事实，不存在第二条 repair 消息、dispatch 或 relay。profile 只允许主体恢复既有 pair/Realm/main Strand 的二人 membership；human 只能 self-rejoin，owned Agent 仍使用 `actor_id=agent_id, executed_by=controller_account_id` 与 immutable controller authorization。它不得加入第三 participant，也不得取得 grant、policy、admin、Strand 或 binding 变更权。

只要至少一名 current authorized member 仍持有该唯一 group 的 private state，其普通同步器观察 accepted membership 变化后，按既有 KeyPackage claim 合同取得回归方 exact package，并在同一 group author 普通 Remove/Add Commit 与 Welcome。该流程完整复用普通 Commit winner、key-access revision、claim consumption 与 Welcome admission；DC 不定义专用 carrier、operation、queue、feature、barrier、quorum 或幂等账本。

**自有 Agent runtime 端点收敛（normative）**：`agent_controller` 分支中，accepted runtime-key authorization 的替换也触发普通端点收敛；它不改变二人 Actor membership，不要求再次 join/rejoin，也不推进 `key_access_revision`。有 current authorization 且保有该唯一 group 私态的 controller endpoint，其普通同步器在获知授权变化或重新读取相关 current 状态时 **MUST** 比较 verified occupied roster 与当前完整 Agent endpoint `(agent_id, verification_method, authorized_event_ref)`；不能仅因 ActorId 已在 group 而跳过。授权、controller binding、Agent active、membership 与 scope gates 全部成立且当前端点缺失时，**MUST** 按既有合同取得该端点的 exact signed KeyPackage claim，并在同一 ordinary winning Commit 中 Remove 同一 Agent 的旧 runtime leaf（若存在）、Add 当前端点、交付其自己的 Welcome。只替换同一完整 ActorId 的 Agent runtime；同一 human Actor 的不同 device 是独立 leaf，不得据 ActorId 合并或移除。

当前完整端点已在 verified roster 时 **MUST NOT** 因重复观察同一授权而再次 Add。缺少 current authorization、合法 fresh claim 或任何 current gate 时失败关闭／等待对应依赖；不得以旧 leaf 或旧 membership 代替授权。该恢复不改写 Realm、Strand、pair、founding authorization basis、binding digest 或 initial exact-pair ref，不要求新 binding endorsement，不复制旧 active MLS state，不回退 epoch。所有私态丢失仍适用 §7.3；同步通知只唤醒重读，不能成为 Add authority。

任一 directional Contact 已撤回时，membership Event 可以被保存，但 KeyPackage claim、MLS Add 与发送必须保持拒绝，resolver 返回 `suspended`。若没有成员保有 private state，则按 §7.3 终结旧 encrypted DC scope；同一 pair / trust domain 没有 successor Realm。

### 8.3 binding 与日常 authority

`ak.direct_conversation.bound` **MUST NOT** 承担阻止第二个 Realm 的职责——唯一性来自 §5.4 的 admission。它是 coordinates 与首次 exact-pair group state 的 participant 可见凭证，wire payload 绑定 `pair_key`、`unordered_participant_ids[2]`、`realm_id`、`main_strand_id`、`founding_unit_digest`、分支化 `authorization_basis` 与 `initial_exact_pair_group_state_ref`。`binding_digest` 是下述内容的 receiver-derived semantic digest，**不是 wire 字段**。

receiver 先必须验证 payload 的每个字段与 accepted founding unit、唯一 main Strand、canonical authorization basis 及该 pair 唯一 group 的 exact-pair winning state 一致，再构造以下唯一 closed object。`p0/p1` 是 wire `unordered_participant_ids` 中两个 exact `ActorId` 按 unsigned RFC 8785 JCS bytes 升序排列的结果；派生对象的字段名固定为 `participants_unordered`，不是 wire 别名。`e0/e1` 是 `authorization_basis.event_refs` 中两个 accepted Event ref 按 unsigned UTF-8 bytes 排序的结果。排序只用于此派生对象，**MUST NOT** 改写已签名 Event bytes。

```text
binding_object = {
  "pair_key": pair_key,
  "participants_unordered": [p0, p1],
  "realm_id": realm_id,
  "main_strand_id": main_strand_id,
  "founding_unit_digest": founding_unit_digest,
  "authorization_basis": {
    "kind": authorization_basis.kind,
    "event_refs": [e0, e1]
  },
  "initial_exact_pair_group_state_ref": initial_exact_pair_group_state_ref
}

binding_digest = H("ak.direct-conversation.binding-digest.v1", binding_object)
```

`H` 的精确定义见 §2：实际前像为 `UTF8("ak.direct-conversation.binding-digest.v1\n") || RFC8785_JCS(binding_object)`，结果为 `sha256:<lowercase-hex>`。`created_at`、Event envelope 的 author/proof 与 `binding_digest` 本身都不在 `binding_object` 中，因而不存在“先放入再排除”或自指前像。实现 **MUST** 执行 [`ak.vector.direct_conversation.binding_digest.v1`](../../artifacts/registry/vector-registry.json) 的逐字节 KAT，**MUST NOT** 使用无 domain 的 `SHA256(JCS(payload - created_at))`。

binding typed current result 即已登记的 `direct_conversation_binding` family，**MUST** 使用 `commit-ordered projection`、`value_shape=set`，由 Realm 的唯一确认序列执行。元素 tag 仍按注册 Event dot 派生，value 为 payload；`(binding_digest,envelope.actor_id)` 只是领域 endorsement 去重键。同一 participant 对同一 digest 的顺序确认记录只计一个 endorsement。双方对相同 semantic payload 的签名可以共存，但同旧 revision 的竞争命令不能跳过 CAS：后执行者若前态已变则重新 author 后再确认。不同 binding digest 在投影前拒绝并产生 suspended 诊断。found 至少需要一份合法已确认 endorsement；base 不要求双方同时在线。

**发送证据与展示引用（normative）。** `ak.direct_conversation.bound` 是 `committed=true` 的 state-changing Event；
仅存入 ingress 或出现在查询投影中不等于可授权。普通 participant Message 的唯一 critical
`direct_conversation_binding` ref **MUST** 指向该 Realm 已确认序列接纳的一份合法 endorsement，且该 endorsement
的 semantic `binding_digest` **MUST** 等于当前无冲突 binding。服务端在列表中选择的代表 Event ref
不是额外的 authority head：**MUST NOT** 要求 Message 逐字引用该代表，也 **MUST NOT** 因后来出现另一份
等价 endorsement 而否定先前已覆盖的引用。上述覆盖与 authority 条件由服务器 admission 验证。
客户端信任自己的 Station，使用 resolver `found.coordinates.binding_event_ref`（found MUST 提供一份
合法已接受 endorsement 的完整 EventId）、current `group_state_ref` 和精确
`event_commit_submission_decisions` 的 committed 结果取得 authoring 坐标；只核对本地操作的 actor、Realm、intent
与 basis 绑定，不下载或重放历史 Event/RealmCommit 闭包。base 客户端 **MUST NOT** 等待所有可见 endorsement
被覆盖，或要求两方各一份确认。缺少当前供料时只等待相关 exact 服务端结果，不改变坐标、
不重建 group、不放松 current Contact、membership、endpoint 或 lifecycle gate。该规则不取代 §7.2
尚未建立 binding 时的 provisional founder Message authority。

binding **MUST NOT** 携带 `binding_state`、`supersedes_binding_ref`、永久 `mls_group_id` 或 consume receipt，也 **MUST NOT** 改变 membership、MLS、policy 或 Realm 坐标；若未来增加此类字段，**MUST** 拆为独立安全命令。

日常写 authority 唯一来自 `ak.authority.direct_conversation_participant.v1` 与接收 Station 本地已验证的 accepted binding、exact-two membership、双方 directional Contact 授权区间、唯一 group 的 exact-pair winning state 及 action-specific lifecycle gate 的交集。这里的普通准入采用 §3 的已验证区间与已知撤销规则，不要求逐次刷新 source current lease 或联络 origin / 治理 Station；初次缺证仍 pending，已知撤销立即阻止新 live。技术 root、`created_by`、founder 身份、本地 slot 与普通 grant **MUST NOT** 替代该 evaluator。root mask 只允许 current materialization 的精确 founding/repair effects；`found` 后 **MUST NOT** 恢复 owner/admin authority。

**授权基础的分支必须贯穿 current gate（normative）**：上文的双方 directional Contact gate 只适用于
`authorization_basis.kind="accepted_contact"`。`kind="agent_controller"` 的 controller↔自有 Agent 分支
不建立或要求 Contact；bootstrap send、MLS Add/Welcome、bound 后日常动作与 repair 均改验 §5.4 的 exact
controller/Agent Account pair、accepted 且仍 current 的 provision/controller binding、Agent active lifecycle 与
当前有效 runtime-key authorization，并继续叠加 action-specific endpoint、membership 与 delegation gates。
不能只凭 founding slot 或裸 principal 判定 ownership，不能把此分支用于 Agent↔第三方。合法 runtime-key
替换不改写原 founding `authorization_basis` 或 binding digest；旧 endpoint 随当前 key authorization 失效。

### 8.3.1 Chat 与平铺 Topic 的结构动作（normative）

Direct Conversation 保留 stable pair／唯一 DM Realm／binding。Main Chat 是 immutable main_strand_id；Chat 是同 Realm、non-Circle、active primary discussion 的普通 Strand。Topic 是同 Realm root Space(kind=topic)，parent_space_id MUST 省略；不建立 Collection、Board 容器、嵌套 Topic 或额外 MLS group。默认只创建 Main Chat，不自动创建 Topic，不新增 ChatId／TopicId；topic 是与 list、board 并列的独立 Space kind。

每个 Chat 至多一个 Topic，分类唯一真相是 strand current 的可选 topic={space_id,rank}；rank 为 1..128 位 ASCII 字母数字。省略 topic 表示未分类。Main Chat 可分类但身份不变。Topic 只影响共享导航，不承载消息，不改变成员、历史资格、Realm default pointer 或模型会话。MUST NOT 为 DM 分类写 Board-scoped position 或 contains Relation。

稳定 participant 对等拥有封闭九动作：ak.strand.create/update/archive/restore 与 ak.space.create/update/archive/restore/tombstone。所有动作在同一 authority cut 验证 canonical main 锚点和实际 target；create 校验 event-derived 新对象，不要求 target 已存在。bootstrap 不增加结构权限。current Contact／owned-Agent controller、provision/runtime、membership、device、executor delegation 与 participation gate 均保持；technical root、created_by 或普通 grant 不替代 participant authority。

| 动作 | 精确 target、字段与生命周期 |
| --- | --- |
| Strand create | active 同 Realm non-Circle primary discussion；仅单 discussion track，无 description、stage、schema 扩展、Agent ceiling 或初始 topic；标题使用 encrypted_metadata。 |
| Strand update | 同 Realm active Chat；仅整体 set encrypted_metadata，或 topic 的显式整体 set／unset。不得写 topic 子路径、直接值、null、tracks、content、stage、scope 或 metadata 明文。每次 topic 变更 MUST 带 expected_state_digest，等于完整前像 strand current canonical JSON 的 SHA-256；不匹配按现行 CAS 零写入拒绝。set 的 Topic 必须是同 Realm active non-Circle root Topic Space。unset 必须已有 topic，可解除归档 Topic 的引用。标题更新不要求分类 CAS；二者同写时仍要求 CAS。 |
| Strand archive/restore | 仅额外 Chat，沿用 active→archived／archived→active；不得 archive/redact main 或破坏 main 锚点。分类保留，不级联 Topic lifecycle。 |
| Space create | 仅同 Realm non-Circle root Topic Space，无父容器、schema 扩展、用户明文 metadata、fields 或 child_scope_policy；metadata 必须加密。 |
| Space update | 同 Realm root Topic Space；仅整体 set encrypted_metadata 或合法 rank；不得写 kind、scope、schema、WIP、parent 或 child policy。 |
| Space archive/restore/tombstone | 独立 Space lifecycle，无隐式分类迁移；tombstone 必须无有效 topic 引用，archived Chat 的引用同样属于活依赖，拒绝 reason=space_has_live_dependents，零写入。 |

ak.strand.move/reorder 与 ak.space.parent 不属于此 participant 扩展。分类通过 ak.strand.update；首次分类、换 Topic、Topic 内排序均整体 set topic，取消分类显式 unset。取消后保留 strand current revision 与历史，不删除 Chat／消息或重建 Strand。Topic 内按 rank、相同 rank 时按 Strand ID 稳定排序。Topic 自身按 Space rank、相同 rank 时按 Space ID 排序。客户端基于获授权完整 current 显式生成 CAS，不补隐式前像。

结构权限失败折叠 direct_conversation_participant_authority_denied；未登记 Space kind 保留 direct_conversation_space_forbidden。合法 authority 后 CAS、FSM 与活依赖 gate 保留各自 reason。Topic archive 不归档 Chat；不得向 archived/tombstoned Topic 新分类，已有归属保持，全部聊天／通知可找回 active Chat。失效引用保留历史，等待显式 unset／换 Topic，不自动迁移、复活或清空上下文。

Chat／Topic 用户 metadata 使用同一 Realm group 下的完整 encrypted_metadata；create/update/current/read/snapshot/replica 无用户明文标题镜像。必要结构 ID／kind／topic／rank 可见。消息、reaction、read cursor、草稿、通知、导航及 Signal recipient 解密后校验以实际 Strand 为准。Agent 默认以实际 (realm_id,strand_id) 隔离模型输入并回复原 Strand；同 Topic 下两个 Chat 不合并，换 Topic、改名、archive 不重建会话，生成中的回复不跟随 UI selection。跨 Chat 引用须显式且获授权。

### 8.3.2 每个 Chat 的个人通知设置（normative）

稳定 participant authority 的单 Event 动作 allowlist 另包含 `ak.strand.watch.set`，它不是 §8.3.1 的结构动作。仅允许 participant 写自己的完整 `(strand_id, watcher_actor_id)` cell：`payload.watcher_actor_id` MUST 逐字等于 envelope 的完整 `actor_id`，target MUST 是同一 DM Realm 内 non-Circle Chat 的实际 Strand。必须携带既有 participant authorization_ref 与合法 accepted binding endorsement ref；bootstrap source、technical root、普通 grant 和 founder 身份不授予该动作。

该权限不包含 `ak.strand.watch.set.others`，包括写 pair 中另一 participant 的 cell；失败按 closed participant evaluator 折叠为 `direct_conversation_participant_authority_denied`，零 durable 写入。membership、Contact／owned-Agent controller、MLS、device、executor delegation 与实际 target lifecycle gates 均继续适用。合法 authority 后保留 Strand watch whole-value CAS、读回与本人私有披露规则；未写 cell 的默认 mentions-only 不变。通知按实际 Strand 路由，不按 Main Chat 或 Topic 汇总后冒充目标。

### 8.4 admission reason producer 与优先级（normative）

Direct Conversation 的普通单 Event 写入继续使用 `ak.self.events.command.submit.v1`，请求中的 signed Event 位于
`/event`，拒绝继续使用既有
`authority-commit-operations.schema.json#/$defs/submit_outcome` 的封闭
`{status="rejected",reason_code}` 分支；本节不新增 endpoint、批次或第二种 problem carrier。唯一机读规则表是
`contract-registry.json#operation_registry/direct_conversation_admission_mappings`。每条规则必须在签发
RealmCommit 之前求值；命中时 Event、RealmCommit、typed current projection、outbox、成功幂等记录与其它 durable
effect **MUST** 全部保持零写入。拒绝不是已提交 exact replay；后来重试必须对届时 authoritative state 完整重算，
不得复用缓存的允许或拒绝。

七条 semantic producer path 的唯一执行者是目标 Realm 的 **current governance Station**。Account Station 的 self ingress 只完成 session、producer proof 与 exact bytes 的路由/转发；不在 edge 判定以下七条 reason，也不保存第二份 profile admission outcome。跨站时使用 `ak.peer.events.command.submit.v1` 的 `authority_forward` 分支，self 响应原样回传 authority outcome；同站时可在同一事务内直接调用相同的 authority evaluator。已提交的 replication 只验证 source Commit 并物化，不重做七条 admission、不重签 Commit、不形成第二个 accepted 状态。reason precedence、零写入与后来重试的重算均以该唯一 authority transaction 为准。

结构化规则表中的七条 producer path 与正文义务一一对应：

- `binding_integrity` 只处理 `ak.direct_conversation.bound` 的 immutable cross-field／accepted-fact 比对，失败为
  `direct_conversation_binding_invalid`；
- `terminal_guard` 在普通 Realm authority 之前拒绝 canonical DM 上的 `ak.realm.destroy` 与
  `ak.realm.tombstone`，失败为 `direct_conversation_terminal_forbidden`；archive、freeze、restore 与 unfreeze
  不命中该规则，继续普通 authority；
- `exact_two_projection` 在 action authority 之前验证 binding 与 authoritative membership 都解析为相同的两个
  distinct principal。membership 的 participant 集是该 Realm 全部 member typed current 行（`join` 或 `leave`）的
  distinct principal：participant 离开不会使集合缩为一人，因此 §8.2 的主体 self-rejoin（`ak.member.rejoin.own`）
  通过本 gate、交由 participant evaluator 判定，pair 外 principal 出现即不符；新写失败为 `direct_conversation_member_count_invalid`。resolver 对已经存在的 Realm 只读返回
  `state="suspended"` 与结构化表登记的 exact-two blocker，不得伪造一次写拒绝，也不得产生 durable write；
- `third_party_member_guard` 比较 invite/join candidate 与 immutable pair，pair 外候选失败为
  `direct_conversation_third_party_member_forbidden`；
- `invite_guard` 拒绝 active DM 的 invite，失败为 `direct_conversation_invite_forbidden`；atomic founding unit 中的
  peer join 不是 invite，不进入该 stage；
- `root_phase_mask` 在 owner aggregation 之前拒绝技术 authority-root 对当前 exact founding/materialization mask 之外的
  operational、grant、member-governance、policy 或 terminal family 动作，失败为
  `direct_conversation_root_mask_violation`。「依赖技术 authority-root」的判定式是：Event actor 是该 Realm
  authority-root typed current 的当前 controller，且该 Event 不在 participant allowlist 内（或是作用于另一成员的
  `ak.member.state` 边）、不是 `ak.direct_conversation.bound`，且其 kind 有登记的 capability action。mask 是 closed
  集合：founding 阶段只有 §6.1 的四 Event unit，materialization 阶段只有该 scope 唯一的 `ak.mls.genesis` 与加入
  另一 participant 的同组 Add／Welcome `ak.mls.commit`；`found` 之后 mask 为空。机读形态见结构化表该规则的
  `root_reliance` 与 `masked_actions`；
- `ak.authority.direct_conversation_participant.v1` 的 closed evaluator 对 allowlisted action 求值所有 activation checks。
  任一 binding、participant、membership、Realm/Strand/MLS、Contact、device、Agent、resource 或 lifecycle 输入失败，
  都只返回 `direct_conversation_participant_authority_denied`；不得暴露失败项，也不得回退到 consent、
  `created_by`、Realm owner aggregation 或本地 projection row。

上述 `direct_conversation_participant_authority_denied` **只由 Event-mapped action 的单 Event submit 产生**。`ak.call.signal.send`、`ak.receipt.broadcast`、`ak.typing.broadcast` 是密文内产品动作，不能作为 `/event` 或 Station 外层 Signal selector；它们的解密后产品策略由接收端校验。Signal 外层按 [`sync/signal.md` §3](../sync/signal.md) 的可见字段执行 participant、membership、scope、MLS basis 与 `signal_class` gate，使用 Signal 自己的拒绝/丢弃载体。

多条件同时命中时必须严格使用结构化表的 `precedence`。尤其 pair 外 invite 同时命中 third-party 与 invite guard 时，
必须返回 `direct_conversation_third_party_member_forbidden`；具体 destroy/tombstone 同时依赖 root 时，必须返回
`direct_conversation_terminal_forbidden`。实现不得按检查代码的偶然顺序、诊断字符串或缓存可用性选择 reason。
[`direct-conversation-admission-fixture.json`](../../artifacts/fixtures/direct-conversation-admission-fixture.json) 与七个
`ak.vector.direct_conversation.admission.*.v1` vector 分别固定每条规则的允许对照、exact reason 负例、零写入和双重命中优先级；
一个 aggregate founding 拒绝或一个泛化示例不能替代任何一项。

## 9. Resolver、隐私与 SDK 边界

### 9.1 resolver 状态

`ak.self.direct_conversation.read.resolve.v1` 是唯一查询入口，其 outcome 为封闭判别联合：

| state | 条件 |
| --- | --- |
| `creation_required` | 无 accepted DM Realm，本方 `== founder`，且 current gate 允许创建；**MUST** 携带 §9.1.1 的 `next_founding_input` |
| `creation_blocked` | 无 accepted DM Realm 且本方 `== founder`，但 current Contact/account/Agent/profile/governance-Station gate 确定性拒绝；**MUST NOT** author genesis Event 或派生 Realm token，也不得诱导重试 |
| `awaiting_founder` | 无 accepted DM Realm 且本方 `!= founder`；等待时长 **MUST NOT** 改变 create authority；即使 exact founder authority 永久不可恢复，v1 也不把权限转给 successor，不另造“永久丢失”wire state |
| `provisional` | 唯一 founding unit 已 accepted 但尚无合法 binding；只可执行 §7.2 的封闭 bootstrap 动作 |
| `found` | 至少一份合法 binding endorsement、唯一 group 的 exact-pair winning state 与普通 participant authority evaluator 均通过 |
| `suspended` | 已有 Realm 但 materialization/object conflict、terminal fault 或 membership/Contact/Agent/account/MLS/governance-Station/lifecycle gate 阻止继续；blocker **MUST** 可机读 |
| `temporarily_unavailable` | 必需依赖不可验证，无法安全归类 |

求值优先级固定：依赖不足以验证 current round 或 founder 时 `temporarily_unavailable`；无 Realm 时区分 `creation_blocked | creation_required | awaiting_founder`；有 Realm 后 identity/materialization/terminal/governance-Station 冲突优先 `suspended`；否则无 binding 为 `provisional`；最后才在 binding、unique group state 与 daily gates 齐备时 `found`。`retry_after` 只是调度提示，**MUST NOT** 产生 fallback authority。

`provisional` **MUST** 携带 `peer_mls_admission`，只读供料值为封闭集合 `missing | pending | durable | repair_required`，以同一 governing cut 的 current occupied peer leaf 创建 Add、exact Welcome/claim binding 和 recipient durable consume 为依据。无 occupied peer Add 为 `missing`；至少一个 occupied authorized peer leaf 的 exact claim consumed 为 `durable`；否则至少一个 exact claim 仍在有效等待期限内为 `pending`；全部对应 claim terminal/已过期为 `repair_required`。缺少必要 provenance 或无法验证 claim 状态时服务 **MUST NOT** 猜测 terminal，返回依赖不可用并保留既有坐标的本地缓存。该状态仅向通过既有 exact-pair/current authorization read gate 的 caller 供应，不披露 raw claim ledger、endpoint 清单或第三方状态。

客户端只在 `missing` 或 `repair_required` 时执行相应 fresh admission；`pending` 时等待 exact durable consume，不因本地时间、opaque claim failure 或 roster 已含 peer 而重做 Add；`durable` 时才尝试首次 binding。供料不是写权限，接受事务 **MUST** 重算所有事实，陈旧供料不能放行 Event。首次 exact-pair state 已存在时 `provisional` 还 **MUST** 携带 `initial_exact_pair_group_state_ref`，逐字等于 immutable 首次 ref；binding author 不得用当前 epoch 的 Commit 替代它。

`provisional` **MUST** 携带 `authorization_basis`，其值必须逐项等于 accepted founding unit 所固化的原始授权依据（§8.3）。客户端直接使用该依据 author binding，**MUST NOT** 以 current Contact round、current runtime key 或跨流时间推断重建它。该供料不授予额外权限；binding integrity 与 current participant/bootstrap gates 仍独立执行。

resolver 对已存在的 unique group winning state **MUST** 返回完整 `group_state_ref`，不存在 winning state 时省略。该 ref 是 winning Genesis/Commit 的完整 Event ID，suite 与全部 Event digest bytes 均从 ref 无损恢复，MUST NOT 再返回 sibling `group_state_digest`。
`found` 必有该 ref；`provisional`/`suspended` 在 winning state 已存在时也不得隐藏。客户端不得从最大 epoch、局部 MLS snapshot 或坐标猜 Event ID。

existing 坐标 **MUST NOT** 因 offline、presence、session、KeyPackage 库存、grant/policy freshness 或 MLS reconcile 而被隐藏。

#### 9.1.1 `creation_required` 的 authoring material（normative）

`direct_conversation_founding_unit_submission` 的 closed shape **不携带** `founding_authority_evidence`：founder 与验证方是同一台 current Station，§5.5 的 self admission 在同一事务内以服务端自己 current 的 Contact round（或 Agent provision）证据校验四条 Event；caller 回传的副本既不进入 `founding_unit_digest` 等任何幂等身份，也不可能成为可信输入，因此不存在于 wire 上。Event origin authority 已由四条 Event 的完整 actual-author `ActorId` 及服务端追加的 admission proofs 表达。

但 founder 仍需要领料才能构造该 unit：§6.1 第一条 `ak.realm.create` 的 §5.4 critical ref、四条共同使用的分支 context、固定首次身份／本轮坐标与 §6.2 派生 baseline 都取决于 pair 当前的 Contact round（或 Agent provision）证据。若 resolver 只回一个无 material 的
`creation_required`，则 founder 在协议层无法确定这些输入——这正是
[`service-http-binding.md`](../sync/service-http-binding.md) §2.2.4 供给闭合律禁止的形态。
因此：

- `creation_required` **MUST** 携带 `next_founding_input {founding_authority_evidence}`。它是 founder 构造
  四条 Event 的领料容器，**不是** submission 的回声：caller 从中读取 固定首次身份、本轮与 binding 坐标去
  author 与签署 Event，**MUST NOT** 把该对象再放回 submission；submission 的 closed shape 对同名成员直接
  `schema_violation`，服务端 **MUST NOT** 以任何私有载体重新收取它。服务端 **MUST NOT** 在该容器里附带
  Event bytes、坐标、`idempotency_key` 或 receipt——四条 Event 仍由 founder 自签，服务端**永不**代签。
- 服务端 **MUST** 按本 pair 选择唯一分支：peer Contact founding 用 `human` 分支（含完整
  bundle 与固定首次身份），own-Agent founding 用 `controller_agent` 分支；
  **MUST NOT** 同时返回两个分支，也 **MUST NOT** 返回与 §5.4 验证口径不同的另一份证据。
- **无料时不得返回本状态**：服务端组装不出或验证不了该 material 时 **MUST** 返回
  `temporarily_unavailable`，**MUST NOT** 返回不带容器的 `creation_required`，也 **MUST NOT**
  为此新增错误码或状态值——求值优先级表里 `temporarily_unavailable` 本就覆盖"依赖不可验证"。
- **新鲜度**：该 material 是响应时刻的快照，**不是** authority。caller **MUST NOT** 跨
  Contact 状态变化复用它；material 在提交时已陈旧的，submission 侧按 §5.4/§6 既有校验拒绝
  （round 不匹配、固定身份／授权实例不匹配、binding 非 current），**MUST NOT** 因为 Event 是依据 resolver
  供料 author 的就放宽任何一条校验。submission 不携带 evidence，服务端 **MUST** 以自己 current 的那份
  证据校验 unit，**MUST NOT** 依赖任何 caller 侧的证据副本。
- **并发 founder 设备**：同一 founder 的多台设备 **MAY** 同时取得 `creation_required` 与
  相同 material；胜负仍只由 §5.5 的 `(founder_id, trust_domain_id, pair_key)` slot CAS 决定，
  失败方得到 `direct_conversation_slot_already_committed` 后 **MUST** 改走 resolver 取回既有
  坐标，**MUST NOT** 用自己那份 unit 重试。material 相同不构成"两份 unit 等价"。

联邦面与 self 面不同：`ak.peer.events.command.submit.v1` 的 `direct_conversation_founding_federation_submission`
**MUST** 显式携带 `founding_authority_evidence`——接收方是另一台 Station，读不到 source 的 Contact round / Agent
provision 状态，该成员是跨信任域的真实载荷，由 source 服务器在 server-to-server 一跳上投影供给并由接收
Station 独立验证；**MUST NOT** 要求 founder 客户端亲手跨服务器搬运这些证据，接收方也 **MUST NOT** 把搬运副本
当作 authority。

实现 **MUST** 执行 [`ak.vector.direct_conversation.founding_authoring_material.v1`](../../artifacts/registry/vector-registry.json)：
它断言容器存在性、单一分支、无 Event bytes / 坐标 / receipt、无料时降为
`temporarily_unavailable`、self submission 的 closed shape 拒绝同名回声成员，以及联邦面对 source 投影
evidence 的显式携带与接收 Station 的独立重新验证。

#### 9.1.2 Origin authority 供给（normative）

Direct Conversation founding 不建立独立 principal↔service binding object。resolver 只返回可验证的 `founding_authority_evidence`；caller author 的每条 founding Event 已签入完整 `ActorId`，负责 founding 的服务按该 ActorId 路由完成本地 pair/device admission 后提供本节要求的 founding 证据。任何缺少该 pair、proof 不匹配或 founding source 与证据不符的情况返回 `temporarily_unavailable` 或 fail closed，不得现场代 principal 签名。本节仅限定安全 founding 的来源证明；不得将其扩展成普通 Message 的 origin 联署、收据或在线准入要求。既有 binding 上的普通发送按 §3 与 §8 由接收 Station 独立验证。


**send blocker 的权威边界（normative）。** wire 上的封闭枚举 `direct_conversation_send_blocker`（[`direct-conversation-operations.schema.json`](../../artifacts/schemas/direct-conversation-operations.schema.json)）**MUST** 只承载 server-verifiable blocker：服务端 **MUST** 能从它有权读取的 accepted authoritative state 证明该值，**MUST NOT** 猜测、解密或把客户端自报当作 authority。`personal_blocked` 是 holder-private account data，只能由 holder client 在本地判定。

这个值由封闭的 **client-local blocker 集合** 承载，登记在 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 的 `ak.profile.direct_conversation_realm.v1#client_local_send_blockers`，其值恰为：

```text
client_local_send_blocker = "personal_blocked"
```

该集合 **MUST NOT** 出现在任何 wire 面：不进入 resolver outcome、任何 operation 的 request/response、任何 Event payload，也不进入 peer carrier 或联邦面。客户端在本地把它与 wire 返回的 `found.send_blockers[]` 合并，再决定是否放行发送。本规范只定义该封闭集合的语义与取值；类型实现属于共享 SDK 层，各客户端 **MUST NOT** 各自另立一套值。

缺少当前 MLS group、epoch 或发送密钥时，客户端仍 **MUST** 在现行 MLS 发送就绪检查处 fail closed；这不属于 Direct Conversation client-local blocker，不得将旧历史密钥专用值恢复到封闭集合或 wire。

client-local blocker **MUST NOT** 令 resolver 返回 `suspended`，也 **MUST NOT** 改变任何 wire 状态：它只影响客户端本地是否放行发送。否则服务端状态会被本地状态污染，同一 pair 在两台设备上会得到不同的 resolver 结论。

`presence_offline` 与 `keypackage_empty` 保留在 wire（服务端确有可证事实），但 **MUST** 只对该 pair 的 existing exact-pair participant 返回；其它任何调用方 **MUST** 得到与"该 pair 不存在"逐字相同的 opaque failure，**MUST NOT** 借这两个值做非参与者枚举或探测。反过来，真实 participant 的 existing 坐标 **MUST NOT** 因为对端离线或 KeyPackage 库存为空而被隐藏。

**连带后果（normative 提示）。** 因为拉黑是单方面本地过滤，"我拉黑了对方，所以发不出去"这件事**只有客户端自己知道**：服务端不知道，对端也不知道，而且本就不该知道——让任一方知道就等于把 holder-private blocklist 泄漏出去。这正是拉黑应有的语义，但习惯"发送前先问服务器要状态"的实现会在这里踩空：resolver 会返回 `found` 且 `send_blockers[]` 为空，发送仍 **MUST** 被客户端本地拦下。实现 **MUST NOT** 为了让服务端"看见"拉黑而新增任何上报、同步或探测通道。本条的规范执行向量是 `ak.vector.direct_conversation.send_blocker_authority.v1`。

### 9.2 隐私

DM Realm、其成员、Strand、MLS 状态、本地 slot、founder 身份、pending 状态，以及"该 pair 正在创建私聊"这一事实本身，**MUST** 只对两个 participant 及合法 owned-Agent controller 可见。其它任何主体 **MUST** 得到与不存在逐字相同的 opaque failure；不存在、不可见、policy deny、authorization deny 与 quarantined **MUST** 共用同一失败形态。DM Realm **MUST NOT** 出现在 directory、discovery、search、alias 解析或成员枚举中。

### 9.3 SDK 与 endpoint 边界

服务端 **MUST NOT** 注册全局 ActivationPlan、跨 endpoint next-action 或 workflow/conversation identity。每个 endpoint 只返回自己的 closed local outcome、blocker/reason、operation ref、exact-retry/conflict 与本 endpoint expiry。

SDK planner 只组合 canonical public facts（Event/RealmCommit/binding/unique group state）、authenticated service durable facts（founding authority evidence、delivery outbox 状态）、controller-private durable facts 与 local ephemeral 状态；每项携 source ref、checkpoint/epoch、freshness/expiry 与 privacy label。客户端 bytes 只负责 authoring 与 exact retry。unknown 或 stale 只阻断相关 action，**MUST NOT** 隐藏 existing DM 坐标。

SDK **MUST NOT** 实现事后从多个 binding 中选择 canonical 的逻辑，也 **MUST NOT** 实现任何 fallback、takeover 或 minimum-token selector。

## 10. 规范性回归边界

founding 相关的机读入口是 [`ak.vector.direct_conversation.founding_unit.v1`](../../artifacts/registry/vector-registry.json)
与 [`ak.vector.direct_conversation.founding_admission.v1`](../../artifacts/registry/vector-registry.json)，
机读 fixture 见 [`direct-conversation-fixture.json`](../sync/authority-commit-log.md)。

Conformance **MUST** 覆盖：

- 自有 Agent 换钥或 same-key re-authorization 后 Actor membership 不变、`key_access_revision` 不增，但 current endpoint 缺失仍触发普通 Add/Welcome；有旧 runtime leaf 时同一 Commit Remove/Add，group ID 与 lifetime binding 不变、epoch 前进；当前端点重复观察不重复 Add，human 第二设备不替换第一设备，paused／缺 current key／缺 fresh claim 不得 Add，所有私态丢失不得重新 Genesis。机读调度边界复用 `direct-conversation-runtime-endpoint-repair-fixture.json#/owned_agent_runtime_repair`，密码学转录仍按普通 MLS Commit／Welcome 合同验证；

- founder 派生：normal 取根轮次 responder、glare 取 §2 严格排序后 `requests[0].request_event_ref` 的 signed Event author `ActorId`，两侧独立计算一致；把 normal 分支误算为 requester、把 Station receipt issuer 当作 founder、乱序或重复 request refs（即使摘要不同）**MUST** 被两侧 admission 拒绝；反向 receipt 到达顺序、摘要排序与解码后 digest 排序不得改变 founder；
- 非 founder 提交 founding unit 在 self 与 peer 两条路径均拒绝；
- caller-authored 派生：`realm_id`、`main_strand_id` 与 `founding_unit_digest` 由两个独立实现从同一 unit bytes 重算得到逐字节相同结果；请求另行携带坐标、服务端预分配 ID、reserved/materializing draft 与 coordinator 选举形态 **MUST** 被拒绝；
- founder 多设备并发各自 author 出不同 unit 时，同一 Station 的唯一 slot **MUST** 只接受先到的合法 unit，后到者返回 `slot_already_committed` 且零写入，两台设备随后从 resolver 得到同一组坐标；
- founder 与 peer 位于同一 Station 与位于两台 Station 两种部署下，self 路径与 §5.6 peer 路径 **MUST** 得到相同 unit digest、相同四条 source RealmCommit、相同 authority-evidence 判定与相同 admission decision；
- 幂等与崩溃恢复：同 `idempotency_key` 同 unit 的 exact retry 返回相同四条 byte-identical RealmCommit 且第四条 `committed_at` 不变，同 key 不同 unit 返回 `duplicate_conflict`；unit 提交、Commit 落库、outbox 入队与响应丢失各崩溃点重放同一 signed bytes 均恢复同一结果，且不产生第二组 Event 或第二套 finality；
- §5.6 branch 的 dependency 不足 **MUST** 是 top-level 409 `dependency_missing` 加零写入，**MUST NOT** 出现只接受一或两条 Event 的 partial；
- basis 形态：unit 内 `ak.member.state{join}` 与 `ak.strand.create` 的 no-basis shape 被接受；同一 no-basis `ak.strand.create` 出现在 founding unit 之外（普通 Realm、同 Realm 的后续 Strand 或单条提交）**MUST** 被 admission 拒绝，而 unit 内改用需要既有授权实例或 `expected_revision` 的形态也 **MUST** 被拒绝；
- recontact current：多轮重新联系保留同一固定首次身份／founder／唯一私聊；跳过中间版本仍核本轮成立与 scope 实例，已知关闭不被旧响应覆盖，缺原件不得重置身份。
- accepted-at 与 current gate 分离：source 在旧 current round 有效时 accepted 的 unit 延迟到撤回后才到 peer，peer 仍接受历史 identity 并按 current gate 投影 `suspended`；
- 对方设备离线时 MLS 建立与发送成功；对方服务器不可达时 founder 仍可建 Realm、建立唯一 group 并发出真密文；
- 同一 scope 的第二个 Genesis、第二 group 或 epoch reset 必须拒绝；
- 跳代、回退、未 active group 作 predecessor、第 17 个候选 group 的既定错误；
- 无 fallback：non-founder 无论等待多久、伪造标记、回填时间或携 negative query 结果，create 均拒绝；
- pair materialization conflict：模拟受信 service 对同 pair 签出两组不同四-Commit unit 时两 Realm 全部冻结，**MUST NOT** 按 Realm token 词法顺序或到达时间选 winner，也 **MUST NOT** 发 tombstone；
- 同对象 token 不同 Genesis 继续走 `object_identity_conflict`，**MUST NOT** 与 pair materialization conflict 合并为一个 selector；
- 终态：`destroy` 与任意 `tombstone` 拒绝；合法 archive/freeze 及其反向操作沿普通路径生效且坐标不变；违规 terminal 后 slot 保持关闭且 resolver `suspended`；
- binding：逐字节 KAT 覆盖固定 domain、closed `binding_object`、participants / authorization refs 换序归一、`created_at` 与 Event author/proof 排除，任一语义字段改变必须产生不同 digest；双方同 semantic endorsement 经顺序确认得到两个独立 dot；同前态竞争时后者必须重试新 revision；同 actor 重复在领域视图只计一个；不同 semantic digest 在 effect projection 前拒绝；current Contact/service refresh 不改 binding digest；
- owned Agent：controller↔own-Agent 只携 `direct_conversation_agent_provision` 时命中 DM variant；改用 `purpose="agent_control"`（那是 PCR genesis 分支，见 [`./key-management.md` §3.6.3](./key-management.md)）、同时携两个 DM roles 或 DM/PCR variants 多命中均零写入拒绝；Agent↔第三方分别覆盖 founder=Agent 与 founder=other；
- 隐私：非 participant 对任意阶段的 pair 查询与不存在逐字相同。

synthetic glare accepted Event、跨双方 CAS、server next-action、successor Realm/Strand、timeout takeover、minimum-token 归一、server-allocated founding ID、reserved/materializing draft、min-service-DID coordinator 与 view-dependent effect digest **MUST** 由负例拒绝。

closed schema 正反例见 `ak.vector.contact.peer_endpoint_selector.v1` 与 `current-signer-contact-endpoint-fixture.json`。

## Direct founding Human historical source (Normative)

现registered Direct四项的每个实际Human device producer MUST 按server-trusted-results新ordinary冻结职责，在原完整founding事务保原授权fact与GovCommitdigest，包含local governor Human为foreign member产生的四项。peer materialization复用committed_event_submission.producer_signer_fact，各item exact原件/事实核验同四项事务原子，缺任一fact零materialization，不新增receipt/独立Direct载体。四项不包含后续Bound Event；最小来源闭包不允许造Bound、绕原Contact/Direct审批与durable binding门，亦不宣称供材修复可单因解释S3后续无submit。
