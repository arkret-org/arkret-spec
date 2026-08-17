---
title: Account Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-08-11
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret 身份由稳定 principal `did_core_id` 表示，并由当前 `full_id` 提供 DID resolution；用户访问通常经过一个或多个服务账户、OAuth/OIDC session、device token 和 Principal Server / Events API。本文件定义这些层的锁定、暂停、注销、软登出、数据擦除和服务账号生命周期。

## 2. 分层

| 层 | 示例 | 生命周期控制者 |
| --- | --- | --- |
| Principal identity anchor | `did_core_id`（稳定）+ registration-time `full_id` evidence | 注册时 DID control proof；注册后不产生业务 authority |
| Account authority | `(principal_id, principal_server_id)`；同一服务内 create-once | Principal Server + accepted PCR device / recovery policy |
| Service account | `alice@example.com` 登录入口 | account service |
| Device session | session grant / grant-binding key | auth service |
| Event / private state | signed Event history / private account data | Events API + principal policy |
| Realm membership | `ak.member.state`（状态机定义见 [`../models/realm-and-space.md`](../models/realm-and-space.md)） | Realm policy/capability |

服务 account 被注销不等于 DID 消失。DID 被恢复、轮换、deactivate 或转手不改变已接受 PCR、
session 或业务关系；只有显式 current external claim、resolution successor 或启用的 DID-root recovery
消费 current DID state。

## 2.1 服务账号登录与找回

服务账号 MAY 使用用户名/密码、passkey、WebAuthn、OAuth/OIDC、企业 SSO 或类似集中认证服务的登录方式。它们只证明调用方通过了某个 account service 的认证，不能直接证明 DID principal 所有权。

登录成功后，account service / auth service MUST 将会话绑定到 principal `did_core_id` 与设备，例如签发短期 `ak.session.grant`、登记 device binding，或要求客户端提交 identity control proof。资源服务器随后验证 grant、device、capability、Realm policy 和撤销状态。`ak.session.grant` 是 Account Authority issuer-ledger credential，不是 Event：issuer 从 closed immutable `ak.session_grant.issuance.v1` preimage 派生 33-octet / 44-character suite-tagged full-digest token，签 JWT，并要求 JWT `jti` 逐字节等于该 typed ID。其 ID derivation、canonical JWK、nonce 与 verifier 规则见 [`key-management.md` §6](./key-management.md)。这个 ID 不是 Event ID，也不是 `ak:grant:` Capability GrantId；三者的 parser、存储索引与 API strong type MUST 分开。

### 2.1.1 Account-first onboarding

用户可以先完成邮箱、passkey、OIDC/SSO 或企业账号登录，而无需理解 DID。但未完成 principal binding 的 session 只能执行 registration/risk/device initialization，不能作为最终 actor 写 Realm、MLS、capability 或 federation state。

客户端必须在首个网络副作用前本地生成并 durable 保存 recovery/identity-root、device identity、HPKE、DPoP keys 与完整 onboarding draft。服务端不得生成或持有 identity root/device private key。PCR genesis accepted 后仍必须完成首个 Seal 与 genesis recovery policy，才能解除 `recovery_material_pending`；该门的作用范围是进入 E2EE Realm（创建/加入）之前。

### 2.1.2 Account handoff、PCR genesis 与首次 Standard grant（normative）

Account Authority 必须使用 holder-bound handoff；普通 OAuth token、OIDC `id_token`、refresh token 或 browser cookie 不能直接成为 Arkret registration authority。固定流程如下：

1. 客户端提交 OIDC code exchange proof 与 RFC 9449 DPoP；Account Authority 验 issuer/client/redirect/state/nonce/PKCE 并返回最多 1 hour 的 opaque `account_handoff_grant` 与 deployment-local `account_subject`。handoff 本身不是 SessionGrant、没有 refresh 语义，不能直接访问 `/_arkret/self/*`；其闭合权限集是 issue identity-binding challenge、issue DID-binding challenge、issue identity-abandonment challenge、abandon identity creation、register、issue session grant 与 issue recovery-completion grant。两个 identity-abandonment 成员在列，是因为 PCR 从未 accepted 时用户没有 principal，不可能有绑定 principal 的 session grant 来承载它们。对已绑定账号，pre-registration handoff 可以换取该账号 principal 的 Standard SessionGrant，因此 OIDC 凭据失陷会暴露服务端可见状态与 grant scope 内操作；但攻击者仍不能缺少 accepted device Event proof 而代表用户写 Event、取得 E2EE 明文或授权设备。
2. Account Authority 原子取得最多 15 minutes 的 `identity_creation_lease`，持久化 `(service_account,audience,lease_id,holder_jkt,fence,expires_at,reserved_principal_id?,reserved_operation_digest?,state)`；同一账号同一 audience 同时只有一个 live holder。handoff 取得与同 holder 续租都必须按 [`../conformance/scalability-constraints.md`](../conformance/scalability-constraints.md) §6.1 限速并经过风险检查；busy 响应除 `retry_after_ms` 外必须回显冲突 live lease 的 `expires_at`，供客户端显示确定等待上界，不得披露 holder key 或原始账号 id。
3. 客户端按已登记 adapter 生成并证明 registration anchor，连同 `FoundingDeviceDescriptor` 构造 ordered genesis unit；客户端 MUST 投影出 `principal_id=did_core_id`，并从 create Event 按 `retype(event_id)` 导出 PCR id。注册证据冻结 method-native `method_history_head`、`version_id`、control-key digest 与 adapter evidence：`did:webvh` 冻结 history entry，`did:web` 冻结 DNS/WebPKI 与 DID Document retrieval，`did:key` 冻结 deterministic expansion。客户端还必须生成独立的 `registration_did_evidence_draft`；其专用 control proof 以 `ak.registration-did-evidence-control-proof-v1` 签署 core/full、adapter version、history/version/key pins 与 `method_evidence_digest`，不得复用或转换 `identity_creation_control_proof`。`accepted_at` 在 draft 中禁止出现：Account Authority 只有在 registry 接受 exact DID operation 后才把 registry 返回的原始 acceptance time 加入完整 `registration_did_evidence`。客户端把 `{full_id,method_history_head,version_id}` 写入 genesis `initial_resolution`，并构造绑定同一 device 与 handoff DPoP key 的 `InitialSessionGrantIntent`。
4. challenge 与 `identity_creation_control_proof` 必须承诺 `account_subject`、`principal_id`、`full_id`、PCR id、DID operation digest、`did_version_id`、`log_head_digest`、`control_key_digest`、create payload digest、founding authorize payload digest、`initial_session_request_digest`、closed unit kinds、lease/fence、DPoP JKT、audience/origin/trust-domain 与最多 300 秒窗口。DID operation digest 是完整 typed `DidOperationSubmitRequestBody` 的 canonical digest；它不是仅对 method-native log entry 计算的 event digest，验证方必须从已接受的 inception wrapper 字段重构并复算前者，并独立确认 `project(full_id) == principal_id`。对 did:webvh，proof key MUST 是 `did_version_id` 所钉的那个 entry 的 **current active update key**（`parameters.updateKeys[0]`），且其 canonical multikey 的 SHA-256 MUST 等于承诺的 `control_key_digest`；不能从 DID Document 的 authentication / service fragment 选择，也不得采信请求自带的 key。account-first inception 时该 entry 就是 entry 0，因此本规则与既有行为一致；对已发布且已轮换的 DID，它锚在建号时刻的当前控制权而不是创世代次——后者可能早已 spent 且不可再签。

**身份锚、resolution 与签名者是三件事，MUST NOT 混用**：`principal_id` 回答“这个 PCR 属于哪一个稳定主体”；`initial_resolution.full_id` 与 `did_inception` ref 提供该主体建号时的可解析 DID 和 inception；`did_version_id` / `log_head_digest` / `control_key_digest` 三元组回答“建号时刻谁控制它”。验证方 MUST 分别校验，并通过 adapter 证明前两者投影一致；MUST NOT 因为 ref 指向 inception 就要求 inception key 签名。Event id 与 envelope digest 禁止进入 transcript。客户端在签名前 MUST 把 challenge 回显的 `account_subject`、`principal_id`、`full_id`、`operation_digest`、`pcr_realm_id`、三项 DID log pin、三个 payload digest、`initial_session_request_digest`、`genesis_unit_kinds`、lease/fence、`dpop_jkt`、`audience`、`origin`、`trust_domain`、issued/expiry window 与本地 frozen draft / handoff 逐字节比较；任一不符都必须 fail closed 且不得生成 root 签名。
5. `register` 携带 `full_id`、exact DID operation、`registration_did_evidence_draft`、root control proof、含 `initial_resolution` 的 `pcr_genesis_unit` 与 `initial_session`。Account Authority CAS 验证 holder/lease/fence/reservation/challenge，独立验证两个不同 proof、冻结 canonical request，再执行单调 saga：

