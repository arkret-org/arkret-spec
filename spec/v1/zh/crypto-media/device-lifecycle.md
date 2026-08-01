---
title: Device Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. Login & Authorization Boundaries

去中心化协议摒弃了传统的账号+密码中心化认证模式，身份的本质是持有私钥。Arkret 把以下三件事分开处理：

- **登录因子验证**：Auth Server 验证 password、passkey、OIDC、SSO 或 recovery factor，只能产出短期 `ak.session.grant`、触发恢复流程、请求已有设备授权，或（外部 enrollment-authority 模型，§5.4）经 `ak.gate.account.command.enroll_device` 请求入册权威签发 `service_attested` 设备授权。
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

`session_public_key` 不仅是会话身份标记，还是会话请求的 proof-of-possession 出示密钥：日常受保护请求 SHOULD 用该 key 对请求做 RFC 9421 HTTP Message Signature（sender-constrained 出示），使会话出示与该 key 绑定，仅截获 `ak.session.grant` 不足以重放。行使该 key 出示的具体形态、覆盖的 components 与 replay window 见 [`../sync/api-conventions.md` §3.2](../sync/api-conventions.md) 与 [`../sync/service-http-binding.md` §2.5](../sync/service-http-binding.md)；高安全 deployment profile 下该 PoP 出示对常规写与敏感读升为 MUST。

资源服务器验证的是 session grant、device authorization、DID proof、capability 和 Realm policy，而不是“用户刚刚输入了正确密码”。密码、SSO session 和 service account id 都不能直接作为 `actor_id`、event sender 或 capability subject。

服务账号密码重置只改变服务账号登录凭据；除非同时存在有效 DID 控制证明或 recovery policy 事件，否则不得自动授予 DID 控制权、不得签发长期 device grant、不得访问 E2EE 密钥备份。

### 1.2 登录、设备授权与设备验证的边界

Arkret v1 把三件事分开处理：

- **登录因子验证**：Auth Server 验证 password、passkey、OIDC、SSO 或 recovery factor，只能产出短期 `ak.session.grant`、触发恢复流程、请求已有设备授权，或（外部 enrollment-authority 模型，§5.4）经 `ak.gate.account.command.enroll_device` 请求入册权威签发 `service_attested` 设备授权。
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
   - 主设备验证 pairing challenge 后，签发 `ak.device.authorize`、符合 DID method 的 key-log operation，或触发 recovery policy 允许的设备授权流程。
   - DID Document SHOULD 只承载身份控制密钥和服务发现入口。普通设备列表、设备信任状态、吊销状态和算法更新 SHOULD 由 `ak.device.*` 事件、device key log 或受控 device registry 表达；只有 DID method 本身要求时，才把设备 verification method 写入 DID Document。
   - 短期浏览器或临时执行环境 MAY 只拿到 `ak.session.grant`，但它不改变长期设备集合，也不得访问 E2EE 历史密钥，除非另有有效设备授权和密钥共享流程。
4. **状态下发**：主设备通过点对点信道或安全的 Sync Service，将必要的工作区快照、加密会话历史（通过 MLS Welcome / Commit 把新设备加入合适的 group）同步给新设备。
5. **事件广播**：主设备向 principal control stream 广播 `ak.device.authorize` 事件；若封装为 Event Envelope，其 `realm_id` 是目标 principal 的 `principal_control_realm_id`。新设备获得的能力由该事件、session grant、Realm capability 和 policy 共同限制，不是自动获得 principal 的全部权限。

#### 2.1.1 短链暂存与 resolve（server-mediated，normative）

§2.1 步骤 1 的“临时连接信息”MAY 由 Principal Server 暂存并以短句柄承载，而非把设备公钥与配对材料整包放进二维码。采用该短链形态时 MUST 满足以下约束；它只改变“配对材料如何到达主设备”这一传输层，不改变 §2.1 步骤 3 的授权模型。

1. **暂存（stage）**：新设备经**免认证**端点 `POST /_arkret/open/device-pairing/requests`（`ak.open.device_pairing.command.stage`）提交 `new_device_pubkey`（canonical `PublicKey`，见 [`public-key.schema.json`](../../artifacts/schemas/public-key.schema.json)：`kty` / `kid` / `alg` / `key` 四字段，`key` 为密钥材料、`kid` 为 `ak:device:<uuidv7>`）与 `client_nonce`，以及可选 `display_name` / `device_metadata`。**stage 请求 MUST NOT 携带 challenge proof**——该 proof 必须承诺 server 在本次调用中才铸出的值，因此在 stage 时不可能存在（这条顺序约束是 §2.1.2 transcript 可生成性的前提）。Server 铸 `device_pairing_request_id`（`device_pairing_request:<uuidv7>`）、短 `pairing_code`、`gate_audience`（本 Account Authority 的 `gate_account_base` origin）与 `server_nonce`，以有界 TTL（SHOULD ≤ 10 分钟）暂存一条 **account-less** 记录（state `pending_authorization`），返回 `{device_pairing_request_id, pairing_code, gate_audience, server_nonce, expires_at}`。暂存记录 MUST 同时保存提交的 `new_device_pubkey` 与 `client_nonce`——它们是 §2.1.2 路径 A transcript 的 member，gate 必须能只凭该记录重算 transcript。暂存记录在被授权前**不绑定任何 principal、不授予任何东西**。
2. **短链承载**：stage 返回后，新设备按 §2.1.2 生成 `challenge_proof`，并由二维码同时承载短 deep-link 与该 proof：`{arkret_base_url}/_arkret/open/device-pairing/resolve#token=<token>&proof=<proof>`，其中 `token = base64url_nopad(canonical_json({"r": device_pairing_request_id, "c": pairing_code}))`，`proof = base64url_nopad(canonical_json(challenge_proof))`。`token` 与 `proof` MUST 仅出现在 URL fragment 或请求 body，MUST NOT 进入 URL path 或 query（避免进入服务端/代理日志）。**proof 走带外通道到达主设备，MUST NOT 经免认证 stage / resolve 面回传给 server**：暂存面是匿名的，让它持有 proof 既无必要也扩大攻击面。
3. **resolve**：已授权设备经**免认证**、body-only 的 `POST /_arkret/open/device-pairing/resolve`（`ak.open.device_pairing.query.resolve`）以 `token` 换取 `DevicePairingBootstrap`（含 `arkret_base_url`、`device_pairing_request_id`、`pairing_code`、`new_device_pubkey`、`client_nonce`、`gate_audience`、`server_nonce`、可选 `display_name`/`device_metadata`、`expires_at`）。已授权设备 MUST 用这些 server-minted 值按 §2.1.2 重算 transcript，并对二维码带来的 `challenge_proof` 完成验签后，才可向用户呈现为可配对设备。随后按 §2.1 步骤 3 走 `ak.gate.account.command.pair_device` 授权：该授权端点仍要求授权方是**已验证设备**，server MUST NOT 因短链暂存本身改变设备集合或放宽授权前置。
4. **回填与 status**：授权端点 MAY 携带 `device_pairing_request_id`。携带时，Account Authority MUST 要求该 id 对应的暂存记录仍为 `pending_authorization` 且未过期，要求记录中的 `pairing_code`、`new_device_pubkey` 与授权请求逐字段一致，并**按 §2.1.2 用该暂存记录自己的字段重算 transcript、验证请求携带的 `challenge_proof`**（逐字段相等比较只能证明字节未被中途替换，不能证明签名对哪个 challenge 或哪个 audience 有效，因此 MUST NOT 用相等比较代替验签）；验证与设备授权落库、暂存记录消费并翻为 `authorized`（记录 `device_id` 与 `authorized_event_ref`）MUST 原子完成，任一不匹配不得授权设备。新设备经**免认证**、body-only 的 `POST /_arkret/open/device-pairing/requests/status`（`ak.open.device_pairing.query.status`）以 `{device_pairing_request_id, pairing_code}` 轮询得到 `{state, device_id?, authorized_event_ref?}`。
5. **防枚举（normative）**：`resolve` 对 {未知 id、`pairing_code` 不符、已过期、非 `pending_authorization`} MUST 返回统一 `not_found`。`status` 对 {未知 id、`pairing_code` 不符} MUST 返回同样的 `not_found`；凭证正确时可返回 `pending_authorization`、`authorized` 或 `expired`，其中 `authorized` MUST 同时携带 `device_id` 与 `authorized_event_ref`，其余状态 MUST 不携带这两个字段。不得通过错误形态泄露 id 是否存在或 code 是否正确。`pairing_code` MUST 使用 §7 定义的 8 位 Crockford-style CSPRNG code，并由暂存、resolve 与 status 端点限速兜底。
6. **有界与清理（normative）**：免认证的 stage、resolve 与 status 端点 MUST 限速；过期暂存记录 MUST 对 `resolve` fail closed，`status` 在凭证正确且记录尚处于有界清理保留期时返回 `expired`，清理后返回 `not_found`。过期记录 SHOULD 被定期清理，Server MUST NOT 无界保留。

#### 2.1.2 Pairing challenge proof transcript（normative）

`challenge_proof` 是新设备对 `new_device_pubkey` 的 possession proof，且**必须绑定本次配对挑战**。它的 wire 形态是 [`device-pairing.schema.json`](../../artifacts/schemas/device-pairing.schema.json) 的 `device_pairing_challenge_proof`（`{transcript, kid, alg, transcript_digest, signature}`），MUST NOT 退化为无语义的 base64url 字节串。`kid` 是选择 staged key 的 device-local `ak:device:` key id（[`did-usage-and-verification.md` §2.3](../identity/did-usage-and-verification.md) 已登记的非 DID 分支），不是 DID URL，因此不得命名为 `verification_method`。

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

- 签名密钥固定为 `new_device_pubkey` 对应的私钥；proof 的 `kid` MUST 逐字节等于 `new_device_pubkey.kid`，`alg` MUST 是 [`signature-alg-registry.json`](../../artifacts/registry/signature-alg-registry.json) 的 active suite 且与 `new_device_pubkey.alg` 相容。
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

**为什么必须绑定这些值**：只签静态公钥的 proof 可跨 request、跨 origin、跨过期窗口重放；只做非空/格式检查等于没有 PoP。`gate_audience` 阻断跨 Account Authority 重放，`pairing_code` + `device_pairing_request_id` + `server_nonce`（或路径 B 的 `transaction_id` + `request_canonical_digest`）阻断跨 request 重放，`expires_at` 阻断过期窗口外重放。

**失败语义**：transcript 重算不符、proof `kid` 与 `new_device_pubkey.kid` 不等、`alg` 不在 active suite、签名验证失败，一律 `failed_precondition`，对外按 §2.1.1 第 5 条的防枚举要求返回统一形态；同一 pairing transcript 累计 10 次失败后按 [`../sync/service-http-binding.md` §3](../sync/service-http-binding.md) 锁定并永久失效。

#### 2.1.3 Pairing challenge 的 conformance 入口

`vector_id`: `ak.vector.device_pairing.challenge_transcript.v1`（向量说明见
[`../conformance/conformance-vectors.md` 23.10](../conformance/conformance-vectors.md)）。它覆盖
stage 到 gate 的 round-trip 正例、同一 `new_device_pubkey` canonical bytes 与 digest 全程不变，
以及坏 audience / 坏 request digest / 旧 pairing code / 跨 request 重放 / 过期 / 改 key / 坏签名 /
proof `kid` 不匹配 / 跨路径复用 proof / 旧 `{kid, alg, public_key}` 形态 /
stage 请求携带 proof 等负向量。

### 2.2 设备吊销

> 吊销后的 MLS secret 与 backup series 轮换 MUST 在一个 `SecurityRotationTransaction` 内进行，
> 且该 transaction MUST 在提交 `ak.device.revoke` **之前**创建：`ak.device.revoke` 一旦 accepted
> 不可回滚，而其后的每一步都是独立远端写。固定顺序、reserved id 与崩溃续跑合同见
> [`../identity/security-transactions.md` §3](../identity/security-transactions.md)。
> 在没有该 transaction 的情况下重试轮换会重新生成 secret 与 series id，而不是续跑首次计划。

当设备丢失时，用户可从任何其他已授权设备、DID 控制密钥或 recovery policy 允许的恢复服务发起吊销操作：发布 `ak.device.revoke`，停止接受该设备的新签名写入，并对受影响的 MLS 群组触发 `Remove` 与 Epoch 更新。若该设备曾被写入 DID Document，撤销流程还必须按 DID method 规则移除或失效对应 verification method。

`ak.device.revoke` 是 principal control stream 上的 Control Move：其 Event Envelope MUST 携带 `seal_basis`（撤销方签名时观察到的 accepted Seal view `{leaves[], control_event_set_root, state_root}`，进入 canonical event bytes 并被撤销证明签名覆盖，见 `../authz/event-auth-state-resolution.md` §5）；payload 不携带任何 frontier 字段。客户端铸造单 leaf basis 的注册来源是 `ak.self.events.query.frontier?realm_id=<principal_control_realm_id>`（Realm Seal view `{realm_id, seal_id, control_event_set_root, state_root, hlc?}`，取 `leaves=[seal_id]`）；该来源不可用时 MUST fail closed，不得伪造 basis。撤销自被 accepted Seal 覆盖（`control_sealed`）起生效；Principal Server / Sync Service 在拒绝该设备后续 session grant、KeyPackage、to-device write 或 Event write 时，MUST 以该 covering Seal 或其后继 Seal view 作为判定依据，不得用本地布尔缓存替代。

**accepted→sealed 窗口的预先 fail-closed（normative）**：撤销已被受理服务 accepted、但尚未被 covering Seal 覆盖（`control_sealed`）的窗口内，受理服务对该设备后续 session grant / KeyPackage / to-device write / Event write 的处置规则按 profile 分级：

- 通用部署 SHOULD 在该窗口内预先 fail closed（拒绝该设备的上述请求）。
- **声明 `ak.profile.e2ee_client.v1` 或任何专门 hardening / 高安全 deployment profile（如 `high_security_organization` / `sovereign_deployment`）的部署 MUST 在该窗口内预先 fail closed**——高安全语境下"撤销已提交即不再为该设备服务"是硬承诺，不得在等待 Seal 期间继续放行被撤销设备的写入或密钥获取。
- receipt→decision 窗口 MUST 服从 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §7.2 的 proposal 有界决议合同；它保证 include / signed-reject / bounded signed-defer 之一，不保证 proposal 被接受，也不是 Seal finality SLA。设备撤销 proposal 尚未进入 accepted Seal 时，若旧授权安全性无法证明，受理服务 MUST fail closed；MLS-backed scope 另受 [`encryption-and-audit.md` §2.4](../crypto-media/encryption-and-audit.md) `max_mls_commit_delay_ms` 发送阻塞窗口约束。迟到但有效的 Seal 仍按 CBA 规则接受，decision-overdue fault 保留。

共享 E2EE Realm 不能只看到“某设备已撤销”的服务端布尔值就推进新 epoch。对应 `ak.mls.commit` Remove 的 `governance_binding.membership_frontier` MUST 覆盖该 `ak.device.revoke` 事件本身，或覆盖一个已经把该撤销导入 Realm governance state 的显式 Control Move，且该撤销 MUST 已被 principal control stream 的 accepted Seal 覆盖；否则该 Remove 不满足 MLS Governance Binding，新的 `covered_seals_cell` 不得声称已覆盖该设备撤销。


## 3. 企业单点登录 (SSO / OIDC Gateway)

企业通常强制要求使用 Okta、Google Workspace 等中心化身份提供商 (IdP) 进行认证。在不破坏去中心化端到端加密前提下，本协议引入 **Auth Gateway (认证网关)** 模式。

### 3.1 架构角色
- **Auth Gateway**：部署在企业内网或受控云端的高安全级别服务器。它通常是组织 DID 明确声明的 session grant issuer 或设备授权服务。只有在企业托管账号场景中，它才 MAY 托管员工 DID 的高权限签发材料；对普通个人 DID，网关 SHOULD 只签发短期 session grant，不应托管用户 principal signing key 或 recovery key。

