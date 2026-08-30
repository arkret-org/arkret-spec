---
title: Device Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-08-11
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. Login & Authorization Boundaries

去中心化协议摒弃了传统的账号+密码中心化认证模式，身份的本质是持有私钥。Arkret 把以下三件事分开处理：

- **登录因子验证**：Auth Server 验证 password、passkey、OIDC、SSO 或 recovery factor，只能产出 sender-constrained handoff/session、触发 identity-root recovery，或请求已有 accepted device 批准配对；它不能自行产生设备授权。
- **设备授权**：新设备成为长期有效设备，MUST 落成 `ak.device.authorize`、DID/key-log operation 或等价 signed event。只有这一步改变设备集合。
- **设备密钥验证**：SAS/QR 只确认 device key / identity key 的人工信任。验证成功不得自动创建登录态、长期 device grant 或 Realm capability。

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

`session_public_key` 不仅是会话身份标记，还是会话请求的 proof-of-possession 出示密钥：日常受保护请求 SHOULD 用该 key 对请求做 RFC 9421 HTTP Message Signature（sender-constrained 出示），使会话出示与该 key 绑定，仅截获 `ak.session.grant` 不足以重放。行使该 key 出示的具体形态、覆盖的 components 与 replay window 见 [`../sync/api-conventions.md` §3.2](../sync/api-conventions.md) 与 [`../sync/service-http-binding.md` §2.5](../sync/service-http-binding.md)；高安全 deployment profile 下该 PoP 出示对所有受保护 `ak.self.*` operation 升为 MUST。

资源服务器验证的是 session grant、device authorization、DID proof、capability 和 Realm policy，而不是“用户刚刚输入了正确密码”。密码、SSO session 和 service account id 都不能直接作为 `actor_id`、event sender 或 capability subject。

服务账号密码重置只改变服务账号登录凭据；除非同时存在有效 DID 控制证明或 recovery policy 事件，否则不得自动授予 DID 控制权、不得签发长期 device grant、不得访问 E2EE 密钥备份。

### 1.2 登录、设备授权与设备验证的边界

登录因子验证、设备授权与设备密钥验证的三项边界以 §1 的列表为唯一规范来源。
“新设备登录”的推荐实现是：新设备先本地生成 device key，使用登录因子或已授权设备完成交互验证，再由当前有效授权方签发 `ak.device.authorize` 或短期 `ak.session.grant`。短期 Web/OIDC 登录可以只使用 `ak.session.grant`；需要 E2EE 历史、secret storage 或长期离线能力时，仍必须走设备授权和设备密钥验证。


## 2. 多设备配对 (Device Pairing)

在 Arkret 中，用户的每个物理/逻辑设备都应该拥有本地独立生成的设备级密钥对 (Device Key)。
多设备登录的过程，本质上是“已授权设备将新设备加入身份控制网”的密码学授权过程。

### 2.1 配对流程 (无密码登录)
1. **新设备初始化**：用户在新手机或新电脑上打开应用，本地生成一组全新的 Ed25519 密钥对。屏幕上显示包含公钥与临时连接信息的二维码 (QR Code)。
2. **主设备扫码**：用户使用已登录的主设备（如已通过面容 ID 解锁的手机）扫描该二维码。
3. **密码学授权**：
   - 主设备验证 pairing challenge 且用户完成显式确认后，签发完整 `ak.device.authorize` Event Initial Submission、符合 DID method 的 key-log operation，或触发 recovery policy 允许的设备授权流程。
   - DID Document SHOULD 只承载身份控制密钥和服务发现入口。普通设备列表、设备信任状态、吊销状态和算法更新 SHOULD 由 `ak.device.*` 事件、device key log 或受控 device registry 表达；只有 DID method 本身要求时，才把设备 verification method 写入 DID Document。
   - 短期浏览器或临时执行环境 MAY 只拿到 `ak.session.grant`，但它不改变长期设备集合，也不得访问 E2EE 历史密钥，除非另有有效设备授权和密钥共享流程。
4. **状态下发**：主设备通过点对点信道或安全的 Principal Server sync surface，将必要的工作区快照、加密会话历史（通过 MLS Welcome / Commit 把新设备加入合适的 group）同步给新设备。
5. **事件广播**：主设备向 principal control stream 广播自己原始签署的 `ak.device.authorize` Event Initial Submission；若封装为 Event Envelope，其 `realm_id` 是目标 principal 的 `principal_control_realm_id`。`pair_device` 请求 MUST 携带该 exact submission；payload 是 commit 阶段 `hpke_key` 与新设备 exact `device_signature` 的唯一 wire source，request 顶层不得复制二者。Account Authority / Principal Server MUST 走普通 Event admission、复算 payload / envelope digest并验证当前设备 proof 与 candidate possession proof（`accepted_device` 分支的 possession domain 与签名对象见 §5.2.2），MUST NOT 代铸 Event、替换 payload 字段或直接写 device-list projection。新设备获得的能力由该 accepted Event、session grant、Realm capability 和 policy 共同限制，不是自动获得 principal 的全部权限。

#### 2.1.1 短链暂存与 resolve（server-mediated，normative）

§2.1 步骤 1 的“临时连接信息”MAY 由 Principal Server 暂存并以短句柄承载，而非把设备公钥与配对材料整包放进二维码。采用该短链形态时 MUST 满足以下约束；它只改变“配对材料如何到达主设备”这一传输层，不改变 §2.1 步骤 3 的授权模型。

1. **暂存（stage）**：新设备经**免认证**端点 `POST /_arkret/open/device-pairing/requests`（`ak.open.device_pairing.command.stage.v1`）提交 `new_device_pubkey`（canonical `PublicKey`，见 [`public-key.schema.json`](../../artifacts/schemas/public-key.schema.json)：`kty` / `kid` / `algorithm` / `key` 四字段，`key` 为密钥材料、`kid` 为 `ak:device:<uuidv7>`）与 `client_nonce`，以及可选 `display_name` / `device_metadata`。**stage 请求 MUST NOT 携带 challenge proof**——该 proof 必须承诺 server 在本次调用中才铸出的值，因此在 stage 时不可能存在（这条顺序约束是 §2.1.2 transcript 可生成性的前提）。Server 铸 `device_pairing_request_id`（`device_pairing_request:<uuidv7>`）、短 `pairing_code`、`gate_audience`（本 Account Authority 的 `gate_account_base_url` origin）与 `server_nonce`，以有界 TTL（SHOULD ≤ 10 分钟）暂存一条 **account-less** 记录（state `pending_authorization`），返回 `{device_pairing_request_id, pairing_code, gate_audience, server_nonce, expires_at}`。暂存记录 MUST 同时保存提交的 `new_device_pubkey` 与 `client_nonce`——它们是 §2.1.2 路径 A transcript 的 member，gate 必须能只凭该记录重算 transcript。暂存记录在被授权前**不绑定任何 principal、不授予任何东西**。
2. **短链承载**：stage 返回后，新设备按 §2.1.2 生成 `challenge_proof`，再按 §5.2.2 生成 `device_pairing_target_attestation`（承载它自己的 `hpke_key` / `algorithms` 并绑定该 `challenge_proof` 的 `transcript_digest`），由二维码同时承载短 deep-link、该 proof 与该 attestation：`{arkret_base_url}/_arkret/open/device-pairing/resolve#token=<token>&proof=<proof>&attestation=<attestation>`，其中 `token = base64url_nopad(canonical_json({"r": device_pairing_request_id, "c": pairing_code}))`，`proof = base64url_nopad(canonical_json(challenge_proof))`，`attestation = base64url_nopad(canonical_json(device_pairing_target_attestation))`。`token`、`proof` 与 `attestation` MUST 仅出现在 URL fragment 或请求 body，MUST NOT 进入 URL path 或 query（避免进入服务端/代理日志）。**proof 与 attestation 走带外通道到达主设备，MUST NOT 经免认证 stage / resolve 面回传给 server**：暂存面是匿名的，让它持有这两者既无必要也扩大攻击面。二维码容量不足时 SHOULD 缩短 `device_metadata` / `display_name` 等可选材料，MUST NOT 把 attestation 改由服务端中转。
3. **resolve 与人工确认**：已授权设备经**免认证**、body-only 的 `POST /_arkret/open/device-pairing/resolve`（`ak.open.device_pairing.read.resolve.v1`）以 `token` 换取 `DevicePairingBootstrap`（含 `arkret_base_url`、`device_pairing_request_id`、`pairing_code`、`new_device_pubkey`、`client_nonce`、`gate_audience`、`server_nonce`、可选 `display_name`/`device_metadata`、`expires_at`）。bootstrap **不含也不得含** `hpke_key`、`algorithms`、`challenge_proof` 或 attestation：这些只经带外通道到达，权威来源见 §5.2.2。已授权设备 MUST 用这些 server-minted 值按 §2.1.2 重算 transcript 并对二维码带来的 `challenge_proof` 完成验签，**再按 §5.2.2 独立重建并验签 `device_pairing_target_attestation`**（要求 `device_id` 等于 `new_device_pubkey.kid`、`device_public_key_did` 与 `new_device_pubkey.key` 解码为同一 Ed25519 key、`pairing_challenge_transcript_digest` 逐字节等于自己刚重算的 `transcript_digest`），全部通过后才可向用户呈现为可配对设备。授权 UI MUST 同时显示 requesting-device metadata、`device_id` / key fingerprint、完整 pairing code 与 `gate_audience`，并要求用户把 code 与新设备屏幕逐位比较后显式确认；通过密码学校验本身不得自动触发授权。用户确认后，批准设备 MUST 从验签通过的 attestation（而非服务端响应或 UI 输入）取 `hpke_key` / `algorithms` 填入 authorize payload，再按 §2.1 步骤 3 走 `ak.gate.account.command.pair_device.v1` 授权：该授权端点仍要求授权方是**已验证设备**，server MUST NOT 因短链暂存本身改变设备集合或放宽授权前置。
4. **回填与 status**：授权端点 MAY 携带 `device_pairing_request_id`。携带时，Account Authority MUST 要求该 id 对应的暂存记录仍为 `pending_authorization` 且未过期，要求记录中的 `pairing_code`、`new_device_pubkey` 与授权请求逐字段一致，并**按 §2.1.2 用该暂存记录自己的字段重算 transcript、验证请求携带的 `challenge_proof`**（逐字段相等比较只能证明字节未被中途替换，不能证明签名对哪个 challenge 或哪个 audience 有效，因此 MUST NOT 用相等比较代替验签）；随后**按 §5.2.2 用同一次重算得到的 `transcript_digest` 与 `authorize_event.event.payload` 的目标材料重建 accepted_device possession 对象、验证 `device_signature`**。这两次验签、设备授权 Event 走普通 admission 落库、device projection 更新、暂存记录消费并翻为 `authorized`（记录 `device_id` 与 `authorized_event_ref`）**MUST 在同一原子边界内完成**：任一不匹配不得授权设备，且不得留下已消费但未授权、或已授权但未消费的中间状态。响应丢失后的重放不是幂等成功——暂存记录已不是 `pending_authorization`，第二次提交 MUST fail closed（不得授权第二台设备、不得重铸 Event），调用方以 status 轮询或 `uncertain_outcome` 指定的查询操作确定结果。新设备经**免认证**、body-only 的 `POST /_arkret/open/device-pairing/requests/status`（`ak.open.device_pairing.read.status.v1`）以 `{device_pairing_request_id, pairing_code}` 轮询得到 `{state, device_id?, authorized_event_ref?}`；`authorized_event_ref` 是 §5.4.1 装配前强制校验的入口。
5. **防枚举（normative）**：`resolve` 对 {未知 id、`pairing_code` 不符、已过期、非 `pending_authorization`} MUST 返回统一 `not_found`。`status` 对 {未知 id、`pairing_code` 不符} MUST 返回同样的 `not_found`；凭证正确时可返回 `pending_authorization`、`authorized` 或 `expired`，其中 `authorized` MUST 同时携带 `device_id` 与 `authorized_event_ref`，其余状态 MUST 不携带这两个字段。不得通过错误形态泄露 id 是否存在或 code 是否正确。`pairing_code` MUST 使用 §7 定义的 8 位 Crockford-style CSPRNG code，并由暂存、resolve 与 status 端点限速兜底。
6. **有界与清理（normative）**：免认证的 stage、resolve 与 status 端点 MUST 限速；过期暂存记录 MUST 对 `resolve` fail closed，`status` 在凭证正确且记录尚处于有界清理保留期时返回 `expired`，清理后返回 `not_found`。过期记录 SHOULD 被定期清理，Server MUST NOT 无界保留。

#### 2.1.2 Pairing challenge proof transcript（normative）

`challenge_proof` 是新设备对 `new_device_pubkey` 的 possession proof，且**必须绑定本次配对挑战**。它的 wire 形态是 [`device-pairing.schema.json`](../../artifacts/schemas/device-pairing.schema.json) 的 `device_pairing_challenge_proof`（`{transcript, kid, signature_algorithm, transcript_digest, signature}`），MUST NOT 退化为无语义的 base64url 字节串。`kid` 是选择 staged key 的 device-local `ak:device:` key id（[`did-usage-and-verification.md` §2.3](../identity/did-usage-and-verification.md) 已登记的非 DID 分支），不是 DID URL，因此不得命名为 `verification_method`。

**签名输入（两个封闭 transcript，由 proof 的 `transcript` 字段判别）**：

```text
new_device_pubkey_digest = "sha256:" || lowercase_hex(sha256(canonical_json(new_device_pubkey)))

# 路径 A：server-mediated 短链（§2.1.1）
ak.device-pairing.challenge.v1:
  UTF8("ak.device-pairing.challenge.v1\n") || canonical_json({
    client_nonce,
    device_pairing_request_id,
    expires_at,
    gate_audience,
    new_device_pubkey_digest,
    pairing_code,
    server_nonce
  })

# 路径 B：to-device 验证（§7）
ak.device-pairing.challenge.to_device.v1:
  UTF8("ak.device-pairing.challenge.to_device.v1\n") || canonical_json({
    expires_at,
    gate_audience,
    new_device_pubkey_digest,
    pairing_code,
    request_canonical_digest,
    transaction_id
  })
```

`canonical_json` 按 [`../conformance/encoding.md` §2](../conformance/encoding.md)（JCS）。`transcript_digest` 是上述完整 bytes 的 `sha256:<hex>`。

**签名与验签**：

- 签名密钥固定为 `new_device_pubkey` 对应的私钥；proof 的 `kid` MUST 逐字节等于 `new_device_pubkey.kid`，`signature_algorithm` MUST 是 [`signature-alg-registry.json`](../../artifacts/registry/signature-alg-registry.json) 的 active suite 且与 `new_device_pubkey.algorithm` 相容。
- verifier MUST **自己重算** transcript bytes，MUST NOT 用「与存档副本逐字节相等」代替验签。重算 digest 与 `transcript_digest` 不等 MUST 拒绝，且 MUST 在验签之前拒绝。各 verifier 的 transcript 输入来源固定如下：

  | verifier | 路径 | transcript 输入来源 |
  | --- | --- | --- |
  | 已授权设备 | A（短链） | `resolve` 返回的 `DevicePairingBootstrap`（`device_pairing_request_id` / `pairing_code` / `gate_audience` / `server_nonce` / `client_nonce` / `expires_at` / `new_device_pubkey`） |
  | 已授权设备 | B（to-device） | to-device 消息中**已进入用户确认 transcript** 的值（`transaction_id` / `pairing_code` / `gate_audience` / `request_canonical_digest` / `expires_at` / `new_device_pubkey`） |
  | Account Authority gate | A（请求携带 `device_pairing_request_id`） | **该 id 对应的暂存记录**，逐项取服务端自己铸出的值；MUST NOT 从请求体取这些值 |
  | Account Authority gate | B（请求携带 `challenge_transcript`） | 请求体的 `challenge_transcript`（`transaction_id` / `request_canonical_digest` / `expires_at`）+ 请求体的 `pairing_code` 与 `new_device_pubkey` + **gate 自己的 `gate_audience` origin** |

- **路径 B 下 gate 的 `gate_audience` MUST 取自身 origin，MUST NOT 接受请求体提供的值**。这正是阻断跨 Account Authority 重放的机制：新设备签的是它以为的目标 authority，若与实际受理方不同，签名必然验不过。允许客户端提供该值等于把这层保护交还给攻击者。
- 路径 B 下 gate MUST 在验签之前先拒绝已过期的 `challenge_transcript.expires_at`。
- `ak.gate.account.command.pair_device.v1` 的请求体 MUST 恰好携带 `device_pairing_request_id`（路径 A）或 `challenge_transcript`（路径 B）之一；两者同时出现或都缺失 MUST `schema_violation`。这条排他约束在 schema 层由 `oneOf` 强制，使 gate 永远知道该用哪套 transcript，而不是靠猜。
- `transcript` 名与当前路径不符 MUST 拒绝；MUST NOT 接受路径 A 的 proof 用于路径 B（反之亦然）。
- proof 未通过验证的暂存记录 MUST NOT 授权任何设备；缺失 `challenge_proof` 的 `ak.gate.account.command.pair_device.v1` MUST `schema_violation`。
- 本 proof 的 `transcript_digest` 同时是 §5.2.2 `accepted_device` possession attestation 的唯一绑定成员。**两条路径共享同一个 attestation schema（`device_pairing_target_attestation`）与同一个 domain**：该对象只绑一个 digest，而路径 A / 路径 B 的 transcript 各自封闭且互不接受（见上一条），所以 digest 本身已经携带路径判别，attestation 无需再分叉成两个形态。verifier MUST 先按本节选定并重算本路径的 transcript，再用得到的 digest 校验 attestation；MUST NOT 直接采信 attestation 自带的 digest 值。

**为什么必须绑定这些值**：只签静态公钥的 proof 可跨 request、跨 origin、跨过期窗口重放；只做非空/格式检查等于没有 PoP。`gate_audience` 阻断跨 Account Authority 重放，`pairing_code` + `device_pairing_request_id` + `server_nonce`（或路径 B 的 `transaction_id` + `request_canonical_digest`）阻断跨 request 重放，`expires_at` 阻断过期窗口外重放。

**失败语义**：transcript 重算不符、proof `kid` 与 `new_device_pubkey.kid` 不等、`signature_algorithm` 不在 active suite、签名验证失败，一律 `failed_precondition`，对外按 §2.1.1 第 5 条的防枚举要求返回统一形态；同一 pairing transcript 累计 10 次失败后按 [`../sync/service-http-binding.md` §3](../sync/service-http-binding.md) 锁定并永久失效。

#### 2.1.3 Pairing challenge 的 conformance 入口

