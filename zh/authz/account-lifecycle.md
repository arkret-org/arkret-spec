# Account Lifecycle

## 1. 目标

Contrix 身份由 DID principal 表示，但用户访问通常经过一个或多个服务账户、OAuth/OIDC session、device token 和 Principal Server / Events API。本文件定义这些层的锁定、暂停、注销、软登出、数据擦除和服务账号生命周期。

## 2. 分层

| 层 | 示例 | 生命周期控制者 |
| --- | --- | --- |
| DID principal | `did:uuid:...` | DID controller / recovery policy |
| Service account | `alice@example.com` 登录入口 | account service |
| Device session | access token / refresh token | auth service |
| Event / private state | signed Event history / private account data | Events API + principal policy |
| Space membership | `cx.member.state` | Space policy/capability |

服务 account 被注销不等于 DID 消失。DID 被恢复或轮换不等于所有服务 session 继续有效。

## 2.1 服务账号登录与找回

服务账号 MAY 使用用户名/密码、passkey、WebAuthn、OAuth/OIDC、企业 SSO 或类似集中认证服务的登录方式。它们只证明调用方通过了某个 account service 的认证，不能直接证明 DID principal 所有权。

登录成功后，account service / auth service MUST 将会话绑定到 DID principal 与设备，例如签发短期 `cx.session.grant`、登记 device binding，或要求客户端提交 DID proof。资源服务器随后验证 grant、device、capability、Space policy 和撤销状态。

### 2.1.1 Account-first onboarding

实现 MAY 提供 account-first 体验：用户先通过 `@alice:example.org`、邮箱、手机号、企业 SSO、OIDC 或邀请链接完成注册和登录，客户端不要求用户理解或手动输入 DID。

在这种模式下，account service / auth service MUST 在允许持久写入前完成以下动作之一：

- 绑定到用户已控制的 principal DID，并验证 DID proof、device binding 或等价 session grant。
- 为该服务账号创建受支持的托管 DID，并记录 controller、recovery policy、trust domain、service-account 绑定和审计证据。

未绑定 DID 的 session MAY 执行注册、风险检查、邀请预览、邮箱验证、设备初始化等 pre-registration 操作；MUST NOT 作为最终 actor 提交 Space Event、capability grant、MLS membership、service delegation 或 federation transaction。

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

## 3. Account States

服务账户状态：

- `active`
- `soft_logged_out`
- `locked`
- `suspended`
- `deactivated`
- `erasure_pending`

状态发布为服务侧 signed account status：

```json
{
  "type": "cx.account.status",
  "account_id": "acct_...",
  "principal_id": "did:uuid:...",
  "status": "suspended",
  "reason_code": "abuse_review",
  "effective_at": "2026-04-26T00:00:00Z",
  "appeal_uri": "https://example.com/appeal/acct_...",
  "signature": {"kid": "did:web:auth.example#key-1", "sig": "..."}
}
```

## 4. Soft Logout

`soft_logged_out` 表示 access token 不再可用，但本地加密数据和 device trust 可保留。客户端 SHOULD：

- 停止 sync。
- 清除 access token。
- 保留 device keys 和 secret storage 本地密钥，除非用户选择清除。
- 使用 refresh、OIDC 或 re-auth 恢复。

服务端返回 `401 soft_logged_out` 时 MUST 不要求客户端删除本地 E2EE 密钥。

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

Space 内 membership 不自动变成 ban；是否移除由 Space policy 决定。

## 7. Deactivated

`deactivated` 表示用户主动或管理员执行账户停用。服务端 MUST：

- 撤销 access/refresh token。
- 停止 push。
- 停用 applet delegated device。
- 标记 device 为 revoked。
- 保留 signed event 历史，除非另有 erasure policy。

客户端 SHOULD 提供本地密钥清除选项。Deactivation 不应伪造 redaction；历史事件如需隐藏，必须提交真实 `cx.redaction` 或遵循 retention policy。

## 8. Erasure

`erasure_pending` 表示物理删除流程开始。实现 MUST 区分：

- canonical event log：通常只能 redaction/minimization，不能破坏审计 hash 链。
- blob bytes：可按 retention/legal hold 删除。
- 本地/受托 projection：可删除或重新物化。
- account private state：可删除。
- policy/audit record：按合规周期保留最小字段。

擦除完成后，服务端 SHOULD 发布 signed erasure receipt。

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
