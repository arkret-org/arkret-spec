---
title: Account Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Cokret 身份由 DID principal 表示，但用户访问通常经过一个或多个服务账户、OAuth/OIDC session、device token 和 Principal Server / Events API。本文件定义这些层的锁定、暂停、注销、软登出、数据擦除和服务账号生命周期。

## 2. 分层

| 层 | 示例 | 生命周期控制者 |
| --- | --- | --- |
| DID principal | `did:webvh:...` | DID controller / recovery policy |
| Service account | `alice@example.com` 登录入口 | account service |
| Device session | session grant / holder key | auth service |
| Event / private state | signed Event history / private account data | Events API + principal policy |
| Realm membership | `ck.member.state`（状态机定义见 [`../models/realm-and-space.md`](../models/realm-and-space.md)） | Realm policy/capability |

服务 account 被注销不等于 DID 消失。DID 被恢复或轮换不等于所有服务 session 继续有效。

## 2.1 服务账号登录与找回

服务账号 MAY 使用用户名/密码、passkey、WebAuthn、OAuth/OIDC、企业 SSO 或类似集中认证服务的登录方式。它们只证明调用方通过了某个 account service 的认证，不能直接证明 DID principal 所有权。

登录成功后，account service / auth service MUST 将会话绑定到 DID principal 与设备，例如签发短期 `ck.session.grant`、登记 device binding，或要求客户端提交 DID proof。资源服务器随后验证 grant、device、capability、Realm policy 和撤销状态。

### 2.1.1 Account-first onboarding

实现 MAY 提供 account-first 体验：用户先通过 `@alice:example.org`、邮箱、手机号、企业 SSO、OIDC 或邀请链接完成注册和登录，客户端不要求用户理解或手动输入 DID。

在这种模式下，account service / auth service MUST 在允许持久写入前完成以下动作之一：

- 绑定到用户已控制的 principal DID，并验证 DID proof、device binding 或等价 session grant。
- 为该服务账号创建受支持的托管 DID，并记录 controller、recovery policy、trust domain、service-account 绑定和审计证据。

未绑定 DID 的 session MAY 执行注册、风险检查、邀请预览、邮箱验证、设备初始化等 pre-registration 操作；MUST NOT 作为最终 actor 提交 Realm Event、capability grant、MLS membership、service delegation 或 federation transaction。

如果用户后续改用自有 DID、pairwise DID 或组织私有 DID，服务 MAY 根据 policy 迁移 handle、service account binding、credential 或后续写入身份。历史 Event 的 `actor_id` 和 grant `subject` MUST NOT 被改写；需要表达迁移时，应发布显式 claim、attestation、profile update 或 account binding record。

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

| 状态 | 触发方 | Session grant | Holder proof refresh | Device trust | E2EE secret storage | Event history | 详细规则 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `active` | — | 有效 | 有效 | 保留 | 保留 | 保留 | — |
| `soft_logged_out` | auth service / 用户 logout | 已撤销 | 可在 fresh DID/device proof 下 refresh | 保留 | 保留 | 保留 | §4 |
| `locked` | 安全风险检测 | 已撤销 | SHOULD 拒绝 | 保留 | 保留 | 保留 | §5 |
| `suspended` | 治理 / 合规 | 拒新发 | 拒新发 | 保留 | 保留 | 保留 | §6 |
| `deactivated` | 用户 / 管理员关账 | 已撤销 | 已撤销 | 标记 revoked | 客户端可清除 | 保留 | §7 |
| `erasure_pending` | 用户擦除请求 / GDPR | 已撤销 | 已撤销 | 已撤销 | 必删 | 按 redaction policy 最小化 | §8 |

`reason_code` 表达**为什么**进入该状态（如 `abuse_review` / `gdpr_request` / `password_compromise`）；状态本身表达**当前所处阶段的协议行为契约**。两者不可替代。

