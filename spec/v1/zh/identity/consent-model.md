---
title: Consent 模型
status: candidate
normative: true
stability: v1
updated: 2026-09-16
sidebar:
  label: Consent 模型
---

## 0. 规范语言

本文中的规范关键字按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释。

## 1. 边界

Consent 是 holder 在 Principal Control Realm（PCR）中维护的方向性许可，用于 invite、通话发起与 presence 等不以 Contact 为授权依据的动作。Contact request/response、Contact-based create/send 与 Personal DM 只读取双方 holder-signed Contact facts，不读取 Consent。

Consent 不授予 Realm capability，也不替代目标 Realm 的 membership、policy 或 authorization 检查。它只决定 holder 的 Station 是否允许相应首次接触继续进入目标 operation。

## 2. 稳定身份与 current result

每条 Consent 由 producer 分配的 `consent_id` 唯一标识。typed current result selector 是该稳定 `consent_id`，value 包含：

- 完整 peer ActorId；
- `consent_scope`；
- 可选 `not_before`、`expires_at`、约束、证据引用与理由；
- `active | revoked` reducer 状态；`expired` 不是物化状态，而是读取／准入时对 `not_before`、`expires_at` 的窗口判定。

current revision 不是 value 的成员：typed current result 的 `revision` 与 `value` 同层，是封闭的 `{commit_id, stream_position}`（见 [`sync/current-results.md` §2](../sync/current-results.md)），`commit_id` 即产生该 revision 的 RealmCommit。

同一 `consent_id` 在任一时刻只有一个 current value。治理 Station按 PCR Realm stream 的 Commit 顺序执行 reducer；协议不暴露集合标签、写索引或合流元数据。

holder-private `ConsentView.state` 逐字映射这一 current 状态，`ConsentList.consents[]` 只列有稳定 `consent_id` 与 exact current revision 的记录；不存在的 Consent 不以伪 `no_consent` row 表示。请求待处理不是 Consent current 状态，也不得从无记录或时间戳猜成 `pending`。如产品需要待处理列表，必须另行注册具备来源与生命周期的 holder-private request carrier。

`ak.self.consent.resource.get.v1` 是对 holder-private current 的条件性单值读取：在认证 holder 的全部 Consent 中，先按必填的完整 `peer` 精确匹配，再按可选的 `consent_scope` 精确过滤；只有匹配集恰有一条时才返回该条 `ConsentView`。匹配集为空时按现有资源不存在响应处理，超过一条时 MUST 以 `failed_precondition` 失败关闭，不得按时间、状态、`consent_id` 排序或其它隐含规则任选一条。`consent_scope` 即使给出也不保证唯一；需要定位指定 `consent_id` 或展示多条记录的客户端 MUST 使用 holder-private list 并按返回的稳定 ID 自行选择。此读取不合并、不覆盖、也不改变任何 Consent current。

## 3. Event

### 3.1 `ak.consent.grant`

Grant payload 使用 `event-payload.schema.json#/$defs/consent_grant_payload`：

```json fragment
{
  "consent_id": "ak:consent:018f2d40-0000-7000-8000-000000000001",
  "peer": {"kind": "actor", "actor_id": "did:webvh:example.net:u:bob"},
  "consent_scope": "invite"
}
```
`consent_id` 必须尚未存在；相同 Event 的重试返回同一提交结果，不产生第二条 Consent。另一个 Event 复用该 ID 必须以 `failed_precondition` 拒绝。

### 3.2 `ak.consent.revoke`

Revoke payload 使用同一稳定 ID，并要求调用方签入 current revision：

```json fragment
{
  "consent_id": "ak:consent:018f2d40-0000-7000-8000-000000000001",
  "expected_revision": {
    "commit_id": "ak:realm_commit:0Zm5xr9E1cVJm2Q7pT4sN8bK6hW3yD1gXfL0aRtUvOc",
    "stream_position": 7
  },
  "reason": "holder_request"
}
```
治理 Station必须在 commit 事务中同时验证目标存在、仍为 active 且 current revision 等于 `expected_revision`。成功后 revision 变为接纳该 Event 的 RealmCommit 的 `{commit_id, stream_position}` 并进入 `revoked`；stale revision、未知 ID、重复撤销或主体不匹配均拒绝。撤销只影响后续 admission，不追溯撤销已经提交的其它 Realm Event。

### 3.3 Producer 与提交

