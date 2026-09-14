---
title: Account Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-09-12
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret 身份由稳定 principal `did_core_id` 表示，并由当前 `did` 提供 DID resolution；用户访问通常经过一个或多个服务账户、OAuth/OIDC session、device token 和 Station / Events API。本文件定义这些层的锁定、暂停、注销、软登出、数据擦除和服务账号生命周期。

## 2. 分层

`AccountId={principal_id,station_id}` 是所有 Station 承载主体的统一身份，包括人类、Agent、
Applet-managed Ghost 与 integration。`ActorId` 只允许 `account`（内嵌完整 AccountId）与 `service`
（服务自身直接行动）两个分支。AccountId 不代表人类登录资格、数据库账号行或特定 provisioning 流程，
也不授予权限；人类账号生命周期、Agent controller/lifecycle/runtime credential、Applet registration/grant
与最小元数据 pairwise profile 的授权规则仍按各自已验证状态独立执行。仅持有 account 身份不得进入
人类登录、恢复或 Agent runtime 专用操作。不同主体类别不得为相同 principal/station 对生成另一身份。

| 层 | 示例 | 生命周期控制者 |
| --- | --- | --- |
| Principal identity anchor | `did_core_id`（稳定）+ registration-time `did` evidence | 注册时 DID control proof；注册后不产生业务 authority |
| Account authority | `(principal_id, station_id)`；同一服务内 create-once | Station + accepted PCR device / recovery policy |
| Service account | `alice@example.com` 登录入口 | account service |
| Device session | session grant / grant-binding key | auth service |
| Event / private state | signed Event history / private account data | Events API + principal policy |
| Realm membership | `ak.member.state`（状态机定义见 [`../models/realm-and-space.md`](../models/realm-and-space.md)） | Realm policy/capability |

服务 account 被注销不等于 DID 消失。DID 被恢复、轮换、deactivate 或转手不改变已接受 PCR、
session 或业务关系；只有显式 current external claim、resolution successor 或启用的 DID-root recovery
消费 current DID state。