```text
reserved -> did_published -> pcr_accepted -> account_bound -> completed
```

`identity_creation_lease.state` MUST 返回上述 Account Authority 持久 saga 的当前状态；初次取得 lease、尚未冻结 DID operation 时返回 `active`。客户端每次取得新 handoff 后 MUST 以该服务端状态重新计算 onboarding phase，MUST NOT 通过本地 checkpoint、Recovery Key、旧 challenge 或旧 callback 是否存在来推断服务端阶段。`reserved_identity` 在 `active` MUST 省略，在 `reserved` 及后续状态 MUST 存在；两者矛盾时客户端 MUST fail closed。

客户端随后只可检查当前服务端状态和所选合法目标所需的本地材料。材料必须验证其 account subject、lease/fence、reserved identity、purpose、challenge 与 expiry；不属于当前 flow、验证失败或当前状态不需要的材料 MUST 从活动 checkpoint 中删除。验证通过且已满足的步骤 MAY 跳过。任何非终态 reload、认证 callback、网络不确定结果或进程重启都 MUST 重新取得服务端状态并重复该 reconciliation，不得从旧页面步骤继续推进。

reconciliation 重算的是服务端 phase、合法目标与所需材料，不得改变同一次活动用户交互中已经验证的临时材料来源。特别地，首次创建页面仍在内存中持有其刚生成的 Recovery Key 时，服务端从 `active` 单调推进到 `reserved` / `did_published` 不得把该 Key 重新解释为“外部已有 Recovery Key”，也不得把首次确认界面切换成恢复界面；客户端 MUST 继续使用该内存材料完成当前目标。用户正确回输生成的 Recovery Key 后，客户端 MUST 在首个网络副作用前把继续该 reservation 所需的 recovery authority 写入平台安全存储，并 durable 等待成功；public checkpoint 只能保存 fingerprint/public key，不能保存明文词组或被解释成 secret possession。reload、callback 或进程重启时，客户端只有在安全存储材料经当前 `account_subject + audience + device` scope 及 server reservation 验证通过后，才可重新展示同一 Key 并回到“生成 Key 确认”步骤；没有该材料时才进入 `Existing Recovery Key` 输入步骤。服务器 reservation 与 public checkpoint 都不能证明用户已记住、导出或仍持有 Key，UI MUST NOT 作此声明。该材料来源只决定如何取得 recovery authority，MUST NOT 提升或回退服务端 phase。

只要 live handoff 的权威目标仍是 `complete_identity`，`active | reserved | did_published | pcr_accepted | account_bound` MUST 由同一条 handoff continuation flow 承载；本地 registration checkpoint 的存在不得改选另一套恢复状态机。经验证的 checkpoint 和 Recovery Key 只能使该 continuation flow 跳过已经满足的内部步骤：有匹配的安全存储 Key 时直接重新展示并要求确认同一 Key；没有时要求输入原 Key；不得因 checkpoint 缺失把 `pcr_accepted` / `account_bound` 误判为死路，也不得因 checkpoint 存在再次要求输入本设备已经验证持有的 Key。

**重算输入与结束方式（normative）**：每次重算恰好从五类事实开始：(1) 最新 `AccountOnboardingSnapshot` 的 account subject、binding/lease state 与 goal；(2) lease 中的 reservation 与 fence；(3) 经 account/lease/reservation 校验的 durable public checkpoint；(4) 当前进程或平台安全存储中经验证的 Recovery Key availability，使用封闭状态 `unavailable | generated_pending_confirmation | recovered_pending_confirmation | generated_locally_validated_durable | existing_validated_durable` 表达；(5) handoff 的 holder binding、expiry 与服务端 freshness 决定。`generated_locally_validated_durable` 只表示本设备完成词组匹配并安全持久化，不表示用户已经记住、导出或完成外部备份。public checkpoint 不得冒充第 (4) 类事实，客户端也不得用 `serde_json::Value` 或自由字符串扩展这些闭合状态。

本流程只有两个 protocol terminal outcome：(a) `binding=bound` / lease `completed` 且首个 session、device 与 recovery-material gate 均完成，此时进入 Ready；(b) 用户显式完成 `abandon_provisional_identity`，旧 reservation 进入不可继续的 tombstone，随后必须以新 handoff 开始一个新流程。handoff/lease 过期、busy、网络结果不确定、命令失败、缺少 Recovery Key 和本地/服务器矛盾都不是成功终态；它们分别进入重新认证、等待后重算、刷新 snapshot、补充原 Key/显式放弃或 fail-closed 修复分支。任何分支恢复后都从上述五类事实重新计算，不得从旧 UI step 继续。

持有 live handoff 的客户端 MUST 通过 `ak.gate.account.read.onboarding` 取得封闭的 `AccountOnboardingSnapshot`。其 `goal` 只能是 `complete_identity`，或同时携带服务端 durable challenge 与 `fresh_authentication_required` 的 `abandon_provisional_identity`；后者只在用户已显式发起放弃后出现。客户端 MUST 采用该服务端 freshness 判定，不得比较本地 bearer、grant digest 或 callback 次数来猜测“是否已经重新认证”。不存在 live abandonment challenge 时服务端 MUST 投影 `complete_identity`，客户端不得从旧本地 challenge 恢复放弃目标。

6. Account Authority 发布 exact client-signed DID operation，使用 registry 返回且 exact replay 稳定的 `accepted_at` 完成 `registration_did_evidence`，并通过 `ak.peer.principal_genesis.command.submit` 原样 relay exact DID operation、完整 frozen evidence、genesis unit 与 root-signed pins。S2S signature 只认证 transport/correlation；Principal Server 必须从 relay 内的 method-native operation 独立验证 adapter projection、两个 root proof、method evidence、DID log pins、root/device Event proofs、descriptor/payload commitments、event-derived PCR id、empty frontier、账号维度 create-once 与 atomicity；MUST NOT 查询 current resolver、数据库最新 DID row 或当前 method head补材料。该 pre-grant genesis unit 不携带、也不得被持久层要求预签发的 Authorization Lease 或 Control Proposal Ack；Account Authority 的 S2S 身份只绑定账号协调与传输来源，不能成为 Event authority。
7. Principal Server 返回 durable batch receipt，`scope.kind="pcr_genesis_unit"`，且 `scope.registration_evidence_digest` MUST 等于完整 `registration_did_evidence` 的 RFC 8785 JCS SHA-256。Account Authority 必须验证 receipt 的 principal/PCR、`initial_resolution`、三项 DID log pin、registration evidence digest、device/key/HPKE、两条 Event digest、accepted frontier/Seal basis 与 frozen registration 逐字一致，才可提交一账号一 principal binding。原子接受同时初始化 `ak.component.identity.resolution.v1`、PCR-local monotonic `current_device_generation_ref := 1` 与 `device_generation_status := active`；generation ref 不等于也不派生自 DID `versionId`，且这些投影不得在 unit 全部验证通过之前可见。
8. Account Authority 随后从 issuer ledger 签发 `credential_class="standard"` grant。`InitialSessionGrantIntent.device_id` 必须等于 founding descriptor；public JWK thumbprint必须等于 handoff/control proof DPoP JKT；audience/scope必须在 handoff ceiling 内。`pcr_accepted` 前不得签发 principal grant；account binding commit 后签发超时只能 exact replay issuer ledger，不能重建 PCR。

整个 register 以 `(service_account,principal_id,operation_digest)` 与 idempotency key 做 exact replay：相同 bytes 返回同一 saga/receipt/grant outcome；同 key 不同 bytes、账号/principal 冲突或 genesis digest 变化必须零写入失败。一个 Account Authority 下一个 service account 只绑定一个 active principal，一个 principal 也只绑定一个 active account。

`AccountRegisterOutcome.binding_receipt` 必须由 Account Authority 签发并闭合绑定 `account_subject`、`principal_id`、`full_id`、method head/version、lease/fence 与 operation digest。注册成功后客户端 MUST 按 adapter 重放并逐字比较 frozen registration evidence：webvh 比较 history entry，web 比较注册时 retrieval/bootstrap evidence，key 比较 deterministic expansion；任何冲突都 fail closed。后续 handoff 返回的 `principal_id` 若不等于本地 frozen/derived `did_core_id`，必须 `account_binding_principal_mismatch`，不得覆盖本地锚。

若设备在 PCR accepted 前物理损毁，新 holder 在旧 lease 过期后可递增 fence、继承 reservation，并用同一 registration control 对新 challenge 与 founding unit 重签。PCR create-once 使并发 unit 只有一个 winner；若旧 unit 已先 accepted，新设备必须走已接受 recovery policy，不能再次 genesis。若 PCR 未 accepted 且 registration control 也丢失，可显式放弃 provisional identity 并新建 DID/PCR。放弃必须是显式用户动作，保留 orphan-anchor tombstone/audit reservation，且不得把已放弃 checkpoint 继续暴露为账号可读状态。

