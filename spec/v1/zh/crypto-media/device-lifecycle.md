---
title: Device Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-09-20
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. Login & Authorization Boundaries

去中心化协议摒弃了传统的账号+密码中心化认证模式，身份的本质是持有私钥。Arkret 把以下三件事分开处理：

- **登录因子验证**：Auth Server 验证 password、passkey、OIDC、SSO 或 recovery factor，只能产出 sender-constrained handoff/session、触发 identity-root recovery，或请求已有 accepted device 批准配对；它不能自行产生设备授权。
- **设备授权**：新设备成为长期有效设备，MUST 落成 `ak.device.authorize`、DID/key-log operation 或等价 signed event。只有这一步改变设备集合。
- **设备信任确认**：§10.1 的 verification checkpoint 只记录“该 exact device key 与 `hpke_key` 已被本账号在环确认过”。取得 checkpoint 不得自动创建登录态、长期 device grant 或 Realm capability。

### 1.1 认证服务（Auth Server）验证什么

Arkret 可以部署 Auth Server（企业 SSO 场景下的部署形态为 Auth Gateway），但它不是协议身份根。它验证的是“某个登录会话是否可以被绑定到某个 DID principal / device”，而不是用用户名、密码、邮箱或 OIDC subject 直接定义主体所有权。

实现 MAY 支持以下登录因子：

- 用户名 + 密码，用于传统 service account 登录。
- Passkey / WebAuthn，用于强认证或无密码登录。
- OIDC / SSO，用于企业或组织管理账号。
- 已授权设备配对，用于普通多设备加入。
- Recovery key、门限恢复或受信恢复服务，用于全部设备丢失后的恢复。

认证成功后，Auth Server MUST 产出以下至少一种可验证绑定：

- `ak.session.grant`：把短期 `session_public_key` 委托给 DID principal / device。
- `ak.device.authorize`：把新设备公钥加入当前设备集合。
- 满足 `recovery_policy` 的 `recover` / key-log event。

`session_public_key` 不仅是会话身份标记，还是会话请求的 proof-of-possession 出示密钥：日常受保护请求 MUST 使用 grant + RFC 9449 DPoP proof；高安全 profile 在此基础上追加 RFC 9421 HTTP Message Signature，使会话出示与该 key 绑定，仅截获 `ak.session.grant` 不足以重放。行使该 key 出示的具体形态、覆盖的 components 与 replay window 见 [`../sync/api-conventions.md` §3.2](../sync/api-conventions.md) 与 [`../sync/service-http-binding.md` §8](../sync/service-http-binding.md)；高安全 deployment profile 下该 PoP 出示对所有受保护 `ak.self.*` operation 升为 MUST。

资源服务器验证的是 session grant、device authorization、DID proof、capability 和 Realm policy，而不是“用户刚刚输入了正确密码”。密码、SSO session 和 service account id 都不能直接作为 `actor_id`、event sender 或 capability subject。

服务账号密码重置只改变服务账号登录凭据；除非同时存在有效 DID 控制证明或 recovery policy 事件，否则不得自动授予 DID 控制权、不得签发长期 device grant、不得访问 E2EE 密钥备份。

### 1.2 登录、设备授权与设备验证的边界

登录因子验证、设备授权与设备信任确认的三项边界以 §1 的列表为唯一规范来源。
“新设备登录”的推荐实现是：新设备先本地生成 device key，使用登录因子或已授权设备完成交互验证，再由当前有效授权方签发 `ak.device.authorize` 或短期 `ak.session.grant`。短期 Web/OIDC 登录可以只使用 `ak.session.grant`；需要 E2EE 历史、secret storage 或长期离线能力时，仍必须完成设备授权，并按 §10.1 取得 verification checkpoint。


## 2. 多设备配对 (Device Pairing)

在 Arkret 中，用户的每个物理/逻辑设备都应该拥有本地独立生成的设备级密钥对 (Device Key)。
多设备登录的过程，本质上是“已授权设备将新设备加入身份控制网”的密码学授权过程。

### 2.1 配对流程 (无密码登录)
1. **新设备初始化**：用户在新手机或新电脑上打开应用，本地生成一组全新的 Ed25519 密钥对，按 §2.1.1 完成 stage 与 finalize，然后展示同一条 pending request 的三个**等价**入口：8 位人工短码、二维码 (QR Code) 与可复制的配对链接。三者 MUST 指向同一条 request；切换展示方式 MUST NOT 重建 key、request、target proof 或 code。
2. **主设备受理**：用户在任意一台已登录的已授权设备上扫码、输入 8 位短码或粘贴链接；三条入口 MUST 解析到同一份 pairing transcript、同一份目标设备持有证明与同一个批准动作，MUST NOT 形成三套协议或产生强弱不等的授权分支。
3. **密码学授权**：
   - 主设备验证 pairing challenge 且用户完成显式确认后，签发完整 `ak.device.authorize` Event Initial Submission、符合 DID method 的 key-log operation，或触发 recovery policy 允许的设备授权流程。
   - DID Document SHOULD 只承载身份控制密钥和服务发现入口。普通设备列表、设备信任状态、吊销状态和算法更新 SHOULD 由 `ak.device.*` 事件、device key log 或受控 device registry 表达；只有 DID method 本身要求时，才把设备 verification method 写入 DID Document。
   - 短期浏览器或临时执行环境 MAY 只拿到 `ak.session.grant`，但它不改变长期设备集合，也不得访问 E2EE 历史密钥，除非另有有效设备授权和密钥共享流程。
4. **状态下发**：主设备通过点对点信道或安全的 Station sync surface，将必要的工作区快照、加密会话历史（通过 MLS Welcome / Commit 把新设备加入合适的 group）同步给新设备。
5. **事件广播**：主设备向 principal control stream 广播自己原始签署的 `ak.device.authorize` Event Initial Submission；若封装为 Event Envelope，其 `realm_id` 是目标 principal 的 `principal_control_realm_id`。`pair_device` 请求 MUST 携带该 exact submission；payload 是 commit 阶段 `hpke_key` 与新设备 exact `device_signature` 的唯一 wire source，request 顶层不得复制二者。Account Authority / Station MUST 走普通 Event admission、复算 payload / envelope digest并验证当前设备 proof 与 candidate possession proof（`accepted_device` 分支的 possession domain 与签名对象见 §5.2.2），MUST NOT 代铸 Event、替换 payload 字段或直接写 device-list projection。新设备获得的能力由该 accepted Event、session grant、Realm capability 和 policy 共同限制，不是自动获得 principal 的全部权限。

#### 2.1.1 短链暂存、finalize 与 resolve（server-mediated，normative）

§2.1 步骤 1 的“临时连接信息”MAY 由 Station 暂存并以短句柄承载，而非把设备公钥与配对材料整包放进二维码。采用该短链形态时 MUST 满足以下约束；它只改变“配对材料如何到达主设备”这一传输层，不改变 §2.1 步骤 3 的授权模型。

本节的 pending request 分**两个阶段**：`stage` 铸出 server 生成字段并保持 **account-less**；`finalize` 才用 candidate 自己持有的 pending account handoff 把该记录单向绑定到 exact `AccountId`。记录 state 依次是 `staged -> ready_for_claim -> authorized`，或在 TTL 到期后 `expired`；`ready_for_claim` MUST NOT 回退到 `staged`，`authorized` MUST NOT 绕过 `ready_for_claim`。已 finalize 的请求有两个等价取回入口：带外二维码 / 链接的 `resolve`，以及已授权设备只输入 8 位短码的**认证短码认领**。两者最终验证的 target proof 与 transcript MUST byte-equivalent，MUST NOT 形成更弱的 code-only 授权分支。

实现这组三项 open operation 的 Station MUST 在自己的 role-scoped `ServiceDescribe.supported_operation_bundles` 宣告已登记的 `ak.operation_bundle.station.device_pairing_handoff.v1`；未宣告该 bundle 的 Station MUST NOT 挂载或接受这三项 canonical HTTP binding。client-visible owner 固定为承载 `arkret_base_url` 与 `/_arkret/open/device-pairing/*` 的 Station origin。`finalize` 与短码认领是认证面，属于 `gate_audience` 指向的 Account Authority，随 `ak.operation_bundle.station.http_core.v1` 一并宣告，不进入上述 open handoff bundle。Account Authority 分离部署时仍负责 `gate_audience` 指向的授权与原子回填边界，但它是该 Station 的后端 authority，不得在另一个 origin 重复宣告或挂载这组三项 open operation；只有 Account Authority 与 Station 合并为同一 client-visible Station origin 时才由同一 origin 同时承载 open handoff 与 gate。客户端 MUST 从 Station describe 展开此 bundle 判断 handoff 可用性，并从 `auth_metadata.account_authority` 定位 gate 与这两项认证操作，不得把两个 origin 都当作 handoff authority。

1. **暂存（stage）**：新设备经**免认证**端点 `POST /_arkret/open/device-pairing/requests`（`ak.open.device_pairing.command.stage.v1`）提交 `new_device_pubkey`（canonical `PublicKey`，见 [`public-key.schema.json`](../../artifacts/schemas/public-key.schema.json)：`kty` / `kid` / `algorithm` / `key` 四字段，`key` 为密钥材料、`kid` 为 `ak:device:<uuidv7>`）与 `client_nonce`，以及可选 `display_name` / `device_metadata`。**stage 请求 MUST NOT 携带 target proof**——该 proof 必须承诺 server 在本次调用中才铸出的值，因此在 stage 时不可能存在（这条顺序约束是 §2.1.2 transcript 可生成性的前提）。Server 铸 `device_pairing_request_id`（`device_pairing_request:<uuidv7>`）、短 `pairing_code`、`gate_audience`（本 Account Authority 的 `gate_account_base_url` origin）与 `server_nonce`，以有界 TTL（SHOULD ≤ 10 分钟）暂存一条 **account-less** 记录（state `staged`），返回 `{device_pairing_request_id, pairing_code, gate_audience, server_nonce, expires_at}`。`pairing_code` MUST 由 OS CSPRNG 生成，并在该服务**整个 live pending 集合内唯一**——它同时是第 5 条短码认领的唯一查找键，重复的 code 会让认领无法定位到 exact 请求。用户主动刷新就是再调用一次本操作：它铸出一条**新的** request 与新的 code，新设备 MUST 立刻停止展示旧的三个入口。v1 明确**不登记**显式取消操作，也不需要：仍是 `staged` 的旧记录本身无害（`resolve`、code claim 与第 6 条 `pair_device` 的前置都是 `ready_for_claim`），而已 finalize 的旧记录由第 2 条的取代规则在下一次成功 `finalize` 时原子终结。一个 `AccountId` 在任一时刻至多存在一条处于 `ready_for_claim` 的可批准请求；实现 MUST NOT 认为一个账号可以同时存在两条可批准的请求，第 2 条的取代规则就是这条 MUST NOT 的执行点。暂存记录 MUST 同时保存提交的 `new_device_pubkey` 与 `client_nonce`——它们是 §2.1.2 staged transcript 的 member，gate 必须能只凭该记录重算 transcript。暂存记录在 finalize 之前**不绑定任何 principal、不授予任何东西**。
2. **账号绑定（finalize）**：candidate 拿到上述 server 生成字段后，从自己持有的 **sender-constrained pending account handoff**（[`../identity/account-lifecycle.md` §2.1.2](../identity/account-lifecycle.md) 的 Bound `account_handoff_grant`）取得 exact `AccountId`，按 §2.1.2 重算 challenge digest，按 §5.2.2 对**包含该 `AccountId` 的完整 transcript** 签署唯一 `device_pairing_target_proof`，再经认证端点 `POST /_arkret/gate/account/device-pairing/finalizations`（`ak.gate.account.command.finalize_device_pairing.v1`，`Authorization: DPoP <account_handoff_grant>` 加匹配 DPoP）把这份**公开、由签名保护**的 proof 附着到该 pending request。调用方资格是三项合取：持有 exact `device_pairing_request_id` + `pairing_code`、持有 staged candidate key（由该签名证明）、持有该 pending account handoff。服务端 MUST 从自己的 durable stage 重算 transcript，MUST 用 staged `new_device_pubkey` 验签 `device_signature`，MUST 要求 `target_proof.account_id` 与该 handoff 绑定的 `AccountId` 逐字节相等，并且 MUST 只允许从 `staged` **单向**进入 `ready_for_claim`。同 intent 的 exact retry 返回相同结果且不重新附加 proof，同 id 异内容 MUST conflict。该 proof 不是秘密（device public key、HPKE public key 与 metadata 都不是秘密），但它 MUST NOT 经免认证的 stage / resolve 请求面上传：匿名面持有它既无必要也扩大可枚举面。本调用零 Event、零授权。

   **取代（normative）**：一次成功的 `finalize` MUST 在**同一 durable 事务**中，把该 `AccountId` 名下**其它**处于 `ready_for_claim` 且未被接纳的 pending 记录原子转入 terminal `expired`，并按第 8 条保留有界 tombstone 以同时维持 exact retry 与阻止重放。取代 MUST 发生在本次记录进入 `ready_for_claim` 之前或同一事务内，MUST NOT 出现两条同时可批准的记录。取代不签发任何 Event、不产生任何授权，也 MUST NOT 回溯改写任何已经 `authorized` 的记录的 terminal outcome。同一 finalize intent 的 exact retry MUST 返回同一 outcome 且 MUST NOT 第二次触发取代。

   取代键是 `AccountId`：每个 `AccountId` 至多一条 `ready_for_claim`，与候选设备 `device_id`、candidate key 是否相同无关——刷新配对页（同一 candidate key 再走一遍）与换一台新设备（不同 candidate key）走的是同一条取代规则。**代价明示**：并行地在两台新设备上加设备被禁止，第二台的 `finalize` 会废掉第一台的码，用户需顺序操作；若产品判断必须支持并行加设备，MUST 先修改第 1 条那句 MUST NOT 再修改本条，MUST NOT 在实现侧私自放宽。

   取代的持久边界在 **gate 侧 durable pending 账本**：账号绑定只在 gate 侧存在，而本节允许 Account Authority 与 Station 分离部署，因此 Station 侧的 open handoff 记录既看不到 `AccountId` 也不承担取代义务。取代只能由持有该账号 sender-constrained pending account handoff 的一方触发，而取得该 handoff 已经过登录因子验证，所以本规则不引入匿名 DoS 面。
3. **短链承载**：finalize 成功后，新设备用同一份已签 `device_pairing_target_proof`（它已在第 2 条生成，本条不另签第二份）承载二维码 `{arkret_base_url}/_arkret/open/device-pairing/resolve#token=<token>&proof=<proof>`。`token = base64url_nopad(canonical_json({"r": device_pairing_request_id, "c": pairing_code}))`，`proof = base64url_nopad(canonical_json(device_pairing_target_proof))`。两者 MUST 仅位于 URL fragment 或请求 body，不得进入 path/query、访问日志或分析事件。二维码与链接 MAY 内含完整 target proof 以支持无需再次向服务端取回的路径，但它必须与第 2 条 finalize 附着的那一份 **byte-equivalent**；出现差异 MUST fail closed。target proof MUST NOT 上传到匿名 stage / resolve 请求面。二维码容量不足时 SHOULD 缩短可选 metadata，不能改为匿名服务端中转 proof。
4. **resolve 与人工确认**：批准设备经 body-only `POST /_arkret/open/device-pairing/resolve`（`ak.open.device_pairing.read.resolve.v1`）解析 token，从 bootstrap 重建 challenge digest，再用 staged key 对唯一 target proof 验签；只有 `ready_for_claim` 的记录可被 resolve。`device_id` 必须等于 staged `new_device_pubkey.kid`；proof 的 `device_public_key_did` 必须解码成 staged key；digest、HPKE 与 algorithms 全部由同一签名绑定。bootstrap MUST NOT 携带 proof、HPKE 或 algorithms 镜像。UI MUST 展示账号、设备 metadata 与完整 pairing code，并要求用户显式确认；device/key fingerprint、`device_id` 与 `gate_audience` MUST 继续参与机器校验，MAY 放入可展开的高级区域，MUST NOT 成为普通用户完成日常配对的必读材料。metadata 的权威只来自已重算并被 proof 承诺的 challenge。批准设备从已验 target proof 复制材料构造并签署完整 `ak.device.authorize`，不得采信服务器或 UI 自报替代材料。
5. **认证短码认领（code claim，normative）**：无摄像头或不便搬运长链接时，已授权设备改经 body-only `POST /_arkret/gate/account/device-pairing/code-claims`（`ak.gate.account.read.claim_device_pairing_code.v1`）**只提交规范化后的 8 位 code**取回同一份请求。服务端 MUST 在下列条件**全部**满足时才返回 resolved bootstrap 与 target proof：调用方是某个 exact `AccountId` 当前 accepted、非 `revocation_pending` 的设备；code 命中唯一的未过期、`ready_for_claim` 且未消费请求；target proof 绑定的 `account_id` 与 `gate_audience` 与调用方当前账号完全相同；proof、staged key、`device_pairing_request_id`、`pairing_code` 与 transcript digest 全部一致。响应只包含完成本地验签所需的 bootstrap 与 target proof，MUST NOT 包含任何私钥、session credential、recovery material 或该账号内其它设备的信息。认领只取回请求、**不产生任何授权**；最终仍必须由已授权设备显式批准并签署 `ak.device.authorize`。code MUST 只出现在请求 body 或 URL fragment，不得进入 path/query、访问日志或分析事件；服务端 MUST 对 caller device、`AccountId` 与本服务分层限速，并按第 9 条执行 exact request 的十次失败预算。取回后的人工确认与第 4 条相同：通过输入短码进入时，输入动作本身已完成短码比对，review 仍 MUST 展示该短码。

   **分离部署下的 current-device linearization（normative）**：Account Authority 必须依次完成 active Standard human SessionGrant 与 exact HTTP DPoP/JTI 校验、caller device／`AccountId`／service transport bucket，再以该 grant 的 signed `device_binding` 作为 expected authorization Event / generation 调用 `ak.peer.device_revocations.command.check.v1` 的专用 `device_pairing_code_claim` action class。`intent_digest` 绑定 operation id、exact `AccountId`、caller device id 与 canonical code-claim request；跨服务只携该 digest，不携明文 pairing code。SessionGrant 快照本身 MUST NOT 证明设备当前 accepted，`device_pairing_code_claim` MUST NOT 冒充 `event_write`，也不得回退到后者。origin Station 在一个 device lock / serializable transaction 内从 durable current projection 返回 decision receipt；只有 fresh、channel-bound、逐字段匹配的 `allow` 才能继续。`revocation_pending`、`revoked`、`authority_mismatch`、`generation_mismatch`、receipt 错配／过期或 origin 不可用全部在 pending lookup 前 fail closed，不得因 code 是否存在而改变公开形态或可观察顺序，也不得创建或增加 request-id 失败计数。

   收到 `allow` 后，Account Authority 才能在自己的**同一份** gate-side pending / abuse ledger 中按 code 定位 exact request；不得让 Station 维护第二份可写 pairing ledger。未知 code 仍不建计数行。只有已定位真实 retained record 后出现 account / audience / proof / staged material / usable-state mismatch，才按第 9 条计数；这些失败继续统一为 `not_found`。current-device gate 只裁决 caller eligibility，不读取 pairing record、不返回 bootstrap，也不产生授权。
6. **原子提交与 exact replay**：`ak.gate.account.command.pair_device.v1` MUST 携带 `device_pairing_request_id`。Account Authority 首次接纳必须从该 id 的未过期 `ready_for_claim` pending 记录重建 challenge digest，并与 authorize payload 的 `pairing_challenge_transcript_digest` 比较，再重建 §5.2.2 对象验证唯一 `device_signature`，并要求重建结果与 finalize 时附着的那一份 proof **byte-equivalent**。pending 记录的 code/key 必须匹配；该记录签名绑定的 `account_id` 必须等于批准方自己的完整 `AccountId`；批准方必须仍是该 exact AccountId 的 current accepted device。仍为 `staged`（未 finalize）的记录 MUST NOT 被接纳；已按第 2 条被取代、处于 terminal `expired` 的记录同样 MUST NOT 被接纳，且与从不存在的记录返回同一 `not_found`。反过来，本操作一旦接纳某条记录并写下 terminal outcome，后续任何 `finalize` 的取代 MUST NOT 回溯改写它。Event admission、设备目录更新、stage 消费、canonical request digest 与 terminal outcome MUST 在同一 durable 事务提交，提交后发送响应。ledger 以 `(device_pairing_request_id, approving AccountId, approving device_id)` 定位；同一 holder 的相同 canonical 请求返回原 `authorized_event_ref` 与 byte-identical outcome，不再要求 stage 为 pending、不再铸 Event；同 id 异请求或异 holder MUST conflict/拒绝。不得因 stage 清理丢失重试终态。目标设备仍可经匿名 body-only status `{device_pairing_request_id,pairing_code}` 取得 `{state,device_id?,authorized_event_ref?}`，并执行 §5.4.1。

7. **防枚举（normative）**：`finalize` 对 {未知 id、`pairing_code` 不符、已过期、已不是 `staged`} MUST 返回统一 `not_found`。`resolve` 对 {未知 id、`pairing_code` 不符、已过期、非 `ready_for_claim`} MUST 返回统一 `not_found`。**认证短码认领**对 {未知 code、错 code、已过期、跨账号、仍为 `staged` 的未 finalize 请求、已消费 code} MUST 返回**同一个** `not_found`——认证并不放宽这条：一个已授权设备同样不得据错误形态判断某个 code 是否存在、属于哪个账号或对应什么设备。`status` 对 {未知 id、`pairing_code` 不符} MUST 返回同样的 `not_found`；凭证正确时可返回 `staged`、`ready_for_claim`、`authorized` 或 `expired`，其中 `authorized` MUST 同时携带 `device_id` 与 `authorized_event_ref`，其余状态 MUST 不携带这两个字段。**被第 2 条取代或按第 9 条锁定的记录**在 tombstone 保留期内对 `status` 返回 `expired`，与 TTL 自然到期**不可区分**；这不构成「该记录曾经存在」的泄露，因为 `status` 的查询凭证是 `device_pairing_request_id` + `pairing_code` 本身——能问出 `expired` 的调用方正是铸出该记录的那台候选设备，它本来就知道记录存在。对 `resolve`、code claim 与 `pair_device`，被取代或锁定的记录与从不存在的记录一样返回统一 `not_found`。`pairing_code` MUST 使用 §7 定义的 8 位 Crockford-style CSPRNG code，并由暂存、finalize、resolve、code claim 与 status 端点限速兜底。
8. **有界与清理（normative）**：免认证的 stage、resolve 与 status 端点以及认证的 finalize 与 code claim 端点 MUST 限速；过期记录 MUST 对 `resolve`、`finalize` 与 code claim fail closed，`status` 在凭证正确且记录尚处于有界清理保留期时返回 `expired`，清理后返回 `not_found`。成功批准、过期、被第 2 条取代或按第 9 条锁定后，该请求与其 code MUST 被单次消费，并保留有界 tombstone 以同时支持 exact retry 与阻止重放。tombstone 保留期 MUST 至少覆盖该记录自己的 `expires_at`——被取代或锁定记录的 code 在原 TTL 结束前仍可能被重放，提前删除 tombstone 会让同一个 code 重新变成「未知」并可被再次铸出；保留期 MUST 有上界，SHOULD 在 `expires_at` 之后按同一清理周期删除。第 9 条的失败计数最晚 MUST 随该 tombstone 一起删除，MUST NOT 为保留计数而延长协议可见 TTL 或 tombstone 保留期。过期记录 SHOULD 被定期清理，Server MUST NOT 无界保留。

9. **失败预算与原子锁定（normative）**：Account Authority MUST 为 gate 侧 pending record 维护服务私有的 abuse-control ledger；它的 key 精确为 `device_pairing_request_id`，计数上限固定为 10。该 ledger 不是 Event、typed current result、authorization、device-pairing success outcome 或客户端可见状态，任何响应都不得披露当前计数。caller device、`AccountId` 与服务级分层限速是独立的 transport abuse bucket，MUST NOT 替代或重置这份每请求失败预算。

   只有在 Account Authority 已用 `device_pairing_request_id`，或 code claim 的 exact `pairing_code`，定位到一条仍在本节有界保留期内的真实 pending record 后，才可为该 request 计数。计数面封闭为 `ak.gate.account.command.finalize_device_pairing.v1`、`ak.gate.account.read.claim_device_pairing_code.v1` 与 `ak.gate.account.command.pair_device.v1`：对已定位记录出现 code 不符、调用方 `AccountId` / handoff 绑定不符、transcript 或签名失败、proof 与 staged 材料不符，或者记录不处于该操作要求的可用状态时，计一次失败。未知 request id 不得创建计数行；code claim 只收到一个无法定位 exact request 的未知 / 错误 code 时也不得创建计数行。schema / JSON 解析失败、身份认证尚未完成、DPoP 或 transport rate limit 在定位 exact request 之前拒绝的调用同样不计入某条 pairing。

   已记录成功结果的 exact retry 不计数：成功 `finalize` 的 byte-identical replay 仍返回原 `ready_for_claim` outcome；若底层 pending record 此后被取代或锁定，该历史 outcome 仍不得被改写，重放也不得把 record 恢复为可用。`pair_device` 的 byte-identical terminal replay 仍返回原 `authorized_event_ref`。已经 `authorized` 或已经有 durable `pair_device` terminal outcome 的记录 MUST NOT 被后续失败计数回溯改写。其它失败即使公开响应仍按第 7 条保持 `not_found`，或按既有错误映射保持 `proof_invalid` / `duplicate_conflict`，也照上述规则计数；响应形状、reason 与可观察时序 MUST NOT 暴露它是第几次失败或是否刚好触发锁定。

   第 1 至第 9 次计数不得改变 pending state。第 10 次计数 MUST 与 `staged|ready_for_claim -> expired`、code 单次消费和第 8 条 tombstone 建立在**同一个 durable transaction**中线性化；并发失败不得丢计数或让第十次之后的调用读到仍可用的 pending record。该事务失败时计数与 pending state 必须一起回滚，MUST NOT 只写其中一边。此安全写入是对“拒绝路径零副作用”的唯一窄化：失败路径仍然必须零 Event、零授权、零 typed current result、零 success outcome 与零其它业务部分写入。