### 3.2 登录时序
1. **浏览器会话初始化**：员工在浏览器打开 Web 端应用，本地生成临时会话密钥 `session_key`。
2. **OIDC 重定向**：浏览器跳转至企业 Okta 完成标准的 OAuth2 / OIDC 身份认证。
3. **网关授权 (Gateway Delegation)**：Okta 认证成功后回调 Auth Gateway。Gateway 验证员工身份无误后，签发短期、受众绑定、scope 受限的 `ak.session.grant`，把 `session_key_pub` 绑定到目标 DID principal、设备、origin、audience、过期时间和允许的 operation 集合。其中绑定的设备 MUST 是客户端持有的稳定协议 `device_id`（`ak:device:<uuid>`，由客户端在认证时显式声明，例如 OAuth `urn:arkret:client:device:<id>` scope 透传到 introspection 的 `org.arkret.device_id` claim）。资源服务器 MUST NOT 从 token / session 标识（如 `jti` / `session_id`）派生或伪造一个 per-token 的 `device_id`——这违反 §4「服务端不得伪造 device identity」，且会让该值在每次 token 轮换时漂移，静默破坏所有按 `(principal, device)` 绑定的不变量（sync cursor 主体/设备匹配、key backup 写入设备授权）。携带认证材料但缺少稳定 device 绑定的会话 MUST 对 device-scoped 操作 fail-closed 拒绝，而非降级放行。
4. **会话生效**：浏览器操作必须同时附带 session grant、device proof 或等价绑定证明。常规写与敏感读 SHOULD 进一步用 `session_key`（即 grant 委托的 `session_public_key`）对每个请求做 RFC 9421 HTTP Message Signature 出示（sender-constrained / PoP，见 [`../sync/api-conventions.md` §3.2](../sync/api-conventions.md)），使会话请求与该 key 绑定，截获 token 不足以重放；高安全 deployment profile 下该出示升为 MUST。资源服务器仍 MUST 重新验证 DID control state、capability、Realm policy、grant scope、audience、origin 和重放状态；不得因为 OIDC 成功就把请求视为 DID 控制证明。
5. **平滑过期**：session grant SHOULD 使用分钟到小时级 TTL，并支持即时撤销。

### 3.3 设备持有绑定与 grant 轮换（normative）

为在「会话凭据短期有效」与「设备会话可跨多日免重登」之间取得一致,session grant 采用 **grant-binding key 持有绑定 + 滚动轮换**模型:

- **持有绑定(cnf.jkt)**:签发 `ak.session.grant` 时,Auth Server MUST 要求客户端出示一个由其 **grant-binding key**(即 DPoP key,RFC 9449 DPoP 式持有证明)签名的 proof,并把该 key 的 RFC 7638 JWK 指纹写入 grant 的 `cnf.jkt`(RFC 7800 confirmation)。`cnf.jkt` 把 grant 绑定到「持有该私钥的会话/设备」,而非仅记一个 `device_id` 字符串。
- **grant 直接出示、短期轮换**:Principal Server 不铸第二个本地会话凭据；客户端以 `ak.session.grant` + DPoP 直接访问 `/_arkret/self/*`。grant 自身为分钟到小时级 TTL，客户端在 grant 临期时用**仍有效的 grant** 与同一 grant-binding key 轮换出新 grant。
- **轮换(rotation)**:grant 临近自身过期时，客户端用**同一 grant-binding key** 签 DPoP 持有证明，向 Auth Server 的 session-grant 轮换端点(见 [`../sync/service-http-binding.md` §2.3](../sync/service-http-binding.md))换出一张新 grant。Auth Server MUST 校验 proof 的 JWK 指纹等于旧 grant 的 `cnf.jkt`(证明持有同一 grant-binding 私钥)，新 grant 保持 `cnf.jkt` 不变、刷新过期、继承 subject/scope/audience；旧 grant MUST 单次使用吊销。如此滚动使设备会话存活到天级，**直到设备被吊销、grant 链被吊销、或底层 `browser_session` 被终结(登出)**——三者任一即拒绝继续轮换(见 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md))。
- **不引入长期离线续期凭据**:本协议以「grant-binding key 轮换 grant」承担续期职责,grant 自身保持分钟到小时级 TTL;不依赖、也不要求签发 OAuth `offline_access` 类长期续期凭据。
- **登出即终结**:轮换链挂靠在 Auth Server 的 `browser_session` 上；`browser_session` 被登出终结后，即便持有正确的 grant-binding 私钥(指纹匹配 `cnf.jkt`)也 MUST NOT 再轮换出新 grant——续期必须重新走完整认证。

**grant-binding key 与设备身份 key 的生命周期正交(normative)**:`grant-binding key` 是**会话认证凭据**,`cnf.jkt`、`ak.session.grant` 轮换与 hard-logout 清除只作用于它；它按 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md) 在 hard logout 时被清除、下次登录轮换,soft recovery 路径保留。§5.2 的**设备身份 key**(`device_public_key` / `verify_key`,签事件 / KeyPackage / MLS leaf)是 E2EE 信任根，只经 `ak.device.revoke` + 重新入册轮换。二者必须独立生成、独立存储并独立轮换：grant-binding key 的私钥字节、公钥字节、JWK thumbprint 与 `kid` 都 MUST NOT 等于或复用设备身份 key 的对应材料。违反该分离要求的会话或设备授权 MUST fail closed。会话生命周期(登录 / 登出 / grant 轮换)MUST NOT 触发设备身份 key 的重铸(见 §5.2)。

此模式只把 Web2 SSO 作为登录因子和会话授权输入。它不授予 E2EE 密钥访问权，不自动创建长期设备，不替代 `ak.device.authorize`、DID/key-log operation 或 recovery policy。


## 4. Device Identity

每个设备 MUST 有稳定 `device_id` 和设备签名密钥。`device_id` 的类型是 `id:device`，wire form MUST 为完整 `ak:device:<uuid>`；当它出现在 JSON object key 中时也同样适用，不得改写成局部别名：

```json
{
  "device_id": "ak:device:019640dd-8000-7000-8000-000000000000",
  "principal_id": "did:webvh:...",
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

设备记录的授权链按模型分流：A 模型由当前 SSK（创世槽位例外为 DID-delegated enrollment key）签名；B 模型始终由 DID-delegated enrollment authority 签名并受 device-generation fence 约束。服务端不得伪造 device identity。

## 5. Signing Hierarchy

仅 A 模型使用以下三层 cross-signing 链；B 模型 MUST NOT 发布该链，而使用 enrollment authority + device generation fence：

- `principal_signing_key`：DID 控制层，负责发布和轮换账户级签名根。
- `self_signing_key`：签名本 principal 的设备。
- `user_signing_key`：签名其他 principal 的 identity key，表达人工验证后的信任。

`self_signing_key` 和 `user_signing_key` SHOULD 存入加密 secret storage，并通过新设备验证后共享。

#### 5.0 Principal 身份模型归一决策表（normative）

v1 并存两套设备入册信任根，但二者不是对等可选：B 模型（外部 enrollment authority）是 v1 权威路径，A 模型（principal 自主权 + cross-signing）是受限形态。两者创世时都由 DID Document delegation 指派专用 enrollment authority，并使用 `enrollment_authority_binding`；差异由 `authority_did` 的归属决定，不由 binding 名称决定。

| principal 身份模型 | DID delegation | 日常 `ak.device.authorize` binding | 恢复 generation | 状态 |
| --- | --- | --- | --- | --- |
| **B：external enrollment authority** | `ArkretDeviceEnrollmentAuthority` service 指向外部 authority DID | 创世/日常/恢复 authorize 均用 `enrollment_authority_binding`；全设备丢失时与 `ak.device.reanchor` 原子提交 | DID-version `current_device_generation_ref` fence | **权威（v1 默认）** |
| **A：principal-owned authority + cross-signing** | `capabilityDelegation` 指向 principal 自持专用 enrollment key；DIDDoc 另含独立 PSK VM | 创世 authorize 用 `enrollment_authority_binding`；PSK 发布 SSK/USK 后，日常/恢复 authorize 用 `cross_signing_binding` | SSK generation；不得建立 B generation fence | **受限** |

判定函数（receiver MUST 单一入口执行，不得按本地偏好在 A/B 间漂移）：

1. 解析 authorizing DID entry/document 的 delegation 与 `authority_did`。
2. `authority_did != principal_id` ⇒ B 模型；control stream MUST NOT 出现 `ak.cross_signing.publish`，fresh-device recovery 必须走 re-anchor unit。
3. `authority_did == principal_id` ⇒ A 模型；创世 enrollment binding 不阻止后续 `ak.cross_signing.publish`，日常与 fresh-device recovery 使用 SSK generation。
4. authority 未被 delegation 指派、归属含混、或同一 stream 同时出现 A/B generation state ⇒ fail closed。

下文 §5.1–§5.2 定义 A 模型 cross-signing，§5.3 定义两模型共用的 delegated genesis，§5.4 定义 enrollment-authority 验证；§8.2/§8.3 的普通事件验签统一读取设备集投影。

### 5.1 Cross-Signing Publish Envelope（A 模型 only）

A 模型 `self_signing_key` (SSK) 与 `user_signing_key` (USK) 的公钥 MUST 通过 `ak.cross_signing.publish` 事件公布到 principal control stream。该事件确立"PSK → {SSK, USK}"绑定；PSK `kid` MUST 解析到 entry 0 或当前 DID head 中 A 模型专用 `verificationMethod` / `assertionMethod`，不得是 identity root、enrollment key 或 device key。B 模型出现该 event 必须 fail closed。

Schema id：`ak.schema.cross_signing_publish.v1`

```json
{
  "kind": "ak.cross_signing.publish",
  "realm_id": "<principal_control_realm_id>",
  "actor_id": "did:webvh:...",
  "payload": {
    "principal_id": "did:webvh:...",
    "trust_domain": "ak:trust_domain:did.webvh.example",
    "principal_signing_key": {
      "kid": "did:webvh:...#ak_principal_signing_v1",
      "alg": "EdDSA",
      "public_key": "z6Mk...",
      "key_format": "multibase"
    },
    "self_signing_key": {
      "kid": "did:webvh:...#ak_self_signing_v1",
      "alg": "EdDSA",
      "public_key": "z6Mk...",
      "key_format": "multibase",
      "binding": {
        "verification_method": "did:webvh:...#ak_principal_signing_v1",
        "alg": "EdDSA",
        "signature": "base64url..."
      }
    },
    "user_signing_key": {
      "kid": "did:webvh:...#ak_user_signing_v1",
      "alg": "EdDSA",
      "public_key": "z6Mk...",
      "key_format": "multibase",
      "binding": {
        "verification_method": "did:webvh:...#ak_principal_signing_v1",
        "alg": "EdDSA",
        "signature": "base64url..."
      }
    },
    "expected_previous_generation": 0,
    "generation": 1,
    "issued_at": "2026-04-26T00:00:00Z"
  }
}
```

Payload-only schema 示例（即 Event `payload` / 上例 `payload` 的规范形态）：

```json schema=schemas/cross-signing-publish.schema.json
{
  "principal_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
  "trust_domain": "ak:trust_domain:did.webvh.example",
  "principal_signing_key": {
    "kid": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#ak_principal_signing_v1",
    "alg": "EdDSA",
    "public_key": "AA",
    "key_format": "raw_base64url"
  },
  "self_signing_key": {
    "kid": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#ak_self_signing_v1",
    "alg": "EdDSA",
    "public_key": "BB",
    "key_format": "raw_base64url",
    "binding": {
      "verification_method": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#ak_principal_signing_v1",
      "alg": "EdDSA",
      "signature": "c2ln"
    }
  },
  "user_signing_key": {
    "kid": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#ak_user_signing_v1",
    "alg": "EdDSA",
    "public_key": "CC",
    "key_format": "raw_base64url",
    "binding": {
      "verification_method": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#ak_principal_signing_v1",
      "alg": "EdDSA",
      "signature": "c2ln"
    }
  },
  "expected_previous_generation": 0,
  "generation": 1,
  "issued_at": "2026-04-26T00:00:00.000Z"
}
```

字段规则：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `principal_signing_key` | required | PSK 当前公钥引用。`kid` MUST 出现在该 principal 当前 DID document 或 key-log head 的 verification methods 中；服务端不接受 `kid` 不在当前控制集中的 publish。 |
| `trust_domain` | required | 部署级 trust domain（`ak:trust_domain:<scope>`）。Receiver MUST 在验证任一 binding 签名前先检查该值与当前接收上下文一致；不一致 MUST `cross_domain_replay_rejected`。 |
| `self_signing_key` | required | SSK 公钥 + 由 PSK 对 canonical SSK record 的签名。`binding.verification_method` MUST 逐字节等于 `principal_signing_key.kid`：验证方必须能唯一确定验签用的 PSK，不得在多 PSK verification method 之间逐个试签。若未来要支持 PSK 轮换窗口内的双 method，必须新增显式判别字段，不得放宽本相等约束。 |
| `user_signing_key` | required | USK 公钥 + 由 PSK 对 canonical USK record 的签名；MUST 与 `self_signing_key` 不同 `public_key`。其 `binding.verification_method` 受与 `self_signing_key` 同一条约束：MUST 逐字节等于 `principal_signing_key.kid`。 |
| `expected_previous_generation` | required | CAS precondition。首次 publish 使用 `0`；后续 publish MUST 等于 receiver 当前 accepted generation。 |
| `generation` | required | 单调递增整数。每次 cross-signing reset（§14）MUST `generation += 1`。Receiver 见到 `generation` 比已 accepted 状态低的 publish MUST 拒绝。 |
| `issued_at` | required | 发布时间；MUST be no later than 接收方本地时钟 + protocol skew。 |

`binding` 的 canonical signing input：

```text
"ak.cross-signing-bind-v1\n"
+ canonical_json({
    "principal_id": <did>,
    "trust_domain": <trust_domain>,
    "subordinate_key_kind": "self_signing" | "user_signing",
    "subordinate_kid": <kid>,
    "subordinate_alg": <alg>,
    "subordinate_public_key": <public_key>,
    "generation": <generation>
  })
```

服务端 MUST 拒绝 `subordinate_alg` 不在协议算法 registry 中、或 `subordinate_public_key` 与 binding 输入声明不一致的 publish。Reducer 接受 publish 前还 MUST 校验 `payload.expected_previous_generation == current accepted generation` 且 `payload.generation == payload.expected_previous_generation + 1`；同一控制提交批次内若 reset 与 stale publish 并发，stale publish 因 head precondition 不成立而 fail closed，不得依赖本地到达顺序。

`trust_domain` 绑定（normative）：`ak.cross_signing.publish` 与 §14 的 reset 使用同一 deployment-scope replay boundary。Receiver MUST 在解析 publish 时先检查 `payload.trust_domain == current_receive_context.trust_domain`；不匹配时直接拒绝，不得把该 publish 纳入 accepted generation。由于 `trust_domain` 也进入 PSK 对 SSK / USK 的 binding transcript，同一 publish bytes 从 deployment A 搬到 deployment B 时签名 transcript 不同，验证必然失败。

### 5.2 Device Trust Chain

设备 trust state 由以下链推导，**不允许跳层**：

```text
DID-method history → principal_signing_key (PSK)
                       ├── self_signing_key (SSK)   ── signs ──► device.verify_key
                       └── user_signing_key (USK)   ── signs ──► other principal's verify_key
```

**设备身份 key 稳定性(normative)**:设备的 `device_public_key`(= `verify_key`,per-device Ed25519)是该设备的 E2EE 信任根，签事件、KeyPackage 与 MLS leaf,并投影进设备验签公钥目录(§8.2)供 receiver 解析。它**只经 `ak.device.revoke` + 以新 key 重新入册(= 新设备)轮换**;会话生命周期——登录、登出、`ak.session.grant` 轮换——**MUST NOT** 触发它的重铸或覆盖。与之相对,§3.3 的 grant-binding(DPoP)key 是会话认证凭据，按 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md) 随登出/重登轮换；二者生命周期和密钥材料均必须分离，任何字节、JWK thumbprint 或 `kid` 复用都不合规(见 §3.3)。

每条 `ak.device.authorize` 事件 MUST 在 `payload.cross_signing_binding` 字段携带 SSK 对该设备 `verify_key`、`hpke_key` 与声明算法集合的签名：

```json
{
  "kind": "ak.device.authorize",
  "payload": {
    "principal_id": "did:webvh:...",
    "device_id": "ak:device:...",
    "device_public_key": "z6Mk...",
    "hpke_key": "z6LS...",
    "algorithms": ["ak.hpke_x25519_aead_chacha20poly1305.v1", "ak.mls.v1"],
    "cross_signing_binding": {
      "verification_method": "did:webvh:...#ak_self_signing_v1",
      "alg": "EdDSA",
      "ssk_generation": 1,
      "signature": "base64url..."
    },
    "...": "..."
  }
}
```

`cross_signing_binding` 的 canonical signing input：

```text
"ak.device-trust-bind-v1\n"
+ canonical_json({
    "principal_id": <did>,
    "device_id": <id:device>,
    "device_public_key": <public_key>,
    "hpke_key": <hpke_public_key>,
    "algorithms": <sorted_unique_algorithm_ids>,
    "ssk_generation": <ssk_generation>
  })