`vector_id`: `ak.vector.device_pairing.challenge_transcript.v1`（向量说明见
[`../conformance/conformance-vectors.md` 23.10](../conformance/conformance-vectors.md)）。它覆盖
stage 到 gate 的 round-trip 正例、同一 `new_device_pubkey` canonical bytes 与 digest 全程不变，
以及坏 audience / 坏 request digest / 旧 pairing code / 跨 request 重放 / 过期 / 改 key / 坏签名 /
proof `kid` 不匹配 / 跨路径复用 proof / 旧 `{kid, alg, public_key}` 形态 /
stage 请求携带 proof 等负向量。

`vector_id`: `ak.vector.device_pairing.accepted_device_attestation.v1`（向量说明见
[`../conformance/conformance-vectors.md` 23.10](../conformance/conformance-vectors.md)）。它覆盖
§5.2.2 attestation 的正例、attestation challenge digest 与本次 pairing 不匹配 /
`hpke_key` 与 `pair_device.hpke_key` 或 payload 不一致 / 两个 binding kind 的 transcript 互换
等负向量，以及 §5.4.1 装配前校验失败时目标设备 fail closed。

### 2.2 设备吊销

> 吊销后的 MLS secret 与 backup series 轮换 MUST 在一个 `SecurityRotationTransaction` 内进行，
> 且该 transaction MUST 在提交 `ak.device.revoke` **之前**创建并 durable prepare。accepted revoke
> 只进入可由 exact `signed_reject` 恢复的 `revocation_pending`；transaction 在 pending 期间可冻结新使用、预留 id 与准备幂等远端步骤，但 MUST 保留 reject 恢复所需材料，不得执行不可逆 device-generation 擦除。只有 covering Seal accepted 后才提交永久撤销、MLS secret / backup series rotation 与终局清理。固定顺序、reserved id 与崩溃续跑合同见
> [`../identity/security-transactions.md` §3](../identity/security-transactions.md)。
> 在没有该 transaction 的情况下重试轮换会重新生成 secret 与 series id，而不是续跑首次计划。

当设备丢失时，用户可从任何其他已授权设备、DID 控制密钥或 recovery policy 允许的恢复服务发起吊销操作：发布 `ak.device.revoke`，停止接受该设备的新签名写入，并对受影响的 MLS 群组触发 `Remove` 与 Epoch 更新。若该设备曾被写入 DID Document，撤销流程还必须按 DID method 规则移除或失效对应 verification method。

`ak.device.revoke` 是 principal control stream 上的 Control Move：其 Event Envelope MUST 携带 `seal_basis={leaves[]}`（撤销方签名时观察到的 accepted Seal refs，进入 canonical Event bytes 并被撤销证明签名覆盖，见 `../authz/event-auth-state-resolution.md` §5）；payload 不携带任何 frontier 或 generation 字段。客户端铸造 basis 的注册来源是 `ak.self.seals.read.frontier.v1?realm_id=<principal_control_realm_id>` 返回的 `RealmSealFrontierView.seal_basis`；single_signer/threshold 下恰一 leaf，open_set 下必须保留完整 canonical antichain。client MUST 验证所有所引 Seal 并自行重算 joined roots，但不把 roots 复制进 Event。来源不可用或不完整时 MUST fail closed，不得伪造 basis。

**`revocation_pending` 状态机（normative）**：机读合同为 [`device-revocation-state.schema.json`](../../artifacts/schemas/device-revocation-state.schema.json)（`ak.schema.device_revocation_state.v1`）。所有 deployment profile 使用同一规则，不存在通用部署 `SHOULD`、E2EE / hardening 才 `MUST` 的分支。

| durable state | 唯一进入条件 | 对目标 generation 的作用 | 唯一退出条件 |
|---|---|---|---|
| 无 pending | 没有未终结的 accepted revoke proposal | 按独立 device authorization / verification 状态判定 | 首个 revoke canonical acceptance |
| `revocation_pending` | revoke 通过 schema、完整 Event / proof、exact authority、device、current PCR-local monotonic generation、precondition、admission 与 canonical Ack 检查；accepted Event、Ack、derived record 与 pending index 在一个原子事务首次 durable commit | 所有部署对 session grant issue/refresh、KeyPackage claim、to-device write、Event write、Principal Server admission-proof issuance 全部 fail closed；可区分的本地主体操作使用 `device_revocation_pending`，KeyPackage anti-enumeration surface 继续使用不透明 `claim_failed` | exact proposal 被同一 Ack authority 合同的有效 `signed_reject` 终结，或被 accepted Seal 覆盖 |
| 已签名拒绝终态 | `signed_reject` 的 Realm、proposal digest、proposal Ack digest、authority set、deadline chain 与签名 quorum 全部验证，并经 proposal Event 精确绑定同一 device / generation | 仅清除该 proposal 的 pending gate；设备是否恢复 active 仍由其独立 authorization / verification 状态决定 | terminal；同一 decision exact replay 为 no-op |
| `revoked` | accepted Seal 的 covered set 包含该 proposal digest | 永久撤销；后续 reject 无效 | terminal |

`ak.device.revoke` **不是** §7.2 authority-authored human self-principal PCR Move 的 Ack-less 例外。每个 accepted revoke MUST 具有 canonical `ControlProposalAck`：本地 authority 可在首次接受事务中签发，外部 authority 必须随 submission 提供满足 quorum 的 Ack。无有效 Ack 时整笔零写入且不得进入 pending。这里的“不等待 Ack”表示 Ack 不是 accepted 之后的第二个安全门槛：accepted Event、Ack 与 `revocation_pending` 必须同一原子 commit 可见；不等待后续 decision、quorum 重收集或 covering Seal。pending record 的 `accepted_at` 与 `acceptance_seq` 必须由该原子 commit 实际分配；不得复制外部预签 Ack 的 `received_at`，两者也不要求相等。

目标 `target_device_authorize_event_id` 与 `target_device_generation_ref` MUST 由 receiver 从 exact `(principal_id, principal_server_id)` 的本地 durable current device projection 派生；producer payload 不得自报。未获 revoke authority 的 caller MUST 在读取任何 device-private state 之前拒绝，且零 Event / Ack / pending 写入。获得合法 revoke authority 的主体也同时获得制造 pending 阻断的能力；这是该高权限的显式 DoS 能力，不得以超时自动解封来掩盖。

**派生的定义域与缺失结论（normative）**：上述派生是 partial function，不是要求 receiver 为任意 `device_id` 合成 selector。只有本地存在完整、已接受、当前 generation 内 active 且 verified 的 authorization projection 时，才能得到 exact authorization Event id 与 generation ref；从未授权、authorization 已不再 current、设备不存在或设备不属于该 exact account pair 时均不得构造空值、占位 Event id 或 generation。对已通过 caller 认证的 `ak.peer.device_revocations.command.check.v1`，这些不可派生情形按下文反枚举规则统一签署 `decision="authority_mismatch"`；对 origin Principal Server 的本地 `/_arkret/self/*` 写入，必须在查询 revocation record 前以 `device_unauthorized` fail closed。两者是不同 disclosure surface，不能互换。若一条声称 current / active / verified 的内部 projection row 已存在，却缺少 schema 要求的 authorization Event id 或 generation ref，则是 projection integrity failure，不是普通“未授权”结论；实现必须隔离/修复该 row 并上浮内部可用性故障，不得把残缺 row 发布到 `keys/query`，也不得为其签署 `allow`。

同一 proposal 的 byte-identical replay MUST 返回首次 accepted Event / Ack / pending fact，不增加记录或延长期限。同一 device / generation 的不同 proposal digest 各自形成独立 durable record；任一未终结 record 都保持 gate，reject 一条不得清除其他条。每个 exact device/generation 最多容纳 128 条 gate-relevant distinct proposal：exact replay 不占新 slot；达到 128 条时，新的不同 authorized revoke 必须在 Event/Ack/pending 写入前以 `limit_exceeded` 零写入拒绝；signed reject 清除其 pending slot；任一 covering Seal把对应 record 改为 revoked，此后该 generation 不再接受新 revoke。若一条已 sealed 而另一条仍 pending，account summary 的 lifecycle 是 `revoked`，但 `revocation_states[]` MUST 同时保留 sealed record 与所有 surviving pending records，按 `(acceptance_seq, proposal_digest)` 排序，不得用单一 status 隐藏并发 proposal。

`signed_reject` 与 Seal 通过同一 proposal terminal-state CAS 串行化：reject 先赢则该 proposal terminal rejected，后到 Seal 不得把已拒绝 proposal复活；Seal 先赢则永久 revoked，后到 reject 拒绝。overdue 仍是 `revocation_pending`，继续五类阻断并写 `control_proposal_decision_overdue` governance/recovery fault；迟到但按通用 CBA 仍有效、且未被先前 terminal reject 排除的 Seal可正常 accepted。restart 必须从 durable proposal/Ack/decision/Seal store 重建等价 gate；缓存、管理员布尔值、timeout、进程内 lease 或 cache eviction 都不是解封真相源。

跨 Account Authority 的 human session-grant issue / refresh 必须调用标准 authenticated S2S `ak.peer.device_revocations.command.check.v1`。请求携 issuer 自己已验证的 exact `AccountId`、`device_id`、`action_class`、immutable intent digest 与 closed `AcceptedDevicePossessionProof`。origin Principal Server 必须在与 revoke acceptance 相同的 lock / serializable transaction 中，从同一次 durable current device projection 取得 accepted device public key、验签 proof、派生 exact authorization Event 与 PCR-local integer generation，并对同一 immutable intent digest 持久化 signed linearization receipt；不得先在锁外读 key/状态、在第二次事务只做 gate。proof 的 principal/device/audience/holder JKT/session intent/time window 必须逐字匹配请求；issue 还必须绑定 account subject、handoff digest 与 request id，refresh 必须绑定 predecessor grant id。issuer MUST NOT 从客户端输入取得 authorization Event/generation，MUST NOT 在 receipt 之外重新解析设备状态；`allow` receipt 携带的 derived binding 是 grant claims 与 introspection `device_binding` 的唯一取值来源。

request 的 `expected_device_authorize_event_id` / `expected_device_generation_ref` 是 issuer 自身已持有的 durable 已验证绑定的复核输入，两者 MUST 同时出现或同时缺省，且 MUST NOT 由调用它的客户端提供。`action_class="session_grant_issue" | "returning_session_grant_issue"` 时二者 MAY 缺省；前者只服务 registration/recovery 初始签发并禁带本节 returning proof，后者只服务 AccountHandoff returning human 并强制 `AcceptedDevicePossessionProof(purpose=session_grant_issue)`。`session_grant_refresh` 强制同一 proof 的 refresh purpose 并携 expected binding。其余 action class 也 MUST 携 expected selectors。携带且与 derived 值不逐字相等时 decision 固定为 `generation_mismatch`，且 receipt MUST NOT 回携 derived binding。

origin Principal Server MUST 先认证 caller 并确认它是该 exact pair 已绑定的 Account Authority，然后才可做任何 device-private lookup。caller 无权、账号不在本服务、设备不存在或设备不属于该账号时，一律返回同形 `authority_mismatch`，调用方 MUST NOT 能区分这四者。

allow 只承认在线性化点早于后续 pending 的那组 exact bytes；issuer 必须在 receipt 的 `expires_at`（最多 30 秒）前把同一 intent + receipt 原子提交，pending 后不得铸新 intent。缓存查询、私有 RPC 或“最近看起来 active”不能替代此 fence。session-grant introspection 仍只读取 issuer ledger，不携可在多请求间复用的 revocation receipt；origin Principal Server 接受每个 `/_arkret/self/*` 请求时 MUST 在该请求本地事务中按 exact device/generation读取自身 durable pending/Seal gate，从而避免 Principal Server → Account Authority → 同一 Principal Server 的回调与 pending 后 receipt reuse。

human session grant 来源固定如下：returning `account_handoff` issuance 不携 expected binding，绑定完全由本次 proof-valid `allow` receipt 提供；SessionGrant operation 不再直接消费 OIDC code。recovery completion MUST 以其已验证 terminal ledger 中的 authorization Event 与 result generation 作为 expected binding，mismatch 一律 fail closed，MUST NOT 降级为客户端断言；refresh MUST 以已签 JWT `device_binding` 作为 expected binding。Native Agent 分支不携 device binding，其 runtime-key lifecycle 使用独立验证器。

human issuance MUST 无条件先调用本 gate，再按 decision 分三路，不存在第四种结果：

- `allow`：签发携 derived `device_binding` 的完整 grant。
- `authority_mismatch`：返回 `403 device_unauthorized`，零 grant / issuer record；客户端进入独立 pairing-first Device Setup，不得把未知或他人设备信息泄露成更细错误。
- `revocation_pending` / `revoked` / `generation_mismatch`：零 issuer writes，分别返回 typed block，且不得降级成新设备或 recovery——被撤销或已换代的设备不得靠“当成新设备”重新取得会话。

MUST NOT 因绑定取得困难跳过本 gate；current-v1 任何 human success 都必须携完整 `device_binding`，不存在 restricted 例外。

gate receipt 的 proof context 固定为 `ak.device_revocation_gate_decision_proof.v1`。`payload_digest = sha256(JCS(receipt_without_proof))`；`proof.verification_method` 必须逐字等于 receipt `verification_method`，其 controller 投影到 Core 后必须精确等于 `account_id.principal_server_id`；`proof.created_at` 必须等于 `linearized_at`。decision 分支封闭：只有 `allow` 携带 origin 派生的 `target_device_authorize_event_id` 与 `target_device_generation_ref`，其余四个 decision MUST NOT 携带二者；`allow` / authority mismatch / generation mismatch 不携 blocker 或 Seal；没有 revoked record 且存在多个 pending 时，pending 只携 lexicographically smallest `proposal_digest` 作为 blocker；存在任一 revoked record 时 decision 固定为 revoked，只携按 `(acceptance_seq, proposal_digest)` 最小 revoked record 的 covering Seal ref，不因另有 surviving pending record 改回 pending。

客户端材料处理也按 terminal state 分层：pending 期间 MUST 保留恢复或验证 `signed_reject` 所需的最小可恢复材料，不得把 pending 当永久撤销擦除；accepted covering Seal 后 MUST 擦除仅属于被撤销 device generation 的 session / KeyPackage / to-device 解密与发送材料。already lawfully issued before pending 的 Principal Server admission proof 继续按其 `accepted_at` 离线验证，后续 pending / Seal 不追溯改变历史 Event validity。

共享 E2EE Realm 不能只看到“某设备已撤销”的服务端布尔值就推进新 epoch。对应 `ak.mls.commit` Remove 的 `governance_binding.security_frontier_digest` MUST 从已经包含该 `ak.device.revoke` 或将其导入 Realm 的显式 leaf-remove Control Move 的 accepted state 重算，且该撤销 MUST 已被 principal control stream 的 accepted Seal 覆盖；否则 Commit 不满足 MLS Security Frontier Binding，唯一 group 的 current winning epoch 不得推进。


## 3. 企业单点登录 (SSO / OIDC Gateway)

企业通常强制要求使用 Okta、Google Workspace 等中心化身份提供商 (IdP) 进行认证。在不破坏去中心化端到端加密前提下，本协议引入 **Auth Gateway (认证网关)** 模式。

### 3.1 架构角色
- **Auth Gateway**：部署在企业内网或受控云端的高安全级别服务器。它通常是组织 DID 明确声明的 session grant issuer 或设备授权服务。只有在企业托管账号场景中，它才 MAY 托管员工 DID 的高权限签发材料；对普通个人 DID，网关 SHOULD 只签发短期 session grant，不应托管用户 principal signing key 或 recovery key。

### 3.2 登录时序
1. **浏览器会话初始化**：员工在浏览器打开 Web 端应用，本地生成临时会话密钥 `session_key`。
2. **OIDC 重定向**：浏览器跳转至企业 Okta 完成标准的 OAuth2 / OIDC 身份认证。
3. **网关授权 (Gateway Delegation)**：Okta 认证成功后回调 Auth Gateway。Gateway 验证员工身份无误后，在自己的 durable issuer ledger 中建立 immutable issuance record，并用 issuer key 签发短期、受众绑定、scope 受限的 `ak.session.grant`，把 `session_key_pub` 绑定到目标 DID principal、设备、origin、audience、过期时间和允许的 operation 集合。Gateway 不持有用户 principal/device/recovery 私钥，不得为该 grant 代签或提交 principal Event。其中绑定的设备 MUST 是客户端持有的稳定协议 `device_id`（`ak:device:<uuid>`，由客户端在认证时显式声明，例如 OAuth `urn:arkret:client:device:<id>` scope 透传到 introspection 的 `org.arkret.device_id` claim）。资源服务器 MUST NOT 从 token / session 标识（如 `jti` / `session_id`）派生或伪造一个 per-token 的 `device_id`——这违反 §4「服务端不得伪造 device identity」，且会让该值在每次 token 轮换时漂移，静默破坏所有按 `(principal, device)` 绑定的不变量（sync cursor 主体/设备匹配、key backup 写入设备授权）。携带认证材料但缺少稳定 device 绑定的会话 MUST 对 device-scoped 操作 fail-closed 拒绝，而非降级放行。
4. **会话生效**：浏览器操作必须同时附带 session grant、device proof 或等价绑定证明。受保护 `ak.self.*` operation SHOULD 进一步用 `session_key`（即 grant 委托的 `session_public_key`）对每个请求做 RFC 9421 HTTP Message Signature 出示（sender-constrained / PoP，见 [`../sync/api-conventions.md` §3.2](../sync/api-conventions.md)），使会话请求与该 key 绑定，截获 token 不足以重放；高安全 deployment profile 下该出示升为 MUST。资源服务器仍 MUST 重新验证 DID control state、capability、Realm policy、grant scope、audience、origin 和重放状态；不得因为 OIDC 成功就把请求视为 DID 控制证明。
5. **平滑过期**：session grant SHOULD 使用分钟到小时级 TTL，并支持即时撤销。

### 3.3 设备持有绑定与 grant 轮换（normative）

为在「会话凭据短期有效」与「设备会话可跨多日免重登」之间取得一致,session grant 采用 **grant-binding key 持有绑定 + 滚动轮换**模型:

- **持有绑定(cnf.jkt)**:签发 `ak.session.grant` 时,Auth Server MUST 要求客户端出示一个由其 **grant-binding key**(即 DPoP key,RFC 9449 DPoP 式持有证明)签名的 proof,并把该 key 的 RFC 7638 JWK 指纹写入 grant 的 `cnf.jkt`(RFC 7800 confirmation)。`cnf.jkt` 把 grant 绑定到「持有该私钥的会话/设备」,而非仅记一个 `device_id` 字符串。客户端签的是本次 holder/request proof；Auth Server 签的是自己的 credential，两者都不替代设备或 principal Event proof。
- **grant 直接出示、短期轮换**:Principal Server 不铸第二个本地会话凭据；客户端以 `ak.session.grant` + DPoP 直接访问 `/_arkret/self/*`。grant 自身为分钟到小时级 TTL，客户端在 grant 临期时用**仍有效的 grant** 与同一 grant-binding key 轮换出新 grant。
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