#### 2.1.2 Pairing challenge digest（normative）

challenge 本身不另签名；新设备只签 §5.2.2 的 `device_pairing_target_proof`。唯一输入由 staged record 重建：

```text
new_device_pubkey_digest = "sha256:" || lowercase_hex(SHA256(JCS(new_device_pubkey)))
device_metadata_digest = "sha256:" || lowercase_hex(SHA256(JCS({display_name: value_or_null, device_metadata: value_or_null})))
challenge_bytes = UTF8("ak.device-pairing.challenge.v1\n") || JCS({
  client_nonce, device_pairing_request_id, expires_at, gate_audience,
  new_device_pubkey_digest, device_metadata_digest, pairing_code, server_nonce
})
pairing_challenge_transcript_digest = "sha256:" || lowercase_hex(SHA256(challenge_bytes))
```

`gate_audience` 在上述 canonical transcript 中取 wire `gate_audience_uri` 的逐字值。批准设备从 resolve bootstrap 重建，Account Authority 从自己的 durable stage 重建；均 MUST NOT 采信客户端自报 transcript。缺省 metadata/display_name 固定为 JSON null。两方均 MUST 比较 digest 后验证 target proof，而非只做非空检查或比较已缓存 signature。域、nonce、request id、code、expiry、key 与 metadata 任一改变均拒绝；过期 pending 不能接纳。没有 staged request id 或 proof signature 的请求 MUST `schema_violation`。同一 pairing 的累计失败计数、十次边界、原子锁定与清理只按 §2.1.1 第 9 条执行；[`../sync/service-http-binding.md`](../sync/service-http-binding.md) 的 transport 绑定与限速规则不另定义 pairing state。

`AccountId` **不进入**本 challenge transcript：stage 是 account-less 的，server 在铸这些字段时并不知道账号，所以它不可能承诺账号。账号绑定由 §5.2.2 target proof 的独立签名成员 `account_id` 承担，并在 §2.1.1 第 2 条 finalize 时由服务端与该 pending account handoff 逐字节比对。两者合起来才是完整 transcript：challenge digest 封死跨 request / 跨 Account Authority / 跨过期窗口 / 换 key 的重放，`account_id` 封死「同一份 attestation 被并进另一个账号」。

唯一通路是 staged short-link：未认证目标不得使用 self to-device API；不登记第二种 challenge transcript。exact replay 先查 durable terminal outcome，首次接纳才检查 pending state。

#### 2.1.3 Pairing challenge 的 conformance 入口

`vector_id`: `ak.vector.device_pairing.challenge_transcript.v1`（向量说明见
[`../conformance/conformance-vectors.md` 23.10](../conformance/conformance-vectors.md)）。它覆盖
stage 到 gate 的单签名 round-trip 正例、同一 `new_device_pubkey` canonical bytes 与 digest 全程不变，
以及坏 audience / 旧 pairing code / 跨 request 重放 / 过期 / 改 key / 坏签名 /
目标 device/key 不匹配 / 非 canonical transcript 域 / 旧 `{kid, alg, public_key}` 形态 /
stage 请求携带 proof / gate 缺 staged request / stage 泄露 principal 或 sibling target / fresh device 调用 self device-messages 等负向量。

`vector_id`: `ak.vector.device_pairing.code_claim.v1`（向量说明见
[`../conformance/conformance-vectors.md` 23.10](../conformance/conformance-vectors.md)）。它覆盖
`stage -> finalize -> code claim -> pair_device` 的两阶段正例、8 位 code 在 live pending 窗口内唯一、
`staged -> ready_for_claim` 的单向性、一次成功 `finalize` 对同一 `AccountId` 其它 `ready_for_claim` 记录的
原子取代（candidate key 相同与不同两组结果一致，已被接纳的记录不被回溯改写，exact retry 不二次取代），
以及错码 / 过期码 / 被取代的旧码 / 跨账号认领 / 未 finalize 请求 /
已消费 code 一律返回同一 `not_found` 的统一失败。

`vector_id`: `ak.vector.device_pairing.accepted_device_attestation.v1`（向量说明见
[`../conformance/conformance-vectors.md` 23.10](../conformance/conformance-vectors.md)）。它覆盖
§5.2.2 attestation 的正例、attestation challenge digest 与本次 pairing 不匹配 /
`hpke_key` 与 `pair_device.hpke_key` 或 payload 不一致 / 两个 binding kind 的 transcript 互换
等负向量，以及 §5.4.1 装配前校验失败时目标设备 fail closed。

#### 2.1.4 Gate 落地与目标设备的结果观察（normative）

用户确认后的授权落地 MUST 发生在 `/_arkret/gate/account/*` 认证面，使用 `ak.gate.account.command.pair_device.v1`。批准设备提交 staged `device_pairing_request_id`、`pairing_code`、`new_device_pubkey`、自己 author 的完整 `ak.device.authorize`，以及自身 fresh device proof；从已验签 `device_pairing_target_proof` 取得的 `hpke_key` 与 `device_signature` 只写入该 authorize Event payload，不在 commit 顶层重复。gate MUST 首次接纳时从仍为 `ready_for_claim` 的 staged record 按 §2.1.2 独立重算 challenge digest，再按 §5.2.2 用该 digest、该记录的签名 `account_id` 与提交 payload 重建 accepted_device possession 对象并验签 payload 内 `device_signature`，MUST NOT 接受无 staged request 的替代 transcript，也不得只做逐字段相等比较。gate 返回的 `authorized_event_ref` 只是 durable `ak.device.authorize` / `ak.device.list_update` 已被接受的引用或等价结果。新设备只通过 §2.1.1 status、后续 full `ak.self.account.stream.subscribe.v1` device list baseline，或重新通过 `ak.gate.account.command.issue_session_grant.v1` 取得 Standard grant 来观察授权结果；它 MUST 验证 durable device list，并在本地装配前完成 §5.4.1 的强制校验。

已授权设备在该 gate 接纳后 MAY 发布 `ak.device.list_update`，并在用户或 policy 允许时按 §10.2 共享账户级 secret-storage material 或 MLS Welcome；identity root / device private key 永不共享。

**pairing-originated verified checkpoint（normative）**：一次经本节落地成功的 accepted-device pairing 同时产生两个**正交**结果：lifecycle 上新设备取得 accepted `ak.device.authorize` 并成为 `active`；trust 上产生一条 `verification_source=pairing_code` 的 §10.1 verification checkpoint。它不是「验证成功自动变成授权」，而是同一次用户在环的配对 ceremony 同时提交了授权结果与信任证据。该 checkpoint 的建立条件是 §10.1 的五项合取，其中带外确认由 §2.1.1 第 4 条的扫码 / 链接显式确认或第 5 条的输入短码满足，账号绑定由 §5.2.2 的签名 `account_id` 满足。accepted `ak.device.authorize` 与该 checkpoint MUST 在同一原子提交可见，或可从同一 accepted authorization 与已签 transcript 确定性重建；两者 MUST NOT 分叉。授权与信任此后仍是两个维度，各自按自己的规则撤销、过期与 fence。

### 2.2 设备吊销

> 吊销后的 MLS secret 与 backup series 轮换 MUST 在一个 `SecurityRotationTransaction` 内进行，
> 且该 transaction MUST 在提交 `ak.device.revoke` **之前**创建并 durable prepare。accepted revoke
> 只进入可由 exact RealmCommit rejected command result 恢复的 `revocation_pending`；transaction 在 pending 期间可冻结新使用、预留 id 与准备幂等远端步骤，但 MUST 保留 reject 恢复所需材料，不得执行不可逆 device-generation 擦除。只有 covering RealmCommit accepted 后才提交永久撤销、MLS secret / backup series rotation 与终局清理。固定顺序、reserved id 与崩溃续跑合同见
> [`../identity/security-transactions.md` §3](../identity/security-transactions.md)。
> 在没有该 transaction 的情况下重试轮换会重新生成 secret 与 series id，而不是续跑首次计划。

当设备丢失时，用户可从任何其他已授权设备、DID 控制密钥或 recovery policy 允许的恢复服务发起吊销操作：发布 `ak.device.revoke`，停止接受该设备的新签名写入，并对受影响的 MLS 群组触发 `Remove` 与 Epoch 更新。若该设备曾被写入 DID Document，撤销流程还必须按 DID method 规则移除或失效对应 verification method。

`ak.device.revoke` 是 principal control stream 的 producer-signed Event。当前治理 Station 在目标 stream head 处验证 caller、device generation、recovery/session policy 与领域 revision；成功时签发该 Event 的 RealmCommit，并在同一事务内更新 device lifecycle 与后续 MLS removal intent。失败或 retryable unavailable 不写共享状态。

`SecurityRotationTransaction` 固定绑定 revoke Event、replacement secret/backup material 与清理步骤。完成结果携带该 revoke Event 的 `CommittedEventRef`；exact replay 返回同一结果，异内容使用同一 transaction id 时返回 conflict。

## 3. 企业单点登录 (SSO / OIDC Gateway)

企业通常强制要求使用 Okta、Google Workspace 等中心化身份提供商 (IdP) 进行认证。在不破坏去中心化端到端加密前提下，本协议引入 **Auth Gateway (认证网关)** 模式。

### 3.1 架构角色
- **Auth Gateway**：部署在企业内网或受控云端的高安全级别服务器。它通常是组织 DID 明确声明的 session grant issuer 或设备授权服务。只有在企业托管账号场景中，它才 MAY 按组织治理委托托管员工账号的高权限签发材料；对普通个人 DID，网关 SHOULD 只签发短期 session grant，不应托管用户 DID control/update key、device key 或 recovery key。v1 不定义独立 principal signing key。

### 3.2 登录时序
1. **浏览器会话初始化**：员工在浏览器打开 Web 端应用，本地生成临时会话密钥 `session_key`。
2. **OIDC 重定向**：浏览器跳转至企业 Okta 完成标准的 OAuth2 / OIDC 身份认证。
3. **网关授权 (Gateway Delegation)**：Okta 认证成功后回调 Auth Gateway。Gateway 验证员工身份无误后，在自己的 durable issuer ledger 中建立 immutable issuance record，并用 issuer key 签发短期、受众绑定、scope 受限的 `ak.session.grant`，把 `session_key_pub` 绑定到目标 DID principal、设备、origin、audience、过期时间和允许的 operation 集合。Gateway 不持有用户 principal/device/recovery 私钥，不得为该 grant 代签或提交 principal Event。其中绑定的设备 MUST 是客户端持有的稳定协议 `device_id`（`ak:device:<uuid>`，由客户端在认证时显式声明，例如 OAuth `urn:arkret:client:device:<id>` scope 透传到 introspection 的 `org.arkret.device_id` claim）。资源服务器 MUST NOT 从 token / session 标识（如 `jti` / `session_id`）派生或伪造一个 per-token 的 `device_id`——这违反 §4「服务端不得伪造 device identity」，且会让该值在每次 token 轮换时漂移，静默破坏所有按 `(principal, device)` 绑定的不变量（sync cursor 主体/设备匹配、key backup 写入设备授权）。携带认证材料但缺少稳定 device 绑定的会话 MUST 对 device-scoped 操作 fail-closed 拒绝，而非降级放行。
4. **会话生效**：浏览器操作必须同时附带 session grant、device proof 或等价绑定证明。高安全 profile 的受保护 `ak.self.*` operation MUST 进一步用 `session_key`（即 grant 委托的 `session_public_key`）对每个请求做 RFC 9421 HTTP Message Signature 出示（sender-constrained / PoP，见 [`../sync/api-conventions.md` §3.2](../sync/api-conventions.md)），使会话请求与该 key 绑定，截获 token 不足以重放；高安全 deployment profile 下该出示升为 MUST。资源服务器仍 MUST 重新验证 DID control state、capability、Realm policy、grant scope、audience、origin 和重放状态；不得因为 OIDC 成功就把请求视为 DID 控制证明。
5. **平滑过期**：session grant SHOULD 使用分钟到小时级 TTL，并支持即时撤销。

### 3.3 设备持有绑定与 grant 轮换（normative）

为在「会话凭据短期有效」与「设备会话可跨多日免重登」之间取得一致,session grant 采用 **grant-binding key 持有绑定 + 滚动轮换**模型:

- **持有绑定(cnf.jkt)**:签发 `ak.session.grant` 时,Auth Server MUST 要求客户端出示一个由其 **grant-binding key**(即 DPoP key,RFC 9449 DPoP 式持有证明)签名的 proof,并把该 key 的 RFC 7638 JWK 指纹写入 grant 的 `cnf.jkt`(RFC 7800 confirmation)。`cnf.jkt` 把 grant 绑定到「持有该私钥的会话/设备」,而非仅记一个 `device_id` 字符串。客户端签的是本次 holder/request proof；Auth Server 签的是自己的 credential，两者都不替代设备或 principal Event proof。
- **grant 直接出示、短期轮换**:Station 不铸第二个本地会话凭据；客户端以 `ak.session.grant` + DPoP 直接访问 `/_arkret/self/*`。grant 自身为分钟到小时级 TTL，客户端在 grant 临期时用**仍有效的 grant** 与同一 grant-binding key 轮换出新 grant。
- **轮换(rotation)**:grant 临近自身过期时，客户端用**同一 grant-binding key** 签 DPoP 持有证明，向 Auth Server 的 session-grant 轮换端点(见 [`../sync/service-http-binding.md` §2.3](../sync/service-http-binding.md))换出一张新 grant。Auth Server MUST 校验 proof 的 JWK 指纹等于旧 grant 的 `cnf.jkt`(证明持有同一 grant-binding 私钥)。稳定 request identity 是 `(predecessor_grant_id, refresh_request_digest)`；同一 issuer transaction MUST 创建保持 `cnf.jkt`、subject/scope/audience 与独立 `session_id` 的 successor，并把 predecessor 原子标为 `superseded`。exact replay 必须返回同一 successor；同 identity 异 canonical intent 必须 `duplicate_conflict` 且零状态变化。如此滚动使设备会话存活到天级，**直到设备被吊销、grant 链被吊销、或底层 `browser_session` 被终结(登出)**——三者任一即拒绝继续轮换(见 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md))。
- **不引入长期离线续期凭据**:本协议以「grant-binding key 轮换 grant」承担续期职责,grant 自身保持分钟到小时级 TTL;不依赖、也不要求签发 OAuth `offline_access` 类长期续期凭据。
- **登出即终结**:轮换链挂靠在 Auth Server 的 `browser_session` 上；`browser_session` 被登出终结后，即便持有正确的 grant-binding 私钥(指纹匹配 `cnf.jkt`)也 MUST NOT 再轮换出新 grant——续期必须重新走完整认证。

Auth Server MUST 以同一 issuer ledger 作为 issue、refresh、revoke、account/device cascade 与 introspection
的唯一状态源。DPoP/holder replay lookup 每次仍须重验 method、target、audience 与 request digest。命中的
successor 已 expired / revoked / superseded 时，必须返回登记的 `session_grant_replay_expired` 或
`session_grant_replay_terminal`，不得用同一 request identity 再发一张；replay record 已无法判定时必须
`session_grant_replay_indeterminate`。完整 ID 与 replay 合同见 [`../identity/key-management.md` §6](../identity/key-management.md)。

**grant-binding key 与设备身份 key 的生命周期正交(normative)**:`grant-binding key` 是**会话认证凭据**,`cnf.jkt`、`ak.session.grant` 轮换与 hard-logout 清除只作用于它；它按 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md) 在 hard logout 时被清除、下次登录轮换,soft recovery 路径保留。§5.2 的**设备身份 key**(`device_public_key_did` / `verify_key`,签事件 / KeyPackage / MLS leaf)是 E2EE 信任根，只经 `ak.device.revoke` + 重新入册轮换。二者必须独立生成、独立存储并独立轮换：grant-binding key 的私钥字节、公钥字节、JWK thumbprint 与 `kid` 都 MUST NOT 等于或复用设备身份 key 的对应材料。违反该分离要求的会话或设备授权 MUST fail closed。会话生命周期(登录 / 登出 / grant 轮换)MUST NOT 触发设备身份 key 的重铸(见 §5.2)。

此模式只把 Web2 SSO 作为登录因子和会话授权输入。它不授予 E2EE 密钥访问权，不自动创建长期设备，不替代 `ak.device.authorize`、DID/key-log operation 或 recovery policy。


## 4. Device Identity

每个设备 MUST 有稳定 `device_id` 和设备签名密钥。`device_id` 的类型是 `id:device`，wire form MUST 为完整 `ak:device:<uuid>`；当它出现在 JSON object key 中时也同样适用，不得改写成局部别名：

```json fragment
{
  "device_id": "ak:device:019640dd-8000-7000-8000-000000000000",
  "display_name": "Alice iPhone",
  "algorithms": ["ak.hpke_x25519_aead_chacha20poly1305.v1", "ak.mls.v1"],
  "verify_key": {
    "kty": "OKP",
    "crv": "Ed25519",
    "kid": "did:webvh:...#ak_device_01HV_verify"
  },
  "hpke_key": {
    "kty": "OKP",
    "crv": "X25519",
    "kid": "did:webvh:...#ak_device_01HV_hpke"
  },
  "created_at": "2026-04-26T00:00:00Z"
}
```
`display_name` 是用户为该设备指定的人类可读名称（如 "Alice iPhone"），用于在设备列表 / 验证 / 撤销 UI 中区分同一 principal 名下的多台设备。它是 optional、可变、UI-only 字段，无唯一性约束，不参与任何 capability、reducer 或加密信任决策；设备的协议层唯一标识始终是 `device_id`。按 [`models/common-fields.md` §3](../models/common-fields.md) 与 [`overview/glossary.md`](../overview/glossary.md) 的命名约定，device record 的人类可读名称字段统一使用 `display_name`，不得用 `device_label`、`device_name` 或裸 `name` 等别名。

设备记录必须来自 root-committed PCR genesis、accepted-policy-authorized recovery unit 或当前 generation 的 accepted device 授权，并受 device-generation fence 约束。genesis 的首设备 authorize 与 recovery 的两条 Event 由各自候选设备 identity key 签署；policy factor 不代签 Event。服务端不得伪造 device identity。

## 5. Device Authorization Chain

Arkret v1 只有一个 principal device model：DID 是 identity-root key log；Principal Control Realm（PCR）是设备目录、撤销、recovery policy 与 generation fence 的业务真相。设备不是 DID actor，也不要求 DID Document 中存在设备或入册 service fragment。

### 5.1 PCR genesis 与首设备（normative）

首次创建 PCR 必须提交一个 closed ordered unit：

1. `ak.realm.create`：由 registration-time DID control key 签名；`realm_genesis.fields.purpose` 必须是 `principal_control`，并携带 `FoundingDeviceDescriptor` 与 durable registration evidence digest。
2. `ak.device.authorize`：由 descriptor 中 `device_public_key_did` 对 possession transcript 和 Event proof 各自签名；`authorization_binding_kind="registration_anchor"`。它不携带任何指向第一条 create 的信封字段；两条的次序由这份 closed ordered unit 的 wire 顺序给出，由同一事务内 position 连续的两笔 RealmCommit 落定，绑定则由 `FoundingDeviceDescriptor` 对本条 authorize **payload** digest 的单向承诺给出（§5.0.1）。

构造方必须按 [`event-and-patch.md` §3.2](../models/event-and-patch.md) 先冻结该 unit 唯一的 canonical 毫秒 authoring checkpoint `T`，再构造、求摘要并签署两条 Event；两条 `event.created_at` 与两个唯一 producer proof 的 `proof.created_at` 必须全部逐字等于 `T`。Station 必须在任何验签或状态写入前检查该等值关系；这不是普通 PCR Event 的全局规则。

identity root 只单向承诺两条 Event 的 payload digest，不承诺 Event id 或 envelope digest。create 与 authorize Event 的完整 account `actor_id` 必须逐字一致；descriptor 与 authorize payload 必须在 `device_id`、device/HPKE key、算法集合和 authorize payload digest 上逐字一致。Station 必须验证 event-derived PCR id（`retype(create.event_id)`，见 [`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md)；它不由 principal DID 或 subject 派生）、空 checkpoint、**账号维度**的 create-once、当前 identity-creation lease fence/expiry 及完整 root/device proofs，然后在一个数据库原子边界内接受两条 Event；任一步失败均零写入。

首设备无需已有设备、账号权威或管理员批准。Account Authority 的 S2S signature 只证明 transport source，不能替代 identity root 或 device proof。

### 5.2 Device possession transcript（normative）

`device_signature` 的 domain **由 `authorization_binding_kind` 判别**，不是单一固定值。该字段有四个取值，各自对应一个 domain 与一个封闭签名对象：

- `registration_anchor`：PCR genesis 的第二条 authorize；domain `ak.device_authorize_possession_proof.v1`，见 §5.2.1。
- `pcr_recovery`：PCR-policy recovery unit 的第二条 authorize（包含 policy 显式选择 did_root factor 的情况）；domain `ak.device_authorize_recovery_possession_proof.v1`，并绑定 recovery session/policy/generation。
- `accepted_device`：已有 accepted device 批准新设备；domain `ak.device_authorize_accepted_device_possession_proof.v1`，见 §5.2.2。
- `applet_managed_delegation`：Applet-managed Bot / Ghost principal 在自己已接受的 `applet_managed_control` PCR 中授权一台受限 delegated device；domain `ak.device_authorize_applet_managed_possession_proof.v1`，见 §5.2.3 与 §15。

四个 domain 都登记在 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)。verifier MUST 先从 payload 的 `authorization_binding_kind` 选定 domain 与成员集合，MUST NOT 尝试其它 domain，也 MUST NOT 接受跨 binding kind 复用的 transcript。

#### 5.2.1 registration/recovery possession transcript（normative）

genesis 时候选设备签署第二条 authorize；recovery 时同一候选设备签署整个封闭 unit。设备 possession 签名对象覆盖完整 authorization core 加注入的 `account_id`；recovery 分支还必须加入 policy/session/generation binding。下面是 `registration_anchor` 分支的**完整成员集合**：

```json fragment
{
  "account_id": {"principal_id": "ak:did_core:webvh:zExamplePrincipalScid", "station_id": "ak:did_core:webvh:zExampleStationScid"},
  "device_id": "ak:device:...",
  "device_public_key_did": "did:key:...",
  "hpke_key": "z...",
  "algorithms": ["..."],
  "device_key_algorithm": "Ed25519",
  "authorized_by": "ak:did_core:webvh:zExamplePrincipalScid",
  "authorization_binding_kind": "registration_anchor",
  "authorized_generation_ref": 1,
  "not_before": "2026-08-09T00:00:00.000Z",
  "expires_at": null,
  "scopes": null,
  "recovery_session_id": null
}
```
签名输入是 `UTF8("<domain>\n") || canonical_json(上述对象)`，`canonical_json` 按 [`../conformance/encoding.md` §2](../conformance/encoding.md)（JCS），`<domain>` 按 §5.2 从 `authorization_binding_kind` 选定。

`algorithms` 必须先按 UTF-8 bytewise 排序去重；缺失的 optional 字段在 transcript 中规范化为 `null`——`expires_at` / `scopes` / `recovery_session_id` 在该对象里是**必需成员**，payload 未携带时取 `null`。把它们写成 optional 会让「成员缺失」与「成员为 `null`」成为同一份授权的两串 canonical bytes，规范化就不可执行；因此 transcript 成员集合恒定，与 payload 是否携带该 optional 字段无关。

transcript 的 `account_id` 取自待签 Event 的完整 account `actor_id`，不是 payload 字段——`device_authorize_payload` 是封闭对象，MUST NOT 镜像 `principal_id` 或 `account_id`，verifier MUST 从自己已认证的 envelope `actor_id.account_id` 重建该成员，MUST NOT 取自 payload 成员、路由、session audience 或任何未签 body 成员。`device_signature` 是**本 transcript 的产物**，因此 MUST NOT 是它的成员：把输出签进输入是循环。Event id、envelope digest、`pairing_challenge_transcript_digest` 及其它 proof material 同样不进入该对象。

`authorized_generation_ref` **在**该对象内，由候选设备一并签名（§5.5.2）；`registration_anchor` 下它 MUST 等于 `1`，即同一 `pcr_genesis_unit` 初始化的值。`registration_anchor` 下 `authorized_by=account_id.principal_id`——这是同一对象两个成员之间的相等，JSON Schema 表达不了，由接纳方按本节校验；`pcr_recovery` 的 authority 来自 re-anchor Event 所绑定的 accepted recovery policy，而不是 current DID controller。

**wire 形态（normative）**：三支 possession transcript 的 wire 形态是 [`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) 的 `device_authorize_possession_transcript` / `device_authorize_recovery_possession_transcript` / `device_authorize_applet_managed_possession_transcript`。三者 `allOf` 同一个 `device_authorize_possession_core`（完整 authorization core 加注入的 `account_id`，不含任何签名或 digest 成员），各自收窄自己的 `authorization_binding_kind` 分支，并以 `unevaluatedProperties: false` 自我收口，因此未登记的成员无法搭车。它们**不是** `device_authorize_payload` 的 `allOf`：payload required `device_signature` 且禁止 `account_id`，那种形态没有任何实例能满足。`accepted_device` 不在这三支之内，它签 §5.2.2 的独立封闭对象。