```

`algorithms` 在进入 signing input 前 MUST 按 UTF-8 bytewise 升序排序并去重；producer MUST 在 `ak.device.authorize.payload.algorithms` 中写入同一 canonical 数组。`hpke_key` 与 `device_public_key` 均为该设备授权记录的一部分，MUST 逐字节进入签名输入；receiver MUST NOT 接受只覆盖 verify key 而不覆盖 HPKE 密封 key 的 `cross_signing_binding`。

当 `ak.device.authorize.payload.device_signature` 出现时，它 MUST 是由该 payload 中 `device_public_key` 对应的**设备身份 key 私钥**签出的 possession proof。该签名不是 SSK 签名；SSK 只签 `cross_signing_binding`。该签名也 MUST NOT 使用 grant-binding（DPoP）key、`session_public_key` 或 grant `cnf.jkt` 对应私钥；这些是会话授权凭证，不是设备身份。receiver MUST 用 `device_public_key` 验证 `device_signature`，失败时拒绝该 `ak.device.authorize`。在 recovery strand（§15）产生的 `ak.device.authorize` 中，`device_signature` REQUIRED，因为服务端不得在只看到 SSK 授权时假定恢复客户端持有新设备私钥。

`device_signature` 的 canonical signing input：

```text
"ak.device-authorize-possession-v1\n"
+ canonical_json({
    "principal_id": <did>,
    "device_id": <id:device>,
    "device_public_key": <public_key>,
    "hpke_key": <hpke_public_key>,
    "algorithms": <sorted_unique_algorithm_ids>,
    "device_key_algorithm": <algorithm>,
    "authorized_by": <device_or_principal_ref>,
    "not_before": <timestamp>,
    "expires_at": <timestamp_or_null>,
    "scopes": <sorted_unique_scope_ids_or_null>,
    "recovery_session_id": <id:recovery_session_or_null>,
    "authorization_binding_kind": "cross_signing" | "enrollment_authority",
    "cross_signing_generation": <ssk_generation_or_null>
  })
```

`device_key_algorithm` MUST be `EdDSA`/`Ed25519` for v1 `device_signature` verification. Optional `expires_at`, `scopes`, and `recovery_session_id` are normalized to `null` when absent; `scopes` is sorted and deduplicated before signing。`authorization_binding_kind` 只描述实际授权制度：A 模型为 `cross_signing`，B 模型以及 A 模型 delegated bootstrap 的首设备路径为 `enrollment_authority`；bootstrap unit 是 batch 上下文，不是第三种 binding kind，MUST NOT 编码为 `bootstrap`。Signature bytes、`device_signature`、`proof` 与 nested authorization-binding signature material 被排除以避免循环；`authorization_binding_kind` 加 `cross_signing_generation` 把 possession proof 绑定到授权制度与 cross-signing generation。

#### 5.2.1 验证算法（normative）

接收方判定 `device` 是否 cross-signed 时 MUST 执行：

1. 解析 principal control stream 中 `accepted_generation = max(publish.generation)` 的 `ak.cross_signing.publish` 事件作为当前 PSK / SSK / USK。
2. 校验 `publish.principal_signing_key.kid` 出现在该 principal DID method 当前控制集中。
3. 校验 `publish.self_signing_key.binding.verification_method` 与
   `publish.user_signing_key.binding.verification_method` 均逐字节等于
   `publish.principal_signing_key.kid`（不等 MUST 拒绝整个 publish，不得改用其它 PSK
   verification method 试签），然后校验两个 `binding.signature` 由该 PSK 对 §5.1
   canonical 输入签名。
4. 在该设备的最新 accepted `ak.device.authorize` 事件中判定授权 regime：
   - 若存在 `enrollment_authority_binding.kind="service_attested"`，receiver MUST 在当前 principal-control frontier 重新执行 §5.4 的入册权威委派、按时点签名、payload-to-projection 相等与未吊销校验。全部通过时 trust state 直接为 `verified`；任一步失败为 `unverified`。该分支不要求 `cross_signing_binding`，并以 accepted `device_authorize_event_id` 作为可复算锚。
   - 否则读取 `cross_signing_binding`；若缺失 MUST 视为 `unverified`，不得回退到"已授权 ⇒ cross-signed"。
5. 比较 `cross_signing_binding.ssk_generation` 与 `accepted_generation`：
   - 相等：用当前 SSK 公钥校验签名，签名输入 MUST 覆盖该设备当前 `device_public_key`、`hpke_key`、canonical `algorithms` 与 `ssk_generation`；通过则 `cross_signed`，失败则 `unverified`。
   - 小于：cross-signing 在该设备签发后已重置；设备 trust state MUST 强制降为 `needs_reverification`（见 §14）。
   - 大于：未来 generation；MUST 视为 `unverified` 并触发 stream re-sync。
6. 跨 principal 信任（USK 签对方 PSK / device key）按对称流程执行：本端 USK binding 必须签发对方 PSK 的 `(kid, generation)` 元组而不是裸公钥，避免对方静默轮换 PSK 后仍继承信任。

实现 MUST 把"未携带 `cross_signing_binding` 的 `ak.device.authorize`"与"binding 校验失败"区分上报：前者仅允许于 [`identity/key-management.md` §5.0.1](../identity/key-management.md) inception bootstrap 或上述 `service_attested` 入册分支，后者属于密码学异常。

#### 5.2.2 设备 lifecycle × trust 正交状态机（normative）

设备状态由**两个正交维度**构成，二者独立演进、不可互相替代：

- **Lifecycle 维度**：`active`（`ak.device.authorize` 在效）↔ `revoked`（显式 `ak.device.revoke` 已吊销，或所属 account 的 accepted `ak.account.status=deactivated` 触发 §5.2.3 级联）。`revoked` 是 **terminal**——一旦吊销，该 `device_id` MUST NOT 被复活；重新启用需新设备新 `device_id` 走新 `ak.device.authorize`。目录态投影见 §8.2 `device_status`。
- **Trust 维度**：`unverified` / `cross_signed` / `needs_reverification` / `verified`，由 §5.2.1 验证算法 + §14 reset 规则驱动。

两维度正交关系与合法转换如下：

| | trust=`unverified` | trust=`cross_signed` | trust=`needs_reverification` | trust=`verified` |
| --- | --- | --- | --- | --- |
| lifecycle=`active` | 初始态 / binding 缺失或校验失败（§5.2.1 步骤4） | §5.2.1 步骤5 binding 校验通过（generation 相等） | §5.2.1 步骤5 generation 小于（旧 binding）或 §14.2 reset 扩散 | SAS/QR 人工验证成功（§10.5）或入册权威背书路径 |
| lifecycle=`revoked` | （吊销后 trust 维度冻结，见下） | — | — | — |

正交转换规则：

- **trust 出边**：`unverified → cross_signed`（binding 校验通过）；`unverified → verified`（§5.4 service-attested 入册链完整通过）；`cross_signed → verified`（人工 SAS/QR 验证）；`cross_signed`/`verified → needs_reverification`（cross-signing reset，§14.2 或 binding generation 落后）；`needs_reverification → cross_signed`（被新 generation SSK 重新 cross-sign，即出现 `ssk_generation == accepted_generation` 的有效 binding）；`needs_reverification → verified`（重新 cross-sign 后再次人工验证，或 service-attested 入册链在新 frontier 重新成立）。`verified` 不直接降回 `cross_signed`（人工信任只被 reset 显式作废为 `needs_reverification`）。
- **lifecycle 出边**：`active → revoked` 只能由显式 `ak.device.revoke` 或所属 account 的 terminal deactivation fanout 触发，terminal，无逆边。两条路径都 MUST 在同一 reducer transaction 产生 device-list update；deactivation 级联不得伪造一条未由合法 actor 签发的 `ak.device.revoke` Event。
- **revoked 设备的 trust 取值**：设备进入 `revoked` 后其 trust 维度**冻结**为吊销时刻的值且不再用于任何信任判定——receiver MUST 把 revoked 设备一律当作不可用于验签 / 不可接收新密钥（§8.2 / §9：`device_status != active` 即 fail-closed），无论其冻结的 trust 值为何。trust 维度仅对 `active` 设备有协议意义。
- **非法迁移**：从 `revoked` 转出任何 lifecycle/trust 态 MUST 被拒绝（视为陈旧投影，按 control 流 frontier fail-closed）。

### 5.3 Delegated Genesis Enrollment

首台设备不得由 identity root 自授权。它必须作为 [`identity/key-management.md` §5.0.1](../identity/key-management.md) PCR bootstrap unit 的第二条 Event，使用 `enrollment_authority_binding`；authority 与 `authorization_ref` 必须精确命中 entry 0/document 中的窄 delegation。第一条 PCR create 由 cold root 锚定，第二条 authorize 由独立 enrollment key 签名；两条原子接受。这是 bootstrap 唯一特殊点，不引入第三种 binding。

A 模型的 authority DID 等于 principal DID，delegation method 是专用 enrollment key而非 device key；接受创世 authorize 后 MAY 发布 `ak.cross_signing.publish`。B 模型 authority DID 是外部账号权威，MUST NOT 发布 SSK/USK。receiver 必须按 authority 归属 fail closed。

### 5.4 委派账号权威入册（`service_attested`）

当设备使用 delegated enrollment path 时，信任根是 DID Document 指派的 enrollment authority，而非 identity root。该路径下 `ak.device.authorize` MUST 携带 `enrollment_authority_binding`，不得同时携带 `cross_signing_binding`：

```json
{
  "enrollment_authority_binding": {
    "kind": "service_attested",
    "authority_did": "did:webvh:.../auth-server",
    "authorization_ref": "did:webvh:<principal>#device-enrollment"
  }
}
```

该 Event 信封 MUST 采用委派执行形态：`actor_id=principal DID`，`executed_by=authority_did`，`authorization_ref` 指向 `ArkretDeviceEnrollmentAuthority` service 或 `capabilityDelegation` method。proof verification method 映射到 `executed_by`。enrollment key 是持久、窄权的独立 key；identity root 始终冷持有。外部 Auth Server MUST NOT 持有或伪造 principal 的 root/SSK。

该 Event payload MUST 显式携带 `device_public_key`、`hpke_key` 与 canonical `algorithms` 数组；入册权威的 Event proof 通过 `event_digest` 覆盖这些字段。`algorithms` MUST 按 UTF-8 bytewise 升序排序并去重。Receiver MUST 拒绝缺失 `hpke_key`、缺失 `algorithms`、或只由入册权威证明 verify key 而未证明 HPKE 密封 key 的 `service_attested` 设备授权。

receiver 接受 `service_attested` 的 `ak.device.authorize` 时 MUST 校验：

1. `authority_did`（= `executed_by`）确为 principal DID 文档**在本 Event accepted-at 时点解析**所指派的入册权威（按时点解析见下），且 `authorization_ref` 委派覆盖设备授权动作；不满足则 `reject`，reason `device_enrollment_authority_not_designated`。
2. `proofs[]` 用入册权威 DID **按时点解析**得到的签名公钥验签通过。
3. `proofs[]` 覆盖的 canonical Event payload 中的 `device_public_key`、`hpke_key` 与 `algorithms` 必须逐字节等于进入设备集投影的 verify key、HPKE key 与算法集合；任何投影替换或重排后不等 MUST fail closed。

`device_id` 是 principal 作用域内的 typed id（`ak:device:<uuid>`），由客户端在该会话内一致使用；入册产生的 `device_public_key` 投影写入设备行时即以该 `device_id` 为键，与会话/恢复查找口径一致。

被接受后，该 device 的 `device_public_key` 作为 principal DID 下的 verification method 进入**设备集投影**（device-set projection），它**不**写入 DID method 的 key log。B 模型的设备信任根是 enrollment-authority 背书 + active device generation fence，SSK cross-signing 在该模型中被禁止而非“可选增强”。A 模型创世槽位使用同一 enrollment binding，后续切换到 §5.2 cross-signing；两种状态机不得混用。

**两套验证 regime（normative）：**

- **入册时（低频）：** 如上，通过解析入册权威 DID 校验 `ak.device.authorize`。
- **普通事件热路径（高频）：** receiver **MUST NOT** 为校验普通业务事件而在线解析 principal DID。普通事件 `proofs[].verification_method` 形如 `{principal_did}#{device_id}`，fragment 即 `device_id`；receiver 从**当前 principal-control 流 frontier 的设备集投影**取该 device 的 `device_public_key` 验签，device 缺失或已吊销即 `reject`。吊销一致性由 control 流 frontier 保证，防止 stale 投影放行已撤销设备。

**按时点解析（normative）：** 历史 `ak.device.authorize` 的复验（审计 / 联邦 replay）MUST 按该 Event 的 server-sealed accepted-at，对入册权威 DID 做按时点解析（`did:webvh` 历史 `versionTime`），用当时有效的入册密钥验签；因此入册权威轮换其签名密钥**不会**使既有授权失效。设备集投影的历史复算同样按时点进行。

**客户端请求入口（normative）：** 客户端经 `ak.gate.account.command.enroll_device` 请求 authority proof。普通入册请求必须用当前 session grant + DPoP；PCR bootstrap 与 verified recovery session 使用各自的受限一次性授权上下文，不得要求尚不存在的普通 device grant。authority 只签最终 `ak.device.authorize` digest，客户端原样提交；服务端不得替换 device key、HPKE key、algorithms、event id 或 actor chain。

## 5a. Privacy-Preserving Push

Arkret 推送通道设计的目标是在不向 push gateway / vendor、上游 Sync Service、网络中间人或第三方 SaaS 控制面泄露身份与可链接信息的前提下，把"有事可投递"的最小信号送达终端。这是 [`discovery/push-notifications.md`](../discovery/push-notifications.md) 与 [`crypto-media/webrtc-signaling.md`](./webrtc-signaling.md) 中"pairwise pseudonym `push_target_id`"语义的协议层定义。

### 5a.1 `push_target_id` 派生与作用域

- 作用域：`per (recipient_service_id, principal_id, device_id, push_route)`。`recipient_service_id` 是当前 Realm membership delivery binding 指向的 Principal Server service DID；同一 DID 在个人 Principal Server 与组织 Principal Server 上注册同一物理设备时，MUST 使用互相不可链接的 `push_target_id`。`push_route` 标识同一设备上不同 push 通道（如 `apns_main`, `fcm_voip`, `webpush_default`），允许同一设备针对不同通道发布相互不可链接的伪名。
- 长度：`push_target_id` MUST 至少 128 bit 熵，编码为 base64url（最少 22 字符）；推荐 256 bit。`high_security_organization`、`sovereign_deployment` / `isolated_sovereign_network` 等高安全 deployment profile MUST 使用 ≥ 256 bit 熵（不可链接性是这些场景的硬隐私属性，128 bit 仅为通用下限）。
- 不可推导性：`push_target_id` MUST NOT 由公开 DID、`device_id`、平台 push token、handle、邮箱或电话号码可推导。生成方式 SHOULD 是 device-local 随机；设备 MAY 用本地 secret 与 `push_route` 派生，前提是源 secret 不可被服务端取回。
- 标识形态：典型 wire 形态为 typed ID `ak:pseudonym:push:<base64url>`，由 `id-kind-registry.json` 中 `pseudonym` 项授权使用；也可作为 raw base64url 字符串出现在 `ak.device.push_route` 等 actor-private state event payload 中。

### 5a.2 注册与撤销