Grant/Revoke Event 的 actor 与认证 holder 必须是 holder PCR 当前 authority-root controller，`authorization_ref` 必须绑定该控制权。服务只接受调用方给出的 `EventAdmissionSubmission { event }`，不得代写、重建或代签 Event。只有当前治理 Station签发的 `RealmCommit` 使更新生效。

## 4. Scope

`consent_scope` 的 closed 值为：

| 值 | 语义 |
| --- | --- |
| `invite` | peer 可发起 Realm/Strand invite。 |
| `voice_call` | peer 可发起语音通话。 |
| `video_call` | peer 可发起视频通话。 |
| `presence` | peer 可观察 holder presence。 |
| `any` | 覆盖全部具体 scope。 |

### 4.1 `any` 与撤销

`any` 是一条独立 Consent，不隐式创建其它记录。撤销某个具体 scope 不影响 `any`；若 holder 希望停止全部许可，客户端必须分别对相关 active `consent_id` 提交带正确 revision 的 Revoke Event。UI 必须在确认前列出仍会保持 active 的 Consent。

### 4.1.1 缓存失效

Revoke 被 RealmCommit 接纳后，holder Station必须立即使相应 invite gate、通话 gate、presence 与 MIMI consent cache 失效。`any` 被撤销时，使该 peer 的全部具体 scope cache 失效；其它独立 active Consent 仍按 §5 求值。缓存不得把 current revision 回退或延迟已知撤销。没有缓存的消费者必须在实际准入边界读取同一 current，不能复用已撤销的 preflight。

current-v1 不提供 private-contact discovery 或 PSI（见 [`discovery/discovery-directory.md` §1／§6](../discovery/discovery-directory.md)）。本条不要求恢复这些入口、索引或轮转；未登记入口必须不可调用、不可广告且不得改变索引。已登记的 MIMI identifiers facade 不得调用未登记发现协议或用 Consent 构造匹配结果。

### 4.1.2 引入证据

holder 可把 active `invite` 或 `any` Consent 的 `CommittedEventRef` 作为 audience-bound introduction evidence。接收方必须向 holder 的 current authority 验证该 ID 当前仍 active；证据本身不复制 Consent value，也不授予目标 Realm 权限。

## 5. Effective Consent

查询 `(holder, peer, concrete_scope)` 时，以下任一 current record 可满足 gate：

- peer 完整 ActorId相等且 scope 等于 concrete scope 的 active record；
- peer 完整 ActorId相等且 scope=`any` 的 active record。

时间窗口必须包含当前验证时间。未知、不可验证、已过期或 authority freshness 不足一律视为未授权。不同 Realm 的 pairwise ActorId不得因 principal DID相同而聚合。

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

通话产品投递、客户端响铃及适用的首次接触 media token 必须分别重验完整 current，采用 [`webrtc-signaling.md` §3b](../crypto-media/webrtc-signaling.md) 的 exact invitation／受权读取合同。该关系不改变 holder PCR 真源；generic encrypted rail 不构成产品准入。非空且未登记语义的 constraints 数组 使该条 record 不可授权，独立其它 concrete／any record 仍单独求值。

### 6.3.1 Holder-private 完整 current 读取

普通 Realm snapshot 的披露不能被用来开放 holder PCR；列表／get 的 ConsentView 也不含完整值。完整读取正式复用 Consent surface，operation 为 `ak.self.consent.read.current.v1`（`POST /_arkret/self/consent/current`）及仅供 hosting Station 代理的 `ak.peer.consent.read.current.v1`（`POST /_arkret/peer/consent/current`）。closed request／outcome 见 `consent-operations.schema.json` 的 `consent_current_read_request_body`／`consent_current_read_outcome`。

两个入口均使用 exact `holder_account_id,peer,consent_scope,audience_actor_id,nonce`，nonce 至少128 bit CSPRNG；self 的认证 Account **MUST** 等于完整 holder，audience **MUST** 是 holder hosting Station 的完整 Service ActorId。peer 只允许该 hosting Station，经当前 PCR authority 读取；邀请发起者、媒体 issuer、同 principal 的另一 Station Account 与普通 Realm governance **MUST NOT** 取得完整值。hosting Station 必须先完成认证 holder／其正式controller的授权，不得把 requester 的声明作为代理资格。完整值只交给该 holder 的认证 self 会话，不向 caller of invitation 或其它消费者转发。

