---
title: Consent 模型
status: candidate
normative: true
stability: v1
updated: 2026-10-21
sidebar:
  label: Consent 模型
---

## 0. 规范语言

本文中的规范关键字按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释。

## 1. 边界

Consent 是 holder 在 Principal Control Realm（PCR）中维护的方向性许可，用于 invite、通话发起与 `consent_only` Presence 等不以 Contact 为授权依据的动作。Contact request/response、Contact-based create/send 与 Personal DM 只读取双方 holder-signed Contact facts，不读取 Consent。

Consent 不授予 Realm capability，也不替代目标 Realm 的 membership、policy 或 authorization 检查。它只决定 holder 的 Station 是否允许相应首次接触继续进入目标 operation。

## 2. 唯一 peer current

Consent 的唯一 subject 是 holder 的实际 inception PCR namespace 与完整 exact peer ActorId；Account 分支包含 Station，Realm pairwise actor 也不得按 principal 合并。typed selector 为 `{kind:"consent",peer_id:ActorId}`，value 为 `{permissions:[...]}`。原生许可不分配 `consent_id`；该 typed ID 仅保留为 MIMI 私有请求 correlation。历史写以原 Event／RealmCommit 定位。

每个 concrete scope 最多一项，permissions 按 `invite,voice_call,video_call,presence` 的固定次序排列，最多四项；每项携 `consent_scope` 及可选 `not_before,expires_at,constraints,evidence_ref,reason`，字段含义和 optional 成员存在性均被用户签名覆盖。重复 scope 或非规范次序 MUST 拒绝，不能排序后改写原件。省略 scope 即不许可，空集合是已确认的全部关闭，仍保留真实 revision／来源；不得删除或 GC 成从未写入。到期只影响实际 gate 求值，不写 clock-driven Event。

current revision 与 value 同层，为封闭 `{commit_id,stream_position}`，见 [current-results](../sync/current-results.md)。self list/get 只供展示，get 按 exact peer 返回唯一 summary，不再接受 scope filter 或多匹配任选。summary 的 permission_scopes 包含所有已存条目；不能用这些不含完整窗口／约束的结果签替换。请求待审仍不是许可 current，缺项／空列表不证明从未写入。

## 3. 唯一完整替换 Event

### 3.1 `ak.consent.replace`

唯一原生 writer 是 `ak.consent.replace`，closed payload 为 `event-payload.schema.json#/$defs/consent_replace_payload`：`peer,expected_current,permissions`。首次写签 `{state:"never_written"}`；已有 current 签 `{state:"present",revision:{commit_id,stream_position}}`。该前态必须从 §6.3.1 完整读取取得；不把 read proof 塞入 payload 或创建预约。

接受方在 PCR 原有 serializable admission 事务内验证实际 holder PCR、用户原签、当前 root controller、authorization_ref／设备与完整 peer，再检查从未写入谓词或 exact revision，接受整份目标集合并签原 covering RealmCommit。同前态竞争至多接受一份，另一份 `failed_precondition`、零 Event／Commit／current／私有效果写入，必须重读并重新确认；不得自动 union、按时间合并、服务端补字段或重签。

### 3.2 删除与精确恢复

关闭一个 scope 是显式移除该项；关闭全部是签空集合。重新许可必须以包括 empty 在内的真实 current revision 作新替换。首次写谓词不能覆盖另一设备已接纳的 empty。旧 Event 重投只恢复原终局，不能重新安装旧值。

提交前耐久冻结 exact signed Event、PCR／holder／peer 与提交身份。unknown 沿统一 submit 的原 authority 终局规则恢复原 Event／Commit；已接纳 exact retry 在新的 current CAS 前识别并返回原 ConsentView／来源，且重验当前披露权限，不以之后的 current 重算旧差异。私有 version 读取使用 exact peer、原 event_id 和 commit_id；缺失／未知终局不得猜作未接受。