- 设备 MUST 通过 `ak.device.push_route` actor-private state Event 把 `(recipient_service_id, principal_id, device_id, push_route, push_target_id, push_gateway_did, encryption_key, capabilities)` 写入当前投递 Principal Server 可见的 principal control stream 或等价 actor-private state；该 Event 不携带 CBA reducer 字段，不进入 shared Realm Seal coverage。目标 actor-private cell 的 `cell_subject` 由 canonical `contract-registry.json` 的 `event_kind_registry.actor_private_contracts` 声明为 composite `(payload.recipient_service_id, payload.principal_id, payload.device_id, payload.push_route)`，family 使用 `cas_register` 且 `bottom=reject`；schema registry 只负责 payload 形状，不是 merge 真相源。`recipient_service_id` MUST 与 [`governance/member-delivery-binding.md` §2](../governance/member-delivery-binding.md) 接受准则中该 device 所属 member 的 `delivery_binding.recipient_service_id` 一致；推送注册按 `(recipient_service_id, principal, device, push_route)` 维度隔离，同一 DID 在不同 Principal Server 上下文中的 push route 不共享、不可关联。
- 撤销：设备 MUST 在同一 actor-private cell 上写后继 `ak.device.push_route` event 设置 `revoked: true` 或重新写入新 `push_target_id`；service / gateway MUST 在 actor-private state 收敛后停止接受旧伪名。
- 轮换：客户端 SHOULD 在 push token 变化、设备恢复、Out-of-band 重新登录、或自定义 rotation 周期（默认 ≤ 90 天）时轮换 `push_target_id`。
- 长期不可恢复性：服务方在丢弃旧 `push_target_id` 后 MUST NOT 保留可把旧 / 新伪名链接回同一 `(recipient_service_id, principal, device)` 的索引；只允许在 rotation 时短暂保留以便迁移未投递消息。短暂保留期 MUST ≤ 24h，或与单条未投递消息 TTL 取较短者；超过该窗口 MUST 物理删除旧 `push_target_id` 与对应索引材料，不得保留任何能把新旧映射回同一 device 的信息。
- **条数与注册速率上限（normative）**：单一 `(recipient_service_id, principal_id, device_id)` 维度下并存的 active `push_route` 条数 MUST ≤ 16（v1 wire 上限；登记于 [`../conformance/scalability-constraints.md` §6.1](../conformance/scalability-constraints.md)），超过时服务端 MUST 拒绝新 `ak.device.push_route` 注册（`push_route_limit_exceeded`）。同一维度的 push-route 注册 / 轮换 MUST 限速，默认窗口 60s 内 ≤ 8 次写入；超额时返回限速响应并记内部审计 `push_route_registration_rate_limited`。该上限防止单设备通过无界 push_route 放大注册状态或制造可链接性面。

### 5a.3 不可链接性要求

- 同一 `principal_id` 在不同 `recipient_service_id`、不同设备或不同 push route 上的 `push_target_id` MUST NOT be linkable by push gateway / 第三方 transport（除非两侧自愿持有相同源 secret）。受托 Sync Service MAY 在自己的授权上下文内持有从成员 delivery binding 到本服务本地 push queue 的短期索引，但不得把该索引导出给 Push Gateway / vendor。
- 同一设备的两条 `push_route` 的伪名 MUST 互相独立；其中一条被泄露不得让攻击者推导另一条。
- 跨 Realm 投递 MUST 使用同一 `push_target_id`（按 device 而非按 Realm），但 push payload 内不得携带 plaintext `realm_id`/`strand_id`/`message_id`；目标拆分由 device 端解 envelope 后完成。

### 5a.4 Push Payload 形态

- 协议层 push payload MUST 视作 `encrypted-envelope.schema.json` 形态或等价 ephemeral encrypted blob。AAD MUST NOT 包含可链接 wire 字段，仅可携带 routing-only `wakeup_kind`（参见 `discovery/push-notifications.md`）。
- gateway / vendor MUST NOT 解密 payload。任何"丰富推送"扩展（如显示发件人）都属于 vendor-side 行为，需要 Realm 与 device 双方明确 opt-in，并对应单独的 plaintext-visible service profile，不在 v1 默认互操作范围。

### 5a.5 与其它子系统的边界

- Sync Service：以 `push_target_id` 作为 push fanout 索引。被 member delivery binding 授权的 Principal Server MAY 在运行时持有 `recipient_service_id + principal_id + device_id + push_route -> push_target_id` 映射以完成投递；该映射不得暴露给 Push Gateway / vendor，日志、导出、法定披露和跨服务复制 MUST 脱敏或失效化。未被该 Realm membership / service binding 授权的服务不得保留可逆映射。
- WebRTC 通话邀请（`webrtc-signaling.md` §9 incoming-call wakeup）通过同一 `push_target_id` 触发；payload 仍走 §5a.4 加密通道。
- 推送规则（`push-notifications.md` §4 keyword / member_count 等）以 `push_target_id` 为目标但 MUST 在不解密 payload 的前提下完成评估，或在 E2EE Realm 中由设备本地评估，详见对应文档。

## 6. Device List Sync

任何设备新增、撤销、签名更新或算法更新，MUST 产生 `ak.device.list_update` event。该 event 是 principal control stream 中的 actor-private durable identity state；若使用 Event Envelope，顶层 `realm_id` MUST 是目标 principal 的 `principal_control_realm_id`。它不进入任一共享 Realm 控制面 Seal coverage / state_root；共享 Realm 只能通过 MLS Welcome / Remove、device trust proof 或 explicit membership / KeyPackage event 感知其结果：

Account Subscribe 的聚合提示 `delta.device_lists` 与本 event payload 不是同一 DTO：前者固定为 `{changed: principal_did[], left: principal_did[]}`，只指出哪些 principal 的权威设备列表需要刷新或清除；后者才携带该 principal 的具体 device 变化。实现 MUST NOT 把 `device_id` 写入 `delta.device_lists.changed/left`，也不得把聚合提示当作完整设备清单。

```json
{
  "kind": "ak.device.list_update",
  "payload": {
    "principal_id": "did:webvh:...",
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
          "methods": ["ak.sas.v1", "ak.qr.v1"],
          "purpose": "same_principal_device_authorization",
          "pairing_code": "7H2K9M4Q",
          "new_device_pubkey": {
            "kty": "OKP",
            "kid": "ak:device:01964137-0000-7000-8000-000000000000",
            "alg": "Ed25519",
            "key": "base64url..."
          },
          "challenge_proof": {
            "transcript": "ak.device-pairing.challenge.to_device.v1",
            "kid": "ak:device:01964137-0000-7000-8000-000000000000",
            "alg": "Ed25519",
            "transcript_digest": "sha256:89abcdef0123456789abcdef0123456789abcdef0123456789abcdef01234567",
            "signature": "base64url..."
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

`new_device_pubkey` MUST 是 canonical `PublicKey`（[`public-key.schema.json`](../../artifacts/schemas/public-key.schema.json) 的 `kty` / `kid` / `alg` / `key` 四字段）；旧的 `{kid, alg, public_key}` 写法不是 v1 wire，MUST `schema_violation`。接收旧设备 MUST 把 `purpose`、`pairing_code`、`new_device_pubkey.kid`、`challenge_proof.transcript_digest`、`gate_audience` 和 `request_canonical_digest` 纳入用户确认与 SAS/QR transcript 绑定，并 MUST 按 §2.1.2 的 `ak.device-pairing.challenge.to_device.v1` transcript 独立重算并验签 `challenge_proof` 后才可继续；不得只因收到该请求就把新设备标记为 trusted。`pairing_code` MUST 是 8 位 Crockford-style 大写字母数字串（字符集 `[A-HJ-NP-Z2-9]`，拒绝易混字符），由 CSPRNG 的 40 个均匀随机 bit 直接编码；它只在短 TTL、单次使用、audience-bound transcript 内有效。用户确认后，旧设备通过 `ak.gate.account.command.pair_device` 完成授权落地；本规范不定义 `/_arkret/self/devices/pairing-requests*` 作为授权批准接口。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->

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
| `device_signature` | body | `signature` | required | 当前设备签名，MUST 链接到 self-signing / principal key。canonical 签名输入见下方 §8.1。 |

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
- 批次内每个 `key_record.signature` 仍按其各自语义独立链接到 self-signing / principal key；`device_signature` 额外对**整批**签名，防止服务端或中间人对批次做增删/重排。
- `device_signature.kid` MUST 指向该设备身份 key；服务端 MUST 用该设备权威 `device_public_key`(§5.2)验签，失败 MUST 拒绝上传（`invalid_param`）。

`POST /_arkret/self/keys/query` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `device_keys` | body | `object` | required | principal DID 到 device ID 列表的映射。 |
| `timeout_ms` | body | `int` | optional | 查询等待上限。 |

服务端在处理 `keys/query` 时 MUST 先认证 requester，并且 MUST 仅在 requester 与被查询 `principal_id` 之间存在当前有效的授权关系时返回目录记录：至少同属一个 requester 可见且 requester 仍为 `join` 的 Realm，或存在当前 call/session/contact profile 明确定义的共享上下文。否则 MUST 使用与不存在不可区分的失败形态（省略该 `(principal_id, device_id)` 记录或写入 `failures` 的非枚举性失败），不得让任意已登录用户枚举其它 principal 的设备存在性 / 吊销状态。

响应字段：`device_keys: object` required；`failures: object` optional。`device_keys` 的每个 `(principal_id, device_id)` 记录为 `query_device_record`：prekey bundle 收在 `algorithms`(算法名 → key_record)子字段下，并在**与 `algorithms` 同级**携带设备验签公钥目录字段 `device_signing_key` 与 `device_status`(见下方 §8.2)。schema 见 [`keys-operations.schema.json`](../../artifacts/schemas/keys-operations.schema.json) 的 `$defs/query_device_record`。

#### 8.2 设备验签公钥目录（normative）

`keys/query` 响应在每个 `(principal_id, device_id)` 记录上附带便捷的**设备验签公钥目录**面，供任意 realm 成员把 `(actor, device)` 解析为权威验签公钥，据此 fail-closed 验证通话信令（[`webrtc-signaling.md` §5](./webrtc-signaling.md)）与持久消息的 proof：

该目录严格是 principal-scoped 目录，不提供 pairwise-DID 枚举或别名查询。声明 `ak.profile.mls.minimal_metadata_realm.v1` 的内容作者性验证 MUST 按 [`encryption-and-audit.md` §2.10.3](./encryption-and-audit.md) 使用 encrypted envelope 所指 epoch 的 MLS LeafNode basic credential / `signature_key`，MUST NOT 为了验签把 pairwise DID 映射为 principal 后调用本 endpoint；`keys/query` 也 MUST NOT 接受 pairwise DID 作为 `principal_id` 的替代形态。

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `device_signing_key` | `did:key`(Ed25519 multibase) | optional | 该设备的**权威验签公钥**，来源 = 该设备权威 `ak.device.authorize.payload.device_public_key`(§5.2/§5.4)。MUST 仅在 lifecycle=`active`、`ak.device.authorize` 已被接受且未吊销 / generation-fenced 时返回；receiver-local trust 四态不参与服务端目录准入。 |
| `hpke_key` | `string`(multibase) | optional | 该设备的 **HPKE 密封公钥**，来源 = 该设备权威 `ak.device.authorize.payload.hpke_key`(§5.2/§5.4)**原样回显**；服务端 MUST NOT 在投影中替换该值。返回条件与 `device_signing_key` 相同。 |
| `trust_algorithms` | `string[]` | optional | 该设备声明的 canonical 算法集合，来源 = `ak.device.authorize.payload.algorithms`(§5.2)**原样回显**（UTF-8 bytewise 升序、去重）。与承载 prekey bundle 的同级 `algorithms` map 是不同字段。客户端执行 §8.3 第 3 步时以本字段与 `hpke_key`、`device_signing_key` 一起重建 `ak.device-trust-bind-v1` 输入。 |
| `device_status` | `enum(active, revoked)` | optional | 目录态。`active` = 该设备 `device.authorize` 在效且未吊销；`revoked` = 已被显式 `ak.device.revoke` 吊销，或所属 account 已 deactivated 并完成 terminal device fanout。 |
| `cross_signing_binding` | `object` | optional | **Tier-2 / A 模型**：该设备权威 `ak.device.authorize.payload.cross_signing_binding`（§5.2）原样回显，形态 `{verification_method, alg, ssk_generation, signature}`。B 模型改用 `enrollment_authority_binding` + `authorized_generation_ref`，不得因无 cross-signing binding 降级。 |
| `enrollment_authority_binding` | `object` | optional | **service-attested**：该设备权威 `ak.device.authorize.payload.enrollment_authority_binding`（§5.4）原样回显，形态 `{kind="service_attested", authority_did, authorization_ref}`。供客户端确认该 device-set 投影中的 device verify key、HPKE key 与算法集合来自已接受的入册权威路径，而非 Tier-1 裸服务断言。 |
| `device_authorize_event_id` | `event_id` | optional | 当前 device-set 投影对应的 accepted `ak.device.authorize` event id。对 `service_attested` 设备，本字段 MUST 与 `enrollment_authority_binding` 一起返回，并标识其 `payload.device_public_key` 被投影为 `device_signing_key` 的授权事件。 |

并在 `keys_query_outcome` 顶层附带**每 principal** 的交叉签名根材料：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `cross_signing` | `object` | optional | **Tier-2**：`{principal_id}` → 该 principal 当前 `accepted_generation` 的 `ak.cross_signing.publish` payload（§5.1，含 `principal_signing_key` / `self_signing_key`(+binding) / `generation`）。供客户端把 SSK 锚定到 DID 控制集再验 device binding。 |

规则：

- 服务端 MUST 仅对 lifecycle=`active`、权威 `ak.device.authorize` 已接受且未吊销 /
  generation-fenced 的设备返回 `device_signing_key`；不满足时 MUST 省略 key，并用
  `device_status` 或 generation 状态表达服务端可判定的原因。receiver-local
  `unverified/cross_signed/needs_reverification/verified` 不参与该目录是否返回 key 的判断；
  客户端仍须按下述 Tier-2 链独立决定是否信任。`device_status=active` 是返回 key 的必要
  条件，但客户端看到省略 key 时不得反推 receiver-local trust 状态。
- **Tier-1 便捷面（降级行为）**：`device_signing_key` 承载服务端在 session-grant / `device.authorize` ingest 时已校验过的 `device_public_key` 断言。既没有 §8.3 `cross_signing_binding` 链、也没有 §5.4 `enrollment_authority_binding` + `device_authorize_event_id` 入册投影锚的客户端，其设备身份信任根退化为"承载服务端诚实"，与 §4「device 身份不可由服务端伪造」相悖，故 **Tier-1 是显式降级行为，MUST NOT 作为 `e2ee_client` conformance profile 下 E2EE / 通话 proof 验签路径的默认行为**：
  - 凡声明 `ak.profile.e2ee_client.v1` 的客户端，在 E2EE 消息与通话信令 proof 验签路径上 MUST 执行 §8.3 的 Tier-2 链验证；仅服务端断言（Tier-1）不满足该 profile 的接受判据。
  - 不在该 profile 下、仅凭 Tier-1 接受 `device_signing_key` 的客户端，MUST 向用户披露"该设备身份未经密码学交叉签名链验证、信任根为承载服务端"（例如以 `unverified` / `device_unverified` 标识呈现），MUST NOT 把该设备呈现为已验证。
- **Cross-signing 硬化面**：返回 `cross_signing_binding`（每设备）与 `cross_signing`（每 principal）的客户端 MUST 按 §8.3 独立验证完整交叉签名链，**不信服务端对 `device_signing_key` 的断言**，仅在链验证通过后才接受该 key。服务端对在效 cross-signing 设备 SHOULD 同时返回这些字段；缺失时客户端 MUST 视为 `unverified` 并 fail-closed。
- **Service-attested 入册面**：使用 §5.4 enrollment-authority 模型的 principal 不产生 `ak.cross_signing.publish`，其设备授权以 accepted `ak.device.authorize` 的 `enrollment_authority_binding` 为信任根。`keys/query` 只有在 principal 的 `device_generation_status="active"` 且设备 `authorized_generation_ref == current_device_generation_ref` 时，才可把该设备标为 active 并返回 `device_signing_key`、`hpke_key` 或可 claim prekey；响应 MUST 同时返回 `enrollment_authority_binding`、`device_authorize_event_id`、`authorized_generation_ref` 与 principal `device_generations` 状态。generation conflicted、引用旧 generation、缺失 binding/ref、`kind != "service_attested"`、投影材料与 accepted Event payload 不等或设备已吊销时 MUST fail closed 且不得返回可用 key；不得因缺少 `cross_signing_binding` 把合法 current-generation service-attested 设备误判为 Tier-1 降级。

接收方验 envelope / signal proof 时 MUST 按 `verification_method` = `` `{actor}#{device_id}` ``（fragment 是完整 `ak:device:<uuidv7>`）经本目录解析 `device_signing_key` 得 verify_key；设备吊销或 generation fenced/conflicted（`device_status != active`、B 模型 generation 不等或目录省略 key）、目录缺失该 `(actor, device)`、cross-signing 链验证未通过、service-attested 投影锚缺失/不合法、或验签失败者 MUST **fail-closed**：丢弃信号，MUST NOT 触发 UI，持久消息 MUST 标为不可验证且不得当作已验证明文呈现。该规则同时适用于通话信令(详见 [`webrtc-signaling.md` §5](./webrtc-signaling.md))与持久消息接收路径。