#### 5.2.2 `accepted_device` target proof（normative）

配对时目标设备的处境相反：stage 时暂存记录是 **account-less**，它不知道哪台 sibling 会批准，因此不可能先签一个包含 `authorized_by` / `not_before` / `expires_at` / `scopes` 的对象；而批准设备在拿到目标 possession proof 之前又无法构造满足最终 DTO 的完整 Event。若两者都要求对方先动，配对就是死锁。因此 `accepted_device` 使用一个**只覆盖目标自有材料、本次账号绑定与本次 pairing challenge 绑定**的封闭对象：

```json fragment
{
  "account_id": {"principal_id": "ak:did_core:...", "station_id": "ak:did_core:..."},
  "device_id": "ak:device:...",
  "device_public_key_did": "did:key:...",
  "hpke_key": "z...",
  "algorithms": ["..."],
  "device_key_algorithm": "Ed25519",
  "authorization_binding_kind": "accepted_device",
  "pairing_challenge_transcript_digest": "sha256:..."
}
```
签名输入是 `UTF8("ak.device_authorize_accepted_device_possession_proof.v1\n") || canonical_json(上述对象)`，`canonical_json` 按 [`../conformance/encoding.md` §2](../conformance/encoding.md)（JCS）。`algorithms` 同样必须先按 UTF-8 bytewise 排序去重。该对象没有 optional 成员，因此不存在缺失字段规范化为 `null` 的情形；签名字段、Event id、envelope digest 及其它 proof material 同样不进入该对象。

**`pairing_challenge_transcript_digest` 是本 attestation 的 challenge replay 边界**：它 MUST 逐字节等于按 §2.1.2 独立重算的 challenge digest，因为该 digest 本身就承诺了整条挑战：

- staged short-link transcript 承诺 `device_pairing_request_id` / `pairing_code` / `gate_audience` / `expires_at` / `server_nonce` / `client_nonce` / `new_device_pubkey_digest` / `device_metadata_digest`。

因此跨 request（`device_pairing_request_id` + nonce）、跨 Account Authority（`gate_audience`）、跨过期窗口（`expires_at`）与换 key（`new_device_pubkey_digest`）的重放全部被阻断，由同一 target signature 认证；一个为别的配对铸出的 attestation 在本次配对里永远验不过。

**`account_id` 是账号绑定成员（normative）**：它 MUST 是本次配对目标账号的完整 `AccountId`，由 candidate 从自己持有的 pending account handoff 取得并**签进本对象**。它之所以能存在而不造成死锁，是因为它只需要 candidate 自己的认证结果，不需要任何 sibling 先动；stage 仍然 account-less，该成员在 §2.1.1 第 2 条 finalize 时才出现。服务端 MUST 在 finalize 时要求它与该 handoff 绑定的 `AccountId` 逐字节相等，gate MUST 在接纳 `pair_device` 时要求它等于批准方自己的完整 `AccountId`，目标设备 MUST 在 §5.4.1 装配前要求它等于被接受 Event 的 `actor_id.account_id`。实现 MUST NOT 用服务端旁路字段、路由、session audience 或客户端未签 body 成员替代它来声称账号归属。

从该对象移出的 `authorized_by` / `not_before` / `expires_at` / `scopes` / `recovery_session_id` 改由**批准设备的 Event proof** 承担：`accepted_device` authorize 的 `proof.verification_method` MUST 使用该授权 Event accepted-at 的 `did` 与 method evidence，而不是 current DID resolution；verifier MUST 取其 bare `did`，经已登记 method adapter 验证并要求 `project(did) == Event.actor_id.account_id.principal_id`，同时要求 fragment 逐字等于 `signing_device_id`，且 `signing_device_id` 必须是 payload.`authorized_by`（§5.3）。实现不得把 principal core 与 device fragment 直接拼成 DID URL。该 proof 覆盖完整 canonical Event bytes；两个签名合起来覆盖的字段集合不小于 `registration_anchor` / `pcr_recovery` 单签名覆盖的集合。目标设备对完整 AccountId 的确认由本对象的签名 `account_id` 与 §5.4.1 的装配前强制校验共同承担。

**wire 形态与载体（normative）**：该 attestation 的 wire 形态是 [`device-pairing.schema.json`](../../artifacts/schemas/device-pairing.schema.json) 的 `device_pairing_target_proof`（上述八个成员加 `device_signature`）。它有两条载体，二者必须携带 **byte-equivalent** 的同一份对象：带外的 staged short-link 二维码 / 链接 fragment，以及 §2.1.1 第 2 条的**认证** finalize 调用——后者是它唯一的 server-facing 载体，也是 §2.1.1 第 5 条短码认领能把它交给批准设备的前提。它 **MUST NOT 经免认证 stage / resolve 请求面回传给 server**：匿名请求面持有该 attestation 既无必要也扩大可枚举面。该对象是公开、由签名保护的材料，不含任何私钥。

**它是 `hpke_key` 与 `algorithms` 的唯一权威来源**：`device_pairing_stage_request_body` 与 `device_pairing_bootstrap` 都不承载这两个值，也 MUST NOT 增设镜像字段——让匿名暂存面持有长期设备 HPKE 公钥与设备算法指纹会平白扩大可枚举面，而镜像一个已被签名的值只会制造第二个非权威副本和一处必须 fail closed 的比对义务。批准设备 MUST 先独立验证 attestation 签名，再从**验签通过的 attestation** 读取 `hpke_key` / `algorithms` 填入 authorize payload；MUST NOT 从服务端响应、UI 输入或任何未签名来源取这两个值。服务端因此无法替换它们。

**gate 侧不需要额外 wire 字段（normative）**：`ak.gate.account.command.pair_device.v1` 的请求体不携带该 attestation 对象。Account Authority 从 `authorize_event.event.payload` 的 `device_id` / `device_public_key_did` / `hpke_key` / `algorithms` / `device_key_algorithm` / `authorization_binding_kind`，加上它**自己按 §2.1.2 重算**得到的 challenge transcript digest 与该 pending 记录在 finalize 时固定下来的签名 `account_id`，重建上述封闭对象，并用请求携带的 `new_device_pubkey` 验签 `device_signature`；重建结果 MUST 与 finalize 时附着的那一份 proof byte-equivalent。目标 descriptor 从已签 Event 取材，challenge 与 `account_id` 从服务端 pending 记录取得；因此无需也不得接受一个客户端在 `pair_device` 请求体中提供的 target proof 副本；重建不符或验签失败 MUST NOT 授权设备。

**持久验签材料**：accepted authorize payload MUST 保存 `pairing_challenge_transcript_digest`，与目标 descriptor、`device_signature` 一起构成原已签对象，stage 清理后仍可重验 target signature；对象中的 `account_id` 由该 Event 自身的 `actor_id.account_id` 逐字节提供，不在 payload 中另设第二个副本。仅凭这组材料不能事后证明 challenge 确由 gate 签发；该事实由首次 admission 的 accepted evidence 保证。不得保存匿名 code/nonces 为公开 Event 字段。

#### 5.2.3 `applet_managed_delegation` possession transcript（normative）

Applet-managed Bot / Ghost principal 在结构上不可能有 founding device：`purpose="applet_managed_control"` 的 PCR genesis MUST NOT 携带 `FoundingDeviceDescriptor`，而它所在的 install / Ghost 创建单元又是封闭固定集合，该 Realm 首个 RealmCommit 覆盖的 genesis unit 恰含一条 `ak.realm.create`。因此它的设备**不在** genesis 内产生，而是在 provision 与 PCR genesis 都已接受之后，作为一条**普通后继 `ak.device.authorize`** 提交到同一个 PCR。这条后继 Event 走普通 Event admission（完整 `expected_revision`、checkpoint 与 signer evidence），不属于任何原子 native unit，因此不触发也不放宽 genesis unit 的 `events.len() == 1` 形状。

设备 possession 签名对象是 §5.2.1 的同一个 core 加 `applet_id`，完整成员集合为：

```json fragment
{
  "account_id": {"principal_id": "ak:did_core:webvh:zExampleManagedActorScid", "station_id": "ak:did_core:webvh:zExampleStationScid"},
  "device_id": "ak:device:...",
  "device_public_key_did": "did:key:...",
  "hpke_key": "z...",
  "algorithms": ["..."],
  "device_key_algorithm": "Ed25519",
  "authorized_by": "ak:did_core:webvh:zExampleManagedActorScid",
  "authorization_binding_kind": "applet_managed_delegation",
  "authorized_generation_ref": 7,
  "not_before": "2026-09-15T00:00:00.000Z",
  "expires_at": "2026-12-15T00:00:00.000Z",
  "scopes": ["..."],
  "recovery_session_id": null,
  "applet_id": "ak:applet:..."
}
```
签名输入是 `UTF8("ak.device_authorize_applet_managed_possession_proof.v1\n") || canonical_json(上述对象)`，`canonical_json` 按 [`../conformance/encoding.md` §2](../conformance/encoding.md)（JCS）。`algorithms` 必须先按 UTF-8 bytewise 排序去重；`account_id` 与 §5.2.1 同样从 Event envelope 的完整 account `actor_id` 注入，不是 payload 字段。本分支的 `expires_at` 与 `scopes` 是 payload required 的，因此在 transcript 里 MUST 为非 `null`；`recovery_session_id` 是规范化的 `null`；`authorized_generation_ref` MUST 等于接纳时刻该 PCR 的 `current_device_generation_ref`（示例中的 `7` 只是占位值）。wire 形态是 `device_authorize_applet_managed_possession_transcript`，见 §5.2.1 的 wire 形态段。

该分支的封闭约束（normative）：

- **`authorized_by` 自锚**：MUST 逐字等于 `Event.actor_id.account_id.principal_id`。授权该设备的是这个 managed principal 自己的 PCR controller key，不是 Applet 的 `service_id`、controller DID 或任何别的 principal；取 `service_id` 会引入一条本规范未定义的跨 principal authority 链路，并与 §3.3「Bot 是独立长期 principal，不复用 Applet service/controller identity」相悖。MUST NOT 使用设备 id。
- **有界委托**：`expires_at` MUST 存在且 MUST NOT 为 `null`，`scopes` MUST 非空。Applet-managed delegated device 不存在"永久、无限 scope"形态；这与 human / Agent 设备不同，因为持有该设备私钥的是 Applet 运行时，而不是 principal 本人。
- **`applet_id` 是撤销围栏载体**：MUST 逐字等于创建该 principal 的那条已接受 `ak.applet.managed_actor.provision` 所属的 exact Applet install。它使该设备能被 §15 的 install revoke fence 直接判定，而不需要在设备目录之外另建一张映射表。
- **不得跨分支复用**：该 payload MUST NOT 携带 `recovery_session_id` 或 `pairing_challenge_transcript_digest`；`registration_anchor` / `pcr_recovery` / `accepted_device` 三个分支同样 MUST NOT 携带 `applet_id`。
- **前置状态**：接受该 Event 前，该 PCR 中 `ak.applet.managed_actor.provision` 与 `applet_managed_control` genesis MUST 已 accepted，且其 exact Applet install MUST 仍为 active。provision 与 genesis 尚未接受，或 install 已被 fence 时 MUST fail closed，前者按普通依赖未满足处理，后者 code=`applet_revoked`。

### 5.3 Event proof key resolution（normative）

所有普通设备 Event 的 `proof.verification_method` MUST 是基于该 account actor principal 已验证、且满足操作 freshness / event-time 要求的 `did` 的 DID URL。receiver MUST 取 DID URL 的 bare `did`，用已登记 method adapter 验证并要求 `project(did) == Event.actor_id.account_id.principal_id`，再要求 fragment 逐字等于完整 `signing_device_id`（`ak:device:<uuid>`）；不得把 fragment 拼到 principal core，也不得把任何 core-plus-fragment 字符串当成 verification method。设备没有独立 DID，因此不得使用 candidate `did:key` 作为该字段。对 `authorization_binding_kind="accepted_device"` 的 authorize，`signing_device_id` 必须是 payload.`authorized_by`，不能是待授权 target device；因此 payload.`authorized_by` 在该分支下必然是设备 id，不是任何 principal DID。

该 Event proof 同时是 `accepted_device` 分支下完整 account actor、`authorized_by`、`not_before`、`expires_at`、`scopes` 的**唯一签名承载**（§5.2.2）：它覆盖完整 canonical Event bytes，而签名方正是选定这些值的批准设备。验签方 MUST 用它校验这些字段，MUST NOT 期望目标设备的 `device_signature` 覆盖它们。

**`applet_managed_delegation` 的签名方不是设备（normative）**：该分支的 `ak.device.authorize` 由 Applet-managed principal 自己的 DID controller method 签署，不由任何设备签署。因此其 `proof.verification_method` MUST 是该 managed principal 已验证 `did` 下的 **DID Document verification method** DID URL，fragment 是该 DID Document 中的 verification method fragment，**MUST NOT** 是 `ak:device:<uuid>`。receiver 仍 MUST 取 bare `did`、经已登记 method adapter 验证并要求 `project(did) == Event.actor_id.account_id.principal_id`。上一段「fragment 逐字等于完整 `signing_device_id`」只约束由设备签署的 Event，不适用于本分支；本分支同样 MUST NOT 由 principal core 拼 fragment，也 MUST NOT 以候选设备的 `did:key` 作为 verification method。

**本分支不使用 candidate overlay，也不得省略 `signer_resolution_evidence_ref`（normative）**：[`../conformance/encoding.md` §4](../conformance/encoding.md) 中「省略 `signer_resolution_evidence_ref` + unit-local candidate overlay」的豁免是一张**恰含两项的封闭表**——human PCR genesis 的 root create 加 founding-device authorize，以及 PCR-policy recovery 的 reanchor 加 replacement authorize。那两项成立的**唯一**理由是：signer 在该原子 unit 被接纳之前，尚不存在可被引用的 accepted signer projection。`applet_managed_delegation` 不满足这个前提：它的 signer 是该 managed principal 的 controller method，而 `ak.applet.managed_actor.provision` 冻结的 `initial_resolution`、`method_history_evidence` 与 `JCS(actor_id)` 的 current resolution typed current result 在本 Event 之前**已经**被接受，可引用的 accepted signer projection 是存在的。因此本分支 MUST 携带 `signer_resolution_evidence_ref`，MUST NOT 建立任何 unit-local candidate overlay，也 MUST NOT 与另一条 Event 组成原子 native unit。实现 MUST NOT 把本分支加进那张封闭表；那张表在 v1 **恰为两项**，把它扩成三项是本条明确禁止的结果。候选设备 key 也不需要 overlay：它由同一 payload 的 `device_public_key_did` 与 `device_signature` 自证持有，而 overlay 要解决的是**签名方**不可解析，本分支的签名方完全可解析。

- 对普通 Event，receiver 从当前 accepted PCR device directory 解析该 method；
- 对 `applet_managed_delegation` 的 authorize，receiver 从该 managed principal 已接受的 current resolution typed current result 解析 controller method；不查 PCR device directory（该目录此时可能为空），不建立 overlay，也不接受 provision 之外的 resolution 来源；
- 对 genesis unit 的第二条 authorize，以及 recovery unit 的 re-anchor 和 authorize 两条 Event，目录尚未包含 candidate。verifier 必须建立只在本次 unit 内可见的 candidate overlay。genesis 的 key 来自经 root 承诺的 descriptor；recovery 的 key 必须同时等于已验证 session 的 `requesting_device_public_key_did` 和 authorize payload 的 `device_public_key_did`。overlay 将规范 account DID URL/device fragment 映射到该 key，只提供验签材料，不授予权限。verifier 先验证对应 descriptor 或 accepted policy/session、payload/digest、possession signature 和全部 Event proof，全部成功后才原子写入 durable directory；
- 不得查询未接受的 projection，不得回退到同 fragment 的旧 key，也不得在验签前产生可观察目录状态。

### 5.4 后续设备配对（normative）

首设备存在后，新设备必须走 §2 pairing。新设备提供自己的 device/HPKE keys 和 §5.2.2 的 possession attestation；批准方必须是 PCR 当前 generation 中 active、未撤销的 accepted device，并对完整 authorize payload 签名。结果 `authorization_binding_kind="accepted_device"`，`authorized_by` 是**批准设备自己的 `device_id`**（完整 `ak:device:<uuid>`），不是该设备所属 principal 的 DID；authorization evidence 必须能定位批准设备的 accepted authorize Event 与 generation。

服务端可以中继 challenge 和 Event，但不得生成、替换或签署新设备 key material。旧 generation、已撤销或具有独立已验证冲突证据的 device 的批准一律 fail closed；仅存在同一旧 generation 的另一个 pending/rejected recovery unit 不构成设备冲突，也不得撤销已 committed generation。该边界由 `ak.vector.identity.device_reanchor.v1` 验证。企业额外审批只能作为显式启用的 PCR policy 叠加，不能成为个人账号首次建 PCR 的默认第二方。

#### 5.4.1 目标设备装配前的强制校验（normative）

§5.2.2 的 attestation 签名承诺了完整 `account_id`，但它不能保证“批准方最终把这份 attestation 用在了哪条被接受的 Event 上”。这一半只能由目标设备**事后核对已被接受的授权**保证。因此：目标设备在**完成本地身份装配之前**（即在把该 `device_id` 与 device key 当作某 principal 的成员使用、拉取或安装该 principal 的 E2EE 材料、发布 KeyPackage、写入任何 `ak.self.*` 状态之前），MUST 先取回被接受的那条 `ak.device.authorize` Event 并逐项校验：

1. Event `payload.device_signature` 与自己产出的 attestation `device_signature` **逐字节相同**；
2. `payload.device_public_key_did`、`payload.hpke_key`、`payload.algorithms` 与自己 attestation 中的对应值**逐字一致**（含 `algorithms` 的排序与去重结果）；
3. `payload.device_id` 等于自己的 `device_id`；
4. `payload.authorization_binding_kind` 为 `accepted_device`；`proof.verification_method` MUST 是该 account actor principal 已验证 `did` 下的 DID URL，取其 bare `did` 经已登记 method adapter 验证后 MUST 满足 `project(did) == Event.actor_id.account_id.principal_id`，且 fragment 逐字等于 `payload.authorized_by`；不得从 principal core 与 device fragment 拼接 verification method；
5. Event 的完整 `actor_id.account_id` 与自己 attestation 中已签的 `account_id` **逐字节相同**，并且等于自己那份 pending account handoff 所绑定的 `AccountId`；同 core 异 Station 必须拒绝。该值 MUST 同时在装配前显式呈现给用户，不得默默采纳服务端给出的任何账号；但判定权威是上述逐字节比较，MUST NOT 降级为“用户点过确认”。

任一项不符，目标设备 MUST fail closed：MUST NOT 使用该身份、MUST NOT 安装或请求该 principal 的任何密钥材料、MUST NOT 发布 KeyPackage，并 MUST 向用户告警（提示该配对已被篡改或指向了非预期账号）。这条校验同样阻断“批准方把 attestation 用到另一个 principal 下”的场景，而且现在是双重封闭：攻击者已经无法让自己账号下的 gate 接纳这份 attestation（§5.2.2 的签名 `account_id` 与批准方账号不等即拒绝），即使某个实现漏了那一道，目标设备在装配前也会因第 5 项拒绝。

**取回路径**：`ak.open.device_pairing.read.status.v1`在 `state="authorized"` 时返回 `authorized_event_ref`，是该校验的入口；目标设备被授权后即已是该 principal 的 accepted device，**读取自己的 PCR 控制流即可取到该 Event 的完整 canonical bytes 与 proof 完成校验**，不需要新增读取面；在完成本节校验之前，该读取是它唯一允许对该 principal 发起的操作。取不到 Event、Event 尚未被 accepted RealmCommit 覆盖、或读取被拒时，MUST 停在 fail-closed 状态并重试/告警，MUST NOT 先装配再校验。

### 5.5 Device trust projection（normative）

设备 trust state 仅由 accepted PCR evidence 决定：registration-anchor genesis、accepted-device authorize、PCR-policy re-anchor、revoke/list update 与 accepted RealmCommit/checkpoint。DID resolver 不提供设备目录或 generation basis。

负责建立 **账号内部 PCR projection** 的 origin Station 必须从自己的 durable accepted store 取得 `principal_genesis_receipt + authorization_chain + accepted_commit + current_device_projection`。`authorization_chain` 在此不是只挑成功授权 hop，而是从 genesis 到 current RealmCommit、足以重放目标 projection 的完整相关 PCR control history，包含 authorize/revoke/reanchor/list moves；origin Station 自行重放并要求 target status=`active`、`authorized_generation_ref == current_device_generation_ref`、generation status=`active`，再与 current projection 逐字段比较。外层 source 对“未撤销”的裸断言不构成 authority。

Arkret v1 没有让远端 verifier 证明 source 已完整披露 PCR 历史的协议。因此，依赖远端全历史无遗漏才能建立安全结论的 first-device active-series recovery 分支是 unsupported，MUST fail closed；实现不得删除校验后无条件成功，也不得用 cursor、checkpoint、receipt、Snapshot、单源签名或私有 sidecar 替代。已有 accepted device 只可使用其它独立闭合、明确授权的恢复路径。Event payload、proof 与 principal/device/key/generation/checkpoint 任一缺失、gap、冲突或 stale 均保持 `unresolved`，不得 TOFU。

上述 PCR 重放要求 **不适用于跨账号 recipient 或普通 peer transport ingress**。跨账号设备信任遵守 §8.2 / §8.3：只通过既有关系门控 `keys/query`——由自己 Station 验证 origin Station signed `device_projection_attestation` 后投影出的 `device_projection`——以及用户侧验证建立，MUST NOT 在该面披露或要求完整 PCR history。Signal source Station 验证自己托管的 exact account-device current authority；destination 只执行 [`sync/signal.md` §3/§4.3](../sync/signal.md) 的 peer transport admission，不重新认证远端设备；recipient 独立验证 current device trust、producer signature 与 MLS binding。peer HTTP 签名不替代 recipient 的设备信任，destination 缺少远端 PCR 或设备目录也不构成拒绝合法 relay 的理由。

#### 5.5.1 Device authorization typed current result 的封闭 value（normative）

一台设备在 PCR 内的当前授权事实是一个 typed current result，family 名 `device_authorization`，subject 是 `payload.device_id`。account 由该 PCR 自身定位，value **MUST NOT** 另设 `account_id` / `principal_id` 副本。一条被接纳的 `ak.device.authorize` 以**整体置换**写入该 result；同一 `device_id` 的后继 authorize 覆盖前值，不做局部 patch。

封闭 value 恰由下列成员组成，不多不少：

| 成员 | 来源 | 说明 |
| --- | --- | --- |
| `device_public_key_did` | payload 逐字 | §8.2 的 `device_projection.device_signing_key_did` 是同一值在 keys/query 面的既有名，不是第二个事实 |
| `hpke_key` | payload 逐字 | |
| `algorithms` | payload 逐字 | 已按 UTF-8 bytewise 排序去重 |
| `device_key_algorithm` | payload 逐字 | |
| `authorized_by` | payload 逐字 | |
| `authorization_binding_kind` | payload 逐字 | |
| `authorized_generation_ref` | payload 逐字 | 见 §5.5.2；**MUST NOT** 由 reducer 读前态产生 |
| `not_before` | payload 逐字 | |
| `expires_at` | payload 逐字（可空、可缺） | 与 `not_before` 合称 `authorization_window`，那是同一对值在服务面的呈现名，不是第三个成员 |
| `scopes` | payload 逐字（可缺） | |
| `applet_id` | payload 逐字（可缺） | |
| `recovery_session_id` | payload 逐字（可缺） | |
| `pairing_challenge_transcript_digest` | payload 逐字（可缺） | §5.2.2 要求 accepted payload 持久保存它 |
| `device_signature` | payload 逐字 | 同上：stage 清理后重验 target signature 的材料 |
| `device_authorize_event_id` | 本 Event envelope 的 `event_id` | 唯一来源；payload **MUST NOT** 携带它 |