`ak.self.consent.command.replace.v1` 只接纳调用方原 `consent_event: EventAdmissionSubmission`，不得代写、重建或代签。root_control_only 不允许不同主体 managed-behalf、consent_write delegation、普通 PCR／co-owner grant 或 automation 替代 holder 原控制权。

## 4. Concrete scope 与失效

closed scope 仅为 `invite,voice_call,video_call,presence`。不存在独立 `any` 或多个同 scope 许可 OR；UI 全选只签当时明确列出的四项，未来新增 scope 默认不授权。同 scope 多窗口 OR 能力正式删除；不同 scope 仍有自己的窗口和约束。

### 4.1 撤回与缓存

替换接纳必须同事务更新 current、必要 quarantine invalidation 与耐久发布意图。quarantine 条目必须保留认证的完整 source_peer_actor_id 供 holder 审核及构造 exact peer；其 source_peer_principal_id 仅服务原反滥用 quota，两者须验证来自同一真实来源，不能由 transport source 或裸 principal 猜 Station。关闭 invite 的 invalidation 用完整 peer_actor_id 匹配条目，不清其它 Station Account；原 source quota ledger 的身份／保留期不变。invite、通话、consent_only presence 和 MIMI 缓存绑定唯一 current revision 与实际 concrete scope；关闭后实际准入不得使用旧 preflight。无关 scope 变化不伪称其被撤回，但缓存复用仍须满足已知 source 版本、当前窗口和 current 边界，不能忽略新 revision。

current-v1 不提供 private-contact discovery 或 PSI；未登记入口不可调用、不可广告且不得改变索引，MIMI identifiers facade 不得用 Consent 推导发现命中。

### 4.1.2 引入证据

holder 可主动提供原 accepted replacement 的 `CommittedEventRef` 作为 audience-bound introduction evidence；该原目标必须含 invite，并绑定完整 holder、peer。接收方在实际 delivery 向 current authority 检查同 peer 当前 invite 条目、窗口和来源。历史原签只帮助认证／定位，不是永久授权；证据不复制完整许可集合，也不授予 Realm 权限。

## 5. Effective Consent

查询 `(holder,exact_peer,concrete_scope)` 只读取这一份 current 的该 scope 条目。不存在、empty、缺项、未来、过期、authority freshness 不足或约束不可解释均不授权；未知／非空未登记约束不能被忽略。没有其它 record／any 可兜底。独立 Contact、membership、Realm capability、设备及生命周期 gates 仍分别执行。

## 6. Operation admission

### 6.1 Invite gate

holder Station在 invite delivery admission 查询 holder PCR 的 typed current result；目标 Realm治理 Station不读取 holder PCR 状态，producer 也不把查询结果写入目标 Event。

`require_explicit_consent` policy 下，没有可验证 active Consent 的 delivery 必须静默丢弃。default policy 下可进入 holder-private quarantine 供 holder review；该 holder-private 数据以 account-data key `ak.account.holder_quarantine` 保存。对 requester 的响应必须保持 `status="deferred"` 且不披露 account existence、Consent 状态、送达或 quarantine 结果。

有 active Consent 只允许 invite 继续提交；目标 Realm仍独立执行其 current membership、capability、policy 与 typed revision 检查。

### 6.1.1 First-contact anti-abuse

holder Station必须在 invite delivery、Contact delivery 与 consent request 的共同入口执行 per-holder 新来源速率和总量限制。identity key 使用完整来源 principal/ActorId，不得只按 IP、域名或裸 DID 聚合。

#### 6.1.1.3 Chokepoint

限速判定与 holder-private queue 写入必须位于同一事务边界。超过限额、holder 不存在、policy deny 与成功排队对 requester 返回同一 opaque 结果；失败分支不得留下可观察副作用。

### 6.2 跨 Station

跨 Station requester 不得查询 holder 的 Consent 列表。holder Station只返回最小、短期、audience-bound admission outcome，且 requester 不得把该 outcome 当成 Realm authorization。