**认证错误码（normative）**：Account status 导致 session grant 或 holder proof 失效时，服务端 MUST 返回与 current status 匹配的专用错误码，而不是退化成通用 `unauthenticated` / `capability_denied`。已签发 session 访问受保护 `/_cokret/self/*` 资源时：`soft_logged_out` 返回 `401 soft_logged_out`；`locked` 返回 `401 account_locked`；`deactivated` 返回 `401 account_deactivated`；`erasure_pending` 返回 `401 account_erased`。新 session grant 签发、session refresh 或登录完成阶段遇到当前 status 时：`locked` SHOULD 返回 `403 account_locked`；`suspended` MUST 返回 `403 account_suspended`；`deactivated` SHOULD 返回 `403 account_deactivated`；`erasure_pending` MUST 返回 `401 account_erased`。这些 code 的机器真源是 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)；HTTP status 的差异只表达“已持有 grant 失效”与“新 grant 被 policy 拒发”的入口差异，不改变 account status 语义。

**合法状态转换（normative）**：上面的 severity-order 仲裁解决"并发 head 选谁"，不替代"哪些 `from → to` 转换本身合法"的定义。`ck.account.status` reducer MUST 按下表判定单条状态转换是否合法；非法转换 MUST `failed_precondition`，`reason_code="account_status_transition_invalid"`：

| from \ to | `active` | `soft_logged_out` | `locked` | `suspended` | `deactivated` | `erasure_pending` |
| --- | --- | --- | --- | --- | --- | --- |
| `active` | —（同态重放） | ✓ | ✓ | ✓ | ✓ | ✓ |
| `soft_logged_out` | ✓（§4，须 fresh DID proof） | — | ✓ | ✓ | ✓ | ✓ |
| `locked` | ✓ | ✓ | — | ✓ | ✓ | ✓ |
| `suspended` | ✓（appeal 解除，须 `supersedes_status_event_id`） | ✓ | ✓ | — | ✓ | ✓ |
| `deactivated` | ✗（见下"重激活"） | ✗ | ✗ | ✗ | — | ✓ |
| `erasure_pending` | ✗ | ✗ | ✗ | ✗ | ✗ | —（terminal） |

- **降低严格度**（任一 `to` 严格度低于 `from`，如 `suspended → active`、`locked → soft_logged_out`）的转换 MUST 满足规则 2（引用 `supersedes_status_event_id` 且在当前 Seal view 可见），否则按并发候选处理，不构成有效转换。
- **`erasure_pending` 为 terminal**（规则 3）：其唯一出边为空，任何转出 MUST 拒绝 `erasure_pending_is_terminal`。
- **`deactivated` 重激活**（normative）：v1 **不**允许 `deactivated → active` 等任意降严格度转换。§7.1 的 deactivation fanout（device `revoked`、KeyPackage `retired`、session/push/to-device 撤销）是不可逆操作，v1 不定义其逆操作语义；需要恢复访问的用户 MUST 走新的 onboarding（绑定到同一 principal DID 的新 session/device/KeyPackage），而非把既有 `deactivated` account status 翻回 `active`。`deactivated` 的唯一合法出边是 `erasure_pending`（继续到擦除）。实现 MUST NOT 接受声称把 `deactivated` 降级回较低严格度状态的 `ck.account.status` event（`account_status_transition_invalid`）。

状态发布为服务侧 signed account status：

```json
{
  "kind": "ck.account.status",
  "account_id": "acct_...",
  "principal_id": "did:webvh:...",
  "status": "suspended",
  "reason_code": "abuse_review",
  "effective_at": "2026-04-26T00:00:00Z",
  "appeal_uri": "https://example.com/appeal/acct_...",
  "signature": {"kid": "did:web:auth.example#key-1", "sig": "..."}
}
```

Current account status projection 是 ordered_log 上的确定性派生值，而不是简单取本地最后到达的 event。本节定义的 severity-order 仲裁是 cell family `ck.component.account.status.v1`（`ordered_log` lattice）之上的 canonical projection；本节即该投影函数的权威定义，实现 MUST 产出与本节规则一致的 current status。若同一 `principal_id` 出现并发 `ck.account.status` head，client / server MUST 按以下规则选择当前状态：