current authority 在与 Grant／Revoke 相同的 PCR serializable cut 读取全部 exact peer、requested scope 及独立 any 的 current records（请求 any 时只匹配 any），包括 active／revoked，不按列表状态猜许可。outcome 由该 cut 的实际 PCR Realm、generation、effective Realm stream head 及完整 `consent_result` rows组成；空集合只表示此 cut 无匹配记录。每 row 的稳定 ID、source stream与current revision必须绑定实际accepted source，完整值包括not_before、expires_at、constraints与状态。此 operation 不签发授权、不写第二账本、不改变 current；list／get继续只用于定位稳定 ID／展示。完整 targeted read 消除 list 与 exact read 的竞争；consumer仍独立求值所有 eligible concrete／any records。

outcome 的 request_digest 是完整请求 RFC8785 JCS 的 SHA-256；签名输入为 `UTF8("ak.consent.current_read.v1") || 0x00 || RFC8785_JCS(outcome仅去除proof)`。proof为 closed `{verification_method,jws}`，当前 authority key／generation须从独立可信配置锚定，不能来自结果自报。窗口不超过evaluated_at后30秒。hosting Station必须验证原outstanding请求、nonce／audience／holder、该generation及签名，再经authenticated self交付；holder客户端必须验证并安装完整typed rows及head，对本地已知更晚head／revoke不回退。材料不完整、时间过期、authority变更或旧读均刷新／拒绝本次，恢复后合法重试；不能仅因历史验签或窗口未过就重复许可。

peer签名场景只引用 `ak.http_signature.scenario.consent_current_read.v1`，适用覆盖集如下：

<!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.consent_current_read.v1 -->
- `@method`、`@target-uri`、`@authority`
- `arkret-operation`
- `content-digest`（relay request 总是带 body）
- `source-service-id`、`destination-service-id`
- `source-trust-domain`、`destination-trust-domain`
- `destination-service-endpoint-digest`（条件项：经 shared ingress 抵达 destination 时必需）
<!-- END ak-http-signature-covered-set -->

### 6.3.2 交接后的私有接受与 hosting 代理（normative）

PCR planned handoff 后，holder 的完整 AccountId 与 hosting Station 不变，Grant／Revoke 及相关私有接受事务由当前 PCR authority 负责。hosting Station MUST 从 inception PCR 与连续 handoff chain 独立确定当前 authority；不能用 AccountId.station_id、接收结果自报的 key 或调用方给出的地址代替。

Grant／Revoke MUST 继续携原 `EventAdmissionSubmission` 经既有 `ak.peer.events.command.submit.v1` 的 `authority_forward` 接纳。该 PCR native 分支只允许 exact holder hosting Station 转发，目标必须是已验证的 holder inception PCR／当前治理任期，producer 必须仍为该 PCR 当前 authority-root controller；当前方在同一 PCR 锁下重验原 device proof、当前设备状态、root ref 与 Consent CAS，并同事务更新 quarantine。它不变成普通协作 Human writer，不创建 `producer_signer_fact_digest`，不复制其它 PCR 历史，也不以 hosting 侧缓存证明当前授权。转发原件、已接受原件的精确重试和原结果必须保留；不能在 hosting Station 重新接纳或代签。

其它私有服务接受正式使用 `ak.peer.consent.command.proxy.v1`（`POST /_arkret/peer/consent/proxy`），closed DTO 见 `consent-private-operations.schema.json`。这不是任意 RPC 或 AccountData PUT；命令集合只包含下表六项。所有请求绑定完整 holder、inception PCR、当前治理 generation、至少128 bit CSPRNG nonce、最多30秒的 outstanding `expires_at`、认证上下文与完整命令。只允许 exact holder hosting Station 作为 RFC9421 Source，Destination 必须是独立验证的当前 PCR authority。沿用 `ak.http_signature.scenario.service_to_service.v1`，不另抄覆盖集，不转发用户 bearer／DPoP／session credential。