`keys/query` 是普通设备专用 `(principal_id, ak:device:<uuidv7>) → accepted ak.device.authorize` 投影。Native Agent runtime 的 stable `device_id` 仅用于 MLS endpoint、KeyPackage、Welcome 与 session binding，不产生 device authorization；服务端 MUST NOT 在 Agent principal 下返回 runtime `device_signing_key`，客户端 MUST NOT 向本 operation 查询 Agent runtime method。ordinary Agent 使用 [`../identity/key-management.md`](../identity/key-management.md) 的 `ak.schema.agent_signer_evidence.v1` operation；Applet/service 使用其注册 evidence。目录缺失后尝试 Agent/MLS key，或 Agent evidence unresolved后回退本目录，均属于禁止的跨-regime fallback。

#### 8.3 客户端交叉签名链验证（Tier-2，normative）

返回 Tier-2 字段时，客户端在接受 `device_signing_key` 为某 `(actor, device)` 的权威验签公钥前 MUST 执行 §5.2.1 链验证，且 **MUST NOT** 仅因服务端返回了 `device_signing_key` 就信任它：

1. **DID 锚定**：独立解析 `actor` 的 DID，校验 `cross_signing.{actor}.principal_signing_key`（`kid` + `public_key`）等于该 DID 当前控制集中对应 verification method 的密钥（逐字节）；不符 MUST 视为 `unverified`。
2. **PSK→SSK**：用上一步 DID 锚定的 PSK 校验 `self_signing_key.binding.signature` 覆盖 §5.1 self-signing canonical 输入；不通过 MUST `unverified`。
3. **SSK→device**：读该设备 `cross_signing_binding`；缺失 MUST `unverified`（除 §5.0.1 inception bootstrap 例外）。比较 `cross_signing_binding.ssk_generation` 与 `cross_signing.{actor}.generation`：相等则用 `self_signing_key.public_key` 校验 `cross_signing_binding.signature` 覆盖 §5.2 `"ak.device-trust-bind-v1\n" + canonical_json({principal_id, device_id, device_public_key, hpke_key, algorithms, ssk_generation})`；小于 MUST `needs_reverification`（降级，不接受）；大于 MUST `unverified` 并触发 re-sync。
4. **接受判据**：仅当 1–3 全部得 `cross_signed` 时，客户端方接受 `device_signing_key` 用于 proof 验签；任一步失败 MUST fail closed（按 `unverified` 处理：丢弃该 `(actor,device)` 的 proof，不触发 UI、不入库）。
5. `device_public_key` 取自 `device_signing_key`(did:key 内嵌的 Ed25519 公钥)，并 MUST 与第 3 步 binding 输入中的 `device_public_key` 为同一把 key——即客户端验证的正是它将用于 proof 验签的那把 key，闭合"目录给的 key ⇔ 被交叉签名背书的 key"。

`POST /_arkret/self/keys/claim` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `one_time_keys` | body | `object` | required | principal DID -> device ID -> algorithm 的映射。 |

响应字段：`one_time_keys: object` required；`failures: object` optional。

规则：

- `claim` MUST 原子消费 one-time key。
- fallback key MUST 标记 `fallback=true`；设备成功使用该 fallback key 建立首个会话后，MUST 在下一次 OTK 上传批次中同时上传新的 fallback key，并 MUST NOT 用旧 fallback key 建立第二个会话。
- 服务端返回 key 时 MUST 附带 device signature。
- 客户端 MUST 拒绝未被 self-signing key 或 principal key 链接的 device key，除非用户明确接受未验证设备。

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
| `device_signature` | `signature` | required | 当前设备签名，MUST 链接到 self-signing / principal key。 |

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

签名算法 v1 为 Ed25519；`signature.alg` MAY 使用注册别名 `Ed25519` 或 `EdDSA`，`signature.kid` MUST 指向同一 accepted signing key。普通 device 从 current accepted device authorization/cross-signing state解析该 key；Native Agent 从 current accepted `ak.agent.key.authorize.verification_method` 解析该 key，并且该 key MUST 同时等于 MLS LeafNode signature key。三条 batch签名与 present entry签名都必须在解析或改变 KeyPackage状态前验证。

upload、consume、revoke 的 byte-exact正向与负向向量由 `ak.vector.crypto.keypackage_write_transcripts.v1` 固化。SDK helper输出与该 fixture不一致时实现 MUST fail closed；不得以当前 server或client实现为兼容依据。

### 9.0.1 Self claim requester proof 与重放闭包（normative）

`ak.self.keys.keypackages.command.claim` 是同一 KeyPackage authority 内的领取面，但 bearer/session 身份本身不能替代对具体领取意图的签名授权。request MUST 携带恰好一个 `proofs[]` 元素并验证 `keypackage-operations.schema.json#/$defs/keypackage_claim_proof`；v1 保留复数 wire 字段只为兼容，未定义 quorum、hybrid 或“任一通过”语义。零个、两个以上、开放对象、`domain`、非 `holder_acceptance` purpose 或非 DID `audience` 都必须在选择 KeyPackage 前拒绝。

先从闭合 request 删除顶层 `proofs`（不是置为 `null`），保留所有实际存在的 optional 字段，计算 `payload_digest = SHA-256(JCS(request_without_proofs))` typed digest。proof `payload_digest` MUST 与之 byte-identical；detached JWS 的 payload segment MUST 为空，并对下列唯一 canonical binding object 的 JCS bytes 签名：

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

verification method 的 DID controller MUST 等于 `requester`，并按 requester 的已接受身份模型唯一解析：cross-signing 模型使用 current accepted SSK；service-attested 模型使用 current accepted、未撤销的 device signing key，且 authenticated session 的稳定 `device_id` 必须匹配；Native Agent 使用 current accepted `ak.agent.key.authorize.verification_method`，且 session 的 Agent/device 绑定与 MLS endpoint 必须匹配；service requester 使用该 service DID 的 current assertion method，并且 service delegation/capability 必须覆盖本 operation。不得跨身份模型降级，普通 device proof、Agent proof 与 service proof 不能相互替代。该 proof 也不能替代 RFC 9421/DPoP sender-constrained transport authentication、target consent/contact/capability/policy 检查，或后续 MLS `payload.claim_envelope` 的独立签名绑定。

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
| `proofs` | `keypackage_claim_proof[1]` | required | 恰好一个 requester `holder_acceptance` detached-JWS proof，完整语义见 §9.0.1；peer surface 不复用此字段，而使用 §9.2 的闭合 `requester_authorization`。 |

`claim` 响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `claims` | `object[]` | required | 每个 claimed KeyPackage 的 `claim_id`、`keypackage_ref`、`keypackage_digest`、device binding、expiry、capabilities 和 `capabilities_digest = sha256(JCS(capabilities))`。 |
| `failures` | `object[]` | optional | 不可领取设备与原因；不得泄露不可见用户或设备。 |

`consume` request MUST validate `schemas/keypackage-operations.schema.json#/$defs/key_packages_consume_request_body`，并由 Welcome 接收方或授权发送方在 Welcome 成功处理且新的 MLS group state 已 durable 持久化后调用，绑定 `key_package_refs[]`、`consumer_device_id`、`signature`，以及可选 `claim_ids[]`、`welcome_ref`、`realm_id`、`strand_id`、`mls_group_id`、`epoch`。若持久化失败，runtime MUST NOT 调用 consume；若 consume响应丢失，必须以同一 signed typed request幂等重试。服务端 MUST 把与首次成功 consume 完全相同的重试作为成功返回，不得因 KeyPackage 已进入 `consumed` 而返回失败。对于 Direct Conversation，只有在 request 精确匹配 active canonical binding、accepted Welcome、claim、recipient principal/device、Realm、Strand、MLS group 与 epoch 后，服务端才可在 terminal KeyPackage row 已清理或不可用时把该重试视为幂等成功；任何字段不同仍 MUST fail closed。实现 SHOULD 保留足够的 terminal consume ledger，使幂等判断不依赖 inventory row 的生命周期。`revoke` request MUST validate `#/$defs/key_packages_revoke_request_body`，可由设备、principal controller 或 policy授权服务发起。

规则：

- 对普通 single-use KeyPackage，`claim` MUST 原子地把 KeyPackage 从 `published` 转为 `claimed`。协商启用的 `last_resort=true` 包是唯一例外：包本身保持 `published`，每次领取只追加独立 `keypackage_claim_record`（见 [`encryption-and-audit.md` §2.6.2](./encryption-and-audit.md)）。
- 同一 `keypackage_ref` 不得被多个 active claim 使用。
- 过期、撤销、设备被移除或 principal control state 失效时，服务 MUST NOT 返回该 KeyPackage。
- **`required_capabilities` ⊆ KeyPackage `capabilities`（normative subset rule）**：claim request 中的 `required_capabilities` 集合 MUST 是被领取 KeyPackage 上声明的 `capabilities`（见 [`encryption-and-audit.md` §2.6 KeyPackage payload](./encryption-and-audit.md)）的**子集**。任何 `required_capabilities ∖ capabilities ≠ ∅` 的 claim MUST 被服务端拒绝（与其它 claim 失败一致使用统一不透明错误码 `claim_failed`，但服务端 SHOULD 在内部审计日志中记录 `keypackage_capability_overreach` 以便滥用检测）。该规则避免了"客户端在 claim 时声明超过 KeyPackage 实际声明的能力，使后续 Welcome / Commit 在错误能力假设下进行"的隐性越权。
- Device / Key Server 在 claim 成功响应中返回的每条 claim MUST 包含 `keypackage_digest = canonical_digest(KeyPackage bytes)`、`capabilities_digest = sha256(JCS(capabilities))`，并携带 claimed 设备的 trust binding。cross-signing 设备携带当前 accepted `ssk_generation`；§5.4 service-attested / enrollment-authority 设备携带该设备 accepted `ak.device.authorize` 的 `device_authorize_event_id`；Native Agent 设备携带当前 accepted `ak.agent.key.authorize` 的 `agent_key_authorize_event_id`。三者 MUST 精确三选一。`ak.mls.welcome` MUST 回填同一 KeyPackage hash 到顶层 `payload.keypackage_digest` 和 `payload.claim_ref.keypackage_digest`，回填同一 digest 到 `payload.claim_ref.capabilities_digest`，并把 claim record 的 trust binding 原样回填到 `payload.claim_ref`；Welcome 接收端在解密前必须比对这些值与本地 claim 记录，并确认该 trust binding 仍指向 claimed 设备当前 accepted state，防止 group manager 或中间服务在 Welcome 阶段替换 KeyPackage、扩大 KeyPackage 能力集合、复用旧 SSK generation、旧设备授权事件或旧 Agent key authorization 的 claim。
- `payload.claim_envelope` 是 requester 对本次 Welcome 的独立签名 transcript，签名身份绑定 requester 而不是被 claim 的设备。cross-signing requester MUST 在 envelope 中携带 requester 当前 accepted `ssk_generation`，并用该 generation 的 SSK 签名；service-attested / enrollment-authority requester MUST 在 envelope 中携带 `requester_device_id` 与 `device_authorize_event_id`，并用该设备当前 accepted `ak.device.authorize.payload.device_public_key` 对 envelope canonical bytes 签名；Native Agent requester MUST 携带 `requester_device_id` 与当前 `agent_key_authorize_event_id`，并用该 authorization 绑定的 active Agent key 签名。三者 MUST 精确三选一。服务端和接收端 MUST 校验 envelope 的 `requester_did`、`requester_device_id`（若存在）、authorization ref、signature `kid` 与当前未撤销设备 / Agent key 投影一致；不得把 claim/claim_ref 中属于 recipient KeyPackage 的 authorization ref 当作 requester 签名身份使用。
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
| `ak.peer.keys.keypackages.query.claim` | `POST /_arkret/peer/keys/keypackages/claims/query` | `peer_key_packages_claim_query_request_body` / `peer_key_packages_claim_query_outcome` |

目标 KeyPackage authority 是 `published → claimed` 的**唯一 CAS 权威**。来源服务只能请求领取并验证目标服务签发的 receipt；不得在本地镜像池上先行标记、推测成功，或用 `ak.peer.events.command.submit` 替代该原子操作。claim 成功只是生成 MLS Welcome 的必要前置条件，不创建 Realm、membership、Strand 或 binding；这些 durable facts 仍必须由其规范 Event 与原签名 proof 创建并经 peer Event / principal-fact 通道投递。

#### 9.2.1 双重授权与签名 transcript

peer claim MUST 同时满足两层授权，任一层缺失或失效都 MUST fail closed：

