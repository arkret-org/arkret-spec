---
title: Account Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-07-16
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret 身份由 DID principal 表示，但用户访问通常经过一个或多个服务账户、OAuth/OIDC session、device token 和 Principal Server / Events API。本文件定义这些层的锁定、暂停、注销、软登出、数据擦除和服务账号生命周期。

## 2. 分层

| 层 | 示例 | 生命周期控制者 |
| --- | --- | --- |
| DID principal | `did:webvh:...` | DID controller / recovery policy |
| Service account | `alice@example.com` 登录入口 | account service |
| Device session | session grant / grant-binding key | auth service |
| Event / private state | signed Event history / private account data | Events API + principal policy |
| Realm membership | `ak.member.state`（状态机定义见 [`../models/realm-and-space.md`](../models/realm-and-space.md)） | Realm policy/capability |

服务 account 被注销不等于 DID 消失。DID 被恢复或轮换不等于所有服务 session 继续有效。

## 2.1 服务账号登录与找回

服务账号 MAY 使用用户名/密码、passkey、WebAuthn、OAuth/OIDC、企业 SSO 或类似集中认证服务的登录方式。它们只证明调用方通过了某个 account service 的认证，不能直接证明 DID principal 所有权。

登录成功后，account service / auth service MUST 将会话绑定到 DID principal 与设备，例如签发短期 `ak.session.grant`、登记 device binding，或要求客户端提交 DID proof。资源服务器随后验证 grant、device、capability、Realm policy 和撤销状态。

### 2.1.1 Account-first onboarding

实现 MAY 提供 account-first 体验：用户先通过 `@alice:example.org`、邮箱、手机号、企业 SSO、OIDC 或邀请链接完成注册和登录，客户端不要求用户理解或手动输入 DID。

在这种模式下，account service / auth service MUST 在允许持久写入前完成以下动作之一：

- 绑定到用户已控制的 principal DID，并验证 DID proof、device binding 或等价 session grant。
- 由客户端创建并签名受支持的 principal DID，服务只托管已签名 history/提供 enrollment authority，并记录 delegation、recovery policy、trust domain、service-account 绑定和审计证据；服务不得生成或持有 identity root。

account-first DID 分支必须执行 [`key-management.md` §5.0.1](./key-management.md) 的两道门：entry 0 发布前完成 custody confirmation；bootstrap 后只允许 gate-closing 首个 Seal、genesis recovery policy 与 `did_recovery` material，直至 recovery-material gate 完成。`personal_node + single_point_of_failure=true` 只允许以本地持久化替代人工抄录确认，不得跳过同一恢复状态标记与持续风险提示。

未绑定 DID 的 session MAY 执行注册、风险检查、邀请预览、邮箱验证、设备初始化等 pre-registration 操作；MUST NOT 作为最终 actor 提交 Realm Event、capability grant、MLS membership、service delegation 或 federation transaction。

如果用户后续改用自有 DID、pairwise DID 或组织私有 DID，服务 MAY 根据 policy 迁移 handle、service account binding、credential 或后续写入身份。历史 Event 的 `actor_id` 和 grant `subject` MUST NOT 被改写；需要表达迁移时，应发布显式 claim、attestation、profile update 或 account binding record。

### 2.1.2 Account handoff 与首次 DID 绑定

采用 §2.1.1 account-first DID 分支的 Account Authority MUST 实现本节的 holder-bound handoff；不得把普通 OAuth access token、OIDC `id_token`、可续期 refresh token 或未绑定 holder 的 browser cookie 直接当作 Arkret 注册权限。Canonical HTTP binding 与 DTO 见 [`../sync/service-http-binding.md` §2.3](../sync/service-http-binding.md) 和 `account-operations.schema.json`。

`service_account -> principal_id` binding record 仍是 Account Authority 的部署本地状态，不进入 federation，也不成为跨部署 canonical identity fact。本节升格为 canonical 的是**客户端与 Account Authority 之间的绑定仪式**：holder constraint、lease/fence、challenge transcript、DID control proof、幂等与错误语义必须跨实现一致，客户端不能为每个 Account Authority 私有适配一条安全边界不同的 endpoint。实现可自由选择本地表结构，但不得把 canonical ceremony 降级回 `/_<impl>/*` 私有客户端协议。

流程固定为：