```json
{
  "device_id": "ak:device:019640dd-8000-7000-8000-000000000000",
  "principal_id": "ak:did_core:webvh:zExamplePrincipalScid",
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

设备记录必须由 root-committed genesis/re-anchor 或当前 generation 的 accepted device 签名，并受 device-generation fence 约束。服务端不得伪造 device identity。

## 5. Device Authorization Chain

Arkret v1 只有一个 principal device model：DID 是 identity-root key log；Principal Control Realm（PCR）是设备目录、撤销、recovery policy 与 generation fence 的业务真相。设备不是 DID actor，也不要求 DID Document 中存在设备或入册 service fragment。

### 5.1 PCR genesis 与首设备（normative）

首次创建 PCR 必须提交一个 closed ordered unit：

1. `ak.realm.create`：由 registration-time DID control key 签名；`realm_genesis.fields.purpose` 必须是 `principal_control`，并携带 `FoundingDeviceDescriptor` 与 durable registration evidence digest。
2. `ak.device.authorize`：由 descriptor 中 `device_public_key_did` 对 possession transcript 和 Event proof 各自签名；`authorization_binding_kind="registration_anchor"`；`prev_refs` 只能含第一条 create Event id。

identity root 只单向承诺两条 Event 的 payload digest，不承诺 Event id 或 envelope digest。create payload 中的 descriptor 与 authorize payload 必须在 `principal_id`、`device_id`、device/HPKE key、算法集合和 authorize payload digest 上逐字一致。Principal Server 必须验证 event-derived PCR id（`retype(create.event_id)`，见 [`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md)；它不由 principal DID 或 subject 派生）、空 frontier、**账号维度**的 create-once、当前 identity-creation lease fence/expiry 及完整 root/device proofs，然后在一个数据库原子边界内接受两条 Event；任一步失败均零写入。

首设备无需已有设备、账号权威或管理员批准。Account Authority 的 S2S signature 只证明 transport source，不能替代 identity root 或 device proof。

### 5.2 Device possession transcript（normative）

`device_signature` 的 domain **由 `authorization_binding_kind` 判别**，不是单一固定值。该字段有三个取值，各自对应一个 domain 与一个封闭签名对象：

- `registration_anchor`：PCR genesis 的第二条 authorize；domain `ak.device_authorize_possession_proof.v1`，见 §5.2.1。
- `pcr_recovery`：PCR-policy 或显式 DID-root recovery unit 的第二条 authorize；domain `ak.device_authorize_recovery_possession_proof.v1`，并绑定 recovery session/policy/generation。
- `accepted_device`：已有 accepted device 批准新设备；domain `ak.device_authorize_accepted_device_possession_proof.v1`，见 §5.2.2。

三个 domain 都登记在 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)。verifier MUST 先从 payload 的 `authorization_binding_kind` 选定 domain 与成员集合，MUST NOT 尝试其它 domain，也 MUST NOT 接受跨 binding kind 复用的 transcript。

#### 5.2.1 registration/recovery possession transcript（normative）

genesis / recovery 时候选设备自己 author 整个封闭 unit，因此签名对象覆盖完整 authorization core；recovery 分支还必须加入 policy/session/generation binding：

```json
{
  "principal_id": "ak:did_core:webvh:zExamplePrincipalScid",
  "device_id": "ak:device:...",
  "device_public_key_did": "did:key:...",
  "hpke_key": "z...",
  "algorithms": ["..."],
  "device_key_algorithm": "Ed25519",
  "authorized_by": "ak:did_core:webvh:zExamplePrincipalScid",
  "not_before": "2026-08-09T00:00:00.000Z",
  "expires_at": null,
  "scopes": null,
  "recovery_session_id": null,
  "authorization_binding_kind": "registration_anchor"
}
```

`algorithms` 必须先按 UTF-8 bytewise 排序去重；缺失的 optional 字段在 transcript 中规范化为 `null`。签名字段、Event id、envelope digest 及其它 proof material 不进入该对象。`registration_anchor` 下 `authorized_by=principal_id`；`pcr_recovery` 的 authority 来自 re-anchor Event 所绑定的 accepted recovery policy，而不是 current DID controller。

#### 5.2.2 `accepted_device` possession attestation（normative）

配对时目标设备的处境相反：stage 时暂存记录是 **account-less**，它既不知道 `principal_id`，也不知道哪台 sibling 会批准（§7 的 to-device 广播下更无法预知 winner），因此不可能先签一个包含 `principal_id` / `authorized_by` / `not_before` / `expires_at` / `scopes` 的对象；而批准设备在拿到目标 possession proof 之前又无法构造满足最终 DTO 的完整 Event。若两者都要求对方先动，配对就是死锁。因此 `accepted_device` 使用一个**只覆盖目标自有材料与本次 pairing challenge 绑定**的封闭对象：

```json
{
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

**`pairing_challenge_transcript_digest` 是本 attestation 唯一的 replay 边界**：它 MUST 逐字节等于本次 pairing 的 `device_pairing_challenge_proof.transcript_digest`（§2.1.2）。单靠这一个成员已经足够，因为该 digest 本身就承诺了整条挑战：

- 路径 A（短链）承诺 `device_pairing_request_id` / `pairing_code` / `gate_audience` / `expires_at` / `server_nonce` / `client_nonce` / `new_device_pubkey_digest`；
- 路径 B（to-device）承诺 `transaction_id` / `request_canonical_digest` / `expires_at` / `gate_audience` / `pairing_code` / `new_device_pubkey_digest`。

因此跨 request（`device_pairing_request_id` / `transaction_id` + nonce）、跨 Account Authority（`gate_audience`）、跨过期窗口（`expires_at`）与换 key（`new_device_pubkey_digest`）的重放全部被阻断，强度与 §2.1.2 的 challenge proof 完全相同；一个为别的配对铸出的 attestation 在本次配对里永远验不过。

从该对象移出的 `principal_id` / `authorized_by` / `not_before` / `expires_at` / `scopes` / `recovery_session_id` 改由**批准设备的 Event proof** 承担：`accepted_device` authorize 的 `proof.verification_method` MUST 使用该授权 Event accepted-at 的 `did` 与 method evidence，而不是 current DID resolution；verifier MUST 取其 bare `did`，经已登记 method adapter 验证并要求 `project(did) == principal_id`，同时要求 fragment 逐字等于 `signing_device_id`，且 `signing_device_id` 必须是 payload.`authorized_by`（§5.3）。实现不得把 `principal_id` core 与 device fragment 直接拼成 DID URL。该 proof 覆盖完整 canonical Event bytes；两个签名合起来覆盖的字段集合不小于 `registration_anchor` / `pcr_recovery` 单签名覆盖的集合。目标设备对 `principal_id` 的确认由 §5.4.1 的装配前强制校验承担。

**wire 形态与载体（normative）**：该 attestation 的 wire 形态是 [`device-pairing.schema.json`](../../artifacts/schemas/device-pairing.schema.json) 的 `device_pairing_target_attestation`（上述七个成员加 `device_signature`）。它与 `challenge_proof` 一样**只走带外通道**——路径 A 的二维码 fragment、路径 B 的 to-device 消息——并且 **MUST NOT 经免认证 stage / resolve 面回传给 server**：暂存面是匿名的，让它持有该 attestation 既无必要也扩大攻击面（§2.1.1 第 2 条的既有隐私边界）。

**它是 `hpke_key` 与 `algorithms` 的唯一权威来源**：`device_pairing_stage_request_body` 与 `device_pairing_bootstrap` 都不承载这两个值，也 MUST NOT 增设镜像字段——让匿名暂存面持有长期设备 HPKE 公钥与设备算法指纹会平白扩大可枚举面，而镜像一个已被签名的值只会制造第二个非权威副本和一处必须 fail closed 的比对义务。批准设备 MUST 先独立验证 attestation 签名，再从**验签通过的 attestation** 读取 `hpke_key` / `algorithms` 填入 authorize payload；MUST NOT 从服务端响应、UI 输入或任何未签名来源取这两个值。服务端因此无法替换它们。

**gate 侧不需要额外 wire 字段（normative）**：`ak.gate.account.command.pair_device.v1` 的请求体不携带该 attestation 对象。Account Authority 从 `authorize_event.event.payload` 的 `device_id` / `device_public_key_did` / `hpke_key` / `algorithms` / `device_key_algorithm` / `authorization_binding_kind`，加上它**自己按 §2.1.2 重算**得到的 challenge transcript digest，重建上述封闭对象，并用请求携带的 `new_device_pubkey` 验签 `device_signature`。所有 transcript 输入都不来自请求方可自由选择的字段，因此无需也不得接受一个客户端提供的 attestation 副本；重建不符或验签失败 MUST NOT 授权设备。

### 5.3 Event proof key resolution（normative）

所有普通设备 Event 的 `proof.verification_method` MUST 是基于该 principal 已验证、且满足操作 freshness / event-time 要求的 `did` 的 DID URL。receiver MUST 取 DID URL 的 bare `did`，用已登记 method adapter 验证并要求 `project(did) == principal_id`（稳定 `did_core_id`），再要求 fragment 逐字等于完整 `signing_device_id`（`ak:device:<uuid>`）；不得把 fragment 拼到 `principal_id`，也不得把任何 core-plus-fragment 字符串当成 verification method。设备没有独立 DID，因此不得使用 candidate `did:key` 作为该字段。对 `authorization_binding_kind="accepted_device"` 的 authorize，`signing_device_id` 必须是 payload.`authorized_by`，不能是待授权 target device；因此 payload.`authorized_by` 在该分支下必然是设备 id，不是任何 principal DID。

该 Event proof 同时是 `accepted_device` 分支下 `principal_id`、`authorized_by`、`not_before`、`expires_at`、`scopes` 的**唯一签名承载**（§5.2.2）：它覆盖完整 canonical Event bytes，而签名方正是选定这些值的批准设备。验签方 MUST 用它校验这些字段，MUST NOT 期望目标设备的 `device_signature` 覆盖它们。

- 对普通 Event，receiver 从当前 accepted PCR device directory 解析该 method；
- 对 genesis/re-anchor unit 的第二条 authorize，目录尚未包含 candidate。verifier 必须建立只在本次 unit 内可见的 candidate overlay，把规范 method 映射到 descriptor/authorize payload 的 `device_public_key_did`，先验证 descriptor/payload/digest、possession signature 和 Event proof，全部成功后才原子写入 durable directory；
- 不得查询未接受的 projection，不得回退到同 fragment 的旧 key，也不得在验签前产生可观察目录状态。

### 5.4 后续设备配对（normative）

首设备存在后，新设备必须走 §2 pairing。新设备提供自己的 device/HPKE keys 和 §5.2.2 的 possession attestation；批准方必须是 PCR 当前 generation 中 active、未撤销的 accepted device，并对完整 authorize payload 签名。结果 `authorization_binding_kind="accepted_device"`，`authorized_by` 是**批准设备自己的 `device_id`**（完整 `ak:device:<uuid>`），不是该设备所属 principal 的 DID；authorization evidence 必须能定位批准设备的 accepted authorize Event 与 generation。

服务端可以中继 challenge 和 Event，但不得生成、替换或签署新设备 key material。旧 generation、已撤销或 conflicted device 的批准一律 fail closed。企业额外审批只能作为显式启用的 PCR policy 叠加，不能成为个人账号首次建 PCR 的默认第二方。

#### 5.4.1 目标设备装配前的强制校验（normative）

§5.2.2 的 attestation 不承诺 `principal_id`，所以“目标设备被并进了哪个 principal”不能由目标设备的签名保证，只能由目标设备**事后核对已被接受的授权**保证。因此：目标设备在**完成本地身份装配之前**（即在把该 `device_id` 与 device key 当作某 principal 的成员使用、拉取或安装该 principal 的 E2EE 材料、发布 KeyPackage、写入任何 `ak.self.*` 状态之前），MUST 先取回被接受的那条 `ak.device.authorize` Event 并逐项校验：

1. Event `payload.device_signature` 与自己产出的 attestation `device_signature` **逐字节相同**；
2. `payload.device_public_key_did`、`payload.hpke_key`、`payload.algorithms` 与自己 attestation 中的对应值**逐字一致**（含 `algorithms` 的排序与去重结果）；
3. `payload.device_id` 等于自己的 `device_id`；
4. `payload.authorization_binding_kind` 为 `accepted_device`；`proof.verification_method` MUST 是该 principal 已验证 `did` 下的 DID URL，取其 bare `did` 经已登记 method adapter 验证后 MUST 满足 `project(did) == payload.principal_id`（稳定 `did_core_id`），且 fragment 逐字等于 `payload.authorized_by`；不得从 principal core 与 device fragment 拼接 verification method；
5. `payload.principal_id` 与用户预期的账号一致——该值 MUST 在装配前显式呈现给用户确认，不得默默采纳服务端给出的任何 principal。

任一项不符，目标设备 MUST fail closed：MUST NOT 使用该身份、MUST NOT 安装或请求该 principal 的任何密钥材料、MUST NOT 发布 KeyPackage，并 MUST 向用户告警（提示该配对已被篡改或指向了非预期账号）。这条校验同样阻断“批准方把 attestation 用到另一个 principal 下”的场景：攻击者可以铸出一条对自己 principal 有效的 Event，但目标设备在装配前就会因第 5 项拒绝。

**取回路径**：`ak.open.device_pairing.read.status.v1`（路径 A）在 `state="authorized"` 时返回 `authorized_event_ref`，是该校验的入口；路径 B 的目标设备从自己发起的 `transaction_id` 关联的授权结果取得同一 ref。目标设备被授权后即已是该 principal 的 accepted device，**读取自己的 PCR 控制流即可取到该 Event 的完整 canonical bytes 与 proof 完成校验**，不需要新增读取面；在完成本节校验之前，该读取是它唯一允许对该 principal 发起的操作。取不到 Event、Event 尚未被 accepted Seal 覆盖、或读取被拒时，MUST 停在 fail-closed 状态并重试/告警，MUST NOT 先装配再校验。

### 5.5 Device trust projection（normative）

设备 trust state 仅由 accepted PCR evidence 决定：registration-anchor genesis、accepted-device authorize、PCR-policy re-anchor、revoke/list update 与 accepted Seal/frontier。DID resolver 不提供设备目录或 generation basis。

远端 receiver 必须取得 `principal_genesis_receipt + authorization_chain + accepted_seal + current_device_projection + range_completeness_evidence`。`authorization_chain` 在此不是只挑成功授权 hop，而是从 genesis 到 current Seal、足以重放目标 projection 的完整相关 PCR control history，包含 authorize/revoke/reanchor/list moves；range-completeness attestation 必须证明该区间没有被 source 隐藏 reducer input。Receiver 自行重放并要求 target status=`active`、`authorized_generation_ref == current_device_generation_ref`、generation status=`active`，再与 current projection逐字段比较。外层 source 对“未撤销”的断言不构成 authority。只有 Event payload、proof 与 evidence 的 principal/device/key/generation/frontier 全部一致时才是 `verified`；缺失、gap、witness disagreement 或 stale evidence保持 `unresolved`，不得 TOFU。

### 5.6 Privacy-Preserving Push

Arkret 推送通道设计的目标是在不向 push gateway / vendor、上游 Principal Server sync surface、网络中间人或第三方 SaaS 控制面泄露身份与可链接信息的前提下，把"有事可投递"的最小信号送达终端。这是 [`discovery/push-notifications.md`](../discovery/push-notifications.md) 与 [`crypto-media/webrtc-signaling.md`](./webrtc-signaling.md) 中"pairwise pseudonym `push_target_id`"语义的协议层定义。

#### 5.6.1 `push_target_id` 派生与作用域

- 作用域：`per (account_id, device_id, push_route)`。`account_id` 是认证 session 中完整且不可拆分的 `AccountId`；同一 principal 在两个 Principal Server 上注册同一物理设备时，MUST 使用互相不可链接的 `push_target_id`。`push_route` 标识同一设备上不同 push 通道（如 `apns_main`, `fcm_voip`, `webpush_default`），允许同一设备针对不同通道发布相互不可链接的伪名。
- 长度与编码：`push_target_id` 的唯一 v1 wire 形态是 `ak:pseudonym:push:<tag>`，其中 `tag` MUST 是完整 32-octet HMAC-SHA256 输出的 canonical unpadded Base64URL 编码，固定 43 个 ASCII 字符。接收方 MUST 解码为恰好 32 octets，并要求重新编码后的字符串与原 `tag` 逐字相等；不得截断、扩展、补 `=` padding 或接受可解码但非 canonical 的替代字符串。其 JSON Schema lexical pattern 为 `^ak:pseudonym:push:[A-Za-z0-9_-]{42}[048AEIMQUYcgkosw]$`。
- 生成方与派生：`push_target_id` MUST 由接收 Principal Server 按 [`discovery/push-notifications.md` §2.2](../discovery/push-notifications.md) 的派生 profile 生成——`HMAC-SHA256(service_push_secret[salt_epoch_id], canonical_json({account_id, device_id, push_route_id, salt_epoch_id}))`——并经注册响应返回给设备（`push-notifications.md` §3.1，这是该伪名唯一的契约通路）。其中 `account_id` 使用其 closed JSON 的 JCS bytes；设备 MUST 使用服务端派生值，MUST NOT 自行铸造 wire 形态的 `push_target_id`；设备 MAY 通过 `ak.device.push_route` account-private state event（§5.6.2）携带 / 核对该值。
- 不可推导性：`push_target_id` MUST NOT 由公开 DID、`device_id`、平台 push token、handle、邮箱或电话号码可推导。`service_push_secret` 原值绝不能上 wire，仅持有公开输入的一方无法重放该派生。rotation 周期与旧 / 新伪名可逆映射的短暂保留窗口见 [`../conformance/scalability-constraints.md`](../conformance/scalability-constraints.md) §6（默认 rotation ≤ 90 天；可逆映射保留 ≤ 24h 或与单条未投递消息 TTL 取较短者）。
- 标识形态：所有操作响应、notify DTO 与 `ak.device.push_route` actor-private Event 都 MUST 使用上述完整 typed form。`common-ids.schema.json#/$defs/push_target_id` 是唯一 schema 定义；不得在领域 schema 复制 regex，也不存在 raw Base64URL、短 token 或另一种兼容形态。该形态由 `id-kind-registry.json` 的 profile-scoped `pseudonym` 外层空间授权，不新增第二个 ID kind。

#### 5.6.2 注册与撤销