**执行放弃的 wire 形态（normative）**：显式放弃由封闭的两步 operation 承载，与既有的 `issue_identity_binding_challenge` + `register` 对位：

1. `ak.gate.account.command.issue_identity_abandonment_challenge`（`POST /_arkret/gate/account/identity-abandonment-challenges`）取一份 challenge。它只签发 challenge，本身不放弃任何东西。
2. `ak.gate.account.command.abandon_identity_creation`（`POST /_arkret/gate/account/identity-abandonments`）出示该 challenge 完成放弃。

两者的凭据都只能是 account handoff grant——PCR 从未 accepted，用户没有 principal，也就不存在绑定 principal 的 `ak.session.grant`——因此它们已加入本节第 1 步 handoff 的封闭权限集。challenge 单次使用、≤300 秒、保存在 shared durable state，并钉死 `account_subject`、holder `cnf.jkt`、本次要放弃的 `principal_id` 与 `did_version_id`、当前 lease id 与 fence、必须向用户展示的封闭后果集合与时窗；这正是"MUST 是显式用户动作"的落点——自动流程不会先取 challenge。确认调用 MUST 出示一份新鲜 handoff grant，MUST NOT 复用签发 challenge 时那份。消费 challenge、写 orphan anchor tombstone/audit reservation、抑制 checkpoint 与释放 lease 是一个事务，任一步失败零写入；同 `request_id` 重放返回同一终态且不产生第二条 tombstone。challenge 与确认之间 PCR 被 accepted 时，确认 MUST 以 `identity_creation_already_accepted` 失败且 MUST NOT 执行放弃。完整规则见 [`key-management.md` §5.0.2](./key-management.md)。

**未完成 reservation 的回收时机属实现策略，本规范只作建议、不强制**：实现 SHOULD 为未完成的 reservation 设定有界生命周期并到期丢弃；`identity_creation_lease` 的 15 分钟 TTL 已经限定了 holder 独占窗口，回收窗口取同量级（例如半小时）是合理默认。具体时长、是否需要用户显式确认、以及与风控冷却期如何叠加，由部署自行决定；本规范不规定，也不要求实现具备自动回收能力。PCR 已 accepted 且无可满足 recovery proof 时必须 fail closed。

账号认证凭据与 principal Recovery Key 是两套正交权力：重置账号密码不能轮换 DID、授权设备或解密 E2EE；Recovery Key 也不能重置账号密码。

### 2.1.2a 绑定已发布 DID（normative）

`account_register_request_body` 的 `proof` 分支用于把一个**已经发布**的 `full_id` 所投影的 `did_core_id` 绑定到已认证的服务账号，
与 `identity_creation` 分支互斥。它不创建 DID、不保留 principal、不执行 PCR genesis。

**要求 DID 控制权证明的适用范围**：对 human principal，控制权证明只在**首次断言“这个新账号/PCR
绑定这个 DID”**、当前外部身份 claim、resolution method successor，以及 accepted recovery policy 明确
启用的 DID-root factor 上要求，不是每请求。
在已成立的绑定**之下**进行的操作不在此列——PCR 内 profile 由 device 签名的 Realm Event 承载，
账号侧属性（邮箱、密码、恢复联系人）由账号认证把关；二者都 MUST NOT 要求 DID 控制权证明。

1. 客户端调用 `ak.gate.account.command.issue_did_binding_challenge`，提交 `principal_id` 与 `full_id`。
   Account Authority MUST 自行按 [`did-usage-and-verification.md` §5.4](./did-usage-and-verification.md)
   的 `high` tier 通过已登记 adapter 解析该 DID（同步刷新或 fail closed），先确认
   `project(full_id) == principal_id`，再从解析出的 current entry 推导 `did_version_id`、
   `log_head_digest` 与 `control_key_digest`。**MUST NOT 接受调用方自报的 DID history。**
2. **不自托管该 DID 的部署 MUST 另行要求 method-native witness / freshness 证据。**
   接受 registry 与 Principal Server 同源是对**自有 DID** 的裁决，**不外延到第三方 DID**：
   自有 DID 的断言是"这是本服务的一个用户"，外部 DID 的断言是"这个账号就是某第三方身份"，
   后者会被导出给依赖方，是有外部爆炸半径的冒充面。
3. 客户端把 challenge 回显字段**逐字节比对**本地期望值后，才用 `did_version_id` 所钉 entry 的
   **current active update key** 签 `account_registration_control_proof`；任一不符 MUST fail closed
   且不得签名。验证方 MUST 从已验证 DID history 选取该 key，MUST NOT 采信请求自带的 key
   或 DID Document 的 verificationMethod。
4. **Soland MUST 独立解析 `full_id`、验证 projection 并自行重验该证明**，不得采信 Account Authority 的结论；
   S2S 签名只认证传输来源。
5. 绑定成立后，Principal Server MUST 把已验证的 `{principal_id,full_id,method_history_head,version_id}`
   作为 PCR genesis `initial_resolution` 持久化，并从 resolution cell 生成 Profile current projection。
   本地账号记录仍是账号运营真相；日常操作使用 `principal_id`，不因普通请求回源 DID host。
6. **绑定的时态**：注册成功后，上述 proof 与 method evidence 冻结为 registration-time historical
   evidence。账号注销/擦除、session、device、capability、MLS 与普通 PCR 操作 MUST NOT 刷新 DID。
   current DID mismatch/deactivation 只把独立 external claim 标为 `stale`/`invalid`，MUST NOT 限制、
   解绑、冻结或转移账号/PCR。

PCR 的作用域是「某个 principal `did_core_id` 在**当前 Principal Server** 上的账号」：同一 `did_core_id` 在不同 Principal Server 上
是完全独立、互不相关、不可迁移的账号与 PCR。全网模型是「特定 Principal Server 上的一个 principal `did_core_id` ↔
一个 arkret 账号」，各 Principal Server 自行治理其系统下的账号。

账号的唯一外部 authority key 是 `(principal_id, principal_server_id)`。同一 `principal_id` 可在不同 Principal Server 上形成独立账号；同一 Principal Server 对同一 pair MUST 终身 create-once，并在注销或 hard erasure 后保留 uniqueness tombstone，禁止第二条 PCR lineage。device、recovery、session、resolution、KeyPackage、secret storage 与 account status 可按本地 PCR lineage 分区，但 PCR id、genesis receipt 与 frontier 不得进入 membership、grant、Contact、Event 或 cache/query 的外部 identity。业务换服务形成新 pair，不存在 cross-PCR link/merge。

注册后的 resolution 变更 MUST 由该 PCR 中的 `ak.identity.resolution.update` 提交，不能直接覆写 profile 或账号表。Event 以 previous Event ref / previous history head 做 CAS，reducer 更新 `ak.component.identity.resolution.v1`；Profile 只公开其 current projection。current holder MAY 请求 Event、receipt 与 accepted Seal 组成的选择性历史 evidence，并用注册 reducer 重放 current projection，不另造 resolution 专用 proof。其他 Principal Server 不要求持久保存该用户的 resolution；敏感操作发生时必须重新取得最新 evidence 并独立验证，短 TTL cache 只能优化读取，不能成为授权依据。

### 2.1.3 SessionGrant 不确定结果与身份边界

SessionGrant issue / refresh 的 exact replay 规则以 [`key-management.md` §6.2](./key-management.md) 为准。
replay 命中 expired outcome 时返回 `session_grant_replay_expired`；命中 revoked / superseded outcome 时返回
`session_grant_replay_terminal`；记录已超过保留期、issuer 无法证明旧 attempt 是否提交时返回
`session_grant_replay_indeterminate`。三者都不得返回成功或在旧 request identity 下补发 grant。客户端
必须取得新的 one-shot proof 与 request identity 后重新认证。

account-first onboarding 在上述终态恢复时 MUST 复用 §2.1.2 的 identity-creation lease fence 与
`reserved_principal_id` / `reserved_operation_digest` / holder-authenticated DID-operation checkpoint：新 holder 在租约
到期并 fence 后继续同一身份创建，不得重做已经 accepted 的 DID operation，也不得重新生成 Recovery
Key。普通登录则回到认证入口。

SessionGrant ID、refresh chain、local auth session 与 cache 的唯一真相源是 issuer ledger。任何不符合
[`key-management.md` §6.1](./key-management.md) ID 构造和 ledger 绑定的 session credential MUST 失效并
要求客户端重新登录；部署不得修改 JWT `jti`、把 Event/cell 重解释为 issuer record，或把无匹配
issuer record 的 row 注入 ledger。失效处理只能删除 session credential 与绑定缓存，MUST 保留
principal 私钥、Recovery Key、DID/PCR/MLS 与 secret-storage 数据；这是 auth session fence，不是
principal identity migration。