1. 客户端对 `ak.gate.account.exchange.create_handoff` 提交 OIDC authorization code exchange proof，并同时提交 RFC 9449 DPoP proof。Account Authority 必须在 authorize transaction 中预先生成并持久化 body proof challenge，换码时一并校验和消费；Account Authority 自己向 issuer `token_endpoint` 换码、验证 issuer / client / redirect / state / nonce / PKCE，并要求 body proof 的 holder signature 与 DPoP JWK 是同一把 Ed25519 key。
2. Account Authority 返回默认且最大 TTL 为 1 hour 的短期 opaque `account_handoff_grant`，并返回已认证 service account 的 canonical `account_handle`，供客户端显示账号及命名本地恢复文件。`account_handle` 是 unsigned UX hint，MUST NOT 被当作 principal 身份证据、授权事实或 `service_account -> principal_id` binding；客户端不得由它推导 DID。handoff 凭据 MUST 绑定 service account、Account Authority audience 与 `cnf.jkt`，MUST NOT 是 `ak.session.grant`，MUST NOT 有 refresh-token 语义，且允许的 operation 集 MUST 精确为 `ak.gate.account.command.issue_identity_binding_challenge`、`ak.gate.account.command.register`、`ak.gate.account.command.issue_session_grant`。它不得认证任何 `/_arkret/self/*`、`/_arkret/root/*`、Realm Event、capability、MLS、service delegation 或 federation 写入。
3. 未绑定账号在同一原子步骤取得 `identity_creation_lease`。租约默认且最大 TTL 为 15 minutes；租约至少持久化 `(service_account, audience, lease_id, holder_jkt, fence, expires_at, reserved_principal_id?, reserved_operation_digest?, state)`；一个 `(service_account, audience)` 同时最多一个未过期 holder。相同 holder 可续租；不同 holder 在租约未过期时只能得到 `identity_creation_busy` 状态，不得取得 fence 或 challenge。
4. 客户端只在本地生成 recovery secret、identity root、next root 与 entry 0 draft，并在发布前完成 custody confirmation；只有 gate 通过后才用 `root_0` 产生 entry 0 method-native controller proof，得到完整签名 DID operation。客户端随后以 handoff + DPoP 调用 `ak.gate.account.command.issue_identity_binding_challenge`，提交这份完整但尚未由客户端直接发布的 operation。Account Authority MUST 验证 operation 形态与 method-native controller proof、从 operation 导出 `principal_id` 与 canonical `operation_digest`，并持久化这份**公开** checkpoint；`operation_digest` 固定为 `sha256:` + `lowercase_hex(SHA-256(RFC8785_JCS(did_operation)))`。checkpoint MUST NOT 包含恢复词、seed、identity-root private key、HKDF PRK 或其可逆封装。
5. Account Authority 生成并持久化一次性 challenge。challenge transcript MUST 绑定 `purpose="account_binding"`、service account（只需服务端状态持有，不得暴露可关联的本地 account id）、`principal_id`、`operation_digest`、`lease_id`、`lease_fence`、`holder_jkt`、Account Authority audience、origin、trust domain、`issued_at`、`expires_at` 与不可预测 nonce；`expires_at - issued_at` MUST ≤ 300 秒。challenge 状态 MUST 位于所有实例共享的 durable store，不能只放进程内 memory；同一 challenge 成功消费一次后，任何重放都 MUST fail closed。
6. 客户端用 entry 0 的 method-native inception control key 签 `identity_creation_control_proof`。对 v1 默认 `did:webvh`，验证 key MUST 是所提交 entry 0 `parameters.updateKeys[0]`，并与 proof 的 `verification_key_multibase` byte-identical；root 不在 DID Document `verificationMethod` 中，验证器不得把“解析已发布 DID 再选 authentication VM”的普通 DID proof 路径误用于此次 inception proof，也不得信任请求另带的任意公钥。
7. 客户端以同一 handoff + DPoP 调用 canonical `ak.gate.account.command.register`，携带当前 lease/fence、原样 DID operation 与 control proof。Account Authority MUST 先 CAS 校验 account / holder / lease / fence / reservation / challenge，再验证 root signature；随后由 Account Authority 内部调用 identity registry 提交 DID operation。只有返回 `accepted`，或返回 `duplicate` 且 canonical operation bytes 与已接受 entry 完全相同、`head_event_digest` 可验证时，才可写 `service_account -> principal_id` verified binding。客户端在该 account-first strand 中 MUST NOT 绕过 register 直接发布 entry 0。
8. 绑定完成后，同一未过期 handoff MAY 以 `SessionGrantRequestBody.proof.proof_kind="pre_registration_handoff"` 调用 `issue_session_grant`。请求仍 MUST 明示已经 verified binding 的 `principal_id`，Authorization 必须是 `DPoP <account_handoff_grant>` 并携带匹配 DPoP proof；Account Authority 必须比较 handoff 所属 service account 与该 binding。handoff 过期时客户端重新认证；不得把 handoff 扩成长期 refresh credential。

采用 B 模型的部署必须由 Principal Server 的部署配置在 `/_arkret/describe` 的 `auth_metadata.account_authority.enrollment_authority_did` pin 首设备入册权威。客户端生成 entry 0 时只使用该部署 pin，并在 Account Authority `describe` 返回同名值时要求二者相等；Account Authority 自身的响应不能成为该 DID 的初始信任源。缺少 pin 或不一致时必须在生成、发布 entry 0 前 fail closed。

`register` 的 identity-creation 分支 MUST 按 `(service_account, principal_id, operation_digest)` 幂等。服务端至少持久化 `reserved -> published -> bound` 进度：registry 已接受但本地 binding 尚未提交时，只能为原 service account 重试完成同一个 binding，不能回滚成“未发布”、不能改绑另一账号，也不能允许新租约改选另一 `principal_id`。相同完整请求重放必须返回已存 outcome 或等价 `duplicate` receipt；challenge 的单次消费与最终 binding commit 必须由同一 durable saga / transaction fence 保护。

如果客户端丢失 handoff holder key，未过期租约不会转让。租约过期后，同一 service account 的新认证 holder MAY 原子递增 fence、取得新 lease，并继承已保留的 `principal_id`、operation digest 与公开 DID operation；旧 fence 从此永久失效。新 holder 仍 MUST 用相同 identity root 对新 challenge 产生 fresh control proof，才能完成 register。只有恢复词而没有旧 DPoP key 的用户因此仍能续跑，但不能用新 holder 改选另一 DID 来覆盖已预留身份。

Account Authority 与客户端 UI MUST 把 service-account 认证凭据（密码、passkey、OIDC/SSO session）和 principal recovery secret 说明为两套正交凭据：重置账号密码只恢复 service account 访问，不恢复、轮换或导出 DID root；输入 recovery secret 只证明或恢复 principal 控制，不重置 service-account 密码。UI 不得用同一个“恢复密钥/恢复账号”标签把两类权力合并描述。