- 目标 account-private cell 的 `cell_subject` 是 canonical `contract-registry.json` 登记的 composite `(payload.account_id, payload.device_id, payload.push_route)`，family 固定使用既有 `server_revision_cas`。每条 `ak.device.push_route` Event MUST 携 `expected_revision`：从未写入的 cell 以 `0` 创建；接受方在同一原子事务比较当前 revision，相等时存储 `revision = expected_revision + 1`，不相等时返回 `cas_conflict` 且零写入。`expected_revision` 是 account-private merge 载体，不是 CBA precondition；该 Event MUST NOT 携共享 reducer `preconditions` / `seal_basis`，也不进入 shared Realm Seal coverage。
- active 写入是闭合 whole-value：`(account_id, device_id, push_route, expected_revision, push_target_id, push_gateway_id, encryption_key, capabilities, expires_at?, updated_at?)`。`account_id` MUST 等于 Event `actor_id.account_id`，且 `push_target_id` MUST 等于该账号认证 session 的注册响应返回值；`push_gateway_id` MUST 是 canonical `did_core_id`，实现不得另收 `push_gateway_did`。active 形态 MUST 省略 `revoked`。
- 撤销写入是互斥的闭合 tombstone：`(account_id, device_id, push_route, expected_revision, revoked=true, updated_at?)`。它 MUST 省略 `push_target_id`、`push_gateway_id`、`encryption_key`、`capabilities` 与 `expires_at`；撤销由 cell subject + revision 定址，不得为定位旧值而重传旧 `push_target_id` 或 provider 秘密。接受后 service / gateway MUST 立即停止接受旧伪名。
- 轮换是对同一 cell 的下一条完整 active 写入，不是局部 patch：客户端 SHOULD 在 push token 变化、设备恢复、Out-of-band 重新登录、或自定义 rotation 周期（默认 ≤ 90 天）时以当前 revision 和新注册响应的完整 active tuple 提交。create(revision 0) → rotate(revision 1) → revoke(revision 2) 三次成功写入后，cell revision 固定为 3；缺失 revision、stale retry 与同 revision sibling 均 fail closed。
- 长期不可恢复性：服务方在丢弃旧 `push_target_id` 后 MUST NOT 保留可把旧 / 新伪名链接回同一 `(account_id, device)` 的索引；只允许在 rotation 时短暂保留以便迁移未投递消息。短暂保留期 MUST ≤ 24h，或与单条未投递消息 TTL 取较短者；超过该窗口 MUST 物理删除旧 `push_target_id`、provider 路由材料及可逆映射。隐私 GC 仍 MUST 永久保留按上述 cell subject 定址的 revision high-water 与最小幂等/审计摘要（subject digest、revision、outcome）；不得保留旧 target 明文，也不得因 GC 把 revision 退回 0 而让离线旧写复活。
- **条数与注册速率上限（normative）**：单一 `(account_id, device_id)` 维度下并存的 active `push_route` 条数 MUST ≤ 16（v1 wire 上限；登记于 [`../conformance/scalability-constraints.md` §6.1](../conformance/scalability-constraints.md)），超过时服务端 MUST 拒绝新 `ak.device.push_route` 注册（`push_route_limit_exceeded`）。同一维度的 push-route 注册 / 轮换 MUST 限速，默认窗口 60s 内 ≤ 8 次写入；超额时返回限速响应并记内部审计 `push_route_registration_rate_limited`。该上限防止单设备通过无界 push_route 放大注册状态或制造可链接性面。

create / rotate / revoke、stale sibling、exact replay 与隐私 GC 的可执行合同由 `ak.vector.push.device_route_revision_cas.v1` 固定。

#### 5.6.3 不可链接性要求

- 同一 `principal_id` 在不同 AccountId、不同设备或不同 push route 上的 `push_target_id` MUST NOT be linkable by push gateway / 第三方 transport（除非两侧自愿持有相同源 secret）。受托 Principal Server sync surface MAY 在自己的授权上下文内持有从 exact AccountId 到本服务本地 push queue 的短期索引，但不得把该索引导出给 Push Gateway / vendor。
- 同一设备的两条 `push_route` 的伪名 MUST 互相独立；其中一条被泄露不得让攻击者推导另一条。
- 跨 Realm 投递 MUST 使用同一 `push_target_id`（按 device 而非按 Realm），但 push payload 内不得携带 plaintext `realm_id`/`strand_id`/`message_id`；目标拆分由 device 端解 envelope 后完成。

#### 5.6.4 Push Payload 形态

- 协议层 push payload MUST 视作 `encrypted-envelope.schema.json` 形态或等价 ephemeral encrypted blob。AAD MUST NOT 包含可链接 wire 字段，仅可携带 routing-only `wakeup_kind`（参见 `discovery/push-notifications.md`）。
- gateway / vendor MUST NOT 解密 payload。任何"丰富推送"扩展（如显示发件人）都属于 vendor-side 行为，需要 Realm 与 device 双方明确 opt-in，并对应单独的 plaintext-visible service profile，不在 v1 默认互操作范围。

#### 5.6.5 与其它子系统的边界

- Principal Server sync surface：以 `push_target_id` 作为 push fanout 索引。由 joined-member ActorId 确定的目标 Principal Server MAY 在运行时持有 `account_id + device_id + push_route -> push_target_id` 映射以完成投递；该映射不得暴露给 Push Gateway / vendor，日志、导出、法定披露和跨服务复制 MUST 脱敏或失效化。不是 `account_id.principal_server_id` 的服务不得保留可逆映射。
- WebRTC 通话邀请（`webrtc-signaling.md` §9 incoming-call wakeup）通过同一 `push_target_id` 触发；payload 仍走 §5.6.4 加密通道。
- 推送规则（`push-notifications.md` §4 keyword / member_count 等）以 `push_target_id` 为目标但 MUST 在不解密 payload 的前提下完成评估，或在 E2EE Realm 中由设备本地评估，详见对应文档。

## 6. Device List Sync

任何设备新增、撤销、签名更新或算法更新，MUST 产生 `ak.device.list_update` event。该 event 是 principal control stream 中的 actor-private durable identity state；若使用 Event Envelope，顶层 `realm_id` MUST 是目标 principal 的 `principal_control_realm_id`。它不进入任一共享 Realm 控制面 Seal coverage / state_root；共享 Realm 只能通过 MLS Welcome / Remove、device trust proof 或 explicit membership / KeyPackage event 感知其结果：

Account Subscribe 的聚合提示 `delta.device_lists` 与本 event payload 不是同一 DTO：前者固定为 `{changed: principal_did[], left: principal_did[]}`，只指出哪些 principal 的权威设备列表需要刷新或清除；后者才携带该 principal 的具体 device 变化。实现 MUST NOT 把 `device_id` 写入 `delta.device_lists.changed/left`，也不得把聚合提示当作完整设备清单。

```json
{
  "kind": "ak.device.list_update",
  "payload": {
    "principal_id": "ak:did_core:webvh:zExamplePrincipalScid",
    "changed": [
      "ak:device:01964137-0000-7000-8000-000000000000"
    ],
    "left": [
      "ak:device:01964138-0000-7000-8000-000000000000"
    ],
    "stream_id": "devstream_42"
  }
}
```

客户端 sync MUST 暴露 device list delta。E2EE 客户端在向 principal 发送新加密内容前，MUST 查询或同步其最新 device list。

## 7. To-Device Messages

To-device message 是面向具体 principal/device 的非 Realm 持久消息，用于密钥交换、验证、secret sharing 和通知。

To-device wire object MUST 使用 `DeviceMessageEnvelope`，而不是持久 `EventEnvelope`。标准 `ak.key.verification.*` 名称在 to-device 通道中出现在 `kind` 字段；它们不得推进 `actor_seq`、`prev_refs`、Realm reducer frontier 或持久 timeline。

`DeviceMessageEnvelope` 基本字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `device_message_id` | `id:device_message` | required | 发送方为一个逻辑消息分配的稳定 UUIDv7 typed ID；服务端在重试、分页和重投时 MUST 原样保留。接收端按 `(sender_principal_id, sender endpoint id, device_message_id)` 去重；endpoint id 由下述三分支分别取 `sender_device_id`、`sender_agent_id` 或 `sender_id`。 |
| `kind` | `string` | required | 消息 kind，例如 `ak.key.verification.request`。标准 to-device kind 由 `device-message.schema.json` 的闭合 dispatch 定义，不得登记成 Event.kind。 |
| `sender_principal_id` | `did_core_id` | required | 发送 principal 的稳定 `did_core_id`。 |
| `sender_device_id` | `id:device` | conditional | human device sender；与完整 `sender_agent_*` 三元组、`sender_id` 严格 XOR。 |
| `sender_agent_id` / `sender_agent_verification_method` / `sender_agent_key_authorize_event_id` | `did` / `did_url` / `id:event` | conditional | Native Agent sender 的完整 signer-evidence 三元组；不得半填或与其它 sender 分支混填。 |
| `sender_id` | `did_core_id` | conditional | 受限 Principal Server sender。只允许 `device-message.schema.json#/$defs/actor_private_update_kind` 闭集，且 `sender_principal_id == recipient_principal_id`；service id MUST 等于为该 recipient 提供当前 authenticated self/to-device surface 的 Principal Server service identity。 |
| `recipient_principal_id` | `did_core_id` | required | 接收 principal 的稳定 `did_core_id`；MUST 等于投递路径中的目标 principal。 |
| `recipient_device_id` | `id:device` | required | 接收设备；MUST 等于投递路径中的目标设备。 |
| `sent_at` | `datetime` | required | 发送时间。 |
| `expires_at` | `datetime` | required | 队列过期时间；不得晚于该 kind/profile 声明的 TTL 上限。 |
| `content` | `object` | required | 类型相关内容；私密内容 SHOULD 端到端加密。 |

`device_message_id`、`recipient_principal_id` 和 `recipient_device_id` MUST 被签名、device proof 或加密 AAD 覆盖。发送接口使用 `messages.{principal_id}.{device_id}` 做批量路由时，服务端在入队前 MUST 把发送请求的 `device_message_id` 与路径目标复制进 `DeviceMessageEnvelope`，且接收端 MUST 拒绝 envelope 目标与当前登录设备不一致的消息。

发送方 MUST 在第一次构造逻辑消息时分配 `device_message_id`，应用重试、HTTP batch 重试和服务端重投都 MUST 沿用该值；重新分配 ID 表示新的逻辑消息，接收端 MUST 独立处理。服务端 MUST 以 `(sender_principal_id, sender endpoint id, device_message_id)` 维护至少覆盖队列 TTL 与短 grace period 的幂等记录：human device、Native Agent、Principal Server service 的 endpoint id 分别是 `sender_device_id`、`sender_agent_id`、`sender_id`。相同 canonical target intent 重试返回既有入队结果且不得新增队列项；同 key 但 `kind`、recipient、`expires_at` 或 `content` 不同，MUST 以 `duplicate_conflict`（reason `device_message_id_conflict`）拒绝整个发送请求且不得入队任一冲突版本。canonical target intent 包含 `device_message_id`、`kind`、`sender_principal_id`、当前且仅当前 sender 分支的全部字段、`recipient_principal_id`、`recipient_device_id`、`expires_at` 与 `content`；不含服务端物化的 `sent_at`、`unsigned` 或 HTTP `Idempotency-Key`。

`sender_id` 只表示 Principal Server 对 holder actor-private CAS cell 已接受 revision 的内部队列物化者，不把 service 冒充成 holder，也不授予任意 service 发送普通 to-device kind 的能力。该分支不走 holder device revocation gate，不排除所谓 origin device，而是 fanout 到 holder 的全部 active devices；service identity 由当前 authenticated Principal Server transport / service resolution 绑定，MUST NOT 作为可跨服务转交的 bearer delegation。`ak.self.device_messages.command.send.v1` 是规范客户端 surface，MUST 拒绝任何试图提交或诱导物化 service sender 的请求；只有 Principal Server 内部 actor-private materializer 可以产生该分支。

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
| `messages.{principal_id}` | body | `object` | required | 目标 principal DID。 |
| `messages.{principal_id}.{device_id}` | body | `object` | required | 目标设备消息；`{device_id}` MUST 是完整 `id:device` wire key。 |
| `messages.{principal_id}.{device_id}.device_message_id` | body | `id:device_message` | required | 发送方分配的稳定逻辑消息 ID；服务端 MUST 原样复制到 `DeviceMessageEnvelope.device_message_id`。 |
| `messages.{principal_id}.{device_id}.kind` | body | `string` | required | to-device 消息 kind，例如 `ak.key.verification.request`。 |
| `messages.{principal_id}.{device_id}.expires_at` | body | `datetime` | required | 队列过期时间；服务端物化 envelope 后必须复制到 `DeviceMessageEnvelope.expires_at`。 |
| `messages.{principal_id}.{device_id}.content` | body | `object` | required | 消息内容；私密内容 SHOULD 端到端加密。 |

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

请求示例（非完整 schema）。`messages.{principal_id}.{device_id}` 的 `{device_id}` 是**收件设备**地址,`content.from_device` 是**发送设备**(MUST 等于 envelope `sender_device_id`,见 §10.1),二者为不同设备，故 UUID 不同：

```json
{
  "messages": {
    "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com": {
      "ak:device:01964137-0000-7000-8000-000000000000": {
        "device_message_id": "ak:device_message:01964137-1000-7000-8000-000000000000",
        "kind": "ak.key.verification.request",
        "expires_at": "2026-04-26T00:10:00Z",
        "content": {
          "transaction_id": "ver_123",
          "from_device": "ak:device:019641aa-0000-7000-8000-000000000001",
          "timestamp": "2026-04-26T00:00:00Z",
          "expires_at": "2026-04-26T00:10:00Z",
          "methods": [
            "ak.sas.v1",
            "ak.qr.v1"
          ]
        }
      }
    }
  }
}
```

同一 principal 的新设备请求旧设备验证/授权时，MUST 使用同一 `POST /_arkret/self/device_messages` wire shape 投递 `ak.key.verification.request`。发送方必须是 gate 签发的 grant-binding session，或受限 fresh-device session grant；后者只能发送 `ak.key.verification.*` bootstrap 消息给同 principal 的已授权设备。请求 content SHOULD 携带 `purpose="same_principal_device_authorization"` 和供 UI 比对/后续 gate finalize 使用的 pairing 材料：

```json
{
  "messages": {
    "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com": {
      "ak:device:01964136-8000-7000-8000-000000000000": {
        "device_message_id": "ak:device_message:01964137-1000-7000-8000-000000000001",
        "kind": "ak.key.verification.request",
        "expires_at": "2026-04-26T00:10:00Z",
        "content": {
          "transaction_id": "ver_456",
          "from_device": "ak:device:01964137-0000-7000-8000-000000000000",
          "timestamp": "2026-04-26T00:00:00Z",
          "expires_at": "2026-04-26T00:10:00Z",
          "methods": [
            "ak.sas.v1",
            "ak.qr.v1"
          ],
          "purpose": "same_principal_device_authorization",
          "pairing_code": "7H2K9M4Q",
          "new_device_pubkey": {
            "kty": "OKP",
            "kid": "ak:device:01964137-0000-7000-8000-000000000000",
            "key": "base64url...",
            "algorithm": "Ed25519"
          },
          "challenge_proof": {
            "transcript": "ak.device-pairing.challenge.to_device.v1",
            "kid": "ak:device:01964137-0000-7000-8000-000000000000",
            "transcript_digest": "sha256:89abcdef0123456789abcdef0123456789abcdef0123456789abcdef01234567",
            "signature": "base64url...",
            "signature_algorithm": "Ed25519"
          },
          "target_attestation": {
            "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
            "device_public_key_did": "did:key:z6Mk...",
            "hpke_key": "z...",
            "algorithms": [
              "ak.hpke_x25519_aead_chacha20poly1305.v1",
              "ak.mls.v1"
            ],
            "device_key_algorithm": "Ed25519",
            "authorization_binding_kind": "accepted_device",
            "pairing_challenge_transcript_digest": "sha256:89abcdef0123456789abcdef0123456789abcdef0123456789abcdef01234567",
            "device_signature": "base64url..."
          },
          "gate_audience": "https://auth.example.com",
          "request_canonical_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
          "device_metadata": {
            "display_name": "Alice's laptop",
            "platform": "desktop"
          }
        }
      }
    }
  }
}
```

`new_device_pubkey` MUST 是 canonical `PublicKey`（[`public-key.schema.json`](../../artifacts/schemas/public-key.schema.json) 的 `kty` / `kid` / `algorithm` / `key` 四字段）；旧的 `{kid, alg, public_key}` 写法不是 v1 wire，MUST `schema_violation`。`target_attestation` 是 §5.2.2 的 `device_pairing_target_attestation`，与路径 A 共享同一 schema 和同一 domain；它是本路径下 `hpke_key` 与 `algorithms` 的唯一权威来源，**只经该 to-device 消息到达**，MUST NOT 经免认证 stage / resolve 面回传给 server。接收旧设备 MUST 把 `purpose`、`pairing_code`、`new_device_pubkey.kid`、`challenge_proof.transcript_digest`、`gate_audience` 和 `request_canonical_digest` 纳入用户确认与 SAS/QR transcript 绑定，并 MUST 按 §2.1.2 的 `ak.device-pairing.challenge.to_device.v1` transcript 独立重算并验签 `challenge_proof`，**再按 §5.2.2 独立重建并验签 `target_attestation`**（`device_id` 等于 `new_device_pubkey.kid`、`device_public_key_did` 与 `new_device_pubkey.key` 解码为同一 Ed25519 key、`pairing_challenge_transcript_digest` 逐字节等于自己刚重算的 `transcript_digest`）后才可继续；不得只因收到该请求就把新设备标记为 trusted，也不得从消息中未经验签的字段取 `hpke_key` / `algorithms`。同一 pairing 向多台 sibling 广播时，每台收到的都是同一份 attestation：它不绑定任何 `authorized_by`，因此不需要预知 winner；实际成为 `authorized_by` 的是最终提交 gate 并被受理的那台设备。`pairing_code` MUST 是 8 位 Crockford-style 大写字母数字串（字符集 `[A-HJ-NP-Z2-9]`，拒绝易混字符），由 CSPRNG 的 40 个均匀随机 bit 直接编码；它只在短 TTL、单次使用、audience-bound transcript 内有效。用户确认后，旧设备通过 `ak.gate.account.command.pair_device.v1` 完成授权落地；本规范不定义 `/_arkret/self/devices/pairing-requests*` 作为授权批准接口。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->

服务端 MUST 同时执行请求级 `(sender, Idempotency-Key)` 幂等与上述消息级 `(sender_principal_id, sender endpoint id, device_message_id)` 幂等；前者识别同一批 HTTP command，后者识别跨批次、跨连接的同一逻辑消息。规范客户端 send surface 上 endpoint 仍是当前 accepted `sender_device_id`（或已授权 Native Agent endpoint）；内部 service fanout 按 `(sender_id, device_message_id)` 的 endpoint 部分去重，不得读取不存在的 `sender_device_id`。已投递消息的队列删除只由接收设备的显式确认（`ak.self.device_messages.command.ack.v1`，见下文与 [`client-sync.md` §10.1](../sync/client-sync.md)）驱动；sync cursor 推进 MUST NOT 触发删除。To-device 消息 SHOULD 端到端加密；未加密消息只能用于能力发现和验证引导，以及 registry 明确为 Principal Server plaintext CAS 的 actor-private update 提示。