1. 严格度高者优先：`erasure_pending` > `deactivated` > `suspended` > `locked` > `soft_logged_out` > `active`。
2. 降低严格度的状态（例如 appeal 后回到 `active`）MUST 在 payload 的 `supersedes_status_event_id` 字段（见 [`event-payload.schema.json#/$defs/account_status_payload`](../../artifacts/schemas/event-payload.schema.json)）引用被解除的 status event id，且该引用必须在当前 Seal view 可见；否则它只是并发候选，不能覆盖更严格状态。
3. **`erasure_pending` 是 terminal 状态（normative，不可逆）**：一旦某 `principal_id` 的 account status projection 进入 `erasure_pending`，它 MUST NOT 被任何 `supersedes_status_event_id` 引用降级回 `deactivated` / `suspended` / `locked` / `soft_logged_out` / `active` 中的任意一个。任何声称把 `erasure_pending` superseded 为较低严格度状态的 `ck.account.status` event MUST 被 reducer / projection 拒绝（`erasure_pending_is_terminal`），并保持 `erasure_pending` 为 current。理由：擦除流程一旦开始即对 blob bytes、account private state、受托 projection 执行不可逆的物理删除/最小化，把状态"恢复"为 active 会产生一个数据已被销毁却显示为正常的不一致账号。需要在擦除真正执行前撤销的，应在进入 `erasure_pending` 之前用较低严格度状态处理；进入 `erasure_pending` 之后只能继续完成擦除并发布 erasure receipt（§8）。`erasure_pending` 之上没有更严格状态，故规则 2 的"降低严格度"路径对它不适用。
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

`soft_logged_out -> active` 的恢复 MUST 绑定 fresh DID proof：session grant refresh、OIDC callback 或 re-auth 只能作为会话恢复材料，不能单独把账号状态恢复为 `active`。服务端 MUST 要求当前 principal DID 的授权 device key、account auth key、passkey 或 recovery policy 允许的密钥对一次性 challenge 签名，并把签名覆盖 `principal_id`、`device_id`、`audience`、`request_canonical_digest`、`challenge`、`issued_at` 与 `expires_at`。**`device_id` 绑定要求**:multi-device principal（principal 控制 ≥1 个授权 device key）下 `device_id` **MUST** 必填并被签名覆盖，绑定到发起恢复请求的具体 device，使该 challenge-response proof 不能被同 principal 的其它设备复用完成会话恢复（满足"会话绑定到 DID 与 device"目标）；仅当 principal 在 control stream 中**无任何未撤销 device record**（即不持有任何当前有效的 device-bound key，例如纯 account-auth-key / passkey 恢复路径）时 `device_id` 方可省略。服务端 MUST 依据该 principal control stream 中 device record 的当前状态（存在 ≥1 条未撤销 device record 即豁免不成立）判定豁免，**MUST NOT** 仅凭本次 proof 的签名 key 类型判定——否则持有未撤销 device-bound key 的 multi-device principal 可用 passkey / account-auth-key 签 proof 伪造"无 device key"假象，从而绕过本节要关闭的同 principal 其它设备复用 proof 窗口。豁免不成立时 MUST NOT 接受缺 `device_id` 的 proof。其中 `issued_at` 与 `expires_at` 是 **必填**（不再是可选）：服务端 MUST 拒绝缺失任一字段、`expires_at` 已过当前时钟、`expires_at - issued_at > 300s`、`issued_at` 相对服务端时钟的偏移（双向）超出 skew 容忍（SHOULD ≤ 300s），或 `issued_at` 晚于服务端当前时钟加 skew 容忍（即 proof 自称在未来签发）的 proof。这把 soft-logout 重放窗口的上界固定为 ≤ 300s，与 [`identity-did.md` §5.1](./identity-did.md) `ck.did.proof` 的 replay window（`expires_at - issued_at ≤ 300s` + skew ≤ 300s）对齐——否则签发方可把 `expires_at` 任意拉远，使一份 soft-logout 恢复 proof 在无上界的时间内反复重放。缺失该证明时返回 `401 did_proof_required`；`expires_at` 缺失或新鲜度超限时返回 `401 did_proof_required`（reason `did_proof_replay_window_exceeded`）；holder proof 单独存在时也 MUST NOT 静默签发新的 active session grant。