当 service account 已绑定到某个 `account authority pair` 时，账号访问可由 account auth、passkey、
已授权 device 或 accepted PCR recovery policy 分别恢复。只有账号 recovery policy 显式登记 DID-root
factor 时，current DID control proof 才可作为附加分支；该分支必须指向同一 account authority pair，不能因 `principal_id` 相同选择另一服务账号。

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
| `soft_logged_out` | auth service / 用户 logout | 已撤销 | 可在 fresh account/passkey 或 PCR device/recovery proof 下 refresh；不要求 current DID | 保留 | 保留 | 保留 | §4 |
| `locked` | 安全风险检测 | 已撤销 | SHOULD 拒绝 | 保留 | 保留 | 保留 | §5 |
| `suspended` | 治理 / 合规 | 拒新发 | 拒新发 | 保留 | 保留 | 保留 | §6 |
| `deactivated` | 用户 / 管理员关账 | 已撤销 | 已撤销 | 标记 revoked | 客户端可清除 | 保留 | §7 |
| `erasure_pending` | 用户擦除请求 / GDPR | 已撤销 | 已撤销 | 已撤销 | 必删 | 按 redaction policy 最小化 | §8 |

`reason_code` 表达**为什么**进入该状态（如 `abuse_review` / `gdpr_request` / `password_compromise`）；状态本身表达**当前所处阶段的协议行为契约**。两者不可替代。

**认证错误码（normative）**：Account status 导致 session grant 或 grant-binding proof 失效时，服务端 MUST 返回与 current status 匹配的专用错误码，而不是退化成通用 `unauthenticated` / `capability_denied`。已签发 session 访问受保护 `/_arkret/self/*` 资源时：`soft_logged_out` 返回 `401 soft_logged_out`；`locked` 返回 `401 account_locked`；`deactivated` 返回 `401 account_deactivated`；`erasure_pending` 返回 `401 account_erased`。新 session grant 签发、session refresh 或登录完成阶段遇到当前 status 时：`locked` SHOULD 返回 `403 account_locked`；`suspended` MUST 返回 `403 account_suspended`；`deactivated` SHOULD 返回 `403 account_deactivated`；`erasure_pending` MUST 返回 `401 account_erased`。这些 code 的机器真源是 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)；`account_locked` / `account_deactivated` 的入口差异由同行 `http_status_by_context` 机读化，`http_status` 是通用默认值。HTTP status 的差异只表达“已持有 grant 失效”与“新 grant 被 policy 拒发”的入口差异，不改变 account status 语义。

**合法状态转换（normative）**：Account Authority issuer ledger MUST 按下表判定从 current record 到 successor record 的状态转换是否合法；非法转换 MUST `failed_precondition`，`reason_code="account_status_transition_invalid"`，且 ledger/account row/audit/outbox 均零写入：

| from \ to | `active` | `soft_logged_out` | `locked` | `suspended` | `deactivated` | `erasure_pending` |
| --- | --- | --- | --- | --- | --- | --- |
| `active` | —（同态重放） | ✓ | ✓ | ✓ | ✓ | ✓ |
| `soft_logged_out` | ✓（§4，须 fresh identity control proof） | — | ✓ | ✓ | ✓ | ✓ |
| `locked` | ✓ | ✓ | — | ✓ | ✓ | ✓ |
| `suspended` | ✓（appeal 解除，须 Account Authority 当前策略授权） | ✓ | ✓ | — | ✓ | ✓ |
| `deactivated` | ✗（见下"重激活"） | ✗ | ✗ | ✗ | — | ✓ |
| `erasure_pending` | ✗ | ✗ | ✗ | ✗ | ✗ | —（terminal） |

- **降低严格度**（任一 `to` 严格度低于 `from`，如 `suspended → active`、`locked → soft_logged_out`）必须由 Account Authority 在 current-head CAS transaction 内验证该转换对应的 fresh identity-control、appeal 或管理员授权。授权证明进入本地审计记录，不进入 portable `AccountStatusRecord`，不得由 receiver 二次裁决。
- **`erasure_pending` 为 terminal**（规则 3）：其唯一出边为空，任何转出 MUST 拒绝 `erasure_pending_is_terminal`。
- **`deactivated` 重激活**（normative）：v1 **不**允许同一 `account_id` 的 `deactivated → active` 等任意降严格度转换。§7.1 的 deactivation fanout 对绑定到该 account 的 device、KeyPackage、session、push 与 to-device 资源不可逆；需要恢复访问的用户 MUST 创建新的 service account（新 `account_id`）并走完整 onboarding，可继续绑定同一 principal `did_core_id`，但不得复活旧 account 或旧资源。`deactivated` 的唯一合法出边是 `erasure_pending`。实现 MUST NOT 签发声称把该 `account_id` 的 `deactivated` 降级回较低严格度状态的 successor record（`account_status_transition_invalid`）。

状态真相是 Account Authority issuer ledger 中的 immutable signed record：

```json
{
  "schema": "ak.schema.account_status_record.v1",
  "account_status_record_id": "ak:account_status_record:Aaqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq",
  "account_authority_id": "ak:did_core:webvh:zGtABZixoZZ3m4cFx3E65LCmg",
  "account_id": "acct_123",
  "principal_authority": {
    "principal_id": "ak:did_core:webvh:z6mkfixture",
    "principal_server_id": "ak:did_core:webvh:zPrincipalServer"
  },
  "principal_control_realm_id": "ak:realm:AZCGyNJicm4u8jUY2OGd52Dj8JvlbxtGx3rDYQWAMPGe",
  "binding_version": 1,
  "status_seq": 7,
  "previous_account_status_record_id": "ak:account_status_record:Abbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "status": "suspended",
  "reason_code": "abuse_review",
  "effective_at": "2026-04-26T00:00:00.000Z",
  "issued_at": "2026-04-26T00:00:00.000Z",
  "verification_method": "did:webvh:zGtABZixoZZ3m4cFx3E65LCmg:auth.example#account-status-key",
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:webvh:zGtABZixoZZ3m4cFx3E65LCmg:auth.example#account-status-key",
    "payload_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "created_at": "2026-04-26T00:00:00.000Z",
    "jws": "a..b"
  }
}
```

`AccountStatusRecord` 的 signer MUST 是对该 `account_id` 具有权威性的 Account Authority。holder 自助请求、appeal、管理员、风控服务或 Principal Server 只能提交 authenticated transition command；它们不得直接签发 portable record。`verification_method`、proof controller 与 `account_authority_id` 必须解析到同一 Account Authority，且 key 在 `issued_at` 对应的历史窗口内 active。record 的 account/principal/binding tuple 必须逐字匹配 Account Authority 本地已接受 binding。

### 3.1 Account Authority issuer ledger 与复制载体（normative）

Account lifecycle 不属于 Principal Control Realm finality domain。`AccountStatusRecord` 不是 Event，不进入 Realm timeline、actor frontier、Seal、CBA、Control Proposal、pending Control index 或 lattice reducer。`principal_control_realm_id` 仅是已验证 account binding coordinate；holder device 或 PCR notary 对 Account Authority 的 deny transition 没有签名或最终否决权。

Account Authority 的本地 issuer ledger 是该 `account_id` 的唯一 lifecycle 真相源：

1. 首次 account binding commit MUST 在同一数据库事务创建 `status_seq=1,status=active` 的 genesis record；它没有 `previous_account_status_record_id`，不查询 Principal Server frontier，也不等待 holder/Seal。
2. successor MUST 对 `(account_authority_id,account_id)` current head 做 CAS，且 `status_seq=current+1`、`previous_account_status_record_id=current.account_status_record_id`。同 request identity + 同 canonical intent exact replay 返回首次 bytes；异 intent 返回 `duplicate_conflict` 且零写入。
3. account row、immutable record、transition audit 与传播 outbox MUST 原子提交。record identity 是 `0x01 || SHA-256(JCS(closed unsigned core))` 的 canonical Base64URL typed token；unsigned core 是除 `record_id` 与 `proof` 外的全部 record 字段。
4. `proof` context 固定为 `ak.account-status-record-proof-v1`；proof payload digest 覆盖同一 unsigned core，`verification_method` 必须与 proof 内字段逐字相同并受 `account_authority_id` 控制。
5. `binding_version` 只能随已接受 account binding 单调推进；同 version 不同 principal authority/PCR tuple 是 fork，较低 version 是 rollback。Account Authority 不得在 binding 尚未权威提交时签 record。

Account Authority 向 Principal Server 复制状态的唯一写 operation 是 `ak.peer.account_status.command.submit`（`POST /_arkret/peer/account-status`）。request 只携 exact signed record；下游 fanout MAY 附带此前 receiver 的 `account_status_receipts[]`，但不得重建、重签或改变 record bytes。