下列值 **MUST NOT** 成为该 result 的成员：

- `device_status`——它不是存储轴，见 §5.5.3；
- `attested_at` 与证明自己的 `expires_at`——它们是 §8.2 attestation 的新鲜度坐标，属于那份签名断言而不属于设备事实；
- `authorization_window`——它是 `(not_before, expires_at)` 的成对呈现名；
- 任何 `account_id` / `principal_id` 副本——subject 与 envelope 已经唯一确定它们。

**attestation 是下游，不是定义。** §8.2 的 `device_projection_attestation` **MUST** 被理解为「origin Station 对本 result 与 §5.5.4 generation result 的一次折叠结果所作的签名断言」：它覆盖的 `device_signing_key_did` / `hpke_key` / `device_authorize_event_id` / `authorized_generation_ref` 逐字取自本 result，`device_status` 是 §5.5.3 的折叠，`authorization_window` 是 `(not_before, expires_at)` 的成对呈现，`attested_at` 与证明 `expires_at` 由签发这次断言的动作产生。attestation 多出来的成员 **MUST NOT** 反向定义本 result 的封闭 value；attestation 不携带的成员（如 `device_signature`、`scopes`）也不因此不被存储。

#### 5.5.2 Generation 进入 wire，reducer 派生不读前态（normative）

`authorized_generation_ref` 由 `ak.device.authorize` 的 **payload 携带**，**MUST NOT** 由 reducer 从前态读出后写入。

裁决理由：v1 的两套 reducer 派生名词表——`result_writes[].result_projection.value_projection.members[].derivation` 与 `result_writes[].derived_members[]`——收录的都是本 Event（payload + envelope）的纯函数；唯二的前态读取例外是两个 authority-root successor counter，而它们之所以被允许，是因为那次写入用 `expected_state_digest` 把整个前态 CAS 冻住了，后继值没有任何作者可选空间（[`../authz/capabilities.md`](../authz/capabilities.md)）。`ak.device.authorize` 没有这样的冻结，读前态的结果在两个实现之间不可保证同值。把 generation 放上 wire 则四支处处可判定：

- `registration_anchor`：**MUST** 等于 `1`。写它的那次 `pcr_genesis_unit` 原子接受同时把 `current_device_generation_ref` 初始化为 `1`（[`../identity/account-lifecycle.md`](../identity/account-lifecycle.md) 第 7 步），两者 **MUST** 一致。
- `pcr_recovery`：**MUST** 等于同一 recovery unit 内 `ak.device.reanchor` 的 `new_device_generation`。
- `accepted_device`：**MUST** 等于接纳时刻该 PCR 的 `current_device_generation_ref`，也即批准设备自己的 `authorized_generation_ref`（§5.4 已要求批准方处在当前 generation）。
- `applet_managed_delegation`：**MUST** 等于接纳时刻该 PCR 的 `current_device_generation_ref`。

接纳方 **MUST** 在接纳前逐条校验上述等式，不等即 fail closed，按 §5.4 已有的 generation fence 形态拒绝。payload 携带的因此是一个**被接纳方用一条等式对已提交状态判定的断言**，与 `ak.device.reanchor` 已经携带的 `previous_device_generation` 同型：后者同样是 producer 自报的前态坐标，同样由等式判定，并不因为自报而成为第二个事实来源。

这与 `ak.device.revoke` 的「producer 不得自报 derived pending selector」**不冲突**，界线是：**可由接纳方用一条等式对已提交状态判定的坐标**可以自报（generation）；**只有 reducer 在本次事务中才产生、外部无从先验的选择子**（revocation pending 记录所指的授权实例与 acceptance 序，见 §5.5.3）不可自报。两者的差别是「可否在接纳前被等式判定」，不是「是否叫 derived」。

签名覆盖：`registration_anchor` / `pcr_recovery` / `applet_managed_delegation` 三支的 possession transcript 把本字段登记为 `device_authorize_possession_core` 的必需成员（§5.2.1），因此候选设备连同本字段一起签名。那三个 transcript 覆盖的是 **authorization core 加注入的 `account_id`**，并排除 `device_signature` 与一切 digest / proof material，因此它们**不是**完整 payload 的 `allOf`；payload 的封闭成员表与 transcript 的成员表是两张表，各自由 schema 独立收口。`accepted_device` 的 §5.2.2 target proof 是一个**显式封闭的八成员对象**，本字段**不**在其中——它与 `authorized_by` / `not_before` / `expires_at` / `scopes` 同处，由批准设备覆盖完整 canonical Event bytes 的 Event proof 承担；§5.2.2 的封闭对象成员表因此不变，目标设备也不需要在 §5.4.1 的装配前比对中新增一项（它的 attestation 本就不承诺 generation）。

设备 generation **MUST NOT** 塞进 `object_*` 公共元数据派生名：公共名的规范输入不含 PCR generation。

#### 5.5.3 `device_status` 是读侧折叠，不是存储轴（normative）

§14.1 的 lifecycle 六值是**读侧折叠**，不是任何 typed current result 的存储成员，也没有对应的 `transition` 投影。

裁决理由：`revocation_pending → revoked` 与 `revocation_pending → 清除` 两条边由覆盖该 revoke Event 的 accepted RealmCommit 的 committed command result 决定（§2.2），`generation_fenced` 与 `expired` 是与当前 generation、当前时刻的比较，`conflicted` 是对该设备自身已验证冲突证据的判断。把这六值写成存储轴，就得为一台**只有入边**的状态机登记载体——那等于把「pending 永不收敛」写进协议。

折叠输入恰为四项：该 `device_id` 的 `device_authorization` result（§5.5.1）、该 `device_id` 的 `device_revocation_proposals` keyed set（下文）、该 PCR 的 `device_generation` result（§5.5.4），以及该设备自身的已验证冲突证据。判定按下列**固定优先序**取第一个成立者，两个实现因此对同一输入得同一值：

1. `revoked`——存在至少一个该设备的 revocation proposal，其覆盖 RealmCommit 的 committed command result 为终局接受。
2. `conflicted`——存在该设备自身的已验证冲突证据。**MUST NOT** 从 pending/rejected re-anchor 候选数目派生（§14.1）。
3. `generation_fenced`——`authorized_generation_ref != current_device_generation_ref`。
4. `revocation_pending`——存在至少一个该设备的 revocation proposal，其覆盖 RealmCommit 尚未给出终局 command result。
5. `expired`——`expires_at` 非空且 `now >= expires_at`。
6. `active`——以上皆不成立，且 `now >= not_before`。`now < not_before` 的设备尚未生效，按 §8.2 的非枚举失败形态省略 row，**MUST NOT** 报成 `active`。

`verified | unresolved | stale` 同样是折叠（判定输入见 §5.5 的 evidence 规则），与 lifecycle 相互独立。§14.1 「两维 **MUST** 分开投影」中的「投影」在此指**分别折叠、分别呈现**，**MUST NOT** 被读成「分别存储」；该句禁止的行为不变：不得用 verification 值代替 lifecycle，也不得因 evidence unresolved 省略 lifecycle。

**Revocation proposal 是不可变 keyed set。** 一条被接纳的 `ak.device.revoke` 向 family `device_revocation_proposals` 追加**一个元素**：subject 为 `payload.device_id`，元素 tag 是该 revoke Event 自身的 canonical dot（即 `proposal_event_id`），元素 value 是该 Event 的完整 payload。元素一经写入不可变，也不被第二条 Event 改写——`revocation_pending` / `rejected` / `revoked` 三态是**该元素与它的覆盖 command result 的折叠**，收敛载体因此是 [`../identity/security-transactions.md` §3](../identity/security-transactions.md) 已经要求持久化的那份 transaction 终局结果，不需要第二条 Event，也不需要一种非 Event 生产者的登记形态。

`ak.schema.device_revocation_state.v1`（[`device-revocation-state.schema.json`](../../artifacts/schemas/device-revocation-state.schema.json)）的三支 `oneOf` 是该折叠的**结果形态**，不是 Event 的写入形状：其中 `target_device_authorize_event_id` 与 `target_device_generation_ref` 由元素与同 `device_id` 的 `device_authorization` result 连接得到，`accepted_at` / `acceptance_seq` 由接纳该元素的事务给出，`committed_at` 与 `denied_actions` 由覆盖 command result 给出。producer 因此确实不自报任何 derived pending selector。

「多个 transaction 独立计数，reject 一条不清另一条」（[`../security/server-threat-model.md`](../security/server-threat-model.md)）在该形状上是**结构性**成立的：每条 proposal 是一个独立元素，每个元素只折叠自己的覆盖 command result，一条被 reject 不改变另一条的折叠输入。

#### 5.5.4 Generation result 与 genesis 同批登记（normative）

PCR-local generation 是一个 Realm 级单值 typed current result，family 名 `device_generation`，selector 除 kind 外无成分（一个 PCR 一份）。封闭 value 恰为 `current_device_generation_ref` 一个成员。

写入方有两个，**都是已登记的 Event kind**：

- `ak.device.authorize` 且 `authorization_binding_kind == "registration_anchor"`：置为 `1`。该 Event 是 `pcr_genesis_unit` 的两条成员之一（有序 `[ak.realm.create, ak.device.authorize]`，见 [`../identity/key-management.md`](../identity/key-management.md)），因此「generation 的初始值由 genesis unit 而非任何已登记 Event 写入」**不成立**：写它的正是这条已登记 Event，unit 只是它被原子接纳的方式。登记这一支不会产生「初始值没有写入方」的 family。
- `ak.device.reanchor`：置为 `payload.new_device_generation`。接纳方 **MUST** 同时要求 `payload.previous_device_generation` 等于当前值，且 `new_device_generation` 是其直接后继。

`device_generation_status`（`active | conflicted`，见 [`keys-operations.schema.json`](../../artifacts/schemas/keys-operations.schema.json)）**不是**该 result 的成员：它的 `conflicted` 与 §5.5.3 的设备级 `conflicted` 同类，是对已验证冲突证据的读侧折叠，没有 Event 生产者。`keys/query` 响应里的 `device_generation_state` 因此是 `(current_device_generation_ref, 折叠出的 status)` 的成对呈现，不是一份两成员的存储值。

generation ref **MUST NOT** 等于或派生自 DID `versionId`；该既有规则不变。

### 5.6 Privacy-Preserving Push

Arkret 推送通道设计的目标是在不向 push gateway / vendor、上游 Station sync surface、网络中间人或第三方 SaaS 控制面泄露 Account/Realm 身份与通知内容的前提下，把"有事可投递"的最小信号送达终端。这是 [`discovery/push-notifications.md`](../discovery/push-notifications.md) 与 [`crypto-media/webrtc-signaling.md`](./webrtc-signaling.md) 中"pairwise pseudonym `push_target_id`"语义的协议层定义。独立公共 Gateway 为完成 provider delivery 必须取得原始 provider route 时，只可走 `push-notifications.md` §3.4 的认证 handoff，并作为按 source Station 强隔离的受信数据处理方持有；这不是 notify payload 的放宽，也不声称对 Gateway 隐藏重复 provider token 的密码学相等性。

#### 5.6.1 `push_target_id` 派生与作用域

- 作用域：`per (account_id, device_id, push_route)`。`account_id` 是认证 session 中完整且不可拆分的 `AccountId`；同一 principal 在两个 Station 上注册同一物理设备时，MUST 使用互相不可链接的 `push_target_id`。`push_route` 标识同一设备上不同 push 通道（如 `apns_main`, `fcm_voip`, `webpush_default`），允许同一设备针对不同通道发布相互不可链接的伪名。
- 长度与编码：`push_target_id` 的唯一 v1 wire 形态是 `ak:pseudonym:push:<tag>`，其中 `tag` MUST 是完整 32-octet HMAC-SHA256 输出的 canonical unpadded Base64URL 编码，固定 43 个 ASCII 字符。接收方 MUST 解码为恰好 32 octets，并要求重新编码后的字符串与原 `tag` 逐字相等；不得截断、扩展、补 `=` padding 或接受可解码但非 canonical 的替代字符串。其 JSON Schema lexical pattern 为 `^ak:pseudonym:push:[A-Za-z0-9_-]{42}[048AEIMQUYcgkosw]$`。
- 生成方与派生：`push_target_id` MUST 由接收 Station 按 [`discovery/push-notifications.md` §2.2](../discovery/push-notifications.md) 的派生 profile 生成——`HMAC-SHA256(service_push_secret[salt_epoch_id], canonical_json({account_id, device_id, push_route_id, salt_epoch_id}))`——并经注册响应返回给设备（`push-notifications.md` §3.1，这是该伪名唯一的契约通路）。其中 `account_id` 使用其 closed JSON 的 JCS bytes；设备 MUST 使用服务端派生值，MUST NOT 自行铸造 wire 形态的 `push_target_id`；设备 MAY 通过 `ak.device.push_route` account-private state event（§5.6.2）携带 / 核对该值。
- 不可推导性：`push_target_id` MUST NOT 由公开 DID、`device_id`、平台 push token、handle、邮箱或电话号码可推导。`service_push_secret` 原值绝不能上 wire，仅持有公开输入的一方无法重放该派生。rotation 周期与旧 / 新伪名可逆映射的短暂保留窗口见 [`../conformance/scalability-constraints.md`](../conformance/scalability-constraints.md) §6（默认 rotation ≤ 90 天；可逆映射保留 ≤ 24h 或与单条未投递消息 TTL 取较短者）。
- 标识形态：所有操作响应、notify DTO 与 `ak.device.push_route` actor-private Event 都 MUST 使用上述完整 typed form。`common-ids.schema.json#/$defs/push_target_id` 是唯一 schema 定义；不得在领域 schema 复制 regex，也不存在 raw Base64URL、短 token 或另一种兼容形态。该形态由 `id-kind-registry.json` 的 profile-scoped `pseudonym` 外层空间授权，不新增第二个 ID kind。

#### 5.6.2 注册与撤销