### 4.1 显式登出（hard logout）与跨服务吊销编排

`soft_logged_out` 是当前 session grant 失效但凭证可恢复的软状态；用户主动「登出」是 **hard logout**——它 MUST 在所有持有该会话凭证的权威处终结会话，而非仅清本地。客户端可见的登出入口是 Principal describe 发布的 Account Authority；Account Authority 内部协调两个权威的状态:

- **Auth Server(认证服务)**:`browser_session`(登录认证上下文)+ 它签发的 `ck.session.grant` 轮换链(及其 `cnf.jkt` 设备持有绑定，见 [`crypto-media/device-lifecycle.md` §3.2](../crypto-media/device-lifecycle.md))。
- **Principal Server(资源服务)**:本地 account session 记录、设备会话记录、对该 grant 的 session-grant 内省缓存(TTL ≤120s)、待投递 to-device 队列。客户端可见登录凭据仍是 `ck.session.grant`，客户端以 `Bearer <ck.session.grant>` + `DPoP` 直接访问 `/_cokret/self/*`(见 [`../sync/api-conventions.md` §3.3](../sync/api-conventions.md));Principal Server **不**为客户端铸独立本地 bearer，**不**暴露第二个客户端可见的 Principal 本地凭据签发 endpoint。

**编排(normative)**:hard logout 由 Account Authority 编排。客户端 MUST 从 `ServiceDescribe.auth_metadata.account_authority.gate_account_base` 派生并调用:

```text
POST /_cokret/gate/account/logout
```

该请求 MUST 使用 `Authorization: Bearer <ck.session.grant>` 出示当前 grant，并带 `DPoP` holder proof；DPoP `ath` MUST 绑定该 grant，`htu` MUST 绑定由 `gate_account_base` 派生出的 `/logout` URL，使 Account Authority 能定位要终结的 grant chain 与 principal device session。客户端 MUST NOT 分别向 Auth Server 与 Principal Server 两个 origin 发起登出；部署内部的分权威调用是 Account Authority 的实现细节。普通客户端可见的 logout endpoint **只有** `POST /_cokret/gate/account/logout`。

1. **客户端** MUST：停止 sync、清除本地 session credential / `session_grant` / OIDC 凭证；hard logout SHOULD 额外清除本设备的 holder(DPoP)私钥，使下次登录轮换 `cnf.jkt`(软恢复路径 MUST 保留该 key 以便 refresh)。
2. **Account Authority → Auth-side** MUST 登出当前 grant 所属的 Auth-side session / `browser_session` 并终结其 `ck.session.grant` 轮换链。若 Auth-side 不在同进程，Account Authority MUST 调用标准 S2S 子操作 `POST /_cokret/gate/account/auth-sessions/logout`(`ck.gate.account.command.logout_auth_session`)；该调用 MUST 使用 Account Authority → Auth Server 的部署内 S2S bearer（同 `session_grant_introspection_bearer` 认证族），MUST NOT 复用客户端为高层 `/logout` URL 铸造的 DPoP proof。此后 (i) 凭同一 `cnf.jkt` 设备 holder proof 调 `refresh` MUST 被拒(`session_logged_out`)，整条轮换链不可再续；(ii) 该 Auth-side session 下任何 grant 的 introspection MUST 返回 inactive(即设备密钥不能在登出后重建或维持会话)。
3. **Account Authority → Principal-side** MUST：作废该 grant 的本地 session-grant 内省缓存（下次内省即得 `active=false`）、吊销 / 标记该 principal 本地 account session 与**本地设备会话记录**(使后续以该设备签名的 device-scoped 操作在本 Principal Server fail closed)+ drop 该设备的待投递 to-device 消息，并移除该设备作用域内的 push registration。因 Principal Server 不为客户端铸独立本地 bearer（会话凭据即 grant 本身，见上），此处无单独的本地 bearer 可撤——作废内省缓存 + 撤设备会话记录即足以使该设备后续 `/_cokret/self/*` 请求 fail closed。此操作终结该设备在本 Principal Server 的本地会话状态，但 **不** 改写 `ck.account.status`、不发 `ck.device.revoke` 协议事件、不擦除 durable device authorization 历史(用户重新登录即可在本设备恢复)。注意它与 `ck.gate.account.command.revoke_session`(仅撤 session grant、不触设备会话记录，用于"撤某个会话但保留设备")是不同操作。