#### 6.2.2 主动披露

holder 可主动签发短期 green-light，绑定 holder、peer、scope、audience、PCR RealmCommit 与 expiry。验证方必须向 current authority确认 freshness；green-light 不包含 Consent value或其它 peer 列表。

### 6.3 通话首次接触

通话产品投递、客户端响铃及适用的首次接触 media token 必须分别重验完整 current，采用 [`webrtc-signaling.md` §3b](../crypto-media/webrtc-signaling.md) 的 exact invitation／受权读取合同。该关系不改变 holder PCR 真源；generic encrypted rail 不构成产品准入。非空且未登记语义的 constraints 使该 concrete scope 条目不可授权，不存在其它同 scope record 或 any 兜底。

### 6.3.1 Holder-private 完整 current 读取

普通 Realm snapshot 不开放 holder PCR。完整编辑前态唯一复用 `ak.self.consent.read.current.v1`（`POST /_arkret/self/consent/current`）和仅供可交接 Organization PCR 的 hosting 代理的 `ak.peer.consent.read.current.v1`（`POST /_arkret/peer/consent/current`），closed DTO 见 `consent-operations.schema.json`。

request 为 exact `holder_account_id,peer,audience_actor_id,nonce`，没有 consent_scope filter；nonce 至少128 bit CSPRNG。self 的认证 holder／正式controller 必须通过既有 holder root 权限，audience 为 holder hosting Station 完整 Service ActorId。peer 只供已独立验证可交接 Organization PCR 的 exact hosting Station；Human 在 owning Station TCB 读取；用户管理的 Agent 不进入跨站代理分支，也不因此获得 Consent 能力。requester、MIMI provider、邀请发起者、media issuer、另一 Station Account 与普通 Realm governor不得取得完整结果；correlation／purpose 不授予读取权。完整结果仅回原获准 holder／controller self 会话。

current authority 在与替换／私有接受相同的 PCR 串行化边界内以一次一致性 cut 读取，返回实际 PCR、generation、effective stream head 和闭合 current 分支：

- `present`：完整 `consent_result`，包括唯一 selector、source_stream_ref、exact revision 与全部 value。empty 也是此分支。
- `never_written`：同 exact subject、同 cut 的明确从未写入声明；由 request_digest 绑定 holder／peer，以实际 PCR／generation／head 认证。不得伪造 Event、Commit 或 position 0 revision。

present 必须返回所有尚未被显式移除的条目，包括过期、未来、不可求值约束和各项完整窗口／附属字段。不能筛出“当前有效”再交编辑，不能拼不同 cut 的逐 scope 结果。缺某 scope、空列表、超时、not_found、拒绝披露都不是 never_written。读取失败不能签替换；显式删除无效项须展示真实差异。

request_digest 为完整请求 RFC8785 JCS 的 SHA-256；proof 是 closed `{verification_method,jws}`，签名输入为 `UTF8("ak.consent.current_read.v1") || 0x00 || RFC8785_JCS(outcome仅去除proof)`。authority key／generation 从独立可信来源锚定。expires_at 不超过 evaluated_at 后30秒；验证 outstanding 请求、nonce、audience、holder、完整 peer、签名、实际 PCR／generation／head 与已知高水位／撤权后交付。present 的 selector、source stream、revision 与 accepted source 必须一致。旧读不得覆盖更新的 head／empty。窗口过期、任期变化或缺材料时刷新，不能补本地空值。

读取不是预约：后续替换在新的接受事务检查 exact current；never_written 同样须仍未写入。所有真实 gate 仍在获准边界内部对所需 concrete scope 求值，对外只返回既有最小短期 audience-bound outcome，不能转发完整编辑结果。

peer 签名继续唯一引用 `ak.http_signature.scenario.consent_current_read.v1`，覆盖集如下：