若 `content` 已端到端加密，加密 AAD MUST 至少覆盖发送方在密封前已知且不可由队列服务物化的 `device_message_id`、`kind`、`sender_principal_id`、`sender_device_id`、`recipient_principal_id`、`recipient_device_id` 和 `expires_at`。`sent_at` 由队列服务入队时物化，不得进入发送方构造的通用 AAD；具体 kind MAY 增加发送前已知的业务关联字段。队列服务不得重写已进入 AAD 的字段。`Idempotency-Key` 是 HTTP 层语义，不进入 envelope，也不参与 AAD。

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
| `ack_token` | body | `string` | required | 服务端先前签发给同一 `(principal_id, device_id)` 的确认令牌。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `pruned_count` | `int` | required | 本次实际删除的消息数；重复或旧令牌的合法 no-op 返回 0。 |

确认语义（normative，完整定义见 [`client-sync.md` §10.1](../sync/client-sync.md)）：确认是累计且单调的——服务端删除令牌覆盖位置（含）之前的全部已投递消息；重复 ack 或 ack 旧令牌返回 `{pruned_count: 0}` 且不得回退确认位置（天然幂等，无需 `Idempotency-Key`）。unknown / 过期 / cross-binding 令牌 MUST 返回 `param_invalid`（reason `invalid_ack_token`）且 MUST NOT 删除任何排队消息。客户端 MUST 在该批次密钥材料 / verification transcript / secret **持久化落盘之后**才 ack；未 ack 的消息在重连时由服务端重新投递，客户端 MUST 先按 `(sender_principal_id, sender endpoint id, device_message_id)` 查询 durable 去重记录：已成功持久化的消息不得再次执行副作用，但仍计入连续完成位点并允许累计 ack。kind-specific `transaction_id` / `request_id` 只用于业务 transcript 关联，不得替代 envelope 级去重键。

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
| `one_time_keys` | body | `object` | optional | 算法名到 one-time key 的映射。 |
| `fallback_keys` | body | `object` | optional | 算法名到 fallback key 的映射。 |
| `device_signature` | body | `signature` | required | 当前设备签名；`kid` MUST 为 PCR current accepted-device 投影中的规范设备 method。canonical 签名输入见下方 §8.1。 |

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
| `device_keys` | body | `object` | required | principal DID 到 device ID 列表的映射。 |
| `timeout_ms` | body | `int` | optional | 查询等待上限。 |

服务端在处理 `keys/query` 时 MUST 先认证 requester，并且 MUST 仅在 requester 与被查询 `principal_id` 之间存在当前有效的授权关系时返回目录记录：至少同属一个 requester 可见且 requester 仍为 `join` 的 Realm，或存在当前 call/session/contact profile 明确定义的共享上下文。否则 MUST 使用与不存在不可区分的失败形态（省略该 `(principal_id, device_id)` 记录或写入 `failures` 的非枚举性失败），不得让任意已登录用户枚举其它 principal 的设备存在性 / 吊销状态。

响应字段：`device_keys: object` required；`failures: array` optional；`device_generations: object` optional（principal → current identity-root generation fence，§8.2 第 3 条的输入）。`device_keys` 的每个 `(principal_id, device_id)` 记录为 `query_device_record`：prekey bundle 收在 `algorithms`（算法名 → key_record）子字段下；同级只携带 `trust_algorithms` 与 origin Principal Server 的 `device_projection_attestation`（见下方 §8.2）。设备公钥、状态与 authorization/generation 坐标只从验签后的 attestation 读取，不在 row 重复。schema 见 [`keys-operations.schema.json`](../../artifacts/schemas/keys-operations.schema.json) 的 `$defs/query_device_record`。

#### 8.2 设备验签公钥目录（normative）

`keys/query` 是**跨 principal** 的关系门控面。它的 device row MUST 恰以 `algorithms`、`trust_algorithms` 与 `device_projection_attestation` 为权威成员；`device_signing_key`、`hpke_key`、`device_status`、`device_authorize_event_id`、`authorized_generation_ref` 只存在于已签 attestation 中。`principal_id` 与 `device_id` **由 `device_keys` 映射的键定位**，不是 row 字段，MUST NOT 作为冗余字段重复出现。设备 row 不得回显 DID Document 的设备或 service authority。

`device_projection_attestation` 是 **origin Principal Server 对 exact device projection 的签名断言**，覆盖 `(principal_id, principal_server_id, device_id, device_signing_key, hpke_key, device_authorize_event_id, authorized_generation_ref, device_status, attested_at, expires_at)`，proof context 为 `ak.device_projection_attestation_proof.v1`（见 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)）。它是本面唯一的验证载体：PCR genesis receipt、device authorization chain 与 accepted Seal **MUST NOT** 出现在本面，它们是 origin Principal Server 的内部账号治理材料，只经 `ak.self.identity.read.resolution_audit.v1` 在 holder / recovery 授权下披露。

receiver MUST 验证：

1. attestation proof 的 controller 投影后**精确等于** `principal_server_id`，且该 key 在其当前已验证 method history 下具备 assertion 能力；`proof.created_at` 逐字等于 `attestation.attested_at`，当前时刻早于 `expires_at`；
2. 外层 `(principal_id, device_id)` map key 与 attestation 的同名字段逐字一致；consumer 仅从验签后的 attestation 取得 `device_signing_key`、`hpke_key`、`device_authorize_event_id`、`authorized_generation_ref` 与 `device_status`；
3. attestation 的 `authorized_generation_ref` 等于同一响应 `device_generations` 中该 principal 的 `current_device_generation_ref`，且 `device_generation_status = active`；
4. attestation 的 `device_status = active`。

任一条不成立时 MUST NOT 把该 row 用于 E2EE / Signal 验签或 KeyPackage claim。反枚举失败形态不变：requester 与目标 principal 之间没有当前有效授权关系时，MUST 省略该 `(principal_id, device_id)` 记录或写入非枚举性 `failures`；revoked、fenced 或 conflicted 的设备同样按此处理，MUST NOT 降级成一条缺字段的 row。

普通 Event proof method 继续按 §5.3 解析：它是基于已验证 principal `did` 的 DID URL；receiver 取 bare `did` 经 adapter 验证并要求其投影等于 actor/principal `did_core_id`，再要求 fragment 逐字等于 `device_id`，不得从 actor core 拼接 fragment。

#### 8.3 客户端独立验证（normative）

客户端不能把服务端裸 `device_signing_key` 断言当作 Tier-2 信任。Tier-2 信任只有两个来源：

1. §8.2 的 origin Principal Server `device_projection_attestation`——它把「这就是该账号当前接受的设备投影」变成一条可独立验签的断言；
2. 用户侧 `ak.key.verification.*` 带外验证。

客户端 **MUST NOT** 被要求从 identity-root anchored PCR genesis 重放 device authorization chain：跨 principal 面按定义拿不到那份材料，要求重放会把账号内部治理日志变成对任意有关系第三方的外露面。验证只需要在 attestation 或 generation 更新时完成；普通消息热路径可使用按 `(principal_id, principal_server_id, device_id, authorized_generation_ref, attested_at)` 缓存的 verified projection，不需要在线解析 DID。缓存 MUST NOT 越过 `expires_at`。

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
| `agent_verification_method` + `agent_key_authorize_event_id` | DID URL + Event id | Native Agent branch | exact current Agent runtime authorization。 |
| `pairwise_verification_method` + `intended_realm_id` | exact `did:key` method + Realm id | pairwise branch | `principal_id` 必须是 method controller 的 `ak:did_core:key:*` 投影，不建立 account / Device / Agent。 |
| `keypackages` | `object[]` | required | MLS KeyPackage 与 metadata；每项 MUST 带 unique `keypackage_id=ak:mls:kp:<uuidv7>` 和 `keypackage_ref`。前者是 registry 已注册的 Arkret MLS profile typed identity，后者绑定完整 KeyPackage bytes；不得把 `keypackage_id` 降格为 non-typed opaque string。 |
| `endpoint_signature` | `signature` | required | 三分支共享的 authoritative batch signature；按所选 endpoint current authority 验证。 |

### 9.0 KeyPackage 写路径签名 transcript（normative）

`upload`、`consume` 与 `revoke` 的 detached signature MUST 使用本节唯一的 byte-exact canonical input。普通 device 与独立 Native Agent runtime 使用完全相同的 canonical bytes；身份分支只决定验签所用的 current accepted key 与落库 trust binding，不得改变 domain、字段集合或缺省规则。Rust 实现 MUST 复用 `arkret-rust-sdk` 的共享 typed canonical helper；其它语言实现 MUST 使用与本节闭合 typed request projection 等价的 canonical helper，并通过本节登记的 byte-exact conformance vector。任何实现都不得从开放 JSON value、本地 principal 类型或 HTTP handler 参数临时拼装 transcript。

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

签名算法 v1 为 Ed25519；`signature.signature_algorithm` MUST 是登记的 `Ed25519`，`signature.kid` MUST 指向同一 accepted signing key。普通 device 从 current accepted PCR device authorization projection 解析该 key；Native Agent 从 current accepted `ak.agent.key.authorize.verification_method` 解析该 key；minimal-metadata 从 exact `did:key` 解析。该 key 在三分支都 MUST 同时等于 MLS LeafNode signature key。batch签名必须在解析或改变 KeyPackage状态前验证；随后逐 entry执行 RFC 9420 self-signature、credential、Leaf key、metadata/capabilities/lifetime校验。

upload、consume、revoke 的 byte-exact正向与负向向量由 `ak.vector.crypto.keypackage_write_transcripts.v1` 固化。SDK helper输出与该 fixture不一致时实现 MUST fail closed；不得以当前 server或client实现为兼容依据。

### 9.0.1 统一 claim requester authorization 与重放闭包（normative）

`ak.self.keys.keypackages.command.claim.v1` 与 `ak.peer.keys.keypackages.command.claim.v1` MUST 消费同一个
`keypackages_claim_request_body`。requester 必须携带 §9.2.1 定义的 closed
`device | native_agent | minimal_metadata_pairwise` `requester_authorization`，并签名 exact unsigned request 与
`service_binding`；不得携带 holder-only proof、额外 proof 容器或平行 transcript。

`service_binding` 必须显式绑定稳定的 source/destination Principal Server DID。trust domain 属于部署态 transport
坐标，不进入 participant transcript；source Principal Server 必须从已验证的 ServiceResolution + ServiceDescribe
取得双方 trust domain，并由外层 RFC 9421 signature/header 绑定。self Principal Server
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
| `target_principal_id` | `did_core_id` | required | 被邀请或加入的 principal 的稳定 `did_core_id`。 |
| `target_device_ids` | `array<id:device>` | conditional | Human-device target branch，至少一项；与 Native Agent/pairwise selector 互斥，不存在空 selector 或服务自行猜测 endpoint 的分支。携 `target_keypackage_ref` 时恰一项。 |
| `target_agent_id + target_agent_verification_method + target_agent_key_authorize_event_id` | typed tuple | conditional | Native Agent target branch；三项同时出现，Agent 等于 `target_principal_id` 且 Event/method 为 current accepted authorization。 |
| `target_pairwise_verification_method` | `did_url` | conditional | Minimal-metadata target branch；与 `target_principal_id` 的 Realm-local `ak:did_core:key` actor 精确投影一致，并排除 device/Agent selectors。 |
| `intended_realm_id` | `id` | required | 目标 Realm。 |
| `requester` | `did` | required | 发起 claim 的 actor 或 service DID。 |
| `required_capabilities` | `string[]` | required | 需要的 content / MLS / policy profile。 |
| `mls_group_id` / `claim_purpose` | typed | required | exact MLS group 与 closed purpose。 |
| `expires_at` | `datetime` | required | claim 有效期。 |
| `requester_authorization` | closed XOR | required | §9.2.1 的 device、native_agent 或 Realm-local pairwise participant signature。 |
| `service_binding` | object | required | exact source/destination service DID；participant 不签部署态 trust domain。 |

`claim` 响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `claims` | `object[]` | required | 每个 claimed KeyPackage 的 `claim_id`、`keypackage_ref`、完整 `keypackage` bytes、closed endpoint binding、expiry 与 capabilities。upload endpoint signature 只在发布准入时验证；claim record 不复制无法从该 record 重建前像的签名。 |
| `claim_request_id` | `base64url` | required | 与 request/receipt 一致。 |
| `claim_receipt` | `peer_keypackage_claim_receipt` | required | destination authority 签名；local source/destination 相等。 |

`consume` request MUST validate `schemas/keypackage-operations.schema.json#/$defs/keypackages_consume_request_body`，并由 Welcome 接收方或授权发送方在 Welcome 成功处理且新的 MLS group state 已 durable 持久化后调用。command required 且仅有单数 `claim_id`、`recipient_durable_receipt` 与 `signature`；owner principal、KeyPackage、Welcome、Realm、MLS group、epoch、recipient service 与 closed device/Native-Agent/minimal-metadata-pairwise signer branch 全部从签名覆盖的 nested durable receipt 读取，Strand 从 accepted Welcome/Realm governance 派生，不得在 command 另设 selector 或坐标镜像。`user_session` 只承担 endpoint 访问控制与限流：human device 与 Native Agent branch 的 session actor 必须匹配 nested recipient principal；minimal-metadata pairwise branch 的 session actor 无需等于 pairwise actor，其 authority 必须完全由 nested endpoint、command signature 与 current Realm joined-member ActorId routing authority 建立，且不得解释为 account/device。consume admission MUST 逐字绑定 consume signer、durable receipt、Welcome recipient、exact claim record、KeyPackage signer 与 endpoint authority。`keypackage_consume_receipt` 顶层只携 service 新生成的 `request_digest + claim_id + consumed_at`、完整 `recipient_durable_receipt` 与 service signature；普通包只有在single-use claim转入consumed后签发，last-resort包则只终结该exact claim audit并保持KeyPackage published。`keypackages_consume_outcome` 只返回完整 signed `consume_receipt`。若持久化失败，runtime MUST NOT 调用 consume；若 consume 响应丢失，必须以同一 signed typed request 幂等重试。服务端 MUST 从 durable terminal ledger 返回首次签发的同一 receipt，不得重新签名；完整 request digest 不同即冲突。对于 Direct Conversation，服务端还必须从 accepted Welcome 与 immutable binding 重新派生 Realm、Strand、MLS group 与 epoch；任何不一致均 fail closed。`revoke` request MUST validate `#/$defs/keypackages_revoke_request_body`，可由设备、principal controller 或 policy 授权服务发起。

规则：

- 对普通 single-use KeyPackage，`claim` MUST 原子地把 KeyPackage 从 `published` 转为 `claimed`。协商启用的 `last_resort=true` 包是唯一例外：包本身保持 `published`，每次领取只追加独立 `keypackage_claim_record`（见 [`encryption-and-audit.md` §2.6.2](./encryption-and-audit.md)）。
- 同一 `keypackage_ref` 不得被多个 active claim 使用。
- 过期、撤销、设备被移除或 principal control state 失效时，服务 MUST NOT 返回该 KeyPackage。
- **registered `required_capabilities` ⊆ signed LeafNode `capabilities`（normative subset rule）**：claim request 中每个 `required_capabilities` 值 MUST 是 [`keypackage-capability-registry.json`](../../artifacts/registry/keypackage-capability-registry.json) 的 active 行，且集合 MUST 是被领取 KeyPackage 的 signed LeafNode `keypackage_capabilities` (`0xF1C1`) 的子集；外层 upload / claim record `capabilities` 必须与该 LeafNode 列表逐项、逐序相等。形状合法但未登记的发布值保留为 unsupported，永远不得满足 required 集合。任何未登记 required 值、`required_capabilities ∖ signed_leaf_capabilities ≠ ∅` 或 outer / LeafNode 不一致的 claim MUST 被服务端拒绝（与其它 claim 失败一致使用统一不透明错误码 `claim_failed`，服务端内部审计统一归入既有 `keypackage_capability_overreach` 类别并记录具体 predicate）。该 claim 检查只是领取前置；committer 还 MUST 按 [`encryption-and-audit.md` §2.6](./encryption-and-audit.md) 把群实际要求写入 `required_keypackage_capabilities` GroupContext extension，并在 Add / Update / Join 时复核。
- Device / Key Server 在 claim 成功响应中返回完整 `keypackage` bytes、`capabilities` 与 claimed endpoint 的 trust binding，不返回同体 digest 回声。普通 device 携带该设备 accepted `ak.device.authorize` 的 `device_authorize_event_id`；Native Agent 携带当前 accepted `ak.agent.key.authorize` 的 `agent_key_authorize_event_id`；minimal-metadata 携 `principal_id + pairwise_verification_method` 且无 authorization ref。三者 MUST 精确 XOR。Consumer MUST 从 claim record 的完整 bytes 重算 `keypackage_digest`、从 capabilities 重算 `capabilities_digest`，再要求 `payload.claim_ref.keypackage_digest` / `payload.claim_ref.capabilities_digest` 与重算值及已发布 `ak.mls.keypackage.payload.keypackage_digest` 一致；Welcome 顶层不复制 KeyPackage digest。`payload.claim_ref` 还必须携带同一 closed endpoint binding，接收端在解密前确认 device/Agent authority 仍 current，或 pairwise method 仍与 actor、Realm affinity 及 leaf 精确一致，防止 group manager 或中间服务替换 KeyPackage、扩大能力集合或复用旧 authority。
- `payload.claim_envelope` 是 requester 对本次 Welcome 的独立签名 transcript，签名身份绑定 requester 而不是被 claim 的 endpoint。普通 principal requester MUST 携带 `requester_device_id` 与 `device_authorize_event_id`，并用该设备当前 accepted `ak.device.authorize.payload.device_public_key_did` 签名；Native Agent requester MUST 携带 `requester_agent_id + requester_agent_verification_method + requester_agent_key_authorize_event_id`，并用所声明的 active Agent key 签名，禁止携带或借用 `requester_device_id`；minimal-metadata requester 仅用通用 `requester_actor_id + requester_pairwise_verification_method`，method 必须是该 actor 的 exact `did:key`。三者 MUST 精确 XOR。服务端和接收端 MUST 校验 envelope 的 requester identity、closed endpoint、authority binding、signature `kid` 与当前投影/Realm affinity 一致；不得把 recipient KeyPackage 的 authority 当作 requester 签名身份使用。
- 每个成功 Welcome 必须携带唯一的 `claim_receipt`，其类型固定为 destination-signed `peer_keypackage_claim_receipt`；same-service claim 也使用同一类型，且 `source_id=destination_id=current authority`。`claim_request_id`、`request_digest`、`claims_digest`、exact unsigned request 与 source/destination service 均进入签名 transcript。Native Agent `current_observation` 必须从 receipt 唯一派生并逐字相等：`request_digest=receipt.request_digest`、`verifier_id=destination_id`、`audience=source_id`、`challenge=claim_request_id`。接收端不得用 evidence 内自报 observation 替代 receipt 导出的 expected context。
- `claim` 失败响应 MUST 对不存在、不可见、无可用设备、policy denied、subset-rule 违反（§上条 `keypackage_capability_overreach`）、过期、`revocation_pending` 与已撤销状态做反枚举处理。所有 deployment profile 的对外错误码 MUST 合并为单一不透明 `claim_failed`；HTTP status、body shape/size class、target-sensitive headers 与量化后的 delay distribution 也必须按 `ak.outward_disclosure.target_private_claim.v1` 同形。不得返回逐 target `failures[]`、`available_count` 或可区分 error message。精确 reason 只进入受限 audit，普通日志与 metrics label 只记录 outward bucket。
- 设备 SHOULD 维持 `keypackage_min_available` 低水位，默认 8。v1 不存在 owner inventory 或 maintenance query，upload、self/peer claim 与 peer outcome-query 均不得返回 `available_count`。客户端维护 endpoint-scoped 本地 inventory ledger，只在本地 usable 数量低于 8 时于一个 single-flight maintenance cycle 上传一个至多包含 `8 - local_usable_count` 个 fresh 包的 deficit batch；健康 inventory 重载必须零上传。并发 runtime MAY 短暂 overfill，但每个 cycle 不得超过其启动时 deficit。
- claimed 但未 consume 的 KeyPackage 到达 claim `expires_at` 后 MUST 转为 revoked / unusable 状态；服务不得把它自动放回 `published`，也不得接受迟到的 consume。设备需要重新发布新的 KeyPackage。
- Device / Key Server MUST 维护过期扫描或等价触发：KeyPackage `expires_at`、claim `expires_at`、device revoke、principal control state 失效、capability revoke 或 Realm policy 变更任一发生时，后续 `query` / `claim` MUST NOT 返回该 KeyPackage；后台清理不得是唯一防线。扫描周期 SHOULD ≤ 60s，且每次 `claim` 路径必须先做同步 freshness 判定。
- KeyPackage claim MUST 对 `(requester_id, target_principal_id)` 做限速，默认窗口为 60s 内最多 5 次 claim 尝试。超过限额时对外仍使用反枚举响应（`claim_failed` 或通用 rate-limited envelope，不泄露目标存在性）；服务端内部审计 reason 记录为 `keypackage_claim_rate_limited`。
- claim record SHOULD 被 Principal Server / Device Key Server 保留到 Welcome 过期后的一段短 TTL，用于重试、诊断和滥用审计；不得长期保留可关联 private Realm / MLS group 的明文目标信息。