`POST /_cokret/gate/account/auth-sessions/logout` 是部署内部 S2S 子操作，不是客户端 account flow。该子操作 MUST 幂等：同一 Auth-side session / grant 已登出、已吊销、未知或已被剪枝时，Auth Server 仍 MUST 返回成功并把链视为已终结；鉴权失败、请求体不合法、或 Auth Server 无法确认完成时才返回错误。普通客户端、yougen、浏览器 UI 与移动客户端 **MUST NOT** 调用或自行派生该路径；即使高层 `/logout` 失败，客户端也只能重试 `ck.gate.account.command.logout`。客户端和服务实现 **MUST NOT** 依赖任何实现私有 / 产品私有(例如 `/_<impl>/*`)路由完成登出。

**登出耐久性(normative)**：hard logout 的本地清除(步骤 1)与 Account Authority 服务端编排(步骤 2、3)不是原子的——客户端在清本地凭证后、Account Authority 返回前可能崩溃、关页或离线。为防止「本地已登出但服务端轮换链仍存活」的窗口，客户端 **SHOULD** 在执行本地清除**之前**把登出意图(至少：Account Authority `/logout` endpoint、grant JWT、用于铸 holder proof 的设备 holder key)持久化(journal)，并在调用失败时重试(含下次启动重放)，直至 Account Authority 确认 grant 链终结后方清除该 journal。其中 Auth-side grant + `browser_session` 终结是耐久性关键步：它一旦完成，轮换链不可再续，后续无法恢复本地 account session。由于 `ck.session.grant` 有受限 TTL(见 [`crypto-media/device-lifecycle.md` §3.3](../crypto-media/device-lifecycle.md))，客户端 **MAY** 在该 TTL(加时钟 skew 容忍)过后停止重试：此时整条链已因自然过期失效，journal 中已无可吊销之物。重试 **MUST** 幂等——对已吊销/已过期 grant 再次调 hard logout 不应被视为错误。

**执行顺序与失败语义(normative)**：Auth-side session logout / grant-chain 终结是耐久性关键步，Account Authority SHOULD 先完成步骤 2，再完成 Principal-side 本地清理。若步骤 2 失败且没有可证明的 durable completion，Account Authority MUST NOT 向客户端返回 `ok=true`；应返回可重试错误（例如 `temporarily_unavailable`）。若步骤 2 已成功而步骤 3 暂时失败，Account Authority MAY 返回成功前把 Principal-side 清理持久化到 durable retry 队列；重复执行高层 `/logout` MUST 幂等。客户端在收到失败或网络中断时 MUST 只重试 `POST /_cokret/gate/account/logout`，MUST NOT 直接调用 `auth-sessions/logout`。

**吊销传播与生效语义(normative)**：Account Authority 内部可同步调用或异步重试 Principal-side 终结，但对客户端返回成功前 MUST 至少保证 Auth-side grant 轮换链已不可续。Principal Server 对本地 session 的有效性以「本地 session 记录 + 对 Account Authority / Auth-side 的 session-grant 内省」为准；Auth-side grant/会话被吊销后，Principal Server MUST 在下一次内省时得到 `active=false` 并 fail closed。实现 MAY 缓存内省结果，但缓存 TTL 与本地 session TTL 共同构成吊销生效的上界，二者 SHOULD ≤ 数分钟；高安全 profile SHOULD 更短或对敏感操作旁路缓存。Auth Server / Principal Server MUST NOT 依赖对方主动 push 吊销；Account Authority 是客户端可见的编排边界。