1. **participant authorization**：requester 对 `requester_authorization` 作 detached signature。签名输入精确为 UTF-8 domain separator `` `ak.peer-keypackage-claim-authorization-v1\n` `` 后接下列对象的 JCS bytes：

   ```json
   {
     "authorization": {
       "device_authorize_event_id": "<present only for service-attested model>",
       "requester_device_id": "<present only for service-attested model>",
       "signed_at": "<RFC3339>",
       "ssk_generation": "<present only for cross-signing model>",
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

   `claim_authorization_draft` MUST 是闭合的 `{request, transport_binding}` 对象；`transport_binding` 明确携带 `source_service_id`、`destination_service_id`、`source_trust_domain` 与 `destination_trust_domain`。客户端 MUST 对 resolver 返回的这些值作 UI / account-context 一致性校验后原样签名，MUST NOT 从本地 endpoint 配置猜测或替换它们。`signature.kid` MUST 等于 `verification_method`。cross-signing 模型必须且只能携带当前 accepted `ssk_generation`，并由该代 SSK 签名；§5.4 service-attested / enrollment-authority 模型必须且只能携带 `requester_device_id + device_authorize_event_id`，并由该 accepted、未撤销设备的 `device_public_key` 签名。目标服务 MUST 独立解析 requester DID / accepted generation / device authorization，不得信任来源服务对 participant key 的裸断言。

   对 service-attested device model，客户端签名后，来源 Principal Server MUST 在发往 peer command 的 body 追加 `requester_signing_key_evidence`（schema `federated-device-signing-key-evidence.schema.json`）。该字段不进入 participant authorization transcript，也不得由客户端自报：其中 `device_authorize_event` 必须是来源当前 active device projection 所引用的原始 accepted `ak.device.authorize` Event。目标服务 MUST 重算该 Event digest / proof transcript，按 Event accepted-at 时点从 requester DID 独立验证 enrollment delegation 与 authority proof，并逐字核对 actor、device、`device_public_key` 和 `device_authorize_event_id` 后，才可用该 key 验证 participant authorization。外层来源服务签名只证明该已验证授权当前仍 active；它不能把裸 key 升格成 participant trust root。cross-signing model 不使用此 evidence；目标必须能从已验证的 requester cross-signing state 独立解析指定 generation，否则 peer claim fail closed。
2. **service authorization**：外层请求 MUST 使用 RFC 9421 HTTP Message Signature，绑定 `@method`、`@target-uri`、`@authority`、`Content-Digest`、`Request-Canonical-Digest`、`Source-Service-ID`、`Destination-Service-ID`、`Source-Trust-Domain`、`Destination-Trust-Domain` 与 `Idempotency-Key`。`Idempotency-Key` MUST 逐字等于 body `claim_request_id`。

`claim_request_id` 与 `claim_nonce` 各自 MUST 含至少 128 bits 不可预测熵。`requester_authorization.signed_at` 不得在接收方当前时间未来 60 秒以上；`expires_at` MUST 晚于 `signed_at` 且 `expires_at - signed_at <= 300s`。外层 HTTP signature 的 `created` / `expires` 窗口同样 MUST 不超过 300 秒。两层签名均绑定 source / destination / trust-domain，可阻断可信来源服务把授权转发给另一目标或另一部署重放。

#### 9.2.2 目标 authority 的独立准入

在触碰 KeyPackage 状态前，目标服务 MUST 独立验证：

- `Source-Service-ID` 是 requester 当前已验证 Principal Server locator / home authority，`Destination-Service-ID` 是 `target_principal_id` 当前 KeyPackage authority，且两端与请求中的 trust domain 均属于允许此次 Realm 建立的同一 trust domain；
- participant authorization 的 requester、verification method、generation / device authorization、freshness 与 exact request/transport binding 全部有效；
- target 当前 active device、KeyPackage expiry / revocation / capability 均有效，并满足 `required_capabilities ⊆ capabilities`；
- `claim_purpose=direct_conversation` 时，request MUST 携带 `pair_key` 与 main `strand_id`；目标服务按 [`../identity/contact-and-direct-conversation.md` §7](../identity/contact-and-direct-conversation.md) 重算 pair key，并验证双方 accepted contact、target 对 requester 的 active `direct_message|any` consent、预留 Realm / Strand / MLS group 的一致性；
- `(Source-Service-ID, target_principal_id)` 的限速与 abuse policy 通过。

`claim_purpose=direct_conversation` 时 `last_resort_allowed` MUST 缺省或为 `false`，目标服务 MUST NOT 返回 last-resort KeyPackage。一般 `realm_membership` claim 只有在双方 feature negotiation 均声明 `ak.feature.mls_last_resort_keypackage.v1` 且请求显式 `last_resort_allowed=true` 时才可返回 last-resort record；否则 single-use pool 耗尽即失败。

#### 9.2.3 原子幂等 ledger 与不确定结果

目标 authority MUST 持久化以 `(Source-Service-ID, claim_request_id)` 唯一索引的 claim ledger，并将 `Request-Canonical-Digest` 记为 `request_digest`。下列动作必须处于同一事务 / 等价线性化边界：

1. 核对已由唯一索引保护的 request reservation 与 digest；
2. 选择仍为 `published` 且通过 freshness / capability gate 的 KeyPackage；
3. 对 single-use KeyPackage 执行 CAS `published → claimed`；
4. 写入 claim record、把 ledger 从 `pending` 变为终态，并写入已序列化的成功 outcome bytes。

实现 MAY 在最终事务前先提交只含 `(Source-Service-ID, claim_request_id, request_digest, state=pending)` 的唯一 reservation，以串行化并发 duplicate；该 reservation 不得选择、锁定或泄露 KeyPackage。上述 1–4 的**最终化**必须在同一事务完成，因而不得出现 KeyPackage 已 `claimed` 但 ledger 无 outcome、或 ledger 已成功但 CAS 未发生的可观察状态。crash 后 recovery worker 只能按原 digest 恢复 / 最终化同一 reservation，不能改用新的请求身份。

同一 source、同一 `claim_request_id`、同一 digest 的 duplicate transport delivery / replay MUST 返回 byte-identical 成功 outcome，且不得第二次领取；这项 receiver 安全性不把 operation 变成可跳过恢复查询的 caller retry-safe。同一 key 携带不同 digest MUST 返回 `duplicate_conflict` 且不得改变任何 KeyPackage。响应丢失、超时或来源服务在 durable dispatch marker 与实际 network send 之间 crash 后，来源服务 MUST 先调用 `ak.peer.keys.keypackages.query.claim`，携带原 `claim_request_id + request_digest`，不得先重发 command，也不得换 nonce 盲目重新 claim。query 只接受原 Source-Service-ID 与 exact digest，返回 `unknown|pending|claimed|claim_failed|expired|revoked`；`unknown` 明确证明目标尚无该 request identity 的 reservation，调用方此时 MAY 重放 exact same canonical command（同 source、claim_request_id、digest、nonce 与 evidence），不得生成新请求；`pending` 表示 reservation 已存在但最终化事务尚未提交，调用方只可按 `retry_after_ms` 再查；`claimed|expired|revoked` MUST 携带原签名 `claim_outcome`，`claim_failed` 只携带不透明 `error_code=claim_failed`。

成功 outcome 的 `claim_receipt.signature` 由目标服务对 `` `ak.peer-keypackage-claim-receipt-v1\n` `` + JCS(receipt 除 `signature` 外全部字段) 签名；receipt MUST 携带并签名覆盖 `source_service_id`、`destination_service_id` 与原 participant-authorized `request`（即不含 authorization / transport-only evidence 的 unsigned request 字段），`request_digest` 绑定完整 peer command，`claims_digest` 绑定 `claims[]` canonical bytes。`claim_request_id`、receipt.request 内同名字段与 outcome 同名字段必须一致。ledger 的可查询 outcome MUST 至少保留到 claim `expires_at + 10 minutes`；其后实现 MAY 只保留符合隐私 / 审计策略的 hash replay tombstone，不得长期保留可关联 private Realm 的不必要明文。

通过 peer claim 生成的 `ak.mls.welcome` MUST 原样携带 `payload.peer_claim_receipt`。目标 Principal Server 在接受该 Welcome 前 MUST：验证 receipt 目标服务签名；以外层认证的 `Source-Service-ID` 精确匹配 `source_service_id`；查询 `(source_service_id, claim_request_id)` durable ledger 并逐字匹配 `request_digest` 与 stored outcome；验证 request 的 requester / target principal / intended Realm / MLS group / claim nonce 与 Event actor、recipient、Realm、Welcome group / `claim_envelope` 一致；验证 stored claim 与 Welcome 的 claim id、KeyPackage ref / digest、recipient device 一致。缺 receipt、ledger 未就绪或任一绑定不一致时均须 fail closed；ledger 尚未可见属于 retryable dependency，不得把未经认领的 Welcome 降级接受。Direct Conversation binding 成为 canonical 前还 MUST 将 receipt.request 的 `pair_key` 与 `strand_id` 精确匹配 binding payload。

所有目标不存在、contact/consent 不满足、设备不可见、KeyPackage 耗尽、capability 不满足、policy denied、participant authorization 失效和限速失败，对**已通过外层服务认证**的 peer caller 必须收敛为同一 `claim_failed` 外观；不得返回 `available_count`、目标设备列表或逐设备 `failures[]`。外层 RFC 9421 signature / source service identity 无法通过时，接收方在读取 target 状态前返回通用 `unauthenticated` / `invalid_signature`；该响应必须只由 transport authentication 决定，对任意 `target_principal_id` 完全相同。

#### 9.2.4 Welcome、consume 与并发 loser

目标设备只有在以下条件全部成立后才可激活 Welcome 并通过其 own Principal Server 的 `ak.self.keys.keypackages.command.consume` 消费 claim：Welcome / claim-ref 校验通过、对应 Realm/member/main-Strand/MLS Event 均可验证、且双方已对同一 `pair_key` 收敛到包含该 Welcome 的 canonical binding winner。peer surface 不提供 consume 代理；来源服务不得代表目标设备把 claim 标为 consumed。

并发 resolver 可能各自领取不同 KeyPackage 并生成不同候选 Realm。loser candidate 的 Welcome MUST 被隔离或忽略，不得激活 MLS state，也不得 consume 对应 KeyPackage；该 single-use claim 到期后按 §9.1 转为 `revoked`，**绝不得回到 `published`**。只有 canonical binding winner 对应的 Welcome 可激活 / consume。实现 MAY 在确定 loser 后提前用授权 revoke 路径终止其 claim，但不得用“释放领取”实现复用。

## 10. Verification Strands

设备密钥验证用于确认“这个 principal/device/key 是否是用户想信任的对象”。验证成功本身不授予登录态、Realm 权限或长期设备权力：

- 同一 principal 的新设备登录，验证成功后仍 MUST 通过 `ak.device.authorize`、DID/key-log operation 或 recovery policy 把设备加入有效设备集合。
- 跨 principal 验证只表达人工信任；通常由本地 `user_signing_key` 签名对方 identity key 或设备 key，不得改变对方设备授权状态。
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
| `ak.key.verification.request` | `methods`, `timestamp`, `expires_at` | 发起验证。`methods` 使用标准方法名，例如 `ak.sas.v1`、`ak.qr.v1`。同 principal 新设备授权请求 SHOULD 另带 `purpose="same_principal_device_authorization"`、`pairing_code`、`new_device_pubkey`（canonical `PublicKey`）、`challenge_proof`（§2.1.2 的 `ak.device-pairing.challenge.to_device.v1`）、`gate_audience`、`request_canonical_digest` 与 `device_metadata?`；这些字段必须进入 SAS/QR transcript 或等价 proof 绑定。 |
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
3. 在用户或 policy 允许时，通过加密 to-device 消息共享 `self_signing_key`、secret storage bootstrap 或 MLS Welcome。

当验证目的为 `same_principal_device_authorization` 时，用户确认后的授权落地 MUST 发生在 `/_arkret/gate/account/*` 认证面，默认使用 `ak.gate.account.command.pair_device`。旧设备把验证 transcript 中绑定的 `pairing_code`、`new_device_pubkey`、`challenge_proof` 以及自身 fresh device proof 提交给 gate；gate MUST 按 §2.1.2 独立重算 transcript 并验签，MUST NOT 只做逐字段相等比较；gate 返回的 `authorized_event_ref` 只是 durable `ak.device.authorize` / `ak.device.list_update` 已被接受的引用或等价结果。新设备可通过同一 to-device transcript 的 `ak.key.verification.done` 中的 `authorized_event_ref` hint、后续 full `ak.self.account.stream.subscribe` device list baseline，或重新通过 `ak.gate.account.command.issue_session_grant` 升级会话来观察授权结果；它 MUST 验证 durable device list，而不得把 `done` 消息本身当成授权真相源。

跨 principal 验证完成后，客户端 MAY 使用 `user_signing_key` 对对方 principal identity key 或 device key 生成信任签名。该签名只影响本 principal 的信任视图，不授予对方 Realm capability。

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
| `cross_signing_reset` | 验证过程中检测到 cross-signing reset，旧 SSK generation 已废止；详见 §14.3。 |

### 10.7 Secret Sharing（`ak.secret.*`）

§10.5(3) 允许已授权设备在验证成功后“通过加密 to-device 消息共享 `self_signing_key`、secret storage bootstrap 或 MLS Welcome”。本节把该动作收敛为两个标准 to-device kind，用于把账户级 secret（如 MLS account secret / secret storage bootstrap key）从一台已授权设备直传给同一 principal 的另一台已通过 §10.3 SAS 验证的设备，无需用户重新输入恢复口令。它是 [`identity/key-management.md` §7](../identity/key-management.md) 无口令恢复路径的设备直传分支，服务端零知识。

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
- 密封密钥绑定（normative）：被请求设备在密封并发送 `ak.secret.send` 前，MUST 校验请求中的 `recipient_hpke_public_key` 逐字节等于目标 `from_device` 在设备集投影（§4 device record / §6 device list，经 §8.3 Tier-2 链验证或 §5.4 service-attested 投影锚验证后视为权威）中登记的 `hpke_key`；不等 MUST fail closed（不密封、不发送），并 SHOULD 提示用户该请求异常。该校验闭合"验证设备 A 的 verify key、却把账户级 secret 密封给攻击者控制的 X25519 公钥"这一密钥绑定缝隙——它独立于 §10.3 SAS（SAS 只绑 verify key）。device `hpke_key` MUST 已被 §5.2 `cross_signing_binding` 或 §5.4 入册权威 Event proof 覆盖；仅有服务端投影、但无法验证 HPKE key 绑定的设备不得作为账户级 secret 的接收目标。
- 反滥用：接收方 MUST 丢弃 unsolicited `ak.secret.send`（无本端 pending `request_id`）；`request_id` 用后即作废；对同一 `from_device` 的重复请求 SHOULD 限速；多次拒绝 SHOULD 提示用户考虑撤销该设备。
- 审计：被请求设备 SHOULD 记录一次 secret 共享审计（如 `ak.audit.accessed`，`access_kind=secret_share`）。
- 止损：误授权后，用户从任一已授权设备发起 §2.2 设备撤销并轮换对应 account secret、重新封装全部备份即可使被泄露设备失效。
- QR：与 §10.4 一致，QR payload 仍 MUST NOT 直接携带任何 secret 本体；secret 只经本节 HPKE 密封的 `ak.secret.send` 传输。

## 11. Secret Storage（client-local cache form）

Secret storage 用于保存：

- `self_signing_key`
- `user_signing_key`
- recovery secret（仅 `personal_node + single_point_of_failure=true` 的显式降级可在可信本地 keychain 持久化；其他 profile 只能在 custody 仪式内瞬态存在，local cache 最多保留不可逆 fingerprint / durable checkpoint，不得保留 secret bytes）
- MLS group secrets backup key
- applet delegated device secret

`ak.secret_storage.v1` 是 **client-local** envelope，仅用于设备本地或可信操作系统 keychain；**不得作为线级 (wire) 上传格式**。

Device / Key Server 的 `ak.keys.backups.*` endpoint MUST 只接受 `ak.schema.key_backup.v1` wire envelope。任何不符合 `ak.schema.key_backup.v1` 顶层 `required`（含 `series_id` / `series_seq`）的请求体 MUST 返回 `schema_violation`，原因码 `key_backup_wire_schema_required`。Client-local `ak.secret_storage.v1` 存储不受影响，但 MUST NOT 通过 `PUT /_arkret/self/keys/backups/{backup_id}` 同步。

任何同步到 Device / Key Server 或其它远端服务的 secret，MUST 使用 §12 的 `ak.schema.key_backup.v1` envelope，并设置对应 `backup_kind`：

| Secret 类别 | `backup_kind` |
| --- | --- |
| DID 恢复材料 | `did_recovery` |
| `self_signing_key`、`user_signing_key` 等账户级 secret | `secret_storage` |
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
  "actor_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
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
      "actor_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
      "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
      "backup_kind": "mls_history",
      "backup_version": "kb_1",
      "created_at": "2026-04-26T00:00:00Z",
      "item_kinds": ["mls_epoch_secret"]
    }
  },
  "contents": [
    {
      "item_kind": "mls_epoch_secret",
      "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
      "mls_group_id": "base64url",
      "epoch": 42,
      "first_event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
      "last_event_id": "ak:event:019640ee-0000-7000-8000-000000000000"
    }
  ],
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "auth_data": {
    "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
    "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#ak:device:01964137-0000-7000-8000-000000000000",
    "signature_algorithm": "Ed25519",
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
    ]
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
- `backup_kind="did_recovery"` 的 wire envelope MUST 使用 `recipient_method="recovery_public_key"`。任何 backup class 只要使用 `recovery_public_key`，就 MUST 携带顶层 `recovery_policy_ref{policy_id, policy_version}` 并由 `auth_data.signed_fields` 覆盖；`recipient_key_ref` 只能解析到该 accepted policy 的 `recovery_key_agreements[]`。`did_recovery` 的 ref 必须等于当前 active policy；`mls_history` / `secret_storage` 仍须按 accepted policy history、active-series 与轮换规则拒绝回滚。不一致 MUST `recovery_policy_mismatch`。只有 `secret_storage_key` 等非 recovery-public-key 方法携带的 `recovery_policy_ref` 才是可选 hint；任何 policy ref 都不得替代 active-series record、frontier_ref 或 Realm/MLS 授权校验。
- 上传设备 MUST 通过 `auth_data` 对 backup metadata 与 ciphertext digest 签名，并精确携带一种设备信任锚：A 模型为当前 `auth_data.ssk_generation`，B 模型为当前 generation 设备的 `auth_data.device_authorize_event_id`；同时出现或同时缺失均拒绝。携带 `frontier_ref` 时也必须精确绑定对应 A 的 `ssk_generation` 或 B 的 `device_generation_ref`。`auth_data.signed_fields` MUST 至少覆盖 `backup_id`、`actor_id`、`backup_kind`、`backup_version`、`series_id`、`series_seq`、`supersedes`、`encryption`、`contents` 与 `ciphertext_digest`；非 genesis envelope 还 MUST 覆盖 `supersedes_digest`，携带 `frontier_ref` 时还 MUST 覆盖 `frontier_ref`，携带 `recovery_policy_ref` 时还 MUST 覆盖 `recovery_policy_ref`。签名链必须链接到当前 principal 的 A/B device trust state。
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

`unlock` 返回完整 encrypted backup object：request body MUST 携带 `ak.schema.key_backup_unlock_proof.v1`（见 `identity/key-management.md` §7.7.1），并受 §7.8 的 fresh device proof 与 rate limit 约束。普通单对象 `delete` MUST 要求当前设备证明、DID proof 或 recovery policy 允许的高风险证明；active series 内的非尾部 envelope MUST NOT 被单独删除，删除链尾部 envelope MUST 同时附 §15 风格的 high-risk proof（principal_signing / device_quorum / trusted_recovery_service）并写入高风险审计。设备revoke后的旧series不得循环调用该单对象operation充当事务完成证据；它必须走[`identity/security-transactions.md` §3](../identity/security-transactions.md)的transaction-bound `ak.self.keys.backup_series.command.erase`并取得完整typed confirmation。

### 12.2 Retention and Erasure

| Profile | `delete_after` 默认 | `legal_hold` 行为 |
| --- | --- | --- |
| `ak.profile.personal_node.v1` | `null`（无自动过期） | clients-only flag；服务端不强制 |
| `ak.profile.small_team.v1` | `null` | 仅在组织声明 `ak:policy:<id>` 允许时可置 `true` |
| `ak.profile.organization.v1` | 365d（可被 Realm policy 覆盖） | 服务端 MUST 在 `legal_hold=true` 时阻塞 user-initiated delete |
| `ak.profile.high_security_organization.v1` | 90d | 服务端 MUST 强制 `legal_hold` 与审计配对 |
| `ak.profile.sovereign_deployment.v1` | deployment-defined | 与本地法务合规框架对齐 |

要求：

- 服务端 MUST 在收到 user erasure 请求（参见 `ak.audit.erasure_receipt` / `ak.schema.erasure_receipt.v1`）时，按 erasure receipt 的 `scope` 与 `subject` 处理对应 backup envelope：若 `subject.kind="principal"` 且 `scope.storage_boundary` 涵盖 `device_secret_store`，相应 `did_recovery` / `secret_storage` envelope MUST 被删除并产出 `ak.schema.erasure_receipt.v1` 子条目。
- 用户主动删除自身备份与 erasure 流程区分清晰：常规 `DELETE` 不写 erasure receipt，但 `identity/key-management.md` §7.8 的高风险审计仍要求落地 `ak.audit.accessed` (`access_kind="key_backup_delete"`).
- `legal_hold=true` 的 envelope MUST 被服务端拒绝删除（即便提供 high-risk proof）；解除 hold MUST 由声明该 hold 的 Policy Server 通过 policy update 完成，并写入审计。
- 同一 series 内的 retention 必须保证链不被打破：服务端 MUST NOT 删除 active series 的非尾部 envelope；旧 series 只有在已经被 active-series record 移出 primary source 后，才 MAY 按 retention / erasure 策略整组删除或迁移。若该删除属于`SecurityRotationTransaction`，两个backup kind的pointer、逐series进度、partial retry与complete confirmation一律以[`identity/security-transactions.md` §3](../identity/security-transactions.md)为准。
- erasure 完成后保留的 `retained_stub_digest` MUST 仅含 metadata 哈希，不含密文与 KDF 参数，以避免间接成为离线爆破证据。

## 13. Realm Key Share and Withholding

Arkret 使用 `ak.realm_key.share` 共享历史解密材料。`share_kind="member_device"` 是普通成员设备历史交付路径；共享前发送设备 MUST 检查：

- 接收设备属于目标 principal。
- 设备未撤销。
- 设备通过 self-signing 或人工验证，或 Realm policy 允许未验证设备。
- history visibility 允许该 principal 获取目标历史范围，且判定时点使用目标 Event range 的 deterministic `T0`，不得使用本地到达顺序或 wall clock。
- effective `ak.realm.history_sharing_policy` 允许该 receiver class、scope、epoch range 和 key source；当 Realm / Circle history visibility 为 `restricted` 时，必须命中 `restricted_rules[]`，且本次请求所用 key 来源 MUST 在命中 rule 的 `key_sources` 内（命中 read rule 但来源不在 `key_sources` 时只放行读取、不交付 key），否则 MUST withhold。
- `key_scope.policy_digest` 绑定本次判定使用的 Realm policy / MLS governance policy root；如判定依赖 membership frontier，`key_scope.membership_frontier_digest` SHOULD 同时写入。
- `sender_device_signature` MUST 覆盖 `share_kind`、发送设备、接收 principal/device、`key_scope`、`aad_digest?`、`ciphertext` 或 `encrypted_key_ref` 与 `created_at`。接收方 MUST 验证该签名链接到当前有效 sender device key，且不得只依赖传输层认证。
- 对 `history_visibility=joined` 的 scope，join 前 epoch key MUST 被拒绝；对 `invited`，share range MUST be no earlier than receiver 的有效 invite frontier；对 `shared`，join 前 history key share 仍需要 policy 明确允许；对 `world_readable`，E2EE key 不因 public history 自动公开。
- current safety policy（redaction / erasure / retention / ban·remove / legal hold）未禁止继续向该 principal / device 交付。
- audit profile 要求的 `ak.realm_key.share_audit` / `ak.audit.accessed` 已满足。
- Archive Node、Key Recovery Service、Recovery Service 或 peer 不能因为持有备份副本就绕过上述检查；服务端 operator 权限不是 key share 授权。

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

## 14. Cross-Signing Reset

重置 `self_signing_key` 或 `user_signing_key` 是高风险操作。实现 MUST 要求以下至少一种证明：

- principal DID 控制密钥签名。
- recovery key 解锁 secret storage。
- 已验证设备 quorum 签名。
- 受信任账户恢复服务签名，且该服务在 DID document 中声明。

重置后，先前设备签名链不再自动可信。客户端 MUST 将所有既有信任标记为 `needs_reverification`。

### 14.1 Reset Envelope

Reset 操作 MUST 写入一条 `ak.cross_signing.reset` 事件到 principal control stream，并在其后**立即**发布新的 `ak.cross_signing.publish`（§5.1）以使协议状态可恢复。实现还 MUST 生成可审计记录：在同一 ordered submit batch 或在 reset accepted 后的 bounded audit window 内写入 `ak.audit.accessed`，`access_kind="cross_signing_reset"`，`target_ref` 指向 reset event 或 principal control Realm，`purpose` 说明 reset reason；声明 active Audit Applet Binding 或 `ak.profile.attested_audit.e2ee.v1` 的部署 MUST 通过 `refs[role="audit_pair"]` 把 reset 与 audit event 配对，其它高安全部署 SHOULD 配对。

Schema id：`ak.schema.cross_signing_reset.v1`

`proof.kind` MUST be one of `principal_signing` / `recovery_unlock` / `device_quorum` / `trusted_recovery_service`，且必须符合 [`cross-signing-reset.schema.json`](../../artifacts/schemas/cross-signing-reset.schema.json) 的 kind-specific shape。下面示例选用 `principal_signing`：

```json
{
  "kind": "ak.cross_signing.reset",
  "realm_id": "<principal_control_realm_id>",
  "actor_id": "did:webvh:...",
  "payload": {
    "trust_domain": "ak:trust_domain:did.webvh.example",
    "reset_event_id": "ak:event:0196414c-5000-7000-8000-000000000000",
    "principal_id": "did:webvh:...",
    "previous_generation": 1,
    "new_generation": 2,
    "reset_reason_code": "rotation",
    "proof": {
      "kind": "principal_signing",
      "verification_method": "did:webvh:...#ak_principal_signing_v1",
      "alg": "EdDSA",
      "signature": "base64url..."
    },
    "issued_at": "2026-04-26T00:00:00Z"
  }
}
```

Payload-only schema 示例（即 Event `payload` / 上例 `payload` 的规范形态）：

```json schema=schemas/cross-signing-reset.schema.json
{
  "trust_domain": "ak:trust_domain:did.webvh.example",
  "reset_event_id": "ak:event:0196414c-5000-7000-8000-000000000000",
  "principal_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
  "previous_generation": 1,
  "new_generation": 2,
  "reset_reason_code": "rotation",
  "proof": {
    "kind": "principal_signing",
    "verification_method": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#ak_principal_signing_v1",
    "alg": "EdDSA",
    "signature": "c2ln"
  },
  "issued_at": "2026-04-26T00:00:00.000Z"
}
```

字段规则：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `previous_generation` | required | 被重置前的 `generation`；MUST 等于当前 accepted publish 的 `generation`。 |
| `new_generation` | required | 后续 publish 将使用的 `generation`；MUST = `previous_generation + 1`。 |
| `reset_reason_code` | required | 机器可读枚举：`rotation` / `compromise` / `device_loss` / `policy_required`。 |
| `proof` | required | 四类高风险证明之一，详见 §14；接收方 MUST 拒绝缺失 / 无效的 proof。 |
| `proof.recovery_session_id` | `recovery_unlock` 时 required | 当 `proof.kind = recovery_unlock` 时，proof body MUST 携带 §15 device recovery state machine 的 `recovery_session_id`（§15 step 2）。它随 `proof_body` 进入下方 §14.1 canonical transcript，使 `recovery_unlock` proof 自身携带 freshness binding，不依赖外部 state machine；receiver MUST 拒绝 `recovery_session_id` 与 `principal_id` 在 `issued_at` 时无活跃 recovery session 匹配的 reset。其余三类 proof 不携带此字段。 |

所有 proof 签名的 canonical input MUST 是：

```text
utf8("ak.cross-signing-reset-v1\n") ||
canonical_json({
  "trust_domain": trust_domain,
  "reset_event_id": reset_event_id,
  "principal_id": principal_id,
  "previous_generation": previous_generation,
  "new_generation": new_generation,
  "reset_reason_code": reset_reason_code,
  "issued_at": issued_at,
  "proof_kind": proof.kind,
  "proof_body": proof without signature fields
})
```

**`trust_domain` 与 `reset_event_id` 绑定（normative）**：

- `trust_domain` 是部署级的 trust 域标识，typed string，形如 `ak:trust_domain:<scope>`。它在每个 deployment 的 `ServiceDescribe.trust_domain` 与 Realm create object 的 `trust_domain` 中声明（详见 [`identity-did.md` §3.6 Trust Domain](../identity/identity-did.md)）。canonical input MUST 把当前 receive context 的 `trust_domain` 嵌入 proof transcript，使同一 principal DID 在 deployment A 签发的 reset proof 无法被 deployment B 重放——B 的 `trust_domain` 字符串不同，proof signature transcript 校验立即失败 (`invalid_signature`)。
- `reset_event_id` 是承载该 reset 的 Event Envelope 的 `event_id`（typed `ak:event:<uuidv7>`），由 producer 在签名前分配。把它纳入 transcript 确保同一 reset proof 不能复用到另一个 Event shell（不同 `event_id` ⇒ 不同 transcript ⇒ 签名失败）。这关闭了"复制 reset proof bytes，包到新 Event 里重放"的攻击面。
- 这两个字段同时是 `ak.cross_signing.reset` payload 的必填字段（[`cross-signing-reset.schema.json`](../../artifacts/schemas/cross-signing-reset.schema.json) `trust_domain` / `reset_event_id`）。
- 接收方验证顺序：(a) 检查 `trust_domain` 与本 receiver 当前 trust 域一致；不一致直接 `cross_domain_replay_rejected`，不进入签名校验。(b) 检查 `reset_event_id == enclosing Event.event_id`；不一致 `reset_event_id_mismatch`。(c) 按上面 canonical input 重算 transcript 并验证每个 proof 的签名；任一不匹配 `invalid_signature`。
- 多 deployment 部署、sovereign trust domain、recovery service 跨域复用、device quorum 跨 trust domain 都受这两个字段保护——任一变化都会让 transcript 失配。

`recovery_unlock.unlock_commitment` 的派生输入 MUST 避免自引用：其
`unlock_binding_input_bytes` 使用与上面相同的字段集合，但 `proof_body`
MUST 同时排除 `signature` 字段和 `unlock_commitment` 字段。随后
`recovery_unlock.signature` 仍然覆盖上面的完整 canonical input，也就是覆盖已经
计算出的 `unlock_commitment`。

`device_quorum.signatures[]` 的每个设备签名分别覆盖同一 canonical input。`trusted_recovery_service` 的 `service_id` MUST 出现在 principal DID Document 的恢复服务声明中；未声明的服务签名无效。该 service proof 不能单独授权 reset：它还 MUST 绑定一个当前 `verified`、未过期、未消费的 `recovery_session_id`，且该 session 已由 `principal_signing`、`recovery_unlock` 或 `device_quorum` 中至少一种非 service 因子验证。仅由另一个 `trusted_recovery_service` session 验证不构成第二因子。

每类 proof 的接收方验证规则见 §14.4；schema（[`cross-signing-reset.schema.json`](../../artifacts/schemas/cross-signing-reset.schema.json)）只编码 wire 形态最低限，签名 / 门限 / commitment 验证均为本节 normative。

### 14.2 `needs_reverification` 扩散规则

Receiver 接受 reset 后 MUST 按以下顺序更新本地状态：

1. **本 principal 名下所有设备**的 trust state 强制从 `cross_signed` / `verified` 降为 `needs_reverification`。reset payload `revoked_device_ids[]` 中列出的已攻陷/丢失设备 MUST 同事务写入 `ak.device.revoke` 并进入 terminal `revoked`；`reset_reason_code ∈ {compromise,device_loss}` 时该数组 MUST 非空。未列出的设备可在重新验证前保留最低限度读能力，但不得通过 require-cross-signed gate，也不得签发新长期授权。
2. **本 principal USK 签发的跨 principal 信任**全部进入 `needs_reverification`：对方在自己视图里看到的"由 X 验证过我"提示 MUST 消失，需要等待新一轮 USK publish 与人工再确认。
3. **MLS leaf credential 与强制重钥**：`revoked_device_ids[]` 对应的全部 MLS leaf MUST 被 Remove proposal 覆盖；principal 参与的每个 active MLS group MUST 在 reset 后发起并接受 Commit（无待移除 leaf 时为 Empty Commit），让 epoch transcript 绑定新 SSK generation。该 Commit 完成前 scope 进入 `epoch_update_required`，发送方 MUST 暂停新加密 application message。旧 leaf 不得因“credential 由 device key 单独签名”继续存活。
4. **in-flight verification transaction**（§10 状态机里仍在 `request` / `ready` / `start` / `accept` / `key` / `mac` 阶段的）MUST 以 `code=cross_signing_reset` cancel，禁止把基于旧 SSK 的 SAS / QR transcript 用旧 generation 完成。
5. **To-device 队列隔离**：reset accepted 后，服务端和客户端 MUST drop 或 quarantine 所有已排队但尚未处理的 `ak.key.verification.*` to-device 消息，以及任何未显式绑定 `new_generation` 的 cross-signing / trust bootstrap 消息。隔离窗口内仅允许 `ak.key.verification.cancel(code=cross_signing_reset)`、新的 `ak.cross_signing.publish` 可验证通知和重新发起的、显式绑定 `new_generation` 的验证事务通过；不得让旧 generation 的 `mac` / `done` 消息在 reset 后完成信任升级。
6. **新的 `ak.cross_signing.publish`** MUST 在 reset 接受后 `ak.profile.cross_signing.reset.v1` 的 `parameters.publish_recovery_window_seconds` 窗口内发布到 control stream（默认 24h）；超时未发布的 reset 会让该 principal 进入"无可用 SSK / USK"窗口，接收方在此窗口内 MUST 拒绝任何 `ak.device.authorize.cross_signing_binding.ssk_generation == new_generation` 的事件，避免静默接受未公布的 SSK。
7. **`secret_storage` backup 同步刷新（normative）**：reset accepted 后，所有引用旧 SSK 的 `secret_storage` 类 `ak.schema.key_backup.v1` envelope MUST 在同一 `publish_recovery_window_seconds` 窗口内被新设备签发的后继 envelope 取代——后继 envelope 的 `series_id` 保持不变、`series_seq` 严格递增、`supersedes` 指向旧 envelope；`contents` 中含 `self_signing_key` / `user_signing_key` 的条目 MUST 对应 `new_generation`。窗口过期后，receiver MUST 把任何引用 retired generation 的 `secret_storage` envelope 视为 `backup_post_reset_stale`，并在恢复流程（§15 step 4）中拒绝作为主解锁源；服务端 SHOULD 在 list 响应中通过 metadata flag 提示该 envelope 已 stale，但 MUST NOT 自行删除（删除属于 §12.2 retention 流程）。

### 14.3 Cancel Code

§10.6 的 cancel code registry 增补一项：

| code | 含义 |
| --- | --- |
| `cross_signing_reset` | 本端或对端在验证过程中检测到 cross-signing reset；transcript 已绑定的 SSK generation 已被废止，必须放弃当前 transaction 并以新 generation 重启。 |

### 14.4 Proof 验证规则（Normative）

`cross-signing-reset.schema.json` 只编码 wire 形态最低限。Receiver 接受任一 reset 前 MUST 按下表对所选 proof.kind 执行**全部**校验；任一失败 MUST 拒绝该 reset 并以下面的 reason_code 标记。canonical input 同 §14.1。

| proof.kind | Receiver MUST 校验 | 失败 reason_code |
| --- | --- | --- |
| `principal_signing` | (a) `verification_method` MUST 是该 principal 当前 DID Document 中具备**principal-grade 控制权**的 verification method（即 [`../identity/key-management.md` §3.2](../identity/key-management.md) 定义的 principal signing key 类，例如 `did:webvh:...#ak_principal_signing_v1` 或等价 DID method 控制密钥），且在 `issued_at` 时刻未撤销 / 未轮换；**MUST NOT** 是被本次 reset 重置对象的 `self_signing_key` / `user_signing_key`（让被废止的密钥自我授权废止自身会导致 trust circular）。(b) `signature` 在 `alg` 下覆盖 §14.1 canonical input 验证通过；(c) `previous_generation` 等于 receiver 持有的 accepted publish generation，`new_generation = previous_generation + 1`。 | `cross_signing_reset_proof_authority_invalid` / `cross_signing_reset_signature_invalid` / `cross_signing_reset_generation_mismatch` |
| `recovery_unlock` | (a) `recovery_secret_ref` 只解析到 recovery session 创建时 snapshot 的 accepted `recovery_policy.recovery_keys[]` 签名 entry（必须在 `issued_at` 时刻 authoritative，未撤销 / 未过期）；DID Document-only key 与 `recovery_key_agreements[]` HPKE key 均 MUST reject；(b) `signature` 验证使用该 signing entry 绑定的 public key、`alg` 在 entry 的算法白名单内、覆盖 §14.1 canonical input（**密码学强度仅由本签名提供**——拥有 recovery-proof 私钥即视作 unlock 通过）；(c) `unlock_commitment` 等于 `SHA-256(utf8("ak.cross-signing-reset-unlock-binding-v1\n") \|\| recovery_secret_ref \|\| unlock_binding_input_bytes)`；`unlock_binding_input_bytes` 按 §14.1 定义，使用同一组 reset 字段，但 `proof_body` 同时排除 `signature` 与 `unlock_commitment`，避免 commitment 对自身取 hash。这是一个**完全由公开材料派生**的 wire-integrity 哈希，receiver 用事件自身的 `recovery_secret_ref` 与 `unlock_binding_input_bytes` 重算后比对；它**不证明持有 recovery secret**（signature 已承担该证明），但绑定 proof 到具体 ref + reset 内容，阻止把同一 ref 的签名跨 reset 复用为另一组 (principal_id, generation) 的 proof shell。 | `cross_signing_reset_recovery_ref_unknown` / `cross_signing_reset_signature_invalid` / `cross_signing_reset_unlock_commitment_mismatch` |
| `device_quorum` | (a) 每个 `signatures[i]` 的 `verification_method` 是当前 principal device set 中**已授权且未撤销**的 device key（按 `signatures[i].device_id` 查找其 `ak.device.authorize` 记录），并验证 `signature` 覆盖 §14.1 canonical input；(b) `signatures[]` 按 `device_id` 去重；(c) 去重后**有效**签名数 ≥ `threshold`；(d) `threshold` 等于 receiver 当前 `recovery_policy.device_quorum.k`（或等价已发布门限策略），小于该值 MUST 拒（`recovery_policy` 自身的发布 / 修改授权——含降低 `device_quorum.k`——受 [`../identity/key-management.md` §8.1](../identity/key-management.md) 的 ratchet 约束:MUST 由当前 principal signing key 或满足旧 policy 门限的 quorum 签名、`version` 严格递增，因此单设备无法单方面调低本门限）。 | `cross_signing_reset_signature_invalid` / `cross_signing_reset_quorum_insufficient` / `cross_signing_reset_quorum_below_policy` |
| `trusted_recovery_service` | (a) `service_id` 出现在 recovery session snapshot 的 accepted `recovery_policy.trusted_recovery_services[]` 中、未撤销、`issued_at` 在其有效窗口内；DID Document-only 声明不充分；(b) `verification_method` 是该服务**已公布**的 verification method；(c) `signature` 覆盖 §14.1 canonical input；(d) 若 policy entry 要求 attestation，`attestation_ref` 在同 `trust_domain` 可验证；(e) `recovery_session_id` 指向当前 verified、未过期、未消费的 session，且该 session 的独立 proof kind 为 `principal_signing` / `recovery_unlock` / `device_quorum`，不得仍为 trusted service。 | `cross_signing_reset_recovery_service_unknown` / `cross_signing_reset_signature_invalid` / `cross_signing_reset_attestation_missing` / `cross_signing_reset_recovery_service_attestation_domain_mismatch` / `cross_signing_reset_second_factor_missing` |

通用规则：

- 所有 proof 的 `alg` MUST 在 [`conformance/encoding.md` §6.1](../conformance/encoding.md) 的 Signature Suite registered set（签名算法白名单）内；未列入算法 MUST `unsupported_signature_alg`。
- `issued_at` 与 receiver 本地时钟偏差超出 [`ak.profile.cross_signing.reset.v1`](../../artifacts/profiles/conformance-profiles.json) 声明的 `parameters.max_clock_skew_seconds`（默认 300s，允许范围 60–900s）MUST `cross_signing_reset_clock_skew_exceeded`。
- 同一 `(principal_id, previous_generation)` 已被某条 reset 消费后，新到达的 reset MUST 以 `cross_signing_reset_replayed` 拒绝；replay-rejection 缓存保留时间不得少于 profile `parameters.reset_replay_cache_min_retention_seconds`（默认 90000s，对应 24h + 1h slack），且必须覆盖 `parameters.publish_recovery_window_seconds`（默认 86400s）所定义的"reset → publish"窗口。
- Receiver MUST 在接受 reset 后 `parameters.publish_recovery_window_seconds` 之内观察到对应的 `ak.cross_signing.publish`；超时未观察到 MUST 进入 §14.2 第 6 项的 "无可用 SSK / USK" 状态，并拒绝任何引用 `new_generation` 的设备授权事件。

## 15. Device Recovery Lifecycle

> 本节的端到端流程 MUST 由一个 `RecoveryTransaction` 承载：`transaction_id` 与全部公开
> Event/object/series id 在首个不可逆副作用前固定，响应丢失与 coordinator 重启从该 resource
> 续跑而不是重新生成。闭合步骤顺序、typed binding 与幂等合同见
> [`../identity/security-transactions.md` §2](../identity/security-transactions.md)。

设备恢复是一个端到端状态机，不能只靠单个 reset proof 或 key backup 下载完成。合规实现 MUST 按以下顺序闭环：

`ak.schema.recovery_session.v1`（[`recovery-session.schema.json`](../../artifacts/schemas/recovery-session.schema.json)）规范化 recovery-session wire contract。Create/get/proofs 的请求响应 shape、`principal_signing` proof 形态和 transcript fixture 均由该 schema 的 `$defs` 固定。session 没有公开 complete operation；`verified → completed` 只能由绑定的 RecoveryTransaction terminal commit 原子推进。

状态机（normative）——状态值固定为 `pending` / `verified` / `completed` / `rejected` / `expired`，合法转换为下表的封闭集合；表外转换 MUST reject：

| 当前状态 | 允许的出边 |
| --- | --- |
| `pending` | `verified` / `rejected` / `expired` |
| `verified` | `completed` / `expired` / `rejected` |
| `completed` / `rejected` / `expired` | 终态，无出边 |

- **`expired` 语义**：`expires_at` 过后仍处于非终态（`pending` / `verified`）的 session MUST 视为 `expired`。实现 MAY 在读取时惰性求值，或 MAY 显式写入状态字段，但对外可观察状态 MUST 一致——同一时点对同一 session 的任何读取不得返回不同状态。`verified` 后未在 `expires_at` 前由绑定 RecoveryTransaction 成功 terminal commit 的 session 同样按本条过期；transaction 不得越过 session expiry 补写完成。
- **`rejected` 进入条件**：proof 校验失败次数达到服务端策略上限，或服务端风控 / 操作员显式拒绝。进入 `rejected` 时 MUST 写入 `rejection_reason_code`，取值为封闭枚举：`proof_failed`（proof 校验失败达到策略上限）、`operator_rejected`（操作员 / 管理面显式拒绝）、`risk_policy`（服务端风控策略拒绝）、`superseded`（被同 principal / device 的新 recovery session 取代）。
- **终态请求**：对处于终态（`completed` / `rejected` / `expired`）的 session 调用 `submit_proof`，或尝试把它绑定到新的 RecoveryTransaction，服务端 MUST 返回 `failed_precondition`，reason_code=`recovery_session_terminal`。协议不存在 public complete 请求。

1. **Recovery policy 与模型快照**：新设备只声明 `principal_id`、`requesting_device_id` 与 trust domain；create request 不携带 `identity_model` 或 generation。coordinator MUST 从 accepted control state 推导模型，不能信任客户端自报；创建 session 时 snapshot `(policy_id, policy_version)`，并且 A 模型 snapshot `ssk_generation`，B 模型 snapshot `current_device_generation_ref`、`device_generation_status`、DID registry head 与 accepted Seal frontier。B 模型状态不是 `active` 时只允许满足 [`identity/key-management.md` §5.0.7](../identity/key-management.md) 的冲突解除形态。challenge 是单 session、单次使用的 256-bit CSPRNG 值；默认 TTL 900s，可缩短不可任意延长。
   coordinator 还必须从同一 accepted state生成closed
   `publication_authority_context`及其JCS digest：A从accepted
   `ak.cross_signing.publish`投影固定
   `ak.authority_set.recovery_cross_signing.v1` concrete policy、snapshot SSK、control
   scope、basis与`[ak.device.authorize, ak.device.list_update]`；B从accepted sealed
   recovery policy及其immutable `acceptance_basis`投影固定
   `ak.authority_set.recovery_identity_reanchor.v1` concrete policy、
   各proof family的完整authorization rules、scope/basis与`[ak.device.reanchor]`。context不能由客户端自报，
   也不能在session存续期内随live state漂移；context的basis必须逐字等于policy
   `acceptance_basis`，不得借用device-generation frontier。缺少可从同一basis重算的concrete policy时create
   必须fail closed。context不得在proof前预测单个verification method；A的单一SSK只是
   单rule、单issuer、threshold=1的特例。“零 Seal frontier”仅指B模型的
   device-generation/re-anchor frontier可以为空；accepted recovery policy自身仍必须有
   acceptance Seal/SealBasis。
   recovery policy必须携带由policy签名覆盖的
   `publication_authorization_rules[]`，与`allowed_proof_kinds[]`一一对应；coordinator仍必须从
   acceptance basis重算其exact verification methods。Shamir `threshold.k`只控制secret
   reconstruction，不是lease PayloadProof quorum；reconstructed recovery signing key对应的rule
   threshold固定为1。proof verified后，prepared plan与lease必须把
   `authorization_rule_id`固定为该proof kind对应的rule id；即使其它rule也允许
   `ak.device.reanchor`，也不得按action或issuer集合重新选择。
2. **Recovery proof**：proof kind 仍由 accepted recovery policy 选择。使用用户 recovery secret 时，签名 key MUST 是 [`identity/key-management.md` §3.3](../identity/key-management.md) 的 Ed25519 `recovery-proof` 子键，不是 identity root，也不是 X25519 backup-HPKE key。所有 proof transcript 必须从 stored session 重建并绑定 `{schema, kind, identity_model, principal_id, requesting_device_id, trust_domain, policy_id, policy_version, recovery_session_id, model_generation_ref, publication_authority_context_digest, challenge, expires_at, created_at, proof_body?}`；`schema="ak.identity.recovery_proof.v1"`。A 的 `model_generation_ref` 是 decimal SSK generation；B 是当前 DID versionId。客户端复制的 policy/model metadata 不得成为权威输入。

   `recovery_unlock` 的 `recovery_secret_ref` 必须解析到 session created-at 时 authoritative 的 policy entry，`verification_method` 必须等于该 entry 对应的 recovery-proof public key。signature 覆盖 generic transcript；`unlock_commitment` 继续使用 `ak.recovery-session-unlock-binding-v1\n` 域并绑定同一 transcript。root 或 backup-HPKE key 签名 MUST reject。
3. **A 模型完成出口**：仅 A 模型可在 proof verified 后用 backup-HPKE key打开承载 SSK 的 recovery-directed envelope，以 snapshot generation 的 SSK 签 `cross_signing_binding`，并仅按session publication context为固定authorize/list Event签发短期high-risk lease。客户端必须在 RecoveryTransaction create 中提交固定 `ak.device.authorize` + `ak.device.list_update` prepared batch；coordinator 只通过 `submit_authorize_unit` 提交该 batch。terminal executor 必须从 accepted batch receipt复验 principal/device/session/generation/actor chain，并在同一 durable commit 接受设备 terminal receipt、追加最后 accepted step、写 completion attestation、推进 transaction 与 session。generation或lease authority context不符为`device_recovery_ssk_generation_mismatch`或`authorization_denied`。
4. **B 模型完成出口**：B 模型没有 SSK。RecoveryTransaction create 必须先固定 ticket id、authority authorization preimage、entry N canonical bytes、带session-context lease的reanchor Event submission、authorize Event id与closed publication intent。publication intent还必须携带从pre-fence accepted DID document投影的`ak.authority_set.recovery_account_authority.v1` concrete policy；candidate entry N只能延续或收紧该委托，不能为本次pre-fence lease首次创造Account Authority。coordinator 按 [`identity/security-transactions.md` §2.2](../identity/security-transactions.md) 先签发 transaction-bound ticket、取得 byte-stable enrollment-authority-signed `ak.device.authorize#R`及同一durable outcome中的authority-signed lease，再发布 entry N，最后原子提交固定 `ak.device.reanchor` + authority output。terminal executor 必须从 accepted batch receipt复验 ticket、DID head snapshot、完整 pre-fence frontier、两个 event digest、replacement device/session 与 generation fence，并按上一条的同一 durable terminal commit 推进 transaction 与 session；不得只看 event store 中两条孤立 Event。可选 `ak.device.list_update` 只能在 unit accepted 后由新设备正常提交，不是 re-anchor unit 的替代。
   该 B 模型出口的正负向行为必须通过 `ak.vector.identity.device_reanchor.v1`。
5. **Backup unlock 顺序**：proof verified 后可用 §3.3 backup-HPKE key打开 policy 允许且属于 recovery bootstrap 的 envelope。A 模型授权前需解开承载 SSK 的 recovery-directed `secret_storage`；B 模型授权前只需 DID/root recovery orchestration material，不得寻找或生成 SSK。其余 `secret_storage`/`mls_history` 在新设备 authorize accepted 且 generation 校验通过后释放，并继续执行 active-series/frontier rules。服务端不得把 recovery proof 当长期 bearer token。
6. **MLS 与 ready**：B 模型把 pre-fence epoch key 视为可能泄露，必须推进到新 epoch；A 模型 Welcome generation 必须等于当前 SSK generation。secret storage、device state、关键 Welcome/history share 未完成前只可显示 `recovery_pending`。
7. **Finalize/audit**：正式 recovery receipt 只能由已接受的新设备 key 在观察到 transaction accepted outputs 后签，绑定 session、policy、identity model、`previous_model_generation_ref`（session snapshot）、`result_model_generation_ref`（完成后的 accepted generation）、proof digest、B 模型 ticket/DID entry/batch receipt/reanchor/authorize refs（A 模型则绑定 authorize/list refs）、所有解锁 backup summaries、Welcome summary、outcome 与时间，并签名绑定所属 RecoveryTransaction 的 `transaction_id`、稳定 `request_digest` 与 `prepared_plan_digest`。客户端离线时 coordinator 必须停在 `awaiting_device_attestation`，不得预签 receipt 或返回 completed。receipt 中的 `backup_classes_unlocked[]`、`welcome_count` 与 `outcome` 是**设备签名的声明**，服务端可以验证签名、引用、digest 与 release state，不得据此声称观察到设备完成解密或 MLS secret 导入。A 模型未 reset 时前后 generation 相等；B 模型 result 必须等于 re-anchor DID versionId。同一 session 的 **byte-identical** receipt 重放是幂等的，MUST 返回已存储的 receipt；只有同一 session 的**第二份不同** receipt 才 reject。授权前失败只写 server outcome/audit evidence，不得伪造 device-signed receipt。正式完成后，受限 recovery grant 只能通过 `ak.gate.account.command.promote_recovery_session_grant` 轮换成新设备 grant；旧 grant不得原地扩权。

KeyPackage low-water refresh：claim 失败后 KeyPackage 不得自动放回；**self / owning-device maintenance** 响应 SHOULD 返回 `available_count`、`low_watermark` 和 `suggested_publish_count`，peer surface 不得返回这些库存字段。当 `available_count < low_watermark` 时，设备 SHOULD 发布新的 KeyPackage；若低水位持续低于 Realm policy 的最小值，发送方 MAY 延迟新设备 Welcome 并返回 `keypackage_refresh_required`。同一 device 多个 KeyPackage 的选择 MUST 使用服务端返回的最早 unclaimed package 或 deterministic order，不得按本地随机重试导致重复 claim。

## 16. Applet Device Delegation

Applet 如需代表 Ghost Actor 或桥接用户参与 E2EE，MUST 使用受限 delegated device：

- device id MUST 标记 `applet_id`。
- capability MUST 限制 Realm、协议、动作和有效期。
- delegated device 不得签发新的 human device。
- delegated device 的 to-device 权限 MUST 只覆盖其 namespace 内 actor。