- 目标 account-private effect 的 storage owner、唯一键、value projection、field maintenance、exact retry 与零副作用拒绝由 [`../models/actor-private-effects.md` §3.3](../models/actor-private-effects.md#33-push-route) 和 canonical `contract-registry.json` 共同闭合。其 composite unique key 是 `(payload.account_id, payload.device_id, payload.push_route)`，family 固定使用 `server_revision_cas`。每条 `ak.device.push_route` Event MUST 携 `expected_server_revision`：从未写入的 route 以 `0` 创建；接受方在同一原子事务比较当前 revision，相等时存储 `revision = expected_server_revision + 1`，不相等时返回 `cas_conflict` 且零写入。`expected_server_revision` 是 account-private merge 载体，不是 authority-commit precondition；该 Event MUST NOT 携共享 reducer `preconditions` / `expected_revision`，也不进入 shared Realm RealmCommit coverage。
- active 写入是闭合 whole-value：`(account_id, device_id, push_route, expected_server_revision, push_target_id, push_gateway_id, encryption_key, capabilities, expires_at?, updated_at?)`。`account_id` MUST 等于 Event `actor_id.account_id`，且 `push_target_id` MUST 等于该账号认证 session 的注册响应返回值；`push_gateway_id` MUST 是 canonical `did_core_id`，实现不得另收 `push_gateway_did`。active 形态 MUST 省略 `revoked`。
- 撤销写入是互斥的闭合 tombstone：`(account_id, device_id, push_route, expected_server_revision, revoked=true, updated_at?)`。它 MUST 省略 `push_target_id`、`push_gateway_id`、`encryption_key`、`capabilities` 与 `expires_at`；撤销由 private effect unique key + revision 定址，不得为定位旧值而重传旧 `push_target_id` 或 provider 秘密。接受后 service / gateway MUST 立即停止接受旧伪名。
- 轮换是对同一 typed current result 的下一条完整 active 写入，不是局部 patch：客户端 SHOULD 在 push token 变化、设备恢复、Out-of-band 重新登录、或自定义 rotation 周期（默认 ≤ 90 天）时以当前 revision 和新注册响应的完整 active tuple 提交。create(revision 0) → rotate(revision 1) → revoke(revision 2) 三次成功写入后，typed current result revision 固定为 3；缺失 revision、stale retry 与同 revision sibling 均 fail closed。
- 长期不可恢复性：服务方在丢弃旧 `push_target_id` 后 MUST NOT 保留可把旧 / 新伪名链接回同一 `(account_id, device)` 的索引；只允许在 rotation 时短暂保留以便迁移未投递消息。短暂保留期 MUST ≤ 24h，或与单条未投递消息 TTL 取较短者；超过该窗口 MUST 物理删除旧 `push_target_id`、provider 路由材料及可逆映射。隐私 GC 仍 MUST 永久保留按上述 typed current result subject 定址的 revision high-water 与最小幂等/审计摘要（subject digest、revision、outcome）；不得保留旧 target 明文，也不得因 GC 把 revision 退回 0 而让离线旧写复活。
- **条数与注册速率上限（normative）**：单一 `(account_id, device_id)` 维度下并存的 active `push_route` 条数 MUST ≤ 16（v1 wire 上限；登记于 [`../conformance/scalability-constraints.md` §6.1](../conformance/scalability-constraints.md)），超过时服务端 MUST 拒绝新 `ak.device.push_route` 注册（`push_route_limit_exceeded`）。同一维度的 push-route 注册 / 轮换 MUST 限速，默认窗口 60s 内 ≤ 8 次写入；超额时返回限速响应并记内部审计 `push_route_registration_rate_limited`。该上限防止单设备通过无界 push_route 放大注册状态或制造可链接性面。

create / rotate / revoke、stale sibling、exact replay 与隐私 GC 的可执行合同由 `ak.vector.push.device_route_revision_cas.v1` 固定。

#### 5.6.3 不可链接性要求

- 同一 `principal_id` 在不同 AccountId、不同设备或不同 push route 上的 `push_target_id` MUST NOT be linkable by push gateway / 第三方 transport（除非两侧自愿持有相同源 secret）。受托 Station sync surface MAY 在自己的授权上下文内持有从 exact AccountId 到本服务本地 push queue 的短期索引，但不得把该 Account 映射导出给 Push Gateway / vendor。`push-notifications.md` §3.4 是 provider route 的封闭例外：公共 Gateway 可在一个 authenticated source-Station tenant 内取得原始 provider token，但 MUST NOT 建立跨 Station token equality index、合并 installation、共享加密键或向另一个 tenant 暴露查询结果；这是强租户隔离和运营信任保证，不是跨 tenant 不可关联的密码学证明。
- 同一设备的两条 `push_route` 的伪名 MUST 互相独立；其中一条被泄露不得让攻击者推导另一条。
- 跨 Realm 投递 MUST 使用同一 `push_target_id`（按 device 而非按 Realm），但 push payload 内不得携带 plaintext `realm_id`/`strand_id`/`message_id`；目标拆分由 device 端解 envelope 后完成。

#### 5.6.4 Push Payload 形态

- 协议层 push payload MUST 视作 `encrypted-envelope.schema.json` 形态或等价 ephemeral encrypted blob。AAD MUST NOT 包含可链接 wire 字段，仅可携带 routing-only `wakeup_kind`（参见 `discovery/push-notifications.md`）。
- gateway / vendor MUST NOT 解密 payload。任何"丰富推送"扩展（如显示发件人）都属于 vendor-side 行为，需要 Realm 与 device 双方明确 opt-in，并对应单独的 plaintext-visible service profile，不在 v1 默认互操作范围。

#### 5.6.5 与其它子系统的边界

- Station sync surface：以 `push_target_id` 作为 push fanout 索引。由 joined-member ActorId 确定的目标 Station MAY 在运行时持有 `account_id + device_id + push_route -> push_target_id` 映射以完成投递；该映射不得暴露给 Push Gateway / vendor，日志、导出、法定披露和跨服务复制 MUST 脱敏或失效化。不是 `account_id.station_id` 的服务不得保留可逆映射。
- WebRTC 通话邀请（`webrtc-signaling.md` §9 incoming-call wakeup）通过同一 `push_target_id` 触发；payload 仍走 §5.6.4 加密通道。
- 推送规则（`push-notifications.md` §4 keyword / member_count 等）以 `push_target_id` 为目标但 MUST 在不解密 payload 的前提下完成评估，或在 E2EE Realm 中由设备本地评估，详见对应文档。

## 6. Device List Sync

任何设备新增、撤销、签名更新或算法更新，MUST 产生 `ak.device.list_update` event。该 event 是 principal control stream 中的 actor-private durable identity state；若使用 Event Envelope，顶层 `realm_id` MUST 是目标 principal 的 `principal_control_realm_id`。它不进入任一共享 Realm 控制面 RealmCommit coverage；共享 Realm 只能通过 MLS Welcome / Remove、device trust proof 或 explicit membership / KeyPackage event 感知其结果：

Account Subscribe 的聚合提示 `delta.device_lists` 与本 event payload 不是同一 DTO：前者固定为 `{changed: principal_did[], left: principal_did[]}`，只指出哪些 principal 的权威设备列表需要刷新或清除；后者才携带该 principal 的具体 device 变化。实现 MUST NOT 把 `device_id` 写入 `delta.device_lists.changed/left`，也不得把聚合提示当作完整设备清单。

```json fragment
{
  "kind": "ak.device.list_update",
  "payload": {
    "changed_ids": [
      "ak:device:01964137-0000-7000-8000-000000000000"
    ],
    "left_ids": [
      "ak:device:01964138-0000-7000-8000-000000000000"
    ],
    "stream_id": "devstream_42"
  }
}
```
客户端 sync MUST 暴露 device list delta。E2EE 客户端在向 principal 发送新加密内容前，MUST 查询或同步其最新 device list。

## 7. To-Device Messages

To-device message 是面向具体 principal/device 的非 Realm 持久消息，用于密钥交换、secret sharing 和通知。

To-device wire object MUST 使用 `DeviceMessageEnvelope`，而不是持久 `EventEnvelope`。标准 to-device kind 名称（`ak.secret.*`、`ak.read_cursor.update` 与 registry 明确的 actor-private update）在 to-device 通道中出现在 `kind` 字段；它们不得推进任何 stream 的 `RealmCommit.stream_position`、Realm reducer checkpoint 或持久 timeline。

`DeviceMessageEnvelope` 基本字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `device_message_id` | `id:device_message` | required | 发送方为一个逻辑消息分配的稳定 UUIDv7 typed ID；服务端在重试、分页和重投时 MUST 原样保留。接收端按完整 closed sender identity 与 `device_message_id` 去重。 |
| `kind` | `string` | required | 消息 kind，例如 `ak.secret.request`。标准 to-device kind 由 `device-message.schema.json` 的闭合 dispatch 定义，不得登记成 Event.kind。 |
| `sender_account_id` + `sender_device_id` | `AccountId` + `id:device` | conditional | human device sender；完整账号与设备共同标识发送端，并与完整 `sender_agent_*` 三元组、`sender_id` 严格 XOR。 |
| `sender_agent_id` / `sender_agent_verification_method` / `sender_agent_key_authorize_event_id` | `did_core_id` / `did_url` / `id:event` | conditional | Agent sender 的完整 signer-evidence 三元组；`sender_agent_id` 是唯一 Agent 身份 carrier，不得再携同值 principal 镜像。 |
| `sender_id` | `did_core_id` | conditional | 受限 Station sender。只允许 `device-message.schema.json#/$defs/actor_private_update_kind` 闭集，且 `sender_id == recipient_account_id.station_id`；不得自报 holder sender 身份。 |
| `recipient_account_id` | `AccountId` | required | 接收方完整账号；MUST 逐分量等于投递路径中的目标账号。 |
| `recipient_device_id` | `id:device` | required | 接收设备；MUST 等于投递路径中的目标设备。 |
| `sent_at` | `datetime` | required | 发送时间。 |
| `expires_at` | `datetime` | required | 队列过期时间；不得晚于该 kind/profile 声明的 TTL 上限。 |
| `content` | `object` | required | 类型相关内容；私密内容 SHOULD 端到端加密。 |

`device_message_id`、closed sender branch、`recipient_account_id` 和 `recipient_device_id` MUST 被签名、device proof 或加密 AAD 覆盖。发送接口的 `messages.{principal_id}.{device_id}` 是当前认证 Station 内显式登记的局部队列坐标；服务端在入队前 MUST 以当前 Station 补全目标 `AccountId`，不得跨 Station 解释该标量。接收端 MUST 拒绝 envelope 目标与当前登录完整账号或设备不一致的消息。

发送方 MUST 在第一次构造逻辑消息时分配 `device_message_id`，应用重试、HTTP batch 重试和服务端重投都 MUST 沿用该值；重新分配 ID 表示新的逻辑消息，接收端 MUST 独立处理。服务端 MUST 以完整 closed sender identity 与 `device_message_id` 维护至少覆盖队列 TTL 与短 grace period 的幂等记录：human device 使用 `(sender_account_id,sender_device_id,device_message_id)`，Agent 使用 `(sender_agent_id,device_message_id)`，Station service 使用 `(sender_id,device_message_id)`。相同 canonical target intent 重试返回既有入队结果且不得新增队列项；同 key 但 `kind`、recipient、`expires_at` 或 `content` 不同，MUST 以 `duplicate_conflict`（reason `device_message_id_conflict`）拒绝整个发送请求且不得入队任一冲突版本。canonical target intent 包含 `device_message_id`、`kind`、当前且仅当前 sender 分支的全部字段、`recipient_account_id`、`recipient_device_id`、`expires_at` 与 `content`；不含服务端物化的 `sent_at`、`unsigned` 或 HTTP `Idempotency-Key`。

`sender_id` 只表示 Station 对 holder actor-private CAS typed current result 已接受 revision 的内部队列物化者，不把 service 冒充成 holder，也不授予任意 service 发送普通 to-device kind 的能力。该分支不走 holder device revocation gate，不排除所谓 origin device，而是 fanout 到 holder 的全部 active devices；service identity 由当前 authenticated Station transport / service resolution 绑定，MUST NOT 作为可跨服务转交的 bearer delegation。`ak.self.device_messages.command.send.v1` 是规范客户端 surface，MUST 拒绝任何试图提交或诱导物化 service sender 的请求；只有 Station 内部 actor-private materializer 可以产生该分支。

To-device 消息是短期队列对象，不是长期 Event history。发送方 MUST 设置 `expires_at`；服务端 MUST 拒绝缺失 `expires_at`、已经过期、早于 `sent_at` 或超过当前 service / Realm / profile TTL 上限的消息。默认最大队列 TTL 为 24 小时；高安全 profile SHOULD 使用更短值。标准验证请求仍受第 8.2 节约束，`request.expires_at` MUST be no later than `timestamp + 10m`。过期消息 MUST 从投递队列中清除，`GET /_arkret/self/device_messages` 不得返回；服务 MAY 仅保留最小幂等记录和脱敏审计摘要到 `expires_at` 后的短 grace period。

发送接口：

```http
POST /_arkret/self/device_messages
Authorization: Bearer <token>
Idempotency-Key: <opaque-string>
Content-Type: application/json
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Idempotency-Key` | header | `string` | required | 发送方生成的幂等键，长度 1..128；服务端 MUST 以 `(sender, Idempotency-Key)` 去重，重复键但 body canonical hash 不同 MUST 拒绝。 |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前 principal 与发送设备。 |
| `messages` | body | `object` | required | 收件人 principal 到 device 消息的映射。 |
| `messages.{principal_id}` | body | `object` | required | map key MUST 是 `did_core_id`（`ak:did_core:<method>:<core>`），不是 bare DID、AccountId 或 ActorId JSON。 |
| `messages.{principal_id}.{device_id}` | body | `object` | required | 目标设备消息；`{device_id}` MUST 是完整 `id:device` wire key。 |
| `messages.{principal_id}.{device_id}.device_message_id` | body | `id:device_message` | required | 发送方分配的稳定逻辑消息 ID；服务端 MUST 原样复制到 `DeviceMessageEnvelope.device_message_id`。 |
| `messages.{principal_id}.{device_id}.kind` | body | `string` | required | to-device 消息 kind，例如 `ak.secret.request`。 |
| `messages.{principal_id}.{device_id}.expires_at` | body | `datetime` | required | 队列过期时间；服务端物化 envelope 后必须复制到 `DeviceMessageEnvelope.expires_at`。 |
| `messages.{principal_id}.{device_id}.content` | body | `object` | required | 消息内容；私密内容 SHOULD 端到端加密。 |

**Station-local 边界（normative）**：本 `ak.self.device_messages.command.send.v1` 请求在认证绑定的被调用 Station 内寻址；`principal_id` 与该 Station 组成目标本地 AccountId，设备 MUST 来自该账号当前已接受的 device projection。队列、发送方幂等键、投递结果与接收 cursor MUST 同时受该 Station-local account 边界约束，同 DID 在另一 Station 的设备或消息不能被合并或命中。body 不承载远端 Station 路由，接收方 MUST NOT 从 principal DID、DID Document 或当前 handle 猜测跨 Station 目标；非本地可投递设备按 `unknown_devices` 处理。该有边界的 principal map 不替代 Event / membership / Relation 的完整 ActorId，也不得把 ActorId JSON 编成 map key。`delivered` / `unknown_devices` 使用同一 `did_core_id -> device_id` key grammar。

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `delivered` | `object` | required | 已入队或已投递设备的 typed map；没有结果时为 `{}`。 |
| `unknown_devices` | `object` | required | 无法识别或不可投递设备的 typed map；没有结果时为 `{}`。 |

**Partial-success / 全局失败语义（normative）**：

- **整体拒绝**（请求级失败：认证 / 授权失败、`Idempotency-Key` 冲突、所有目标 envelope 缺 `expires_at` / 已过期 / 超 TTL 上限、body 非 canonical）MUST 走 HTTP 错误响应（4xx，按 [`../sync/api-conventions.md`](../sync/api-conventions.md) Problem Details）；此时不入队任何消息。
- **部分成功**（请求被接受、至少一个目标被处理，但部分设备落入 `unknown_devices`）：逐设备结果只由必填的 `delivered` / `unknown_devices` typed map 表达，不附加通用布尔判别。
- **覆盖关系**：`delivered` 与 `unknown_devices` 的设备集合 MUST 互不相交，且其并集 MUST 等于请求 `messages` 中的全部 `(principal_id, device_id)` 目标全集（每个目标恰好出现在二者之一）。consumer 据此可断言无目标被静默丢弃。
- 单设备因 TTL / `expires_at` 等可投递性原因不可入队时，该设备 MUST 计入 `unknown_devices`（携带可投递性失败语义），不使整请求失败。

请求示例（非完整 schema）。`messages.{principal_id}.{device_id}` 的 `{device_id}` 是**收件设备**地址,`content.from_device_id` 是**发送设备**(MUST 等于 envelope `sender_device_id`,见 §10.2),二者为不同设备，故 UUID 不同：

```json fragment
{
  "messages": {
    "ak:did_core:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR": {
      "ak:device:01964137-0000-7000-8000-000000000000": {
        "device_message_id": "ak:device_message:01964137-1000-7000-8000-000000000000",
        "kind": "ak.secret.request",
        "expires_at": "2026-04-26T00:10:00Z",
        "content": {
          "request_id": "req_123",
          "secret_id": "example_mls_account_secret",
          "from_device_id": "ak:device:019641aa-0000-7000-8000-000000000001",
          "recipient_hpke_public_key": "9CKz3Ai9iQz0kHhZcH0H2jqvS-LcQ0YjvKq3aH9mQ0U"
        }
      }
    }
  }
}
```
未被 `ak.device.authorize` durable accepted 的新设备没有合法的 human-device sender endpoint，也不得取得 restricted fresh-device SessionGrant；因此它 MUST NOT 调用本节 send/read/ack surface，MUST NOT 通过任何 to-device kind 发现或通知 sibling devices。新设备授权只走 §2.1.1 的匿名 stage/resolve/status 与二维码、手动复制或等价带外通道；用户以带外交付动作选择批准设备。stage/resolve/status 保持 account-less，不返回 principal 或 sibling device 集合。唯一 `device_pairing_target_proof` 只经二维码/短链 fragment 到达批准设备，并按 §2.1.1 独立验签。

授权前没有签发 grant，因此不存在 bootstrap grant 撤销语义：pending pairing 只能过期、被成功授权原子消费，或在记录清理后变为不可解析；它从未授予账号能力。授权后的设备撤销使用普通 `ak.device.revoke` 合同。部署 MAY 在已认证账号边界内提供不含 token、pairing code、proof、attestation 或 sibling 列表的脱敏唤醒提示，但该提示不是配对传输、不得替代带外交付，也不得使匿名请求绑定 principal。

服务端 MUST 同时执行请求级 `(sender, Idempotency-Key)` 幂等与上述消息级 closed-sender 幂等；前者识别同一批 HTTP command，后者识别跨批次、跨连接的同一逻辑消息。规范客户端 send surface 上 endpoint 仍是当前 accepted `sender_account_id + sender_device_id`（或已授权 Agent endpoint）；内部 service fanout 按 `(sender_id, device_message_id)` 去重。已投递消息的队列删除只由接收设备的显式确认（`ak.self.device_messages.command.ack.v1`，见下文与 [`client-sync.md` §10.1](../sync/client-sync.md)）驱动；sync cursor 推进 MUST NOT 触发删除。To-device 消息 SHOULD 端到端加密；未加密消息只能用于能力发现和验证引导，以及 registry 明确为 Station plaintext CAS 的 actor-private update 提示。

若 `content` 已端到端加密，加密 AAD MUST 至少覆盖发送方在密封前已知且不可由队列服务物化的 `device_message_id`、`kind`、完整 closed sender branch、`recipient_account_id`、`recipient_device_id` 和 `expires_at`。`sent_at` 由队列服务入队时物化，不得进入发送方构造的通用 AAD；具体 kind MAY 增加发送前已知的业务关联字段。队列服务不得重写已进入 AAD 的字段。`Idempotency-Key` 是 HTTP 层语义，不进入 envelope，也不参与 AAD。

接收接口：

```http
GET /_arkret/self/device_messages?after=<cursor>&limit=<n>
Authorization: Bearer <token>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前接收设备。 |
| `after` | query | `cursor` | optional | 上次同步位置（stream cursor）。 |
| `limit` | query | `int` | optional | 返回数量上限；服务端 MUST enforce 最大值。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `messages` | `object[]` | required | 当前设备可见的 to-device 消息（`DeviceMessageEnvelope[]`，不是 Event Envelope）。 |
| `ack_token` | `string` | optional | `messages` 非空时 MUST 返回。覆盖本页及之前所有已投递消息的不透明确认令牌；客户端持久化处理完成后回传给 `ak.self.device_messages.command.ack.v1`。语义见 [`client-sync.md` §10.1](../sync/client-sync.md)。 |
| `next_cursor` | `cursor` | optional | 下一次读取 stream cursor（只读位置，不触发删除）。 |
| `has_more` | `boolean` | required | 是否还有后续消息页。 |
| `limited` | `boolean` | optional | 是否因 limit 被截断。 |
| `lost` | `boolean` | optional | 自该设备上次确认位置以来，服务端因过期或容量约束丢弃过未确认消息时 SHOULD 置 `true`；客户端 SHOULD 触发密钥恢复路径。 |

确认接口：

```http
POST /_arkret/self/device_messages/ack
Authorization: Bearer <token>
Content-Type: application/json
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前接收设备。 |
| `ack_token` | body | `string` | required | 服务端先前签发给同一 `(account_id, device_id)` 的确认令牌。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `pruned_count` | `int` | required | 本次实际删除的消息数；重复或旧令牌的合法 no-op 返回 0。 |

确认语义（normative，完整定义见 [`client-sync.md` §10.1](../sync/client-sync.md)）：确认是累计且单调的——服务端删除令牌覆盖位置（含）之前的全部已投递消息；重复 ack 或 ack 旧令牌返回 `{pruned_count: 0}` 且不得回退确认位置（天然幂等，无需 `Idempotency-Key`）。unknown / 过期 / cross-binding 令牌 MUST 返回 `param_invalid`（reason `invalid_ack_token`）且 MUST NOT 删除任何排队消息。客户端 MUST 在该批次密钥材料 / secret **持久化落盘之后**才 ack；未 ack 的消息在重连时由服务端重新投递，客户端 MUST 先按 closed sender 分支查询 durable 去重记录：human device 使用 `(sender_account_id,sender_device_id,device_message_id)`，Agent 使用 `(sender_agent_id,device_message_id)`，Station service 使用 `(sender_id,device_message_id)`。已成功持久化的消息不得再次执行副作用，但仍计入连续完成位点并允许累计 ack。kind-specific `transaction_id` / `request_id` 只用于业务 transcript 关联，不得替代 envelope 级去重键。

## 8. One-Time and Fallback Keys

设备支持非 MLS 加密或引导 MLS 时，MUST 发布 one-time / fallback prekey：

```http
POST /_arkret/self/keys/upload
POST /_arkret/self/keys/query
POST /_arkret/self/keys/claim
```

`POST /_arkret/self/keys/upload` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `device_id` | body | `id:device` | required | 当前上传设备。 |
| `device_signature` | body | `signature` | required | 当前设备签名；`kid` MUST 为 PCR current accepted-device 投影中的规范设备 method。canonical 签名输入见下方 §8.1。 |
| `one_time_keys` | body | `object` | optional | 算法名到 one-time key 的映射。 |
| `fallback_keys` | body | `object` | optional | 算法名到 fallback key 的映射。 |

响应字段：`one_time_key_counts: object` required；`fallback_keys: object` optional。

#### 8.1 `device_signature` canonical 签名输入（normative）

`keys/upload` 的 `device_signature` 由该设备的**设备身份 key**(event-signer 的 Ed25519 `did:key`，即 §5.2 `device_public_key_did` 对应私钥)对本次上传批次签名，绑定 `device_id` 与所上传的 OTK / fallback 批次。canonical 签名输入：

```text
"ak.keys-upload-v1\n"
+ canonical_json({
    "device_id": <id:device>,
    "one_time_keys": <one_time_keys or {}>,
    "fallback_keys": <fallback_keys or {}>
  })
```

- `canonical_json` 为 RFC 8785 JCS（见 [`../conformance/encoding.md`](../conformance/encoding.md)）；缺省的 `one_time_keys` / `fallback_keys` MUST 规范化为空对象 `{}` 后参与签名，不得省略键，保证发送方与验签方对同一批次得到逐字节一致的输入。
- 批次内每个 `key_record.signature` 仍按其各自语义独立链接到 PCR current accepted-device key；`device_signature` 额外对**整批**签名，防止服务端或中间人对批次做增删/重排。
- `device_signature.kid` MUST 指向该设备身份 key；服务端 MUST 用该设备权威 `device_public_key_did`(§5.2)验签，失败 MUST 拒绝上传（`param_invalid`）。

`POST /_arkret/self/keys/query` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `device_keys` | body | `array` | required | closed `{account_id: AccountId, device_ids: device_id[]}` entries，1..16 项，每项 `device_ids` 1..32 项；按 JCS(account_id) 无符号 UTF-8 字节排序，重复 AccountId 拒绝。 |
| `timeout_ms` | body | `int` | optional | 查询等待上限。 |

完整 canonical 请求上限 64 KiB。上述数组界限与字节界限同时约束本面与 §8.2.1 的跨站转发；超界整体拒绝，MUST NOT 截断 selector 或只返回前缀结果。

服务端在处理 `keys/query` 时 MUST 先认证 requester，并且 MUST 仅在 requester AccountId 与被查询 `account_id` 之间存在当前有效的授权关系时返回目录记录：至少同属一个 requester 可见且 requester 仍为 `join` 的 Realm，或存在当前 Contact／call／session 明确定义的共享上下文（Contact 场景不要求存在共同 Realm）。否则 MUST 使用与不存在不可区分的失败形态（省略该 `(account_id, device_id)` 记录或写入 `failures` 的非枚举性失败），不得让任意已登录用户枚举其它 principal 的设备存在性 / 吊销状态。

响应字段：`device_keys: array` required，每项 `{account_id, device_keys}`，内层 `device_keys` 为 device ID → `query_device_record`；`failures: array` optional，账号级失败用 exact `account_id`；`device_generations: array` optional，每项 `{account_id, generation_state}`（§8.2 第 3 条的输入）。两个外层数组按 JCS(account_id) 无符号 UTF-8 字节排序，重复 AccountId MUST 拒绝，同 core 不同 Station 不得合并。每个 `(account_id, device_id)` 的 `query_device_record`：prekey bundle 收在 `algorithms`（算法名 → key_record）子字段下；同级只携带 `trust_algorithms`、`device_projection` 与 `signer_evidence_ref`（见下方 §8.2）。设备公钥、状态与 authorization/generation 坐标只在 `device_projection` 内出现一次，不在 row 或更外层重复展开。schema 见 [`keys-operations.schema.json`](../../artifacts/schemas/keys-operations.schema.json) 的 `$defs/query_device_record`；Station↔Station 面的已签 row 是另一个类型 `$defs/peer_query_device_record`。

`POST /_arkret/self/keys/claim` 的 `one_time_keys` 请求为 closed `{account_id, device_algorithms}` entries，内层 `device_algorithms` 是 device ID 到算法名的映射；响应同名字段为 `{account_id, device_keys}` entries，内层为 device ID 到算法/key_record 的映射。外层均按 JCS(account_id) 无符号 UTF-8 字节排序，重复 AccountId MUST 拒绝；one-time key 的原子消费、授权、失败与重试定位都绑定 exact `(account_id, device_id)`，不得把同 core 不同 Station 合并。scalar device ID / algorithm map 不承载复合账号身份，继续保留。每个 `account_id.station_id` MUST 等于本 Station：单次 one-time prekey 的原子消费只在其 origin Station 成立，跨站单次材料走 §9.2 的 KeyPackage claim，MUST NOT 为非 MLS one-time prekey 另建第二套联邦消费 ledger；非本 Station 目标按 §8.2 的非枚举形态失败。

#### 8.2 设备验签公钥目录（normative）

`keys/query` 是**跨账号** 的关系门控面。它有两个**不同类型**的 device row，不得互相替代：客户端面的 `query_device_record` 与 Station↔Station 面（§8.2.1）的 `peer_query_device_record`。

客户端面的 `query_device_record` MUST 恰以 `algorithms`、`trust_algorithms`、`device_projection` 与 `signer_evidence_ref` 为成员。`device_projection` MUST 恰以 `device_signing_key_did`、`hpke_key`、`device_authorize_event_id`、`authorized_generation_ref`、`device_status`、`attested_at`、`expires_at` 与 `authorization_window` 为成员，是这些值在本 row 内的**唯一**出现位置。该 row **MUST NOT** 携带 origin 的 `device_projection_attestation`、其 detached proof/JWS，或任何只为验证该 proof 而存在的 wrapper；客户端也 MUST NOT 把 `device_projection` 当作可转交的 portable evidence。

Station↔Station 面的 `peer_query_device_record` MUST 恰以 `algorithms`、`trust_algorithms`、`device_projection_attestation` 与 `signer_evidence_ref` 为成员；设备公钥、状态与 authorization/generation 坐标只存在于已签 attestation 中。

两个 row 的 `account_id` 都由外层 entry 定位、`device_id` 都由内层 map key 定位，不是 device row 的镜像字段，MUST NOT 作为冗余字段重复出现。设备 row 不得回显 DID Document 的设备或 service authority。

`device_projection_attestation` 是 **origin Station 对 exact device projection 的签名断言**，覆盖 `(account_id, device_id, device_signing_key_did, hpke_key, device_authorize_event_id, authorized_generation_ref, device_status, authorization_window, attested_at, expires_at)`。它是 §5.5.1 `device_authorization` result 与 §5.5.4 `device_generation` result 的**下游签名投影**，不是这两个 result 的定义：`device_signing_key_did` / `hpke_key` / `device_authorize_event_id` / `authorized_generation_ref` 逐字取自前者（`device_signing_key_did` 是 payload `device_public_key_did` 在本面的既有名），`device_status` 是 §5.5.3 的读侧折叠，`authorization_window` 是 `(not_before, expires_at)` 的成对呈现，`attested_at` 与证明 `expires_at` 由签发本次断言的动作产生。本面成员表 **MUST NOT** 被当作 device typed current result 的封闭 value 来源。该断言的 proof context 为 `ak.device_projection_attestation_proof.v1`（见 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)）。origin Station MUST 继续生成并持久化它，它是 §8.2.1 peer row 与 `account_device` signer evidence 的载体；客户端面的 row 不携带它。`signer_evidence_ref` MUST 定位包含该 exact attestation 的不可变 `account_device` AuthenticatedSignerResolutionEvidence；origin Station MUST 在返回 row 前持久化该对象及其 Service attester 证据闭包，供普通成员历史响应按签名时刻验签。客户端面 row 上的 `signer_evidence_ref` 与 peer row 上的是同一个引用，仍指向那份完整不可变 evidence；任何一方 MUST NOT 从删去 proof 的 `device_projection` 重新计算该 ref，也 MUST NOT 因本裁剪删除后续 Event / 历史闭包确实使用的 ref。`current_signer_evidence` 的 account-device item MUST 返回同一引用。该引用不引入另一份设备 authority，也不授权通用 Control Event；历史响应规则见 [`history-visibility.md`](../governance/history-visibility.md)。attestation 是本 keys/query 面唯一的设备投影验证载体；PCR genesis、device authorization chain 与 accepted RealmCommit 不得经 keys/query 披露。它们只可经 §8.2.2 的 holder / 合法 Event verifier 限用途依赖读取或既有 resolution audit 读取，不因此开放任意 PCR 枚举。

origin Station MUST 在签发时从该 exact account-device 的 current accepted `ak.device.authorize` 验证授权有效期：当前时刻 `now >= not_before`，且原授权 `expires_at` 非空时 `now < expires_at`；仅有缓存的 `active` 标记不能替代这项检查。缺少对应 accepted 授权 Event、时间材料无法验证、授权尚未生效或已经到期时，MUST NOT 签发可用 row。`authorization_window` 必须逐字表达原 device grant 的 not_before 与可空 expires_at。证明的短 expires_at 只限制当前查询缓存，普通消息缓存复用按 authorization_window 与关闭证明判断，不要求每条消息重签。证明的 `attested_at` 表示本次当前投影检查的时刻，证明 `expires_at` MUST 晚于 `attested_at`，且 MUST NOT 晚于原授权非空的 `expires_at`；实现自定的短 TTL 只能进一步收紧此上界，不能延长原设备授权。没有有效剩余窗口时，按下述非枚举失败形态省略 row，不得通过重签证明、刷新缓存或依赖后台过期扫描延续授权。

普通 Event 的历史 signer evidence 认证与当前 `keys/query` 结果验收分开。历史认证 MUST 从完整来源证据按源签名 `attested_at` 验证当时的 method、assertion 能力、签名、精确 Account/设备授权实例及原授权窗口；MUST NOT 要求接收站曾在证明短 `expires_at` 前见过该原件，也不得把本地首次观察时间增加为授权坐标。相同完整证据 K 的接收站按相同关闭集合归约，首次取得证据时短缓存已过期不制造历史 revoke 或独立 origin 重签门槛。这里使用 `attested_at` 认证源在当时作出的事实，绝不冒充本地观察时间；新的 live 操作仍核真实授权期限及已知关闭，有限期历史仍执行 authority-commit existence anchor 规则。下列新鲜度门只约束本次当前设备查询结果及明确要求它的新 key-access / Signal / E2EE 动作。

自己 Station MUST 先对远端 origin 的已签 row 验证以下全部规则，验证通过后才可把它投影成客户端面的 `query_device_record`；**MUST NOT** 把未验证的 peer row 去掉 proof 当作已验证结果交给客户端。客户端消费该 Station 的结果时，只在 `device_projection` 上执行第 2–4 项的请求、密钥、generation 和状态绑定及有效期检查，不解析 origin DID history：

1. attestation proof 的 controller 投影后**精确等于** `attestation.account_id.station_id`，且该 key 在其当前已验证 method history 下具备 assertion 能力；`proof.created_at` 逐字等于 `attestation.attested_at`，当前时刻早于 `expires_at`；
2. 外层 entry 的 exact `account_id` 与内层 `device_id` map key 必须分别与已签 attestation 同名字段一致，自己 Station 才可投影该 row；投影出的 `device_projection` MUST 逐字保留已验签 attestation 的 `device_signing_key_did`、`hpke_key`、`device_authorize_event_id`、`authorized_generation_ref`、`device_status`、`authorization_window`、`attested_at` 与 `expires_at`，MUST NOT 改写、补位或延长其中任何值。客户端只从 `device_projection` 取这些值，并 MUST 核对外层 `account_id` 与内层 `device_id` map key 逐字等于本次请求的 selector；
3. `authorized_generation_ref` 等于同一响应 `device_generations` 中 exact 同一 AccountId 的 `generation_state` 内的 `current_device_generation_ref`，且 `device_generation_status = active`；
4. `device_status = active`。

任一条不成立时 MUST NOT 把该 row 用于 E2EE / Signal 验签或 KeyPackage claim。反枚举失败形态不变：requester 与目标 AccountId 之间没有当前有效授权关系时，MUST 省略该 `(account_id, device_id)` 记录或写入非枚举性 `failures`；revoked、fenced 或 conflicted 的设备同样按此处理，MUST NOT 降级成一条缺字段的 row。