- receiver MUST 验证 RFC 9421 transport、record id/digest/proof、Account Authority 历史 key、exact account/principal/binding tuple，并以 `(account_authority_id,account_id)` 持久化单调 replica。`seq=current+1` 且 predecessor 精确相等才可 advance；same seq + same id 是 `duplicate`；lower seq 返回 `failed_precondition` + `account_status_record_stale`；same seq + different id 或 next seq predecessor mismatch 返回 `failed_precondition` + `account_status_record_fork` 并停止该 record 的自动重试/补链、进入 quarantine/operator alert；低于 durable floor 的 binding version 返回 `failed_precondition` + `account_status_binding_rollback`。这三类均零写入且对 exact record 不可重试。只有 higher seq gap 返回 `dependency_missing` 与 exact `required_status_seq` 并触发 bounded resolve；`peer_stale` 保留 federation frontier quarantine 原义，不表示 lower account-status sequence。
- 每份 `AccountStatusReceipt` 闭合绑定 `receipt_id`、account-status record id/digest、Account Authority、account、status_seq、receiver 与 accepted_at；proof context 固定为 `ak.account-status-replication-receipt-proof-v1`。它只证明该 receiver 已 durable replicated exact record，不授予签发 authority。
- `Idempotency-Key` 必填并进入 HTTP Message Signature transcript。Scope 是 `(Source-Service-ID,Destination-Service-ID,Idempotency-Key)`；同 key 不同 canonical body MUST `duplicate_conflict`。`accepted | duplicate` 是该 receiver 的 terminal ack；本协议不存在 `pending_seal`。
- HTTP 必须使用 RFC 9421 Message Signature，覆盖 method、target URI、authority、`Content-Digest`、Source/Destination service DID、Source/Destination trust domain 与 `Idempotency-Key`。Outer signature 只认证 transport caller，不替代 Account Authority record proof。
- receiver 遇 gap 或需要 freshness observation 时使用 `ak.peer.account_status.read.resolve`（`POST /_arkret/peer/account-status/resolve`）向 Account Authority 取得最多 128 条从 `from_status_seq` 开始的原始连续 records。响应按 `status_seq` 升序；`has_more=true` 时给出 `next_status_seq`。未知、无关系或无权 caller 必须在读取 ledger 前以 operation 注册的 non-enumerating outcome 拒绝。

首个接收 Principal Server 从自身已持久化的 account session/device/KeyPackage/to-device/push-route、principal locator 与 Realm delivery-binding 状态确定**实际受影响 Principal Server 集合**，建立有界 durable outbox，并对每个目标复用上述 operation 的 receipted fanout 分支。集合只包含已经持有或即将持有该 account/principal 状态的服务；不得把 `account_id` 广播给无关 federation peer。每个目标按 `(account_authority_id,account_id,destination_service_id,record_id)` 去重；ack 后移出 outbox，失败按 bounded exponential backoff 重试。Outbox 必须有按 account/record/target 的唯一键、每 account 最大目标数 256、每目标最大一条未完成状态更新；不得跳过 predecessor、`deactivated` 或 `erasure_pending` 屏障，目标缺 gap 时先 resolve/补齐再提交后继。

上述 genesis/CAS、record identity/proof、gap/stale/duplicate/fork、幂等冲突与 fanout incomplete/complete 转换由 conformance vector `ak.vector.account_status.issuer_ledger.v1` 闭合。

Current account status 是 ledger current head 的 `status`。该 ledger 是 Account Authority 单写者的 strict hash chain，不存在并发 Event head、severity winner 或 PCR reducer。`account_id` 是 lifecycle key；同一 principal 绑定的其它 `account_id` 独立求值。

`AccountStatusRecord.expires_at` 仅是管理端与 UI 的复核/续期提示，不会在到时自动解除 `locked`、`suspended` 或其它状态。解除或改变状态仍 MUST 由 Account Authority 提交 successor record；receiver MUST NOT 根据本地墙钟合成状态。

1. 所有授权 gate MUST 读取本地 authoritative head（Account Authority）或已验证 monotonic replica（其它服务）；freshness 不足时向 Account Authority resolve，不能回调 holder device。
2. 降低严格度只由 Account Authority current-head transaction 执行，receiver 不接受绕过 predecessor 的恢复 record。
3. **`erasure_pending` 是 terminal 状态（normative，不可逆）**：任何 successor 均以 `erasure_pending_is_terminal` 拒绝。
4. 普通读面返回 `current_status`、`current_status_record_id` 与 `current_status_seq`；`reason_code`、`reason`、`effective_at` 来自同一 current record，不存在 producer-biased winner。

**Deactivation 进度 flag（normative）**：`status` 是封闭 6 值枚举（不含下列 token）。`deactivation_partial`（§7.1）与 `deactivation_federation_incomplete`（§7 末）**不是** `status` 值，而是 `deactivated` 状态下叠加的**独立服务侧 flag**，表达 deactivation fanout 的完成进度：

- `deactivation_partial`：boolean，默认 `false`。当某条本地 fanout（session/device/applet/KeyPackage/push/to-device）因网络或服务不可达失败、服务端仍在重试时为 `true`。`status` 仍为 `deactivated`。
- `deactivation_federation_incomplete`：boolean，默认 `false`。当该 principal 曾在其它 Principal Server 持有状态、源 Principal Server 未在 `deactivation_propagation_window_ms` 内得到 peer ack 时为 `true`，并触发 §7 末列出的写入暂停。`status` 仍为 `deactivated`。

二者均为服务侧投影 flag，与封闭 6 值 `status` 正交，MUST NOT 作为 `status` 取值出现在 wire 上；客户端 UI 据此区分"停用进行中 / 已完成"。

## 4. Soft Logout

`soft_logged_out` 表示当前 session grant 不再可用，但本地加密数据和 device trust 可保留。客户端 SHOULD：

- 停止 sync。
- 清除当前 session credential。
- 保留 device keys 和 secret storage 本地密钥，除非用户选择清除。
- 使用 session grant refresh、OIDC、re-auth、account auth、accepted device 或 PCR recovery policy 恢复；只有被选 authority 分支所需的 proof 必填。

服务端返回 `401 soft_logged_out` 时 MUST NOT 要求客户端删除本地 E2EE 密钥。

`soft_logged_out -> active` 的恢复 MUST 绑定所选 authority branch：授权 device、account auth key、
passkey 或 accepted PCR recovery policy 对一次性 challenge 签名，并覆盖 `principal_id`、`principal_server_id`、`device_id?`、
audience、request digest、challenge 与时窗。device 分支必须使用该 PCR current frontier；account/passkey
分支只能恢复服务账号/session，不能授权 PCR device 或 E2EE secret。未显式启用 DID-root factor时，
服务端 MUST NOT 取得 latest resolution 或返回 `did_proof_required`。

**豁免判定的 frontier 新鲜度（normative，fail-closed）**：上述“无任何未撤销 device record”判定 MUST 基于 fresh PCR control-stream frontier。frontier stale/unknown 时保守要求 `device_id`，不得把暂时读不到记录解释为无设备。DID resolver degraded 不影响 device/account/passkey/PCR-policy 分支；只有 accepted policy 实际选择 DID-root factor 时才按 [`identity-did.md` §3.4](./identity-did.md) fail closed。`issued_at` 与 `expires_at` 必填，`expires_at - issued_at` MUST 不超过 300 秒；缺少所选 authority branch proof 返回对应 account/PCR error，未选择 DID-root factor 时 MUST NOT 返回 `did_proof_required`。

### 4.1 显式登出（hard logout）与跨服务吊销编排

`soft_logged_out` 是当前 session grant 失效但凭证可恢复的软状态；用户主动「登出」是 **hard logout**——它 MUST 在所有持有该会话凭证的权威处终结会话，而非仅清本地。客户端可见的登出入口是 Principal describe 发布的 Account Authority；Account Authority 内部协调两个权威的状态:

- **Auth Server(认证服务)**:`browser_session`(登录认证上下文)+ 它签发的 `ak.session.grant` 轮换链(及其 `cnf.jkt` 设备持有绑定，见 [`crypto-media/device-lifecycle.md` §3.2](../crypto-media/device-lifecycle.md))。
- **Principal Server(资源服务)**:本地 account session 记录、设备会话记录、对该 grant 的 session-grant 内省缓存(TTL ≤120s)、待投递 to-device 队列。客户端可见登录凭据仍是 `ak.session.grant`，客户端以 `Bearer <ak.session.grant>` + `DPoP` 直接访问 `/_arkret/self/*`(见 [`../sync/api-conventions.md` §3.3](../sync/api-conventions.md));Principal Server **不**为客户端铸独立本地 bearer，**不**暴露第二个客户端可见的 Principal 本地凭据签发 endpoint。

**编排(normative)**:hard logout 由 Account Authority 编排。客户端 MUST 从 `ServiceDescribe.auth_metadata.account_authority.gate_account_base` 派生并调用:

```text
POST /_arkret/gate/account/logout
```

该请求 MUST 使用 `Authorization: Bearer <ak.session.grant>` 出示当前 grant，并带 `DPoP` proof；DPoP `ath` MUST 绑定该 grant，`htu` MUST 绑定由 `gate_account_base` 派生出的 `/logout` URL，使 Account Authority 能定位要终结的 grant chain 与 principal device session。客户端 MUST NOT 分别向 Auth Server 与 Principal Server 两个 origin 发起登出；部署内部的分权威调用是 Account Authority 的实现细节。普通客户端可见的 logout endpoint **只有** `POST /_arkret/gate/account/logout`。

1. **客户端** MUST：停止 sync、清除本地 session credential / `session_grant` / OIDC 凭证；hard logout SHOULD 额外清除本设备的 grant-binding(DPoP)私钥，使下次登录轮换 `cnf.jkt`(软恢复路径 MUST 保留该 key 以便 refresh)。
2. **Account Authority → Auth-side** MUST 登出当前 grant 所属的 Auth-side session / `browser_session`，在同一 issuer ledger 中幂等撤销该链的 active grant 并终结轮换链。若 Auth-side 不在同进程，Account Authority MUST 调用标准 S2S 子操作 `POST /_arkret/gate/account/auth-sessions/logout`(`ak.gate.account.command.logout_auth_session`)；该调用 MUST 使用 Account Authority → Auth Server 的部署内 S2S bearer（同 `session_grant_introspection_bearer` 认证族），MUST NOT 复用客户端为高层 `/logout` URL 铸造的 DPoP proof。此后 (i) 凭同一 `cnf.jkt` grant-binding proof 调 `refresh` MUST 被拒(`session_logged_out`)，整条轮换链不可再续；(ii) 该 Auth-side session 下任何 grant 的 introspection MUST 从同一 ledger 返回 inactive(即 grant-binding key 不能在登出后重建或维持会话)。该步骤不得发布 SessionGrant state Event。
3. **Account Authority → Principal-side** MUST：作废该 grant 的本地 session-grant 内省缓存（下次内省即得 `active=false`）、吊销 / 标记该 principal 本地 account session 与**本地设备会话记录**(使后续以该设备签名的 device-scoped 操作在本 Principal Server fail closed)+ drop 该设备的待投递 to-device 消息，并移除该设备作用域内的 push registration。因 Principal Server 不为客户端铸独立本地 bearer（会话凭据即 grant 本身，见上），此处无单独的本地 bearer 可撤——作废内省缓存 + 撤设备会话记录即足以使该设备后续 `/_arkret/self/*` 请求 fail closed。此操作终结该设备在本 Principal Server 的本地会话状态，但 **不** 创建 AccountStatusRecord、不发 `ak.device.revoke` 协议事件、不擦除 durable device authorization 历史(用户重新登录即可在本设备恢复)。注意它与 `ak.gate.account.command.revoke_session`(仅撤 session grant、不触设备会话记录，用于"撤某个会话但保留设备")是不同操作。

`POST /_arkret/gate/account/auth-sessions/logout` 是部署内部 S2S 子操作，不是客户端 account flow。该子操作 MUST 幂等：同一 Auth-side session / grant 已登出、已吊销、未知或已被剪枝时，Auth Server 仍 MUST 返回成功并把链视为已终结；鉴权失败、请求体不合法、或 Auth Server 无法确认完成时才返回错误。普通客户端、inkson、浏览器 UI 与移动客户端 **MUST NOT** 调用或自行派生该路径；即使高层 `/logout` 失败，客户端也只能重试 `ak.gate.account.command.logout`。客户端和服务实现 **MUST NOT** 依赖任何实现私有 / 产品私有(例如 `/_<impl>/*`)路由完成登出。

**登出耐久性(normative)**：hard logout 的本地清除(步骤 1)与 Account Authority 服务端编排(步骤 2、3)不是原子的——客户端在清本地凭证后、Account Authority 返回前可能崩溃、关页或离线。为防止「本地已登出但服务端轮换链仍存活」的窗口，客户端 **SHOULD** 在执行本地清除**之前**把登出意图(至少：Account Authority `/logout` endpoint、grant JWT、用于铸 grant-binding(DPoP)proof 的 grant-binding key)持久化(journal)，并在调用失败时重试(含下次启动重放)，直至 Account Authority 确认 grant 链终结后方清除该 journal。其中 Auth-side grant + `browser_session` 终结是耐久性关键步：它一旦完成，轮换链不可再续，后续无法恢复本地 account session。由于 `ak.session.grant` 有受限 TTL(见 [`crypto-media/device-lifecycle.md` §3.3](../crypto-media/device-lifecycle.md))，客户端 **MAY** 在该 TTL(加时钟 skew 容忍)过后停止重试：此时整条链已因自然过期失效，journal 中已无可吊销之物。重试 **MUST** 幂等——对已吊销/已过期 grant 再次调 hard logout 不应被视为错误。

**执行顺序与失败语义(normative)**：Auth-side session logout / grant-chain 终结是耐久性关键步，Account Authority SHOULD 先完成步骤 2，再完成 Principal-side 本地清理。若步骤 2 失败且没有可证明的 durable completion，Account Authority MUST NOT 向客户端返回 `ok=true`；应返回可重试错误（例如 `temporarily_unavailable`）。若步骤 2 已成功而步骤 3 暂时失败，Account Authority MAY 返回成功前把 Principal-side 清理持久化到 durable retry 队列；重复执行高层 `/logout` MUST 幂等。客户端在收到失败或网络中断时 MUST 只重试 `POST /_arkret/gate/account/logout`，MUST NOT 直接调用 `auth-sessions/logout`。

**吊销传播与生效语义(normative)**：Account Authority 内部可同步调用或异步重试 Principal-side 终结，但对客户端返回成功前 MUST 至少保证 Auth-side grant 轮换链已不可续。Principal Server 对本地 session 的有效性以「本地 session 记录 + 对 Account Authority / Auth-side 的 session-grant 内省」为准；Auth-side grant/会话被吊销后，Principal Server MUST 在下一次内省时得到 `active=false` 并 fail closed。实现 MAY 缓存内省结果，但缓存 TTL 与本地 session TTL 共同构成吊销生效的上界，二者 SHOULD ≤ 数分钟；高安全 profile SHOULD 更短或对敏感操作旁路缓存。Auth Server / Principal Server MUST NOT 依赖对方主动 push 吊销；Account Authority 是客户端可见的编排边界。

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

为关闭"deactivation 后仍有未撤销路径继续投递或被授权"的窗口，**deactivation accepted 进入 frontier 的同一事务边界内** MUST 对 `owner_account_id == deactivated.account_id` 的资源触发下列 fanout。授权、设备、KeyPackage、push 与队列存储 MUST 保存该 owner 绑定；无法证明 owner 的记录 MUST fail closed 并进入人工恢复队列，不能按相同 `principal_id` 扩大到其它 service account：

| 域 | Fanout 动作 | 触发什么 event |
| --- | --- | --- |
| **Session grant** | 撤销全部 `ak.session.grant`（含 applet delegated session）；后续 session-grant introspection MUST 返回 `inactive`。 | 服务端撤销表 + 可选 `ak.audit.accessed` |
| **Device grant** | 全部 `ak.device.*` 标 `revoked`；后续 `ak.self.events.command.submit` 用 revoked device 签名 MUST `actor_signature_revoked`。 | reducer 状态转换 |
| **Applet delegation** | 撤销所有 `ak.applet.registration` 持有的 delegated device；applet 服务后续调用 MUST `delegation_revoked`。 | reducer 状态转换 |
| **KeyPackage** | 按精确 `owner_account_id` 逐行 read/CAS到终态：`published+unused → retired`；`claimed+unconsumed → revoked`并保留原 claim ID；`consumed`保持 immutable。CAS stale必须重读并继续，直到写入目标终态或确认已处同一终态；stale conflict不得计作完成。任何 terminal不得复活或二次 claim。 | reducer + KeyPackage store 失效 |
| **Push route** | 撤销 `ak.device.push_route`；push gateway MUST 停止向该 principal 的注册 endpoint 投递。 | reducer + push gateway 缓存失效 |
| **To-device queue** | 服务端 to-device 队列 drop 所有 `recipient_principal_id == deactivated_principal` 的 pending message；后续投递 MUST `recipient_unavailable`。 | server-side queue 状态 |
| **Identity link cache** | 客户端与服务端可见缓存 MUST eager invalidate 所有 `(*, pairwise_did → deactivated_principal)` 映射；不得等待 7d TTL 或 MLS epoch 推进。 | `ak.identity_link` cache invalidation |
| **Capability cache** | 所有 cached `ak.capability.grant` decision 引用该 principal 作为 subject 或 issuer 的 MUST eager invalidate；下次 capability check 走完整判定。 | cache invalidation |