**Station 生命周期边界（normative）**：本文件所有账号找回与 reactivation 只作用于原 exact
AccountId 和原 PCR lineage，MUST 遵守 [`common-fields.md` §4.2 的账号隔离铁律](../models/common-fields.md#42-主体引用字段)。
Station 永久停止服务，其上的 Account 与 PCR 随之终止；协议不定义将其迁移或复活到另一 Station
的路径。相同 principal 在另一 Station 的注册是独立账号创建，MUST NOT 继承原账号的 membership、
grant、owner/admin/notary/recovery authority、设备授权或 PCR。Realm 的其他参与者只能凭自身有效
授权继续治理或执行已定义的恢复流程，MUST NOT 以同 principal 账号替代死亡账号。
网络超时或暂时离线不构成可验证的永久死亡证明，MUST NOT 单凭不可达自动签发账号终止事实、转移权限
或创建替代账号；同一 Station 恢复服务后仍按原 AccountId 的已接受状态处理。

## 2.1 服务账号登录与找回

普通客户端 MUST 先按 [server-trusted-results §1.2](../sync/server-trusted-results.md#12-普通客户端的-station-接入normative) 从明确选择/预配的 Station 建立并持久核对身份与认证绑定；首次接入不要求客户端重放 DID 方法历史。服务账号 MAY 使用用户名/密码、passkey、WebAuthn、OAuth/OIDC、企业 SSO 或类似集中认证服务的登录方式。它们只证明调用方通过了某个 account service 的认证，不能直接证明 DID principal 所有权。

登录成功后，account service / auth service MUST 将会话绑定到完整 `AccountId={principal_id,station_id}` 与该账号的设备，例如签发短期 `ak.session.grant`、登记 device binding，或要求客户端提交 identity control proof。资源服务器随后验证 grant、device、capability、Realm policy 和撤销状态。`ak.session.grant` 是 Account Authority issuer-ledger credential，不是 Event：issuer 从 closed immutable `ak.session_grant.issuance.v1` preimage 派生 33-octet / 44-character suite-tagged full-digest token，签 JWT，并要求 JWT `jti` 逐字节等于该 typed ID。其 ID derivation、canonical JWK、nonce 与 verifier 规则见 [`key-management.md` §6](./key-management.md)。这个 ID 不是 Event ID，也不是 `ak:grant:` Capability GrantId；三者的 parser、存储索引与 API strong type MUST 分开。

### 2.1.1 Account-first onboarding

用户可以先完成邮箱、passkey、OIDC/SSO 或企业账号登录，而无需理解 DID。但未完成 principal binding 的 session 只能执行 registration/risk/device initialization，不能作为最终 actor 写 Realm、MLS、capability 或 federation state。

客户端必须在首个网络副作用前本地生成并 durable 保存 recovery/identity-root、device identity、HPKE、DPoP keys 与完整 onboarding draft。服务端不得生成或持有 identity root/device private key。PCR genesis accepted 后仍必须完成首个 Seal 与 genesis recovery policy，才能解除 `recovery_material_pending`；该门的作用范围是进入 E2EE Realm（创建/加入）之前。

### 2.1.2 Account handoff、PCR genesis 与首次 Standard grant（normative）

Account Authority 必须使用 holder-bound handoff；普通 OAuth token、OIDC `id_token`、refresh token 或 browser cookie 不能直接成为 Arkret registration authority。固定流程如下：

1. 客户端只向 `POST /_arkret/gate/account/authentication-handoffs` 提交 OIDC code exchange proof 与 RFC 9449 DPoP；这是 current-v1 唯一 authorization-code consumer。Account Authority 验 issuer/client/redirect/nonce/PKCE 与账号绑定并返回最多 1 hour 的 opaque `account_handoff_grant` 与 deployment-local `account_subject`；外部 OP callback 的 `state` 由实际持有 redirect transaction 的客户端验证，只有 Account Authority 自己持有该 transaction 时才由它权威验证。handoff 本身不是 SessionGrant、没有 refresh 语义，不能直接访问 `/_arkret/self/*`；其闭合权限集是 issue identity-binding challenge、issue DID-binding challenge、issue identity-abandonment challenge、abandon identity creation、register、issue session grant 与 issue recovery-completion grant。两个 identity-abandonment 成员在列，是因为 PCR 从未 accepted 时用户没有 principal，不可能有绑定 principal 的 session grant 来承载它们。对已绑定账号，`account_handoff` 只有在调用方同时证明 accepted device 私钥持有且 origin current-device gate 返回 `allow` 时才能换取 Standard SessionGrant；仅窃取账号因子、handoff 与旧 `device_id` 必须得到零 grant。deployment policy 允许 reactivation 时，fresh account auth MAY 为 `deactivated` 原账号返回 `binding.state=bound` 的 recovery candidate handoff，但该 handoff 本身不改变 account status，普通 issue/register/refresh 仍必须 `account_deactivated`；只有 §3 的 recovery-completion operation 可消费完整 PCR recovery closure 并原子恢复账号。policy deny 时 handoff 创建即返回 `account_deactivated` 且零恢复写入。
`binding.state="bound"` 后不得进入 identity onboarding，也不得从一个巨型 UI 状态机直接猜 continuation。客户端必须先执行不产生远程副作用的本地证据规范化：等待 account-scoped secure-store hydration 完成，验证 account/principal/device/key 一致性，仅从当前 transaction 输入删除已证明过期或 terminal 的临时 checkpoint；跨账号材料、长期 key、多个有效 candidate 与 storage error 只能隔离到 diagnostics，不得静默修剪成“无设备”。输出闭合为：

- `ReturningDevice`：恰有一个与 bound exact AccountId 匹配且 private/public key 自证一致的 accepted-device candidate；
- `NoReturningDevice`：hydration 已明确完成但没有可用旧 device key；
- `LocalEvidenceUnavailable`：存储未就绪、读取失败或候选矛盾。

只有 `ReturningDevice` 进入 `HumanSessionGrantRequest`。请求用 `Authorization: DPoP <account_handoff_grant>` 与匹配 DPoP，body 固定为 `{request_id,principal_id,device_id,audience,accepted_device_possession_proof}`，不得再携 handoff-holder body signature、客户端 challenge 或 `requested_scope`。accepted-device proof 使用 `ak.session_grant_accepted_device_possession_proof.v1`，绑定 `account_subject`、handoff grant digest、request id、完整 `account_id`、device、audience、holder JKT、canonical immutable session intent 与最多 300 秒时窗。method adapter 只把 proof 的 bare controller DID 投影到 `account_id.principal_id`；`account_id.station_id` 必须由已接受 AccountHandoff（issue）或 predecessor SessionGrant（refresh）独立绑定，禁止从 DID URL、HTTP audience 或当前服务猜测。origin Station 必须在同一 current-device linearization 中用 durable accepted device key 验签并判定 authorization：`allow` 才签完整、含 `device_binding` 的 Standard grant；`authority_mismatch` 返回 `403 device_unauthorized` 且零 grant；`revocation_pending | revoked | generation_mismatch` 分别 typed block 且零 grant。

`NoReturningDevice` 在用户显式选择 Recovery 后，以同一 Bound AccountHandoff 与匹配 DPoP 提交 `RecoverySessionGrantRequest`。Account Authority 必须从自身 account binding 验证 `principal_id` 与 `audience`，把 handoff 的 holder JWK/JKT 和 candidate `device_id` 冻结进一个最长 15 minutes、不可 refresh、不可 upgrade 的 `credential_class=recovery_session` grant；其 holder 固定为 `recovery_candidate_device`，不得携 accepted `device_binding`。成功只消费本次 DPoP `jti`，不得消费 AccountHandoff；同一 `request_id` 与 canonical intent 精确重放必须返回同一签名 grant，冲突 intent 必须 fail closed。该 grant 只承载 [`../sync/service-http-binding.md`](../sync/service-http-binding.md) §2.1.2a 的闭合恢复操作集；恢复完成后由专用 completion operation 另发 Standard grant，旧 recovery grant 不得原地变级。

`NoReturningDevice` 进入独立、pairing-first 的 Device Setup；Recovery 只在用户显式选择后打开，并且只能使用上述 restricted grant。`LocalEvidenceUnavailable` 停在 retry/diagnostics，不能伪装成新设备或 Recovery。以下第 2 步起的 identity-creation lease 仅适用于 `identity_creation_active | identity_creation_busy`，不得由 `bound` 分支进入。

2. Account Authority 原子取得最多 15 minutes 的 `identity_creation_lease`，持久化 `(service_account,audience,lease_id,holder_jkt,fence,expires_at,reserved_principal_id?,reserved_registration_anchor_digest?,state)`；同一账号同一 audience 同时只有一个 live holder。handoff 取得与同 holder 续租都必须按 [`../conformance/scalability-constraints.md`](../conformance/scalability-constraints.md) §6.1 限速并经过风险检查；busy 响应除 `retry_after_ms` 外必须回显冲突 live lease 的 `expires_at`，供客户端显示确定等待上界，不得披露 holder key 或原始账号 id。
3. 客户端按已登记 `did:webvh:1.0` adapter 构造 closed `principal_registration_anchor`，连同 `FoundingDeviceDescriptor` 构造 ordered genesis unit；客户端 MUST 投影出 `principal_id=did_core_id`，并从 create Event 按 `retype(event_id)` 导出 PCR id。v1 锚只有 `webvh_registration` 一支：它携注册时 exact accepted DID operation、从 inception 起无缺口的 log entries、该区间全部适用 witness records 与 exact normalized DID Document。任何其他 method（包括 `did:key` 与 `did:web`）命中 human 注册时 MUST 在 schema 与角色准入阶段以 `unsupported_did_method` fail closed，不得落到 method parser 或 history replay。`method_history_head`、`version_id` 与 control-key digest 一律由验证方从锚自身导出，不是调用方自报的镜像。客户端还必须生成独立的 `registration_did_evidence_draft`；其专用 control proof 以 `ak.registration_did_evidence_control_proof.v1` 签署 core/DID、adapter version、history/version/key pins 与 `method_evidence_digest`，不得复用或转换 `identity_creation_control_proof`。`accepted_at` 在 draft 中禁止出现：Account Authority 只有在 registry 接受 exact DID operation 后才把 registry 返回的原始 acceptance time 加入完整 `registration_did_evidence`。客户端把 `{did,method_history_head,version_id}` 写入 genesis `initial_resolution`，并构造绑定同一 device 与 handoff DPoP key 的 `InitialSessionGrantIntent`。
4. durable challenge record 与 `identity_creation_control_proof` 必须绑定 `account_subject`、`principal_id`、`did`、PCR id、`registration_anchor_digest`、`did_version_id`、`control_key_digest`、create payload digest、founding authorize payload digest、`initial_session_request_digest`、closed unit kinds、lease/fence、DPoP JKT、audience/origin/trust-domain 与最多 300 秒窗口。`registration_anchor_digest` 是完整 typed `principal_registration_anchor` 的 canonical digest；它不是仅对 method-native log entry 计算的 event digest，验证方必须从已接受的锚对象重构并复算前者，并独立确认 `project(did) == principal_id`。`proof_kind` 固定为 `did_webvh_inception_update_key`，并且 `anchor_kind` 固定为 `webvh_registration`；任何其他值零写入拒绝。proof key MUST 是 `did_version_id` 所钉的那个 entry 的 **current active update key**（`parameters.updateKeys[0]`），且其 canonical multikey 的 SHA-256 MUST 等于承诺的 `control_key_digest`；不能从 DID Document 的 authentication / service fragment 选择，也不得采信请求自带的 key。account-first inception 时该 entry 就是 entry 0，因此本规则与既有行为一致；对已发布且已轮换的 DID，它锚在建号时刻的当前控制权而不是创世代次——后者可能早已 spent 且不可再签。

**challenge 与执行权独立（normative）**：客户端 MUST 完成本地材料准备与必要用户确认后再申请 challenge。签发只冻结/核对 reservation，MUST NOT 修改 lease expiry 或消费 renewal 额度；新的成功签发按 §6.1 独立预算计数。取得共享事务锁并重读当前 handoff、账号与 live holder/lease/fence 后，用服务端权威当前时间的 canonical 值 t 签发 `issued_at=t, expires_at=t+TTL`，其中 `0 < TTL <= 300 seconds`；MUST NOT 截到签发 handoff 或 lease 的截止时间。锁等待期间到期仍必须拒绝。register 在首次外部副作用前分别检查当前 handoff/账号有效、live lease 的 holder/id/fence、challenge 自身窗口及未失效状态、全部冻结材料绑定；这些条件同时成立才可继续。续租不延长原 challenge，challenge 不延长执行权。

同账号、holder、lease id/fence、reservation 与全部 proof 绑定未变时，新的合法 handoff 或 same-holder renewal MUST 允许复用仍有效的原 challenge/proof，不得仅因 bearer/callback 改变而要求新签发或重签。过期后重新 acquisition 或 takeover 改变 fence 时旧 proof 不可复用，不得原地恢复旧 fence。丢响应且持有原请求时客户端 MUST 优先 exact replay；replay 不重算时间窗、不重复计数、不绕过当前授权或已替换/消费/过期状态。已提交 register 的 canonical outcome replay 与已冻结 saga 内部恢复沿用原合同，不能因证明后来到期重做外部副作用。

**身份锚、resolution 与签名者是三件事，MUST NOT 混用**：`principal_id` 回答“这个 PCR 属于哪一个稳定主体”；`initial_resolution.did` 与 `principal_registration_anchor` 提供该主体建号时的可解析 DID 和注册锚；`did_version_id` / `control_key_digest` 两元组回答“建号时刻谁控制它”。验证方 MUST 分别校验，并通过 adapter 证明前两者投影一致；MUST NOT 因为 ref 指向 inception 就要求 inception key 签名。Event id 与 envelope digest 禁止进入 transcript。客户端在签名前 MUST 核对 challenge 的 `request_id, challenge_id, challenge, purpose, issued_at, expires_at`，其余签名输入从自己已提交并冻结的 request 与已认证 handoff/account context 重建；不能从新的可变 UI 状态补值。Account Authority MUST 耐久保存完整 transcript，在 register 同事务重新比较 DID operation/pins、PCR/genesis/initial-session digests、account subject、lease/fence、JKT、audience/origin/trust-domain 与有效窗；篡改任一项零写入拒绝。已发布 DID binding 的独立解析结果不随该回显收缩删除。

human-anchor 的 wire pins 不重复 `log_head_digest`；account registration 与 identity creation control proof 的签名 transcript 严格使用对应 closed schema 除 `signature` 外的字段，不隐藏补回已删除的摘要字段。`did_version_id` 钉住 adapter 导出的注册版本；完整 `method_history_head` 如仍由 registration evidence、resolution 或其他独立合同要求，MUST 从已验证的确切 WebVH entry 按 adapter 计算，且只能从 `principal_registration_anchor` 导出。`versionId` 的 entry hash 在去掉 proof 并替换 versionId 后计算，**不等于**完整已签 log entry 的 JCS SHA-256，MUST NOT 解码前者冒充后者；缺少确切 entry 时该完整摘要未知。`control_key_digest` 保留供有界 evidence 消费；组织/service 的独立注册载体和专用 registration evidence 签名不在此收缩内。
5. `register` 携带 `did`、exact `principal_registration_anchor`、`registration_did_evidence_draft`、root control proof、含 `initial_resolution` 的 `pcr_genesis_unit` 与 `initial_session`。`registration_did_evidence_draft` 与 `identity_creation_control_proof` 只按各自的注册防重与控制意图用途保留，MUST NOT 替代锚这份 method-native primary material。Account Authority CAS 验证 holder/lease/fence/reservation/challenge，独立验证两个不同 proof、冻结 canonical request，再执行单调 saga：

```text
reserved -> did_published -> pcr_accepted -> account_bound -> completed
```

**inception 校验复用（normative）**：实现 MAY 对同一 immutable `principal_registration_anchor` 只做**一次** SDK 校验，并把该不可由任意调用者伪造的已验证结果传给两个 proof verifier；但 `identity_creation_control_proof` 与 `registration_did_evidence` 的 control proof 是两份不同签名与不同绑定，MUST 继续**分别**验签与绑定核对。该复用只消除同一输入的解析/方法验证重复，MUST NOT 引入新的 wire proof、可信客户端布尔值或跨请求不失效的缓存。

`identity_creation_lease.state` MUST 返回上述 Account Authority 持久 saga 的当前状态；初次取得 lease、尚未冻结 DID operation 时返回 `active`。客户端每次取得新 handoff 后 MUST 以该服务端状态重新计算 onboarding phase，MUST NOT 通过本地 checkpoint、Recovery Key、旧 challenge 或旧 callback 是否存在来推断服务端阶段。`reserved_identity` 在 `active` MUST 省略，在 `reserved` 及后续状态 MUST 存在；两者矛盾时客户端 MUST fail closed。

客户端随后只可检查当前服务端状态和所选合法目标所需的本地材料。材料必须验证其 account subject、lease/fence、reserved identity、purpose、challenge 与 expiry；不属于当前 flow、验证失败或当前状态不需要的材料 MUST 从活动 checkpoint 中删除。验证通过且已满足的步骤 MAY 跳过。任何非终态 reload、认证 callback、网络不确定结果或进程重启都 MUST 重新取得服务端状态并重复该 reconciliation，不得从旧页面步骤继续推进。

reconciliation 重算的是服务端 phase、合法目标与所需材料，不得改变同一次活动用户交互中已经验证的临时材料来源。特别地，首次创建页面仍在内存中持有其刚生成的 Recovery Key 时，服务端从 `active` 单调推进到 `reserved` / `did_published` 不得把该 Key 重新解释为“外部已有 Recovery Key”，也不得把首次确认界面切换成恢复界面；客户端 MUST 继续使用该内存材料完成当前目标。用户正确回输生成的 Recovery Key 后，客户端 MUST 在首个网络副作用前把继续该 reservation 所需的 recovery authority 写入平台安全存储，并 durable 等待成功；public checkpoint 只能保存 fingerprint/public key，不能保存明文词组或被解释成 secret possession。reload、callback 或进程重启时，客户端只有在安全存储材料经当前 `account_subject + audience + device` scope 及 server reservation 验证通过后，才可重新展示同一 Key 并回到“生成 Key 确认”步骤；没有该材料时才进入 `Existing Recovery Key` 输入步骤。服务器 reservation 与 public checkpoint 都不能证明用户已记住、导出或仍持有 Key，UI MUST NOT 作此声明。该材料来源只决定如何取得 recovery authority，MUST NOT 提升或回退服务端 phase。

只要 live handoff 的权威目标仍是 `complete_identity`，`active | reserved | did_published | pcr_accepted | account_bound` MUST 由同一条 handoff continuation flow 承载；本地 registration checkpoint 的存在不得改选另一套恢复状态机。经验证的 checkpoint 和 Recovery Key 只能使该 continuation flow 跳过已经满足的内部步骤：有匹配的安全存储 Key 时直接重新展示并要求确认同一 Key；没有时要求输入原 Key；不得因 checkpoint 缺失把 `pcr_accepted` / `account_bound` 误判为死路，也不得因 checkpoint 存在再次要求输入本设备已经验证持有的 Key。

**重算输入与结束方式（normative）**：每次重算恰好从五类事实开始：(1) 最新 `AccountOnboardingState` 的 account subject、binding/lease state 与 goal；(2) lease 中的 reservation 与 fence；(3) 经 account/lease/reservation 校验的 durable public checkpoint；(4) 当前进程或平台安全存储中经验证的 Recovery Key availability，使用封闭状态 `unavailable | generated_pending_confirmation | recovered_pending_confirmation | generated_locally_validated_durable | existing_validated_durable` 表达；(5) handoff 的 holder binding、expiry 与服务端 freshness 决定。`generated_locally_validated_durable` 只表示本设备完成词组匹配并安全持久化，不表示用户已经记住、导出或完成外部备份。public checkpoint 不得冒充第 (4) 类事实，客户端也不得用 `serde_json::Value` 或自由字符串扩展这些闭合状态。

本流程只有两个 protocol terminal outcome：(a) `binding=bound` / lease `completed` 且首个 session、device 与 recovery-material gate 均完成，此时进入 Ready；(b) 用户显式完成 `abandon_provisional_identity`，旧 reservation 进入不可继续的 tombstone，随后必须以新 handoff 开始一个新流程。handoff/lease 过期、busy、网络结果不确定、命令失败、缺少 Recovery Key 和本地/服务器矛盾都不是成功终态；它们分别进入重新认证、等待后重算、刷新 snapshot、补充原 Key/显式放弃或 fail-closed 修复分支。任何分支恢复后都从上述五类事实重新计算，不得从旧 UI step 继续。

持有尚未到原始 `expires_at` 且未撤销的 handoff 的客户端 MUST 通过 `ak.gate.account.read.onboarding.v1` 取得封闭的 `AccountOnboardingState`。这里的只读 reconciliation authority 在成功的 register 已消费 handoff 后仍持续到该 handoff 的原始 expiry：服务端 MUST 只允许同一 bearer、同一 DPoP holder 读取同一 handoff/account 的 durable projection，使 response loss 能观察 `account_bound` / `completed`；该 consumed handoff 不再授权任何 command、session issuance 或另一 principal。过期、撤销或未知 handoff 必须拒绝。其 `goal` 恰为 `{goal:"complete_identity"}`。删除 abandonment challenge 后不存在服务端待确认的放弃子状态；客户端仅在用户显式选择后冻结本次放弃 intent，完成新鲜认证，再发送唯一放弃命令。自动 reconciliation 不得发起该动作。

**DID 首次发布的 frozen-reservation barrier（normative）**：Account Authority MUST 在首次向 DID registry 或 method-native log 提交任何 publication 请求之前，于同一原子步骤中验证当前 live `identity_creation_lease`、匹配 fence、holder、reservation 与 challenge，并冻结 `principal_id`、`did`、完整 canonical `principal_registration_anchor` bytes 及其 digest。缺少 live lease、lease 已过期、fence 不匹配或 holder 不一致的 holder-originated command MUST 在任何 registry I/O 之前 fail closed 且零写入；在 registry I/O 完成之后再检查 lease 不构成该前置条件的替代，因为已发生的外部副作用不可撤销。

reservation 一旦冻结，任何首次提交、超时重试、崩溃恢复、response-loss reconciliation 与 fence takeover MUST 只查询或 exact replay 已冻结的同一份 canonical DID operation；MUST NOT 替换 `principal_id`、`did`、operation digest 或 canonical bytes，也 MUST NOT 为该 reservation 创建第二份 DID operation。registry 对 exact replay 返回的 acceptance MUST 稳定收敛到同一个 `did_published` checkpoint 与同一个 `accepted_at`。

**跨 Authority 时间不构成因果排序（normative）**：`registration_did_evidence.accepted_at` 记录受信 registry 按自身权威时钟首次接纳 exact DID operation 的时刻，`control_proof.created_at` 记录证明签署方在自己签名原像内承诺的时刻；两者来自不同 Authority 的独立时钟，彼此之间不存在可依赖的因果排序。任何实现 MUST NOT 以两者的先后或差值作为接受或拒绝该 evidence 的条件，MUST NOT 要求 `accepted_at` 不早于 `control_proof.created_at`，也 MUST NOT 为此引入容差窗口、clock-skew 参数或补偿偏移。完整历史 `registration_did_evidence` 同样 MUST NOT 被施加相对于接收方当前时间的新鲜度检查。`accepted_at` MUST 原样取自 registry 对 exact operation 的原始接纳结果并由 Account Authority 冻结进 evidence digest；MUST NOT 由客户端指定、取 `max()`、在重放时重新取当前时间，也 MUST NOT 为修正时间重签完整 evidence。`control_proof.created_at` 留在签名原像内且签名后不可改写，但它不是受信授时、registry receipt 或独立的新鲜度授权；首次执行权仍只由本节的 challenge 窗口、live lease/holder/fence 与 `identity_creation_control_proof` 合同保证，删除本比较不放宽其中任何一项。

**中断恢复只续作、不重发（normative）**：已授权并持久冻结的 reservation 在 registry 响应丢失、进程崩溃，或 registry 已接纳而本地 `did_published` 尚未提交时，Account Authority MUST 重放同一 exact DID operation、取回同一原始 `accepted_at`，并以同一 frozen `registration_did_evidence_draft` 继续该 saga。MUST NOT 要求 registry 重新接纳，MUST NOT 更换 `did`、request identity 或任何已冻结材料，MUST NOT 重签 control proof 或完整 evidence，也 MUST NOT 仅因原 challenge 在此期间过期就把该内部续作重新视为首次发布。调用方认证、当前 lease/fence、takeover/abandonment 与终态约束仍按本节既有合同执行；registry 暂不可达属于依赖失败与结果不确定，MUST NOT 归类为签名或证明无效。

lease/fence 授权当前 holder 冻结 reservation 并发起 holder-originated command；它不是外部 registry 的跨系统锁，registry 也不需要理解它。Account Authority 的内部 saga recovery MAY 在原 holder lease 过期后查询或 exact replay 已冻结的 operation——例如 registry 已接受而本地 `did_published` checkpoint 尚未提交的崩溃场景——但 MUST NOT 据此接受任何 stale holder command 或新的 operation；通过 fence takeover 取得 lease 的新 holder MUST 继承该 frozen reservation，MUST NOT 替换其中冻结的 DID operation。

三种机制的责任边界（normative）：identity-creation lease/fence 提供 holder 互斥；frozen reservation 加 exact replay 保证同一账号/audience reservation 最多有一份 canonical DID operation 到达 registry；账号维度 PCR create-once 只保证 PCR acceptance 唯一，不保证 DID 发布唯一，也不能补救已经发生的 registry 副作用。DID 发布唯一性由 live lease/fence 授权下的原子冻结与 frozen operation exact replay 共同保证。上述 barrier 由 conformance vector `ak.vector.identity.frozen_reservation_barrier.v1` 覆盖（见 [`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md) §10.9.0.3）。

6. Account Authority 发布 exact client-signed DID operation，使用 registry 返回且 exact replay 稳定的 `accepted_at` 完成 `registration_did_evidence`，并通过 `ak.peer.principal_genesis.command.submit.v1` 原样 relay exact DID operation、完整 frozen evidence、genesis unit 与 root-signed pins。S2S signature 只认证 transport/correlation；Station 必须从 relay 内的 method-native operation 独立验证 adapter projection、两个 root proof、method evidence、DID log pins、root/device Event proofs、descriptor/payload commitments、event-derived PCR id、empty frontier、账号维度 create-once 与 atomicity；MUST NOT 查询 current resolver、数据库最新 DID row 或当前 method head补材料。该 pre-grant genesis unit 不携带、也不得被持久层要求预签发的 Authorization Lease 或 Control Proposal Ack；Account Authority 的 S2S 身份只绑定账号协调与传输来源，不能成为 Event authority。
7. Station 返回 durable batch receipt，`scope.kind="pcr_genesis_unit"`，且 `scope.registration_evidence_digest` MUST 等于完整 `registration_did_evidence` 的 RFC 8785 JCS SHA-256。genesis 的完整验证由第 6 步的 Station 唯一负责。Account Authority 只验证该**经认证的 outcome 与自己冻结的材料相符**：receipt 的 account/principal/PCR、`initial_resolution`、三项 DID log pin、registration evidence digest、device/key/HPKE、DID operation、lease/fence 与 request identity 逐字一致，之后才可提交一账号一 principal binding。Account Authority MUST NOT 为同一事实从 `events[]` 的 Event ID 派生 digest、resolve 已接纳 Event 或再次重放 genesis。HTTP 2xx、只带 Event ID、或未绑定本次冻结请求的 receipt MUST NOT 足以提交 binding。receipt 不复制 Event digest，也不携带或证明 accepted frontier/Seal basis。`scope.device_key_digest` 与 `scope.hpke_key_digest` 的原像与 `control_key_digest` 同族，固定为 `SHA-256(UTF-8(canonical multikey))`：前者的原像是 `founding_device_descriptor.`device_public_key_did` **剥去 `did:key:` 前缀后的裸 multikey**，后者的原像是 `hpke_key` 的原样字节；两者都固定 SHA-256，不随 Realm `digest_algorithm` 变化。receipt 承载它们是因为 receipt 不携原始 key；`founding_device_descriptor` 本身携 key，因此不得再携这两个 digest（见 `derived-wire-field-removal-lock.json`）。把完整 `did:key:` URI 当原像是错误约定，MUST 拒绝。原子接受同时初始化 `ak.component.identity.resolution.v1`、PCR-local monotonic `current_device_generation_ref := 1` 与 `device_generation_status := active`；generation ref 不等于也不派生自 DID `versionId`，且这些投影不得在 unit 全部验证通过之前可见。
8. Account Authority 随后从 issuer ledger 签发 `credential_class="standard"` grant。`InitialSessionGrantIntent.device_id` 必须等于 founding descriptor；public JWK thumbprint必须等于 handoff/control proof DPoP JKT；audience 必须等于该部署的 Principal audience。Standard human scope 是规范固定的非空、排序、唯一 operation set，由 issuer 独立物化；`InitialSessionGrantIntent` 与其它 human request 均不得携 `requested_scope`。`pcr_accepted` 前不得签发 principal grant；account binding commit 后签发超时只能 exact replay issuer ledger，不能重建 PCR。

整个 register 以 `(service_account,principal_id,registration_anchor_digest)` 与 idempotency key 做 exact replay：相同 bytes 返回同一 saga/receipt/grant outcome；同 key 不同 bytes、账号/principal 冲突或 genesis digest 变化必须零写入失败。一个 Account Authority 下一个 service account 只绑定一个 active principal，一个 principal 也只绑定一个 active account。

`AccountRegisterOutcome.binding_receipt` 必须由 Account Authority 签发并闭合绑定 `account_subject`、`principal_id`、`did`、method head/version、lease/fence 与 operation digest。Account Authority 验证方法原生 registration evidence 及发行者历史，客户端消费已认证且与预期 service/issuer 绑定的注册结果，MUST 核对其账号、自己生成的 DID/设备公钥、frozen operation bytes 与派生 digest、lease/fence 和 receipt 坐标；任何冲突都 fail closed。该本地意图比对不要求回取或重放 Account Authority/主体的完整方法历史，也不把任意 registry endpoint 视为受信服务。后续 handoff 返回的 `principal_id` 若不等于本地 frozen/derived `did_core_id`，必须 `account_binding_principal_mismatch`，不得覆盖本地锚。私钥 possession 和带外设备信任按 [服务器信任与结果消费](../sync/server-trusted-results.md) 保留。

若设备在 PCR accepted 前物理损毁，新 holder 在旧 lease 过期后可递增 fence、继承 reservation，并用同一 registration control 对新 challenge 与 founding unit 重签。PCR create-once 使并发 unit 只有一个 winner；若旧 unit 已先 accepted，新设备必须走已接受 recovery policy，不能再次 genesis。若 PCR 未 accepted 且 registration control 也丢失，可显式放弃 provisional identity 并新建 DID/PCR。放弃必须是显式用户动作，保留 orphan-anchor tombstone/audit reservation，且不得把已放弃 checkpoint 继续暴露为账号可读状态。

**执行放弃的唯一 wire 形态（normative）**：`ak.gate.account.command.abandon_identity_creation.v1`（`POST /_arkret/gate/account/identity-abandonments`）直接提交 `{request_id, identity_creation_lease_id, lease_fence, principal_id, did_version_id}`，使用为本次用户确认新取得、holder-bound 的 account handoff grant 与 DPoP proof。客户端发送前 MUST 展示固定后果：旧锚永久不可用、不能注销、没有可延续业务状态、必须新建 identity root/DID/PCR。自动登录、恢复或 fence 递增不得触发该命令；协议认证 holder 与本次请求，不声称挑战或自报确认字段证明 UI 已展示。

Account Authority 从 durable onboarding checkpoint 取得 account subject、冻结 identity/version、lease/fence 与后果，重验 live lease、fresh handoff 与 PCR-never-accepted。fresh 必须来自晚于该 frozen reservation 创建时刻的一次成功重新认证；只刷新 token 或复用原认证事件不满足。服务端从自己的 durable authentication record 判定，不接受客户端时间或布尔确认。终态检查、单一 orphan tombstone、checkpoint 抑制、lease 释放与幂等 outcome MUST 同事务；并发 PCR 已 accepted 时 `identity_creation_already_accepted`、零写入。相同 request_id 和 exact bytes 返回原 outcome，不制造第二 tombstone；不同 bytes 拒绝。重认证强度与冷却仍属部署治理。完整规则见 [key-management §5.0.2](./key-management.md)。

**未完成 reservation 的保留期限、自动垃圾回收时机与部署风控冷却属实现策略，本规范只作建议、不强制**：实现 SHOULD 为未完成的 reservation 设定有界生命周期并到期丢弃；`identity_creation_lease` 的 15 分钟 TTL 已经限定了 holder 独占窗口，回收窗口取同量级（例如半小时）是合理默认。具体时长、是否需要用户显式确认、以及与风控冷却期如何叠加，由部署自行决定；本规范不规定，也不要求实现具备自动回收能力。该豁免只覆盖保留期限、自动回收时机与风控冷却；本节的 holder 互斥、frozen-reservation barrier、exact replay 与已放弃 checkpoint 抑制是 normative 安全规则，不在实现策略豁免范围内。PCR 已 accepted 且无可满足 recovery proof 时必须 fail closed。

账号认证凭据与 principal Recovery Key 是两套正交权力：重置账号密码不能轮换 DID、授权设备或解密 E2EE；Recovery Key 也不能重置账号密码。

### 2.1.2a 绑定已发布 DID（normative）

`account_register_request_body` 的 `proof` 分支用于把一个**已经发布**的 `did` 所投影的 `did_core_id` 绑定到已认证的服务账号，
与 `identity_creation` 分支互斥。它不创建 DID、不保留 principal、不执行 PCR genesis。

**要求 DID 控制权证明的适用范围**：对 human principal，控制权证明只在**首次断言“这个新账号/PCR
绑定这个 DID”**、当前外部身份 claim、resolution method successor，以及 accepted recovery policy 明确
启用的 DID-root factor 上要求，不是每请求。
在已成立的绑定**之下**进行的操作不在此列——PCR 内 profile 由 device 签名的 Realm Event 承载，
账号侧属性（邮箱、密码、恢复联系人）由账号认证把关；二者都 MUST NOT 要求 DID 控制权证明。

1. 客户端调用 `ak.gate.account.command.issue_did_binding_challenge.v1`，提交 `principal_id` 与 `did`。
   Account Authority MUST 自行按 [`did-usage-and-verification.md` §5.4](./did-usage-and-verification.md)
   的 `high` tier 通过已登记 adapter 解析该 DID（同步刷新或 fail closed），先确认
   `project(did) == principal_id`，再从解析出的 current entry 推导 `did_version_id`、
   `log_head_digest` 与 `control_key_digest`。**MUST NOT 接受调用方自报的 DID history。**
2. **不自托管该 DID 的部署 MUST 另行要求 method-native witness / freshness 证据。**
   接受 registry 与 Station 同源是对**自有 DID** 的裁决，**不外延到第三方 DID**：
   自有 DID 的断言是"这是本服务的一个用户"，外部 DID 的断言是"这个账号就是某第三方身份"，
   后者会被导出给依赖方，是有外部爆炸半径的冒充面。
3. 客户端把 challenge 回显字段**逐字节比对**本地期望值后，才用 `did_version_id` 所钉 entry 的
   **current active update key** 签 `account_registration_control_proof`；任一不符 MUST fail closed
   且不得签名。验证方 MUST 从已验证 DID history 选取该 key，MUST NOT 采信请求自带的 key
   或 DID Document 的 verificationMethod。
4. **该 DID 的 adapter / high-tier 验证实现与受信解析结果 MUST 归同一指定 owner**；同一部署 MAY 由 Station
   既有 resolver 承接该职责。指定 owner 完整解析 `did`、验证 method 证据与 `project(did)`，并对本次绑定提交的
   exact proof transcript 验签。非 owner 一方消费该已认证结果，MUST NOT 为同一份方法证据重复重放，也
   MUST NOT 采信调用方自报的结论；S2S 或部署内通道只认证传输来源。`ak.root.identity.read.resolve.v1` 只是
   解析载体，其存在 MUST NOT 被当作该实现已满足 §5.4 `high` tier 与 freshness 要求的证明；部署 MUST 另行
   核实指定 owner 的实际完整验证及所需的时间 / 版本绑定。
5. 绑定成立后，Station MUST 把已验证的 `{principal_id,did,method_history_head,version_id}`
   作为 PCR genesis `initial_resolution` 持久化，并从 resolution cell 生成 Profile current projection。
   本地账号记录仍是账号运营真相；日常操作使用 `principal_id`，不因普通请求回源 DID host。
6. **绑定的时态**：注册成功后，上述 proof 与 method evidence 冻结为 registration-time historical
   evidence。账号注销/擦除、session、device、capability、MLS 与普通 PCR 操作 MUST NOT 刷新 DID。
   current DID mismatch/deactivation 只把独立 external claim 标为 `stale`/`invalid`，MUST NOT 限制、
   解绑、冻结或转移账号/PCR。

**challenge 生成与绑定提交是两个不同时间点（normative）**：第 1 步的解析与第 3–5 步的提交各自是一次独立的时间观察。两阶段若按 §5.4 的 freshness / current-key 合同需要刷新，MUST 刷新；MUST NOT 复用已失效的 challenge-era currentness，也 MUST NOT 声称整个注册只需要一次解析。第三方 DID 的 method-native witness / freshness、current active update key、exact proof transcript 与 `project(did)` 检查继续由上述指定 owner 执行；本家 Station 与 Account Authority 之间的部署内互信 MUST NOT 外推为信任第三方 DID host。本分支同样不新增第二份 DID、第二条 PCR lineage、账号绑定覆盖或私有注册端点。

账号的唯一外部身份是 closed `AccountId {principal_id, station_id}`；两个字段均为规范化 `did_core_id`，必须作为一个原子值传递和比较。`authority` 表达“为什么有权”，由签名、grant、producer proof 与已确认授权状态 承载；`AccountId` 只表达“是谁”。协议和实现 MUST NOT 重新引入 authority-named identity、只按一个分量比较、把两个分量作为松散 identity 传递，或用 PCR / service-local key 替代 `AccountId`。

`AccountId` 与创建它的 Station 数据谱系永久绑定。同一 `principal_id` 在另一 Station 上注册会形成新的 `AccountId`、新的账号和新的 PCR lineage，绝不是原账号的搬迁、恢复、接管、合并或别名。原 Station 上的 Event、PCR、投影、设备上下文、session、cursor、to-device queue、push registration、admission 与审计谱系 MUST NOT 迁移、合并、由另一 Station 接管、继承或改写为另一 `station_id`；DID 表示、DID Document、handle 或 resolution 变化不改变该绑定。Station 的进程、数据库、存储副本或同一运营方基础设施 MAY 做运维迁移/复制，但该操作不得改变 wire `AccountId`、权威历史或数据所有权。

**跨 Station 权限隔离（normative）**：即使 `principal_id` 完全相同，只要 `station_id` 不同，就是两个不同的 Account；二者之间 MUST NOT 因 principal 相等而产生任何隐式授权、权限继承、代行或恢复关系。任何 membership、capability、Realm root controller 或 recovery trustee 对 Account 的匹配 MUST 使用完整 `AccountId`。两个 Account 之间的显式授权也必须分别满足所用授权合同，不能由共同 principal 代替。

**Station 永久失效边界（normative）**：如果承载该 Account 的 Station 及其原有权威谱系已永久不可恢复，该 Account 与 PCR 就不可恢复；协议 MUST NOT 通过另一个 Station 延续或复活它们。暂时离线或同一 Station 谱系内的运维恢复不属于此情形。Realm 本身不绑定服务器。普通 Realm 的 Seal 确认服务故障切换或 root controller 变更必须满足各自独立的已登记授权与状态连续性合同；它们 MUST NOT 复活失效 Account，也不得把该 Account 的权限赋给另一 Station 上的同 principal Account。

同一 Station 对同一 `AccountId` MUST 终身只创建一个 service-local account binding 与一条 PCR genesis lineage，并在 hard erasure 后保留 uniqueness tombstone，禁止 replacement `AccountId`、第二条 PCR lineage或重新 registration。该 create-once 约束不把既有 account 的 `active` status 变成一次性资源：§3 允许 deployment policy 门控的原 account reactivation。device、recovery、session、resolution、KeyPackage、secret storage 与 account status 可按本地 PCR lineage 分区，但 PCR id、genesis receipt 与 frontier 不得进入 membership、grant、Contact、Event 或 cache/query 的外部 identity。

注册后的 resolution 变更 MUST 由该 PCR 中的 `ak.identity.resolution.update` 提交，不能直接覆写 profile 或账号表。Event 以 previous Event ref / previous history head 做 CAS，reducer 更新 `ak.component.identity.resolution.v1`；Profile 只公开其 current projection。current holder MAY 请求 Event、receipt 与 accepted Seal 组成的选择性历史 evidence，并用注册 reducer 重放 current projection，不另造 resolution 专用 proof。其他 Station 不要求持久保存该用户的 resolution；敏感操作发生时必须重新取得最新 evidence 并独立验证，短 TTL cache 只能优化读取，不能成为授权依据。

### 2.1.3 SessionGrant 不确定结果与身份边界

**认证事务与既有会话隔离（normative）**：显式登录、服务账号注册、OIDC callback 和
AccountHandoff continuation 由当前认证事务独占其页面与 continuation。客户端 MUST 先等待安全存储
hydration 完成，再验证 callback state 并使用该事务冻结的 issuer/client/redirect、nonce、PKCE 与
holder 材料；Account Authority 仍按 §2.1.2 执行 code exchange proof 与账号绑定验证，不转移或重复
发明 callback state 的权威所有者。
本地存在旧 SessionGrant、非空 bearer、既有 AccountId 或已显示过应用页面，均 MUST NOT 被解释为
本次认证成功，MUST NOT 跳过 callback 或把它重定向到业务页面。旧会话仍有效也适用本规则。
用户显式取消事务后 MAY 返回既有账号，但仍须按该会话的当前授权状态验证，不能消费未验证 callback。

进入认证事务时，客户端 MUST 停止旧会话的自动 bootstrap、refresh、同步与账号派生读取，并隔离
已在途的旧任务：其晚到成功、拒绝、持久化写入或导航不得覆盖当前事务及之后接纳的会话。
这只是客户端执行所有权切换，不撤销服务端 grant，不删除长期设备或恢复材料。客户端 SHOULD
复用一个会话代次/所有权边界，不为此新增协议接口、凭据种类或持久化 ready/head 镜像。

只有本次事务按 §2.1.2 取得并验证完整 Standard grant、核对 current-principal 的 exact AccountId、
Station、holder/device 与唯一 PCR，并 durable 保存该 grant 及对应本地材料后，才可发布新的活动会话
并由该成功分支离开认证页面、启动业务 bootstrap。注册 continuation 中提前建立账号存储上下文
不代表完成注册；recovery readiness 仍遵守 §2.1.2，不能由旧会话或新 grant 推定。
错误或可重试结果必须留在当前事务中显示，不得默默回到起点。临时错误保留合法 exact request，
重试不能再次消费 authorization code，也不能改变 frozen request identity。

**终态失效的本地完成边界（normative）**：一次资源请求的 401 本身不证明账号/设备被撤销。
客户端按已登记错误分类执行允许的会话恢复；恢复明确终态拒绝，或恢复后对同一活动会话的验证仍明确
拒绝时，MUST 停止使用该凭据。处理必须绑定原请求的会话所有权与完整 AccountId/device/grant，
MUST NOT 清除后来接纳的会话或另一认证事务。失效必须覆盖该 grant 的内存状态、恢复来源及重复 bearer
缓存，等待安全存储删除完成后才可宣称清理成功；不得只清空 UI token 而在重载时复活同一无效 grant。
删除失败必须显示存储错误并保持禁止自动恢复的当前运行态，不能报告清理完成或降低存储安全等级。
网络超时、5xx、429、材料暂不可读与协议验证失败不得被臆断为服务端撤销，也不得触发身份或密钥重建。
资源服务器调用 issuer introspection 的 S2S 请求失败（包括 S2S 凭据被拒）、非成功 HTTP 响应或
不完整成功响应 MUST 返回 `503 auth_unavailable`，不得转换成终端用户 `401 unauthenticated`。
只有成功验证的 issuer outcome 明确声明该 grant 非 active，才可据此拒绝该用户会话。
只清理本次失效会话所拥有的凭据/绑定缓存；另一活动 handoff 的 holder、exact request 和长期
device、Recovery Key、DID/PCR/MLS、secret-storage 材料 MUST 保留。

SessionGrant issue / refresh 的 exact replay 规则以 [`key-management.md` §6.2](./key-management.md) 为准。
replay 命中 expired outcome 时返回 `session_grant_replay_expired`；命中 revoked / superseded outcome 时返回
`session_grant_replay_terminal`；记录已超过保留期、issuer 无法证明旧 attempt 是否提交时返回
`session_grant_replay_indeterminate`。三者都不得返回成功或在旧 request identity 下补发 grant。客户端
必须取得新的 one-shot proof 与 request identity 后重新认证。

account-first onboarding 在上述终态恢复时 MUST 复用 §2.1.2 的 identity-creation lease fence 与
`reserved_principal_id` / `reserved_registration_anchor_digest` / holder-authenticated registration-anchor checkpoint：新 holder 在租约
到期并 fence 后继续同一身份创建，不得重做已经 accepted 的 DID operation，也不得重新生成 Recovery
Key。普通登录则回到认证入口。

SessionGrant ID、refresh chain、local auth session 与 cache 的唯一真相源是 issuer ledger。任何不符合
[`key-management.md` §6.1](./key-management.md) ID 构造和 ledger 绑定的 session credential MUST 失效并
要求客户端重新登录；部署不得修改 JWT `jti`、把 Event/cell 重解释为 issuer record，或把无匹配
issuer record 的 row 注入 ledger。失效处理只能删除 session credential 与绑定缓存，MUST 保留
principal 私钥、Recovery Key、DID/PCR/MLS 与 secret-storage 数据；这是 auth session fence，不是
principal identity migration。

当登录账号已绑定到某个 exact `AccountId` 时，账号访问可由 account auth、passkey、
已授权 device 或 accepted PCR recovery policy 分别恢复。只有账号 recovery policy 显式登记 DID-root
factor 时，current DID control proof 才可作为附加分支；该分支必须指向同一 `AccountId`，不能因 `principal_id` 相同选择另一 Station 上的账号。

密码找回或邮箱验证码重置只允许恢复 service account 访问。除非同时满足 DID recovery policy，服务端 MUST NOT 因密码重置而：

- 轮换 DID 控制密钥。
- 授权新长期设备。
- 读取或重包 E2EE secret storage。
- 签发超过短期登录范围的 capability。
- 撤销用户现有设备，除非 recovery policy 或风险处置策略明确要求。

同理，账号恢复不会反向恢复、重置或改变 DID。失去 DID control key 不影响未启用 DID-root factor
的账号/PCR；组织账号恢复流程只服从 organization 角色合同，不能反推 human 账号需要 current DID。

## 3. Account Status Values

服务账户 `status` 值（封闭枚举，v1 wire MUST 仅使用以下值）：

- `active`
- `soft_logged_out`
- `locked`
- `suspended`
- `deactivated`
- `erasure_pending`

**正交性矩阵**：六个状态各自承载独立 lifecycle 行为，不能合并。下表给出关键正交维度，新状态提案 MUST 论证它在该矩阵中占据未覆盖的格子，否则用 `reason_code` 表达即可：

| 状态 | 触发方 | Session grant | DPoP grant 轮换 | Device trust | E2EE secret storage | Event history | 详细规则 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `active` | — | 有效 | 有效 | 保留 | 保留 | 保留 | — |
| `soft_logged_out` | auth service / 用户 logout | 已撤销 | 拒绝 ordinary refresh；须完整重新认证取得 fresh AccountHandoff，或执行明确的账户控制动作 | 保留 | 保留 | 保留 | §4 |
| `locked` | 安全风险检测 | 已撤销 | SHOULD 拒绝 | 保留 | 保留 | 保留 | §5 |
| `suspended` | 治理 / 合规 | 拒新发 | 拒新发 | 保留 | 保留 | 保留 | §6 |
| `deactivated` | 用户 / 管理员关账 | 已撤销 | 已撤销 | 标记 revoked | 客户端可清除 | 保留 | §7 |
| `erasure_pending` | 用户擦除请求 / GDPR | 已撤销 | 已撤销 | 已撤销 | 必删 | 按 redaction policy 最小化 | §8 |

`reason_code` 表达**为什么**进入该状态（如 `abuse_review` / `gdpr_request` / `password_compromise`）；状态本身表达**当前所处阶段的协议行为契约**。两者不可替代。

**认证错误码（normative）**：Account status 导致 session grant 或 grant-binding proof 失效时，服务端 MUST 返回与 current status 匹配的专用错误码，而不是退化成通用 `unauthenticated` / `capability_denied`。已签发 session 访问受保护 `/_arkret/self/*` 资源时：`soft_logged_out` 返回 `401 soft_logged_out`；`locked` 返回 `401 account_locked`；`deactivated` 返回 `401 account_deactivated`；`erasure_pending` 返回 `401 account_erased`。新 session grant 签发、session refresh 或普通登录完成阶段遇到 current status 时：`locked` SHOULD 返回 `403 account_locked`；`suspended` MUST 返回 `403 account_suspended`；`deactivated` SHOULD 返回 `403 account_deactivated`；`erasure_pending` MUST 返回 `401 account_erased`。唯一例外是下文完成完整 PCR recovery closure 的专用 completion operation：deployment policy allow 时它可在同一 issuer transaction 作者化 `deactivated → active` 并签发首个新 generation grant。尚未完成 recovery、policy deny 或普通 login/refresh 均不得使用该例外。这些 code 的机器真源是 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)；`account_locked` / `account_deactivated` 的入口差异由同行 `http_status_by_context` 机读化，`http_status` 是通用默认值。HTTP status 的差异只表达“已持有 grant 失效”与“新 grant 被 policy 拒发”的入口差异，不改变 account status 语义。

**合法状态转换（normative）**：Account Authority issuer ledger MUST 按下表判定从 current record 到 successor record 的状态转换是否合法；非法转换 MUST `failed_precondition`，`reason_code="account_status_transition_invalid"`，且 ledger/account row/audit/outbox 均零写入：

| from \ to | `active` | `soft_logged_out` | `locked` | `suspended` | `deactivated` | `erasure_pending` |
| --- | --- | --- | --- | --- | --- | --- |
| `active` | —（同态重放） | ✓ | ✓ | ✓ | ✓ | ✓ |
| `soft_logged_out` | ✓（§4，须 fresh AccountHandoff 或明确账户控制授权） | — | ✓ | ✓ | ✓ | ✓ |
| `locked` | ✓ | ✓ | — | ✓ | ✓ | ✓ |
| `suspended` | ✓（appeal 解除，须 Account Authority 当前策略授权） | ✓ | ✓ | — | ✓ | ✓ |
| `deactivated` | ✓（见下“重激活”；须 deployment policy allow + completed PCR recovery） | ✗ | ✗ | ✗ | — | ✓ |
| `erasure_pending` | ✗ | ✗ | ✗ | ✗ | ✗ | —（terminal） |

- **降低严格度**（任一 `to` 严格度低于 `from`，如 `suspended → active`、`locked → soft_logged_out`）必须由 Account Authority 在 current-head CAS transaction 内验证该转换对应的 fresh identity-control、appeal 或管理员授权。授权证明进入本地审计记录，不进入 portable `AccountStatusRecord`，不得由 receiver 二次裁决。
- **`erasure_pending` 为 terminal**（规则 3）：其唯一出边为空，任何转出 MUST 拒绝 `erasure_pending_is_terminal`。
- **`deactivated` 重激活**（normative）：deployment MAY 以本地 account-governance policy 永久拒绝恢复，也 MAY 允许恢复原 `account_id`；协议不得要求 holder 迁移到另一 Station。v1 不创建 replacement account：成功分支继续使用原 `(account_id, principal_id, station_id)` binding 与原 PCR lineage，MUST NOT 再次 registration、再次 PCR genesis 或释放 pair uniqueness。policy deny 必须返回 `account_deactivated` 且零 account/PCR/session/device 权威写入。

  policy allow 只解决 Account Authority 是否准许离开 `deactivated`；它不产生 PCR authority。调用方还 MUST 完成同一 PCR 的标准 RecoveryTransaction / re-anchor，满足已 accepted recovery policy，并取得 replacement device 签名的 completed terminal receipt 与 Station 签名的 completion attestation。单独的密码/OIDC、fresh account authentication、管理员/appeal 批准或 current DID control proof 均不能授权 replacement device；只有 accepted recovery policy 明确登记的 factor 可以参与。Account Authority 必须逐字验证 receipt/attestation 的 account binding、principal/PCR、transaction、replacement device authorization Event 与单调增加的 `result_model_generation_ref`，验证 Station completion attestation 对 exact receipt digest 的签名绑定，并确认 origin Station 的 current device projection 已接受该 exact Event/generation。receipt 的 `completed_at` 是 replacement device 作者化终态材料的时间，completion attestation 的 `completed_at` 是 coordinator 原子接受该 receipt 并完成 transaction 的时间；前者 MUST 不晚于后者，不要求二者逐字相等。

  只有上述验证完成后，Account Authority 才可在同一 durable issuer transaction 对 current head 签发 `deactivated → active` successor、原子恢复本地 account row、记录 audit/outbox，并签发绑定 exact replacement device authorization Event 与新 generation 的首个 Standard SessionGrant。`deactivated → soft_logged_out | locked | suspended` 仍非法；`erasure_pending` 仍 terminal。status commit 或 grant response 丢失只允许 exact replay 同一 recovery transaction、status successor 与 issuer-ledger grant，不得重新 re-anchor、产生第二 generation 或第二 successor。

  §7.1 deactivation fanout 的旧 session、device、KeyPackage、applet/agent delegation、push route 与 pending to-device delivery 保持 terminal，reactivation 不执行 bulk un-revoke。既有 `status_seq` / `previous_account_status_record_id` 排序 lifecycle successor；PCR 的 `current_device_generation_ref` fence 旧设备资源，因此 v1 不增加平行 `activation_epoch`。普通 login、returning-device grant issue、refresh 与通用 admin status patch 在 current status 为 `deactivated` 时仍必须 `account_deactivated`；只有完成上述 recovery evidence closure 的专用 completion operation 可以作者化 active successor。

状态真相是 Account Authority issuer ledger 中的 immutable signed record：

```json
{
  "schema": "ak.schema.account_status_record.v1",
  "account_status_record_id": "ak:account_status_record:Aaqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq",
  "account_authority_id": "ak:did_core:webvh:zGtABZixoZZ3m4cFx3E65LCmg",
  "account_id": {
    "principal_id": "ak:did_core:webvh:z6mkfixture",
    "station_id": "ak:did_core:webvh:zStation"
  },
  "principal_control_realm_id": "ak:realm:AZCGyNJicm4u8jUY2OGd52Dj8JvlbxtGx3rDYQWAMPGe",
  "binding_version": 1,
  "status_seq": 7,
  "previous_account_status_record_id": "ak:account_status_record:Abbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "status": "suspended",
  "reason_code": "abuse_review",
  "effective_at": "2026-04-26T00:00:00.000Z",
  "issued_at": "2026-04-26T00:00:00.000Z",
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:webvh:zGtABZixoZZ3m4cFx3E65LCmg:auth.example#account-status-key",
    "payload_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "created_at": "2026-04-26T00:00:00.000Z",
    "jws": "a..b"
  }
}
```

`AccountStatusRecord` 的 signer MUST 是对该 `account_id` 具有权威性的 Account Authority。holder 自助请求、appeal、管理员、风控服务或 Station 只能提交 authenticated transition command；它们不得直接签发 portable record。`proof.verification_method` 的 controller 与 `account_authority_id` 必须解析到同一 Account Authority，且 key 在 `issued_at` 对应的历史窗口内 active。record 的 account/principal/binding tuple 必须逐字匹配 Account Authority 本地已接受 binding。

### 3.1 Account Authority issuer ledger 与复制载体（normative）

Account lifecycle 不属于 Principal Control Realm finality domain。`AccountStatusRecord` 不是 Event，不进入 Realm timeline、actor frontier、Seal、CBS、Control Proposal、pending Control index 或 lattice reducer。`principal_control_realm_id` 仅是已验证 account binding coordinate；holder device 或 PCR notary 对 Account Authority 的 deny transition 没有签名或最终否决权。

Account Authority 的本地 issuer ledger 是该 `account_id` 的唯一 lifecycle 真相源：

1. 首次 account binding commit MUST 在同一数据库事务创建 `status_seq=1,status=active` 的 genesis record；它没有 `previous_account_status_record_id`，不查询 Station frontier，也不等待 holder/Seal。
2. successor MUST 对 `(account_authority_id,account_id)` current head 做 CAS，且 `status_seq=current+1`、`previous_account_status_record_id=current.account_status_record_id`。同 request identity + 同 canonical intent exact replay 返回首次 bytes；异 intent 返回 `duplicate_conflict` 且零写入。
3. account row、immutable record、transition audit 与传播 outbox MUST 原子提交。record identity 是 `0x01 || SHA-256(JCS(closed unsigned core))` 的 canonical Base64URL typed token；unsigned core 是除 `account_status_record_id` 与 `proof` 外的全部 record 字段。
4. `proof` context 固定为 `ak.account_status_record_proof.v1`；proof payload digest 覆盖同一 unsigned core，`proof.verification_method` 必须受 `account_authority_id` 控制。
5. `binding_version` 只能随已接受 account binding 单调推进；同 version 不同 principal authority/PCR tuple 是 fork，较低 version 是 rollback。Account Authority 不得在 binding 尚未权威提交时签 record。

Account Authority 向 Station 复制状态的唯一写 operation 是 `ak.peer.account_status.command.submit.v1`（`POST /_arkret/peer/account-status`）。request 只携 exact signed record；下游 fanout MAY 附带此前 receiver 的 `account_status_receipts[]`，但不得重建、重签或改变 record bytes。

- receiver MUST 验证 RFC 9421 transport、record id/digest/proof、Account Authority 历史 key、exact account/principal/binding tuple，并以 `(account_authority_id,account_id)` 持久化单调 replica。**分类的唯一比较基线是该 key 的 durable replica head（normative）**：receiver MUST NOT 用「该 `status_seq` 上已存的历史行」作基线，否则本地保留了多少历史这一纯 retention 决策会改变同一份 request bytes 的 typed 结果。按下表分类，先判 binding version、再判 sequence，首个命中的分支即结论：
  - `submitted.binding_version < head.binding_version`：`failed_precondition` + `account_status_binding_rollback`。该判定先于全部 sequence 分支，避免 rollback binding 从 advance 分支被写入。
  - 无 durable head 时：`status_seq=1` 是 genesis，accepted；`status_seq>1` 返回 `dependency_missing` 与 `required_status_seq=1`。
  - `submitted.status_seq == head.status_seq + 1`：predecessor 精确等于 `head.account_status_record_id` 才 advance；不等则 `failed_precondition` + `account_status_record_fork`。
  - `submitted.status_seq == head.status_seq`：record id 相同是 `duplicate`（幂等 terminal ack，零写入）；record id 不同是 `failed_precondition` + `account_status_record_fork`。
  - `submitted.status_seq < head.status_seq`：一律 `failed_precondition` + `account_status_record_stale`，**即使该 record 与 receiver 本地仍保留的同 `status_seq` 历史行逐字节相同**。`duplicate` 只留给「durable head 就是这条 record」；对更低 sequence 返回 `duplicate` 会让 Account Authority 的 bounded outbox 在后继 record 尚未复制时就把该 destination 标记完成。
  - `submitted.status_seq > head.status_seq + 1`：`dependency_missing` 与 exact `required_status_seq = head.status_seq + 1`，触发 bounded resolve。

  `account_status_record_fork` 分支 MUST 停止该 record 的自动重试/补链并进入 quarantine/operator alert。`account_status_binding_rollback`、`account_status_record_fork`、`account_status_record_stale` 三类均零写入且对 exact record 不可重试；只有 `dependency_missing` 保留 exact record 的可重试性。`peer_stale` 保留 federation frontier quarantine 原义，不表示 lower account-status sequence。本表的 canonical 机读投影是 [`account-status-replica-decision-table.json`](../../artifacts/registry/account-status-replica-decision-table.json)，receiver 与 conformance MUST 从该 registry 取值；registry 与本节 MUST 同批更新。
- 每份 `AccountStatusReceipt` 闭合绑定 `receipt_id`、account-status record id/digest、Account Authority、account、status_seq、receiver 与 accepted_at；proof context 固定为 `ak.account_status_replication_receipt_proof.v1`。它只证明该 receiver 已 durable replicated exact record，不授予签发 authority。
- `Idempotency-Key` 必填并进入 HTTP Message Signature transcript。Scope 是 `(Source-Service-ID,Destination-Service-ID,Idempotency-Key)`；同 key 不同 canonical body MUST `duplicate_conflict`。`accepted | duplicate` 是该 receiver 的 terminal ack；本协议不存在 `pending_seal`。
- HTTP 必须使用 RFC 9421 Message Signature，覆盖 method、target URI、authority、`Content-Digest`、Source/Destination service DID、Source/Destination trust domain 与 `Idempotency-Key`。Outer signature 只认证 transport caller，不替代 Account Authority record proof。
- receiver 遇 gap 或需要 freshness observation 时使用 `ak.peer.account_status.read.resolve.v1`（`POST /_arkret/peer/account-status/resolve`）向 Account Authority 取得最多 128 条从 `from_status_seq` 开始的原始连续 records。响应按 `status_seq` 升序；`has_more=true` 时给出 `next_status_seq`。未知、无关系或无权 caller 必须在读取 ledger 前以 operation 注册的 non-enumerating outcome 拒绝。

首个接收 Station 从自身已持久化的 account session/device/KeyPackage/to-device/push-route、principal locator，以及引用该 exact AccountId 的 Realm membership 确定**实际受影响 Station 集合**，建立有界 durable outbox，并对每个目标复用上述 operation 的 receipted fanout 分支。集合只包含已经持有或即将持有该账号状态的服务；不得按相同 `principal_id` 扩大广播给无关 federation peer。每个目标按 `(account_authority_id,account_id,destination_id,account_status_record_id)` 去重；ack 后移出 outbox，失败按 bounded exponential backoff 重试。Outbox 必须有按 account/record/target 的唯一键、每 account 最大目标数 256、每目标最大一条未完成状态更新；不得跳过 predecessor、`deactivated` 或 `erasure_pending` 屏障，目标缺 gap 时先 resolve/补齐再提交后继。

上述 genesis/CAS、record identity/proof、gap/stale/duplicate/fork、幂等冲突与 fanout incomplete/complete 转换由 conformance vector `ak.vector.account_status.issuer_ledger.v1` 闭合。

Current account status 是 ledger current head 的 `status`。该 ledger 是 Account Authority 单写者的 strict hash chain，不存在并发 Event head、severity winner 或 PCR reducer。`account_id` 是 lifecycle key；同一 principal 绑定的其它 `account_id` 独立求值。

`AccountStatusRecord.expires_at` 仅是管理端与 UI 的复核/续期提示，不会在到时自动解除 `locked`、`suspended` 或其它状态。解除或改变状态仍 MUST 由 Account Authority 提交 successor record；receiver MUST NOT 根据本地墙钟合成状态。

1. 所有授权 gate MUST 读取本地 authoritative head（Account Authority）或已验证 monotonic replica（其它服务）；freshness 不足时向 Account Authority resolve，不能回调 holder device。
2. 降低严格度只由 Account Authority current-head transaction 执行，receiver 不接受绕过 predecessor 的恢复 record。
3. **`erasure_pending` 是 terminal 状态（normative，不可逆）**：任何 successor 均以 `erasure_pending_is_terminal` 拒绝。
4. 普通读面返回 `current_status`、`current_status_record_id` 与 `current_status_seq`；`reason_code`、`reason`、`effective_at` 来自同一 current record，不存在 producer-biased winner。

**Deactivation 进度 flag（normative）**：`status` 是封闭 6 值枚举（不含下列 token）。`deactivation_partial`（§7.1）与 `deactivation_federation_incomplete`（§7 末）**不是** `status` 值，而是 `deactivated` 状态下叠加的**独立服务侧 flag**，表达 deactivation fanout 的完成进度：

- `deactivation_partial`：boolean，默认 `false`。当某条本地 fanout（session/device/applet/KeyPackage/push/to-device）因网络或服务不可达失败、服务端仍在重试时为 `true`。`status` 仍为 `deactivated`。
- `deactivation_federation_incomplete`：boolean，默认 `false`。当该 principal 曾在其它 Station 持有状态、源 Station 未在 `deactivation_propagation_window_ms` 内得到 peer ack 时为 `true`，并触发 §7 末列出的写入暂停。`status` 仍为 `deactivated`。

二者均为服务侧投影 flag，与封闭 6 值 `status` 正交，MUST NOT 作为 `status` 取值出现在 wire 上；客户端 UI 据此区分"停用进行中 / 已完成"。

## 4. Soft Logout

`soft_logged_out` 表示当前 session grant 不再可用，但本地加密数据和 device trust 可保留。客户端 SHOULD：

- 停止 sync。
- 清除当前 session credential。
- 保留 device keys 和 secret storage 本地密钥，除非用户选择清除。
- `soft_logged_out` 已撤销 predecessor grant，因此不得把旧 grant、grant-binding key 或 accepted-device proof 组合成 ordinary refresh。账号/passkey 分支必须完整重新认证并产生 fresh AccountHandoff，再执行 returning-human SessionGrant issue；其它恢复只允许走协议明确登记的账户控制动作，例如专用 RecoveryTransaction completion。两条路径不得共享 refresh challenge 或通用 `proof_kind` 枚举。

服务端返回 `401 soft_logged_out` 时 MUST NOT 要求客户端删除本地 E2EE 密钥。

`soft_logged_out -> active` 由 Account Authority 的 current-head CAS transaction 执行，不是 ordinary refresh 内的一种可选 proof。human refresh 只适用于 current status 仍为 `active` 且 predecessor 尚有效的轮换链；一旦 status 为 `soft_logged_out`，refresh 必须返回 `soft_logged_out` 且零 successor。账号/passkey 分支只能通过完整重新认证取得 fresh AccountHandoff；Account Authority 先原子提交被该 fresh authorization 支持的 status successor，再允许 closed returning-human issue。PCR recovery 只走专用 recovery operation。实现不得为 soft logout 新增 challenge endpoint、`did_proof_required` fallback、client-generated nonce 或恢复用 `proof_kind` 分支。

### 4.1 显式登出（hard logout）与跨服务吊销编排

`soft_logged_out` 是当前 session grant 失效但凭证可恢复的软状态；用户主动「登出」是 **hard logout**——它 MUST 在所有持有该会话凭证的权威处终结会话，而非仅清本地。客户端可见的登出入口是 Principal describe 发布的 Account Authority；Account Authority 内部协调两个权威的状态:

- **Auth Server(认证服务)**:`browser_session`(登录认证上下文)+ 它签发的 `ak.session.grant` 轮换链(及其 `cnf.jkt` 设备持有绑定，见 [`crypto-media/device-lifecycle.md` §3.2](../crypto-media/device-lifecycle.md))。
- **Station(资源服务)**:对 issuer grant ledger 的有界内省缓存(TTL ≤120s)、待投递 to-device 队列及 push registration。Station **不**保存独立的本地 session 记录：issuer grant ledger 是唯一会话授权状态，内省缓存只是它的有界投影，敏感 operation MUST 旁路缓存并取 fresh 结果。客户端可见登录凭据仍是 `ak.session.grant`，客户端以 `Authorization: DPoP <ak.session.grant>` + `DPoP` proof 直接访问 `/_arkret/self/*`(见 [`../sync/api-conventions.md` §3.3](../sync/api-conventions.md));Station **不**为客户端铸独立本地 bearer，**不**暴露第二个客户端可见的 Principal 本地凭据签发 endpoint。

**编排(normative)**:hard logout 由 Account Authority 编排。客户端 MUST 从 `ServiceDescribe.auth_metadata.account_authority.gate_account_base_url` 派生并调用:

```text
POST /_arkret/gate/account/logout
```

该请求 MUST 使用 `Authorization: DPoP <ak.session.grant>` 出示当前 grant，并带 `DPoP` proof；DPoP `ath` MUST 绑定该 grant，`htu` MUST 绑定由 `gate_account_base_url` 派生出的 `/logout` URL，使 Account Authority 能定位要终结的 grant chain 与 principal device session。客户端 MUST NOT 分别向 Auth Server 与 Station 两个 origin 发起登出；部署内部的分权威调用是 Account Authority 的实现细节。普通客户端可见的 logout endpoint **只有** `POST /_arkret/gate/account/logout`。

1. **客户端** MUST：停止 sync、清除本地 session credential / `session_grant` / OIDC 凭证；hard logout SHOULD 额外清除本设备的 grant-binding(DPoP)私钥，使下次登录轮换 `cnf.jkt`(软恢复路径 MUST 保留该 key 以便 refresh)。
2. **Account Authority → Auth-side** MUST 登出当前 grant 所属的 Auth-side session / `browser_session`，在同一 issuer ledger 中幂等撤销该链的 active grant 并终结轮换链。若 Auth-side 不在同进程，Account Authority MUST 调用标准 S2S 子操作 `POST /_arkret/gate/account/auth-sessions/logout`(`ak.gate.account.command.logout_auth_session.v1`)；该调用 MUST 使用 [`../sync/service-http-binding.md` §2.2.3](../sync/service-http-binding.md) 登记的 Account Authority → Auth Server 部署内认证通道，MUST NOT 复用客户端为高层 `/logout` URL 铸造的 DPoP proof。此后 (i) 凭同一 `cnf.jkt` grant-binding proof 调 `refresh` MUST 被拒(`session_logged_out`)，整条轮换链不可再续；(ii) 该 Auth-side session 下任何 grant 的 introspection MUST 从同一 ledger 返回 inactive(即 grant-binding key 不能在登出后重建或维持会话)。该步骤不得发布 SessionGrant state Event。
3. **Account Authority → Principal-side**：issuer grant ledger 是唯一会话授权/吊销真源。Station 的内省缓存只是受既定 TTL 限制的投影，主动失效 SHOULD 执行；敏感 operation 继续强制旁路缓存。hard logout 保留该设备 to-device drop 与 push registration 移除，因为它们是独立投递状态。不得新建或吊销另一份“本地设备会话记录”来代替 grant 状态，也不创建 AccountStatusRecord 或 ak.device.revoke，不擦除设备授权历史。

`POST /_arkret/gate/account/auth-sessions/logout` 是部署内部 S2S 子操作，不是客户端 account flow。该子操作 MUST 幂等：同一 Auth-side session / grant 已登出、已吊销、未知或已被剪枝时，Auth Server 仍 MUST 返回成功并把链视为已终结；鉴权失败、请求体不合法、或 Auth Server 无法确认完成时才返回错误。普通客户端、inkson、浏览器 UI 与移动客户端 **MUST NOT** 调用或自行派生该路径；即使高层 `/logout` 失败，客户端也只能重试 `ak.gate.account.command.logout.v1`。客户端和服务实现 **MUST NOT** 依赖任何实现私有 / 产品私有(例如 `/_<impl>/*`)路由完成登出。

**登出耐久性(normative)**：hard logout 的本地清除(步骤 1)与 Account Authority 服务端编排(步骤 2、3)不是原子的——客户端在清本地凭证后、Account Authority 返回前可能崩溃、关页或离线。为防止「本地已登出但服务端轮换链仍存活」的窗口，客户端 **SHOULD** 在执行本地清除**之前**把登出意图(至少：Account Authority `/logout` endpoint、grant JWT、用于铸 grant-binding(DPoP)proof 的 grant-binding key)持久化(journal)，并在调用失败时重试(含下次启动重放)，直至 Account Authority 确认 grant 链终结后方清除该 journal。其中 Auth-side grant + `browser_session` 终结是耐久性关键步：它一旦完成，轮换链不可再续，后续无法恢复本地 account session。由于 `ak.session.grant` 有受限 TTL(见 [`crypto-media/device-lifecycle.md` §3.3](../crypto-media/device-lifecycle.md))，客户端 **MAY** 在该 TTL(加时钟 skew 容忍)过后停止重试：此时整条链已因自然过期失效，journal 中已无可吊销之物。重试 **MUST** 幂等——对已吊销/已过期 grant 再次调 hard logout 不应被视为错误。若高层 `/logout` 的 Auth-side introspection 对该 grant 返回 `not_found` 且不再提供 principal/device 元数据，Account Authority **MUST** 仍以原始、可解析的 grant JWT 调用 `ak.gate.account.command.logout_auth_session.v1`；只有该 S2S 子操作确认完成后才可把高层请求视为幂等成功，此时因不存在可定位的 Principal-side 会话元数据而跳过步骤 3 是允许的。`audience_mismatch` **MUST NOT** 被折叠为 `not_found` 或“already gone”：它仍须 fail closed，避免把发往错误 Account Authority 的登出 journal 误判为已经终结。

**执行顺序与失败语义(normative)**：Auth-side session logout / grant-chain 终结是耐久性关键步，Account Authority SHOULD 先完成步骤 2，再完成 Principal-side 本地清理。若步骤 2 失败且没有可证明的 durable completion，Account Authority MUST 返回可重试 Problem Details（例如 `temporarily_unavailable`），不得返回 2xx typed outcome。若步骤 2 已成功而步骤 3 暂时失败，Account Authority MAY 返回成功前把 Principal-side 清理持久化到 durable retry 队列；重复执行高层 `/logout` MUST 幂等。客户端在收到失败或网络中断时 MUST 只重试 `POST /_arkret/gate/account/logout`，MUST NOT 直接调用 `auth-sessions/logout`。

**吊销传播与生效语义(normative)**：Account Authority 内部可同步调用或异步重试 Principal-side 终结，但对客户端返回成功前 MUST 至少保证 Auth-side grant 轮换链已不可续。Station 对会话有效性的唯一判据是 issuer grant ledger 的 session-grant 内省结果，不存在第二份本地 session 授权记录；Auth-side grant/会话被吊销后，Station MUST 在下一次权威查询得到 `active=false` 并 fail closed。实现 MAY 缓存内省结果，但该有界缓存的绝对 TTL（≤120s）就是吊销生效的唯一上界，MUST NOT 由任何本地记录另行延长；敏感 operation MUST 旁路缓存取 fresh 结果，高安全 profile SHOULD 采用更短 TTL。Auth Server / Station MUST NOT 依赖对方主动 push 吊销；Account Authority 是客户端可见的编排边界。

**轮换链单次 successor 与重用即妥协(normative)**：一次逻辑 refresh 只能产生一个 successor。轮换 MUST 在同一 issuer transaction 创建 successor 并把 predecessor 标记为 `superseded`。使用相同 `(predecessor_grant_id, refresh_request_digest)` 与 byte-identical intent 的 exact replay MUST 返回已记录的同一 successor；不得把它误判为第二次消费。对同一已 superseded grant 使用不同 request identity 或不同 canonical intent 再次发起轮换 MUST 拒(`grant_already_consumed` 或 `duplicate_conflict`)，且 SHOULD 视为凭证泄露信号并吊销整条轮换链。

**与 soft logout 的区别**：soft logout 可凭 §4 登记的 account/device/PCR recovery authority 恢复；hard logout 终结 grant 链 + `browser_session`，恢复 MUST 重新走完整认证。

## 5. Locked

`locked` 表示安全风险临时锁定。服务端 MUST：

- 拒绝新 session grant。
- 可允许 recovery / appeal / export。
- SHOULD 拒绝 DPoP grant 轮换（与 §3 正交性矩阵 `locked` 行一致）。
- 不自动删除 Event history 或私有 account data。

已登录设备 SHOULD 收到 account status sync，并停止提交写事件。

## 6. Suspended

`suspended` 表示治理或合规暂停。服务端 SHOULD：

- 拒绝写入和 Applet delegation。
- 可继续允许读取自有数据和导出。
- 可对公共目录隐藏 profile。
- 在联邦中广播最小必要状态，避免其他节点继续接受来自该 service account 的写入。

Realm 内 membership 不自动变成 ban；是否移除由 Realm policy 决定。

## 7. Deactivated

`deactivated` 表示用户主动或管理员执行账户停用。服务端 MUST：

- 撤销 session grant。
- 停止 push。
- 停用 applet delegated device。
- 标记 device 为 revoked。
- 保留 signed event 历史，除非另有 erasure policy。

客户端 SHOULD 提供本地密钥清除选项。Deactivation MUST NOT 伪造 redaction；历史事件如需隐藏，必须提交真实 `ak.redaction` 或遵循 retention policy。

### 7.1 Deactivation Fanout（normative）

为关闭"deactivation 后仍有未撤销路径继续投递或被授权"的窗口，**deactivation accepted 进入 frontier 的同一事务边界内** MUST 对 exact `deactivated.account_id` 所属资源触发下列 fanout。本地存储先把该 `AccountId` 解析为 `account_pk` 并只按此外键关联；跨服务存储必须保留完整 canonical `AccountId`。无法证明 owner 的记录 MUST fail closed 并进入人工恢复队列，不能按相同 `principal_id` 扩大到另一账号：

| 域 | Fanout 动作 | 触发什么 event |
| --- | --- | --- |
| **Session grant** | 撤销全部 `ak.session.grant`（含 applet delegated session）；后续 session-grant introspection MUST 返回 `inactive`。 | 服务端撤销表 + 可选 `ak.audit.accessed` |
| **Device grant** | 全部 `ak.device.*` 标 `revoked`；后续 `ak.self.events.command.submit.v1` 用 revoked device 签名 MUST `actor_signature_revoked`。 | reducer 状态转换 |
| **Applet delegation** | 撤销所有 `ak.applet.registration` 持有的 delegated device；applet 服务后续调用 MUST `delegation_revoked`。 | reducer 状态转换 |
| **KeyPackage** | 由认证 `AccountId` 解析本地 `account_pk`，按该本地外键逐行 read/CAS 到终态：`published+unused → retired`；`claimed+unconsumed → revoked`并保留原 claim ID；`consumed`保持 immutable。KeyPackage wire object 不携 owner ID。CAS stale 必须重读并继续，直到写入目标终态或确认已处同一终态；stale conflict 不得计作完成。任何 terminal 不得复活或二次 claim。 | reducer + KeyPackage store 失效 |
| **Push route** | 撤销 exact `AccountId` 下的全部 `ak.device.push_route`；push gateway MUST 停止向这些注册 endpoint 投递。 | reducer + push gateway 缓存失效 |
| **To-device queue** | 服务端 to-device 队列 drop 所有目标 `AccountId == deactivated_account_id` 的 pending message；后续投递 MUST `recipient_unavailable`。 | server-side queue 状态 |
| **Identity link cache** | 客户端与服务端可见缓存 MUST eager invalidate 所有 `(*, pairwise_did → deactivated_principal)` 映射；不得等待 7d TTL 或 MLS epoch 推进。 | `ak.identity_link` cache invalidation |
| **Capability cache** | 所有 cached `ak.capability.grant` decision 以该完整 `AccountId` / account ActorId 作为 subject 或 issuer 的 MUST eager invalidate；下次 capability check 走完整判定。 | cache invalidation |

**写屏障（write barrier）**：`deactivated` accepted 进入当前 account status frontier 后，任何通过该 `account_id` 的 session、device 或 account binding 发起，或以该 account 作为 owner 的新 `ak.session.grant`、`ak.device.authorize`、KeyPackage publish / claim、agent / applet delegation、capability grant / delegation、push route、to-device enqueue，以及以 `{kind:"account",account_id:<该账号>}` 为 target 的 Realm membership 写入 MUST `failed_precondition`，`reason_code="account_deactivated"`。该屏障按完整 AccountId 的 status frontier 生效，不得被较新的 HLC、不同 device、未完成 federation ack、相同 `principal_id` 的其它账号或尚未失效的本地 cache 绕过。§3 的合法 reactivation 只在 completed PCR recovery 已接受新 device generation、Account Authority 已提交 exact `deactivated → active` successor 后解除该 account 的新写 gate；旧 fanout 资源仍保持 terminal，所有新 session/device/KeyPackage 必须绑定 replacement authorization Event 与新 current generation。同一 Station 不得借此为同一 pair 创建第二本地 account row 或第二 PCR genesis。已经在屏障前 accepted 的历史 Event 不被改写；尚处 pending / quarantine / soft-fail 的写入 MUST 在恢复前重新检查 current status、exact device authorization 与 generation fence。

约束：

- **不自动 ban**：deactivation 不等于 Realm 内 `ak.member.state` 转 `ban`/`leave`。哪些 Realm membership 自动 `ak.member.state = leave`（自愿停用）vs. 保留 `join`（policy 决定）由 Realm policy component `account_deactivation.member_action` 字段控制（该字段作为 Realm policy component 的登记见 [`../models/realm-and-space.md` §2.2](../models/realm-and-space.md)，经 `ak.realm.policy_bundle` payload 的 `account_deactivation` 组件写入；本节是其封闭枚举与处置语义的单一权威源）。该字段是封闭枚举，v1 取值域为：
  - `leave_self_initiated`（默认）：把该 principal 在本 Realm 的 membership 视为自愿退出，自动转 `ak.member.state = leave`。
  - `retain_membership`：保留 `join`，由 Realm policy 在后续显式处置（deactivation 本身不改 membership state）。
  - `leave_all`：无条件把该 principal 在本 Realm 的 membership 转 `leave`，等同 self-initiated 但不区分触发方语义。

  未识别的取值 MUST 按未知 policy 字段 fail closed（保守取 `retain_membership` 不主动改 membership，并标记 policy 解析告警），不得静默回退为默认值。注意本字段控制的是 membership state，与上表前 6 行无条件必停的本地投递撤销正交。
- **本地投递必停**：无论 policy 是否 ban，上表前 6 行（session/device/applet/KeyPackage/push/to-device queue）必停 — 否则会出现"账户已停用但其 device 还能签名 / push gateway 还在投递"的不可解释窗口。
- **Push route 行的完成判据（normative）**：push gateway 是独立主体，push route 行的完成判据是 push gateway 侧停止投递。当 gateway 独立持有注册 endpoint / 投递状态时，Station MUST 通过已登记的内部通道通知 gateway 并取得处理结果；Station 的本地存储 purge 不构成该行的完成。未取得 gateway 处理结果时该行按未完成计，适用下文 `deactivation_partial` 的标记与重试语义。
- **MLS Remove**：若 Realm policy 决定 deactivate → leave，对应 MLS group MUST 在 grace window（默认 `mls_deactivation_grace_ms = 600,000 ms`）内 emit `ak.mls.commit` Remove；超时未 commit 则该 Realm 的成员客户端 MUST 在 verified timeline 中把该 principal 标 `unverifiable_member`，不再接受其新 epoch 消息。
- Fanout 失败的 partial state：如果某条 fanout 因网络 / 服务不可达失败，server `account_status` MUST 标 `deactivation_partial` 并继续重试；客户端 UI MUST 显式标记 "停用未完成" 而不是显示已停用。
- **跨 Station 传播**：若该 principal 曾在其它 Station 上持有 device / KeyPackage / to-device / push-route 状态，或通过 Realm membership ActorId routing projection 使用过 peer 服务，首个接收 Station MUST 按 §3.1 的 durable affected-service index 与 `ak.peer.account_status.command.submit.v1` receipted fanout 分支主动推送原始 `AccountStatusRecord` 及其专用 `account_status_receipts[]`；不得塞入通用 Realm federation batch，不得广播给无关 peer。每个 destination 返回的 `accepted | duplicate` 才构成 ack。未在 `deactivation_propagation_window_ms` 内得到全部 ack 时，本地 `propagation_state` 转为 `incomplete`，服务侧投影 flag `deactivation_federation_incomplete=true`，并暂停新 Realm onboard、新 session/device grant 与新 KeyPackage 发布；该 flag 是可变的 outbox/projection 状态，MUST NOT 回写或重签 immutable record。后续全部 ack 到达后将 flag 清零并保留审计记录。

## 8. Erasure

`erasure_pending` 表示物理删除流程开始。实现 MUST 区分：

进入 deactivation/erasure 的 authority 来自 account auth 与该账号所绑定 PCR 的 accepted device/recovery
policy，按操作要求组合验证。current DID controller 既不是必需条件，也不能单独执行该动作。DID host
unreachable、external claim stale 或 DID deactivated 时，合法 holder 仍 MUST 能删除/擦除账号；仅持有
current DID proof 而没有所需 account/PCR authority MUST fail closed。

**进入前置 fanout（normative）**：任何从 `active` / `soft_logged_out` / `locked` /
`suspended` 直接进入 `erasure_pending` 的 accepted transition，MUST 在同一状态事务中先
执行 §7.1 的本地撤销 fanout（session、device、Applet、KeyPackage、push route 与
to-device queue），其失败与重试沿用 `deactivation_partial` 语义。Realm membership 处置
逐 Realm 复用 `account_deactivation.member_action`；未配置时默认 `leave`。从
`deactivated` 进入 `erasure_pending` 时不得重复产生已完成的撤销副作用，但 MUST 继续任何
尚未完成的 fanout。只有该前置步骤被接管后，projection 才可对外宣告 §3 矩阵中的“已撤销”。

- canonical event log：通常只能 redaction/minimization，不能破坏审计 hash 链。
- blob bytes：可按 retention/legal hold 删除。
- 本地/受托 projection：可删除或重新物化。
- account private state：可删除。
- policy/audit record：按合规周期保留最小字段。

**擦除完成态语义（normative）**：v1 **不**新增 `erased` / `tombstoned` 终态。`erasure_pending` 的 "pending" 表示"擦除已发起且不可逆"，**不**表示"擦除尚未完成"——擦除流程进入该状态后 account status projection 永久停在 `erasure_pending`（§3 规则 3，terminal）。擦除是否**已物理完成**由 erasure receipt（下文）独立表征，而非由 status 推进表达：审计 / UI MUST 通过是否存在有效 `ak.schema.erasure_receipt.v1`（及其 `outcome`）区分"擦除排队 / 进行中"与"擦除已结束",MUST NOT 从 `erasure_pending` 本身推断完成与否。

**执行状态机（normative）**：接收方接受一条 `status=erasure_pending` 的 `AccountStatusRecord` 时，必须为每个适用 storage boundary 建立一个可恢复的 durable execution，唯一键为 `(receiver_id,account_id,triggering_status_record_id,storage_boundary)`。接收 operation 只有在 execution intent 已持久后才可返回 `accepted | duplicate`；若 replica store 与 job store 不能共享物理事务，实现必须在启动与周期 reconciliation 中从已接受 record 重新派生缺失 intent，并在修复前保持 fail closed。worker 复用同一 typed erasure service 执行删除；不得在 account-status HTTP 事务内同步做物理擦除，也不得把 receipt submit 当作执行命令。精确重试、进程崩溃与 lease 过期都继续同一个 job；同 key 异 account/record/boundary 内容为永久冲突。`completed`、`partially_completed` 与 `blocked_by_legal_hold` 都是该 job 的 terminal receipt outcome，只有 transport/infrastructure failure 可重试。

Account Authority 不新增第二条私有 peer erase command。它发布 `erasure_pending` record 后只追踪上述确定性 execution，并通过既有 erasure receipt submit/get 轨道取得结果。Account Authority 只有在验证 receipt package、issuer proof、subject/scope、closed trigger 的 `account_status_record_id` 逐字等于本次 record，以及现行 `AccountId {principal_id,station_id}` 全部一致后，才可把物理擦除标为完成；收到 account-status `accepted`、HTTP 2xx、空返回或 connector 本地 no-op 都不构成完成证据。

擦除完成后，服务端 SHOULD 发布 signed erasure receipt；若服务声明支持 hard erasure conformance，则 MUST 使用 `ak.schema.erasure_receipt.v1` payload，并可通过 `ak.audit.erasure_receipt` durable audit Event 发布。Receipt 至少绑定 closed `trigger`、`subject`、`scope.storage_boundary`、`outcome`、`erased_classes[]`、`retained_stub_digest`、`legal_hold_ref?`、`completed_at`、`issuer` 与 `proofs[]`；retained stub 必须逐字绑定同一个 trigger。账号物理擦除时 trigger MUST 是 exact `erasure_pending` AccountStatusRecord id；其他擦除类型绑定各自授权 Event 的 event 分支。`proofs[]` MUST 至少包含 1 条，且其中至少一条由 `issuer` 当前有效的 verification method 签名；空 `proofs[]` MUST 触发下文 fail-closed 校验（等同 `proofs[]` 校验失败）。`retained_stub_digest` MUST 等于 `hash(canonical_json(retained_stub))`；stub 可内联在 receipt，也可通过 erasure receipt endpoint 获取，但两者 canonical bytes 必须一致。Stub 只保留 typed trigger/reference 结构、冗余 digest 一致性、receipt/stub binding，以及连接仍存在的 signature、redaction authorization 与 legal-hold evidence 所需最小字段，MUST NOT 保留已擦除明文或裸明文 digest。原 canonical bytes 已擦除时，stub 与 receipt 均不能独立重算或证明其 hash preimage。Receipt 只证明 issuer 在声明的存储边界内完成、部分完成或因 legal hold 阻止删除，不证明独立第三方副本已经消失。

**Legal hold 阻塞终态（normative）**：erasure 与 legal hold 并存时，擦除流程有一个稳定终态：`ak.schema.erasure_receipt.v1` 的 `outcome` 枚举含 `blocked_by_legal_hold`（与 `completed` / `partially_completed` 并列；schema 真源见 [`erasure-receipt.schema.json`](../../artifacts/schemas/erasure-receipt.schema.json)，该 outcome 下 `legal_hold_ref` 为必填）。语义约束：

- `outcome="blocked_by_legal_hold"` 是 **合法终态**，表示 issuer 在声明的存储边界内因 legal hold 不能删除受保护数据，擦除合法地、**无限期**挂起在该边界。它 **不** 构成"擦除未完成、需重试"——verifier / 调度方 MUST NOT 因该 outcome 反复重试擦除流程或把它当作失败；它与 §3 规则 3 的 `erasure_pending` terminal 状态一致：account status 永久停在 `erasure_pending`，由 receipt 的 `outcome` 表征其物理终态为"被 legal hold 阻塞"。
- legal hold 解除后，issuer SHOULD 继续执行此前被阻塞的删除并发布一份新的 `completed` / `partially_completed` receipt（按 `subject` / `scope.storage_boundary` 取最新有效 receipt）；在解除前，`blocked_by_legal_hold` 始终是该边界的当前权威终态。
- **UI 披露（normative）**：客户端 / admin UI MUST 在持有 `blocked_by_legal_hold` receipt 时向用户明确披露"该账号 / 数据擦除因 legal hold 暂被合法阻塞"（含 `legal_hold_ref`），MUST NOT 把它呈现为无限期 `pending` / "擦除进行中"或让用户以为流程卡死等待重试。注意它仍区别于 §8 fail-closed 校验失败（digest 不匹配 / stub 不可获取 / `proofs[]` 校验失败）导致的"擦除视为未完成"——后者 MUST 继续 fail-closed 并重试，前者是已结论的合法阻塞终态。

**Fail-closed 校验（normative）**：verifier 在接受一份 `ak.schema.erasure_receipt.v1` 之前 MUST 重算 `hash(canonical_json(retained_stub))` 并与 receipt 的 `retained_stub_digest` 比对。当 stub（内联或经 endpoint 获取）与 `retained_stub_digest` **不一致** 时，verifier MUST 拒绝该 receipt（`erasure_receipt_stub_digest_mismatch`），并将该 erasure 视为 **未完成**（fail closed），不得据此把 subject 标记为已擦除、不得释放 legal hold、不得停止重试擦除流程。digest 不匹配意味着 stub 被替换、截断或与 receipt 不同源，无法证明声明的存储边界内删除已真正发生；默认结论是"擦除未完成"而非"擦除成功"。同理，receipt 缺失 `retained_stub_digest`、stub 无法获取，或 `proofs[]` 校验失败时，verifier MUST 同样 fail closed。

### 8.1 用户自助擦除入口（normative）

用户本人发起账号擦除的唯一客户端 operation 是 `ak.gate.account.command.request_erasure.v1`
（`POST /_arkret/gate/account/erasure-requests`）。该入口由 Account Authority 在 gate 面
直接受理（gate 面服务方与客户端路由规则见
[`../sync/service-http-binding.md` §2.1.2](../sync/service-http-binding.md)），它只做
的三件事——鉴权、durable 记录擦除意图、触发本节既有的 `erasure_pending` 签发流程——
全部落在 Account Authority 内部，不存在跨服务移交：`erasure_pending` record 的签发者、
状态转换合法性判定与进入前置 fanout 的编排方本来就是 Account Authority，受理与签发同侧，
因此不出现"受理已 durable 而签发悬于另一服务"的中间态。它不创建第二套擦除语义，受理
本身也不直接签发 AccountStatusRecord——按 §3，holder 自助请求只能提交 authenticated
transition command，record 的签发者 MUST 是 Account Authority。

**认证新鲜度的归属（normative）**：需要 fresh 高风险动作认证的操作 MUST 由 Account
Authority 直接受理，认证新鲜度由 Account Authority 本地判定——它是唯一掌握 recent
login、WebAuthn、recovery key 事实的一方。Station MUST NOT 依据 session grant
introspection 或本地会话状态自行判定或近似认证新鲜度：introspection 响应刻意不投影
`auth_time` 或认证 proof kind，这是有意的闭合设计，任何试图在 Station 侧绕过该
闭合、重建新鲜度判定的做法都 MUST 视为协议违规。

- **请求与受理（normative）**：请求体是 closed object，只携带 `request_id` 幂等身份
  （schema 见 [`account-operations.schema.json`](../../artifacts/schemas/account-operations.schema.json)
  的 `account_request_erasure_request_body` / `account_request_erasure_outcome`）。成功响应是
  **受理确认**：它只证明意图已 durable 记录，既不表示 `erasure_pending`
  AccountStatusRecord 已签发，更不表示物理擦除完成。完成状态 MUST 经既有 account-status
  查询面（`ak.self.account.read.viewer.v1` 的 account lifecycle state、
  `ak.self.account.stream.subscribe.v1` 的 account-aggregate delta）观察；物理完成由本节既有
  的 erasure receipt 表征。客户端与服务端 MUST NOT 把本操作的成功响应解释为 record 签发或
  擦除完成的证据。
- **高风险动作认证（normative）**：Account Authority MUST 把本操作作为高风险动作处理，
  要求 fresh 高风险动作认证（recent login、WebAuthn、recovery key 或部署等价机制，与 §10
  的认证要求同族）；认证强度、风控检查与冷却期属部署治理，本节不规定具体时长。session
  不满足部署策略时 MUST 返回 `reauthentication_required` 且零写入，不得记录意图。
- **幂等（normative）**：同一 `request_id` 的 exact replay MUST 返回首次记录的同一受理
  outcome（含原 `recorded_at`），MUST NOT 产生第二条意图；同 `request_id` 不同 canonical
  bytes MUST `duplicate_conflict` 且零写入。`request_id` 不同而本账号已存在 record 尚未签发
  的 live 擦除意图时 MUST `failed_precondition`，`reason_code="erasure_request_already_pending"`。
  `erasure_pending` record 一经签发，§8 的进入前置 fanout 已在同一状态事务撤销 session
  grant，后续请求在认证层以 `account_erased` 失败。
- **撤回窗口（normative）**：不可逆点是 Account Authority 签发 `erasure_pending`
  AccountStatusRecord，而不是本操作的受理。Account Authority MAY 在受理与签发之间设置撤回
  窗口；窗口时长与是否存在属部署治理，可以是零。配置窗口时受理 outcome MUST 携带
  `withdrawal_window_ends_at`，且 Account Authority MUST NOT 在该时刻之前签发 record；未配置
  时该字段 MUST 省略。撤回只对 record 尚未签发的 live 意图有意义；record 一经签发，§3
  规则 3 的 terminal 语义生效，任何撤回 MUST fail closed。v1 不为撤回定义独立的 wire
  operation；部署如提供撤回窗口，其撤回面（部署治理）的效力 MUST 终结于 record 签发，
  MUST NOT 以任何形式复活已签发的 record。
- **进入条件**：本操作只接受 current status 为 `active` / `soft_logged_out` / `suspended`
  的请求；current status 由 Account Authority 本地判定，它是 account status 的真相源，
  无需向其它服务取证。`locked` / `deactivated` / `erasure_pending` 下 session grant 已按
  §3 矩阵失效，请求在认证层以对应状态码失败。受理后 Account Authority 签发的 record、
  传播、异步执行与回执完全复用 §8 既有流程；record 的 `reason_code` SHOULD 表达触发来源
  （如 `gdpr_request`）。

## 9. Session Revocation

用户或服务可撤销：

- 单个 session grant
- 单个 grant-binding session chain
- 单个 device
- 全部 session
- Applet delegated session

撤销 device MUST 产生 device list update。E2EE 客户端 MUST 停止向 revoked device 分享新密钥。

## 9.1 Agent principal lifecycle

由 Agent provisioning 与 accountability grant 证明、且 Actor Profile 分类为 `actor_kind="agent"` 的 Agent，其 lifecycle 是 controller 账户 lifecycle 的从属体；Profile 分类本身不建立该关系：

- **Provisioning** 由 controller 通过 `ak.self.agent.command.provision.v1` operation 发起。controller 先按 [`key-management.md` §3.6.3](./key-management.md) 生成并发布不含 PCR binding 的 Agent DID inception；`prepare` 校验该 accepted entry 0，写 private durable reservation 与 signed opaque allocation handle，并返回逐字一致的 `initial_resolution`，但 canonical published state 保持为零，且**不**分配 Agent PCR id。controller 把该承诺写入本地冻结的 PCR genesis，取 `principal_control_realm_id = retype(event_id)`，再签署恰好一条前向声明该值的 `ak.agent.provision` Event；`commit` 经普通 Event admission 接受后，在同一 reducer transaction 原子派生分别闭合的最小 provision、accountability、selector 与 realm-id-claim projections。不得用多 Event fan-out、服务代签、完整 payload 复制或部分 projection 替代。
  必填且 immutable 的 `requested_scope` 只建立 Agent key/session 的全局硬上限，不是 Realm 授权；其 private disclosure 与 commitment 只包含该完整 scope。provisioning 不得据此创建任何 `ak.capability.grant`。后续 Agent key scope、Realm-scoped grant 与 session request 不得越过该 ceiling；participation selection 是独立的 controller 偏好，在动作时只能进一步拒绝，不能补回 requested_scope 未授权的 action。
  commit 只把 outcome 推进到 `awaiting_pcr_genesis`：genesis 尚未接受时 Agent 对外不存在，DID PCR service entry、pairing handle 与 list/get 可见性全部推迟；accepted 的 provision 不可撤销，controller 必须从 durable intent 恢复并继续提交同一 genesis。Agent PCR genesis 必须在另一次提交中送出，其 `initial_resolution` 必须逐字段等于 provisioning 保存值；accepted 后 outcome 先成为 `awaiting_did_binding`。controller 使用 inception 预承诺的 update key 发布连续 entry 1，在其中加入 create-locked PCR service 四元组；只有该 update accepted 后 outcome 才成为 complete。
  controller E2EE client 随后提交 Actor Profile；若该 PCR 使用 exporter scheme，可另行上传 [`key-management.md` §7.5.6](./key-management.md) controller-owned history-only backup，但它不是 provisioning 或 pairing 前置。通用 Agent view 从 complete 起只暴露 lifecycle、readiness、presence 三轴；未完成首次 pairing 由 `readiness.blockers` 中的 `runtime_key_missing`/`pairing_open` 表达，不新增第四状态轴。pairing poll 可返回 operation-local `runtime_state` 诊断，但不得复制进 list/get/key_state。
- **Pause**(`ak.self.agent.command.pause.v1`):保留 agent identity、`accountability_grant`、`agent_key_authorize`、capability grants 的 durable state。Pause Event 是写入 `ak.component.agent.status.v1` 的 Control Move，authoring frontiers 只由 Event Envelope 顶层 `seal_basis` 表达；payload 不得携带第二套 producer 自报 frontier。Auth Server MUST 拒绝新 agent session grant；已签发 session token MUST 在独立于 session TTL、且 MUST ≤ 60 秒的 pause revocation freshness window（见 [`key-management.md` §3.6.1](./key-management.md)）内通过 introspection、status check、revocation list 或等价机制 fail closed。实现 MAY 选择同步 revocation 或每次资源访问强制 status 重查，但 MUST NOT 把该窗口放宽到 session 最大 TTL，也 MUST NOT 仅依赖自然过期继续接受 paused agent token。Pending action requests SHOULD 标 `awaiting_resume`。
- **Resume**(`ak.self.agent.command.resume.v1`):只检查current controller写权限、Agent非terminal、controller/accountability parent gate以及Event顶层seal_basis/current frontier与CAS；通过即可paused→active。key、session、capability、target Realm policy/membership、KeyPackage和MLS就绪是实际动作时独立AND gate，不得因缺少child authority拒绝resume。恢复不重发grant、不复活revoked key、leave membership或旧session；Sidecar desired/effective状态从current facts重算。
- **Deactivate**(`ak.self.agent.command.deactivate.v1`):terminal state。controller 请求只携带恰好一个 `ak.self.agent.deactivate` lifecycle Event；其 accepted Seal 形成 parent lifecycle write barrier，并机械使全部 child runtime key、session、pairing handle、capability grant、KeyPackage、presence 与未来 submission ineffective。客户端不得提交逐 key/grant revocation bundle，服务端也不得把 cleanup 成功当作接受 lifecycle Event 的前置。runtime endpoint、pending action、Sidecar desired access、membership/MLS removal 与 recovery-backup pruning MAY 异步幂等清理，但 terminal authority 不可因此恢复；远端、introspection 与 cache MUST 在 ≤60 秒 freshness 上界内 fail closed。历史 child Event 保留审计，显式 revoke 只用于 parent 非 terminal 时的定点撤销。
- **Controller lifecycle 传播**:Controller 进入 `deactivated` / `suspended` 时，其 accountable Agents 的 active sessions MUST 通过本节 revocation 链失效，后续 agent session grant MUST fail closed。Accountability grant 失效同样使 agent 进入 ineligible 状态。
- **Controller Realm membership 传播**：Agent 不能作为无主 effective member 留在 Collaboration Realm。controller 不再处于 Agent binding 所钉定的 exact join Event generation 时，所有对应 Agent 的 Event authoring、capability、delivery、KeyPackage 与 MLS active membership立即 fail closed；不等待 cleanup。canonical Agent member cell 只由实际 initiator签名的 `agent_membership_cascade` unit 改写：self leave 是完整原子 batch，第三方紧急 ban/remove 先原子落 terminal + durable exact-set intent，再补 complete-set cleanup。服务端不得合成 Agent leave，controller 重新加入也不自动恢复旧 Agent binding。
- **Pairing expiry**:关闭过期handle和未激活批准，清除open fields并重新派生readiness；不改变lifecycle、key、grant或历史。无current key时保留runtime_key_missing，不以历史授权row区分分支。
- **Runtime attach/replace**:active或paused Agent通过同一renew_pairing operation取得新handle，批准时从current exact authorization set派生attach/replace并签署唯一authorize Event。旧key在新Event经Seal生效前保持原约束；同一Event原子移除全部旧authorization dots，lifecycle/grants/principal/DM历史保留。新runtime必须用新raw key和endpoint完成MLS transition及允许的history恢复；保留历史对象不保证立即可解密。服务撤销成功与密码学排除是不同终点，≤60秒传播不是旧epoch secret被遗忘的保证。详见key-management §3.6.1。

**合法迁移表（normative）**：lifecycle 意图闭合枚举的合法 (from → to) 转换如下；表中未列出的转换 MUST 拒绝（`failed_precondition`，非法 Agent lifecycle 转换）。`deactivated` 是 terminal 状态（无出边）。Pairing 的完成/过期只改变 key/handle facts及派生 readiness，MUST NOT 被表达为 lifecycle 迁移；open pairing handle 是属性而非状态，且不与 pause / resume 互锁。

| from \ to | `active` | `paused` | `deactivated` |
| --- | --- | --- | --- |
| `active` | — | ✓（pause） | ✓（deactivate） |
| `paused` | ✓（resume，须重校验，见上） | — | ✓（deactivate） |
| `deactivated` | ✗ | ✗ | —（terminal） |

具体 wire 与 conformance 规则见 [`key-management.md` §3.6.1](./key-management.md)、[`../sync/service-http-binding.md` §2.4](../sync/service-http-binding.md) 与 [`../conformance/conformance-profiles.md` §18.1](../conformance/conformance-profiles.md)。

## 10. Admin and Support APIs

实现 SHOULD 提供：

- 查询当前账户状态。
- 列出设备和 session。
- 撤销 session。
- 发起 deactivation。
- 发起 export。
- 查询 support contact。
- 提交 appeal。

这些 API 必须使用高风险动作认证，例如 recent login、WebAuthn、recovery key 或管理员多方审批。

**认证新鲜度的归属（normative）**：与 §8.1 同一原则——需要 fresh 高风险动作认证的操作
MUST 由 Account Authority 直接受理，认证新鲜度由 Account Authority 本地判定。Principal
Server MUST NOT 依据 session grant introspection 或本地会话状态自行判定或近似认证新鲜度；
introspection 响应不投影 `auth_time` 或认证 proof kind 是有意的闭合设计，不得为绕过该闭合
而在 Station 侧重建新鲜度判定。