`keys/query` 的 `failures[].reason_code` 是封闭两值词表，不得扩展、细分或按内部原因分裂：目标不存在、不可见、无当前授权关系、被撤销、被 fence 或被 policy 拒绝一律使用 `device_result_unavailable`；只有「本次未能取得或验证该 `(account_id, device_id)` 的当前已签投影」使用 `device_directory_unavailable`，它 MUST 只表达调用方自己 Station 的取材结果，MUST NOT 因目标状态而出现，也 MUST NOT 携带 origin 的内部原因。后者 MAY 携 `retry_after_ms`。取材失败 MUST NOT 被渲染成省略的 row、空 `device_keys` 或空设备列表——那会让调用方把「暂时取不到」误读成「对方没有设备」。

普通 Event proof method 继续按 §5.3 解析：它是基于已验证 principal `did` 的 DID URL；receiver 取 bare `did` 经 adapter 验证并要求其投影等于 actor/principal `did_core_id`，再要求 fragment 逐字等于 `device_id`，不得从 actor core 拼接 fragment。

普通 human Account device 的 Event signer evidence 用途是下列封闭分流：写 shared authority-commit Data 的 Event 使用 `account_device`；event-kind registry 明确登记为 `wire_scope=actor_private_event` 且 `reducer_input=false` 的 actor-private Event 也使用 `account_device`；写 shared authority-commit Control 的 generic Control Event 使用 §8.2.2 的 `account_device_control`。authority-commit 分类 `None` 只表示 actor-private Event 不进入共享 reducer，绝不得将它改判为 Control。两个 native unit 继续由其专用 verifier 处理。

`account_device` 接受 actor-private Event 时，验证方 MUST 验证完整 attestation 及 Service attester 历史闭包，并逐字绑定 Event actual producer 的完整 `AccountId`、exact `device_id`、DID method/key、原 `ak.device.authorize` 实例、generation 和 Event 签名时刻所在的原 `authorization_window`；live 提交仍独立检查 current generation 及 revoked/expired/fenced/pending-revoke 状态。只有 session/transport authentication、`principal` 证据、`account_device_control` 证据、错误 Account/Station、错误 device/method、错误授权实例，或签名时刻在授权窗口外时 MUST 拒绝。该 `wire_scope` 分支只为 actual producer 是普通 human Account device 的 Event 补齐用途，不允许 Agent/Service actor 借用 human device evidence，也不放宽 Event kind、payload、holder-only writer 或 actor-private 可见性校验。

#### 8.2.1 跨站 peer 设备目录与 prekey lookup（normative）

`keys/query` 的目标 AccountId 的 `station_id` 不是本 Station 时，本 Station MUST 通过
`ak.peer.keys.read.lookup.v1`（`POST /_arkret/peer/keys/query`）向该 exact `station_id` 取材，验证后把受限
typed 结果放进同一个 `keys_query_outcome`。客户端 MUST NOT 直接调用任何 peer 面，本 Station MUST NOT 转发
客户端的 SessionGrant、DPoP 或任何本地 bearer；peer 调用只使用本 Station 自己的 RFC 9421 service signature 与
`Source-Service-ID` / `Destination-Service-ID` / `Content-Digest` header profile；
该 operation 绑定 canonical 合同的 `ak.http_signature.scenario.service_to_service.v1`，
覆盖集与时效窗口（共享的 `ak.http_signature.freshness.v1`）的判据与数值见
[`../sync/service-http-binding.md` §8.1 / §8.3](../sync/service-http-binding.md)，本节不复制。

**既有操作已覆盖的范围（normative 盘点）**：`ak.peer.current_signer_evidence.read.resolve.v1` 只在一个具名
Realm 内交付 signer evidence，既不给设备目录也不给 prekey bundle；
`ak.peer.keys.keypackages.command.claim.v1` 是跨站单次 MLS 材料的**唯一**原子领取合同。因此 v1 的
`self/keys/claim` 单次 one-time prekey 领取 MUST 只针对 `account_id.station_id` 等于本 Station 的目标；跨站单次
材料走 KeyPackage claim，不得为非 MLS one-time prekey 另建第二套联邦消费 ledger。本节只补两者都不覆盖的那段：
**跨站设备目录与已发布 prekey bundle 的只读取材**。

请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `request_id` | `id:request` | required | 调用方 Station 为本次取材生成的稳定 id；destination 只用于关联与限速，不建立 durable ledger。 |
| `requester_account_id` | `AccountId` | required | 发起查询的 exact 完整账号；其 `station_id` MUST 逐字等于已认证 `Source-Service-ID`。destination MUST NOT 从 principal 分量、路由或会话推断它。 |
| `purpose` | `enum(e2ee_message_encryption, mls_group_admission, call_media)` | required | 本次取材的用途；destination 按用途独立判定授权，不得按最宽用途一次性放行。 |
| `relationship_basis` | closed XOR | required | `{kind:"realm_membership", realm_id}` 或 `{kind:"contact"}`。 |
| `device_keys` | `array` | required | closed `{account_id: AccountId, device_ids: device_id[]}` entries，1..16 项、每项 1..32 个 device；每个 `account_id.station_id` MUST 逐字等于已认证 `Destination-Service-ID`。 |

完整 canonical 请求上限 64 KiB，完整响应上限 512 KiB；超界整体失败，不得截断或分页。响应为 closed
`{request_id, requester_account_id, device_keys[], device_generations[]?, failures[]?}`，逐字回显请求的
`request_id` 与 `requester_account_id`。本面的 device row 类型是 `peer_query_device_record`——origin 自签的
`device_projection_attestation` 加 `signer_evidence_ref`，**不是**客户端面的 `query_device_record`；`failures[]`
与 `device_generations[]` 的形态与 §8.2 逐字相同。

destination MUST 在读取任何目标状态**之前**完成 transport 认证与 header/body 绑定，然后独立判定授权，
MUST NOT 采信调用方自报的关系：

- `realm_membership`：`requester_account_id` 与每个目标 `account_id` 在该 exact `realm_id` 上都是 destination
  自己 accepted 状态下的 current effective joined member。
- `contact`：目标账号自己当前 effective 的对 `requester_account_id` 方向 Contact head 授予的 scope 满足本次
  `purpose`——`e2ee_message_encryption` 需 `direct_message`，`mls_group_admission` 需 `invite`，`call_media` 需
  `voice_call` 或 `video_call`。该分支 MUST NOT 要求存在共同 Realm；反过来，requester 单方面的 Contact 事实、
  历史成员身份、目录命中或 Consent quarantine 都不构成授权。

判定通过的每个 `(account_id, device_id)` 返回完整已签 `peer_query_device_record`。**未通过、目标不存在、不可见、已撤销、
已 fence 或 policy 拒绝一律收敛为同一形态**：省略该 row 或写入 `reason_code=device_result_unavailable` 的
`failures` 项；destination MUST NOT 用 HTTP 状态码、响应大小或 per-target reason 区分它们，并 MUST 对
`(Source-Service-ID, requester_account_id)` 与 `(Source-Service-ID, target account_id)` 分别限速。transport
认证失败在读取任何目标状态前返回通用 `unauthenticated` / `signature_invalid`，对任意 selector 完全相同。

调用方 Station 对每条返回 row MUST 执行 §8.2 的四条验证；任一条不成立、peer 调用失败、超时、签名不可验证或
超出预算时，MUST 就该 `(account_id, device_id)` 写入 `reason_code=device_directory_unavailable`，MUST NOT
省略成空结果、MUST NOT 沿用过期缓存、MUST NOT 延长任何 attestation 的 `expires_at`，也 MUST NOT 用裸缓存
公钥补位。结果只按 `(requester AccountId, 自己 Station 会话)` 缓存，账号或 Station 切换、已知撤销与 generation
变化立即失效；迟到响应不得安装到另一个会话。destination 不对结果重新签名；调用方 Station 验签 origin 自己签的
`device_projection_attestation` 之后，按 §8.2 第 2 条把它逐字投影成客户端面的 `device_projection`，并原样转交
同一个 `signer_evidence_ref`，不得代签、重建或补造证据闭包，也不得把 attestation 或其 proof 交给客户端。

本操作 MUST NOT 恢复客户端 DID resolver、远端 attestation 历史重放或任何私有服务端 API；它也不披露 PCR
genesis、authorization chain、RealmCommit 或目标的 Realm/Contact 清单。

实现 MUST 通过 [`ak.vector.device.peer_directory_lookup_blinding.v1`](../../artifacts/registry/vector-registry.json)
与 [`ak.vector.device.directory_unavailable_not_empty.v1`](../../artifacts/registry/vector-registry.json)：前者证明
不存在／不可见／无关系／已撤销／已 fence／policy 拒绝在响应体、状态码与时序上完全同形，且 transport 认证在读取任何
目标状态前判定；后者证明取材失败与"对方没有设备"是两件事，且不得靠缓存、空列表或延长有效期掩盖。

#### 8.2.2 Human control signer evidence（normative）

Human 设备签署高风险 Event 时使用 `AuthenticatedSignerResolutionEvidence` 的 `account_device_control` 分支。该 evidence 绑定 Account、device method/key、current generation，以及授权 Event 的 `CommittedEventRef`；验证方核对 producer proof、current device lifecycle、authority generation 和目标 stream 的连续 RealmCommit，不下载或重放账号历史。

Evidence 只证明 exact signer 在该 generation 的授权来源；membership、scope、capability、recovery policy 与领域 revision 仍由当前治理 Station在 commit 位置独立验证。

#### 8.3 客户端设备信任（normative）

客户端信任自己已认证 Station 确认的 exact account-device 当前授权投影。远端 origin Station 的 attestation 及其 assertion key/history 由自己 Station 验证；客户端不执行 DID/PCR 历史验证，不将任意服务直接返回的设备公钥视为本账号服务器结果。跨站目标的取材由自己 Station 按 §8.2.1 完成；客户端 MUST NOT 直连 origin Station 的 peer 面，也 MUST NOT 把自己的 SessionGrant / DPoP 交给任何其它服务。

客户端 MUST 核对请求的完整 AccountId、device_id、密钥、generation、状态和有效期，并保留 KeyPackage/MLS/消息认证与 §10.1 的带外 verification checkpoint。服务器确认授权不能将未带外确认的新设备或替换密钥标为用户已验证。缓存按账号/自己 Station 会话隔离，已知撤销或 generation 变化立即失效，不越过 `expires_at`。收到 `device_directory_unavailable` 时，客户端 MUST 把该 `(account_id, device_id)` 视为**本次不可用**并保持等待或重试，MUST NOT 解释为该设备不存在、已撤销或对方无设备，MUST NOT 据此降级加密、跳过收件人或推进任何带外验证状态。

客户端把 `keys/query` 结果落到本地 authoring 授权状态时，只 MUST 保存这份可信 self 投影及后续确实使用的 `signer_evidence_ref` 与时态；**MUST NOT** 把未签名的 `device_projection` 填进任何声明为完整签名证据的位置，特别是 `current_signer_evidence` 的 `account_device` item——该 item 仍 MUST 返回 origin 的同一 `signer_evidence_ref`，其所指对象仍是那份含完整 attestation 的不可变 evidence。重启恢复按同一规则从 durable 状态重建，不得用缓存投影冒充证据。若某个 self 入口实际承担 portable evidence 交付，该入口保持完整；本节只裁剪不承担交付的 `keys/query` 普通结果。

跨账号查询不得披露 PCR genesis / authorization chain / RealmCommit。服务间 attestation 继续是 origin 可归责的已签载体；客户端无需复制其历史证据闭包。

## 9. MLS KeyPackage Claim API

MLS KeyPackage 使用独立的 single-use claim API，而不是复用 one-time prekey 语义。

本节 self 与 peer HTTP operation 的闭合 DTO schema 见 [`schemas/keypackage-operations.schema.json`](../../artifacts/schemas/keypackage-operations.schema.json)。OpenAPI 与 `sync/service-http-binding.md` 的字段表 MUST 引用同一 schema fragment；不得再以开放 `OperationRequest` / `OperationResult` 作为这些安全敏感路径的 generated-SDK 契约。

推荐操作：

```http
POST /_arkret/self/keys/keypackages/upload
POST /_arkret/self/keys/keypackages/claim
POST /_arkret/self/keys/keypackages/consume
POST /_arkret/self/keys/keypackages/revoke
POST /_arkret/peer/keys/keypackages/claim
POST /_arkret/peer/keys/keypackages/claims/query
```

`upload` 请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `principal_id` | `did_core_id` | required | KeyPackage 所属 principal 的稳定 `did_core_id`。 |
| `device_id` | `id:device` | device branch | KeyPackage 所属 current accepted device；与另外两分支互斥。 |
| `agent_verification_method` + `agent_key_authorize_event_id` | DID URL + Event id | Agent branch | exact current Agent runtime authorization。 |
| `keypackages` | `object[]` | required | MLS KeyPackage 与 metadata；每项 MUST 带 unique `keypackage_id=ak:mls:kp:<uuidv7>` 和 `keypackage_ref`。前者是 registry 已注册的 Arkret MLS profile typed identity，后者绑定完整 KeyPackage bytes；不得把 `keypackage_id` 降格为 non-typed opaque string。 |
| `endpoint_signature` | `signature` | required | 两分支共享的 authoritative batch signature；按所选 endpoint current authority 验证。 |

### 9.0 KeyPackage 写路径签名 transcript（normative）

`upload`、`consume` 与 `revoke` 的 detached signature MUST 使用本节唯一的 byte-exact canonical input。普通 device 与独立 Agent runtime 使用完全相同的 canonical bytes；身份分支只决定验签所用的 current accepted key 与落库 trust binding，不得改变 domain、字段集合或缺省规则。Rust 实现 MUST 复用 `arkret-rust-sdk` 的共享 typed canonical helper；其它语言实现 MUST 使用与本节闭合 typed request projection 等价的 canonical helper，并通过本节登记的 byte-exact conformance vector。任何实现都不得从开放 JSON value、本地 principal 类型或 HTTP handler 参数临时拼装 transcript。

三条 batch signing input 分别为：

```text
UTF8("ak.self.keys.keypackages.upload.create.v1\n")
+ JCS(upload request 只删除顶层 endpoint_signature)

UTF8("ak.self.keys.keypackages.command.consume.v1\n")
+ JCS(consume request 删除 signature)

UTF8("ak.self.keys.keypackages.command.revoke.v1\n")
+ JCS(revoke request 删除 signature)
```

JCS 对象保留 typed request 中所有 required 字段，并只保留 wire body **实际存在**的 optional 字段。缺省字段必须省略；producer 不得把缺省改写成 JSON `null`。SDK DTO 以 `skip_serializing_if` 省略的空 optional collection 同样不进入 transcript。domain separator 后直接拼接 JCS bytes，不插入空格、额外换行、BOM 或 NUL terminator。

upload 顶层 `endpoint_signature` 始终 required，且是 request 唯一的 authoritative batch authorization。
`keypackage_upload_entry` 不含签名字段；完整 typed request中的 selector、所有 entry bytes/metadata、entry数量与顺序、
`last_resort` 及 request optional fields 都由 batch签名覆盖。batch签名无效时整个 request MUST 在任何 KeyPackage状态写入前拒绝。
接收方不得尝试 per-entry signature、`ak.keypackage-upload-v1`、只覆盖 `{device_id,keypackages}` 的旧 transcript或任何实现私有 fallback。

签名算法 v1 为 Ed25519；`signature.signature_algorithm` MUST 是登记的 `Ed25519`，`signature.kid` MUST 指向同一 accepted signing key。普通 device 从 current accepted PCR device authorization projection 解析该 key；Agent 从 current accepted `ak.agent.key.authorize.verification_method` 解析该 key。该 key 在两分支都 MUST 同时等于 MLS LeafNode signature key。batch签名必须在解析或改变 KeyPackage状态前验证；随后逐 entry执行 RFC 9420 self-signature、credential、Leaf key、metadata/capabilities/lifetime校验。

upload、consume、revoke 的 byte-exact正向与负向向量由 `ak.vector.crypto.keypackage_write_transcripts.v1` 固化。SDK helper输出与该 fixture不一致时实现 MUST fail closed；不得以当前 server或client实现为兼容依据。

### 9.0.1 统一 claim requester authorization 与重放闭包（normative）

`ak.self.keys.keypackages.command.claim.v1` 与 `ak.peer.keys.keypackages.command.claim.v1` MUST 消费同一个
`keypackages_claim_request_body`。requester 必须携带 §9.2.1 定义的 closed
`device | agent` `requester_authorization`，并签名 exact unsigned request 与
`service_binding`；不得携带 holder-only proof、额外 proof 容器或平行 transcript。

`service_binding` 必须显式绑定稳定的 source/destination Station DID。trust domain 属于部署态 transport
坐标，不进入 participant transcript；source Station 必须从已验证的 ServiceResolution + ServiceDescribe
取得双方 trust domain，并由外层 RFC 9421 signature/header 绑定。self Station
先按当前 session/controller、device generation 或 Agent runtime authorization 验证 participant signature，再从
`intended_realm_id` 的 current accepted membership ActorId routing projection 重建并逐字核对 destination。local claim 的
source/destination 相等，但仍走同一 authorization、receipt 与 destination-authority CAS；remote claim 必须把原
canonical body byte-identical durable relay 给 destination，不得由服务代签或改写 participant authorization。

authority 以 `(source_id, claim_request_id)` 建唯一 ledger，并在同一线性化点写入 exact request digest、
KeyPackage CAS 与 byte-identical terminal outcome。同 id+digest 只返回第一次结果；同 id 不同 digest 在 inventory
lookup 前拒绝。不确定结果必须使用原 `claim_request_id + request_digest` 调
`ak.peer.keys.keypackages.read.claim.v1`，不得换 nonce 或盲重放 command。local/remote 成功均返回同一个
`peer_keypackage_claim_receipt`；local receipt 的 source/destination 相等。

`claim` 请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `claim_request_id` | `base64url` | required | 至少 128-bit CSPRNG 随机 object identity；它同时是 `Idempotency-Key`、durable ledger key 与 claim-envelope challenge 的唯一随机值，uncertain outcome query 必须复用。 |
| `target_account_id + target_device_ids` | `AccountId + array<id:device>` | conditional | Human-device target branch；完整账号与至少一台设备共同出现，并与 Agent selector 互斥。携 `target_keypackage_ref` 时恰一项。 |
| `target_agent_id + target_agent_verification_method + target_agent_key_authorize_event_id` | typed tuple | conditional | Agent target branch；三项同时出现，`target_agent_id` 是唯一目标身份 carrier，Event/method 为 current accepted authorization。 |
| `intended_realm_id` | `id` | required | 目标 Realm。 |
| `requester_account_id` | `AccountId` | conditional | human-device requester 的完整账号；Agent requester 的身份只由 Agent authorization 分支携带。 |
| `required_capabilities` | `string[]` | required | 需要的 content / MLS / policy profile。 |
| `mls_group_id` / `claim_purpose` | typed | required | exact MLS group 与 closed purpose。 |
| `expires_at` | `datetime` | required | claim 有效期。 |
| `requester_authorization` | closed XOR | required | §9.2.1 的 device 或 agent participant signature。 |
| `service_binding` | object | required | exact source/destination service DID；participant 不签部署态 trust domain。 |

`claim` 响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `claim_request_id` | `base64url` | required | 与 request/receipt 一致。 |
| `claims` | `object[]` | required | 每个 claimed KeyPackage 的 `claim_id`、`keypackage_ref`、完整 `keypackage` bytes、closed endpoint binding、expiry 与 capabilities。upload endpoint signature 只在发布准入时验证；claim record 不复制无法从该 record 重建前像的签名。 |
| `claim_receipt` | `peer_keypackage_claim_receipt` | required | destination authority 签名；local source/destination 相等。 |

`consume` request MUST validate `schemas/keypackage-operations.schema.json#/$defs/keypackages_consume_request_body`，并由 Welcome 接收方或授权发送方在 Welcome 成功处理且新的 MLS group state 已 durable 持久化后调用。command required 且仅有单数 `claim_id`、`recipient_durable_receipt` 与 `signature`；owner principal、KeyPackage、Welcome、Realm、MLS group、epoch、recipient service 与 closed device/Agent signer branch 全部从签名覆盖的 nested durable receipt 读取，Strand 从 accepted Welcome/Realm governance 派生，不得在 command 另设 selector 或坐标镜像。`user_session` 只承担 endpoint 访问控制与限流：human device 与 Agent branch 的 session actor 必须匹配 nested recipient principal。consume admission MUST 逐字绑定 consume signer、durable receipt、Welcome recipient、exact claim record、KeyPackage signer 与 endpoint authority。`keypackage_consume_receipt` 顶层只携 service 新生成的 `request_digest + claim_id + consumed_at`、完整 `recipient_durable_receipt` 与 service signature；普通包只有在single-use claim转入consumed后签发，last-resort包则只终结该exact claim audit并保持KeyPackage published。`keypackages_consume_outcome` 只返回完整 signed `consume_receipt`。若持久化失败，runtime MUST NOT 调用 consume；若 consume 响应丢失，必须以同一 signed typed request 幂等重试。服务端 MUST 从 durable terminal ledger 返回首次签发的同一 receipt，不得重新签名；完整 request digest 不同即冲突。对于 Direct Conversation，服务端还必须从 accepted Welcome 与 immutable binding 重新派生 Realm、Strand、MLS group 与 epoch；任何不一致均 fail closed。`revoke` request MUST validate `#/$defs/keypackages_revoke_request_body`，可由设备、principal controller 或 policy 授权服务发起。

规则：