### 9.1 KeyPackage 状态机（normative）

上述分散规则共同定义下列受控状态机，单段 KeyPackage（由 `keypackage_ref` 标识）的合法状态与转换为：

| 状态 | 语义 | 合法后继 | 终态? |
| --- | --- | --- | --- |
| `published` | 已 upload，可被 claim | `claimed`（原子 claim）、`revoked`（device revoke / principal 失效 / KeyPackage `expires_at` 到期）、`retired`（account deactivation，[`account-lifecycle.md` §7.1](../identity/account-lifecycle.md)） | 否 |
| `claimed` | 已被某次 claim 原子占用 | `consumed`（Welcome 成功处理后 consume）、`revoked`（claim `expires_at` 到期 / device revoke / capability revoke） | 否 |
| `consumed` | 已被 Welcome 消费 | —（终态） | **是** |
| `revoked` | 因过期 / 吊销 / policy 失效不可用 | —（终态） | **是** |
| `retired` | account deactivation 标记的 unused KeyPackage | —（终态） | **是** |

转换约束：

- **`published → claimed` 原子**：普通 single-use 包的 `claim` MUST 原子转换；同一 `keypackage_ref` 不得被多个 active claim 占用。`last_resort=true` 包不执行该状态边，始终保持 `published`，其多个 active claim 由互相独立的 append-only claim record 表达。
- **`claimed` 不回 `published`**：claimed 但未 consume 的 KeyPackage 到达 claim `expires_at` 后 MUST 转 `revoked`，服务 MUST NOT 自动放回 `published`，也 MUST NOT 接受迟到的 consume。
- **终态集合**：`{ consumed, revoked, retired }` 均为 terminal，任何转出 MUST 被拒绝。`published` / `claimed` 的过期或吊销一律收敛到 `revoked`（claim 路径同步 freshness 判定，扫描周期 SHOULD ≤ 60s，见上）。
- **`retired`**：仅 account deactivation fanout（[`../identity/account-lifecycle.md` §7.1](../identity/account-lifecycle.md)）把 unused（`published`）KeyPackage 标 `retired`；已 `claimed` / `consumed` 的不改写。新邀请 MUST NOT 从 `retired` / `revoked` / `consumed` 的 KeyPackage 选取。

### 9.2 跨 Principal Server 原子 claim（normative）

当 requester 与 target 由不同 Principal Server 托管时，来源服务不得调用目标服务的 `/_arkret/self/*`，也不得把 KeyPackage 领取伪装成 durable Event。v1 唯一 wire surface 为：

| operation | HTTP | request / response schema |
| --- | --- | --- |
| `ak.self.keys.keypackages.command.claim.v1` | `POST /_arkret/self/keys/keypackages/claim` | `keypackages_claim_request_body` / `keypackages_claim_outcome` |
| `ak.peer.keys.keypackages.command.claim.v1` | `POST /_arkret/peer/keys/keypackages/claim` | `keypackages_claim_request_body` / `keypackages_claim_outcome` |
| `ak.peer.keys.keypackages.read.claim.v1` | `POST /_arkret/peer/keys/keypackages/claims/query` | `peer_keypackages_claim_query_request_body` / `peer_keypackages_claim_query_outcome` |

目标 KeyPackage authority 是 `published → claimed` 的**唯一 CAS 权威**。来源服务只能请求领取并验证目标服务签发的 receipt；不得在本地镜像池上先行标记、推测成功，或用 `ak.peer.events.command.submit.v1` 替代该原子操作。claim 成功只是生成 MLS Welcome 的必要前置条件，不创建 Realm、membership、Strand 或 binding；这些 durable facts 仍必须由其规范 Event 与原签名 proof 创建并经 peer Event / principal-fact 通道投递。

#### 9.2.1 双重授权与签名 transcript

peer claim MUST 同时满足两层授权，任一层缺失或失效都 MUST fail closed：

