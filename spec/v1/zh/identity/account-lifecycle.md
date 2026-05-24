---
title: Account Lifecycle
---

## 1. 目标

Contrix 身份由 DID principal 表示，但用户访问通常经过一个或多个服务账户、OAuth/OIDC session、device token 和 Principal Server / Events API。本文件定义这些层的锁定、暂停、注销、软登出、数据擦除和服务账号生命周期。

## 2. 分层

| 层 | 示例 | 生命周期控制者 |
| --- | --- | --- |
| DID principal | `did:webvh:...` | DID controller / recovery policy |
| Service account | `alice@example.com` 登录入口 | account service |
| Device session | access token / refresh token | auth service |
| Event / private state | signed Event history / private account data | Events API + principal policy |
| Realm membership | `cx.member.state` | Realm policy/capability |

服务 account 被注销不等于 DID 消失。DID 被恢复或轮换不等于所有服务 session 继续有效。

## 2.1 服务账号登录与找回

服务账号 MAY 使用用户名/密码、passkey、WebAuthn、OAuth/OIDC、企业 SSO 或类似集中认证服务的登录方式。它们只证明调用方通过了某个 account service 的认证，不能直接证明 DID principal 所有权。

登录成功后，account service / auth service MUST 将会话绑定到 DID principal 与设备，例如签发短期 `cx.session.grant`、登记 device binding，或要求客户端提交 DID proof。资源服务器随后验证 grant、device、capability、Realm policy 和撤销状态。

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

| 状态 | 触发方 | Access token | Refresh token | Device trust | E2EE secret storage | Event history | 详细规则 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `active` | — | 有效 | 有效 | 保留 | 保留 | 保留 | — |
| `soft_logged_out` | auth service / 用户 logout | 已撤销 | 可在 fresh DID/device proof 下 refresh | 保留 | 保留 | 保留 | §4 |
| `locked` | 安全风险检测 | 已撤销 | SHOULD 撤销 | 保留 | 保留 | 保留 | §5 |
| `suspended` | 治理 / 合规 | 拒新发 | 拒新发 | 保留 | 保留 | 保留 | §6 |
| `deactivated` | 用户 / 管理员关账 | 已撤销 | 已撤销 | 标记 revoked | 客户端可清除 | 保留 | §7 |
| `erasure_pending` | 用户擦除请求 / GDPR | 已撤销 | 已撤销 | 已撤销 | 必删 | 按 redaction policy 最小化 | §8 |

`reason_code` 表达**为什么**进入该状态（如 `abuse_review` / `gdpr_request` / `password_compromise`）；状态本身表达**当前所处阶段的协议行为契约**。两者不可替代。

状态发布为服务侧 signed account status：

```json
{
  "kind": "cx.account.status",
  "account_id": "acct_...",
  "principal_id": "did:webvh:...",
  "status": "suspended",
  "reason_code": "abuse_review",
  "effective_at": "2026-04-26T00:00:00Z",
  "appeal_uri": "https://example.com/appeal/acct_...",
  "signature": {"kid": "did:web:auth.example#key-1", "sig": "..."}
}
```

Current account status projection 是 ordered_log 上的确定性派生值，而不是简单取本地最后到达的 event。若同一 `principal_id` 出现并发 `cx.account.status` head，client / server MUST 按以下规则选择当前状态：

1. 严格度高者优先：`erasure_pending` > `deactivated` > `suspended` > `locked` > `soft_logged_out` > `active`。
2. 降低严格度的状态（例如 appeal 后回到 `active`）MUST 在 payload 中引用被解除的 status event id（`supersedes_status_event_id` 或等价审计字段），且该引用必须在当前 Anchor view 可见；否则它只是并发候选，不能覆盖更严格状态。
3. 同严格度并发时，以 `(effective_at, event_id)` 的 canonical order 取最大值作为 projection current，其他 head 仍保留在 ordered_log conflict/audit view 中。

## 4. Soft Logout