| command.kind | context | 接受语义与结果 |
| --- | --- | --- |
| `list` | `holder_session` | 同 cut 读取 holder 的 `ConsentList`；只用于展示／定位稳定 ID，不作为最终准入。 |
| `version` | `holder_session` | 按 exact `consent_id,commit_id` 返回原 accepted Grant／Revoke 的 `ConsentView`，供 Event 精确重试；不得把原结果解释成当前许可。 |
| `effects` | `holder_session` | 同 cut 读取 holder quarantine、invite delivery 与 receive policy 的完整 revision/content。required nullable cell 的 null 只证明该 cut 从未写入／当前不存在；缺项或来源未知不能当空值。 |
| `invite_policy` | `holder_session` | 复用原 closed receive policy，完整 account 必须等于 holder；在同一 PCR 私有接受锁下耐久替换并返回 revision/content。 |
| `invite_delivery` | `station` | 保留原完整 `InviteDeliveryRequest` 及原认证 notification source；重验 Event／Commit／原 producer 证据和 recipient／introduction 关系，沿同一个 receive-policy、quota、去重、Consent current 与最终 private CAS 接受路径执行。对原 requester 仍只给原 opaque 结果。 |
| `request` | `station` | 保留 hosting Station 已认证的完整 requester ActorId 与原 closed Consent request；requester 必须为该 hosting Station 的真实 Account，目标必须为 exact holder。原 quota／live-entry 去重和 holder-private queue 在同一接受事务执行，结果仍恒为 accepted_for_processing。 |

`holder_session` 的完整 actor 必须等于 exact holder Account；device 必须来自 hosting 侧真实认证会话，并由 PCR authority 在同一接受锁下验证仍为当前 active endpoint。`station` 的 actor 必须是认证 Source 的完整 Service actor，且只准使用表中两项服务命令；不得借它读取、写 policy 或声称 holder root 控制权。两个分支都不能把 caller 的声明当作授权。当前方还须验证 holder 的 inception PCR 绑定与实际本地治理权，冻结中、旧任期或导入未完成均不可用、零写入。

proxy outcome 绑定完整 request digest、PCR、generation、实际 effective Realm stream head、evaluated_at、expires_at 及同名 outcome 分支，窗口不得超出原请求或 evaluated_at 后30秒。hosting Station 必须在认证的当前 authority transport 上核全部绑定、会话／device fence 与已知 head／private-cell revision 高水位，再经原 self surface 交付。缓存的 list、version、effects 或旧 proxy outcome 永不授权新的 delivery CAS。旧任期、已知新撤权、旧 head／cell revision、过期或不完整材料都刷新／拒绝本次；不能回退或换本地 writer。

proxy 的写命令以 `(holder,governance_generation,nonce)` 与完整 request digest 保留原窗口内的耐久精确重试 fence；相同 key 不同 bytes 拒绝，相同请求不再执行私有写入、不延长窗口。原结果回放仍重验当前 disclosure 与设备权限。读取命令重新取得当前 cut，不冻结可反复使用的授权结果。所有这些 fence、policy revision、source quota、去重、quarantine 与 delivery 状态必须随 PCR 私有冻结状态一起完整迁入；新方未证明其完整性时不能签 handoff acceptance。

hosting 侧 AccountData／device 更新只展示已验证 authority 接受的内容与原 revision，不独立推进该业务 revision，不构成第二个 CAS writer。变更接受后须使用原正式 actor-private 更新路径唤醒 holder；通知丢失时从当前 authority 读取并按已知 head／cell 高水位恢复，不能重新执行业务接受。Consent Revoke、quarantine invalidation 与最终 delivery 接受的线性顺序始终由当前方同一事务决定，两个数据库之间不假定分布式事务。

## 7. MIMI 映射

MIMI update facade只接受调用方签署的 `EventAdmissionSubmission`，并按 decision 映射到 `ak.consent.grant` 或 `ak.consent.revoke`。facade不得构造 Event。对外投影只暴露最小 `(peer, scope, active)`，不暴露 reason、evidence 或 revision。

## 8. 隐私与管理

Consent list/get 仅允许 holder 或 holder 明确授权的 controller。peer 不能读取 holder 的 Consent ID、revision、expiry 或历史。管理 UI 可按 peer 聚合展示，但不得把聚合视图写回 wire。

### 8.1 本地聚合撤销

“撤销该 peer 的全部许可”是客户端编排：先从同一 current authority取得 holder 可见的全部 active Consent，再为每个 `consent_id` 用其精确 current revision签署 Revoke Event。任一竞争更新都使对应 Event stale；客户端必须刷新后重新确认，不得由服务端隐式扩大撤销集合。

## 9. Conformance

实现至少验证：唯一 `consent_id`、stale revision 拒绝、exact retry、`any` 与具体 scope 的独立性、撤销后 cache 即时失效、跨 Station anti-enumeration、pairwise ActorId隔离以及 requester 观察等价类。