**写屏障（write barrier）**：`deactivated` accepted 进入当前 account status frontier 后，任何通过该 `account_id` 的 session、device 或 account binding 发起，或以该 account 作为 owner 的新 `ak.session.grant`、`ak.device.authorize`、KeyPackage publish / claim、agent / applet delegation、capability grant / delegation、push route、to-device enqueue 和 Realm membership delivery-binding 写入 MUST `failed_precondition`，`reason_code="account_deactivated"`。该屏障按 `account_id` 的 status frontier 生效，不得被较新的 HLC、不同 device、未完成 federation ack 或尚未失效的本地 cache 绕过；绑定同一 principal `did_core_id` 的不同 active `account_id` 不受旧 account 屏障影响，但必须用自己的新 session/device/KeyPackage 完成 onboarding。已经在屏障前 accepted 的历史 Event 不被改写；尚处 pending / quarantine / soft-fail 的写入 MUST 在恢复前重新检查该屏障。

约束：

- **不自动 ban**：deactivation 不等于 Realm 内 `ak.member.state` 转 `ban`/`leave`。哪些 Realm membership 自动 `ak.member.state = leave`（自愿停用）vs. 保留 `join`（policy 决定）由 Realm policy component `account_deactivation.member_action` 字段控制（该字段作为 Realm policy component 的登记见 [`../models/realm-and-space.md` §2.2](../models/realm-and-space.md)，经 `ak.realm.policy_bundle` payload 的 `account_deactivation` 组件写入；本节是其封闭枚举与处置语义的单一权威源）。该字段是封闭枚举，v1 取值域为：
  - `leave_self_initiated`（默认）：把该 principal 在本 Realm 的 membership 视为自愿退出，自动转 `ak.member.state = leave`。
  - `retain_membership`：保留 `join`，由 Realm policy 在后续显式处置（deactivation 本身不改 membership state）。
  - `leave_all`：无条件把该 principal 在本 Realm 的 membership 转 `leave`，等同 self-initiated 但不区分触发方语义。

  未识别的取值 MUST 按未知 policy 字段 fail closed（保守取 `retain_membership` 不主动改 membership，并标记 policy 解析告警），不得静默回退为默认值。注意本字段控制的是 membership state，与上表前 6 行无条件必停的本地投递撤销正交。
- **本地投递必停**：无论 policy 是否 ban，上表前 6 行（session/device/applet/KeyPackage/push/to-device queue）必停 — 否则会出现"账户已停用但其 device 还能签名 / push gateway 还在投递"的不可解释窗口。
- **MLS Remove**：若 Realm policy 决定 deactivate → leave，对应 MLS group MUST 在 grace window（默认 `mls_deactivation_grace_ms = 600,000 ms`）内 emit `ak.mls.commit` Remove；超时未 commit 则该 Realm 的成员客户端 MUST 在 verified timeline 中把该 principal 标 `unverifiable_member`，不再接受其新 epoch 消息。
- Fanout 失败的 partial state：如果某条 fanout 因网络 / 服务不可达失败，server `account_status` MUST 标 `deactivation_partial` 并继续重试；客户端 UI MUST 显式标记 "停用未完成" 而不是显示已停用。
- **跨 Principal Server 传播**：若该 principal 曾在其它 Principal Server 上持有 device / KeyPackage / to-device / push-route 状态，或通过 Realm membership delivery binding 使用过 peer 服务，首个接收 Principal Server MUST 按 §3.1 的 durable affected-service index 与 `ak.peer.account_status.command.submit` receipted fanout 分支主动推送原始 `AccountStatusRecord` 及其专用 `account_status_receipts[]`；不得塞入通用 Realm federation batch，不得广播给无关 peer。每个 destination 返回的 `accepted | duplicate` 才构成 ack。未在 `deactivation_propagation_window_ms` 内得到全部 ack 时，本地 `propagation_state` 转为 `incomplete`，服务侧投影 flag `deactivation_federation_incomplete=true`，并暂停新 Realm onboard、新 session/device grant 与新 KeyPackage 发布；该 flag 是可变的 outbox/projection 状态，MUST NOT 回写或重签 immutable record。后续全部 ack 到达后将 flag 清零并保留审计记录。

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

**执行状态机（normative）**：接收方接受一条 `status=erasure_pending` 的 `AccountStatusRecord` 时，必须为每个适用 storage boundary 建立一个可恢复的 durable execution，唯一键为 `(receiver_service_id,account_id,triggering_status_record_id,storage_boundary)`。接收 operation 只有在 execution intent 已持久后才可返回 `accepted | duplicate`；若 replica store 与 job store 不能共享物理事务，实现必须在启动与周期 reconciliation 中从已接受 record 重新派生缺失 intent，并在修复前保持 fail closed。worker 复用同一 typed erasure service 执行删除；不得在 account-status HTTP 事务内同步做物理擦除，也不得把 receipt submit 当作执行命令。精确重试、进程崩溃与 lease 过期都继续同一个 job；同 key 异 account/record/boundary 内容为永久冲突。`completed`、`partially_completed` 与 `blocked_by_legal_hold` 都是该 job 的 terminal receipt outcome，只有 transport/infrastructure failure 可重试。

Account Authority 不新增第二条私有 peer erase command。它发布 `erasure_pending` record 后只追踪上述确定性 execution，并通过既有 erasure receipt submit/get 轨道取得结果。Account Authority 只有在验证 receipt package、issuer proof、subject/scope、closed trigger 的 `record_id` 逐字等于本次 record，以及现行 `(principal_id,principal_server_id)` authority pair 全部一致后，才可把物理擦除标为完成；收到 account-status `accepted`、HTTP 2xx、空返回或 connector 本地 no-op 都不构成完成证据。

擦除完成后，服务端 SHOULD 发布 signed erasure receipt；若服务声明支持 hard erasure conformance，则 MUST 使用 `ak.schema.erasure_receipt.v1` payload，并可通过 `ak.audit.erasure_receipt` durable audit Event 发布。Receipt 至少绑定 closed `trigger`、`subject`、`scope.storage_boundary`、`outcome`、`erased_classes[]`、`retained_stub_digest`、`legal_hold_ref?`、`completed_at`、`issuer` 与 `proofs[]`；retained stub 必须逐字绑定同一个 trigger。账号物理擦除时 trigger MUST 是 exact `erasure_pending` AccountStatusRecord id；其他擦除类型绑定各自授权 Event 的 event 分支。`proofs[]` MUST 至少包含 1 条，且其中至少一条由 `issuer` 当前有效的 verification method 签名；空 `proofs[]` MUST 触发下文 fail-closed 校验（等同 `proofs[]` 校验失败）。`retained_stub_digest` MUST 等于 `hash(canonical_json(retained_stub))`；stub 可内联在 receipt，也可通过 erasure receipt endpoint 获取，但两者 canonical bytes 必须一致。Stub 只保留 typed trigger/reference 结构、冗余 digest 一致性、receipt/stub binding，以及连接仍存在的 signature、redaction authorization 与 legal-hold evidence 所需最小字段，MUST NOT 保留已擦除明文或裸明文 digest。原 canonical bytes 已擦除时，stub 与 receipt 均不能独立重算或证明其 hash preimage。Receipt 只证明 issuer 在声明的存储边界内完成、部分完成或因 legal hold 阻止删除，不证明独立第三方副本已经消失。

**Legal hold 阻塞终态（normative）**：erasure 与 legal hold 并存时，擦除流程有一个稳定终态：`ak.schema.erasure_receipt.v1` 的 `outcome` 枚举含 `blocked_by_legal_hold`（与 `completed` / `partially_completed` 并列；schema 真源见 [`erasure-receipt.schema.json`](../../artifacts/schemas/erasure-receipt.schema.json)，该 outcome 下 `legal_hold_ref` 为必填）。语义约束：

- `outcome="blocked_by_legal_hold"` 是 **合法终态**，表示 issuer 在声明的存储边界内因 legal hold 不能删除受保护数据，擦除合法地、**无限期**挂起在该边界。它 **不** 构成"擦除未完成、需重试"——verifier / 调度方 MUST NOT 因该 outcome 反复重试擦除流程或把它当作失败；它与 §3 规则 3 的 `erasure_pending` terminal 状态一致：account status 永久停在 `erasure_pending`，由 receipt 的 `outcome` 表征其物理终态为"被 legal hold 阻塞"。
- legal hold 解除后，issuer SHOULD 继续执行此前被阻塞的删除并发布一份新的 `completed` / `partially_completed` receipt（按 `subject` / `scope.storage_boundary` 取最新有效 receipt）；在解除前，`blocked_by_legal_hold` 始终是该边界的当前权威终态。
- **UI 披露（normative）**：客户端 / admin UI MUST 在持有 `blocked_by_legal_hold` receipt 时向用户明确披露"该账号 / 数据擦除因 legal hold 暂被合法阻塞"（含 `legal_hold_ref`），MUST NOT 把它呈现为无限期 `pending` / "擦除进行中"或让用户以为流程卡死等待重试。注意它仍区别于 §8 fail-closed 校验失败（digest 不匹配 / stub 不可获取 / `proofs[]` 校验失败）导致的"擦除视为未完成"——后者 MUST 继续 fail-closed 并重试，前者是已结论的合法阻塞终态。