`soft_logged_out` 表示 access token 不再可用，但本地加密数据和 device trust 可保留。客户端 SHOULD：

- 停止 sync。
- 清除 access token。
- 保留 device keys 和 secret storage 本地密钥，除非用户选择清除。
- 使用 refresh、OIDC 或 re-auth 恢复，但恢复请求仍必须携带 fresh DID/device proof。

服务端返回 `401 soft_logged_out` 时 MUST 不要求客户端删除本地 E2EE 密钥。

`soft_logged_out -> active` 的恢复 MUST 绑定 fresh DID proof：refresh token、OIDC callback 或 re-auth 只能作为会话恢复材料，不能单独把账号状态恢复为 `active`。服务端 MUST 要求当前 principal DID 的授权 device key、account auth key、passkey 或 recovery policy 允许的密钥对一次性 challenge 签名，并把签名覆盖 `principal_id`、`device_id?`、`audience`、`request_canonical_hash`、`challenge` 与 `expires_at?`。缺失该证明时返回 `401 did_proof_required`；refresh token 单独有效时也不得静默签发新的 active session grant。

## 5. Locked

`locked` 表示安全风险临时锁定。服务端 MUST：

- 拒绝新 access token。
- 可允许 recovery / appeal / export。
- 可撤销 refresh token。
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

- 撤销 access/refresh token。
- 停止 push。
- 停用 applet delegated device。
- 标记 device 为 revoked。
- 保留 signed event 历史，除非另有 erasure policy。

客户端 SHOULD 提供本地密钥清除选项。Deactivation 不应伪造 redaction；历史事件如需隐藏，必须提交真实 `cx.redaction` 或遵循 retention policy。

### 7.1 Deactivation Fanout（normative）

为关闭"deactivation 后仍有未撤销路径继续投递或被授权"的窗口，**deactivation accepted 进入 frontier 的同一事务边界内** MUST 触发下列 fanout：

| 域 | Fanout 动作 | 触发什么 event |
| --- | --- | --- |
| **Session / access token** | 撤销全部 `cx.session.grant`（含 applet delegated session）；后续 token introspection MUST 返回 `inactive`。 | 服务端撤销表 + 可选 `cx.audit.accessed` |
| **Device grant** | 全部 `cx.device.*` 标 `revoked`；后续 `cx.events.submit` 用 revoked device 签名 MUST `actor_signature_revoked`。 | reducer 状态转换 |
| **Applet delegation** | 撤销所有 `cx.applet.registration` 持有的 delegated device；applet 服务后续调用 MUST `delegation_revoked`。 | reducer 状态转换 |
| **Key package** | 标记所有 unused MLS KeyPackage 为 retired；新邀请 MUST 不从该 principal 选 KeyPackage。 | reducer + key package store 失效 |
| **Push route** | 撤销 `cx.device.push_route`；push gateway MUST 停止向该 principal 的注册 endpoint 投递。 | reducer + push gateway 缓存失效 |
| **To-device queue** | 服务端 to-device 队列 drop 所有 `recipient_principal_id == deactivated_principal` 的 pending message；后续投递 MUST `recipient_unavailable`。 | server-side queue 状态 |
| **Identity link cache** | 客户端与服务端可见缓存 MUST eager invalidate 所有 `(*, pairwise_did → deactivated_principal)` 映射；不得等待 7d TTL 或 MLS epoch 推进。 | `cx.identity_link` cache invalidation |
| **Capability cache** | 所有 cached `cx.capability.grant` decision 引用该 principal 作为 subject 或 issuer 的 MUST eager invalidate；下次 capability check 走完整判定。 | cache invalidation |