当 service account 已绑定到某个 `principal_id` 时，DID proof MAY 作为恢复该 service account 访问的强证据。恢复服务 SHOULD 通过一次性 challenge 验证用户当前控制该 `principal_id`，再允许重设 service account 密码、重新绑定 passkey / WebAuthn 凭据、解除 `soft_logged_out`，或签发短期 session grant。该 DID proof MUST 按 DID method 和本地 trust policy 验证 DID Document、key log / method history、当前 authentication key 或授权 device key、challenge audience、origin、过期时间和重放状态。

密码找回或邮箱验证码重置只允许恢复 service account 访问。除非同时满足 DID recovery policy，服务端 MUST NOT 因密码重置而：

- 轮换 DID 控制密钥。
- 授权新长期设备。
- 读取或重包 E2EE secret storage。
- 签发超过短期登录范围的 capability。
- 撤销用户现有设备，除非 recovery policy 或风险处置策略明确要求。

同理，通过 DID proof 恢复 service account 访问，也不会反向恢复、重置或改变 DID 本身。若用户已经丢失 DID 控制密钥，则必须走 DID recovery policy；组织账号恢复流程只能恢复组织 service account，不能替代 DID recovery。

当 service account 恢复结果与 DID 当前控制状态不一致时，服务端 SHOULD 进入 `locked` 或 `soft_logged_out`，要求用户用已授权设备、recovery key、门限恢复、企业管理员多方审批或 DID proof 完成重新绑定。

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
| `soft_logged_out` | auth service / 用户 logout | 已撤销 | 可在 fresh DID/device proof 下 refresh | 保留 | 保留 | 保留 | §4 |
| `locked` | 安全风险检测 | 已撤销 | SHOULD 拒绝 | 保留 | 保留 | 保留 | §5 |
| `suspended` | 治理 / 合规 | 拒新发 | 拒新发 | 保留 | 保留 | 保留 | §6 |
| `deactivated` | 用户 / 管理员关账 | 已撤销 | 已撤销 | 标记 revoked | 客户端可清除 | 保留 | §7 |
| `erasure_pending` | 用户擦除请求 / GDPR | 已撤销 | 已撤销 | 已撤销 | 必删 | 按 redaction policy 最小化 | §8 |

`reason_code` 表达**为什么**进入该状态（如 `abuse_review` / `gdpr_request` / `password_compromise`）；状态本身表达**当前所处阶段的协议行为契约**。两者不可替代。

**认证错误码（normative）**：Account status 导致 session grant 或 grant-binding proof 失效时，服务端 MUST 返回与 current status 匹配的专用错误码，而不是退化成通用 `unauthenticated` / `capability_denied`。已签发 session 访问受保护 `/_arkret/self/*` 资源时：`soft_logged_out` 返回 `401 soft_logged_out`；`locked` 返回 `401 account_locked`；`deactivated` 返回 `401 account_deactivated`；`erasure_pending` 返回 `401 account_erased`。新 session grant 签发、session refresh 或登录完成阶段遇到当前 status 时：`locked` SHOULD 返回 `403 account_locked`；`suspended` MUST 返回 `403 account_suspended`；`deactivated` SHOULD 返回 `403 account_deactivated`；`erasure_pending` MUST 返回 `401 account_erased`。这些 code 的机器真源是 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)；HTTP status 的差异只表达“已持有 grant 失效”与“新 grant 被 policy 拒发”的入口差异，不改变 account status 语义。

**合法状态转换（normative）**：上面的 severity-order 仲裁解决"并发 head 选谁"，不替代"哪些 `from → to` 转换本身合法"的定义。`ak.account.status` reducer MUST 按下表判定单条状态转换是否合法；非法转换 MUST `failed_precondition`，`reason_code="account_status_transition_invalid"`：

| from \ to | `active` | `soft_logged_out` | `locked` | `suspended` | `deactivated` | `erasure_pending` |
| --- | --- | --- | --- | --- | --- | --- |
| `active` | —（同态重放） | ✓ | ✓ | ✓ | ✓ | ✓ |
| `soft_logged_out` | ✓（§4，须 fresh DID proof） | — | ✓ | ✓ | ✓ | ✓ |
| `locked` | ✓ | ✓ | — | ✓ | ✓ | ✓ |
| `suspended` | ✓（appeal 解除，须 `supersedes_status_event_id`） | ✓ | ✓ | — | ✓ | ✓ |
| `deactivated` | ✗（见下"重激活"） | ✗ | ✗ | ✗ | — | ✓ |
| `erasure_pending` | ✗ | ✗ | ✗ | ✗ | ✗ | —（terminal） |

- **降低严格度**（任一 `to` 严格度低于 `from`，如 `suspended → active`、`locked → soft_logged_out`）的转换 MUST 满足规则 2（引用 `supersedes_status_event_id` 且在当前 Seal view 可见），否则按并发候选处理，不构成有效转换。
  - **例外：`soft_logged_out → active` 自助恢复**（normative）：该转换由 §4 的 fresh DID proof（设备 / principal 重新证明控制权）授权，**不要求** `supersedes_status_event_id`；fresh DID proof 即构成有效降严格度转换的充分凭据。其余降严格度转换（`suspended → active`、`locked → *` 等）仍按规则 2 要求 `supersedes_status_event_id`。
- **`erasure_pending` 为 terminal**（规则 3）：其唯一出边为空，任何转出 MUST 拒绝 `erasure_pending_is_terminal`。
- **`deactivated` 重激活**（normative）：v1 **不**允许同一 `account_id` 的 `deactivated → active` 等任意降严格度转换。§7.1 的 deactivation fanout 对绑定到该 account 的 device、KeyPackage、session、push 与 to-device 资源不可逆；需要恢复访问的用户 MUST 创建新的 service account（新 `account_id`）并走完整 onboarding，可继续绑定同一 principal DID，但不得复活旧 account 或旧资源。`deactivated` 的唯一合法出边是 `erasure_pending`。实现 MUST NOT 接受声称把该 `account_id` 的 `deactivated` 降级回较低严格度状态的 `ak.account.status` event（`account_status_transition_invalid`）。