**Fail-closed 校验（normative）**：verifier 在接受一份 `ak.schema.erasure_receipt.v1` 之前 MUST 重算 `hash(canonical_json(retained_stub))` 并与 receipt 的 `retained_stub_digest` 比对。当 stub（内联或经 endpoint 获取）与 `retained_stub_digest` **不一致** 时，verifier MUST 拒绝该 receipt（`erasure_receipt_stub_digest_mismatch`），并将该 erasure 视为 **未完成**（fail closed），不得据此把 subject 标记为已擦除、不得释放 legal hold、不得停止重试擦除流程。digest 不匹配意味着 stub 被替换、截断或与 receipt 不同源，无法证明声明的存储边界内删除已真正发生；默认结论是"擦除未完成"而非"擦除成功"。同理，receipt 缺失 `retained_stub_digest`、stub 无法获取，或 `proofs[]` 校验失败时，verifier MUST 同样 fail closed。

## 9. Session Revocation

用户或服务可撤销：

- 单个 session grant
- 单个 grant-binding session chain
- 单个 device
- 全部 session
- Applet delegated session

撤销 device MUST 产生 device list update。E2EE 客户端 MUST 停止向 revoked device 分享新密钥。

## 9.1 Personal agent principal lifecycle

Native personal agent(`actor_kind="agent"`,`accountable_principal_ids` 指向 controller principal)的 lifecycle 是 controller 账户 lifecycle 的从属体:

- **Provisioning** 由 controller 通过 `ak.self.agent.command.provision` operation 发起。controller 先按 [`key-management.md` §3.6.3](./key-management.md) 生成并发布不含 PCR binding 的 managed Agent DID inception；`prepare` 校验该 accepted entry 0，写 private durable reservation与signed opaque allocation handle，并返回逐字一致的 `initial_resolution`，但canonical published state保持为零，且**不**分配 Agent PCR id。controller 把该承诺写入本地冻结的 PCR genesis，取 `principal_control_realm_id = retype(event_id)`，再签署恰好一条前向声明该值的 `ak.agent.provision` Event；`commit` 经普通 Event admission接受后在同一 reducer transaction原子派生分别闭合的最小 provision、accountability、selector与realm-id-claim projections。不得用多Event fan-out、服务代签、完整payload复制或部分projection替代。必填且 immutable 的 `requested_scope`只建立 Agent key/session 的全局硬上限，不是Realm授权；其private disclosure与commitment只包含该完整 scope。provisioning不得据此创建任何`ak.capability.grant`。后续Agent key scope、Realm-scoped grant与session request不得越过该 ceiling；participation selection 是独立的 controller 偏好，在动作时只能进一步拒绝，不能补回 requested_scope 未授权的 action。commit 只把 outcome 推进到 `awaiting_pcr_genesis`：genesis 尚未接受时 Agent 对外不存在，DID PCR service entry、pairing handle 与 list/get 可见性全部推迟；controller 决定不再提交 genesis 时以 `ak.self.agent.command.issue_provisioning_abandonment_challenge` + `ak.self.agent.command.abandon_provisioning` 显式放弃。Agent PCR genesis 必须在另一次提交中送出，其 `initial_resolution` 必须逐字段等于 provisioning 保存值；accepted 后 outcome 先成为 `awaiting_did_binding`。controller 使用 inception 预承诺的 update key 发布连续 entry 1，在其中加入 create-locked PCR service 四元组；只有该 update accepted 后 outcome 才成为 complete，其 `pcr_recovery.status=pending`。controller E2EE client随后提交Actor Profile，并上传[`key-management.md` §7.5.6](./key-management.md) controller-owned recovery backup。通用Agent view从complete起只暴露lifecycle、readiness、presence三轴；未完成首次pairing由`readiness.blockers`中的`runtime_key_missing`/`pairing_open`表达，不新增第四状态轴。pairing poll可返回operation-local `runtime_state`诊断，但不得复制进list/get/key_state。
- **Pause**(`ak.self.agent.command.pause`):保留 agent identity、`accountability_grant`、`agent_key_authorize`、capability grants 的 durable state。Pause Event 是写入 `ak.component.agent.status.v1` 的 Control Move，authoring frontiers 只由 Event Envelope 顶层 `seal_basis` 表达；payload 不得携带第二套 producer 自报 frontier。Auth Server MUST 拒绝新 agent session grant；已签发 session token MUST 在独立于 session TTL、且 MUST ≤ 60 秒的 pause revocation freshness window（见 [`key-management.md` §3.6.1](./key-management.md)）内通过 introspection、status check、revocation list 或等价机制 fail closed。实现 MAY 选择同步 revocation 或每次资源访问强制 status 重查，但 MUST NOT 把该窗口放宽到 session 最大 TTL，也 MUST NOT 仅依赖自然过期继续接受 paused agent token。Pending action requests SHOULD 标 `awaiting_resume`。
- **Resume**(`ak.self.agent.command.resume`):Event 同样以顶层 `seal_basis` 表达 authoring frontiers；receiver MUST 在接受时读取 accepted current control frontier，重新校验 controller、agent、key、capability、Realm policy 与 `accountability_grant` freshness。Payload 不是 reducer receipt，不得声称包含“接收时捕获”的 frontier；任一重校验不通过则拒绝 resume，agent 保持 `paused`。
- **Deactivate**(`ak.self.agent.command.deactivate`):terminal state。controller 请求只携带恰好一个 `ak.self.agent.deactivate` lifecycle Event；其 accepted Seal 形成 parent lifecycle write barrier，并机械使全部 child runtime key、session、pairing handle、capability grant、KeyPackage、presence 与未来 submission ineffective。客户端不得提交逐 key/grant revocation bundle，服务端也不得把 cleanup 成功当作接受 lifecycle Event 的前置。runtime endpoint、pending action、Sidecar desired access、membership/MLS removal 与 recovery-backup pruning MAY 异步幂等清理，但 terminal authority 不可因此恢复；远端、introspection 与 cache MUST 在 ≤60 秒 freshness 上界内 fail closed。历史 child Event 保留审计，显式 revoke 只用于 parent 非 terminal 时的定点撤销。
- **Controller lifecycle 传播**:Controller 进入 `deactivated` / `suspended` 时，其 accountable native agents 的 active sessions MUST 通过本节 revocation 链失效，后续 agent session grant MUST fail closed。Accountability grant 失效同样使 agent 进入 ineligible 状态。
- **Controller Realm membership 传播**：Native Personal Agent 不能作为无主 effective member 留在 Collaboration Realm。controller 不再处于 Agent binding 所钉定的 exact join Event generation 时，所有对应 Agent 的 Event authoring、capability、delivery、KeyPackage 与 MLS active membership立即 fail closed；不等待 cleanup。canonical Agent member cell 只由实际 initiator签名的 `agent_membership_cascade` unit 改写：self leave 是完整原子 batch，第三方紧急 ban/remove 先原子落 terminal + durable exact-set intent，再补 complete-set cleanup。服务端不得合成 Agent leave，controller 重新加入也不自动恢复旧 Agent binding。
- **Pairing expiry**:仅适用于从未完成首次 key 授权的 Agent。`pairing.expires_at` 到达时关闭并省略 open-handle fields，readiness 保持 `not_ready` 且含 `runtime_key_missing`；pairing poll 对该 handle MAY 报 `runtime_state=pairing_expired`。该过期不得创建、撤销或改写任何 Realm grant，也不得改变 lifecycle 意图；controller 可重新发起 pairing 或进入 `deactivated`。
- **Runtime replacement re-pairing**:controller MAY 对任何已持有 active authorized key 的 Agent(lifecycle `active` 或 `paused`)经 `ak.self.agent.command.renew_pairing` 重开 pairing。通用 view 只以 open `pairing_mode=replacement`、handle fields 与 `readiness.blockers` 中的 `pairing_open` 表达；不增加 `runtime_state` 轴。lifecycle 意图、既有 key 与 grant 在新配对完成前保持不变；新配对完成时全部旧 key以 reason=`superseded_by_repairing` 原子撤销，lifecycle 意图原样保留。replacement handle 过期无副作用并清除 open-handle fields。怀疑失陷时 SHOULD 先 pause 再替换。详见 [`key-management.md` §3.6.1](./key-management.md)。

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