1. **participant authorization**：requester 对 `requester_authorization` 作 detached signature。签名输入精确为 UTF-8 domain separator `` `ak.peer-keypackage-claim-authorization-v1\n` `` 后接下列对象的 JCS bytes：

   ```json
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

   上例是 `kind=device` 分支。`service_binding` 是闭合的 `{source_id, destination_id}`；客户端从业务已钉的 target ActorId routing projection 取得 destination DID，不得从 endpoint URL 或 DID 字符串猜测。部署态 trust domain 只由 source Principal Server 验证 ServiceResolution + ServiceDescribe 后写入外层已签 HTTP headers，peer receiver 逐字复核。`signature.kid` MUST 等于 `verification_method`。`requester_authorization` 是 closed XOR：human principal 必须且只能携带 `kind=device + requester_device_id + device_authorize_event_id`，并由该 accepted、未撤销设备的 `device_public_key_did` 签名；Native Agent 必须且只能携带 `kind=native_agent + requester_agent_id + agent_key_authorize_event_id`，并由 accepted current Agent runtime method 签名。Agent id、verification method 与 authorization Event 必须逐字绑定 current AgentSignerEvidence、claim requester、repair author actor 与随后生成的 MLS Event/KeyPackage signer，且不得借用 `ak:device` 身份。目标服务 MUST 独立解析对应 authority chain，不得信任来源服务对 participant key 的裸断言。

   客户端/Agent runtime 签名后，来源 Principal Server MUST 在本地验证 account pair、当前 device/runtime authorization、generation 与 revoke/pending 状态，再签发 peer command。body 不携带 PCR/device/Agent signer history sidecar；目标服务验证 authenticated source service、request transcript 与来源服务签名。该 service attestation 提供可验证归责，不声称在密码学上阻止恶意 Principal Server 作恶。
2. **service authorization**：外层请求 MUST 使用 RFC 9421 HTTP Message Signature，绑定 `@method`、`@target-uri`、`@authority`、`Content-Digest`、`Source-Service-ID`、`Destination-Service-ID`、`Source-Trust-Domain`、`Destination-Trust-Domain` 与 `Idempotency-Key`。`Idempotency-Key` MUST 逐字等于 body `claim_request_id`。

成功响应的反方向也必须闭合。每条 `keypackage_claim_record` MUST 携带与分支一致的 principal/device 或 Agent endpoint、authorization Event id、KeyPackage digest 与 signature；目标 Principal Server 的签名 `claim_receipt` 对 exact claim bytes 可验证归责。requester MUST 核对 authorization Event 的内嵌 Principal Server admission proof、claim receipt、KeyPackage 签名与所有 selector，任一不匹配都不得安装 KeyPackage 或 author Welcome。wire 不得携 PCR/control-history/device/Agent signer-evidence sidecar，外部 verifier 不重放 PCR genesis、Seal 或 range-completeness。

`claim_request_id` MUST 由 CSPRNG 生成并含至少 128 bits 不可预测熵。它是同一 claim transaction 的唯一随机值：HTTP `Idempotency-Key`、durable ledger key 以及 Welcome `claim_envelope` canonical 签名 transcript 中的 `claim_request_id` MUST 是同一值。该 transcript 值 MUST 从同一 Welcome 的 destination-signed `claim_receipt.claim_request_id` 取得，且不得在 `claim_envelope` wire 中重复。byte-identical replay 必须复用同一值；新尝试必须生成新值；同一 `(source_id, claim_request_id)` 下任何其它 request bytes 均为 `duplicate_conflict`。`requester_authorization.signed_at` 不得在接收方当前时间未来 60 秒以上；`expires_at` MUST 晚于 `signed_at` 且 `expires_at - signed_at <= 300s`。外层 HTTP signature 的 `created` / `expires` 窗口同样 MUST 不超过 300 秒。participant signature 绑定 source / destination service DID；外层 service signature 另绑定双方 trust domain，合并阻断转发到另一目标或另一部署的重放。

#### 9.2.2 目标 authority 的独立准入

在触碰 KeyPackage 状态前，目标服务 MUST 独立验证：

- `Source-Service-ID` 是 requester 当前已验证 Principal Server locator / home authority，`Destination-Service-ID` 是 `target_principal_id` 当前 KeyPackage authority，且两端与请求中的 trust domain 均属于允许此次 Realm 建立的同一 trust domain；
- participant authorization 的 requester、verification method、generation / device authorization、freshness 与 exact request/service binding 全部有效；
- target 当前 active device、KeyPackage expiry / revocation / capability 均有效，并满足 `required_capabilities ⊆ capabilities`；
- `claim_purpose=direct_conversation` 时，request MUST 携带 `pair_key` 与 main
  `strand_id`；目标服务按 [`../identity/contact-and-direct-conversation.md` §7](../identity/contact-and-direct-conversation.md)
  重算 pair key，并验证双方 current directional Contact heads 都包含 `direct_message`、预留 Realm / Strand /
  MLS group 的一致性；该路径不得查询 Consent；
- accepted member rejoin 后的普通同组 Add/Welcome 可以在 `claim_purpose=direct_conversation` 请求中携带 `target_keypackage_ref`，此时还必须携带 closed target XOR：human
  branch 必须且只能携带恰一个 `target_device_ids`；Native Agent branch 必须且只能携带
  `target_agent_id + target_agent_verification_method + target_agent_key_authorize_event_id`，禁止
  `target_device_ids`，且 `target_agent_id == target_principal_id`。owner authority 必须验证该 exact ref 属于
  对应 target 与 signer，selector、claim record、current portable signer evidence 及 KeyPackage signature
  逐字一致，状态为 current
  `published`、未消费、未撤销且 `last_resort=false`；不得忽略 exact ref 后按 device、capability 或库存顺序
  另选。成功 outcome 必须恰有一条 claim 且其 `keypackage_ref` 逐字等于 `target_keypackage_ref`；任一不匹配
  以不透明 `claim_failed` 零写入；
- `(Source-Service-ID, target_principal_id)` 的限速与 abuse policy 通过。

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

同一 source、同一 `claim_request_id`、同一 digest 的 duplicate transport delivery / replay MUST 返回 byte-identical 成功 outcome，且不得第二次领取；这项 receiver 安全性不把 operation 变成可跳过恢复查询的 caller retry-safe。同一 key 携带不同 digest MUST 返回 `duplicate_conflict` 且不得改变任何 KeyPackage。响应丢失、超时或来源服务在 durable dispatch marker 与实际 network send 之间 crash 后，来源服务 MUST 先调用 `ak.peer.keys.keypackages.read.claim.v1`，携带原 `claim_request_id + request_digest`，不得先重发 command，也不得换 `claim_request_id` 盲目重新 claim。query 只接受原 Source-Service-ID 与 exact digest，返回 `unknown|pending|claimed|claim_failed|expired|revoked`；`unknown` 明确证明目标尚无该 request identity 的 reservation，调用方此时 MAY 重放 exact same canonical command（同 source、claim_request_id、digest 与 evidence），不得生成新请求；`pending` 表示 reservation 已存在但最终化事务尚未提交，调用方只可按 `retry_after_ms` 再查；`claimed|expired|revoked` MUST 携带原签名 `claim_outcome`，`claim_failed` 只携带不透明 `error_code=claim_failed`。

成功 outcome 的 `claim_receipt.signature` 由目标服务对 `` `ak.peer-keypackage-claim-receipt-v1\n` `` + JCS(receipt 除 `signature` 外全部字段) 签名；receipt MUST 携带并签名覆盖 `source_id`、`destination_id` 与原 participant-authorized `request`（即不含 authorization / transport-only evidence 的 unsigned request 字段），`request_digest` 绑定完整 peer command，`claims_digest` 绑定 `claims[]` canonical bytes。`claim_request_id`、receipt.request 内同名字段与 outcome 同名字段必须一致。ledger 的可查询 outcome MUST 至少保留到 claim `expires_at + 10 minutes`；其后实现 MAY 只保留符合隐私 / 审计策略的 hash replay tombstone，不得长期保留可关联 private Realm 的不必要明文。

通过统一 claim 生成的 `ak.mls.welcome` MUST 原样携带 `payload.claim_receipt`。目标 Principal Server 在接受该 Welcome 前 MUST：验证 receipt 目标服务签名；精确匹配 `source_id`（same-service 时与 destination 相等，remote 时与外层认证的 `Source-Service-ID` 相等）；查询 `(source_id, claim_request_id)` durable ledger 并逐字匹配 `request_digest` 与 stored outcome；验证 request 的 requester / target principal / intended Realm / MLS group 与 Event actor、recipient、Realm、Welcome group / `claim_envelope` 一致；验签 transcript 的 `claim_request_id` 必须从同一 Welcome 的 exact `claim_receipt.claim_request_id` 取得并逐字等于 receipt request 中的值，不得信任 envelope 自报或默认；验证 stored claim 与 Welcome 的 claim id、KeyPackage ref / digest、recipient device 一致。缺 receipt、ledger 未就绪或任一绑定不一致时均须 fail closed；ledger 尚未可见属于 retryable dependency，不得把未经认领的 Welcome 降级接受。Direct Conversation immutable binding accepted 前还 MUST 将 receipt.request 的 `pair_key` 与 `strand_id` 精确匹配该 pair 唯一 durable operation 已锁定的 binding payload。

所有目标不存在、任一方 Contact head/scope 不满足、设备不可见、KeyPackage 耗尽、capability 不满足、policy denied、participant authorization 失效和限速失败，对**已通过外层服务认证**的 peer caller 必须收敛为同一 `claim_failed` 外观；不得返回 `available_count`、目标设备列表或逐设备 `failures[]`。外层 RFC 9421 signature / source service identity 无法通过时，接收方在读取 target 状态前返回通用 `unauthenticated` / `signature_invalid`；该响应必须只由 transport authentication 决定，对任意 `target_principal_id` 完全相同。

#### 9.2.4 Welcome、consume 与唯一 materializing operation

目标设备只有在以下条件全部成立后才可激活 Welcome 并通过其 own Principal Server 的 `ak.self.keys.keypackages.command.consume.v1` 消费 claim：Welcome / claim-ref 校验通过、对应 Realm/member/main-Strand/MLS Event 均可验证，且 Welcome 精确属于同一 `(trust_domain,pair_key)` 唯一 `materializing` operation 锁定的 Realm、main Strand、initial MLS group 与 immutable binding。peer surface 不提供 consume 代理；来源服务不得代表目标设备把 claim 标为 consumed。

同一 `(trust_domain,pair_key)` 的并发 resolver MUST 在任何 KeyPackage claim 前命中同一个 durable operation；coordinator 已把 operation 置为 `materializing` 后，所有重试只能恢复该 operation 的同一坐标和 claim identity。实现不得领取并行替代 KeyPackage、生成第二候选 Realm/Welcome、比较 binding digest 选择 winner，或把一次 claim 释放回 `published` 以尝试另一候选。重复 claim command 使用既有 idempotency/ledger 规则返回或查询原 outcome；不匹配唯一 operation 的 Welcome 必须在激活 MLS state 和 consume 前 fail closed。

### 9.3 普通 MLS join admission 与补偿（normative）

public/invite/closed/knock/admin-add 的最终 join都必须携未过期、single-use、签名的
`MlsJoinAdmissionReceipt`。receipt完整绑定 target Realm/member/**exact target device**、KeyPackage ref/claim、
group ID、current winning MLS group state、expected epoch、current security frontier、join authority basis、exact member Event
draft ID/digest、eligible committer、ciphersuite、issuer、issued/expires-at与reservation ID。target-device签名的
reservation在任何 claim CAS之前持久化；claim-before rejection零烧。

唯一顺序是：target-device signed reservation → KeyPackage claim CAS → durable committer journal genesis +
exact commitment → member Event accepted → append accepted frontier → Add Commit + Welcome → recipient durable
group state + consume intent → consume original claim。

journal genesis与committer commitment必须在member acceptance之前存在，并逐字绑定member draft、claim、
group/generation/base epoch、eligible committer identity与recovery identity。acceptance后只可append accepted
frontier/Commit facts。takeover必须签 predecessor、current epoch与相同 exact commitment，并以journal CAS接管；
不得更换draft、target device、KeyPackage或generation。claim后任何terminal failure都必须把原claim推进
`revoked`，不得第二次claim；只有recipient durable后才能consume。

注册唯一 authority source `ak.authority.membership_compensation.v1`。补偿 delegation由实际 accepted join
Event的authoring proof signer产生；其无签名、无自身digest、无`delegation_id`的closed core逐字绑定
admission/join identity、member Event ID/digest、membership cell与J1 provenance、subject、真实
`actor_id/executed_by?/authorization_ref?/verification_method`分支、executor service DID+proof key、resource、
deadline及唯一action。先从exact RFC8785/JCS core计算stable `delegation_digest`，再机械派生外层
`delegation_id=ak:membership_compensation_delegation:sha256:<lowercase_hex>`；ID后缀必须逐字等于该digest，
外层author signature覆盖ID、core与digest。不可转授，也不得用普通grant/source代替。

action是closed XOR：self join仅 `ak.member.compensate.leave`，delegated/admin join仅
`ak.member.compensate.remove`；未知action fail closed。executor author fresh标准 `ak.member.state`减权 Event，
固定原join actor，`executed_by=executor`，`authorization_ref`精确引用delegation。terminal certificate仅作
critical submission evidence，不进入被授权Event digest。destination authority以
`(admission_id,delegation_digest)`做single-use CAS；current membership head仍是J1时最多一次写入，already absent或
已被J2/new join supersede时返回 `membership_compensation_conflict` 且零写，绝不得删除后来重新加入者。

失败分支固定为：claim前拒绝零烧；claim后/member acceptance前只revoke原claim；member accepted/Add前执行
membership compensation；Add已接受后先执行同一membership compensation，再由eligible committer执行标准MLS
Remove。Remove绑定旧group/generation/leaf/commit，新generation上只能no-op。deadline触发operation failure，
但cleanup authority持续到成功消费或确定性 conflict。重复、跨admission、executor/proof key错配或deadline前滥用
都必须拒绝。success/repair terminal不得生成compensation terminal certificate。

## 10. Verification Strands

设备密钥验证用于确认“这个 principal/device/key 是否是用户想信任的对象”。验证成功本身不授予登录态、Realm 权限或长期设备权力：

- 同一 principal 的新设备登录，验证成功后仍 MUST 通过 `ak.device.authorize`、DID/key-log operation 或 recovery policy 把设备加入有效设备集合。
- 跨 principal 验证只表达本地人工信任，不得改变对方 PCR 设备授权状态。
- `ak.session.grant` 只授予短期会话能力；不得因 SAS/QR 成功而自动升级为长期设备授权。

### 10.1 标准消息类型

Arkret 标准验证消息通过 to-device 通道发送：

- `ak.key.verification.request`
- `ak.key.verification.ready`
- `ak.key.verification.start`
- `ak.key.verification.accept`
- `ak.key.verification.key`
- `ak.key.verification.mac`
- `ak.key.verification.done`
- `ak.key.verification.cancel`

所有验证消息 content MUST 包含：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `transaction_id` | `string` | required | 交易 ID；对参与 principal/device 组合唯一，长度 1..128，不能复用已完成或已取消交易。 |
| `from_device` | `id:device` | required | 发送设备；MUST 等于 envelope 的 `sender_device_id`。 |

各消息的额外字段：

| `kind` | 额外必填字段 | 说明 |
| --- | --- | --- |
| `ak.key.verification.request` | `methods`, `timestamp`, `expires_at` | 发起验证。`methods` 使用标准方法名，例如 `ak.sas.v1`、`ak.qr.v1`。同 principal 新设备授权请求 SHOULD 另带 `purpose="same_principal_device_authorization"`、`pairing_code`、`new_device_pubkey`（canonical `PublicKey`）、`challenge_proof`（§2.1.2 的 `ak.device-pairing.challenge.to_device.v1`）、`target_attestation`（§5.2.2 的 `device_pairing_target_attestation`，本路径下 `hpke_key` / `algorithms` 的唯一权威来源）、`gate_audience`、`request_canonical_digest` 与 `device_metadata?`；这些字段必须进入 SAS/QR transcript 或等价 proof 绑定。 |
| `ak.key.verification.ready` | `methods` | 接受请求并回报本设备可用方法。 |
| `ak.key.verification.start` | `method` | 选择方法并开始。SAS 还 MUST 带 `key_agreement_protocols`、`hashes`、`message_authentication_codes`、`short_authentication_string`。 |
| `ak.key.verification.accept` | `commitment` | 接受 `start` 并提交本端 ephemeral key 承诺；还 MUST 固定选定算法。 |
| `ak.key.verification.key` | `key` | 发送本端 ephemeral public key。 |
| `ak.key.verification.mac` | `mac`, `keys` | 发送待验证 key 的 MAC 与 key-id MAC。 |
| `ak.key.verification.done` | none | 双方 MAC 验证通过后完成。MAY 带本地生成的签名摘要。 |
| `ak.key.verification.cancel` | `code` | 任意阶段取消；`reason` MAY 给出面向用户的短说明。 |

### 10.2 状态机、超时与并发

标准交互状态机为：

```text
request -> ready -> start -> accept -> key -> mac -> done
```

`cancel` MAY 在任意阶段发送。接收方 MUST 对重复的同一消息做幂等处理；对越序或状态不匹配的消息 MUST cancel，`code=unexpected_message`。

请求超时规则：

- `request.timestamp` 不能比接收设备本地时间晚 5 分钟以上。
- `request.expires_at` MUST be no later than `timestamp + 10m`。
- 用户在展示提示后 2 分钟内没有交互，客户端 SHOULD 本地取消或隐藏提示。
- 过期交易的后续消息 MUST 被忽略或以 `code=timeout` 取消。

并发规则：

- `request` 可以发送给同一 principal 的多个设备；`ready` 之后实际验证 MUST 收敛到两个具体设备。
- 一台接收设备接受后，发起方 SHOULD 向其他待处理设备发送 `cancel`，`code=accepted_by_other_device`。
- 交易完成或取消后，`transaction_id` MUST NOT 在相同 principal/device 组合中重用。

### 10.3 SAS 验证

SAS 验证 MUST 绑定：

- 双方 principal id
- 双方 device id
- 双方 device verify key
- transaction id
- chosen method and algorithms

`accept.commitment` MUST 是对本端 ephemeral public key 与 canonical `start` 消息的哈希承诺。收到 `key` 后，接收方 MUST 重算 commitment；不一致 MUST cancel，`code=mismatched_commitment`。

MAC 阶段 MUST 覆盖完整 transcript，包括双方 principal id、device id、device verify key、transaction id、method、算法选择、双方 ephemeral key 和待验证 key id。任何 transcript 不一致 MUST cancel，`code=mismatched_mac`。

Transcript 中的双方 principal/device MUST 与 `DeviceMessageEnvelope` 的 sender/recipient 字段一致；不一致时 MUST cancel，`code=mismatched_mac` 或 `unexpected_message`。

SAS 展示值 MUST 从同一 transcript 派生。用户确认前，客户端不得把对方 device key 标记为 verified。

### 10.4 QR 验证

QR 验证 MUST 使用一次性 secret 或 public commitment，且 QR 内容 MUST 有过期时间和 intended verifier。

QR payload MUST 至少绑定：

- `transaction_id`
- 展示端 principal id 与 device id
- intended verifier principal id；若已知，还 SHOULD 绑定 intended verifier device id
- 一次性 secret 或 public commitment
- `expires_at`
- supported verification method

QR payload MUST NOT 包含长期私钥、secret storage key、recovery secret 或 MLS group secret。扫码后，客户端仍 MUST 通过 to-device transcript 完成 `mac` / `done`，不能只凭扫码动作直接信任设备。

### 10.5 成功后的动作

同一 principal 的新设备配对完成后，已授权设备 MAY：

1. 签发 `ak.device.authorize` 或符合 DID method 的 key-log operation。
2. 发布 `ak.device.list_update`。
3. 在用户或 policy 允许时，通过加密 to-device 消息共享账户级 secret-storage material 或 MLS Welcome；不得共享 identity root/device private key。

当验证目的为 `same_principal_device_authorization` 时，用户确认后的授权落地 MUST 发生在 `/_arkret/gate/account/*` 认证面，默认使用 `ak.gate.account.command.pair_device.v1`。旧设备把验证 transcript 中绑定的 `pairing_code`、`new_device_pubkey`、`challenge_proof`、自己 author 的完整 `ak.device.authorize` 提交，以及自身 fresh device proof 提交给 gate；从已验签 `target_attestation` 取得的 `hpke_key` 与 `device_signature` 只写入该 authorize Event payload，不在 commit 顶层重复。gate MUST 按 §2.1.2 独立重算 challenge transcript 并验签，再按 §5.2.2 用该 digest 与提交 payload 重建 accepted_device possession 对象并验签 payload 内 `device_signature`，MUST NOT 只做逐字段相等比较；gate 返回的 `authorized_event_ref` 只是 durable `ak.device.authorize` / `ak.device.list_update` 已被接受的引用或等价结果。新设备可通过同一 to-device transcript 的 `ak.key.verification.done` 中的 `authorized_event_ref` hint、后续 full `ak.self.account.stream.subscribe.v1` device list baseline，或重新通过 `ak.gate.account.command.issue_session_grant.v1` 升级会话来观察授权结果；它 MUST 验证 durable device list，而不得把 `done` 消息本身当成授权真相源，并 MUST 在本地装配前完成 §5.4.1 的强制校验。

跨 principal 验证完成后，客户端 MAY 保存由当前 accepted device 签署的本地 trust receipt。该 receipt 只影响本 principal 的信任视图，不授予对方 Realm capability。

### 10.6 Cancel Code Registry

标准 cancel code：

| code | 含义 |
| --- | --- |
| `user_cancelled` | 用户主动取消。 |
| `timeout` | 交易过期或交互超时。 |
| `unknown_transaction` | 本设备不存在该交易。 |
| `unexpected_message` | 消息与当前状态机不匹配。 |
| `unsupported_method` | 无共同验证方法。 |
| `unsupported_algorithm` | 无共同 key agreement、hash、MAC 或 SAS 表示算法。 |
| `mismatched_commitment` | ephemeral key commitment 校验失败。 |
| `mismatched_mac` | MAC 或 key-id MAC 校验失败。 |
| `device_revoked` | 任一参与设备已撤销。 |
| `untrusted_device` | policy 要求验证设备，但设备信任链不满足。 |
| `policy_denied` | Realm、组织或账号 policy 拒绝。 |
| `accepted_by_other_device` | 同一请求已被另一设备接受。 |
| `device_generation_fenced` | 验证过程中发现目标设备属于旧 DID generation；必须重新解析 PCR evidence。 |

### 10.7 Secret Sharing（`ak.secret.*`）

§10.5(3) 允许 accepted device 在验证成功后通过加密 to-device 消息共享账户级 secret-storage material 或 MLS Welcome。本节把该动作收敛为两个标准 to-device kind，用于把账户级 secret（如 MLS account secret / secret storage bootstrap key）从一台已授权设备直传给同一 principal 的另一台已通过 §10.3 SAS 验证的设备，无需用户重新输入恢复口令。它是 [`identity/key-management.md` §7](../identity/key-management.md) 无口令恢复路径的设备直传分支，服务端零知识。

标准 kind（均走 §7 to-device 通道，不进入 Event registry 或任何持久 timeline）：

- `ak.secret.request`：请求设备（通常是新设备）向已授权设备索取某个 `secret_id`。
- `ak.secret.send`：被请求设备把 secret 以 HPKE 密封后回传给请求设备。

两者 content 闭合形态见 [`schemas/device-message.schema.json`](../../artifacts/schemas/device-message.schema.json) 的 `secret_request_content` / `secret_send_content`。

`ak.secret.request.content` 字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `request_id` | `string` | required | 调用方生成的随机关联 id；MUST NOT 在被应答或取消后重用。 |
| `secret_id` | `string` | required | 被请求 secret 的不透明标识，例如 `org.example.mls_account_secret`。 |
| `from_device` | `id:device` | required | 请求（新）设备；MUST 等于 envelope 的 `sender_device_id`。 |
| `recipient_hpke_public_key` | `string` | required | 请求设备控制的 base64url X25519 HPKE 公钥，被请求设备据此密封。它 **MUST** 逐字节等于目标 `from_device` 在该 principal 设备集投影（§4 device record / §6 device list）中登记的权威 `hpke_key`；不等即 fail closed（见下方规则）。**MUST NOT** 仅因该公钥"看似格式合法"或与某条 SAS transcript 内某值相符就接受——SAS（§10.3）只验证双方 device verify key（Ed25519），不覆盖 HPKE（X25519）密封密钥，故密封目标公钥必须独立绑定到权威 `hpke_key`。 |

`ak.secret.send.content` 字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `request_id` | `string` | required | 关联到 pending 的 `ak.secret.request`；MUST 等于密封 plaintext 内被认证的 `request_id`。 |
| `secret_id` | `string` | required | 与请求一致的 secret 标识。 |
| `from_device` | `id:device` | required | 授权（已有）设备；MUST 等于 envelope 的 `sender_device_id`，且 MUST 是接收 principal 的未撤销设备。 |
| `scheme` | `string` | required | MUST 为 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 中的 active suite id；v1 default-MUST 为 `ak.hpke_x25519_aead_chacha20poly1305.v1`。未登记 / 非 active suite MUST fail closed（`unsupported_hpke_suite`）。 |
| `enc` | `string` | required | base64url HPKE（RFC 9180）封装密钥（KEM 输出）。 |
| `ciphertext` | `string` | required | base64url HPKE AEAD 密文。HPKE AAD 见下方定义。 |

HPKE AAD（本 kind 的具体绑定）MUST 是对以下字段的 canonical JSON（RFC 8785 JCS）：`device_message_id`、`kind`、`sender_principal_id`、`sender_device_id`、`recipient_principal_id`、`recipient_device_id`、content 中的 `request_id`、content 中的 `secret_id`，以及 envelope 中已经通过 [`time.schema.json#/$defs/timestamp`](../../artifacts/schemas/time.schema.json) 验证的原字段 `expires_at`。`expires_at` 在 AAD 中仍是逐字相同的 `.sssZ` string；MUST NOT 另派生 `expires_at_unix` / `expires_at_unix_ms`，也不得宽松解析后重排。principal / device / message ID 与 `request_id` / `secret_id` 都使用外层原始 canonical string，在收发两端从 `DeviceMessageEnvelope` 与 `ak.secret.send.content` 确定性重建。把 `device_message_id` 与 `request_id` / `secret_id` 同时放入 AAD 可防止中间层替换外层幂等身份或业务关联字段。§7 的通用 AAD 最小集不包含由队列服务物化的 `sent_at`；本 kind 由发送方分配的 `device_message_id` 与密封 plaintext 内的一次性 `request_id` 提供抗重放/新鲜性绑定。

`ak.secret.send` 的 plaintext（仅 HPKE 解封后可见，不出现在 wire 任何明文字段）MUST 至少携带被请求 secret 本体、其版本号、`request_id` 与 `secret_id`；接收方解封后 MUST 校验内层 `request_id` / `secret_id` 与外层 content 一致、且 `request_id` 命中本端某个 pending 请求，否则丢弃。

规则（normative）：

- 时序：`ak.secret.request` / `ak.secret.send` MUST 在两台设备完成 §10.3 SAS 验证之后发送。请求与发送绑定的设备 MUST 与该 SAS transcript 绑定的 device key 一致，防止“验证设备 A、把 secret 发给设备 B”。
- TTL：二者受 §7 队列 TTL 约束；`ak.secret.send` SHOULD 使用更短 `expires_at`（推荐 10–60 分钟）。
- 用户在环：被请求设备在发送 `ak.secret.send` 前 MUST 经用户显式授权，并 MUST 校验目标 device ∈ 本 principal 当前授权设备集合且未撤销。
- 密封密钥绑定（normative）：被请求设备在密封并发送 `ak.secret.send` 前，MUST 校验请求中的 `recipient_hpke_public_key` 逐字节等于目标 `from_device` 在设备集投影（§4 device record / §6 device list，经 §8.3 PCR authorization evidence 验证后视为权威）中登记的 `hpke_key`；不等 MUST fail closed（不密封、不发送），并 SHOULD 提示用户该请求异常。该校验闭合"验证设备 A 的 verify key、却把账户级 secret 密封给攻击者控制的 X25519 公钥"这一密钥绑定缝隙——它独立于 §10.3 SAS（SAS 只绑 verify key）。device `hpke_key` MUST 被 accepted `ak.device.authorize` payload 与 PCR authorization chain 覆盖；仅有服务端裸投影、但无法验证 HPKE key 绑定的设备不得作为账户级 secret 的接收目标。
- 反滥用：接收方 MUST 丢弃 unsolicited `ak.secret.send`（无本端 pending `request_id`）；`request_id` 用后即作废；对同一 `from_device` 的重复请求 SHOULD 限速；多次拒绝 SHOULD 提示用户考虑撤销该设备。
- 审计：被请求设备 SHOULD 记录一次 secret 共享审计（如 `ak.audit.accessed`，`access_kind=secret_share`）。
- 止损：误授权后，用户从任一已授权设备发起 §2.2 设备撤销并轮换对应 account secret、重新封装全部备份即可使被泄露设备失效。
- QR：与 §10.4 一致，QR payload 仍 MUST NOT 直接携带任何 secret 本体；secret 只经本节 HPKE 密封的 `ak.secret.send` 传输。

## 11. Secret Storage（client-local cache form）

Secret storage 用于保存：

- recovery secret（仅 `personal_node + single_point_of_failure=true` 的显式降级可在可信本地 keychain 持久化；其他 profile 只能在 custody 仪式内瞬态存在，local cache 最多保留不可逆 fingerprint / durable checkpoint，不得保留 secret bytes）
- MLS group secrets backup key
- applet delegated device secret

`ak.secret_storage.v1` 是 **client-local** envelope，仅用于设备本地或可信操作系统 keychain；**不得作为线级 (wire) 上传格式**。

Device / Key Server 的 `ak.keys.backups.*` endpoint MUST 只接受 `ak.schema.key_backup.v1` wire envelope。任何不符合 `ak.schema.key_backup.v1` 顶层 `required`（含 `series_id` / `series_seq`）的请求体 MUST 返回 `schema_violation`，原因码 `key_backup_wire_schema_required`。Client-local `ak.secret_storage.v1` 存储不受影响，但 MUST NOT 通过 `PUT /_arkret/self/keys/backups/{backup_id}` 同步。

任何同步到 Device / Key Server 或其它远端服务的 secret，MUST 使用 §12 的 `ak.schema.key_backup.v1` envelope，并设置对应 `backup_kind`：

| Secret 类别 | `backup_kind` |
| --- | --- |
| 账户级 secret-storage material | `secret_storage` |
| MLS epoch / Realm history secret | `mls_history` |
| 外部托管或 profile 自定义 account secret | `secret_storage` |

每个 `backup_kind` MUST 使用独立 HKDF info 字符串派生 commitment / wrap key，禁止跨 class 共享密钥材料。规范权威表述见 [`../identity/key-management.md` §7.1](../identity/key-management.md)：HKDF info 形如 `arkret-key-backup/<backup_kind>/<subdomain>/v1`（`/` 分隔，含 subdomain 维度）。任何 v1 wire 实现 MUST 跟随 `identity/key-management.md` 的 canonical 形式，本节描述只作为引导。

recovery secret、identity root seed、HKDF PRK 与完整派生 private key 不属于上表任何 wire 类别；即使本地 `ak.secret_storage.v1` 降级缓存允许持有 recovery secret，也 MUST NOT 把该 item 映射为 `ak.schema.key_backup.v1`、`ak.secret.send` 或任意远端同步对象。

Client-local secret storage 的存储格式仍可使用本节的 `ak.secret_storage.v1` envelope，但其字段不进入任何 wire / hash / 签名输入；服务端不接受该 envelope。

## 12. Key Backup

Key backup 保存已加密的 exporter history-secret ranges。它只覆盖当前 actor 已经合法取得的历史范围，不保存
active MLS group state、leaf signer、sender counter、ratchet 或 pending Welcome，也不存在 managed Agent PCR 的跨-principal
active-state 例外。Native Agent 与 ordinary endpoint 的 fresh restore 都只能安装 schema 允许的 history-secret ranges；重新进入
active group 必须走 current authorization 下的标准 KeyPackage/Add/Welcome（见 [`../identity/key-management.md` §7.5.6](../identity/key-management.md)）。

备份单元使用 `ak.schema.key_backup.v1`，并设置 `backup_kind="mls_history"`。示例：

```json
{
  "backup_id": "ak:backup:01964138-8000-7000-8000-000000000000",
  "actor_id": "ak:did_core:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH",
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "backup_kind": "mls_history",
  "backup_version": "kb_1",
  "series_id": "ak:backup_series:01964138-1000-7000-8000-000000000000",
  "series_seq": 0,
  "supersedes": null,
  "created_at": "2026-04-26T00:00:00Z",
  "encryption": {
    "recipient_method": "secret_storage_key",
    "recipient_key_ref": "mls_group_secrets_backup_key",
    "aead": {
      "name": "xchacha20_poly1305",
      "aead_profile": "ak.aead.xchacha20_poly1305.v1",
      "nonce": "base64url..."
    }
  },
  "domain_separation": {
    "subdomain": "mls_epoch"
  },
  "contents": [
    {
      "item_kind": "mls_epoch_secret",
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "mls_group_id": "base64url",
      "epoch": 42,
      "first_event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
      "last_event_id": "ak:event:AbxXq2kgnCNX8X5eerT7jjvw-n-ylkJEhAuk2jGoe6CJ"
    }
  ],
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "auth_data": {
    "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
    "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#ak:device:01964137-0000-7000-8000-000000000000",
    "signature": "base64url...",
    "signature_algorithm": "Ed25519"
  }
}
```

备份 MUST 加密给 recovery public key 或 secret storage key。服务端 MUST NOT 能解密。

> **Recipient method 与 fresh-device 恢复（normative）**：上例的 `recipient_method="secret_storage_key"` 仅适用于**已经持有 secret_storage root key 的现有设备**（见 `identity/key-management.md` §7.5.3）。**全新设备 / 新浏览器**在尚未解锁 secret_storage root 之前 MUST NOT 直接用 `secret_storage_key` envelope 恢复 `mls_history`；它 MUST 走以下两步之一：
> 1. **recovery_public_key（推荐，HPKE）**：`mls_history` envelope 直接加密给 actor 的 recovery public key（`recipient_method="recovery_public_key"`，HPKE base mode，参数见 `identity/key-management.md` §7.5.2）。新设备用经 recovery policy 解锁的 recovery 私钥即可 HPKE-open，无需先持有 secret_storage root。这是 fresh-browser same-account MLS 恢复的规范路径。
> 2. **先解 root，再用 secret_storage_key**：新设备先用 `passphrase_kdf`（`passphrase_kdf` envelope，见 `identity/key-management.md` §7.5.1），或经 recovery policy 释放 recovery private key 后用 `recovery_public_key` 解出 `secret_storage` 域的 root（取得 `mls_group_secrets_backup_key`），之后才能解 `secret_storage_key` 的 `mls_history` envelope。
>
> `recipient_method` 取值 MUST 来自 `ak.schema.key_backup.v1` 的枚举（`passphrase_kdf` / `recovery_public_key` / `secret_storage_key`）。实现 MUST NOT 发出枚举外的值（例如 `device_snapshot_secret`、`threshold_recovery`、`hardware_wrapped_key` 不是合法 wire 值，receiver/validator MUST fail closed）。threshold / hardware / trusted recovery service 是 recovery policy / proof 层的 unlock factor，不是 backup envelope recipient method。

规则：

- 备份 metadata MUST 绑定 actor DID、device id、backup id、backup class、created_at、ciphertext digest 和加密参数。
- 任何 backup class 只要使用 `recovery_public_key`，就 MUST 携带顶层 `recovery_policy_ref{policy_id, policy_version}`；该成员自动进入完整 envelope 签名转录。`recipient_key_ref` 只能解析到该 accepted policy 的 `recovery_key_agreements[]`。`mls_history` / `secret_storage` 在读取/恢复时须按 accepted policy history、active-series 与轮换规则拒绝回滚。不一致 MUST `recovery_policy_mismatch`。只有 `secret_storage_key` 等非 recovery-public-key 方法携带的 `recovery_policy_ref` 才是可选 hint；任何 policy ref 都不得替代 active-series record、frontier_ref 或 Realm/MLS 授权校验。
- 上传设备 MUST 通过 `auth_data` 对 backup metadata 与 ciphertext digest 签名，并携带当前 accepted `device_authorize_event_id`；`frontier_ref` 只允许最小值为 1 的整数 `device_generation_ref`。签名输入固定为 `RFC8785_JCS(envelope 删除 auth_data.signature)`，所有实际存在的 required、optional 与 `x_*` 成员自动受认证，不携字段名清单。签名链必须链接到当前 PCR device authorization evidence。
- 服务端 MUST 只允许同一 actor 的当前授权设备、满足 recovery policy 的恢复流程，或 policy 明确授权的组织恢复服务读取备份密文。
- v1 没有 controller-owned managed Agent active-state backup 分支。`mls_history` 对所有 actor 都只承载 exporter history-secret ranges；它不携 Agent PCR binding、active MLS state、runtime key 或 pairing readiness。Fresh Agent endpoint 生成新 runtime key，并经标准 KeyPackage/Add/Welcome 重新加入唯一 group。
- 服务端返回备份列表时 SHOULD 最小化 metadata；不得向无关 caller 暴露 Realm membership、MLS group id 或历史范围。
- 删除备份只删除服务端密文和 metadata；它不撤销 DID 控制权，也不改变 Realm membership。需要吊销设备或轮换 MLS epoch 时必须发布相应事件。
- 被撤销设备上传的新备份 MUST 被拒绝。撤销前上传的备份 MAY 继续保留，但恢复使用时必须重新验证当前 recovery policy、device revocation state 和 Realm history visibility。
- **Series & freshness**：所有 wire envelope MUST 满足 `identity/key-management.md` §7.6 的 series 链规则（`series_id` / `series_seq` / `supersedes` / `supersedes_digest`）。Receiver 在恢复或读取时 MUST 先用 `ak.key_backup.active_series` / `ak.schema.key_backup_active_series.v1` signed active-series record 确认 canonical `series_id`（当同一 `(actor_id, backup_kind)` 存在多个 series 时），再重建链并仅使用尾部 envelope；服务端 MUST NOT 重写、改写或省略已上传 envelope 的链字段，除非按 §12.2 retention 流程整组迁移。

### 12.1 Backup API

Device / Key Server 对 encrypted backup object 提供标准操作：

```http
PUT /_arkret/self/keys/backups/{backup_id}
GET /_arkret/self/keys/backups
POST /_arkret/self/keys/backups/{backup_id}/unlock
DELETE /_arkret/self/keys/backups/{backup_id}
```

`PUT` 请求体 MUST 是 `ak.schema.key_backup.v1`，且 path 中的 `backup_id` MUST 与 body 中的 `backup_id` 一致。`PUT` 按 `(actor_id, backup_id)` 幂等；同一 `backup_id` 若提交不同 canonical content MUST 返回冲突错误。

`PUT` 还 MUST：(a) 校验 `series_seq` 严格大于该 series 已有的最大 sequence（首条 MUST `series_seq=0`）；(b) 校验 `supersedes` 引用的前一条 envelope 存在、`actor_id` / `series_id` 匹配，并由当前 caller 可见；(c) 校验 `supersedes_digest` 等于服务端持有的前一条 canonical_json digest（排除 `auth_data.signature`）；任一失败 MUST 返回 `409 Conflict`，reason 分别为 `series_seq_not_monotonic` / `series_predecessor_not_found` / `series_chain_broken`。

`GET /_arkret/self/keys/backups` 支持 `?series_id=<series_id>` 与 `?backup_kind=<class>` 过滤；响应 MUST 按 `series_seq` 升序返回该 series 的全部 envelope metadata，便于 client 重建链。当仅按 `backup_kind` 查询且返回多个 series 时，server / client MUST NOT 用返回顺序、最大 `series_seq` 或最新 `created_at` 推断 active series；恢复方 MUST 使用 `identity/key-management.md` §7.6 的 `ak.key_backup.active_series` / `ak.schema.key_backup_active_series.v1` signed active-series record。`list` 响应只返回调用方可见的 backup metadata、digest 和 retention hints；不得越过 `identity/key-management.md` §7.8 的限速。

`unlock` 返回完整 encrypted backup object：request body MUST 携带 `ak.schema.key_backup_unlock_proof.v1`，并受 fresh PCR device proof 与 rate limit 约束。普通单对象 `delete` MUST 要求当前设备或 accepted recovery policy 允许的高风险证明；current DID proof 只有在同一 account authority pair 的本地 recovery policy 显式启用 DID-root factor 时才可进入。active series 的删除还必须遵守 transaction-bound erase 合同，不得用单对象 operation 伪造完成证据。

### 12.2 Retention and Erasure

| Profile | `delete_after` 默认 | `legal_hold` 行为 |
| --- | --- | --- |
| `ak.profile.personal_node.v1` | `null`（无自动过期） | clients-only flag；服务端不强制 |
| `ak.profile.small_team.v1` | `null` | 仅在组织声明 `ak:policy:<id>` 允许时可置 `true` |
| `ak.profile.organization.v1` | 365d（可被 Realm policy 覆盖） | 服务端 MUST 在 `legal_hold=true` 时阻塞 user-initiated delete |
| `ak.profile.high_security_organization.v1` | 90d | 服务端 MUST 强制 `legal_hold` 与审计配对 |
| `ak.profile.sovereign_deployment.v1` | deployment-defined | 与本地法务合规框架对齐 |

要求：

- 服务端 MUST 在收到 user erasure 请求（参见 `ak.audit.erasure_receipt` / `ak.schema.erasure_receipt.v1`）时，按 erasure receipt 的 `scope` 与 `subject` 处理对应 backup envelope：若 `subject.kind="principal"` 且 `scope.storage_boundary` 涵盖 `device_secret_store`，相应 `secret_storage` envelope MUST 被删除并产出 `ak.schema.erasure_receipt.v1` 子条目。
- 用户主动删除自身备份与 erasure 流程区分清晰：常规 `DELETE` 不写 erasure receipt，但 `identity/key-management.md` §7.8 的高风险审计仍要求落地 `ak.audit.accessed` (`access_kind="key_backup_delete"`).
- `legal_hold=true` 的 envelope MUST 被服务端拒绝删除（即便提供 high-risk proof）；解除 hold MUST 通过受授权的 policy update 完成，并写入审计。
- 同一 series 内的 retention 必须保证链不被打破：服务端 MUST NOT 删除 active series 的非尾部 envelope；旧 series 只有在已经被 active-series record 移出 primary source 后，才 MAY 按 retention / erasure 策略整组删除或迁移。若该删除属于`SecurityRotationTransaction`，两个backup kind的pointer、逐series进度、partial retry与complete confirmation一律以[`identity/security-transactions.md` §3](../identity/security-transactions.md)为准。
- erasure 完成后保留的 `retained_stub_digest` MUST 仅含 metadata 哈希，不含密文与 KDF 参数，以避免间接成为离线爆破证据。

## 13. Private History-Key Request and Response

历史密钥恢复不得使用 public Realm Event 或通用 `DeviceMessageTarget`。唯一 surface、DTO 与 proof transcript 来自
[`history-key.schema.json`](../../artifacts/schemas/history-key.schema.json) 和
[`history-visibility.md`](../governance/history-visibility.md)：

- `POST /_arkret/self/history-key-requests` 创建 scope-private durable request；`POST /_arkret/self/history-key-requests/read` 执行无状态列表查询；
- `POST /_arkret/self/history-key-responses` 发送 immutable manifest/chunk；
- `POST /_arkret/self/history-key-responses/read` 与 `POST /_arkret/self/history-key-responses/ack` 仅凭 `Arkret-History-Capability` 呈递的 history response capability 读取/确认；URL、query 与 body 均不携 request locator。

Requester 必须在发送前 durable 保存 HPKE private key、canonical request intent、closed
`trusted_scope_anchor` 及使该 anchor 成为本地 trusted 的 verification checkpoint/material；create 返回后保存
service receipt 和 sealed history response capability。相同 request id+intent 返回相同 bytes，不同 intent 冲突；retry 不得替换
requester 选择的任何 authority anchor。
Source 必须先 durable 保存完整 outbox 后发送；accepted/duplicate 只推进 exact record，重启后不得重封。

Request、source response、service receipt 与 service response record 分别使用 proof-context registry 中的四个 closed
context，全部复用标准 generic detached-JWS proof shape。Source proof 签入 actor/sender domain/scope/request/receipt/
response stream/expiry 与 content；不签服务生成的 sent_at 或 release attestation。Service record
proof 覆盖 sequence、cursor、source-record digest、exact response、sent_at 与条件式 release attestation。Ordinary human/Native Agent/minimal source sender domain
按 exact historical active Leaf BasicCredential identity 校验；RRK holder 使用 archive 钉住的 holder signing binding，
不得冒充 MLS leaf。

每个 chunk 首次入队是 release 线性化点：服务在同一事务复核 request 当前 membership、source、scope/Circle parent、
current history frontier、profile-dispatched closed authority predicates、typed locator/digest vector、safety/audit 与 quota，再原子生成
`HistoryReleaseAttestation`、分配单调 sequence/cursor 并持久化 record。
Exact retry 返回原 record/receipt 且不重跑已收紧 policy；同 id 异 digest 冲突。Receiver 可 durable 暂存乱序 chunk，
但 manifest/descriptor、activation slice、current release proof 与 HPKE 全部通过后才安装。

Ack 必须携 `high_water_cursor` 与按顺序 record digest 的
`{response_id,record_digest,status}`。status 只允许 `installed|cryptographically_rejected|superseded_duplicate`；
三者均释放 processing quota，只有 installed 计入 range coverage。服务在 ack/GC 后保留有界 idempotency tombstone 到
原 expiry，避免 exact retry 永久 pending。


## 14. PCR-Policy Device Recovery

全设备丢失时，账号重新登录不能替代 PCR recovery proof。基础路径由丢失前已进入 accepted Seal 的
recovery policy 授权，并提交两条 Event：

1. policy-authorized `ak.device.reanchor` 绑定 policy/version/session、`principal_id`、`principal_server_id`、replacement
   authorize payload digest 与 monotonic PCR generation CAS；
2. replacement device 自签 `ak.device.authorize`，`authorization_binding_kind="pcr_recovery"`，
   `prev_refs` 只指向 re-anchor Event。

两条 Event 必须原子接受，receipt `scope.kind="device_reanchor_unit"`。该 scope 的封闭字段集恰为
`{kind, principal_id, principal_server_id, realm_id, previous_device_generation, new_device_generation}`：它与 `ak.device.reanchor` payload 选择同一个本地 account authority pair，每个同名字段 MUST 与被覆盖 payload 逐字节相等，任一不等以 `device_reanchor_authority_mismatch` fail closed。re-anchor 与 replacement-authorize digest 分别从 `events[]` 中唯一对应 kind 的 typed `event_id` 解码，scope 不重复携带。scope MUST NOT 携带 `did_version_id`、
`registry_head` 或任何 DID publication 字段，接收方也 MUST NOT 由 generation ref 反向合成它们。接受后
generation fence 使旧 generation 全部失效。`current_device_generation_ref` 是 PCR-local monotonic ref，
MUST NOT 使用或等于 DID `versionId`；resolution cell 不随基础恢复推进。

DID-root 只是在 recovery policy 中显式启用、可撤销的一种 proof kind。当前 DID root 本身不能
re-anchor；method 不支持 history/pre-rotation 或 policy 未启用时必须拒绝。RecoveryTransaction 不包含
DID publication；用户执行 resolution successor 时必须走独立 DID operation 发布流程，且其失败不得改变
PCR recovery transaction 的 accepted-step ledger。

### 14.1 Device lifecycle 与 trust 正交状态

设备 lifecycle 为 `active | revocation_pending | revoked | expired | generation_fenced | conflicted`；验证状态为 `verified | unresolved | stale`。两维 MUST 分开投影，account `device_summary` 不得用 verification 值代替 lifecycle status，也不得因 evidence unresolved 省略 lifecycle。业务授权要求 lifecycle=`active`、evidence=`verified`、authorize generation 等于 current generation 且目标 Event basis 被 accepted Seal 覆盖。任何单一条件失败都不能由账号 session、DPoP 或 transport service signature 补足。

### 14.2 Recovery UI requirements

客户端必须在任何网络副作用前 durable 保存 identity root/recovery、device identity、HPKE、DPoP keys 与完整 onboarding/recovery draft。UI 应区分：可 exact retry、genesis 已由另一 unit 赢得、必须 re-anchor、以及无 proof 无法恢复；不得让用户通过再次注册静默替换既有 PCR。

## 15. Applet Device Delegation

Applet 如需代表 Ghost Actor 或桥接用户参与 E2EE，MUST 使用受限 delegated device：

- device id MUST 标记 `applet_id`。
- capability MUST 限制 Realm、协议、动作和有效期。
- delegated device 不得签发新的 human device。
- delegated device 的 to-device 权限 MUST 只覆盖其 namespace 内 actor。