<!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.consent_current_read.v1 -->
- `@method`、`@target-uri`、`@authority`
- `arkret-operation`
- `content-digest`（relay request 总是带 body）
- `source-service-id`、`destination-service-id`
- `source-trust-domain`、`destination-trust-domain`
- `destination-service-endpoint-digest`（条件项：经 shared ingress 抵达 destination 时必需）
<!-- END ak-http-signature-covered-set -->

### 6.3.2 交接后的私有接受与 hosting 代理（normative）

Human 的 完整替换、current、quarantine、quota／去重、policy、delivery 最终 CAS 与通知在 owning Station 的同一 PCR 权威边界内完成；内部拆分仍须原子提交和耐久 exact retry，不产生 remote PCR governor、代理会话证明或跨 governor publication。普通设备同步、account subscribe 的 baseline／catch-up 和本地耐久通知保持。

本节其余跨 governor proxy 仅适用于 [`authority-commit-log.md` §8.1](../sync/authority-commit-log.md#81-pcr-治理归属与交接资格normative) 允许独立交接且具备原有 Consent 能力的 Organization PCR；并不赋予其 Human session 能力。其 planned handoff 后完整 AccountId 与 hosting Station 不变，完整替换 及私有接受事务归当前 PCR authority。hosting MUST 从 accepted inception／原生来源与连续 handoff chain 独立确定当前 authority；不能用接收结果自报的 key、地址或标签代替。Human／用户管理的 Agent 请求该跨站分支 MUST 零效果拒绝。

完整替换 MUST 继续携原 `EventAdmissionSubmission` 经既有 `ak.peer.events.command.submit.v1` 的 `authority_forward` 接纳。该 PCR native 分支只允许 exact holder hosting Station 转发，目标必须是已验证的 holder inception PCR／当前治理任期，producer 必须仍为该 PCR 当前 authority-root controller；当前方在同一 PCR 锁下重验原 device proof、当前设备状态、root ref 与 Consent CAS，并同事务更新 quarantine。它不变成普通协作 Human writer，不创建 `producer_signer_fact_digest`，不复制其它 PCR 历史，也不以 hosting 侧缓存证明当前授权。转发原件、已接受原件的精确重试和原结果必须保留；不能在 hosting Station 重新接纳或代签。

其它私有服务接受正式使用 `ak.peer.consent.command.proxy.v1`（`POST /_arkret/peer/consent/proxy`），closed DTO 见 `consent-private-operations.schema.json`。这不是任意 RPC 或 AccountData PUT；命令集合只包含下表六项。所有请求绑定完整 holder、inception PCR、当前治理 generation、至少128 bit CSPRNG nonce、最多30秒的 outstanding `expires_at`、认证上下文与完整命令。只允许 exact holder hosting Station 作为 RFC9421 Source，Destination 必须是独立验证的当前 PCR authority。沿用 `ak.http_signature.scenario.service_to_service.v1`，不另抄覆盖集，不转发用户 bearer／DPoP／session credential。

| command.kind | context | 接受语义与结果 |
| --- | --- | --- |
| `list` | `holder_session` | 同 cut 读取 holder 的 `ConsentList`；只用于展示 exact peer summary，不作为最终准入。 |
| `version` | `holder_session` | 按 exact `peer,event_id,commit_id` 返回原 accepted 替换的 `ConsentView`，供 Event 精确重试；不得把原结果解释成当前许可。 |
| `effects` | `holder_session` | 同 cut 读取 holder quarantine、invite delivery 与 receive policy 的完整 revision/content。required nullable cell 的 null 只证明该 cut 从未写入／当前不存在；缺项或来源未知不能当空值。 |
| `invite_policy` | `holder_session` | 复用原 closed receive policy，完整 account 必须等于 holder；在同一 PCR 私有接受锁下耐久替换并返回 revision/content。 |
| `invite_delivery` | `station` | 保留原完整 `InviteDeliveryRequest` 及原认证 notification source；重验 Event／Commit／原 producer 证据和 recipient／introduction 关系，沿同一个 receive-policy、quota、去重、Consent current 与最终 private CAS 接受路径执行。对原 requester 仍只给原 opaque 结果。 |
| `request` | `station` | 保留 hosting Station 已认证的完整 requester ActorId 与原 closed Consent request；requester 必须为该 hosting Station 的真实 Account，目标必须为 exact holder。原 quota／live-entry 去重和 holder-private queue 在同一接受事务执行，结果仍恒为 accepted_for_processing。 |

`holder_session` 的完整 actor 必须等于 exact holder Account；device 必须来自 hosting 侧真实认证会话，并由 PCR authority 在同一接受锁下验证仍为当前 active endpoint。`station` 的 actor 必须是认证 Source 的完整 Service actor，且只准使用表中两项服务命令；不得借它读取、写 policy 或声称 holder root 控制权。两个分支都不能把 caller 的声明当作授权。当前方还须验证 holder 的 inception PCR 绑定与实际本地治理权，冻结中、旧任期或导入未完成均不可用、零写入。

proxy outcome 绑定完整 request digest、PCR、generation、实际 effective Realm stream head、evaluated_at、expires_at 及同名 outcome 分支，窗口不得超出原请求或 evaluated_at 后30秒。hosting Station 必须在认证的当前 authority transport 上核全部绑定、会话／device fence 与已知 head／private-cell revision 高水位，再经原 self surface 交付。缓存的 list、version、effects 或旧 proxy outcome 永不授权新的 delivery CAS。旧任期、已知新撤权、旧 head／cell revision、过期或不完整材料都刷新／拒绝本次；不能回退或换本地 writer。

proxy 的写命令以 `(holder,governance_generation,nonce)` 与完整 request digest 保留原窗口内的耐久精确重试 fence；相同 key 不同 bytes 拒绝，相同请求不再执行私有写入、不延长窗口。原结果回放仍重验当前 disclosure 与设备权限。读取命令重新取得当前 cut，不冻结可反复使用的授权结果。所有这些 fence、policy revision、source quota、去重、quarantine 与 delivery 状态必须随 PCR 私有冻结状态一起完整迁入；新方未证明其完整性时不能签 handoff acceptance。

hosting 侧 AccountData／device 更新只展示已验证 authority 接受的内容与原 revision，不独立推进该业务 revision，不构成第二个 CAS writer。变更接受后须使用原正式 actor-private 更新路径唤醒 holder；通知丢失时从当前 authority 读取并按已知 head／cell 高水位恢复，不能重新执行业务接受。Consent 关闭替换、quarantine invalidation 与最终 delivery 接受的线性顺序始终由当前方同一事务决定，两个数据库之间不假定分布式事务。

### 6.3.3 Organization 跨 governor 私有效果发布（normative）

本节仅服务 §6.3.2 的已验证 Organization 分离 governor；Human 的本地通知不依赖此 peer publication，Human／用户管理的 Agent 的跨站请求零效果拒绝。

`ak.peer.consent.command.publish_effects.v1`（`POST /_arkret/peer/consent/effects`）是当前 PCR authority 到 exact holder hosting Station 的闭合发布载体，DTO 见 `consent-private-operations.schema.json`。它只发布 `holder_quarantine,invite_delivery,invite_receive_policy` 三个 required nullable cell 的完整原 revision/content；不是第七个 proxy 命令，不提供任意 key 或任意 AccountData PUT，也不放宽 §6.3.2 的 holder-session／station 两个 context。

Source MUST 是从 holder inception PCR 与连续 handoff chain 独立验证的当前治理 Station，Destination MUST 等于完整 holder 的 hosting Station。沿用 `ak.http_signature.scenario.service_to_service.v1`。请求绑定完整 holder、realm、generation、至少128 bit CSPRNG nonce、实际 effective Realm stream head、evaluated_at、expires_at 和完整 effects；窗口最多30秒。hosting 不接受调用方地址、自报 key、旧任期、冻结或不完整来源作为权威。新收到的 cut 不得低于包括新 authority assertion 在内的已知 head；同位置不同 Commit 或同 cell revision 不同 content 是分叉，必须拒绝。null 不得抹去已知的非空 cell revision，来源缺失不能被投影成空。

authority 的实际私有 CAS／queue／invalidation 接受与耐久 publication intent MUST 同事务提交；精确业务重试不新增 intent、不再次执行业务 CAS。publisher 每次尝试从当前本地、未冻结 PCR 接受锁取得完整新 cut，在锁外以自己的真实 Service 身份发送；失联重试重新取得 cut／nonce／窗口，不能延长或重复使用旧授权材料。成功确认仅可在同一接受锁下、有匹配 intent sequence 的条件下删除／确认意图；冻结中不得改变导出状态。在途旧确认不能覆盖更新的接受，也不能改变已经冻结的迁移内容。

hosting 验证 Source、当前治理权、请求窗口和已知 head／cell 高水位后，MUST 在一个本地投影事务内保留已验证 cut，按原 business revision/content 更新展示副本并推进正式 cursor-covered `account_data.station_cas` 位置。它不接受业务 CAS、不签发 RealmCommit，不独立增加该 cell 的 business revision。只有实际新增的投影 revision 可经原正式 actor-private 更新路径唤醒 holder；sender 是 hosting Station 自己的真实 Service，authority 不冒充它。等价 publication／确认丢失／冷恢复不得重复投影或 fanout；原 requester 始终只收到原 opaque outcome。

publication outcome 只携完整 request digest 和 `applied|duplicate`，不授予业务授权。意图、确认边界及拒绝回退所需的私有耐久状态必须随 planned handoff 完整迁入；新 governor 用自己的当前身份恢复未确认意图，旧 governor 不得继续发布。holder 离线时也必须保留正式 account subscribe 的 baseline／catch-up；丢失低延迟通知不能通过伪造 holder 会话、重放业务接受、普通 PCR replication 或第二个 CAS writer 修复。未实现该发布载体的实现必须在接受冻结变更前拒绝启动 PCR handoff。

## 7. MIMI 映射

MIMI request 的 opaque consent_id 仅绑定私有 correlation，不进入原生 payload／selector。所有 decision 均携 caller-signed `ak.consent.replace` 完整 Event；具体身份、单 scope 差异与终局恢复依 [MIMI §10](../extensions/mimi-interop.md#10-identifiers-and-consent)。facade 只验证并转交原件，不合并、补字段或代签。对外投影只暴露原有最小 peer／scope／active outcome，不披露其它项、理由、证据或 revision。

## 8. 隐私与管理

list/get/current 只允许原 holder 或正式获准 controller，peer 不读取许可集合、revision、expiry、empty／never_written 或历史。管理 UI 展示完整前态与目标差异；关闭全部以单份空集合原签替换，不再逐 ID 聚合撤销。原生 request 删除 any，仍禁止 invite（邀请走 invite delivery），其结果恒为 accepted_for_processing=true；quarantine、new-source quota、同事务去重及不可枚举响应保持。请求待审不自动授权。

## 9. Conformance

至少验证完整 peer／Station 隔离、同前态竞争、empty 与 never_written 区分、首次写与 empty 竞争、unknown 原件恢复、完整编辑不丢未来／过期／未知约束条目、重复 scope／any 拒绝、单 scope 删除不清其它项、多 correlation 串行同 current、跨后续更新的 exact retry、越权完整读取拒绝、窗口／缓存／私有效果失效及 requester 观察等价类。schema-only 检查不代表真实 PCR／HTTP／冷恢复验收通过。

具名简化向量：`ak.vector.consent.peer_current.v1`，见正式 vector registry；生产验证按领域任务执行。