状态发布为服务侧 signed account status：

```json
{
  "kind": "ak.account.status",
  "account_id": "acct_...",
  "principal_id": "did:webvh:...",
  "status": "suspended",
  "reason_code": "abuse_review",
  "effective_at": "2026-04-26T00:00:00Z",
  "appeal_uri": "https://example.com/appeal/acct_...",
  "signature": {"kid": "did:webvh:zGtABZixoZZ3m4cFx3E65LCmg:auth.example#key-1", "sig": "..."}
}
```

Current account status projection 是 ordered_log 上的确定性派生值，而不是简单取本地最后到达的 event。cell family `ak.component.account.status.v1` 的 `cell_subject` 是 `account_id`；`principal_id` 是该 service account 的绑定主体，不是 lifecycle key。本节定义的 severity-order 仲裁是该 cell 上的 canonical projection。若同一 `account_id` 出现并发 `ak.account.status` head，client / server MUST 按以下规则选择当前状态；同一 principal 绑定的其它 `account_id` MUST 独立求值：

`account_status_payload.expires_at` 仅是管理端与 UI 的复核 / 续期提示，不参与 reducer projection，也不会在到时自动解除 `locked` / `suspended` 或其它状态。解除或改变状态仍 MUST 提交新的 `ak.account.status`，并遵守下述 severity、`supersedes_status_event_id` 与 terminal 规则；receiver MUST NOT 根据本地墙钟合成状态事件。

1. 严格度高者优先：`erasure_pending` > `deactivated` > `suspended` > `locked` > `soft_logged_out` > `active`。
2. 降低严格度的状态（例如 appeal 后回到 `active`）MUST 在 payload 的 `supersedes_status_event_id` 字段（见 [`event-payload.schema.json#/$defs/account_status_payload`](../../artifacts/schemas/event-payload.schema.json)）引用被解除的 status event id，且该引用必须在当前 Seal view 可见；否则它只是并发候选，不能覆盖更严格状态。
3. **`erasure_pending` 是 terminal 状态（normative，不可逆）**：一旦某 `account_id` 的 account status projection 进入 `erasure_pending`，它 MUST NOT 被任何 `supersedes_status_event_id` 引用降级回 `deactivated` / `suspended` / `locked` / `soft_logged_out` / `active` 中的任意一个。任何声称把 `erasure_pending` superseded 为较低严格度状态的 `ak.account.status` event MUST 被 reducer / projection 拒绝（`erasure_pending_is_terminal`），并保持 `erasure_pending` 为 current。理由：擦除流程一旦开始即对 blob bytes、account private state、受托 projection 执行不可逆的物理删除/最小化，把状态"恢复"为 active 会产生一个数据已被销毁却显示为正常的不一致账号。需要在擦除真正执行前撤销的，应在进入 `erasure_pending` 之前用较低严格度状态处理；进入 `erasure_pending` 之后只能继续完成擦除并发布 erasure receipt（§8）。`erasure_pending` 之上没有更严格状态，故规则 2 的"降低严格度"路径对它不适用。
4. 同严格度并发时，先按 domain 语义主键 `effective_at` 取较晚者；`effective_at` 仍相等的并发 head，最终消歧 MUST 落到 [`../conformance/encoding.md` §4.2](../conformance/encoding.md) 的统一 canonical tie-break(`event_digest` bytewise 最大值)，而**不**用 `event_id`——`event_id` 是 UUIDv7，其时间戳前缀是 producer 设定的墙钟量，用作 tie-break 会重新引入墙钟依赖。被选中者为 projection current，其他 head 仍保留在 ordered_log conflict/audit view 中。

**Deactivation 进度 flag（normative）**：`status` 是封闭 6 值枚举（不含下列 token）。`deactivation_partial`（§7.1）与 `deactivation_federation_incomplete`（§7 末）**不是** `status` 值，而是 `deactivated` 状态下叠加的**独立服务侧 flag**，表达 deactivation fanout 的完成进度：

- `deactivation_partial`：boolean，默认 `false`。当某条本地 fanout（session/device/applet/KeyPackage/push/to-device）因网络或服务不可达失败、服务端仍在重试时为 `true`。`status` 仍为 `deactivated`。
- `deactivation_federation_incomplete`：boolean，默认 `false`。当该 principal 曾在其它 Principal Server 持有状态、源 Principal Server 未在 `deactivation_propagation_window_ms` 内得到 peer ack 时为 `true`，并触发 §7 末列出的写入暂停。`status` 仍为 `deactivated`。

二者均为服务侧投影 flag，与封闭 6 值 `status` 正交，MUST NOT 作为 `status` 取值出现在 wire 上；客户端 UI 据此区分"停用进行中 / 已完成"。

## 4. Soft Logout

`soft_logged_out` 表示当前 session grant 不再可用，但本地加密数据和 device trust 可保留。客户端 SHOULD：

- 停止 sync。
- 清除当前 session credential。
- 保留 device keys 和 secret storage 本地密钥，除非用户选择清除。
- 使用 session grant refresh、OIDC 或 re-auth 恢复，但恢复请求仍必须携带 fresh DID/device proof。

服务端返回 `401 soft_logged_out` 时 MUST NOT 要求客户端删除本地 E2EE 密钥。