- 对普通 single-use KeyPackage，`claim` MUST 原子地把 KeyPackage 从 `published` 转为 `claimed`。协商启用的 `last_resort=true` 包是唯一例外：包本身保持 `published`，每次领取只追加独立 `keypackage_claim_record`（见 [`encryption-and-audit.md` §2.6.2](./encryption-and-audit.md)）。
- 同一 `keypackage_ref` 不得被多个 active claim 使用。
- 过期、撤销、设备被移除或 principal control state 失效时，服务 MUST NOT 返回该 KeyPackage。
- **registered `required_capabilities` ⊆ signed LeafNode `capabilities`（normative subset rule）**：claim request 中每个 `required_capabilities` 值 MUST 是 [`keypackage-capability-registry.json`](../../artifacts/registry/keypackage-capability-registry.json) 的 active 行，且集合 MUST 是被领取 KeyPackage 的 signed LeafNode `keypackage_capabilities` (`0xF1C1`) 的子集；外层 upload / claim record `capabilities` 必须与该 LeafNode 列表逐项、逐序相等。形状合法但未登记的发布值保留为 unsupported，永远不得满足 required 集合。任何未登记 required 值、`required_capabilities ∖ signed_leaf_capabilities ≠ ∅` 或 outer / LeafNode 不一致的 claim MUST 被服务端拒绝（与其它 claim 失败一致使用统一不透明错误码 `claim_failed`，服务端内部审计统一归入既有 `keypackage_capability_overreach` 类别并记录具体 predicate）。该 claim 检查只是领取前置；committer 还 MUST 按 [`encryption-and-audit.md` §2.6](./encryption-and-audit.md) 把群实际要求写入 `required_keypackage_capabilities` GroupContext extension，并在 Add / Update / Join 时复核。
- Station device/key surface 在 claim 成功响应中返回完整 `keypackage` bytes、`capabilities` 与 claimed endpoint 的 trust binding，不返回同体 digest 回声。普通 device 携带该设备 accepted `ak.device.authorize` 的 `device_authorize_event_id`；Agent 携带当前 accepted `ak.agent.key.authorize` 的 `agent_key_authorize_event_id`。两者 MUST 精确 XOR。Consumer MUST 从 claim record 的完整 bytes 重算 `keypackage_digest`、从 capabilities 重算 `capabilities_digest`，再要求 `payload.claim_ref.keypackage_digest` / `payload.claim_ref.capabilities_digest` 与重算值逐字一致。比较只有这两端——claim record 里的完整 bytes 与 capabilities，和 Welcome 的 `claim_ref`。KeyPackage 的发布不产生 durable Event（`ak.self.keys.keypackages.upload.create.v1` 的 `durable_effect.kind` 为 `none`），因此不存在可作第三个比较项的已发布 digest；Welcome 顶层同样不复制 KeyPackage digest。`payload.claim_ref` 还必须携带同一 closed endpoint binding，接收端在解密前确认 device/Agent authority 仍 current，防止 group manager 或中间服务替换 KeyPackage、扩大能力集合或复用旧 authority。
- `payload.claim_envelope` 是 requester 对本次 Welcome 的独立签名 transcript，签名身份绑定 requester 而不是被 claim 的 endpoint。普通 principal requester MUST 携带 `requester_device_id` 与 `device_authorize_event_id`，并用该设备当前 accepted `ak.device.authorize.payload.device_public_key_did` 签名；Agent requester MUST 携带 `requester_agent_id + requester_agent_verification_method + requester_agent_key_authorize_event_id`，并用所声明的 active Agent key 签名，禁止携带或借用 `requester_device_id`。两者 MUST 精确 XOR。服务端和接收端 MUST 校验 envelope 的 requester identity、closed endpoint、authority binding、signature `kid` 与当前投影/Realm affinity 一致；不得把 recipient KeyPackage 的 authority 当作 requester 签名身份使用。
- 每个成功 Welcome 必须携带唯一的 `claim_receipt`，其类型固定为 destination-signed `peer_keypackage_claim_receipt`；same-service claim 也使用同一类型，且 `source_id=destination_id=current authority`。`claim_request_id`、`request_digest`、`claims_digest`、exact unsigned request 与 source/destination service 均进入签名 transcript。Agent 使用仍有效的可复用 authority lease/gate；接收端独立核对 receipt、实际 claim 与 Agent key/authorization/scope。claim 自身签名已绑定请求，不新增 Agent observation 包装。
- `claim` 失败响应 MUST 对不存在、不可见、无可用设备、policy denied、subset-rule 违反（§上条 `keypackage_capability_overreach`）、过期、`revocation_pending` 与已撤销状态做反枚举处理。所有 deployment profile 的对外错误码 MUST 合并为单一不透明 `claim_failed`；HTTP status、body shape/size class、target-sensitive headers 与量化后的 delay distribution 也必须按 `ak.outward_disclosure.target_private_claim.v1` 同形。不得返回逐 target `failures[]`、`available_count` 或可区分 error message。精确 reason 只进入受限 audit，普通日志与 metrics label 只记录 outward bucket。
- 设备 SHOULD 维持 `keypackage_min_available` 低水位，v1 默认目标 `N=8`。`N` 是端点补货的操作目标，不是“设备离线期间任意领取突发均可成功”的协议可用性保证；任何有限 `N` 都不能提供该保证。v1 不存在 owner inventory、maintenance query 或包级终态通知，upload、self/peer claim 与 peer outcome-query 均不得返回 `available_count`。客户端维护 endpoint-scoped 本地 inventory ledger，只在本地 usable 数量低于当前目标 `N` 时于一个 single-flight maintenance cycle 上传一个至多包含 `N - local_usable_count` 个 fresh 包的 deficit batch；默认配置下即为 `8 - local_usable_count`。健康 inventory 重载必须零上传。并发 runtime MAY 短暂 overfill，但每个 cycle 不得超过其启动时 deficit。
- 本地 `usable` 是端点根据自己已经持久观察的 publish、Welcome/consume/revoke 与 KeyPackage 自身 `expires_at` 求出的保守补货输入，不是 Station 当前可领取库存的镜像。另一个 requester 已 claim、但 owner 尚未观察到 Welcome/consume 的普通包，MAY 暂时仍被本地账本计为 usable；这只会造成服务器侧可领取库存低于本地估计，不授权复用该包，也不允许从不透明 `claim_failed` 推测库存。v1 明确不保证该观察窗口内及时补回未观察的 claim；若产品需要更强的离线领取 SLO，部署只能提高本地目标并自行量测，不能改变 wire、枚举库存或恢复已领取包。
- 普通 claim 的 `expires_at` MUST 不晚于所领取 KeyPackage 自身的 `expires_at`。claimed 但未 consume 的 KeyPackage 到达 claim `expires_at` 后 MUST 转为 revoked / unusable 状态；服务不得把它自动放回 `published`，也不得接受迟到的 consume。无论 owner 是否观察过该 claim，客户端在 KeyPackage 自身 `expires_at` 到达后 MUST 把本地条目排除出 usable 集合，并在下一个在线 maintenance cycle 按同一 deficit 规则发布 fresh KeyPackage。因而 v1 的闭合恢复点是包自身到期后的本地确定性收敛，而不是未登记的 owner 终态推送。
- Station device/key surface MUST 维护过期扫描或等价触发：KeyPackage `expires_at`、claim `expires_at`、device revoke、principal control state 失效、capability revoke 或 Realm policy 变更任一发生时，后续 `query` / `claim` MUST NOT 返回该 KeyPackage；后台清理不得是唯一防线。扫描周期 SHOULD ≤ 60s，且每次 `claim` 路径必须先做同步 freshness 判定。
- KeyPackage claim MUST 对 closed requester identity 与 closed target identity 做限速；human 分支使用完整 `AccountId`，Agent 分支使用其唯一 branch identity。默认窗口为 60s 内最多 5 次 claim 尝试。超过限额时对外仍使用反枚举响应（`claim_failed` 或通用 rate-limited envelope，不泄露目标存在性）；服务端内部审计 reason 记录为 `keypackage_claim_rate_limited`。
- claim record SHOULD 被 Station / Device Key Server 保留到 Welcome 过期后的一段短 TTL，用于重试、诊断和滥用审计；不得长期保留可关联 private Realm / MLS group 的明文目标信息。

### 9.1 KeyPackage 状态机（normative）

上述分散规则共同定义下列受控状态机，单段 KeyPackage（由 `keypackage_ref` 标识）的合法状态与转换为：

| 状态 | 语义 | 合法后继 | 终态? |
| --- | --- | --- | --- |
| `published` | 已 upload，可被 claim | `claimed`（原子 claim）、`revoked`（device revoke / principal 失效 / KeyPackage `expires_at` 到期 / account deactivation） | 否 |
| `claimed` | 已被某次 claim 原子占用 | `consumed`（Welcome 成功处理后 consume）、`revoked`（claim `expires_at` 到期 / device revoke / capability revoke） | 否 |
| `consumed` | 已被 Welcome 消费 | —（终态） | **是** |
| `revoked` | 因过期 / 吊销 / policy 失效不可用 | —（终态） | **是** |

转换约束：

- **`published → claimed` 原子**：普通 single-use 包的 `claim` MUST 原子转换；同一 `keypackage_ref` 不得被多个 active claim 占用。`last_resort=true` 包不执行该状态边，始终保持 `published`，其多个 active claim 由互相独立的 append-only claim record 表达。
- **`claimed` 不回 `published`**：claimed 但未 consume 的 KeyPackage 到达 claim `expires_at` 后 MUST 转 `revoked`，服务 MUST NOT 自动放回 `published`，也 MUST NOT 接受迟到的 consume。
- **终态集合**：`{ consumed, revoked }` 均为 terminal，任何转出 MUST 被拒绝。`published` / `claimed` 的过期、吊销或 account deactivation 一律收敛到 `revoked`（claim 路径同步 freshness 判定，扫描周期 SHOULD ≤ 60s，见上）。
- account deactivation fanout（[`../identity/account-lifecycle.md` §7.1](../identity/account-lifecycle.md)）把 unused（`published`）KeyPackage 标 `revoked` 并记录 reason=`principal_deactivated`；已 `consumed` 的不改写。新邀请 MUST NOT 从 `revoked` / `consumed` 的 KeyPackage 选取。

### 9.2 跨 Station 原子 claim（normative）

当 requester 与 target 由不同 Station 托管时，来源服务不得调用目标服务的 `/_arkret/self/*`，也不得把 KeyPackage 领取伪装成 durable Event。v1 唯一 wire surface 为：

| operation | HTTP | request / response schema |
| --- | --- | --- |
| `ak.self.keys.keypackages.command.claim.v1` | `POST /_arkret/self/keys/keypackages/claim` | `keypackages_claim_request_body` / `keypackages_claim_outcome` |
| `ak.peer.keys.keypackages.command.claim.v1` | `POST /_arkret/peer/keys/keypackages/claim` | `keypackages_claim_request_body` / `keypackages_claim_outcome` |
| `ak.peer.keys.keypackages.read.claim.v1` | `POST /_arkret/peer/keys/keypackages/claims/query` | `peer_keypackages_claim_query_request_body` / `peer_keypackages_claim_query_outcome` |

目标 KeyPackage authority 是 `published → claimed` 的**唯一 CAS 权威**。来源服务只能请求领取并验证目标服务签发的 receipt；不得在本地镜像池上先行标记、推测成功，或用 `ak.peer.events.command.submit.v1` 替代该原子操作。claim 成功只是生成 MLS Welcome 的必要前置条件，不创建 Realm、membership、Strand 或 binding；这些 durable facts 仍必须由其规范 Event 与原签名 proof 创建并经 peer Event / principal-fact 通道投递。

#### 9.2.1 双重授权与签名 transcript

peer claim MUST 同时满足两层授权，任一层缺失或失效都 MUST fail closed：

1. **participant authorization**：requester 对 `requester_authorization` 作 detached signature。签名输入精确为 UTF-8 domain separator `` `ak.peer-keypackage-claim-authorization-v1\n` `` 后接下列对象的 JCS bytes：

   ```json fragment
   {
     "authorization": {
       "device_authorize_event_id": "<accepted authorization for requester_device_id>",
       "requester_device_id": "<requester device>",
       "signed_at": "<RFC3339>",
       "verification_method": "<kid>"
     },
     "request": "<the exact unsigned claim request object>",
     "service_binding": {
       "destination_id": "<Destination-Service-ID>",
       "source_id": "<Source-Service-ID>"
     }
   }
   ```

   上例是 `kind=device` 分支。`service_binding` 是闭合的 `{source_id, destination_id}`；客户端从业务已钉的 target ActorId routing projection 取得 destination DID，不得从 endpoint URL 或 DID 字符串猜测。部署态 trust domain 只由 source Station 验证 ServiceResolution + ServiceDescribe 后写入外层已签 HTTP headers，peer receiver 逐字复核。`signature.kid` MUST 等于 `verification_method`。`requester_authorization` 是 closed XOR：human principal 必须且只能携带 `kind=device + requester_device_id + device_authorize_event_id`，并由该 accepted、未撤销设备的 `device_public_key_did` 签名；Agent 必须且只能携带 `kind=agent + requester_agent_id + agent_key_authorize_event_id`，并由 accepted current Agent runtime method 签名。Agent id、verification method 与 authorization Event 必须逐字绑定 current AgentSignerEvidence、claim requester、repair author actor 与随后生成的 MLS Event/KeyPackage signer，且不得借用 `ak:device` 身份。来源 Station MUST 独立解析本地 exact requester Account 的对应 authority chain；目标服务 MUST 验证下述来源 Station 的完整 service attestation，不得把未认证的 participant key 裸断言作为授权。

   客户端/Agent runtime 签名后，来源 Station MUST 在本地验证 account pair、当前 device/runtime authorization、generation 与 revoke/pending 状态，再签发 peer command。body 不携带 PCR/device/Agent signer history sidecar；目标服务验证 authenticated source service、request transcript 与来源服务签名。该 service attestation 提供可验证归责，不声称在密码学上阻止恶意 Station 作恶。目标服务 MUST NOT 以本机同 principal 的 Account、设备目录或 Agent signer 状态替代来源 Station 的 requester authority；也不得从 DID 或 endpoint 猜测其 Station。来源服务的 authority 必须由 §9.2.2 的当前 Realm membership routing 或精确 Contact/account pair 独立约束；仅有有效服务签名而没有该业务范围授权仍 MUST 拒绝。
2. **service authorization**：外层请求 MUST 使用 RFC 9421 HTTP Message Signature。跨部署 KeyPackage
   claim 是 [`../sync/service-http-binding.md` §8.1](../sync/service-http-binding.md) 一般 service-to-service
   场景的一个实例，且其三个条件项同时成立（带 body、跨 trust domain、参与幂等），因此本次适用的
   必需覆盖项为：

   <!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.service_to_service.v1 -->
   - `@method`、`@target-uri`、`@authority`
   - `arkret-operation`
   - `source-service-id`、`destination-service-id`
   - `content-digest`（本 operation 总是带 body）
   - `source-trust-domain`、`destination-trust-domain`（本 operation 跨 trust domain）
   - `idempotency-key`（本 operation 参与幂等）
   <!-- END ak-http-signature-covered-set -->

   `Idempotency-Key` MUST 逐字等于 body `claim_request_id`。

成功响应的反方向也必须闭合。每条 `keypackage_claim_record` MUST 携带与分支一致的 principal/device 或 Agent endpoint、authorization Event id、KeyPackage digest 与 signature；目标 Station 的签名 `claim_receipt` 对 exact claim bytes 可验证归责。requester MUST 核对 authorization Event 的内嵌 可携带 producer signer evidence、claim receipt、KeyPackage 签名与所有 selector，任一不匹配都不得安装 KeyPackage 或 author Welcome。wire 不得携 PCR/control-history/device/Agent signer-evidence sidecar，外部 verifier 不重放 PCR genesis、RealmCommit 或完整控制历史。

`claim_request_id` MUST 由 CSPRNG 生成并含至少 128 bits 不可预测熵。它是同一 claim transaction 的唯一随机值：HTTP `Idempotency-Key`、durable ledger key 以及 Welcome `claim_envelope` canonical 签名 transcript 中的 `claim_request_id` MUST 是同一值。该 transcript 值 MUST 从同一 Welcome 的 destination-signed `claim_receipt.claim_request_id` 取得，且不得在 `claim_envelope` wire 中重复。byte-identical replay 必须复用同一值；新尝试必须生成新值；同一 `(source_id, claim_request_id)` 下任何其它 request bytes 均为 `duplicate_conflict`。`requester_authorization.signed_at` 不得在接收方当前时间未来 60 秒以上；`expires_at` MUST 晚于 `signed_at` 且 `expires_at - signed_at <= 300s`。外层 HTTP signature 的 `created` / `expires` 判据是 [`../sync/service-http-binding.md` §8.3](../sync/service-http-binding.md) 的共享窗口，本节不另定数值。participant signature 绑定 source / destination service DID；外层 service signature 另绑定双方 trust domain，合并阻断转发到另一目标或另一部署的重放。

#### 9.2.2 目标 authority 的独立准入

在触碰 KeyPackage 状态前，目标服务 MUST 独立验证：

- `Source-Service-ID` 是 requester closed 分支当前已验证的 Station locator / home authority；human target 时 `Destination-Service-ID` MUST 逐字等于 `target_account_id.station_id`，Agent target 时则等于已接受 Realm routing evidence 为该 target actor 选择的当前 KeyPackage authority。两端与请求中的 trust domain 均属于允许此次 Realm 建立的同一 trust domain；不得用同一 principal 分量下另一 Account 的 Station 替代；
- participant authorization 的 requester、verification method、generation / device authorization、freshness 与 exact request/service binding 全部有效：目标服务独立验证 closed 分支、requester/endpoint 一致性、freshness 与完整 request/service binding；当前 participant key、generation 和撤销状态由来源 Station 按 §9.2.1 验证并以绑定完整 body 的 service attestation 负责。不得在目标端重放远端 PCR 或借用本地同 principal 目录；
- target 当前 active device、KeyPackage expiry / revocation / capability 均有效，并满足 `required_capabilities ⊆ capabilities`；
- `claim_purpose=direct_conversation` 时，request MUST 携带 `pair_key` 与 main
  `strand_id`；目标服务按 [`../identity/contact-and-direct-conversation.md` §7](../identity/contact-and-direct-conversation.md)
  重算 pair key，并验证双方 current directional Contact heads 都包含 `direct_message`、预留 Realm / Strand /
  MLS group 的一致性；该路径不得查询 Consent；
- accepted member rejoin 后的普通同组 Add/Welcome 可以在 `claim_purpose=direct_conversation` 请求中携带 `target_keypackage_ref`，此时还必须携带 closed target XOR：human
  branch 必须且只能携带恰一个 `target_device_ids`；Agent branch 必须且只能携带
  `target_agent_id + target_agent_verification_method + target_agent_key_authorize_event_id`，禁止
  `target_account_id` 与 `target_device_ids`。owner authority 必须从当前分支唯一 identity carrier 解析 target actor，并验证该 exact ref 属于
  对应 target 与 signer，selector、claim record、current portable signer evidence 及 KeyPackage signature
  逐字一致，状态为 current
  `published`、未消费、未撤销且 `last_resort=false`；不得忽略 exact ref 后按 device、capability 或库存顺序
  另选。成功 outcome 必须恰有一条 claim 且其 `keypackage_ref` 逐字等于 `target_keypackage_ref`；任一不匹配
  以不透明 `claim_failed` 零写入；
- human target 以 `(Source-Service-ID,target_account_id)`、Agent target 以 `(Source-Service-ID,target_agent_id)` 为精确输入的限速与 abuse policy 通过；这些 key 不得降维为 principal 分量。

`claim_purpose=direct_conversation` 时 `last_resort_allowed` MUST 缺省或为 `false`，
目标服务 MUST NOT 返回 last-resort KeyPackage。一般 `realm_membership` claim 只有在双方 feature negotiation
均声明 `ak.feature.mls_last_resort_keypackage.v1` 且请求显式 `last_resort_allowed=true` 时才可返回 last-resort
record；否则 single-use pool 耗尽即失败。

#### 9.2.3 原子幂等 ledger 与不确定结果

目标 authority MUST 持久化以 `(Source-Service-ID, claim_request_id)` 唯一索引的 claim ledger，并把从已验证 exact canonical body bytes 内部计算的 Arkret digest 记为 `request_digest`。下列动作必须处于同一事务 / 等价线性化边界：

1. 核对已由唯一索引保护的 request reservation 与 digest；
2. 一般 profile 选择仍为 `published` 且通过 freshness / capability gate 的 KeyPackage；
   携带 `target_keypackage_ref` 的同组重加入请求只锁定该 exact KeyPackage，不得执行候选选择；
3. 对 single-use KeyPackage 执行 CAS `published → claimed`；
4. 在同一 current authority snapshot 上生成并复核 target portable evidence，写入 claim record、把
   ledger 从 `pending` 变为终态，并写入已序列化的成功 outcome bytes。

实现 MAY 在最终事务前先提交只含 `(Source-Service-ID, claim_request_id, request_digest, state=pending)` 的唯一 reservation，以串行化并发 duplicate；该 reservation 不得选择、锁定或泄露 KeyPackage。上述 1–4 的**最终化**必须在同一事务完成，因而不得出现 KeyPackage 已 `claimed` 但 ledger 无 outcome、或 ledger 已成功但 CAS 未发生的可观察状态。crash 后 recovery worker 只能按原 digest 恢复 / 最终化同一 reservation，不能改用新的请求身份。

目标先验证当前 transport 的 Source-Service-ID、签名与 exact canonical request digest，再查询 durable ledger；
同一 source、claim_request_id、digest 的 duplicate MAY 直接 exact replay，MUST 返回同一已存 claim outcome
及其当前 closed ledger state，不得第二次领取、激活或授予新 authority。异 digest 返回 duplicate_conflict，零写入。
peer command 使用 `peer_keypackages_claim_command_outcome`：pending、claimed、consumed、claim_failed、expired、
revoked 与 read query 共享相同字段和终态语义，原签名 claim_outcome bytes 不变；失败不能降成缺少已存结果的另一协议。

响应丢失、超时或 dispatch marker 与 network send 间 crash 后，来源 MAY 直接重放原 canonical command；
transport HTTP signature 可刷新，participant intent、evidence、request identity 和 bytes 不变。read.claim MAY 用于
观察 pending、退避或调用方丢失 command bytes 时恢复，不是重发前置。query 的 unknown 只表示无该 reservation；
新执行仍需原 command 未过期且完整 current admission 通过。pending 的 query/replay 均只观察或续跑原 reservation，
按 retry_after_ms 退避，不能产生第二次 claim。claimed/consumed/expired/revoked 携原签名 claim_outcome 及该状态
要求的收据；claim_failed 携不透明 error_code=claim_failed 及规范要求的 terminal_receipt，不披露失败原因。query 仅接受原 Source-Service-ID 和 exact digest。
已存结果读取不得仅因原 command 新鲜度已过而拒绝；它不重新披露任何需新授权的敏感材料，也不恢复被撤销权限。
ledger GC 后过期 command 必须拒绝，不能成为新 claim；网络发送与远端收到 bytes 不属于数据库原子事务。


成功 outcome 的 `claim_receipt.signature` 由目标服务对 `` `ak.peer-keypackage-claim-receipt-v1\n` `` + JCS(receipt 除 `signature` 外全部字段) 签名；receipt MUST 携带并签名覆盖 `source_id`、`destination_id` 与原 participant-authorized `request`（即不含 authorization / transport-only evidence 的 unsigned request 字段），`request_digest` 绑定完整 peer command，`claims_digest` 绑定 `claims[]` canonical bytes。`claim_request_id`、receipt.request 内同名字段与 outcome 同名字段必须一致。ledger 的可查询 outcome MUST 至少保留到 claim `expires_at + 10 minutes`；其后实现 MAY 只保留符合隐私 / 审计策略的 hash replay tombstone，不得长期保留可关联 private Realm 的不必要明文。

通过统一 claim 生成的 `MlsWelcomeDelivery` MUST 原样携带 `claim_receipt`。当前治理 Station 必须在接纳 `MlsCommitSubmission` 的同一数据库事务内验证 receipt 目标服务签名；精确匹配 `source_id`；查询 `(source_id, claim_request_id)` durable ledger 并逐字匹配 `request_digest` 与 stored outcome；验证 requester、target principal、intended Realm、MLS group、recipient endpoint、claim id 与 KeyPackage ref/digest。缺 receipt、ledger 未就绪或任一绑定不一致时整个 submission fail closed，Commit、public group state 与全部 recipient delivery 均不得部分落盘。Direct Conversation 还必须把 receipt.request 的 `pair_key` 与 `strand_id` 精确匹配已提交的 founding unit。Delivery 是收件人队列对象，不进入任何 Event stream，也没有独立 finality。

所有目标不存在、任一方 Contact head/scope 不满足、设备不可见、KeyPackage 耗尽、capability 不满足、policy denied、participant authorization 失效和限速失败，对**已通过外层服务认证**的 peer caller 必须收敛为同一 `claim_failed` 外观；不得返回 `available_count`、目标设备列表或逐设备 `failures[]`。外层 RFC 9421 signature / source service identity 无法通过时，接收方在读取 target 状态前返回通用 `unauthenticated` / `signature_invalid`；该响应必须只由 transport authentication 决定，对任意 closed target selector（human AccountId、Agent id 或 pairwise method）完全相同。

#### 9.2.4 Welcome、consume 与已接受的 founding unit

Direct Conversation 唯一 Realm 与 main Strand **MUST** 从已接受的 caller-authored founding unit、source acceptance receipt 与 pair 唯一 slot 验证，遵循 [私聊 §5–§7](../identity/contact-and-direct-conversation.md)。resolver 只读；不得创建 coordinator、reserved/materializing operation 或第二套坐标选择机制。唯一 MLS group 从 effective scope 派生；Add 与 Welcome 必须沿同一 accepted Genesis / winning Commit lineage 推进。

Station **MUST** 在 founding self/peer admission 时验证 exact unit、source acceptance receipt（peer 分支）与本地唯一 slot；self receipt 是原子接受的输出，不是输入。recipient runtime **MUST** 通过已登记的 accepted Event/RealmCommit/governance dependency 读取面验证 exact founding unit、pair、Realm、main Strand、current membership/endpoint gates、Welcome 对应的 accepted winning Add Commit，以及原 claim receipt / claim envelope 的 requester、recipient、KeyPackage、group 和 epoch 绑定。runtime 不得被要求读取 Station 私有 slot 或未提供查询入口的 receipt；也不得用未验证的本地缓存替代 accepted 证明。首次 Welcome 不得以最终 `ak.direct_conversation.bound` 已 accepted 为前提：该 endorsement 只能在 recipient durable 接受之后完成。已有 binding 时仍必须逐字匹配既有坐标与同一 group，不得另建候选 Realm 或重置 epoch。

Welcome 成功处理且 group state durable 保存后，才可生成 recipient durable receipt，并通过 own Station 的 `ak.self.keys.keypackages.command.consume.v1` 消费原 claim；peer surface 不提供 consume 代理。保存失败不得签收。consume 的 signed request 与原 outcome 按 §9.1 幂等恢复。

本节不移除 §9.2.3 的 claim ledger、可选 query 和 direct exact replay，也不移除适用的普通 committer durable journal / winning Commit 约束。网络结果不明不得换 claim identity 盲重试、并行领取替代包，或把已领取包放回 published。房间唯一性证明与 claim 的恢复账本各司其职；本地缓存不能替代 accepted facts 或签名收据。

### 9.3 普通 MLS join admission 与补偿（normative）