**轮换链单次使用与重用即妥协(normative)**:`ck.session.grant` 轮换 MUST 单次使用——轮换成功即吊销旧 grant；对**已消费**的 grant 再次发起轮换 MUST 拒(`grant_already_consumed`)，且 SHOULD 视为凭证泄露信号并吊销整条轮换链(并入上面的会话终结)。

**与 soft logout 的区别**:soft logout 可凭 fresh DID/device proof(§4)恢复；hard logout 终结 grant 链 + `browser_session`，恢复 MUST 重新走完整认证(新 `browser_session`)，设备密钥本身不足以重建会话。

## 5. Locked

`locked` 表示安全风险临时锁定。服务端 MUST：

- 拒绝新 session grant。
- 可允许 recovery / appeal / export。
- SHOULD 拒绝 holder proof refresh（与 §3 正交性矩阵 `locked` 行一致）。
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

客户端 SHOULD 提供本地密钥清除选项。Deactivation MUST NOT 伪造 redaction；历史事件如需隐藏，必须提交真实 `ck.redaction` 或遵循 retention policy。

### 7.1 Deactivation Fanout（normative）

为关闭"deactivation 后仍有未撤销路径继续投递或被授权"的窗口，**deactivation accepted 进入 frontier 的同一事务边界内** MUST 触发下列 fanout：

| 域 | Fanout 动作 | 触发什么 event |
| --- | --- | --- |
| **Session grant** | 撤销全部 `ck.session.grant`（含 applet delegated session）；后续 session-grant introspection MUST 返回 `inactive`。 | 服务端撤销表 + 可选 `ck.audit.accessed` |
| **Device grant** | 全部 `ck.device.*` 标 `revoked`；后续 `ck.self.events.command.submit` 用 revoked device 签名 MUST `actor_signature_revoked`。 | reducer 状态转换 |
| **Applet delegation** | 撤销所有 `ck.applet.registration` 持有的 delegated device；applet 服务后续调用 MUST `delegation_revoked`。 | reducer 状态转换 |
| **KeyPackage** | 标记所有 unused MLS KeyPackage 为 retired；新邀请 MUST NOT 从该 principal 选 KeyPackage。 | reducer + KeyPackage store 失效 |
| **Push route** | 撤销 `ck.device.push_route`；push gateway MUST 停止向该 principal 的注册 endpoint 投递。 | reducer + push gateway 缓存失效 |
| **To-device queue** | 服务端 to-device 队列 drop 所有 `recipient_principal_id == deactivated_principal` 的 pending message；后续投递 MUST `recipient_unavailable`。 | server-side queue 状态 |
| **Identity link cache** | 客户端与服务端可见缓存 MUST eager invalidate 所有 `(*, pairwise_did → deactivated_principal)` 映射；不得等待 7d TTL 或 MLS epoch 推进。 | `ck.identity_link` cache invalidation |
| **Capability cache** | 所有 cached `ck.capability.grant` decision 引用该 principal 作为 subject 或 issuer 的 MUST eager invalidate；下次 capability check 走完整判定。 | cache invalidation |

**写屏障（write barrier）**：`deactivated` accepted 进入当前 account status frontier 后，任何以该 principal 为 actor、subject、issuer、recipient 或 device owner 的新 `ck.session.grant`、`ck.device.authorize`、KeyPackage publish / claim、agent / applet delegation、capability grant / delegation、push route、to-device enqueue 和 Realm membership delivery-binding 写入 MUST `failed_precondition`，`reason="principal_deactivated"`。该屏障按 account status frontier 生效，不得被较新的 HLC、不同 device、未完成 federation ack 或尚未失效的本地 cache 绕过。已经在屏障前 accepted 的历史 Event 不被改写；尚处 pending / quarantine / soft-fail 的写入 MUST 在恢复前重新检查该屏障。

约束：