`soft_logged_out -> active` 的恢复 MUST 绑定 fresh DID proof：session grant refresh、OIDC callback 或 re-auth 只能作为会话恢复材料，不能单独把账号状态恢复为 `active`。服务端 MUST 要求当前 principal DID 的授权 device key、account auth key、passkey 或 recovery policy 允许的密钥对一次性 challenge 签名，并把签名覆盖 `principal_id`、`device_id`、`audience`、`request_canonical_digest`、`challenge`、`issued_at` 与 `expires_at`。**`device_id` 绑定要求**:multi-device principal（principal 控制 ≥1 个授权 device key）下 `device_id` **MUST** 必填并被签名覆盖，绑定到发起恢复请求的具体 device，使该 challenge-response proof 不能被同 principal 的其它设备复用完成会话恢复（满足"会话绑定到 DID 与 device"目标）；仅当 principal 在 control stream 中**无任何未撤销 device record**（即不持有任何当前有效的 device-bound key，例如纯 account-auth-key / passkey 恢复路径）时 `device_id` 方可省略。服务端 MUST 依据该 principal control stream 中 device record 的当前状态（存在 ≥1 条未撤销 device record 即豁免不成立）判定豁免，**MUST NOT** 仅凭本次 proof 的签名 key 类型判定——否则持有未撤销 device-bound key 的 multi-device principal 可用 passkey / account-auth-key 签 proof 伪造"无 device key"假象，从而绕过本节要关闭的同 principal 其它设备复用 proof 窗口。豁免不成立时 MUST NOT 接受缺 `device_id` 的 proof。

**豁免判定的 frontier 新鲜度（normative，fail-closed）**：上述"无任何未撤销 device record"豁免判定 **MUST** 基于 **fresh control-stream frontier**——即服务端读取的 principal control-stream device 集投影必须满足本地 freshness policy（与 [`../authz/capabilities.md` §18.2](../authz/capabilities.md) 高风险 action 在 freshness `unknown` 时 fail-closed 的纪律一致）。当 control stream 因分区 / outage 不可达、frontier stale 或 device 集投影 freshness 为 `unknown` 时，服务端 **MUST** 保守按"该 principal 存在 device record"处理：即视为 multi-device principal，`device_id` 必填且必须被签名覆盖，缺 `device_id` 的恢复 proof **MUST NOT** 被接受（豁免不成立）。**MUST NOT** 把"暂时读不到 device record"乐观解释为"无 device record ⇒ 可省略 `device_id`"——否则攻击者可在分区窗口内用 passkey / account-auth-key 签一份缺 `device_id` 的 proof，伪造"该 principal 无 device key"假象绕过设备绑定。`did:webvh` resolver 处于 §3.4 cache-only degraded mode 时该恢复 / 绑定路径属于高风险写入，遵循 [`identity-did.md` §3.4](./identity-did.md) 的 fail-closed 不变量。其中 `issued_at` 与 `expires_at` 是 **必填**（不再是可选）：服务端 MUST 拒绝缺失任一字段、`expires_at` 已过当前时钟、`expires_at - issued_at > 300s`、`issued_at` 相对服务端时钟的偏移（双向）超出 skew 容忍（SHOULD ≤ 300s），或 `issued_at` 晚于服务端当前时钟加 skew 容忍（即 proof 自称在未来签发）的 proof。这把 soft-logout 重放窗口的上界固定为 ≤ 300s，与 [`identity-did.md` §5.1](./identity-did.md) `ak.did.proof` 的 replay window（`expires_at - issued_at ≤ 300s` + skew ≤ 300s）对齐——否则签发方可把 `expires_at` 任意拉远，使一份 soft-logout 恢复 proof 在无上界的时间内反复重放。缺失该证明时返回 `401 did_proof_required`；`expires_at` 缺失或新鲜度超限时返回 `401 did_proof_required`（reason `did_proof_replay_window_exceeded`）；grant-binding proof 单独存在时也 MUST NOT 静默签发新的 active session grant。

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
2. **Account Authority → Auth-side** MUST 登出当前 grant 所属的 Auth-side session / `browser_session` 并终结其 `ak.session.grant` 轮换链。若 Auth-side 不在同进程，Account Authority MUST 调用标准 S2S 子操作 `POST /_arkret/gate/account/auth-sessions/logout`(`ak.gate.account.command.logout_auth_session`)；该调用 MUST 使用 Account Authority → Auth Server 的部署内 S2S bearer（同 `session_grant_introspection_bearer` 认证族），MUST NOT 复用客户端为高层 `/logout` URL 铸造的 DPoP proof。此后 (i) 凭同一 `cnf.jkt` grant-binding proof 调 `refresh` MUST 被拒(`session_logged_out`)，整条轮换链不可再续；(ii) 该 Auth-side session 下任何 grant 的 introspection MUST 返回 inactive(即 grant-binding key 不能在登出后重建或维持会话)。
3. **Account Authority → Principal-side** MUST：作废该 grant 的本地 session-grant 内省缓存（下次内省即得 `active=false`）、吊销 / 标记该 principal 本地 account session 与**本地设备会话记录**(使后续以该设备签名的 device-scoped 操作在本 Principal Server fail closed)+ drop 该设备的待投递 to-device 消息，并移除该设备作用域内的 push registration。因 Principal Server 不为客户端铸独立本地 bearer（会话凭据即 grant 本身，见上），此处无单独的本地 bearer 可撤——作废内省缓存 + 撤设备会话记录即足以使该设备后续 `/_arkret/self/*` 请求 fail closed。此操作终结该设备在本 Principal Server 的本地会话状态，但 **不** 改写 `ak.account.status`、不发 `ak.device.revoke` 协议事件、不擦除 durable device authorization 历史(用户重新登录即可在本设备恢复)。注意它与 `ak.gate.account.command.revoke_session`(仅撤 session grant、不触设备会话记录，用于"撤某个会话但保留设备")是不同操作。