public/invite/closed/knock/admin-add 的最终 join都必须携未过期、single-use、签名的
`MlsJoinAdmissionReceipt`。receipt完整绑定 target Realm/member/**exact target device**、KeyPackage ref/claim、
group ID、current winning MLS group state、expected epoch、current key-access revision、join authority basis、exact member Event
draft ID/digest、eligible committer、ciphersuite、issuer、issued/expires-at与reservation ID。target-device签名的
reservation在任何 claim CAS之前持久化；claim-before rejection零烧。

唯一顺序是：target-device signed reservation → KeyPackage claim CAS → durable committer journal genesis +
exact commitment → member Event accepted in its authority stream → append RealmCommit → Add Commit + Welcome → recipient durable
group state + consume intent → consume original claim。

journal genesis与committer commitment必须在member acceptance之前存在，并逐字绑定member draft、claim、
group/generation/base epoch、eligible committer identity与recovery identity。acceptance后只可append accepted
checkpoint/Commit facts。takeover必须签 predecessor、current epoch与相同 exact commitment，并以journal CAS接管；
不得更换draft、target device、KeyPackage或generation。claim后任何terminal failure都必须把原claim推进
`revoked`，不得第二次claim；只有recipient durable后才能consume。

注册唯一 authority source `ak.authority.membership_compensation.v1`。补偿 delegation由实际 accepted join
Event的authoring proof signer产生；其无签名、无`delegation_id`的closed core逐字绑定
admission/join identity、member Event ID/digest、member Event对应的 RealmCommit与J1 provenance、subject、真实
`actor_id/executed_by?/authorization_ref?/verification_method`分支、executor service DID+proof key、resource、
deadline及唯一action。对exact RFC8785/JCS core计算SHA-256，并机械派生外层
`delegation_id=ak:membership_compensation_delegation:sha256:<lowercase_hex>`；ID后缀就是该digest的唯一wire表示，
delegation、terminal certificate与single-use CAS token都只携带`delegation_id`，MUST NOT再携带sibling
`delegation_digest`（[`../conformance/encoding.md` §4.0.1](../conformance/encoding.md)）；外层author signature覆盖ID与core。不可转授，也不得用普通grant/source代替。

action是closed XOR：self join仅 `ak.member.compensate.leave`，delegated/admin join仅
`ak.member.compensate.remove`；未知action fail closed。executor author fresh标准 `ak.member.state`减权 Event，
固定原join actor，`executed_by=executor`，`authorization_ref`精确引用delegation。terminal certificate仅作
critical submission evidence，不进入被授权Event digest。destination authority以
`(admission_id,delegation_id)`做single-use CAS；current membership head仍是J1时最多一次写入，already absent或
已被J2/new join supersede时返回 `membership_compensation_conflict` 且零写，绝不得删除后来重新加入者。

失败分支固定为：claim前拒绝零烧；claim后/member acceptance前只revoke原claim；member accepted/Add前执行
membership compensation；Add已接受后先执行同一membership compensation，再由eligible committer执行标准MLS
Remove。Remove绑定旧group/generation/leaf/commit，新generation上只能no-op。deadline触发operation failure，
但cleanup authority持续到成功消费或确定性 conflict。重复、跨admission、executor/proof key错配或deadline前滥用
都必须拒绝。success/repair terminal不得生成compensation terminal certificate。

## 10. 设备信任 checkpoint 与 Secret Sharing

设备 trust evidence 回答“这台设备及其密钥是否已被本账号在环确认过”。它与 device lifecycle 正交（§14.1）：evidence 取值只有 `verified | unresolved | stale`，本身**不授予**登录态、Realm 权限或长期设备权力：

- 同一 principal 的新设备仍 MUST 通过 `ak.device.authorize`、符合 DID method 的 key-log operation 或 recovery policy 才进入有效设备集合，并按 §5.4.1 在本地装配前完成强制校验。
- `ak.session.grant` 只授予短期会话能力；取得 verification checkpoint 不得被升级为长期设备授权。
- v1 不定义 device-level 的跨 principal 人工验证协议；跨 principal 联系人验真不在 v1 范围（见 §10.1 末尾）。

### 10.1 Verification checkpoint（normative）

evidence=`verified` 只来自 **verification checkpoint**：一条绑定 exact `(AccountId, device_id, device signing key, hpke_key, authorize generation)` 的 durable 记录。v1 的 checkpoint 来源是**封闭集合**；机读真源是 [`account-operations.schema.json`](../../artifacts/schemas/account-operations.schema.json) 的 `device_summary.verification_source`，其取值只允许：

| `verification_source` | 唯一来源 | 建立条件 |
| --- | --- | --- |
| `genesis` | §5.1 PCR genesis 与首设备 | 初始账号创建 ceremony 中首设备对 exact device signing key 与 `hpke_key` 提供私钥持有证明，并被 accepted registration-anchor authorize 覆盖。 |
| `pairing_code` | §2.1 accepted-device pairing / re-verification ceremony；机制定义见 §2.1.4 的 pairing-originated verified checkpoint | 见下方五项条件。 |
| `recovery` | §14 PCR-policy device recovery | accepted recovery unit 按 recovery policy 为 replacement device 建立；checkpoint 绑定该 unit 的 result generation。 |

只有**同时**满足以下全部条件，一次 pairing 才产生 `verification_source=pairing_code` 的 checkpoint：

1. 批准方是该 exact AccountId 的 accepted、未撤销、current generation 内设备；
2. candidate 对 exact device signing key 与 `hpke_key` 提供 §5.2.2 的有效持有证明；
3. `pairing_code`、`device_pairing_request_id`、`gate_audience`、`expires_at`、candidate keys 与 metadata 绑定到同一份 §2.1.2 canonical transcript，完整 `AccountId` 由 §5.2.2 target proof 的签名成员 `account_id` 绑定到同一份 target signature（stage 是 account-less 的，账号不可能进入 §2.1.2 transcript）；
4. 用户通过扫码、输入短码（§2.1.1 第 5 条的认证短码认领），或在配对链接流程中显式确认短码，完成带外确认；
5. accepted `ak.device.authorize` 与对应 checkpoint 在同一原子提交可见，或可从同一 accepted authorization 与已签 transcript 确定性重建。

以下 MUST NOT 单独产生 checkpoint：账号登录因子、SSO session、普通 `ak.session.grant`、仅向用户展示 fingerprint、服务端自报“这是同一设备”，以及任何未完成上述带外确认的候选流程。新增 verification source MUST 先扩展本节封闭集合与上述 schema 枚举；实现不得用任意字符串、profile 自报或本地标记进入该集合。`verification_source` 与 DID URL 形态的 `verification_method` 是两个不同字段，MUST NOT 互相替代。

checkpoint 的失效遵守既有 lifecycle 与 generation 规则，不另设独立超时：

- 目标设备被 revoke 或进入 `revocation_pending`：该 checkpoint MUST NOT 再用于 live authorization；
- authorize generation 被 fence，或设备 key rotation 后 checkpoint 不再绑定 exact key：evidence MUST 变为 `stale`；
- 没有可验证 checkpoint，或 PCR evidence 出现 gap / 冲突：evidence 保持 `unresolved`，MUST NOT TOFU。

account `device_summary` 的 `verification_source` MUST 在 evidence=`verified` 时出现，在 evidence=`unresolved` 时缺省；曾 verified 后转 `stale` 的 row 保留原 `verification_source` 作为 provenance，但 MUST NOT 据此继续 live authorization。该字段是 provenance 投影，不是第二个真相源：checkpoint 本身仍由 accepted PCR evidence（§5.5）与上述条件决定。

`stale` / `unresolved` 的历史设备、受控导入设备与 key rotation 后的设备统一重新走 §2.1 的 account-bound pairing / re-verification ceremony 取得新 checkpoint。v1 不提供第二套 device-level 验证协议，也不定义独立的“验证设备”页面或 verification 专用二维码；§2.1.1 的 pairing 二维码是唯一 QR 载体。

跨 principal 的联系人验真不在 v1 范围：它应绑定双方 stable principal / identity key 的 safety number，而不是逐台确认会轮换的 device key。v1 MUST NOT 以 device-level 验证消息、to-device transcript 或本地 trust receipt 冒充该能力。

### 10.2 新设备 MLS 建立（normative）

新设备不得向旧设备请求或接收账户 secret、MLS epoch/exporter secret 或 active group state。完成 §10.1 verification checkpoint 与当前设备授权后，它只能发布自己的 KeyPackage，由每个目标 scope 的当前成员提交 Add，并通过该设备专属的 `MlsWelcomeDelivery` 取得 Welcome。Welcome 只建立从该次 Add 开始的成员资格，不补发加入前的解密材料。

账户级 `secret_storage` 恢复仅使用 §12 的端到端加密备份；identity root、device private key、MLS private state、sender counter 与 pending Welcome 永不通过 to-device 消息共享。配对二维码、短码和链接也不得携带这些材料。

## 11. Secret Storage（client-local cache form）

Secret storage 用于保存：

- recovery secret（仅 `personal_node + single_point_of_failure=true` 的显式降级可在可信本地 keychain 持久化；其他 profile 只能在 custody 仪式内瞬态存在，local cache 最多保留不可逆 fingerprint / durable checkpoint，不得保留 secret bytes）
- applet delegated device secret

`ak.secret_storage.v1` 是 **client-local** envelope，仅用于设备本地或可信操作系统 keychain；**不得作为线级 (wire) 上传格式**。

Station device/key surface 的 `ak.keys.backups.*` endpoint MUST 只接受 `ak.schema.key_backup.v1` wire envelope。任何不符合 `ak.schema.key_backup.v1` 顶层 `required`（含 `series_id` / `series_seq`）的请求体 MUST 返回 `schema_violation`，原因码 `key_backup_wire_schema_required`。Client-local `ak.secret_storage.v1` 存储不受影响，但 MUST NOT 通过 `PUT /_arkret/self/keys/backups/{backup_id}` 同步。

任何同步到 Station device/key surface 或其它远端服务的 secret，MUST 使用 §12 的 `ak.schema.key_backup.v1` envelope，并设置对应 `backup_kind`：

| Secret 类别 | `backup_kind` |
| --- | --- |
| 账户级 secret-storage material | `secret_storage` |
| 外部托管或 profile 自定义 account secret | `secret_storage` |

每个 `backup_kind` MUST 使用独立 HKDF info 字符串派生 commitment / wrap key，禁止跨 class 共享密钥材料。规范权威表述见 [`../identity/key-management.md` §7.1](../identity/key-management.md)：HKDF info 形如 `arkret-key-backup/<backup_kind>/<subdomain>/v1`（`/` 分隔，含 subdomain 维度）。任何 v1 wire 实现 MUST 跟随 `identity/key-management.md` 的 canonical 形式，本节描述只作为引导。

recovery secret、identity root seed、HKDF PRK 与完整派生 private key 不属于上表任何 wire 类别；即使本地 `ak.secret_storage.v1` 降级缓存允许持有 recovery secret，也 MUST NOT 把该 item 映射为 `ak.schema.key_backup.v1`、`ak.secret.send` 或任意远端同步对象。

Client-local secret storage 的存储格式仍可使用本节的 `ak.secret_storage.v1` envelope，但其字段不进入任何 wire / hash / 签名输入；服务端不接受该 envelope。

## 12. Key Backup

`backup_kind=secret_storage` 表示端到端加密备份。治理 Station 只保存密文、版本链和当前 Realm stream 的 `realm_commit_id` 锚点，不能解密、补发或据此取得 MLS 成员资格。重新加入 MLS group 必须由当前治理 Station 接受成员 Event 与 `mls_commit_submission`，再通过单独的 `MlsWelcomeDelivery` 私密投递 Welcome。

### 12.1 Backup API

备份上传、读取和删除仍使用 `ak.schema.key_backup.v1`。每个 successor 必须链接同一 series 的直接 predecessor；客户端验证密文摘要、设备签名以及可选 `source_commit_ref`（出现时其 `realm_commit_id` 与 `device_generation_ref` 都必须存在），但该锚点只证明备份产生时观察到的 Realm stream 位置，不证明任何 Circle 或 Sidecar stream 的位置。`ak.key_backup.active_series` 的 signed payload 复用同一个闭合两字段锚：唯一顶层名是 `source_commit_ref`，`realm_commit_id` 直接使用强类型 `RealmCommitId`；`source_ref`、内层 `commit_ref` 和完整 `CommittedEventRef` 都不是 v1 wire，MUST 在验签或状态写入前拒绝。

### 12.2 Retention and Erasure

服务端按账户保留策略删除密文；删除备份不删除 RealmCommit 或 Event。客户端不得把服务端持有密文解释为服务端持有解密能力。

## 14. PCR-Policy Device Recovery

全设备丢失时，账号重新登录不能替代 PCR recovery proof。基础路径由丢失前已进入 accepted RealmCommit 的
recovery policy 授权，并由唯一的 RecoveryTransaction terminal commit
（[`../identity/security-transactions.md` §2](../identity/security-transactions.md)）在同一事务内提交两条 Event
与承载它们的、position 连续的首批新 generation RealmCommit（每条 Event 各一笔）：

1. replacement device 签署的、policy-authorized `ak.device.reanchor` 绑定 policy/version/session、exact `account_id`、replacement
   authorize payload digest 与 monotonic PCR generation CAS；
2. 同一 replacement device identity key 自签 `ak.device.authorize`，`authorization_binding_kind="pcr_recovery"`。
   它不携带任何指向 re-anchor Event 的信封字段：两条的唯一绑定是 re-anchor payload 中
   `replacement_authorize_payload_digest` 对本条 authorize payload 的**单向**承诺，次序由这份 unit 的
   wire 顺序与同一事务内 position 连续的两笔 RealmCommit 落定。

构造方必须先冻结该 recovery unit 唯一的 canonical 毫秒 authoring checkpoint `T`，再构造、求摘要并签署两条 Event；re-anchor、replacement authorize 及各自唯一 producer proof 的 `created_at` 必须全部逐字等于 `T`。`T` 是该 unit 在已签历史窗口比较中的唯一 Event-time / signer-window / policy-session 时间坐标，proof 不另建签名时间轴；接收方按 [`event-and-patch.md` §3.2](../models/event-and-patch.md) 在验签与任何 recovery 状态写入前 fail closed 比较，并继续以可信 `now` 独立执行现有 current session/lease expiry 等 live admission 检查。

两条 Event 与各自对应、位于同一 PCR stream 连续 position 的两笔新 generation RealmCommit 必须在同一原子提交中接受；两笔 RealmCommit 仅由当前治理 Station 签发，replacement device 只签两条 Event 与 receipt。receipt
`scope.kind="device_reanchor_unit"`。该 scope 的封闭字段集恰为
`{kind, account_id, realm_id, previous_device_generation, new_device_generation}`：它与 `ak.device.reanchor` payload 选择同一个 exact AccountId，每个同名字段 MUST 与被覆盖 payload 逐字节相等，任一不等以 `device_reanchor_authority_mismatch` fail closed。re-anchor 与 replacement-authorize digest 分别从 `events[]` 中唯一对应 kind 的 typed `event_id` 解码，scope 不重复携带。scope MUST NOT 携带 `did_version_id`、
`registry_head` 或任何 DID publication 字段，接收方也 MUST NOT 由 generation ref 反向合成它们。接受后
generation fence 使旧 generation 全部失效。`current_device_generation_ref` 是 PCR-local monotonic ref，
MUST NOT 使用或等于 DID `versionId`；resolution typed current result 不随基础恢复推进。

DID-root 只是在 recovery policy 中显式启用、可撤销的一种 proof kind。当前 DID root 本身不能
re-anchor；method 不支持 history/pre-rotation 或 policy 未启用时必须拒绝。RecoveryTransaction 不包含
DID publication；用户执行 resolution successor 时必须走独立 DID operation 发布流程，且其失败不得改变
PCR recovery transaction 的 accepted-step ledger。

**候选设备 key 的唯一承诺与 PoP（normative）**：create request 在 `requesting_device_id` 后必须携带
`requesting_device_public_key_did` 与 `requesting_device_signature`，前者是无 fragment、规范编码的 Ed25519
`did:key` 公钥值。该公钥值本身是唯一冻结承诺，不另携可被替换的 key alias。它与 DPoP grant-binding key
独立，必须满足 §3 的身份 key/会话 key 分离规则。

create-time PoP 的封闭对象由
[`recovery-session.schema.json#/$defs/recovery_device_possession_transcript`](../../artifacts/schemas/recovery-session.schema.json#/$defs/recovery_device_possession_transcript)
定义：`schema="ak.identity.recovery_device_possession.v1"`、`request_id`、`session_grant_id`、
`session_grant_cnf_jkt`、`account_id`、`requesting_device_id`、`requesting_device_public_key_did`、
`trust_domain` 和条件式 `expected_recovery_policy_ref`。grant id/JKT 必须从认证本次请求的
`recovery_session` grant 取得，不能由未认证 body 指定；其它成员与 create request 逐字相同。
`expected_recovery_policy_ref` 仅在请求提供时包含，不得将省略改为 null。签名原像为
`UTF8("ak.identity.recovery_device_possession.v1\n") || JCS(上述对象)`，签名是 64 字节 Ed25519 signature
的 base64url 无填充编码。`requesting_device_signature` 本身不进入原像。未知 multicodec、错误长度、
非规范 key 编码、错误 PoP 或与 grant-binding key 复用均 fail closed，使用现有 `recovery_evidence_unbound`。

来源 Station 必须在生成 session/challenge 及写入 pending session **之前**验完 PoP，并把公钥值冻结在
`RecoverySessionState.requesting_device_public_key_did`。所有 factor（含显式 `did_root`）的
`did_root_transcript` / `generic_recovery_transcript` 均必须在 `requesting_device_id` 后包含此冻结值。
只证明持有 device id 字符串或 DPoP key 不满足该条件。session create 的 canonical intent 幂等摘要覆盖完整
请求（包括 PoP）；同 grant/request_id 异 intent 为 `duplicate_conflict`，精确重试不换 key、不换 challenge。

`recovery_unlock.recovery_secret_ref` 是 accepted recovery-policy key entry 的不透明本地引用标签，
不是 DID、DID URL 或公钥编码；它不得用看似 `did:key` 的占位文本冒充可解析验证方法。实际签名 key
只由同一 proof 的 `verification_method` 指定，该值必须是可解析的真实 DID URL，并逐字匹配 session
冻结的 policy entry。fixture 可使用公开测试 key，但 label 与 verification method 两个名字空间不得混用。

**unit admission 与原子边界（normative）**：两条 Event 的 proof method 均使用同一已验证 account DID 下、
fragment 精确等于 `requesting_device_id` 的设备 method。verifier 从该账号已有可信 binding/accepted PCR
resolution evidence 校验 principal 投影，不要求重新在线读取 current DID history；不得以设备 `did:key` 为
Event actor 或把它冒充 account DID。unit-local overlay 的 key、session 冻结 key、两条 Event 实际验签 key
与 authorize payload key 必须逐字相符；authorize 的 device id 必须等于 session requesting device id。
先验 candidate key 的签名不是授权：接收方仍必须验证 exact AccountId/Station/PCR lineage、当前有效的
policy/version、已 verified 且未过期的 session、原 grant/JKT、challenge、generation 与完整 checkpoint CAS、
re-anchor 的 authorize payload digest 承诺，以及该 unit 恰为两条 Event、wire 顺序固定、并在同一 PCR stream 上取得 position 连续的两笔 RealmCommit。

RecoveryTransaction 终结时，reanchor Event 与 replacement-device authorize Event 必须分别取得同一 PCR stream 中连续的 `CommittedEventRef`。generation CAS、设备目录变更、session 消费与 transaction completion 在同一事务提交；失败为零写入。byte-identical retry 返回同一 receipt，异内容返回 conflict。

基础 `pcr_policy` 恢复 MUST NOT 要求 `registry_head`、current DID updateKeys、`did_recovery_anchor` ref、
旧 `payload.did_version_id` 或 DID publication；session schema 不含 `registry_head`。DID 服务不可达不得
成为基础 policy 恢复的额外前提。显式启用 `did_root` factor 时，该 factor 自身的 current authority、
history/pre-rotation 验证仍须完成；即使它验证成功，两条 Event 也仍由上述 replacement key 签署。

### 14.1 Device lifecycle 与 trust 正交状态

设备 lifecycle 为 `active | revocation_pending | revoked | expired | generation_fenced | conflicted`；其中 `conflicted` 只报告设备本身的已验证冲突，不得从 pending/rejected re-anchor 候选数目派生，generation 的推进唯一遵循完整 unit 的 RealmCommit committed 结果；承载两条 recovery Event 的两笔连续 RealmCommit 只能由当前治理 Station 在 RecoveryTransaction 的 `commit_recovery_unit` 原子提交中签发，terminal completed 而缺少任一 RealmCommit、或任一 RealmCommit 已提交而 transaction 未 completed 都不是可观察状态。验证状态为 `verified | unresolved | stale`。**两维都是读侧折叠而非存储轴**：lifecycle 六值的封闭折叠输入与固定优先序见 §5.5.3，设备授权事实与 generation 的存储形态见 §5.5.1 / §5.5.4。两维 MUST 分开投影——此处「投影」指分别折叠、分别呈现，MUST NOT 读成分别存储——account `device_summary` 不得用 verification 值代替 lifecycle status，也不得因 evidence unresolved 省略 lifecycle。新 live 业务授权要求 lifecycle=`active`、evidence=`verified`、authorize generation 等于治理 Station 在接纳事务中验证的 current generation，并遵守本节已知撤销与 revocation-pending gate。设备 authorize/re-anchor 的权威来源必须是已确认 PCR 安全状态；普通目标 Event 不要求 producer 先取得额外的新 RealmCommit basis，也不要求 origin Station 在线，但它自身必须由目标 stream 的 current governance Station 在解析授权实例、依赖与关闭集合后签发 covering RealmCommit，才成为 accepted。安全目标继续按其 state-changing Event/unit 的附加事务规则生效。历史资格按 event-auth-state-resolution 的精确授权实例与 committed 关闭边界判断，不以当前查询 TTL 追溯抹除合法历史。任何实际必要的单一条件失败都不能由账号 session、DPoP 或 transport service signature 补足。

### 14.2 Recovery UI requirements

客户端必须在任何网络副作用前 durable 保存本次流程需要的 device identity、HPKE、DPoP keys 与完整 onboarding/recovery draft；新注册还须保存 identity root/recovery material，基础 policy recovery 不要求持有注册 identity root。恢复 secret 按 key-management 的本地保管规则处理。UI 应区分：可 exact retry、genesis 已由另一 unit 赢得、必须 re-anchor、以及无 proof 无法恢复；不得让用户通过再次注册静默替换既有 PCR。

## 15. Applet Device Delegation

Applet-managed principal（Bot Actor 与 Ghost Actor，见 [`../extensions/applet-integration.md` §3.3 / §3.4](../extensions/applet-integration.md)）如需参与 E2EE——发布 KeyPackage、作为 Welcome 接收方入组、签署 MLS durable receipt——MUST 使用**受限 delegated device**。本节对 Bot 与 Ghost 等效适用：两者用同一个 managed-actor provision + `applet_managed_control` PCR 模型，因此也用同一条设备授权路径，不存在只覆盖其中一方的形态。

Delegated device 不引入新的 MLS recipient endpoint 分支：它就是普通 device 分支的成员，§9.2.1 的 device / Agent 两分支封闭 XOR 不变。

- **唯一授权路径**：一条 `authorization_binding_kind="applet_managed_delegation"` 的 `ak.device.authorize`，在该 principal 自己的 `applet_managed_control` PCR 中作为 **genesis 之后的普通后继 Event** 提交，形状与约束见 §5.2.3，签名方解析见 §5.3。MUST NOT 把它塞进 install fixed set、Ghost provisioning aggregate 或任何 genesis unit；MUST NOT 让 Applet service 以自己的 `service_id` 代替该 principal 授权设备。
- **有界委托**：`scopes` MUST 非空且限制到该 delegated device 实际需要的 Realm / 动作，`expires_at` MUST 是非 null 的到期时刻。过期后该设备 MUST 与 `expired` lifecycle 一样失去新业务授权（§14.1）。
- **跟随 install revoke fence（normative）**：delegated device 的有效性 MUST 与 payload `applet_id` 指向的 exact Applet install 的 active 状态做 AND，判定口径与 [`../extensions/applet-integration.md` §4b](../extensions/applet-integration.md) 的 revoke fence 逐字一致。该 install 被 fence 之后，接收方 MUST 立即拒绝该设备的新 KeyPackage 发布、新 Welcome 准入与新 MLS durable receipt，code=`applet_revoked`；MUST NOT 等待另一条 `ak.device.revoke`，也 MUST NOT 因为 PCR 中该 authorize 仍在而认为设备仍然有效。缺少这一条，撤销一个 Applet 之后它的 Bot 仍能继续签 MLS 回执。历史读取与既有 accepted Event 的复验不受影响。
- **不得向上委托**：delegated device MUST NOT 授权任何新设备——它 MUST NOT 作为 `accepted_device` 分支的批准方，也 MUST NOT 签发第二条 `applet_managed_delegation` authorize。managed principal 的设备集合只能由其 controller method 直接授权。
- **不得跨 namespace**：delegated device 的 to-device 权限 MUST 只覆盖其 Applet namespace 内的 actor。
- **不进入 PCR recovery**：`applet_managed_control` PCR 不使用 `pcr_recovery` 分支。Applet 丢失 delegated device 私钥时，正确做法是 revoke 该设备并授权一台新的 delegated device；MUST NOT 为 managed principal 发起 human recovery session 或 factor transcript。