- **不自动 ban**：deactivation 不等于 Realm 内 `ck.member.state` 转 `ban`/`leave`。哪些 Realm membership 自动 `ck.member.state = leave`（自愿停用）vs. 保留 `join`（policy 决定）由 Realm policy 的 `account_deactivation.member_action` 字段控制。该字段是封闭枚举，v1 取值域为：
  - `leave_self_initiated`（默认）：把该 principal 在本 Realm 的 membership 视为自愿退出，自动转 `ck.member.state = leave`。
  - `retain_membership`：保留 `join`，由 Realm policy 在后续显式处置（deactivation 本身不改 membership state）。
  - `leave_all`：无条件把该 principal 在本 Realm 的 membership 转 `leave`，等同 self-initiated 但不区分触发方语义。

  未识别的取值 MUST 按未知 policy 字段 fail closed（保守取 `retain_membership` 不主动改 membership，并标记 policy 解析告警），不得静默回退为默认值。注意本字段控制的是 membership state，与上表前 6 行无条件必停的本地投递撤销正交。
- **本地投递必停**：无论 policy 是否 ban，上表前 6 行（session/device/applet/KeyPackage/push/to-device queue）必停 — 否则会出现"账户已停用但其 device 还能签名 / push gateway 还在投递"的不可解释窗口。
- **MLS Remove**：若 Realm policy 决定 deactivate → leave，对应 MLS group MUST 在 grace window（默认 `mls_deactivation_grace_ms = 600,000 ms`）内 emit `ck.mls.commit` Remove；超时未 commit 则该 Realm 的成员客户端 MUST 在 verified timeline 中把该 principal 标 `unverifiable_member`，不再接受其新 epoch 消息。
- Fanout 失败的 partial state：如果某条 fanout 因网络 / 服务不可达失败，server `account_status` MUST 标 `deactivation_partial` 并继续重试；客户端 UI MUST 显式标记 "停用未完成" 而不是显示已停用。
- **跨 Principal Server 传播**：若该 principal 曾在其它 Principal Server 上持有 device / KeyPackage / to-device / push-route 状态，或通过 Realm membership delivery binding 使用过 peer 服务，源 Principal Server MUST 按 [`../sync/federation.md` §4.4.1](../sync/federation.md) 主动推送 `ck.account.status` deactivation。未在 `deactivation_propagation_window_ms` 内得到 peer ack 时，`account_status` MUST 标 `deactivation_federation_incomplete`，并暂停新 Realm onboard、新 session/device grant 与新 KeyPackage 发布。

## 8. Erasure

`erasure_pending` 表示物理删除流程开始。实现 MUST 区分：

- canonical event log：通常只能 redaction/minimization，不能破坏审计 hash 链。
- blob bytes：可按 retention/legal hold 删除。
- 本地/受托 projection：可删除或重新物化。
- account private state：可删除。
- policy/audit record：按合规周期保留最小字段。

**擦除完成态语义（normative）**：v1 **不**新增 `erased` / `tombstoned` 终态。`erasure_pending` 的 "pending" 表示"擦除已发起且不可逆"，**不**表示"擦除尚未完成"——擦除流程进入该状态后 account status projection 永久停在 `erasure_pending`（§3 规则 3，terminal）。擦除是否**已物理完成**由 erasure receipt（下文）独立表征，而非由 status 推进表达：审计 / UI MUST 通过是否存在有效 `ck.schema.erasure_receipt.v1`（及其 `outcome`）区分"擦除排队 / 进行中"与"擦除已结束",MUST NOT 从 `erasure_pending` 本身推断完成与否。

擦除完成后，服务端 SHOULD 发布 signed erasure receipt；若服务声明支持 hard erasure conformance，则 MUST 使用 `ck.schema.erasure_receipt.v1` payload，并可通过 `ck.audit.erasure_receipt` durable audit Event 发布。Receipt 至少绑定 `subject`、`scope.storage_boundary`、`outcome`、`erased_classes[]`、`retained_stub_digest`、`legal_hold_ref?`、`completed_at`、`issuer` 与 `proofs[]`。`proofs[]` MUST 至少包含 1 条，且其中至少一条由 `issuer` 当前有效的 verification method 签名；空 `proofs[]` MUST 触发下文 fail-closed 校验（等同 `proofs[]` 校验失败）。`retained_stub_digest` MUST 等于 `hash(canonical_json(retained_stub))`；stub 可内联在 receipt，也可通过 erasure receipt endpoint 获取，但两者 canonical bytes 必须一致。Stub 只保留验证 event graph、signature event_digest、seal inclusion、redaction authorization 与 receipt linkage 所需的最小字段，MUST NOT 保留已擦除明文或裸明文 digest。Receipt 只证明 issuer 在声明的存储边界内完成、部分完成或因 legal hold 阻止删除，不证明独立第三方副本已经消失。