`POST /_arkret/gate/account/auth-sessions/logout` 是部署内部 S2S 子操作，不是客户端 account flow。该子操作 MUST 幂等：同一 Auth-side session / grant 已登出、已吊销、未知或已被剪枝时，Auth Server 仍 MUST 返回成功并把链视为已终结；鉴权失败、请求体不合法、或 Auth Server 无法确认完成时才返回错误。普通客户端、inkson、浏览器 UI 与移动客户端 **MUST NOT** 调用或自行派生该路径；即使高层 `/logout` 失败，客户端也只能重试 `ak.gate.account.command.logout`。客户端和服务实现 **MUST NOT** 依赖任何实现私有 / 产品私有(例如 `/_<impl>/*`)路由完成登出。

**登出耐久性(normative)**：hard logout 的本地清除(步骤 1)与 Account Authority 服务端编排(步骤 2、3)不是原子的——客户端在清本地凭证后、Account Authority 返回前可能崩溃、关页或离线。为防止「本地已登出但服务端轮换链仍存活」的窗口，客户端 **SHOULD** 在执行本地清除**之前**把登出意图(至少：Account Authority `/logout` endpoint、grant JWT、用于铸 grant-binding(DPoP)proof 的 grant-binding key)持久化(journal)，并在调用失败时重试(含下次启动重放)，直至 Account Authority 确认 grant 链终结后方清除该 journal。其中 Auth-side grant + `browser_session` 终结是耐久性关键步：它一旦完成，轮换链不可再续，后续无法恢复本地 account session。由于 `ak.session.grant` 有受限 TTL(见 [`crypto-media/device-lifecycle.md` §3.3](../crypto-media/device-lifecycle.md))，客户端 **MAY** 在该 TTL(加时钟 skew 容忍)过后停止重试：此时整条链已因自然过期失效，journal 中已无可吊销之物。重试 **MUST** 幂等——对已吊销/已过期 grant 再次调 hard logout 不应被视为错误。

**执行顺序与失败语义(normative)**：Auth-side session logout / grant-chain 终结是耐久性关键步，Account Authority SHOULD 先完成步骤 2，再完成 Principal-side 本地清理。若步骤 2 失败且没有可证明的 durable completion，Account Authority MUST NOT 向客户端返回 `ok=true`；应返回可重试错误（例如 `temporarily_unavailable`）。若步骤 2 已成功而步骤 3 暂时失败，Account Authority MAY 返回成功前把 Principal-side 清理持久化到 durable retry 队列；重复执行高层 `/logout` MUST 幂等。客户端在收到失败或网络中断时 MUST 只重试 `POST /_arkret/gate/account/logout`，MUST NOT 直接调用 `auth-sessions/logout`。

**吊销传播与生效语义(normative)**：Account Authority 内部可同步调用或异步重试 Principal-side 终结，但对客户端返回成功前 MUST 至少保证 Auth-side grant 轮换链已不可续。Principal Server 对本地 session 的有效性以「本地 session 记录 + 对 Account Authority / Auth-side 的 session-grant 内省」为准；Auth-side grant/会话被吊销后，Principal Server MUST 在下一次内省时得到 `active=false` 并 fail closed。实现 MAY 缓存内省结果，但缓存 TTL 与本地 session TTL 共同构成吊销生效的上界，二者 SHOULD ≤ 数分钟；高安全 profile SHOULD 更短或对敏感操作旁路缓存。Auth Server / Principal Server MUST NOT 依赖对方主动 push 吊销；Account Authority 是客户端可见的编排边界。

**轮换链单次使用与重用即妥协(normative)**:`ak.session.grant` 轮换 MUST 单次使用——轮换成功即吊销旧 grant；对**已消费**的 grant 再次发起轮换 MUST 拒(`grant_already_consumed`)，且 SHOULD 视为凭证泄露信号并吊销整条轮换链(并入上面的会话终结)。

**与 soft logout 的区别**:soft logout 可凭 fresh DID/device proof(§4)恢复；hard logout 终结 grant 链 + `browser_session`，恢复 MUST 重新走完整认证(新 `browser_session`)，设备密钥本身不足以重建会话。

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
| **KeyPackage** | 标记所有 unused MLS KeyPackage 为 retired；新邀请 MUST NOT 从该 principal 选 KeyPackage。 | reducer + KeyPackage store 失效 |
| **Push route** | 撤销 `ak.device.push_route`；push gateway MUST 停止向该 principal 的注册 endpoint 投递。 | reducer + push gateway 缓存失效 |
| **To-device queue** | 服务端 to-device 队列 drop 所有 `recipient_principal_id == deactivated_principal` 的 pending message；后续投递 MUST `recipient_unavailable`。 | server-side queue 状态 |
| **Identity link cache** | 客户端与服务端可见缓存 MUST eager invalidate 所有 `(*, pairwise_did → deactivated_principal)` 映射；不得等待 7d TTL 或 MLS epoch 推进。 | `ak.identity_link` cache invalidation |
| **Capability cache** | 所有 cached `ak.capability.grant` decision 引用该 principal 作为 subject 或 issuer 的 MUST eager invalidate；下次 capability check 走完整判定。 | cache invalidation |

**写屏障（write barrier）**：`deactivated` accepted 进入当前 account status frontier 后，任何通过该 `account_id` 的 session、device 或 account binding 发起，或以该 account 作为 owner 的新 `ak.session.grant`、`ak.device.authorize`、KeyPackage publish / claim、agent / applet delegation、capability grant / delegation、push route、to-device enqueue 和 Realm membership delivery-binding 写入 MUST `failed_precondition`，`reason_code="account_deactivated"`。该屏障按 `account_id` 的 status frontier 生效，不得被较新的 HLC、不同 device、未完成 federation ack 或尚未失效的本地 cache 绕过；绑定同一 principal DID 的不同 active `account_id` 不受旧 account 屏障影响，但必须用自己的新 session/device/KeyPackage 完成 onboarding。已经在屏障前 accepted 的历史 Event 不被改写；尚处 pending / quarantine / soft-fail 的写入 MUST 在恢复前重新检查该屏障。