**写屏障（write barrier）**：`deactivated` accepted 进入当前 account status frontier 后，任何以该 principal 为 actor、subject、issuer、recipient 或 device owner 的新 `cx.session.grant`、`cx.device.authorize`、KeyPackage publish / claim、agent / applet delegation、capability grant / delegation、push route、to-device enqueue 和 Realm membership delivery-binding 写入 MUST `failed_precondition`，`reason="principal_deactivated"`。该屏障按 account status frontier 生效，不得被较新的 HLC、不同 device、未完成 federation ack 或尚未失效的本地 cache 绕过。已经在屏障前 accepted 的历史 Event 不被改写；尚处 pending / quarantine / soft-fail 的写入 MUST 在恢复前重新检查该屏障。

约束：

- **不自动 ban**：deactivation 不等于 Realm 内 `cx.member.state` 转 `ban`/`leave`。哪些 Realm membership 自动 `cx.member.state = leave`（自愿停用）vs. 保留 `join`（policy 决定）由 Realm policy 的 `account_deactivation.member_action` 字段控制（默认 `leave_self_initiated`）。
- **本地投递必停**：无论 policy 是否 ban，上表前 6 行（session/device/applet/KeyPackage/push/to-device queue）必停 — 否则会出现"账户已停用但其 device 还能签名 / push gateway 还在投递"的不可解释窗口。
- **MLS Remove**：若 Realm policy 决定 deactivate → leave，对应 MLS group MUST 在 grace window（默认 `mls_deactivation_grace_ms = 600,000 ms`）内 emit `cx.mls.commit` Remove；超时未 commit 则该 Realm 的成员客户端 MUST 在 verified timeline 中把该 principal 标 `unverifiable_member`，不再接受其新 epoch 消息。
- Fanout 失败的 partial state：如果某条 fanout 因网络 / 服务不可达失败，server `account_status` MUST 标 `deactivation_partial` 并继续重试；客户端 UI MUST 显式标记 "停用未完成" 而不是显示已停用。
- **跨 Principal Server 传播**：若该 principal 曾在其它 Principal Server 上持有 device / KeyPackage / to-device / push-route 状态，或通过 Realm membership delivery binding 使用过 peer 服务，源 Principal Server MUST 按 [`../sync/federation.md` §4.4.1](../sync/federation.md) 主动推送 `cx.account.status` deactivation。未在 `deactivation_propagation_window_ms` 内得到 peer ack 时，`account_status` MUST 标 `deactivation_federation_incomplete`，并暂停新 Realm onboard、新 session/device grant 与新 KeyPackage 发布。

## 8. Erasure

`erasure_pending` 表示物理删除流程开始。实现 MUST 区分：

- canonical event log：通常只能 redaction/minimization，不能破坏审计 hash 链。
- blob bytes：可按 retention/legal hold 删除。
- 本地/受托 projection：可删除或重新物化。
- account private state：可删除。
- policy/audit record：按合规周期保留最小字段。

擦除完成后，服务端 SHOULD 发布 signed erasure receipt；若服务声明支持 hard erasure conformance，则 MUST 使用 `cx.schema.erasure_receipt.v1` payload，并可通过 `cx.audit.erasure_receipt` durable audit Event 发布。Receipt 至少绑定 `subject`、`erasure_scope.storage_boundary`、`outcome`、`erased_classes[]`、`retained_stub_hash`、`legal_hold_ref?`、`completed_at`、`issuer` 与 `proofs[]`。`retained_stub_hash` MUST 等于 `hash(canonical_json(retained_stub))`；stub 可内联在 receipt，也可通过 erasure receipt endpoint 获取，但两者 canonical bytes 必须一致。Stub 只保留验证 event graph、signature event_digest、anchor inclusion、redaction authorization 与 receipt linkage 所需的最小字段，MUST NOT 保留已擦除明文或裸明文 digest。Receipt 只证明 issuer 在声明的存储边界内完成、部分完成或因 legal hold 阻止删除，不证明独立第三方副本已经消失。

## 9. Session Revocation

用户或服务可撤销：

- 单个 access token
- 单个 refresh token
- 单个 device
- 全部 session
- Applet delegated session

撤销 device MUST 产生 device list update。E2EE 客户端 MUST 停止向 revoked device 分享新密钥。

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