**Fail-closed 校验（normative）**：verifier 在接受一份 `ck.schema.erasure_receipt.v1` 之前 MUST 重算 `hash(canonical_json(retained_stub))` 并与 receipt 的 `retained_stub_digest` 比对。当 stub（内联或经 endpoint 获取）与 `retained_stub_digest` **不一致** 时，verifier MUST 拒绝该 receipt（`erasure_receipt_stub_digest_mismatch`），并将该 erasure 视为 **未完成**（fail closed），不得据此把 subject 标记为已擦除、不得释放 legal hold、不得停止重试擦除流程。digest 不匹配意味着 stub 被替换、截断或与 receipt 不同源，无法证明声明的存储边界内删除已真正发生；默认结论是"擦除未完成"而非"擦除成功"。同理，receipt 缺失 `retained_stub_digest`、stub 无法获取，或 `proofs[]` 校验失败时，verifier MUST 同样 fail closed。

## 9. Session Revocation

用户或服务可撤销：

- 单个 session grant
- 单个 holder-bound session chain
- 单个 device
- 全部 session
- Applet delegated session

撤销 device MUST 产生 device list update。E2EE 客户端 MUST 停止向 revoked device 分享新密钥。

## 9.1 Personal agent principal lifecycle

Native personal agent(`actor_kind="agent"`,`accountable_principal_ids` 指向 controller principal)的 lifecycle 是 controller 账户 lifecycle 的从属体:

- **Provisioning** 由 controller 通过 `ck.self.agent.command.provision` operation 发起，fan-out 写入 Actor Profile、`ck.identity.accountability_grant`、初始 `ck.capability.grant`(带 `effective_after_first_authorized_key=true` flag)。Agent provisioning status 投影闭合枚举:`pending_runtime_key` → `active`(pairing 完成) / `pairing_expired`(pairing 窗口过期) → `paused` / `deactivated`。
- **Pause**(`ck.self.agent.command.pause`):保留 agent identity、`accountability_grant`、`agent_key_authorize`、capability grants 的 durable state。Auth Server MUST 拒绝新 agent session grant；已签发 session token SHOULD 在 revocation freshness window(≤ 该部署 agent session 最大 TTL，见 [`key-management.md` §3.6.1](./key-management.md))内 fail closed，实现可选同步 revocation 或自然过期 + status 重查。Pending action requests SHOULD 标 `awaiting_resume`。
- **Resume**(`ck.self.agent.command.resume`):前 MUST 重新校验 controller、agent、key、capability、Realm policy 与 `accountability_grant` freshness；任一不通过则拒绝 resume,agent 保持 `paused`。
- **Deactivate**(`ck.self.agent.command.deactivate`):terminal state,fan-out `ck.agent.key.revoke`、`ck.capability.revoke` / delegation revoke、runtime endpoint revoke、pending action request 失效。Sidecar Circle 同步移除该 agent；若该 Circle 为 MLS-backed，则执行 MLS remove 与 epoch rotation（见 [`../models/circle.md` §11.1](../models/circle.md)）。
- **Controller lifecycle 传播**:Controller 进入 `deactivated` / `suspended` 时，其 accountable native agents 的 active sessions MUST 通过本节 revocation 链失效，后续 agent session grant MUST fail closed。Accountability grant 失效同样使 agent 进入 ineligible 状态。
- **Pairing expiry**:`pairing.expires_at` 到达且未完成 pairing 时，服务 MUST 自动 `ck.capability.revoke` 撤销 pending grant,agent status 转 `pairing_expired`;controller 可重新发起 pairing 或显式 revoke 进入 `deactivated`。

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