约束：

- **不自动 ban**：deactivation 不等于 Realm 内 `ak.member.state` 转 `ban`/`leave`。哪些 Realm membership 自动 `ak.member.state = leave`（自愿停用）vs. 保留 `join`（policy 决定）由 Realm policy component `account_deactivation.member_action` 字段控制（该字段作为 Realm policy component 的登记见 [`../models/realm-and-space.md` §2.1](../models/realm-and-space.md)，经 `ak.realm.policy_components` 写入；本节是其封闭枚举与处置语义的单一权威源）。该字段是封闭枚举，v1 取值域为：
  - `leave_self_initiated`（默认）：把该 principal 在本 Realm 的 membership 视为自愿退出，自动转 `ak.member.state = leave`。
  - `retain_membership`：保留 `join`，由 Realm policy 在后续显式处置（deactivation 本身不改 membership state）。
  - `leave_all`：无条件把该 principal 在本 Realm 的 membership 转 `leave`，等同 self-initiated 但不区分触发方语义。

  未识别的取值 MUST 按未知 policy 字段 fail closed（保守取 `retain_membership` 不主动改 membership，并标记 policy 解析告警），不得静默回退为默认值。注意本字段控制的是 membership state，与上表前 6 行无条件必停的本地投递撤销正交。
- **本地投递必停**：无论 policy 是否 ban，上表前 6 行（session/device/applet/KeyPackage/push/to-device queue）必停 — 否则会出现"账户已停用但其 device 还能签名 / push gateway 还在投递"的不可解释窗口。
- **MLS Remove**：若 Realm policy 决定 deactivate → leave，对应 MLS group MUST 在 grace window（默认 `mls_deactivation_grace_ms = 600,000 ms`）内 emit `ak.mls.commit` Remove；超时未 commit 则该 Realm 的成员客户端 MUST 在 verified timeline 中把该 principal 标 `unverifiable_member`，不再接受其新 epoch 消息。
- Fanout 失败的 partial state：如果某条 fanout 因网络 / 服务不可达失败，server `account_status` MUST 标 `deactivation_partial` 并继续重试；客户端 UI MUST 显式标记 "停用未完成" 而不是显示已停用。
- **跨 Principal Server 传播**：若该 principal 曾在其它 Principal Server 上持有 device / KeyPackage / to-device / push-route 状态，或通过 Realm membership delivery binding 使用过 peer 服务，源 Principal Server MUST 按 [`../sync/federation.md` §4.4.1](../sync/federation.md) 主动推送 `ak.account.status` deactivation。未在 `deactivation_propagation_window_ms` 内得到 peer ack 时，`account_status` MUST 标 `deactivation_federation_incomplete`，并暂停新 Realm onboard、新 session/device grant 与新 KeyPackage 发布。

## 8. Erasure

`erasure_pending` 表示物理删除流程开始。实现 MUST 区分：

- canonical event log：通常只能 redaction/minimization，不能破坏审计 hash 链。
- blob bytes：可按 retention/legal hold 删除。
- 本地/受托 projection：可删除或重新物化。
- account private state：可删除。
- policy/audit record：按合规周期保留最小字段。

**擦除完成态语义（normative）**：v1 **不**新增 `erased` / `tombstoned` 终态。`erasure_pending` 的 "pending" 表示"擦除已发起且不可逆"，**不**表示"擦除尚未完成"——擦除流程进入该状态后 account status projection 永久停在 `erasure_pending`（§3 规则 3，terminal）。擦除是否**已物理完成**由 erasure receipt（下文）独立表征，而非由 status 推进表达：审计 / UI MUST 通过是否存在有效 `ak.schema.erasure_receipt.v1`（及其 `outcome`）区分"擦除排队 / 进行中"与"擦除已结束",MUST NOT 从 `erasure_pending` 本身推断完成与否。

擦除完成后，服务端 SHOULD 发布 signed erasure receipt；若服务声明支持 hard erasure conformance，则 MUST 使用 `ak.schema.erasure_receipt.v1` payload，并可通过 `ak.audit.erasure_receipt` durable audit Event 发布。Receipt 至少绑定 `subject`、`scope.storage_boundary`、`outcome`、`erased_classes[]`、`retained_stub_digest`、`legal_hold_ref?`、`completed_at`、`issuer` 与 `proofs[]`。`proofs[]` MUST 至少包含 1 条，且其中至少一条由 `issuer` 当前有效的 verification method 签名；空 `proofs[]` MUST 触发下文 fail-closed 校验（等同 `proofs[]` 校验失败）。`retained_stub_digest` MUST 等于 `hash(canonical_json(retained_stub))`；stub 可内联在 receipt，也可通过 erasure receipt endpoint 获取，但两者 canonical bytes 必须一致。Stub 只保留验证 event graph、signature event_digest、seal inclusion、redaction authorization 与 receipt linkage 所需的最小字段，MUST NOT 保留已擦除明文或裸明文 digest。Receipt 只证明 issuer 在声明的存储边界内完成、部分完成或因 legal hold 阻止删除，不证明独立第三方副本已经消失。

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

