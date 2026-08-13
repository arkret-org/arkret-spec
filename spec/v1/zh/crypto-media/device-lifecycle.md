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

Arkret v1 把三件事分开处理：

- **登录因子验证**：Auth Server 验证 password、passkey、OIDC、SSO 或 recovery factor，只能产出 sender-constrained handoff/session、触发 identity-root recovery，或请求已有 accepted device 批准配对；它不能自行产生设备授权。
- **设备授权**：新设备成为长期有效设备，MUST 落成 `ak.device.authorize`、DID/key-log operation 或等价 signed event。只有这一步改变设备集合。
- **设备密钥验证**：SAS/QR 只确认 device key / identity key 的人工信任。验证成功不得自动创建登录态、长期 device grant 或 Realm capability。

因此“新设备登录”的推荐实现是：新设备先本地生成 device key，使用登录因子或已授权设备完成交互验证，再由当前有效授权方签发 `ak.device.authorize` 或短期 `ak.session.grant`。短期 Web/OIDC 登录可以只使用 `ak.session.grant`；需要 E2EE 历史、secret storage 或长期离线能力时，仍必须走设备授权和设备密钥验证。


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
5. **事件广播**：主设备向 principal control stream 广播自己原始签署的 `ak.device.authorize` Event Initial Submission；若封装为 Event Envelope，其 `realm_id` 是目标 principal 的 `principal_control_realm_id`。`pair_device` 请求 MUST 携带该 exact submission、payload 内 exact `hpke_key` 与新设备 exact `device_signature`；Account Authority / Principal Server MUST 走普通 Event admission、复算 payload / envelope digest并验证当前设备 proof 与 candidate possession proof（`accepted_device` 分支的 possession domain 与签名对象见 §5.2.2），MUST NOT 代铸 Event、替换 payload 字段或直接写 device-list projection。新设备获得的能力由该 accepted Event、session grant、Realm capability 和 policy 共同限制，不是自动获得 principal 的全部权限。

#### 2.1.1 短链暂存与 resolve（server-mediated，normative）

§2.1 步骤 1 的“临时连接信息”MAY 由 Principal Server 暂存并以短句柄承载，而非把设备公钥与配对材料整包放进二维码。采用该短链形态时 MUST 满足以下约束；它只改变“配对材料如何到达主设备”这一传输层，不改变 §2.1 步骤 3 的授权模型。

1. **暂存（stage）**：新设备经**免认证**端点 `POST /_arkret/open/device-pairing/requests`（`ak.open.device_pairing.command.stage`）提交 `new_device_pubkey`（canonical `PublicKey`，见 [`public-key.schema.json`](../../artifacts/schemas/public-key.schema.json)：`kty` / `kid` / `algorithm` / `key` 四字段，`key` 为密钥材料、`kid` 为 `ak:device:<uuidv7>`）与 `client_nonce`，以及可选 `display_name` / `device_metadata`。**stage 请求 MUST NOT 携带 challenge proof**——该 proof 必须承诺 server 在本次调用中才铸出的值，因此在 stage 时不可能存在（这条顺序约束是 §2.1.2 transcript 可生成性的前提）。Server 铸 `device_pairing_request_id`（`device_pairing_request:<uuidv7>`）、短 `pairing_code`、`gate_audience`（本 Account Authority 的 `gate_account_base` origin）与 `server_nonce`，以有界 TTL（SHOULD ≤ 10 分钟）暂存一条 **account-less** 记录（state `pending_authorization`），返回 `{device_pairing_request_id, pairing_code, gate_audience, server_nonce, expires_at}`。暂存记录 MUST 同时保存提交的 `new_device_pubkey` 与 `client_nonce`——它们是 §2.1.2 路径 A transcript 的 member，gate 必须能只凭该记录重算 transcript。暂存记录在被授权前**不绑定任何 principal、不授予任何东西**。
2. **短链承载**：stage 返回后，新设备按 §2.1.2 生成 `challenge_proof`，再按 §5.2.2 生成 `device_pairing_target_attestation`（承载它自己的 `hpke_key` / `algorithms` 并绑定该 `challenge_proof` 的 `transcript_digest`），由二维码同时承载短 deep-link、该 proof 与该 attestation：`{arkret_base_url}/_arkret/open/device-pairing/resolve#token=<token>&proof=<proof>&attestation=<attestation>`，其中 `token = base64url_nopad(canonical_json({"r": device_pairing_request_id, "c": pairing_code}))`，`proof = base64url_nopad(canonical_json(challenge_proof))`，`attestation = base64url_nopad(canonical_json(device_pairing_target_attestation))`。`token`、`proof` 与 `attestation` MUST 仅出现在 URL fragment 或请求 body，MUST NOT 进入 URL path 或 query（避免进入服务端/代理日志）。**proof 与 attestation 走带外通道到达主设备，MUST NOT 经免认证 stage / resolve 面回传给 server**：暂存面是匿名的，让它持有这两者既无必要也扩大攻击面。二维码容量不足时 SHOULD 缩短 `device_metadata` / `display_name` 等可选材料，MUST NOT 把 attestation 改由服务端中转。
3. **resolve 与人工确认**：已授权设备经**免认证**、body-only 的 `POST /_arkret/open/device-pairing/resolve`（`ak.open.device_pairing.read.resolve`）以 `token` 换取 `DevicePairingBootstrap`（含 `arkret_base_url`、`device_pairing_request_id`、`pairing_code`、`new_device_pubkey`、`client_nonce`、`gate_audience`、`server_nonce`、可选 `display_name`/`device_metadata`、`expires_at`）。bootstrap **不含也不得含** `hpke_key`、`algorithms`、`challenge_proof` 或 attestation：这些只经带外通道到达，权威来源见 §5.2.2。已授权设备 MUST 用这些 server-minted 值按 §2.1.2 重算 transcript 并对二维码带来的 `challenge_proof` 完成验签，**再按 §5.2.2 独立重建并验签 `device_pairing_target_attestation`**（要求 `device_id` 等于 `new_device_pubkey.kid`、`device_public_key` 与 `new_device_pubkey.key` 解码为同一 Ed25519 key、`pairing_challenge_transcript_digest` 逐字节等于自己刚重算的 `transcript_digest`），全部通过后才可向用户呈现为可配对设备。授权 UI MUST 同时显示 requesting-device metadata、`device_id` / key fingerprint、完整 pairing code 与 `gate_audience`，并要求用户把 code 与新设备屏幕逐位比较后显式确认；通过密码学校验本身不得自动触发授权。用户确认后，批准设备 MUST 从验签通过的 attestation（而非服务端响应或 UI 输入）取 `hpke_key` / `algorithms` 填入 authorize payload，再按 §2.1 步骤 3 走 `ak.gate.account.command.pair_device` 授权：该授权端点仍要求授权方是**已验证设备**，server MUST NOT 因短链暂存本身改变设备集合或放宽授权前置。
4. **回填与 status**：授权端点 MAY 携带 `device_pairing_request_id`。携带时，Account Authority MUST 要求该 id 对应的暂存记录仍为 `pending_authorization` 且未过期，要求记录中的 `pairing_code`、`new_device_pubkey` 与授权请求逐字段一致，并**按 §2.1.2 用该暂存记录自己的字段重算 transcript、验证请求携带的 `challenge_proof`**（逐字段相等比较只能证明字节未被中途替换，不能证明签名对哪个 challenge 或哪个 audience 有效，因此 MUST NOT 用相等比较代替验签）；随后**按 §5.2.2 用同一次重算得到的 `transcript_digest` 与 `authorize_event.event.payload` 的目标材料重建 accepted_device possession 对象、验证 `device_signature`**。这两次验签、设备授权 Event 走普通 admission 落库、device projection 更新、暂存记录消费并翻为 `authorized`（记录 `device_id` 与 `authorized_event_ref`）**MUST 在同一原子边界内完成**：任一不匹配不得授权设备，且不得留下已消费但未授权、或已授权但未消费的中间状态。响应丢失后的重放不是幂等成功——暂存记录已不是 `pending_authorization`，第二次提交 MUST fail closed（不得授权第二台设备、不得重铸 Event），调用方以 status 轮询或 `uncertain_outcome` 指定的查询操作确定结果。新设备经**免认证**、body-only 的 `POST /_arkret/open/device-pairing/requests/status`（`ak.open.device_pairing.read.status`）以 `{device_pairing_request_id, pairing_code}` 轮询得到 `{state, device_id?, authorized_event_ref?}`；`authorized_event_ref` 是 §5.4.1 装配前强制校验的入口。
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
- `ak.gate.account.command.pair_device` 的请求体 MUST 恰好携带 `device_pairing_request_id`（路径 A）或 `challenge_transcript`（路径 B）之一；两者同时出现或都缺失 MUST `schema_violation`。这条排他约束在 schema 层由 `oneOf` 强制，使 gate 永远知道该用哪套 transcript，而不是靠猜。
- `transcript` 名与当前路径不符 MUST 拒绝；MUST NOT 接受路径 A 的 proof 用于路径 B（反之亦然）。
- proof 未通过验证的暂存记录 MUST NOT 授权任何设备；缺失 `challenge_proof` 的 `ak.gate.account.command.pair_device` MUST `schema_violation`。
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
> 且该 transaction MUST 在提交 `ak.device.revoke` **之前**创建：`ak.device.revoke` 一旦 accepted
> 不可回滚，而其后的每一步都是独立远端写。固定顺序、reserved id 与崩溃续跑合同见
> [`../identity/security-transactions.md` §3](../identity/security-transactions.md)。
> 在没有该 transaction 的情况下重试轮换会重新生成 secret 与 series id，而不是续跑首次计划。

当设备丢失时，用户可从任何其他已授权设备、DID 控制密钥或 recovery policy 允许的恢复服务发起吊销操作：发布 `ak.device.revoke`，停止接受该设备的新签名写入，并对受影响的 MLS 群组触发 `Remove` 与 Epoch 更新。若该设备曾被写入 DID Document，撤销流程还必须按 DID method 规则移除或失效对应 verification method。

`ak.device.revoke` 是 principal control stream 上的 Control Move：其 Event Envelope MUST 携带 `seal_basis={leaves[]}`（撤销方签名时观察到的 accepted Seal refs，进入 canonical Event bytes 并被撤销证明签名覆盖，见 `../authz/event-auth-state-resolution.md` §5）；payload 不携带任何 frontier 字段。客户端铸造 single-leaf basis 的注册来源是 `ak.self.events.read.frontier?realm_id=<principal_control_realm_id>` 返回的 Realm Seal view，取 `leaves=[seal_id]`；client MUST 验证所引 Seal并自行重算 roots，但不把 roots 复制进 Event。来源不可用时 MUST fail closed，不得伪造 basis。撤销自被 accepted Seal 覆盖（`control_sealed`）起生效；Principal Server / Principal Server sync surface 在拒绝该设备后续 session grant、KeyPackage、to-device write 或 Event write 时，MUST 以该 covering Seal 或其后继 Seal view 作为判定依据，不得用本地布尔缓存替代。

**accepted→sealed 窗口的预先 fail-closed（normative）**：撤销已被受理服务 accepted、但尚未被 covering Seal 覆盖（`control_sealed`）的窗口内，受理服务对该设备后续 session grant / KeyPackage / to-device write / Event write 的处置规则按 profile 分级：

- 通用部署 SHOULD 在该窗口内预先 fail closed（拒绝该设备的上述请求）。
- **声明 `ak.profile.e2ee_client.v1` 或任何专门 hardening / 高安全 deployment profile（如 `high_security_organization` / `sovereign_deployment`）的部署 MUST 在该窗口内预先 fail closed**——高安全语境下"撤销已提交即不再为该设备服务"是硬承诺，不得在等待 Seal 期间继续放行被撤销设备的写入或密钥获取。
- receipt→decision 窗口 MUST 服从 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §7.2 的 proposal 有界决议合同；它保证 include / signed-reject / bounded signed-defer 之一，不保证 proposal 被接受，也不是 Seal finality SLA。设备撤销 proposal 尚未进入 accepted Seal 时，若旧授权安全性无法证明，受理服务 MUST fail closed；MLS-backed scope 另受 [`encryption-and-audit.md` §2.4](../crypto-media/encryption-and-audit.md) `max_mls_commit_delay_ms` 发送阻塞窗口约束。迟到但有效的 Seal 仍按 CBA 规则接受，decision-overdue fault 保留。

共享 E2EE Realm 不能只看到“某设备已撤销”的服务端布尔值就推进新 epoch。对应 `ak.mls.commit` Remove 的 `governance_binding.security_frontier_digest` MUST 从已经包含该 `ak.device.revoke` 或将其导入 Realm 的显式 leaf-remove Control Move 的 accepted state 重算，且该撤销 MUST 已被 principal control stream 的 accepted Seal 覆盖；否则 Commit 不满足 MLS Security Frontier Binding，active generation 不得推进。


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

**grant-binding key 与设备身份 key 的生命周期正交(normative)**:`grant-binding key` 是**会话认证凭据**,`cnf.jkt`、`ak.session.grant` 轮换与 hard-logout 清除只作用于它；它按 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md) 在 hard logout 时被清除、下次登录轮换,soft recovery 路径保留。§5.2 的**设备身份 key**(`device_public_key` / `verify_key`,签事件 / KeyPackage / MLS leaf)是 E2EE 信任根，只经 `ak.device.revoke` + 重新入册轮换。二者必须独立生成、独立存储并独立轮换：grant-binding key 的私钥字节、公钥字节、JWK thumbprint 与 `kid` 都 MUST NOT 等于或复用设备身份 key 的对应材料。违反该分离要求的会话或设备授权 MUST fail closed。会话生命周期(登录 / 登出 / grant 轮换)MUST NOT 触发设备身份 key 的重铸(见 §5.2)。

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
2. `ak.device.authorize`：由 descriptor 中 `device_public_key` 对 possession transcript 和 Event proof 各自签名；`authorization_binding_kind="registration_anchor"`；`prev_refs` 只能含第一条 create Event id。

