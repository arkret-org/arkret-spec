# Account Lifecycle

## 1. 目标

Contrix 身份由 DID principal 表示，但用户访问通常经过一个或多个服务账户、OAuth/OIDC session、device token 和 repo 服务。本文件定义这些层的锁定、暂停、注销、软登出、数据擦除和服务账号生命周期。

## 2. 分层

| 层 | 示例 | 生命周期控制者 |
| --- | --- | --- |
| DID principal | `did:uuid:...` | DID controller / recovery policy |
| Service account | `alice@example.com` 登录入口 | account service |
| Device session | access token / refresh token | auth service |
| Repo data | principal repo / private state | repo service + principal policy |
| Space membership | `cx.member.state` | Space policy/capability |

服务 account 被注销不等于 DID 消失。DID 被恢复或轮换不等于所有服务 session 继续有效。

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

服务端返回 `M_SOFT_LOGOUT` 时 MUST 不要求客户端删除本地 E2EE 密钥。

## 5. Locked

`locked` 表示安全风险临时锁定。服务端 MUST：

- 拒绝新 access token。
- 可允许 recovery / appeal / export。
- 可撤销 refresh token。
- 不自动删除 repo 数据。

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
- index projection：可删除或重新物化。
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