- **Provisioning** 由 controller 通过 `ak.self.agent.command.provision` operation 发起：先分配 Agent DID / Agent PCR binding，并在 controller PCR 仅写入 `ak.identity.accountability_grant` 与 selector claim；必填且 immutable 的 `requested_scope` 只建立 Agent key/session 的全局硬上限，不是 Realm 授权，provisioning 不得据此创建任何 `ak.capability.grant`。后续 Agent key scope、Realm-scoped grant、participation selection 与 session request 可以更窄，但 actions/resources 必须被 provision ceiling 覆盖且全局 mandatory constraints 不得删除或放宽，并继续受 Realm membership / policy 收窄；这里未允许的权限以后不得补回。raw response 的 `pcr_recovery.status=pending`。controller E2EE client 随后本地生成 Agent PCR MLS state，提交 Agent PCR genesis / Actor Profile，并上传 [`key-management.md` §7.5.6](./key-management.md) controller-owned recovery backup；该状态变为 `ready` 前不得完成首次 pairing。Agent provisioning status 投影闭合枚举:`pending_runtime_key` → `active`(pairing 完成) / `pairing_expired`(pairing 窗口过期) → `paused` / `deactivated`。
- **Pause**(`ak.self.agent.command.pause`):保留 agent identity、`accountability_grant`、`agent_key_authorize`、capability grants 的 durable state。Pause Event 是写入 `ak.component.agent.status.v1` 的 Control Move，authoring basis 只由 Event Envelope 顶层 `seal_basis` 表达；payload 不得携带第二套 producer 自报 frontier。Auth Server MUST 拒绝新 agent session grant；已签发 session token MUST 在独立于 session TTL、且 MUST ≤ 60 秒的 pause revocation freshness window（见 [`key-management.md` §3.6.1](./key-management.md)）内通过 introspection、status check、revocation list 或等价机制 fail closed。实现 MAY 选择同步 revocation 或每次资源访问强制 status 重查，但 MUST NOT 把该窗口放宽到 session 最大 TTL，也 MUST NOT 仅依赖自然过期继续接受 paused agent token。Pending action requests SHOULD 标 `awaiting_resume`。
- **Resume**(`ak.self.agent.command.resume`):Event 同样以顶层 `seal_basis` 作为 authoring basis；receiver MUST 在接受时读取 accepted current control frontier，重新校验 controller、agent、key、capability、Realm policy 与 `accountability_grant` freshness。Payload 不是 reducer receipt，不得声称包含“接收时捕获”的 frontier；任一重校验不通过则拒绝 resume，agent 保持 `paused`。
- **Deactivate**(`ak.self.agent.command.deactivate`):terminal state,fan-out `ak.agent.key.revoke`、`ak.capability.revoke` / delegation revoke、runtime endpoint revoke、pending action request 失效，并使该 agent 全部 open pairing handle 永久不可解析。该 Agent MUST 立即离开所有相关 Sidecar desired access，停止投递，并对每个 backing scope 执行 membership remove、MLS remove 与 epoch rotation（见 [`../models/sidecar.md` §4](../models/sidecar.md)）。若 controller `mls_history` active series 含该 Agent PCR managed item，还 MUST 按 [`key-management.md` §7.5.6 / §9.1](./key-management.md) 开新 series 排除该 binding、确认可恢复后再按 retention 删除旧 series；这不声称撤回已合法下载的历史 plaintext。
- **Controller lifecycle 传播**:Controller 进入 `deactivated` / `suspended` 时，其 accountable native agents 的 active sessions MUST 通过本节 revocation 链失效，后续 agent session grant MUST fail closed。Accountability grant 失效同样使 agent 进入 ineligible 状态。
- **Controller Realm membership 传播**：Native Personal Agent 不能作为无主成员留在 Collaboration Realm。controller 在某 Realm 的 `ak.member.state` 从 `join` 转为 `leave` / `ban` 时，该 Realm 中所有仍为 `join` 且经 active accountability / provisioning 证明归属于该 controller 的 Native Personal Agents MUST 强制级联为 `leave`，并触发 Circle、delivery route 与 MLS Remove；不得因 agent runtime 不在线、未响应或未同意而延迟。controller 重新加入不自动恢复这些 agent membership。
- **Pairing expiry**:仅适用于从未完成首次 key 授权的 agent:`pairing.expires_at` 到达且未完成 pairing 时，agent status 转 `pairing_expired`，但不得因此创建、撤销或改写任何 Realm grant；controller 可重新发起 pairing 或显式 revoke 进入 `deactivated`。
- **Runtime replacement re-pairing**:controller MUST 先把 `active` agent pause，再对 `paused` agent 经 `ak.self.agent.command.renew_pairing` 重开 pairing(runtime 迁移、key 丢失恢复、例行换钥)。重开 pairing 不是状态迁移:agent 保持 paused，既有 key 与 grant 在新配对完成前保持不变；新配对完成时全部旧 key 以 reason=`superseded_by_repairing` 原子撤销，且仍须显式 resume；handle 过期无副作用。详见 [`key-management.md` §3.6.1](./key-management.md)。

**合法迁移表（normative）**：上述闭合枚举的合法 (from → to) 转换如下；表中未列出的转换 MUST 拒绝（`failed_precondition`，非法 agent provisioning 转换）。`deactivated` 是 terminal 状态（无出边）。`pairing_expired` 只描述从未完成首次配对的 agent；仅 `paused` 可带 open replacement handle，该 handle 是属性而非状态。

| from \ to | `pending_runtime_key` | `active` | `pairing_expired` | `paused` | `deactivated` |
| --- | --- | --- | --- | --- | --- |
| `pending_runtime_key` | — | ✓（pairing 完成） | ✓（pairing 窗口过期） | ✗ | ✓（显式 deactivate） |
| `active` | ✗ | — | ✗ | ✓（pause） | ✓（deactivate） |
| `pairing_expired` | ✓（重新发起 pairing） | ✗ | — | ✗ | ✓（显式 revoke） |
| `paused` | ✗ | ✓（resume，须重校验，见上） | ✗ | — | ✓（deactivate） |
| `deactivated` | ✗ | ✗ | ✗ | ✗ | —（terminal） |

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