identity root 只单向承诺两条 Event 的 payload digest，不承诺 Event id 或 envelope digest。create payload 中的 descriptor 与 authorize payload 必须在 `principal_id`、`device_id`、device/HPKE key、算法集合和 authorize payload digest 上逐字一致。Principal Server 必须验证 event-derived PCR id（`retype(create.event_id)`，见 [`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md)；它不由 principal DID 或 subject 派生）、空 frontier、**账号维度**的 create-once、当前 identity-creation lease fence/expiry 及完整 root/device proofs，然后在一个数据库原子边界内接受两条 Event；任一步失败均零写入。

首设备无需已有设备、账号权威或管理员批准。Account Authority 的 S2S signature 只证明 transport source，不能替代 identity root 或 device proof。

### 5.2 Device possession transcript（normative）

`device_signature` 的 domain **由 `authorization_binding_kind` 判别**，不是单一固定值。该字段有三个取值，各自对应一个 domain 与一个封闭签名对象：

- `registration_anchor`：PCR genesis 的第二条 authorize；domain `ak.device-authorize-possession-proof-v1`，见 §5.2.1。
- `pcr_recovery`：PCR-policy 或显式 DID-root recovery unit 的第二条 authorize；domain `ak.device-authorize-recovery-possession-proof-v1`，并绑定 recovery session/policy/generation。
- `accepted_device`：已有 accepted device 批准新设备；domain `ak.device-authorize-accepted-device-possession-proof-v1`，见 §5.2.2。

三个 domain 都登记在 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)。verifier MUST 先从 payload 的 `authorization_binding_kind` 选定 domain 与成员集合，MUST NOT 尝试其它 domain，也 MUST NOT 接受跨 binding kind 复用的 transcript。

#### 5.2.1 registration/recovery possession transcript（normative）

genesis / recovery 时候选设备自己 author 整个封闭 unit，因此签名对象覆盖完整 authorization core；recovery 分支还必须加入 policy/session/generation binding：

```json
{
  "principal_id": "ak:did_core:webvh:zExamplePrincipalScid",
  "device_id": "ak:device:...",
  "device_public_key": "did:key:...",
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
  "device_public_key": "did:key:...",
  "hpke_key": "z...",
  "algorithms": ["..."],
  "device_key_algorithm": "Ed25519",
  "authorization_binding_kind": "accepted_device",
  "pairing_challenge_transcript_digest": "sha256:..."
}
```

签名输入是 `UTF8("ak.device-authorize-accepted-device-possession-proof-v1\n") || canonical_json(上述对象)`，`canonical_json` 按 [`../conformance/encoding.md` §2](../conformance/encoding.md)（JCS）。`algorithms` 同样必须先按 UTF-8 bytewise 排序去重。该对象没有 optional 成员，因此不存在缺失字段规范化为 `null` 的情形；签名字段、Event id、envelope digest 及其它 proof material 同样不进入该对象。

**`pairing_challenge_transcript_digest` 是本 attestation 唯一的 replay 边界**：它 MUST 逐字节等于本次 pairing 的 `device_pairing_challenge_proof.transcript_digest`（§2.1.2）。单靠这一个成员已经足够，因为该 digest 本身就承诺了整条挑战：

- 路径 A（短链）承诺 `device_pairing_request_id` / `pairing_code` / `gate_audience` / `expires_at` / `server_nonce` / `client_nonce` / `new_device_pubkey_digest`；
- 路径 B（to-device）承诺 `transaction_id` / `request_canonical_digest` / `expires_at` / `gate_audience` / `pairing_code` / `new_device_pubkey_digest`。

因此跨 request（`device_pairing_request_id` / `transaction_id` + nonce）、跨 Account Authority（`gate_audience`）、跨过期窗口（`expires_at`）与换 key（`new_device_pubkey_digest`）的重放全部被阻断，强度与 §2.1.2 的 challenge proof 完全相同；一个为别的配对铸出的 attestation 在本次配对里永远验不过。

从该对象移出的 `principal_id` / `authorized_by` / `not_before` / `expires_at` / `scopes` / `recovery_session_id` 改由**批准设备的 Event proof** 承担：`accepted_device` authorize 的 `proof.verification_method` MUST 使用该授权 Event accepted-at 的 `full_id` 与 method evidence，而不是 current DID resolution；verifier MUST 取其 bare `full_id`，经已登记 method adapter 验证并要求 `project(full_id) == principal_id`，同时要求 fragment 逐字等于 `signing_device_id`，且 `signing_device_id` 必须是 payload.`authorized_by`（§5.3）。实现不得把 `principal_id` core 与 device fragment 直接拼成 DID URL。该 proof 覆盖完整 canonical Event bytes；两个签名合起来覆盖的字段集合不小于 `registration_anchor` / `pcr_recovery` 单签名覆盖的集合。目标设备对 `principal_id` 的确认由 §5.4.1 的装配前强制校验承担。

**wire 形态与载体（normative）**：该 attestation 的 wire 形态是 [`device-pairing.schema.json`](../../artifacts/schemas/device-pairing.schema.json) 的 `device_pairing_target_attestation`（上述七个成员加 `device_signature`）。它与 `challenge_proof` 一样**只走带外通道**——路径 A 的二维码 fragment、路径 B 的 to-device 消息——并且 **MUST NOT 经免认证 stage / resolve 面回传给 server**：暂存面是匿名的，让它持有该 attestation 既无必要也扩大攻击面（§2.1.1 第 2 条的既有隐私边界）。

**它是 `hpke_key` 与 `algorithms` 的唯一权威来源**：`device_pairing_stage_request_body` 与 `device_pairing_bootstrap` 都不承载这两个值，也 MUST NOT 增设镜像字段——让匿名暂存面持有长期设备 HPKE 公钥与设备算法指纹会平白扩大可枚举面，而镜像一个已被签名的值只会制造第二个非权威副本和一处必须 fail closed 的比对义务。批准设备 MUST 先独立验证 attestation 签名，再从**验签通过的 attestation** 读取 `hpke_key` / `algorithms` 填入 authorize payload；MUST NOT 从服务端响应、UI 输入或任何未签名来源取这两个值。服务端因此无法替换它们。

**gate 侧不需要额外 wire 字段（normative）**：`ak.gate.account.command.pair_device` 的请求体不携带该 attestation 对象。Account Authority 从 `authorize_event.event.payload` 的 `device_id` / `device_public_key` / `hpke_key` / `algorithms` / `device_key_algorithm` / `authorization_binding_kind`，加上它**自己按 §2.1.2 重算**得到的 challenge transcript digest，重建上述封闭对象，并用请求携带的 `new_device_pubkey` 验签 `device_signature`。所有 transcript 输入都不来自请求方可自由选择的字段，因此无需也不得接受一个客户端提供的 attestation 副本；重建不符或验签失败 MUST NOT 授权设备。

### 5.3 Event proof key resolution（normative）

所有普通设备 Event 的 `proof.verification_method` MUST 是基于该 principal 已验证、且满足操作 freshness / event-time 要求的 `full_id` 的 DID URL。receiver MUST 取 DID URL 的 bare `full_id`，用已登记 method adapter 验证并要求 `project(full_id) == principal_id`（稳定 `did_core_id`），再要求 fragment 逐字等于完整 `signing_device_id`（`ak:device:<uuid>`）；不得把 fragment 拼到 `principal_id`，也不得把任何 core-plus-fragment 字符串当成 verification method。设备没有独立 DID，因此不得使用 candidate `did:key` 作为该字段。对 `authorization_binding_kind="accepted_device"` 的 authorize，`signing_device_id` 必须是 payload.`authorized_by`，不能是待授权 target device；因此 payload.`authorized_by` 在该分支下必然是设备 id，不是任何 principal DID。

该 Event proof 同时是 `accepted_device` 分支下 `principal_id`、`authorized_by`、`not_before`、`expires_at`、`scopes` 的**唯一签名承载**（§5.2.2）：它覆盖完整 canonical Event bytes，而签名方正是选定这些值的批准设备。验签方 MUST 用它校验这些字段，MUST NOT 期望目标设备的 `device_signature` 覆盖它们。

- 对普通 Event，receiver 从当前 accepted PCR device directory 解析该 method；
- 对 genesis/re-anchor unit 的第二条 authorize，目录尚未包含 candidate。verifier 必须建立只在本次 unit 内可见的 candidate overlay，把规范 method 映射到 descriptor/authorize payload 的 `device_public_key`，先验证 descriptor/payload/digest、possession signature 和 Event proof，全部成功后才原子写入 durable directory；
- 不得查询未接受的 projection，不得回退到同 fragment 的旧 key，也不得在验签前产生可观察目录状态。

### 5.4 后续设备配对（normative）

首设备存在后，新设备必须走 §2 pairing。新设备提供自己的 device/HPKE keys 和 §5.2.2 的 possession attestation；批准方必须是 PCR 当前 generation 中 active、未撤销的 accepted device，并对完整 authorize payload 签名。结果 `authorization_binding_kind="accepted_device"`，`authorized_by` 是**批准设备自己的 `device_id`**（完整 `ak:device:<uuid>`），不是该设备所属 principal 的 DID；authorization evidence 必须能定位批准设备的 accepted authorize Event 与 generation。

服务端可以中继 challenge 和 Event，但不得生成、替换或签署新设备 key material。旧 generation、已撤销或 conflicted device 的批准一律 fail closed。企业额外审批只能作为显式启用的 PCR policy 叠加，不能成为个人账号首次建 PCR 的默认第二方。

#### 5.4.1 目标设备装配前的强制校验（normative）

§5.2.2 的 attestation 不承诺 `principal_id`，所以“目标设备被并进了哪个 principal”不能由目标设备的签名保证，只能由目标设备**事后核对已被接受的授权**保证。因此：目标设备在**完成本地身份装配之前**（即在把该 `device_id` 与 device key 当作某 principal 的成员使用、拉取或安装该 principal 的 E2EE 材料、发布 KeyPackage、写入任何 `ak.self.*` 状态之前），MUST 先取回被接受的那条 `ak.device.authorize` Event 并逐项校验：

1. Event `payload.device_signature` 与自己产出的 attestation `device_signature` **逐字节相同**；
2. `payload.device_public_key`、`payload.hpke_key`、`payload.algorithms` 与自己 attestation 中的对应值**逐字一致**（含 `algorithms` 的排序与去重结果）；
3. `payload.device_id` 等于自己的 `device_id`；
4. `payload.authorization_binding_kind` 为 `accepted_device`；`proof.verification_method` MUST 是该 principal 已验证 `full_id` 下的 DID URL，取其 bare `full_id` 经已登记 method adapter 验证后 MUST 满足 `project(full_id) == payload.principal_id`（稳定 `did_core_id`），且 fragment 逐字等于 `payload.authorized_by`；不得从 principal core 与 device fragment 拼接 verification method；
5. `payload.principal_id` 与用户预期的账号一致——该值 MUST 在装配前显式呈现给用户确认，不得默默采纳服务端给出的任何 principal。

任一项不符，目标设备 MUST fail closed：MUST NOT 使用该身份、MUST NOT 安装或请求该 principal 的任何密钥材料、MUST NOT 发布 KeyPackage，并 MUST 向用户告警（提示该配对已被篡改或指向了非预期账号）。这条校验同样阻断“批准方把 attestation 用到另一个 principal 下”的场景：攻击者可以铸出一条对自己 principal 有效的 Event，但目标设备在装配前就会因第 5 项拒绝。

**取回路径**：`ak.open.device_pairing.read.status`（路径 A）在 `state="authorized"` 时返回 `authorized_event_ref`，是该校验的入口；路径 B 的目标设备从自己发起的 `transaction_id` 关联的授权结果取得同一 ref。目标设备被授权后即已是该 principal 的 accepted device，**读取自己的 PCR 控制流即可取到该 Event 的完整 canonical bytes 与 proof 完成校验**，不需要新增读取面；在完成本节校验之前，该读取是它唯一允许对该 principal 发起的操作。取不到 Event、Event 尚未被 accepted Seal 覆盖、或读取被拒时，MUST 停在 fail-closed 状态并重试/告警，MUST NOT 先装配再校验。

### 5.5 Device trust projection（normative）

设备 trust state 仅由 accepted PCR evidence 决定：registration-anchor genesis、accepted-device authorize、PCR-policy re-anchor、revoke/list update 与 accepted Seal/frontier。DID resolver 不提供设备目录或 generation basis。

远端 receiver 必须取得 `principal_genesis_receipt + authorization_chain + accepted_seal + current_device_projection + range_completeness_evidence`。`authorization_chain` 在此不是只挑成功授权 hop，而是从 genesis 到 current Seal、足以重放目标 projection 的完整相关 PCR control history，包含 authorize/revoke/reanchor/list moves；range-completeness attestation 必须证明该区间没有被 source 隐藏 reducer input。Receiver 自行重放并要求 target status=`active`、`authorized_generation_ref == current_device_generation_ref`、generation status=`active`，再与 current projection逐字段比较。外层 source 对“未撤销”的断言不构成 authority。只有 Event payload、proof 与 evidence 的 principal/device/key/generation/frontier 全部一致时才是 `verified`；缺失、gap、witness disagreement 或 stale evidence保持 `unresolved`，不得 TOFU。

### 5.6 Privacy-Preserving Push

Arkret 推送通道设计的目标是在不向 push gateway / vendor、上游 Principal Server sync surface、网络中间人或第三方 SaaS 控制面泄露身份与可链接信息的前提下，把"有事可投递"的最小信号送达终端。这是 [`discovery/push-notifications.md`](../discovery/push-notifications.md) 与 [`crypto-media/webrtc-signaling.md`](./webrtc-signaling.md) 中"pairwise pseudonym `push_target_id`"语义的协议层定义。

#### 5.6.1 `push_target_id` 派生与作用域

- 作用域：`per (recipient_service_id, principal_id, device_id, push_route)`。`recipient_service_id` 是当前 Realm membership delivery binding 指向的 Principal Server service DID；同一 DID 在个人 Principal Server 与组织 Principal Server 上注册同一物理设备时，MUST 使用互相不可链接的 `push_target_id`。`push_route` 标识同一设备上不同 push 通道（如 `apns_main`, `fcm_voip`, `webpush_default`），允许同一设备针对不同通道发布相互不可链接的伪名。
- 长度：`push_target_id` MUST 至少 128 bit 熵，编码为 base64url（最少 22 字符）；推荐 256 bit。`high_security_organization`、`sovereign_deployment` / `isolated_sovereign_network` 等高安全 deployment profile MUST 使用 ≥ 256 bit 熵（不可链接性是这些场景的硬隐私属性，128 bit 仅为通用下限）。
- 不可推导性：`push_target_id` MUST NOT 由公开 DID、`device_id`、平台 push token、handle、邮箱或电话号码可推导。生成方式 SHOULD 是 device-local 随机；设备 MAY 用本地 secret 与 `push_route` 派生，前提是源 secret 不可被服务端取回。
- 标识形态：典型 wire 形态为 typed ID `ak:pseudonym:push:<base64url>`，由 `id-kind-registry.json` 中 `pseudonym` 项授权使用；也可作为 raw base64url 字符串出现在 `ak.device.push_route` 等 actor-private state event payload 中。

#### 5.6.2 注册与撤销

- 设备 MUST 通过 `ak.device.push_route` actor-private state Event 把 `(recipient_service_id, principal_id, device_id, push_route, push_target_id, push_gateway_service_id, encryption_key, capabilities)` 写入当前投递 Principal Server 可见的 principal control stream 或等价 actor-private state；该 Event 不携带 CBA reducer 字段，不进入 shared Realm Seal coverage。目标 actor-private cell 的 `cell_subject` 由 canonical `contract-registry.json` 的 `event_kind_registry.actor_private_contracts` 声明为 composite `(payload.recipient_service_id, payload.principal_id, payload.device_id, payload.push_route)`，family 使用 `cas_register` 且 `bottom=reject`；schema registry 只负责 payload 形状，不是 merge 真相源。`recipient_service_id` MUST 与 [`governance/member-delivery-binding.md` §2](../governance/member-delivery-binding.md) 接受准则中该 device 所属 member 的 `delivery_binding.recipient_service_id` 一致；推送注册按 `(recipient_service_id, principal, device, push_route)` 维度隔离，同一 DID 在不同 Principal Server 上下文中的 push route 不共享、不可关联。
- 撤销：设备 MUST 在同一 actor-private cell 上写后继 `ak.device.push_route` event 设置 `revoked: true` 或重新写入新 `push_target_id`；service / gateway MUST 在 actor-private state 收敛后停止接受旧伪名。
- 轮换：客户端 SHOULD 在 push token 变化、设备恢复、Out-of-band 重新登录、或自定义 rotation 周期（默认 ≤ 90 天）时轮换 `push_target_id`。
- 长期不可恢复性：服务方在丢弃旧 `push_target_id` 后 MUST NOT 保留可把旧 / 新伪名链接回同一 `(recipient_service_id, principal, device)` 的索引；只允许在 rotation 时短暂保留以便迁移未投递消息。短暂保留期 MUST ≤ 24h，或与单条未投递消息 TTL 取较短者；超过该窗口 MUST 物理删除旧 `push_target_id` 与对应索引材料，不得保留任何能把新旧映射回同一 device 的信息。
- **条数与注册速率上限（normative）**：单一 `(recipient_service_id, principal_id, device_id)` 维度下并存的 active `push_route` 条数 MUST ≤ 16（v1 wire 上限；登记于 [`../conformance/scalability-constraints.md` §6.1](../conformance/scalability-constraints.md)），超过时服务端 MUST 拒绝新 `ak.device.push_route` 注册（`push_route_limit_exceeded`）。同一维度的 push-route 注册 / 轮换 MUST 限速，默认窗口 60s 内 ≤ 8 次写入；超额时返回限速响应并记内部审计 `push_route_registration_rate_limited`。该上限防止单设备通过无界 push_route 放大注册状态或制造可链接性面。

#### 5.6.3 不可链接性要求

- 同一 `principal_id` 在不同 `recipient_service_id`、不同设备或不同 push route 上的 `push_target_id` MUST NOT be linkable by push gateway / 第三方 transport（除非两侧自愿持有相同源 secret）。受托 Principal Server sync surface MAY 在自己的授权上下文内持有从成员 delivery binding 到本服务本地 push queue 的短期索引，但不得把该索引导出给 Push Gateway / vendor。
- 同一设备的两条 `push_route` 的伪名 MUST 互相独立；其中一条被泄露不得让攻击者推导另一条。
- 跨 Realm 投递 MUST 使用同一 `push_target_id`（按 device 而非按 Realm），但 push payload 内不得携带 plaintext `realm_id`/`strand_id`/`message_id`；目标拆分由 device 端解 envelope 后完成。

#### 5.6.4 Push Payload 形态

- 协议层 push payload MUST 视作 `encrypted-envelope.schema.json` 形态或等价 ephemeral encrypted blob。AAD MUST NOT 包含可链接 wire 字段，仅可携带 routing-only `wakeup_kind`（参见 `discovery/push-notifications.md`）。
- gateway / vendor MUST NOT 解密 payload。任何"丰富推送"扩展（如显示发件人）都属于 vendor-side 行为，需要 Realm 与 device 双方明确 opt-in，并对应单独的 plaintext-visible service profile，不在 v1 默认互操作范围。

#### 5.6.5 与其它子系统的边界

- Principal Server sync surface：以 `push_target_id` 作为 push fanout 索引。被 member delivery binding 授权的 Principal Server MAY 在运行时持有 `recipient_service_id + principal_id + device_id + push_route -> push_target_id` 映射以完成投递；该映射不得暴露给 Push Gateway / vendor，日志、导出、法定披露和跨服务复制 MUST 脱敏或失效化。未被该 Realm membership / service binding 授权的服务不得保留可逆映射。
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
| `message_id` | `id:device_message` | required | 发送方为一个逻辑消息分配的稳定 UUIDv7 typed ID；服务端在重试、分页和重投时 MUST 原样保留。接收端统一按 `(sender_principal_id, sender_device_id, message_id)` 去重。 |
| `kind` | `string` | required | 消息 kind，例如 `ak.key.verification.request`。标准 to-device kind 由 `device-message.schema.json` 的闭合 dispatch 定义，不得登记成 Event.kind。 |
| `sender_principal_id` | `did` | required | 发送 principal。 |
| `sender_device_id` | `id:device` | required | 发送设备。 |
| `recipient_principal_id` | `did` | required | 接收 principal；MUST 等于投递路径中的目标 principal。 |
| `recipient_device_id` | `id:device` | required | 接收设备；MUST 等于投递路径中的目标设备。 |
| `sent_at` | `datetime` | required | 发送时间。 |
| `expires_at` | `datetime` | required | 队列过期时间；不得晚于该 kind/profile 声明的 TTL 上限。 |
| `content` | `object` | required | 类型相关内容；私密内容 SHOULD 端到端加密。 |
| `device_proof` | `proof` | optional | 传输认证不能覆盖的场景 MAY 带 detached device proof。 |

`message_id`、`recipient_principal_id` 和 `recipient_device_id` MUST 被签名、device proof 或加密 AAD 覆盖。发送接口使用 `messages.{principal_id}.{device_id}` 做批量路由时，服务端在入队前 MUST 把发送请求的 `message_id` 与路径目标复制进 `DeviceMessageEnvelope`，且接收端 MUST 拒绝 envelope 目标与当前登录设备不一致的消息。

发送方 MUST 在第一次构造逻辑消息时分配 `message_id`，应用重试、HTTP batch 重试和服务端重投都 MUST 沿用该值；重新分配 ID 表示新的逻辑消息，接收端 MUST 独立处理。服务端 MUST 以 `(sender_principal_id, sender_device_id, message_id)` 维护至少覆盖队列 TTL 与短 grace period 的幂等记录：相同 canonical target intent 重试返回既有入队结果且不得新增队列项；同 key 但 `kind`、recipient、`expires_at` 或 `content` 不同，MUST 以 `duplicate_conflict`（reason `message_id_conflict`）拒绝整个发送请求且不得入队任一冲突版本。canonical target intent 是 `{message_id, kind, sender_principal_id, sender_device_id, recipient_principal_id, recipient_device_id, expires_at, content}` 的 canonical JSON；不含服务端物化的 `sent_at`、`unsigned` 或 HTTP `Idempotency-Key`。

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
| `messages.{principal_id}.{device_id}.message_id` | body | `id:device_message` | required | 发送方分配的稳定逻辑消息 ID；服务端 MUST 原样复制到 `DeviceMessageEnvelope.message_id`。 |
| `messages.{principal_id}.{device_id}.kind` | body | `string` | required | to-device 消息 kind，例如 `ak.key.verification.request`。 |
| `messages.{principal_id}.{device_id}.expires_at` | body | `datetime` | required | 队列过期时间；服务端物化 envelope 后必须复制到 `DeviceMessageEnvelope.expires_at`。 |
| `messages.{principal_id}.{device_id}.content` | body | `object` | required | 消息内容；私密内容 SHOULD 端到端加密。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `ok` | `boolean` | required | 请求是否被**接受处理**（见下 partial-success 规则）。 |
| `delivered` | `object` | optional | 已入队或已投递设备摘要。 |
| `unknown_devices` | `object` | optional | 无法识别或不可投递的设备。 |

**Partial-success / 全局失败语义（normative）**：

- **整体拒绝**（请求级失败：认证 / 授权失败、`Idempotency-Key` 冲突、所有目标 envelope 缺 `expires_at` / 已过期 / 超 TTL 上限、body 非 canonical）MUST 走 HTTP 错误响应（4xx，按 [`../sync/api-conventions.md`](../sync/api-conventions.md) error envelope），**不**用 `ok=false` 表达；此时不入队任何消息。
- **部分成功**（请求被接受、至少一个目标被处理，但部分设备落入 `unknown_devices`）：`ok` MUST 为 `true`——`ok` 表达"请求已被接受并逐设备处理"，而非"全部设备均成功"。逐设备结果由 `delivered` / `unknown_devices` 表达。
- **覆盖关系**：`delivered` 与 `unknown_devices` 的设备集合 MUST 互不相交，且其并集 MUST 等于请求 `messages` 中的全部 `(principal_id, device_id)` 目标全集（每个目标恰好出现在二者之一）。consumer 据此可断言无目标被静默丢弃。
- 单设备因 TTL / `expires_at` 等可投递性原因不可入队时，该设备 MUST 计入 `unknown_devices`（携带可投递性失败语义），不使整请求失败。

请求示例（非完整 schema）。`messages.{principal_id}.{device_id}` 的 `{device_id}` 是**收件设备**地址,`content.from_device` 是**发送设备**(MUST 等于 envelope `sender_device_id`,见 §10.1),二者为不同设备，故 UUID 不同：

```json
{
  "messages": {
    "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com": {
      "ak:device:01964137-0000-7000-8000-000000000000": {
        "message_id": "ak:device_message:01964137-1000-7000-8000-000000000000",
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
        "message_id": "ak:device_message:01964137-1000-7000-8000-000000000001",
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
            "device_public_key": "did:key:z6Mk...",
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

`new_device_pubkey` MUST 是 canonical `PublicKey`（[`public-key.schema.json`](../../artifacts/schemas/public-key.schema.json) 的 `kty` / `kid` / `algorithm` / `key` 四字段）；旧的 `{kid, alg, public_key}` 写法不是 v1 wire，MUST `schema_violation`。`target_attestation` 是 §5.2.2 的 `device_pairing_target_attestation`，与路径 A 共享同一 schema 和同一 domain；它是本路径下 `hpke_key` 与 `algorithms` 的唯一权威来源，**只经该 to-device 消息到达**，MUST NOT 经免认证 stage / resolve 面回传给 server。接收旧设备 MUST 把 `purpose`、`pairing_code`、`new_device_pubkey.kid`、`challenge_proof.transcript_digest`、`gate_audience` 和 `request_canonical_digest` 纳入用户确认与 SAS/QR transcript 绑定，并 MUST 按 §2.1.2 的 `ak.device-pairing.challenge.to_device.v1` transcript 独立重算并验签 `challenge_proof`，**再按 §5.2.2 独立重建并验签 `target_attestation`**（`device_id` 等于 `new_device_pubkey.kid`、`device_public_key` 与 `new_device_pubkey.key` 解码为同一 Ed25519 key、`pairing_challenge_transcript_digest` 逐字节等于自己刚重算的 `transcript_digest`）后才可继续；不得只因收到该请求就把新设备标记为 trusted，也不得从消息中未经验签的字段取 `hpke_key` / `algorithms`。同一 pairing 向多台 sibling 广播时，每台收到的都是同一份 attestation：它不绑定任何 `authorized_by`，因此不需要预知 winner；实际成为 `authorized_by` 的是最终提交 gate 并被受理的那台设备。`pairing_code` MUST 是 8 位 Crockford-style 大写字母数字串（字符集 `[A-HJ-NP-Z2-9]`，拒绝易混字符），由 CSPRNG 的 40 个均匀随机 bit 直接编码；它只在短 TTL、单次使用、audience-bound transcript 内有效。用户确认后，旧设备通过 `ak.gate.account.command.pair_device` 完成授权落地；本规范不定义 `/_arkret/self/devices/pairing-requests*` 作为授权批准接口。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->

服务端 MUST 同时执行请求级 `(sender, Idempotency-Key)` 幂等与上述消息级 `(sender_principal_id, sender_device_id, message_id)` 幂等；前者识别同一批 HTTP command，后者识别跨批次、跨连接的同一逻辑消息。已投递消息的队列删除只由接收设备的显式确认（`ak.self.device_messages.command.ack`，见下文与 [`client-sync.md` §10.1](../sync/client-sync.md)）驱动；sync cursor 推进 MUST NOT 触发删除。To-device 消息 SHOULD 端到端加密；未加密消息只能用于能力发现和验证引导。

若 `content` 已端到端加密，加密 AAD MUST 至少覆盖发送方在密封前已知且不可由队列服务物化的 `message_id`、`kind`、`sender_principal_id`、`sender_device_id`、`recipient_principal_id`、`recipient_device_id` 和 `expires_at`。`sent_at` 由队列服务入队时物化，不得进入发送方构造的通用 AAD；具体 kind MAY 增加发送前已知的业务关联字段。队列服务不得重写已进入 AAD 的字段。`Idempotency-Key` 是 HTTP 层语义，不进入 envelope，也不参与 AAD。

接收接口：

```http
GET /_arkret/self/device_messages?after=<cursor>&limit=<n>
Authorization: Bearer <token>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前接收设备。 |
| `from` | query | `cursor` | optional | 上次同步位置（stream cursor）。 |
| `limit` | query | `int` | optional | 返回数量上限；服务端 MUST enforce 最大值。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `messages` | `object[]` | required | 当前设备可见的 to-device 消息（`DeviceMessageEnvelope[]`，不是 Event Envelope）。 |
| `ack_token` | `string` | optional | `messages` 非空时 MUST 返回。覆盖本页及之前所有已投递消息的不透明确认令牌；客户端持久化处理完成后回传给 `ak.self.device_messages.command.ack`。语义见 [`client-sync.md` §10.1](../sync/client-sync.md)。 |
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
| `ok` | `boolean` | required | 确认是否被接受（含旧令牌 no-op 的情况）。 |
| `pruned_count` | `int` | optional | 本次实际删除的消息数。 |

确认语义（normative，完整定义见 [`client-sync.md` §10.1](../sync/client-sync.md)）：确认是累计且单调的——服务端删除令牌覆盖位置（含）之前的全部已投递消息；重复 ack 或 ack 旧令牌返回 `{ok: true}` 且不得回退确认位置（天然幂等，无需 `Idempotency-Key`）。unknown / 过期 / cross-binding 令牌 MUST 返回 `invalid_param`（reason `invalid_ack_token`）且 MUST NOT 删除任何排队消息。客户端 MUST 在该批次密钥材料 / verification transcript / secret **持久化落盘之后**才 ack；未 ack 的消息在重连时由服务端重新投递，客户端 MUST 先按 `(sender_principal_id, sender_device_id, message_id)` 查询 durable 去重记录：已成功持久化的消息不得再次执行副作用，但仍计入连续完成位点并允许累计 ack。kind-specific `transaction_id` / `request_id` 只用于业务 transcript 关联，不得替代 envelope 级去重键。

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

`keys/upload` 的 `device_signature` 由该设备的**设备身份 key**(event-signer 的 Ed25519 `did:key`，即 §5.2 `device_public_key` 对应私钥)对本次上传批次签名，绑定 `device_id` 与所上传的 OTK / fallback 批次。canonical 签名输入：

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
- `device_signature.kid` MUST 指向该设备身份 key；服务端 MUST 用该设备权威 `device_public_key`(§5.2)验签，失败 MUST 拒绝上传（`invalid_param`）。

`POST /_arkret/self/keys/query` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `device_keys` | body | `object` | required | principal DID 到 device ID 列表的映射。 |
| `timeout_ms` | body | `int` | optional | 查询等待上限。 |

服务端在处理 `keys/query` 时 MUST 先认证 requester，并且 MUST 仅在 requester 与被查询 `principal_id` 之间存在当前有效的授权关系时返回目录记录：至少同属一个 requester 可见且 requester 仍为 `join` 的 Realm，或存在当前 call/session/contact profile 明确定义的共享上下文。否则 MUST 使用与不存在不可区分的失败形态（省略该 `(principal_id, device_id)` 记录或写入 `failures` 的非枚举性失败），不得让任意已登录用户枚举其它 principal 的设备存在性 / 吊销状态。

响应字段：`device_keys: object` required；`failures: object` optional。`device_keys` 的每个 `(principal_id, device_id)` 记录为 `query_device_record`：prekey bundle 收在 `algorithms`(算法名 → key_record)子字段下，并在**与 `algorithms` 同级**携带设备验签公钥目录字段 `device_signing_key` 与 `device_status`(见下方 §8.2)。schema 见 [`keys-operations.schema.json`](../../artifacts/schemas/keys-operations.schema.json) 的 `$defs/query_device_record`。

#### 8.2 设备验签公钥目录（normative）

`keys/query` 的 device row 必须返回 `principal_id`、`device_id`、`device_signing_key`、`hpke_key`、`algorithms`、`device_authorize_event_id`、`authorized_generation_ref`、lifecycle status 以及可独立验证的 PCR authorization evidence。设备 row 不得回显 DID Document 的设备或 service authority。

receiver 必须验证：

1. `principal_genesis_receipt` 覆盖 root-signed PCR create 与 founding authorize；
2. authorization chain 从该 founding state，经 accepted-device authorize 或 PCR-policy re-anchor，到目标 `device_authorize_event_id`；
3. accepted Seal 覆盖链的当前 frontier，device 未 revoke/conflict，`authorized_generation_ref == current_device_generation_ref`；
4. row 的 signing/HPKE key 与 authorize payload 逐字一致。

缺失、stale 或冲突证据时不得返回可用于 E2EE/Signal 验签或 KeyPackage claim 的 active key。普通 Event proof method 继续按 §5.3 解析：它是基于已验证 principal `full_id` 的 DID URL；receiver 取 bare `full_id` 经 adapter 验证并要求其投影等于 actor/principal `did_core_id`，再要求 fragment 逐字等于 `device_id`，不得从 actor core 拼接 fragment。

#### 8.3 客户端独立验证（normative）

客户端不能把服务端裸 `device_signing_key` 断言当作 Tier-2 信任。它必须从 identity-root anchored PCR genesis/re-anchor 开始重放 device authorization chain，并检查 generation fence、revocation 和 Seal coverage。验证只需要在 evidence/frontier 更新时完成；普通消息热路径可使用按 `(principal_id, device_id, authorized_generation_ref, seal_ref)` 缓存的 verified projection，不需要在线解析 DID。

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
| `principal_id` | `did` | required | KeyPackage 所属 principal。 |
| `device_id` | `id:device` | required | KeyPackage 所属设备。 |
| `key_packages` | `object[]` | required | MLS KeyPackage 与 metadata；每项 MUST 带 unique `keypackage_id` 和 `keypackage_ref`。 |
| `device_signature` | `signature` | required | 当前设备签名，MUST 链接到 PCR current accepted-device 投影中的规范设备 method。 |

### 9.0 KeyPackage 写路径签名 transcript（normative）

`upload`、`consume` 与 `revoke` 的 detached signature MUST 使用本节唯一的 byte-exact canonical input。普通 device 与独立 Native Agent runtime 使用完全相同的 canonical bytes；身份分支只决定验签所用的 current accepted key 与落库 trust binding，不得改变 domain、字段集合或缺省规则。Rust 实现 MUST 复用 `arkret-rust-sdk` 的共享 typed canonical helper；其它语言实现 MUST 使用与本节闭合 typed request projection 等价的 canonical helper，并通过本节登记的 byte-exact conformance vector。任何实现都不得从开放 JSON value、本地 principal 类型或 HTTP handler 参数临时拼装 transcript。

三条 batch signing input 分别为：

```text
UTF8("ak.self.keys.keypackages.upload.create\n")
+ JCS(upload request 删除顶层 device_signature，并删除每个 key_packages[] entry 的 device_signature)

UTF8("ak.self.keys.keypackages.command.consume\n")
+ JCS(consume request 删除 signature)

UTF8("ak.self.keys.keypackages.command.revoke\n")
+ JCS(revoke request 删除 signature)
```

JCS 对象保留 typed request 中所有 required 字段，并只保留 wire body **实际存在**的 optional 字段。缺省字段必须省略；producer 不得把缺省改写成 JSON `null`。SDK DTO 以 `skip_serializing_if` 省略的空 optional collection 同样不进入 transcript。domain separator 后直接拼接 JCS bytes，不插入空格、额外换行、BOM 或 NUL terminator。

upload 顶层 `device_signature` 始终 required，是整个 request 的 authoritative batch authorization。每个 `keypackage_upload_entry.device_signature` 是 optional defense-in-depth signature；其 signing input 为：

```text
UTF8("ak.self.keys.keypackages.upload.create\n")
+ JCS({
     "principal_id": <request principal_id>,
     "device_id": <request device_id>,
     "key_package": <该 entry 删除 device_signature>
   })
```

entry signature 不覆盖、替代或降级 batch signature。batch signature 无效时整个 request MUST 在任何 KeyPackage 状态写入前拒绝。batch 有效但 present entry signature 无效时，只能拒绝对应 entry；entry signature 缺省时，已验证的 batch authorization覆盖该 entry。接收方不得尝试 `ak.keypackage-upload-v1`、只覆盖 `{device_id,key_packages}` 的旧 transcript或任何实现私有 fallback。

签名算法 v1 为 Ed25519；`signature.alg` MAY 使用注册别名 `Ed25519`，`signature.kid` MUST 指向同一 accepted signing key。普通 device 从 current accepted PCR device authorization projection 解析该 key；Native Agent 从 current accepted `ak.agent.key.authorize.verification_method` 解析该 key，并且该 key MUST 同时等于 MLS LeafNode signature key。三条 batch 签名与 present entry 签名都必须在解析或改变 KeyPackage 状态前验证。

upload、consume、revoke 的 byte-exact正向与负向向量由 `ak.vector.crypto.keypackage_write_transcripts.v1` 固化。SDK helper输出与该 fixture不一致时实现 MUST fail closed；不得以当前 server或client实现为兼容依据。

### 9.0.1 Self claim requester proof 与重放闭包（normative）

`ak.self.keys.keypackages.command.claim` 是同一 KeyPackage authority 内的领取面，但 bearer/session 身份本身不能替代对具体领取意图的签名授权。request MUST 携带单数 `holder_acceptance_proof` 并验证 `keypackage-operations.schema.json#/$defs/keypackage_claim_proof`。v1 不定义 quorum、hybrid 或“任一通过”语义；这类能力必须由未来单独定义的新 request schema 承载。缺失该字段、出现任何未声明 proof 容器、proof 对象开放、携带 `domain`、purpose 非 `holder_acceptance` 或 `audience` 非 DID，都必须在选择 KeyPackage 前拒绝。

先从闭合 request 删除顶层 `holder_acceptance_proof`（不是置为 `null`），保留所有实际存在的 optional 字段，计算 `payload_digest = SHA-256(JCS(request_without_holder_acceptance_proof))` typed digest。proof `payload_digest` MUST 与之 byte-identical；detached JWS 的 payload segment MUST 为空，并对下列唯一 canonical binding object 的 JCS bytes 签名：

```json
{
  "context": "ak.keypackage-claim-request-proof-v1",
  "payload_digest": "<proof.payload_digest>",
  "requester": "<request.requester>",
  "target_principal_id": "<request.target_principal_id>",
  "intended_realm_id": "<request.intended_realm_id>",
  "claim_nonce": "<request.claim_nonce>",
  "verification_method": "<proof.verification_method>",
  "created_at": "<proof.created_at>",
  "proof_purpose": "holder_acceptance",
  "audience": "<receiving KeyPackage authority service DID>"
}
```

proof `kind` MUST 为 `detached_jws`，`audience` MUST byte-identical 于实际接收并持有 KeyPackage 池的 authority service DID，不得使用 HTTP Host、URL 或 caller 自选值；JWS protected `alg`、proof `alg` 与解析到的 key algorithm 必须一致，禁止逐 key/逐算法 fallback。首次改变 KeyPackage 状态时，`created_at <= verifier_now + 60s`、`created_at < request.expires_at <= created_at + 300s` 且 `verifier_now < request.expires_at`；非 canonical timestamp、过期或未来时间都在 inventory lookup/CAS 前 fail closed。

verification method 的 DID controller MUST 等于 `requester`，并按 requester 的已接受身份唯一解析：普通 principal 使用 current accepted、未撤销且属于 active generation 的 device signing key，且 authenticated session 的稳定 `device_id` 必须匹配；Native Agent 使用 current accepted `ak.agent.key.authorize.verification_method`，且 session 的 Agent/device 绑定与 MLS endpoint 必须匹配；service requester 使用该 service DID 的 current assertion method，并且 service delegation/capability 必须覆盖本 operation。普通 device proof、Agent proof 与 service proof 不能相互替代。该 proof 也不能替代 RFC 9421/DPoP sender-constrained transport authentication、target consent/contact/capability/policy 检查，或后续 MLS `payload.claim_envelope` 的独立签名绑定。

`claim_nonce` MUST 是 22..128 字符无 padding base64url，携带至少 128 bits CSPRNG entropy，并与 `requester` 组成 self claim 的 protocol object identity。authority MUST 以 `(requester, claim_nonce)` 建唯一 ledger，在同一原子事务/线性化点写入 `payload_digest`、KeyPackage `published -> claimed` CAS（或 last-resort claim record）和 byte-exact terminal outcome：

- 同一 identity、同一 `payload_digest` 的重试返回第一次的 byte-identical outcome（包括当时的 `available_count`），不得再次选包或推进状态；
- 同一 identity、不同 `payload_digest` 必须在 inventory lookup/CAS 前 fail closed，外部保持统一 `claim_failed`，内部审计 `duplicate_conflict`；
- 首次收到时 request 已过期且 ledger 不存在，必须拒绝且不得创建 claim；已有 terminal ledger 的读取仍须当前有效、与 `requester`/device/service 绑定一致的 sender-constrained authentication，绝不能让 proof 历史有效性绕过当前 revoke/pause/deactivate；
- terminal outcome 与 digest ledger MUST 至少保留到全部返回 claim 已进入 `consumed`/`revoked` terminal state，且不得早于 `request.expires_at + 24h`。清理完整 outcome 后仍必须保留到 request 已不可能重新通过 freshness gate 的 nonce tombstone；重放永远不能创建第二次 claim。

因此 operation registry 的本 operation 使用 `idempotency_mechanism=object_id`、`retry_safe=true`；调用方在不确定结果后重试同一 request identity，而不是换 nonce 重新领取。此 ledger 只闭合 transport/result uncertainty，不改变一次性 KeyPackage 每份最多一次 `published -> claimed` 的状态机约束。正负路径由 `ak.vector.keypackage.self_claim_authorization_idempotency.v1` 固化。

`claim` 请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `target_principal_id` | `did` | required | 被邀请或加入的 principal。 |
| `target_device_ids` | `array<id:device>` | optional | 为空时由服务选择可用设备。 |
| `intended_realm_id` | `id` | required | 目标 Realm。 |
| `requester` | `did` | required | 发起 claim 的 actor 或 service DID。 |
| `required_capabilities` | `string[]` | required | 需要的 content / MLS / policy profile。 |
| `minimal_metadata_allowed` | `boolean` | optional | 是否允许 pseudonymous credential。 |
| `claim_nonce` | `string` | required | 至少 128-bit CSPRNG entropy；与 `requester` 组成 claim object identity 和原子幂等 ledger key。 |
| `expires_at` | `datetime` | required | claim 有效期。 |
| `holder_acceptance_proof` | `keypackage_claim_proof` | required | 唯一 requester `holder_acceptance` detached-JWS proof，完整语义见 §9.0.1；peer surface 不复用此字段，而使用 §9.2 的闭合 `requester_authorization`。 |

`claim` 响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `claims` | `object[]` | required | 每个 claimed KeyPackage 的 `claim_id`、`keypackage_ref`、`keypackage_digest`、device binding、expiry、capabilities 和 `capabilities_digest = sha256(JCS(capabilities))`。 |
| `failures` | `object[]` | optional | 不可领取设备与原因；不得泄露不可见用户或设备。 |

`consume` request MUST validate `schemas/keypackage-operations.schema.json#/$defs/key_packages_consume_request_body`，并由 Welcome 接收方或授权发送方在 Welcome 成功处理且新的 MLS group state 已 durable 持久化后调用，绑定 `key_package_refs[]`、`signature`、可选 `claim_ids[]`、`welcome_ref`、`realm_id`、`strand_id`、`mls_group_id`、`epoch`，以及 closed consumer XOR：human device 仅携 `consumer_device_id`；Native Agent 仅携 `consumer_agent_id + consumer_agent_verification_method + consumer_agent_key_authorize_event_id`，不得伪装成 `ak:device`。嵌入的 `recipient_mls_durable_receipt` 使用同一 closed signer XOR，不携 signer-evidence sidecar。consume admission MUST 逐字绑定 consume signer、durable receipt、Welcome recipient、exact claim record、KeyPackage signer与 authorization Event。若持久化失败，runtime MUST NOT 调用 consume；若 consume响应丢失，必须以同一 signed typed request幂等重试。服务端 MUST 把与首次成功 consume 完全相同的重试作为成功返回，不得因 KeyPackage 已进入 `consumed` 而返回失败。对于 Direct Conversation，只有在 request 精确匹配该 `pair_key` 的唯一 immutable binding、accepted Welcome、claim、recipient principal、closed recipient signer、Realm、Strand、MLS group 与 epoch 后，服务端才可在 terminal KeyPackage row 已清理或不可用时把该重试视为幂等成功；任何字段不同仍 MUST fail closed。实现 SHOULD 保留足够的 terminal consume ledger，使幂等判断不依赖 inventory row 的生命周期。`revoke` request MUST validate `#/$defs/key_packages_revoke_request_body`，可由设备、principal controller 或 policy授权服务发起。

规则：

- 对普通 single-use KeyPackage，`claim` MUST 原子地把 KeyPackage 从 `published` 转为 `claimed`。协商启用的 `last_resort=true` 包是唯一例外：包本身保持 `published`，每次领取只追加独立 `keypackage_claim_record`（见 [`encryption-and-audit.md` §2.6.2](./encryption-and-audit.md)）。
- 同一 `keypackage_ref` 不得被多个 active claim 使用。
- 过期、撤销、设备被移除或 principal control state 失效时，服务 MUST NOT 返回该 KeyPackage。
- **`required_capabilities` ⊆ KeyPackage `capabilities`（normative subset rule）**：claim request 中的 `required_capabilities` 集合 MUST 是被领取 KeyPackage 上声明的 `capabilities`（见 [`encryption-and-audit.md` §2.6 KeyPackage payload](./encryption-and-audit.md)）的**子集**。任何 `required_capabilities ∖ capabilities ≠ ∅` 的 claim MUST 被服务端拒绝（与其它 claim 失败一致使用统一不透明错误码 `claim_failed`，但服务端 SHOULD 在内部审计日志中记录 `keypackage_capability_overreach` 以便滥用检测）。该规则避免了"客户端在 claim 时声明超过 KeyPackage 实际声明的能力，使后续 Welcome / Commit 在错误能力假设下进行"的隐性越权。
- Device / Key Server 在 claim 成功响应中返回的每条 claim MUST 包含 `keypackage_digest = canonical_digest(KeyPackage bytes)`、`capabilities_digest = sha256(JCS(capabilities))`，并携带 claimed 设备的 trust binding。普通 device 携带该设备 accepted `ak.device.authorize` 的 `device_authorize_event_id`；Native Agent 携带当前 accepted `ak.agent.key.authorize` 的 `agent_key_authorize_event_id`。两者 MUST 精确二选一。`ak.mls.welcome` MUST 回填同一 KeyPackage hash 到顶层 `payload.keypackage_digest` 和 `payload.claim_ref.keypackage_digest`，回填同一 digest 到 `payload.claim_ref.capabilities_digest`，并把 claim record 的 trust binding 原样回填到 `payload.claim_ref`；Welcome 接收端在解密前必须比对这些值与本地 claim 记录，并确认该 trust binding 仍指向 claimed device/Agent 当前 accepted state，防止 group manager 或中间服务替换 KeyPackage、扩大能力集合或复用旧 authorization。
- `payload.claim_envelope` 是 requester 对本次 Welcome 的独立签名 transcript，签名身份绑定 requester 而不是被 claim 的 endpoint。普通 principal requester MUST 携带 `requester_device_id` 与 `device_authorize_event_id`，并用该设备当前 accepted `ak.device.authorize.payload.device_public_key` 签名；Native Agent requester MUST 携带 `requester_agent_id + requester_agent_verification_method + requester_agent_key_authorize_event_id`，并用所声明的 active Agent key 签名，禁止携带或借用 `requester_device_id`。两者 MUST 精确二选一。服务端和接收端 MUST 校验 envelope 的 requester identity、closed endpoint、authorization ref、signature `kid` 与当前未撤销投影一致；不得把 recipient KeyPackage 的 authorization ref 当作 requester 签名身份使用。
- 每个成功 Welcome 必须且只能携带 `self_claim_receipt` 或 `peer_claim_receipt`。self claim outcome 必返 authority-signed `self_keypackage_claim_receipt`：`operation_id=ak.self.keys.keypackages.command.claim`、`claim_request_id=request.claim_nonce`、`request_digest` 覆盖含 holder proof 的完整 exact request、`claims_digest` 覆盖 exact claims、`source_service_id=destination_service_id=current authority`。Native Agent `current_observation` 必须从所选 receipt 唯一派生并逐字相等：`operation_id=receipt.operation_id`（peer 为 `ak.peer.keys.keypackages.command.claim`）、`request_digest=receipt.request_digest`、`verifier_id=destination_service_id`、`audience=source_service_id`、`challenge=claim_request_id`（self 即 claim_nonce）。接收端不得用 evidence 内自报 observation 替代 receipt 导出的 expected context。
- `claim` 失败响应 MUST 对不存在、不可见、无可用设备和 policy denied 做反枚举处理。对外错误码合并为单一不透明错误码 `claim_failed`：通用部署 SHOULD 合并，**声明 `ak.profile.e2ee_client.v1` 的服务端 MUST 合并**——即在 `e2ee_client` profile 下，subset-rule 违反（§上条 `keypackage_capability_overreach`）、不存在、不可见、无可用设备、policy denied、过期 / 撤销等**所有**失败原因 MUST 对外返回同一 `claim_failed`，不得让 subset-rule 违反与其它失败产生可区分响应，否则攻击者可借响应差异探测目标 KeyPackage 的 capability 指纹（哪些 capability 被声明 / 未声明）。任何 profile 下都不得返回可区分失败原因的 error message。服务端 SHOULD 使用统一状态码、最小响应体、限速和延迟填充降低时序侧信道；实现不得故意让不同失败原因产生稳定可测的响应差异。
- 设备 SHOULD 维持 `keypackage_min_available` 低水位，默认 8。Device / Key Server 的 **self / owning-device 可见** upload、claim 或 maintenance query 响应 SHOULD 返回 `available_count`；peer claim / outcome-query MUST NOT 返回该字段。客户端发现可用 KeyPackage 低于低水位时，MUST 在下一次 sync / device maintenance 周期补充上传，避免邀请路径因耗尽而失败。
- claimed 但未 consume 的 KeyPackage 到达 claim `expires_at` 后 MUST 转为 revoked / unusable 状态；服务不得把它自动放回 `published`，也不得接受迟到的 consume。设备需要重新发布新的 KeyPackage。
- Device / Key Server MUST 维护过期扫描或等价触发：KeyPackage `expires_at`、claim `expires_at`、device revoke、principal control state 失效、capability revoke 或 Realm policy 变更任一发生时，后续 `query` / `claim` MUST NOT 返回该 KeyPackage；后台清理不得是唯一防线。扫描周期 SHOULD ≤ 60s，且每次 `claim` 路径必须先做同步 freshness 判定。
- KeyPackage claim MUST 对 `(requester_service_id, target_principal_id)` 做限速，默认窗口为 60s 内最多 5 次 claim 尝试。超过限额时对外仍使用反枚举响应（`claim_failed` 或通用 rate-limited envelope，不泄露目标存在性）；服务端内部审计 reason 记录为 `keypackage_claim_rate_limited`。
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
| `ak.peer.keys.keypackages.command.claim` | `POST /_arkret/peer/keys/keypackages/claim` | `peer_key_packages_claim_request_body` / `peer_key_packages_claim_outcome` |
| `ak.peer.keys.keypackages.read.claim` | `POST /_arkret/peer/keys/keypackages/claims/query` | `peer_key_packages_claim_query_request_body` / `peer_key_packages_claim_query_outcome` |

目标 KeyPackage authority 是 `published → claimed` 的**唯一 CAS 权威**。来源服务只能请求领取并验证目标服务签发的 receipt；不得在本地镜像池上先行标记、推测成功，或用 `ak.peer.events.command.submit` 替代该原子操作。claim 成功只是生成 MLS Welcome 的必要前置条件，不创建 Realm、membership、Strand 或 binding；这些 durable facts 仍必须由其规范 Event 与原签名 proof 创建并经 peer Event / principal-fact 通道投递。

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
     "request": "<the exact claim_authorization_draft.request object>",
     "transport_binding": {
       "destination_service_id": "<Destination-Service-ID>",
       "destination_trust_domain": "<Destination-Trust-Domain>",
       "source_service_id": "<Source-Service-ID>",
       "source_trust_domain": "<Source-Trust-Domain>"
     }
   }
   ```

   上例是 `kind=device` 分支。`claim_authorization_draft` MUST 是闭合的 `{request, transport_binding}` 对象；`transport_binding` 明确携带 `source_service_id`、`destination_service_id`、`source_trust_domain` 与 `destination_trust_domain`。客户端 MUST 对 resolver 返回的这些值作 UI / account-context 一致性校验后原样签名，MUST NOT 从本地 endpoint 配置猜测或替换它们。`signature.kid` MUST 等于 `verification_method`。`requester_authorization` 是 closed XOR：human principal 必须且只能携带 `kind=device + requester_device_id + device_authorize_event_id`，并由该 accepted、未撤销设备的 `device_public_key` 签名；Native Agent 必须且只能携带 `kind=native_agent + requester_agent_id + agent_key_authorize_event_id`，并由 accepted current Agent runtime method 签名。Agent id、verification method 与 authorization Event 必须逐字绑定 current AgentSignerEvidence、claim requester、repair author actor 与随后生成的 MLS Event/KeyPackage signer，且不得借用 `ak:device` 身份。目标服务 MUST 独立解析对应 authority chain，不得信任来源服务对 participant key 的裸断言。

   客户端/Agent runtime 签名后，来源 Principal Server MUST 在本地验证 account pair、当前 device/runtime authorization、generation 与 revoke/pending 状态，再签发 peer command。body 不携带 PCR/device/Agent signer history sidecar；目标服务验证 authenticated source service、request transcript 与来源服务签名。该 service attestation 提供可验证归责，不声称在密码学上阻止恶意 Principal Server 作恶。
2. **service authorization**：外层请求 MUST 使用 RFC 9421 HTTP Message Signature，绑定 `@method`、`@target-uri`、`@authority`、`Content-Digest`、`Source-Service-ID`、`Destination-Service-ID`、`Source-Trust-Domain`、`Destination-Trust-Domain` 与 `Idempotency-Key`。`Idempotency-Key` MUST 逐字等于 body `claim_request_id`。

成功响应的反方向也必须闭合。每条 `keypackage_claim_record` MUST 携带与分支一致的 principal/device 或 Agent endpoint、authorization Event id、KeyPackage digest 与 signature；目标 Principal Server 的签名 `claim_receipt` 对 exact claim bytes 可验证归责。requester MUST 核对 authorization Event 的内嵌 Principal Server admission proof、claim receipt、KeyPackage 签名与所有 selector，任一不匹配都不得安装 KeyPackage 或 author Welcome。wire 不得携 PCR/control-history/device/Agent signer-evidence sidecar，外部 verifier 不重放 PCR genesis、Seal 或 range-completeness。

`claim_request_id` 与 `claim_nonce` 各自 MUST 含至少 128 bits 不可预测熵。`requester_authorization.signed_at` 不得在接收方当前时间未来 60 秒以上；`expires_at` MUST 晚于 `signed_at` 且 `expires_at - signed_at <= 300s`。外层 HTTP signature 的 `created` / `expires` 窗口同样 MUST 不超过 300 秒。两层签名均绑定 source / destination / trust-domain，可阻断可信来源服务把授权转发给另一目标或另一部署重放。

#### 9.2.2 目标 authority 的独立准入

在触碰 KeyPackage 状态前，目标服务 MUST 独立验证：

- `Source-Service-ID` 是 requester 当前已验证 Principal Server locator / home authority，`Destination-Service-ID` 是 `target_principal_id` 当前 KeyPackage authority，且两端与请求中的 trust domain 均属于允许此次 Realm 建立的同一 trust domain；
- participant authorization 的 requester、verification method、generation / device authorization、freshness 与 exact request/transport binding 全部有效；
- target 当前 active device、KeyPackage expiry / revocation / capability 均有效，并满足 `required_capabilities ⊆ capabilities`；
- `claim_purpose=direct_conversation|direct_conversation_repair` 时，request MUST 携带 `pair_key` 与 main
  `strand_id`；目标服务按 [`../identity/contact-and-direct-conversation.md` §7](../identity/contact-and-direct-conversation.md)
  重算 pair key，并验证双方 current directional Contact heads 都包含 `direct_message`、预留 Realm / Strand /
  MLS group 的一致性；该路径不得查询 Consent；
- `claim_purpose=direct_conversation_repair` 时还必须携带 `target_keypackage_ref` 与 closed target XOR：human
  branch 必须且只能携带恰一个 `target_device_ids`；Native Agent branch 必须且只能携带
  `target_agent_id + target_agent_verification_method + target_agent_key_authorize_event_id`，禁止
  `target_device_ids`，且 `target_agent_id == target_principal_id`。owner authority 必须验证该 exact ref 属于
  对应 target 与 signer，selector、claim record、current portable signer evidence 及 KeyPackage signature
  逐字一致，状态为 current
  `published`、未消费、未撤销且 `last_resort=false`；不得忽略 exact ref 后按 device、capability 或库存顺序
  另选。成功 outcome 必须恰有一条 claim 且其 `key_package_ref` 逐字等于 `target_keypackage_ref`；任一不匹配
  以不透明 `claim_failed` 零写入；
- `(Source-Service-ID, target_principal_id)` 的限速与 abuse policy 通过。

`claim_purpose=direct_conversation|direct_conversation_repair` 时 `last_resort_allowed` MUST 缺省或为 `false`，
目标服务 MUST NOT 返回 last-resort KeyPackage。一般 `realm_membership` claim 只有在双方 feature negotiation
均声明 `ak.feature.mls_last_resort_keypackage.v1` 且请求显式 `last_resort_allowed=true` 时才可返回 last-resort
record；否则 single-use pool 耗尽即失败。

#### 9.2.3 原子幂等 ledger 与不确定结果

目标 authority MUST 持久化以 `(Source-Service-ID, claim_request_id)` 唯一索引的 claim ledger，并把从已验证 exact canonical body bytes 内部计算的 Arkret digest 记为 `request_digest`。下列动作必须处于同一事务 / 等价线性化边界：

1. 核对已由唯一索引保护的 request reservation 与 digest；
2. 一般 profile 选择仍为 `published` 且通过 freshness / capability gate 的 KeyPackage；
   `direct_conversation_repair` 则只锁定 request 的 exact `target_keypackage_ref`，不得执行候选选择；
3. 对 single-use KeyPackage 执行 CAS `published → claimed`；
4. 在同一 current authority snapshot 上生成并复核 target portable evidence，写入 claim record、把
   ledger 从 `pending` 变为终态，并写入已序列化的成功 outcome bytes。

实现 MAY 在最终事务前先提交只含 `(Source-Service-ID, claim_request_id, request_digest, state=pending)` 的唯一 reservation，以串行化并发 duplicate；该 reservation 不得选择、锁定或泄露 KeyPackage。上述 1–4 的**最终化**必须在同一事务完成，因而不得出现 KeyPackage 已 `claimed` 但 ledger 无 outcome、或 ledger 已成功但 CAS 未发生的可观察状态。crash 后 recovery worker 只能按原 digest 恢复 / 最终化同一 reservation，不能改用新的请求身份。

同一 source、同一 `claim_request_id`、同一 digest 的 duplicate transport delivery / replay MUST 返回 byte-identical 成功 outcome，且不得第二次领取；这项 receiver 安全性不把 operation 变成可跳过恢复查询的 caller retry-safe。同一 key 携带不同 digest MUST 返回 `duplicate_conflict` 且不得改变任何 KeyPackage。响应丢失、超时或来源服务在 durable dispatch marker 与实际 network send 之间 crash 后，来源服务 MUST 先调用 `ak.peer.keys.keypackages.read.claim`，携带原 `claim_request_id + request_digest`，不得先重发 command，也不得换 nonce 盲目重新 claim。query 只接受原 Source-Service-ID 与 exact digest，返回 `unknown|pending|claimed|claim_failed|expired|revoked`；`unknown` 明确证明目标尚无该 request identity 的 reservation，调用方此时 MAY 重放 exact same canonical command（同 source、claim_request_id、digest、nonce 与 evidence），不得生成新请求；`pending` 表示 reservation 已存在但最终化事务尚未提交，调用方只可按 `retry_after_ms` 再查；`claimed|expired|revoked` MUST 携带原签名 `claim_outcome`，`claim_failed` 只携带不透明 `error_code=claim_failed`。

成功 outcome 的 `claim_receipt.signature` 由目标服务对 `` `ak.peer-keypackage-claim-receipt-v1\n` `` + JCS(receipt 除 `signature` 外全部字段) 签名；receipt MUST 携带并签名覆盖 `source_service_id`、`destination_service_id` 与原 participant-authorized `request`（即不含 authorization / transport-only evidence 的 unsigned request 字段），`request_digest` 绑定完整 peer command，`claims_digest` 绑定 `claims[]` canonical bytes。`claim_request_id`、receipt.request 内同名字段与 outcome 同名字段必须一致。ledger 的可查询 outcome MUST 至少保留到 claim `expires_at + 10 minutes`；其后实现 MAY 只保留符合隐私 / 审计策略的 hash replay tombstone，不得长期保留可关联 private Realm 的不必要明文。

通过 peer claim 生成的 `ak.mls.welcome` MUST 原样携带 `payload.peer_claim_receipt`。目标 Principal Server 在接受该 Welcome 前 MUST：验证 receipt 目标服务签名；以外层认证的 `Source-Service-ID` 精确匹配 `source_service_id`；查询 `(source_service_id, claim_request_id)` durable ledger 并逐字匹配 `request_digest` 与 stored outcome；验证 request 的 requester / target principal / intended Realm / MLS group / claim nonce 与 Event actor、recipient、Realm、Welcome group / `claim_envelope` 一致；验证 stored claim 与 Welcome 的 claim id、KeyPackage ref / digest、recipient device 一致。缺 receipt、ledger 未就绪或任一绑定不一致时均须 fail closed；ledger 尚未可见属于 retryable dependency，不得把未经认领的 Welcome 降级接受。Direct Conversation immutable binding accepted 前还 MUST 将 receipt.request 的 `pair_key` 与 `strand_id` 精确匹配该 pair 唯一 durable operation 已锁定的 binding payload。

所有目标不存在、任一方 Contact head/scope 不满足、设备不可见、KeyPackage 耗尽、capability 不满足、policy denied、participant authorization 失效和限速失败，对**已通过外层服务认证**的 peer caller 必须收敛为同一 `claim_failed` 外观；不得返回 `available_count`、目标设备列表或逐设备 `failures[]`。外层 RFC 9421 signature / source service identity 无法通过时，接收方在读取 target 状态前返回通用 `unauthenticated` / `invalid_signature`；该响应必须只由 transport authentication 决定，对任意 `target_principal_id` 完全相同。

#### 9.2.4 Welcome、consume 与唯一 materializing operation

目标设备只有在以下条件全部成立后才可激活 Welcome 并通过其 own Principal Server 的 `ak.self.keys.keypackages.command.consume` 消费 claim：Welcome / claim-ref 校验通过、对应 Realm/member/main-Strand/MLS Event 均可验证，且 Welcome 精确属于同一 `(trust_domain,pair_key)` 唯一 `materializing` operation 锁定的 Realm、main Strand、initial MLS group 与 immutable binding。peer surface 不提供 consume 代理；来源服务不得代表目标设备把 claim 标为 consumed。

同一 `(trust_domain,pair_key)` 的并发 resolver MUST 在任何 KeyPackage claim 前命中同一个 durable operation；coordinator 已把 operation 置为 `materializing` 后，所有重试只能恢复该 operation 的同一坐标和 claim identity。实现不得领取并行替代 KeyPackage、生成第二候选 Realm/Welcome、比较 binding digest 选择 winner，或把一次 claim 释放回 `published` 以尝试另一候选。重复 claim command 使用既有 idempotency/ledger 规则返回或查询原 outcome；不匹配唯一 operation 的 Welcome 必须在激活 MLS state 和 consume 前 fail closed。

### 9.3 普通 MLS join admission 与补偿（normative）

public/invite/closed/knock/admin-add 的最终 join都必须携未过期、single-use、签名的
`MlsJoinAdmissionReceipt`。receipt完整绑定 target Realm/member/**exact target device**、KeyPackage ref/claim、
group ID、MLS generation、expected epoch、current security frontier、join authority basis、exact member Event
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
admission/join identity、member Event ID/digest、membership cell/incarnation与J1 provenance、subject、真实
`actor_id/executed_by?/authorization_ref?/verification_method`分支、executor service DID+proof key、resource、
deadline及唯一action。先从exact RFC8785/JCS core计算stable `delegation_digest`，再机械派生外层
`delegation_id=ak:membership-compensation-delegation:sha256:<lowercase_hex>`；ID后缀必须逐字等于该digest，
外层author signature覆盖ID、core与digest。不可转授，也不得用普通grant/source代替。

action是closed XOR：self join仅 `ak.member.compensate.leave`，delegated/admin join仅
`ak.member.compensate.remove`；未知action fail closed。executor author fresh标准 `ak.member.state`减权 Event，
固定原join actor，`executed_by=executor`，`authorization_ref`精确引用delegation。terminal certificate仅作
critical submission evidence，不进入被授权Event digest。destination authority以
`(admission_id,delegation_digest)`做single-use CAS；current provenance仍是J1时最多一次写入，already absent或
J2/new incarnation分别返回destination-signed `already_absent|superseded`且零写，绝不得删除后来重新加入者。

失败分支固定为：claim前拒绝零烧；claim后/member acceptance前只revoke原claim；member accepted/Add前执行
membership compensation；Add已接受后先执行同一membership compensation，再由eligible committer执行标准MLS
Remove。Remove绑定旧group/generation/leaf/commit，新generation上只能no-op。deadline触发operation failure，
但cleanup authority持续到signed terminal outcome。重复、跨admission、executor/proof key错配或deadline前滥用
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

当验证目的为 `same_principal_device_authorization` 时，用户确认后的授权落地 MUST 发生在 `/_arkret/gate/account/*` 认证面，默认使用 `ak.gate.account.command.pair_device`。旧设备把验证 transcript 中绑定的 `pairing_code`、`new_device_pubkey`、`challenge_proof`、从已验签 `target_attestation` 取得的 `hpke_key` 与 `device_signature`、自己 author 的完整 `ak.device.authorize` 提交，以及自身 fresh device proof 提交给 gate；gate MUST 按 §2.1.2 独立重算 challenge transcript 并验签，再按 §5.2.2 用该 digest 与提交 payload 重建 accepted_device possession 对象并验签 `device_signature`，MUST NOT 只做逐字段相等比较；gate 返回的 `authorized_event_ref` 只是 durable `ak.device.authorize` / `ak.device.list_update` 已被接受的引用或等价结果。新设备可通过同一 to-device transcript 的 `ak.key.verification.done` 中的 `authorized_event_ref` hint、后续 full `ak.self.account.stream.subscribe` device list baseline，或重新通过 `ak.gate.account.command.issue_session_grant` 升级会话来观察授权结果；它 MUST 验证 durable device list，而不得把 `done` 消息本身当成授权真相源，并 MUST 在本地装配前完成 §5.4.1 的强制校验。

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

HPKE AAD（本 kind 的具体绑定）MUST 是对以下字段的 canonical JSON（RFC 8785 JCS）：`message_id`、`kind`、`sender_principal_id`、`sender_device_id`、`recipient_principal_id`、`recipient_device_id`、content 中的 `request_id`、content 中的 `secret_id`，以及 envelope 中已经通过 [`time.schema.json#/$defs/timestamp`](../../artifacts/schemas/time.schema.json) 验证的原字段 `expires_at`。`expires_at` 在 AAD 中仍是逐字相同的 `.sssZ` string；MUST NOT 另派生 `expires_at_unix` / `expires_at_unix_ms`，也不得宽松解析后重排。principal / device / message ID 与 `request_id` / `secret_id` 都使用外层原始 canonical string，在收发两端从 `DeviceMessageEnvelope` 与 `ak.secret.send.content` 确定性重建。把 `message_id` 与 `request_id` / `secret_id` 同时放入 AAD 可防止中间层替换外层幂等身份或业务关联字段。§7 的通用 AAD 最小集不包含由队列服务物化的 `sent_at`；本 kind 由发送方分配的 `message_id` 与密封 plaintext 内的一次性 `request_id` 提供抗重放/新鲜性绑定。

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

Key backup 保存已加密的 Realm / MLS 历史密钥材料。它只覆盖当前 actor 已经通过 membership、history visibility 和 Realm policy 获得的历史范围，不是给未来新成员预先保留历史 secret 的机制。唯一的 managed-principal 托管分支是 [`../identity/key-management.md` §7.5.6](../identity/key-management.md)：Native Personal Agent controller 可把其依当前 Agent DID delegation 合法持有的 Agent PCR MLS state 写入 **controller-owned** `mls_history` envelope；外层 `actor_id` 与 caller 仍是 controller，不放宽跨 actor backup 访问。

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
    "hkdf_info": "arkret-key-backup/mls_history/mls_epoch/v1",
    "subdomain": "mls_epoch",
    "aead_aad": {
      "schema": "ak.schema.key_backup.v1",
      "actor_id": "ak:did_core:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH",
      "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
      "backup_kind": "mls_history",
      "backup_version": "kb_1",
      "created_at": "2026-04-26T00:00:00Z",
      "item_kinds": [
        "mls_epoch_secret"
      ]
    }
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
    "signed_fields": [
      "backup_id",
      "actor_id",
      "backup_kind",
      "backup_version",
      "series_id",
      "series_seq",
      "supersedes",
      "encryption",
      "domain_separation",
      "contents",
      "ciphertext_digest"
    ],
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
- 任何 backup class 只要使用 `recovery_public_key`，就 MUST 携带顶层 `recovery_policy_ref{policy_id, policy_version}` 并由 `auth_data.signed_fields` 覆盖；`recipient_key_ref` 只能解析到该 accepted policy 的 `recovery_key_agreements[]`。`mls_history` / `secret_storage` 在读取/恢复时须按 accepted policy history、active-series 与轮换规则拒绝回滚。不一致 MUST `recovery_policy_mismatch`。只有 `secret_storage_key` 等非 recovery-public-key 方法携带的 `recovery_policy_ref` 才是可选 hint；任何 policy ref 都不得替代 active-series record、frontier_ref 或 Realm/MLS 授权校验。
- 上传设备 MUST 通过 `auth_data` 对 backup metadata 与 ciphertext digest 签名，并携带当前 accepted `device_authorize_event_id`；`frontier_ref` 只允许 `device_generation_ref`。`auth_data.signed_fields` MUST 至少覆盖 `backup_id`、`actor_id`、`backup_kind`、`backup_version`、`series_id`、`series_seq`、`supersedes`、`encryption`、`contents` 与 `ciphertext_digest`；非 genesis envelope 还 MUST 覆盖 `supersedes_digest`，携带 `frontier_ref` 时还 MUST 覆盖 `frontier_ref`，携带 `recovery_policy_ref` 时还 MUST 覆盖 `recovery_policy_ref`。签名链必须链接到当前 PCR device authorization evidence。
- 服务端 MUST 只允许同一 actor 的当前授权设备、满足 recovery policy 的恢复流程，或 policy 明确授权的组织恢复服务读取备份密文。
- 含 Agent PCR managed item 的 envelope MUST 使用 `recovery_public_key`，携带 controller 当前 `recovery_policy_ref`，并让 public index、plaintext keybag 与 AEAD AAD 对同一 `managed_principal_binding` canonical set 达成逐字一致；服务端在接受上传前 MUST 按 envelope `created_at` 验证 Agent DID/PCR/controller/delegation binding。该验证只证明 controller 当时有权托管密钥，不让服务端获得解密能力，也不让历史解密能力替代当前 Agent DID authoring authorization。
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
- `legal_hold=true` 的 envelope MUST 被服务端拒绝删除（即便提供 high-risk proof）；解除 hold MUST 由声明该 hold 的 Policy Server 通过 policy update 完成，并写入审计。
- 同一 series 内的 retention 必须保证链不被打破：服务端 MUST NOT 删除 active series 的非尾部 envelope；旧 series 只有在已经被 active-series record 移出 primary source 后，才 MAY 按 retention / erasure 策略整组删除或迁移。若该删除属于`SecurityRotationTransaction`，两个backup kind的pointer、逐series进度、partial retry与complete confirmation一律以[`identity/security-transactions.md` §3](../identity/security-transactions.md)为准。
- erasure 完成后保留的 `retained_stub_digest` MUST 仅含 metadata 哈希，不含密文与 KDF 参数，以避免间接成为离线爆破证据。

## 13. Realm Key Share and Withholding

Arkret 使用 `ak.realm_key.share` 共享历史解密材料。`share_kind="member_device"` 是普通成员设备历史交付路径；共享前发送设备 MUST 检查：

- 接收设备属于目标 principal。
- 设备未撤销。
- 设备是 PCR current accepted、未撤销且未被 generation fence 的设备；如 Realm policy 另要求人工验证，也必须满足该附加条件。
- history visibility 允许该 principal 获取目标历史范围，且判定时点使用目标 Event range 的 deterministic `T0`，不得使用本地到达顺序或 wall clock。
- effective `ak.realm.history_sharing_policy` 允许该 receiver class、scope、epoch range 和 key source；当 Realm / Circle history visibility 为 `restricted` 时，必须命中 `restricted_rules[]`，且本次请求所用 key 来源 MUST 在命中 rule 的 `key_sources` 内（命中 read rule 但来源不在 `key_sources` 时只放行读取、不交付 key），否则 MUST withhold。
- `key_scope.policy_digest` 绑定本次判定使用的 Realm policy / MLS governance policy root；如判定依赖 membership frontier，`key_scope.membership_frontier_digest` SHOULD 同时写入。
- `sender_device_signature` MUST 覆盖 `share_kind`、发送设备、接收 principal/device、`key_scope`、`aad_digest?`、`ciphertext` 或 `encrypted_key_ref` 与 `created_at`。接收方 MUST 验证该签名链接到当前有效 sender device key，且不得只依赖传输层认证。
- 对 `history_visibility=joined` 的 scope，join 前 epoch key MUST 被拒绝；对 `invited`，share range MUST be no earlier than receiver 的有效 invite frontier；对 `shared`，join 前 history key share 仍需要 policy 明确允许；对 `world_readable`，E2EE key 不因 public history 自动公开。
- current safety policy（redaction / erasure / retention / ban·remove / legal hold）未禁止继续向该 principal / device 交付。
- audit profile 要求的 `ak.realm_key.share_audit` / `ak.audit.accessed` 已满足。
- Archive Node、Key Recovery Service、Recovery Service 或 peer 不能因为持有备份副本就绕过上述检查；服务端 operator 权限不是 key share 授权。

`ak.realm_key.share` 的 v1 wire 合同**不携带、也不隐式依赖**发送方 `ak.device.authorize` Event ref。authoring 不得为了构造 share 查询 `list_devices` 的 current row、current device snapshot 或其它“现在最新”设备视图；这类查询结果既未进入 `RealmKeySharePayload`，也未进入 `sender_device_signature` transcript，接收方无法冻结或重放，故不构成安全证据。发送方设备资格只由本节既有的 Event envelope/CBA、`source_authorization_ref`、`sender_device_id` 与 `sender_device_signature` 验证链判定。若未来要求 exact accepted device-authorization evidence，必须先新增进入 closed schema、canonical transcript 与 receiver installation gate 的独立冻结 carrier；实现不得私下增加字段或恢复 current-snapshot 门槛。

`share_kind="realm_recovery_key"` 是 Realm `durability_policy` 的 RRK 持久化封存路径（[`encryption-and-audit.md` §2.10.8](./encryption-and-audit.md)）。它 MUST 携带 `recipient_verification_method` 与 `recovery_recipient_id`，MUST NOT 携带 `recipient_device_id`，且 `sender_device_signature` MUST 覆盖 `share_kind`、发送设备、`recipient_principal_id`、`recipient_verification_method`、`recovery_recipient_id`、`key_scope`、`aad_digest?`、`ciphertext` 或 `encrypted_key_ref` 与 `created_at`。发送方 MUST 按 §2.10.8 校验 RRK DID service 绑定与 effective `durability_policy`，不得复用本节的成员设备资格校验来替代 RRK 校验。

本节是 key-share 资格校验的 **canonical 来源**；history-visibility、late key recovery 等处对发送侧前置校验的引用以本节为准，不再各自重述。

拒绝共享时发送 `ak.realm_key.withheld`，其 payload 使用 `withheld_reason_code` 承载原因码：

- `unverified_device`
- `blacklisted_device`
- `not_member`
- `history_not_visible`
- `policy_denied`
- `unknown_session`

`ak.realm_key.withheld` 与 share 共用同一 delivery cell family，因此它同样 MUST 携带 `share_kind`（v1 仅 `member_device`）、`key_scope` 与 `source_authorization_ref`。withheld 虽不携带 secret，但 `not_member` / `history_not_visible` 等 reason 会产生主体级终态语义；仅有任意设备的 Event 签名不足以授权它向目标 delivery cell 写入拒绝记录。缺失或不覆盖该决定的 source authorization MUST 以 `late_recovery_share_not_authorized` 拒绝整个 Event，MUST NOT 把未授权 withheld 投影为终态。

withheld 的 `key_scope.policy_digest` 是**来源方作出该拒绝判定时实际求值的** effective Realm/Circle policy root，它钉住拒绝所依据的 policy snapshot，不表示该 share 曾获授权：`not_member` / `history_not_visible` / `policy_denied` 绑定作出相应 membership、visibility 或 sharing-policy 判定时的 root；`unverified_device` / `blacklisted_device` / `unknown_session` 绑定此次拒绝所依据的 effective device/session eligibility policy root。设备、session 与 membership 事实仍由 Event CBA、引用与领域校验提供，MUST NOT 用 `policy_digest` 自证。receiver MUST 在同一 Event CBA / T₀ basis 上重算并逐字比较该 root。来源方若无法在 canonical basis 上解析出唯一 effective policy root，MUST NOT 生成 canonical durable withheld，只能 fail closed 并走领域登记的非 Event / pending 错误路径，MUST NOT 填零值、接收时当前最新 root 或实现私有占位。

### 13.0 Delivery cell identity 与 sender-device transcript（normative）

`ak.realm_key.share` 与 `ak.realm_key.withheld` 写入同一 `ak.component.realm_key.delivery.v1` cell family。其 cell subject 是固定 arity 4 的判别式复合 subject：`[share_kind, recipient_principal_id, recipient_target_id, effective_scope_id]`。两个 kind 使用逐字相同的 registry descriptor。实现 MUST 按 registry 纯函数重算 cell 与 value；wire 没有 producer 自选 cell。

`sender_device_signature` 的 canonical transcript 由本节固定，schema description 与任何 SDK 方法都不构成替代真源。签名对象为：

```text
{
  context: "ak.realm-key-share-sender-proof-v1",
  share_kind,
  sender_device_id,
  source_authorization_ref,
  recipient_principal_id,
  <仅选中 variant 的 target fields>,
  key_scope,
  <ciphertext 或 encrypted_key_ref，精确一个>,
  aad_digest?,
  expires_at?,
  created_at
}
```

按 [`../conformance/encoding.md` §2](../conformance/encoding.md) 的 canonical JSON 签名。未选中的 variant target 字段、未选中的 material 字段与缺省 optional 字段 MUST 省略，MUST NOT 写 `null`；payload schema 已把 `ciphertext` / `encrypted_key_ref` 收紧为 exactly-one，因此 transcript 中恰有一个 material 字段。`expires_at` 出现时 MUST 进入 transcript。verifier MUST 逐字节重建同一 transcript，并要求 signature `kid` 解析到 `sender_device_id` 对应的、该 sender principal 当前 accepted 且未撤销的设备 key；外层 Event proof MUST NOT 替代这条领域签名。

#### 13.0.1 Delivery append value projection（normative）

delivery cell 的 lattice 是 `ordered_log`，每个 accepted Event 产生恰好一个 `op.kind="append"` entry。该 entry 的值由本节固定为一个**纯函数投影**：receiver MUST 根据 Event 与 registry 合同独立计算，不可确定时以 `reducer_projection_failed` 拒绝整个 Event。实现 MUST NOT 接受 producer 自选的任意 JSON value。

投影结果是 canonical JSON object。缺省的 optional member MUST 省略，MUST NOT 写 `null`。

`ak.realm_key.share` 的 member 与来源：

| member | 来源 |
| --- | --- |
| `delivery_outcome` | 字面量 `"shared"` |
| `share_kind` | `payload.share_kind` |
| `recipient_principal_id` | `payload.recipient_principal_id` |
| `recipient_target_id` | 与 cell subject 同一 `select`：`member_device` → `payload.recipient_device_id`；`realm_recovery_key` → `payload.recovery_recipient_id` |
| `effective_scope_id` | 与 cell subject 同一 `select`：`realm` → `payload.key_scope.effective_scope.realm_id`；`circle` → `payload.key_scope.effective_scope.circle_id` |
| `policy_digest` | `payload.key_scope.policy_digest` |
| `from_epoch`（optional） | `payload.key_scope.from_epoch` |
| `to_epoch`（optional） | `payload.key_scope.to_epoch` |
| `sender_device_id` | `payload.sender_device_id` |
| `source_authorization_ref` | `payload.source_authorization_ref` |
| `payload_digest` | 完整签名 payload 的 canonical JSON bytes 的 digest |

`ak.realm_key.withheld` 使用同一前十项（`delivery_outcome` 为字面量 `"withheld"`）与同一 `payload_digest`，并追加：

| member | 来源 |
| --- | --- |
| `withheld_reason_code` | `payload.withheld_reason_code` |

规则与理由：

- **plane 边界。** delivery family 在 registry 中是 `plane=data`，因此该 cell 的 joined value MUST NOT 进入治理 `state_root`；它的 Seal 级承诺走 [`../authz/event-auth-state-resolution.md` §6.4](../authz/event-auth-state-resolution.md) 的 `data_view_root`（§6.2.1 明确 data plane cell 不进入 `state_root`）。
- **不复制材料本身。** `op.value` 由每个参与方独立重算并进入数据面观测承诺；把 HPKE 密文抄进去会让所有节点为记账各背一份密文副本。投影只承诺指纹。
- **`payload_digest` 承诺完整语义，不逐字段枚举。** [`../authz/event-auth-state-resolution.md` §9.3.1](../authz/event-auth-state-resolution.md) 规定同一 `(cell, actor_id, issuer_seq)` 上完整 canonical `write.op` bytes 相同即幂等 duplicate。若投影只承诺部分字段，语义不同的两条交付会产生逐字相同的 entry 而被静默去重——例如密文相同但 `expires_at` 不同的续期 share、`aad_digest` 不同的重封、RRK 轮换后 `recipient_verification_method` 改变的重新封存，以及 `key_scope` 中 `membership_frontier_digest` / `history_visibility` 的差异。逐字段枚举会在 payload 每次演进时重新产生该缺口，因此本节固定为对**完整签名 payload**（含 `sender_device_signature`）取 digest：任何语义差异都改变 `payload_digest`，而逐字节相同的重放仍然幂等。
- **digest 形态**遵循该 Realm 的 `digest_algorithm` 与 [`../conformance/encoding.md` §3.1](../conformance/encoding.md) 的 `<suite>:<lowercase_hex>` wire 形态；输入是 payload 的 canonical JSON bytes（[`../conformance/encoding.md` §2](../conformance/encoding.md)）。
- **不使用 Event 标识符。** `event_id` / `event_digest` MUST NOT 出现在 `op.value` 中：entry value 是内容承诺，不是 Event 引用；`event_digest` 另由 §9.3.1 的 equivocation tie-break 使用，写回 `op.value` 会产生自引用。审计侧的 share 与结果关联仍由 `ak.realm_key.share_audit` 的 `share_event_ref` 承担。
- 其余可读 member 保留，是为了让数据面投影和诊断无需重新解析 payload；它们不承担完整性职责，完整性由 `payload_digest` 承担。

### 13.1 来源级扣留 vs 主体级拒绝（normative）

`ak.realm_key.withheld` 必须区分两类语义，二者对接收端是否为终态不同：

- **主体级拒绝**——`not_member` / `history_not_visible`，或接收 principal/device 已处于 ban / leave / removed / account 失权态。该 reader 在目标 `T0` 本就不具读资格，withhold 为**终态 fail-closed**；客户端 MUST NOT 重试，事件维持 metadata-only。
- **来源级扣留**——reader 在 `T0` 仍具读资格（§3 visibility 通过、receiver 未失权），仅因本次请求所用 `key_source` 不在命中 `restricted_rules[]` rule 的 `key_sources` 内（或该来源未满足 audit/device 验证）而被拒，`withheld_reason_code` 取 `policy_denied`。该扣留**只对当前来源终态、对该 reader 非终态**：

  - key source MUST NOT 把它当作主体级拒绝；接收端 MUST 将事件保持在 `decryption_pending` 可恢复车道（§2.3.4 `key_unavailable` 语义），不得降级为"已拒绝"展示。
  - 接收端 SHOULD 从 effective `ak.realm.history_sharing_policy` 命中 rule 的 `key_sources` 解析出授权来源集合，并改向其中任一来源（`key_backup` / `archive_node` / `verified_member_device` / `recovery_service`）重新请求；对已具读资格的 reader 公布该集合不构成披露。
  - 被重新请求的授权来源 MUST 独立重跑本节完整闸门——读资格是必要非充分条件，授权来源不得因 reader 读资格成立就跳过 T0 / device / audit 校验。
  - 若当前无任何授权来源可服务，事件停在 `decryption_pending`，超时后按 §2.3.4 转 `decryption_failed`，日后仍可经 §2.3.5 late key recovery 解锁。任何时点都不得出现"读资格成立却被标记为永久不可解"的终态。

### 13.2 历史 key 请求、来源发现与选择（normative）

§13 / §13.1 规定了 key source **交付**前的资格与扣留语义；本节规定接收方**如何发现、选择并向具体来源发起请求**——这是与交付独立的发现 + 请求流程。

**`ak.realm_key.request`**——read-eligible 的接收方向某个 key source 发起的历史 key 请求。它是可靠
to-device 触发消息，与 `ak.key.verification.request` 同类，使用
[`device-message.schema.json`](../../artifacts/schemas/device-message.schema.json) 的
`DeviceMessageEnvelope.content`，经 device message 队列中继到 `target_source_ref` 指向的来源；
它不进入 Event registry 或 reducer state，也不得使用 durable `EventEnvelope`。content 字段顺序对齐本表：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `key_scope` | yes | 请求的 `effective_scope`、`from_epoch` / `to_epoch`（请求的 epoch 区间）。 |
| `recipient_principal_id` | yes | 接收主体 DID（MUST == 请求签名者，§13.2 校验 1）。 |
| `recipient_device_id` | yes | 接收设备 id。 |
| `recipient_hpke_public_key` | yes | 用于封装 `history_secret` 的接收设备公钥（KeyPackage init key 或等价设备公钥）。 |
| `requested_source_kind` | yes | 本次面向的来源类别，取 `own_device` / `verified_member_device` / `archive_node` / `recovery_service`。**不含 `key_backup`**——它走 `ak.self.keys.backups.command.unlock`、不经本请求。 |
| `target_source_ref` | yes | 本请求路由到的**具体来源**：peer（`own_device` / `verified_member_device`）为目标 `device_id`，service（`archive_node` / `recovery_service`）为 service DID。若 service 复用本 to-device kind，`DeviceMessageEnvelope.recipient_principal_id` MUST 等于该 service DID，`recipient_device_id` MUST 是该 service 在 describe 中暴露的具体队列 / 设备目标；未暴露时 MUST 走服务专有 operation。无该字段则 relay / service 路由与审计无法定位来源。 |

**触发**：接收方在某 Event 处于 `decryption_pending` 且自身在该 Event 的 `T0` read-eligible（[`../governance/history-visibility.md`](../governance/history-visibility.md) §3）时 MAY 发起；对 `decryption_failed` 的 late recovery 同样适用（§2.3.5）。`ak.realm_key.request` 只是发起信号，不降低任何授权要求——被请求来源 MUST 独立执行 §13 canonical 校验后才交付。

**两类场景的来源不同（normative）**：

- **同 principal 恢复**——已是成员、在新设备上恢复或丢设备后恢复**自己已有权读取**的历史。来源为 `own_device`（同 principal 另一台在线设备）或 `key_backup`（**接收方本人的** `mls_history` key backup，加密于其本人 recovery key 之下、经 unlock 取回；见 [`../identity/key-management.md`](../identity/key-management.md) §7.7 与 `backup_kind="mls_history"`）。`mls_history` backup 只装"用户已有权读取的"历史，故 `key_backup` 只适用本场景。
- **跨 principal 新成员**——首次加入、获取 join 前**从未持有**的历史。来源为 `verified_member_device`（现有成员重新分享其保留的 `history_secret`）、`archive_node` 或 `recovery_service`。**`own_device` / `key_backup` 不适用**：新成员从未有权读取这些 epoch，其本人 backup 里也不会有它们。

**来源选择 = 三层求交（normative）**：接收方选择来源 MUST 同时满足——

1. **policy 允许**：来源类别在 effective `ak.realm.history_sharing_policy` 命中 rule 的 `key_sources` 内（§13 / history-visibility §6 / §3.1）。
2. **describe 可用**：该来源对应能力在权威 `ServiceDescribe.supported_features` 中声明——按 [`../sync/service-surface.md`](../sync/service-surface.md) §3 的能力发现原则，客户端 MUST 以 describe 为权威发现面，不得对猜测 endpoint 直接探测。
3. 取 `policy 允许 ∩ describe 可用` 的交集，**先按上文场景筛掉不适用的来源**，再按优先级逐一尝试——同 principal 恢复推荐 `own_device` → `key_backup`；跨 principal 新成员推荐 `verified_member_device` → `archive_node` → `recovery_service`；部署 MAY 在 Realm policy 覆盖该顺序。交集为空时事件停在 `decryption_pending`（§13.1 末条），不得报永久不可解。

**服务端能力广告**：服务端 MUST 通过 `ServiceDescribe.supported_features` 声明其支持的历史 key 投递途径：

- `ak.feature.realm_key.backup_retrieval.v1`：托管 key_backup 取回（`POST /_arkret/self/keys/backups/{backup_id}/unlock`，见 [`../identity/key-management.md`](../identity/key-management.md) §7.7）。
- `ak.feature.realm_key.peer_relay.v1`：中继 peer 的 `ak.realm_key.request`（device-to-device，经 device message 队列投递）；授权后的 `ak.realm_key.share` / `ak.realm_key.withheld` 仍是 durable event，队列 MAY 只投递其 event ref / 通知。
- `ak.feature.realm_key.archive_retrieval.v1`：作为 archive_node 服务历史 key。

`archive_node` / `recovery_service` / `key_recovery_service` 是独立 `service_kind`（service-surface §3 注册值），其取回 endpoint 由 Realm policy 点名的 service DID 各自 describe 暴露。

**每来源的请求 / 取回映射**：

- `key_backup`：走 `ak.self.keys.backups.command.unlock`（unlock proof，§7.7），**不**使用 `ak.realm_key.request`。
- `verified_member_device` / `own_device`：发 `ak.realm_key.request` 给目标设备，服务端按 `peer_relay` 中继；目标设备校验 §13 闸门后提交 durable `ak.realm_key.share` 或 `ak.realm_key.withheld`（MAY 另经 to-device 队列通知接收方对应 event ref）。
- `archive_node` / `recovery_service`：按该服务 describe 声明的 endpoint 取回；只有当 describe 暴露可接收 `DeviceMessageEnvelope` 的具体 queue/device target 时 MAY 复用 `ak.realm_key.request`，否则 MUST 使用服务专有 operation。

**请求合法性校验（normative）**：`ak.realm_key.request` 是非授权性的**触发信号**——被请求 source MUST NOT 因为收到请求就交付，而是独立按 §13 canonical 闸门 + 授权事件日志 fail-closed 重验下列**全部**，任一不过 MUST 回 `ak.realm_key.withheld`：

1. **只能为自己请求**：`recipient_principal_id` MUST == 请求事件**签名者**的 principal；不接受代他人请求。
2. **recipient 在目标范围 `T0` eligible**：按 Realm 事件日志中 recipient 的 `ak.member.state` 判定其在 `key_scope` 各 epoch 的 `T0` 为 read-eligible（history-visibility §3）；membership 取自**签名事件日志**，不取自请求自述。
3. **policy 允许**：effective `ak.realm.history_sharing_policy` 命中 rule 覆盖该 receiver class、`key_scope` 区间与本 source 类别（含 `restricted_rules[].key_sources`）。
4. **请求来自 recipient 的授权设备**：`ak.realm_key.request` 的签名 MUST 链到 recipient principal 在 `T0` 当前授权的设备。
5. **seal 目标属于 recipient**：`recipient_hpke_public_key` MUST 是该 recipient principal 的**已授权设备**公钥（对 KeyPackage / device-list 校验），防止把历史 seal 到未授权 key。

合法性来自 source 对授权事件日志的**重验**，而非对请求内容的信任；伪造的请求无法越过 membership / device / policy 任一关。

**push 豁免与落点（优化路径，normative）**：持有相应 `history_secret` 且已确认接收方 read-eligible 的 source MAY 不等 `ak.realm_key.request`、直接提交 durable `ak.realm_key.share`，仍 MUST 通过 §13 完整闸门与上述等价 recipient/device/policy 校验。其可行**落点是 admission（发 `ak.mls.welcome` 之时），不是 invite 之时**——invite 时被邀请者尚未发布 KeyPackage / 设备公钥，无可封装目标，故 invite 只能携带历史**资格意图**（policy 声明该 invitee 可看的 range），不能携带 sealed key。push 的 seal 目标 MUST 是**接收方掌握私钥的设备 HPKE 公钥**（§2.10.4）——MLS KeyPackage init key 的私钥通常不暴露供带外解封，故 admin **不能**直接用 claim 到的 KeyPackage init key seal。因此 push-at-admission **仅当**接收设备已发布/可获取一把专用设备 HPKE 公钥时成立；否则历史交付走 **request 驱动**:receiver 在 `ak.realm_key.request.recipient_hpke_public_key` 中广告其设备 HPKE 公钥，provider 据此 seal 并提交 share。admin 不持有的更早 epoch 同样由 receiver 事后按本节 pull 补全。

## 14. PCR-Policy Device Recovery

全设备丢失时，账号重新登录不能替代 PCR recovery proof。基础路径由丢失前已进入 accepted Seal 的
recovery policy 授权，并提交两条 Event：

1. policy-authorized `ak.device.reanchor` 绑定 policy/version/session、`principal_id`、`principal_server_id`、replacement
   authorize payload digest 与 monotonic PCR generation CAS；
2. replacement device 自签 `ak.device.authorize`，`authorization_binding_kind="pcr_recovery"`，
   `prev_refs` 只指向 re-anchor Event。

两条 Event 必须原子接受，receipt `scope.kind="device_reanchor_unit"`。该 scope 的封闭字段集恰为
`{kind, principal_id, principal_server_id, realm_id, previous_device_generation, new_device_generation, reanchor_digest, replacement_authorize_digest}`：它与 `ak.device.reanchor` payload 选择同一个本地 account authority pair，每个同名字段 MUST 与被覆盖 payload 逐字节相等，任一不等以 `device_reanchor_authority_mismatch` fail closed。scope MUST NOT 携带 `did_version_id`、
`registry_head` 或任何 DID publication 字段，接收方也 MUST NOT 由 generation ref 反向合成它们。接受后
generation fence 使旧 generation 全部失效。`current_device_generation_ref` 是 PCR-local monotonic ref，
MUST NOT 使用或等于 DID `versionId`；resolution cell 不随基础恢复推进。

DID-root 只是在 recovery policy 中显式启用、可撤销的一种 proof kind。当前 DID root 本身不能
re-anchor；method 不支持 history/pre-rotation 或 policy 未启用时必须拒绝。只有该分支或用户同时执行
resolution successor 时 transaction 才包含 DID publication；DID host outage 不影响 PCR-policy 分支。

### 14.1 Device lifecycle 与 trust 正交状态

设备 lifecycle 为 `active | revoked | expired | generation_fenced | conflicted`；验证状态为 `verified | unresolved | stale`。业务授权要求 lifecycle=`active`、evidence=`verified`、authorize generation 等于 current generation 且目标 Event basis 被 accepted Seal 覆盖。任何单一条件失败都不能由账号 session、DPoP 或 transport service signature 补足。

### 14.2 Recovery UI requirements

客户端必须在任何网络副作用前 durable 保存 identity root/recovery、device identity、HPKE、DPoP keys 与完整 onboarding/recovery draft。UI 应区分：可 exact retry、genesis 已由另一 unit 赢得、必须 re-anchor、以及无 proof 无法恢复；不得让用户通过再次注册静默替换既有 PCR。

## 15. Applet Device Delegation

Applet 如需代表 Ghost Actor 或桥接用户参与 E2EE，MUST 使用受限 delegated device：

- device id MUST 标记 `applet_id`。
- capability MUST 限制 Realm、协议、动作和有效期。
- delegated device 不得签发新的 human device。
- delegated device 的 to-device 权限 MUST 只覆盖其 namespace 内 actor。
