# Third-Party Invites

## 1. 目标

去中心化协议通常假设所有的主键都是其原生的密码学标识符（如 DID）。然而，在现实协作中，用户经常需要邀请**尚未注册或不知道其 DID** 的外部人员（如通过电子邮件地址或手机号）。

本规范定义了如何通过**第三方标识符 (3PID - Third-Party Identifier)** 安全地将外部用户邀请到 Space，并在他们注册并创建 DID 后认领这些邀请。

## 2. 身份验证代理机制

由于外部的邮箱或手机号无法自己生成非对称密钥对和 DID，邀请流程 MUST 借助一个**身份验证服务 (Identity Verification Service)** 来充当代理。

这个代理服务通常是发起邀请的用户所在的 Principal Server、组织控制的 Identity Verification Service，或 Space policy 明确允许的第三方验证服务。服务 DID、用途、过期时间和可见性 MUST 写入 invite metadata 或 Space policy。

## 3. 邀请流程

### 3.1 创建待定邀请 (Pending Invite)

当 Alice 想通过电子邮件 `bob@example.com` 邀请 Bob 加入 Space 时：

1. **发起盲化邀请**：Alice 的客户端向她的 Principal Server 或授权的 Identity Verification Service 提交一个针对 3PID 的邀请。公开持久化 Event 中 MUST NOT 写入明文邮箱、手机号或可枚举的未加盐哈希。
2. **生成邀请令牌**：验证服务生成至少 128 bit 熵的随机 `invite_token`，并生成独立 `token_salt`。`invite_token` MUST 只通过外部通知渠道发送给被邀请人，不得写入公开 Event。
3. **写入占位符 Event**：Alice 向 Space 提交一个特殊的 `cx.invite.third_party` Event：

```json
{
  "kind": "cx.invite.third_party",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "display_name_hint": "external invite",
  "token_commitment": "sha256:<hash(token_salt || invite_token)>",
  "token_salt_id": "salt:2026-04-28:invite-001",
  "verification_service_did": "did:web:identity.alice.example",
  "verification_public_key": "z6Mkf...",
  "expires_at": "2026-05-05T00:00:00Z",
  "max_claims": 1
}
```

`token_commitment` 是盐化承诺；`token_salt` 原值只保存在验证服务的私有状态或加密审计记录中。`verification_public_key` 是验证服务生成的临时签名公钥，用于未来验证认领。若需要在 UI 显示目标邮箱，应只在邀请者本地私有状态中保存，或以 E2EE 方式保存给有权查看邀请详情的管理员。

### 3.2 发送外部通知

身份验证服务通过传统渠道（SMTP 邮件、SMS）将包含链接的邀请发送给该 3PID：
`https://app.contrix.example/invite?token=<invite_token>&space=cx:space:...`

外部通知 MUST 避免在 URL query 中携带长期有效 token。推荐使用短期 one-time link、fragment token、或先打开应用再通过 out-of-band code 录入。邮件/SMS 内容不得包含 Space 私密名称、成员列表、历史摘要或其他未授权预览。

## 4. 认领流程 (Claiming)

当 Bob 收到邮件并点击链接，他在客户端完成了注册并获得了自己的 `did:web:bob.example.com`。接下来他需要认领这个邀请。

### 4.1 出示 Token 与绑定

Bob 的客户端将 `invite_token`、自己的 DID、设备证明和 intended Space 提交给 Alice 的身份验证服务。
身份验证服务验证 token、过期时间、claim 次数和 Space 绑定无误后，原子消费该 token，并使用之前预留的**临时私钥 (对应 3.1 节的 `verification_public_key`)** 签署一个**绑定证明 (Binding Proof)**，声明：
“持有该 Token 的人现在对应的 DID 是 `did:web:bob.example.com`”。

### 4.2 提交转换 Event

身份验证服务（或 Bob 代理）将该证明连同 Bob 的签名，打包成一个 `cx.invite.claim` Event 提交到 Space：

```json
{
  "kind": "cx.invite.claim",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "subject_did": "did:web:bob.example.com",
  "token_commitment": "sha256:<hash(token_salt || invite_token)>",
  "claim_nonce": "01JX...",
  "binding_proof": {
    "verification_service_did": "did:web:identity.alice.example",
    "verification_method": "did:web:identity.alice.example#invite-001",
    "subject_did": "did:web:bob.example.com",
    "space_id": "cx:space:01js0sp0000000000000000000",
    "audience": "contrix.invite.claim",
    "expires_at": "2026-05-05T00:00:00Z",
    "signature": "<身份验证服务的签名>"
  },
  "subject_proof": "<Bob DID/device 对 claim 的签名>"
}
```

### 4.3 状态机转换

Space 中的其他节点（Sync Service / 客户端本地 projection）在收到该 Event 时：
1. 匹配 `token_commitment` 与未过期、未撤销、未认领的 `cx.invite.third_party`。
2. 验证 `binding_proof` 必须由对应的 `verification_public_key` 签署，并绑定 `subject_did`、`space_id`、audience、过期时间和 claim nonce。
3. 验证 `subject_proof` 来自 Bob DID 的当前有效 verification method，防止验证服务把 token 绑定到攻击者 DID。
4. 原子标记 pending invite 为 `claimed`；同一个 `token_commitment` 的第二次认领 MUST reject。
5. 如果验证通过，该占位符邀请正式转变为针对 `did:web:bob.example.com` 的标准 `cx.invite.create` 或等价 membership proposal。
6. 随后 Bob 按照正常流程发送 `cx.invite.accept` 加入 Space。

## 5. E2EE 场景处理

对于端到端加密的 Space，MLS (Message Layer Security) 组无法包含一个没有公钥的邮件地址。

因此，在 Pending Invite 阶段，Bob 是**不在** MLS 组中的，无法加密或解密任何内容。
只有当 Bob 认领了邀请（4.3 节）并获得了 DID 和相应的客户端初始化密钥包 (KeyPackage) 时，Alice 或群管理员才会向他发送 MLS `Welcome` 消息，将他正式引入加密组。

## 6. 过期、撤销与隐私要求

- 所有可被认领或接受的 invite MUST 携带 `expires_at`；`cx.invite.third_party` 的默认过期时间 SHOULD 不超过 7 天，高安全 Space SHOULD 不超过 24 小时。
- 邀请者、Space 管理员或 policy server MAY 发布 `cx.invite.revoke` 撤销 pending invite。撤销后任何 claim MUST reject。
- 验证服务 MUST 对 token claim 做限速、IP / device 风险控制和重放检测；失败响应不得泄露 token 是否存在、Space 是否存在或 3PID 是否被邀请。
- Event 中不得出现明文 3PID、未加盐 3PID hash、token 原文、短信验证码或邮件验证码。需要审计时只能保存加密审计记录、salt id、token commitment、发送时间和服务签名。
- `token_salt` MUST 按邀请或批次高熵生成，不能使用全局常量 salt。低熵 3PID 的承诺必须加入服务私有 pepper 或改用不公开的 lookup table，防止离线字典爆破。
- claim 成功后，外部 3PID 与 `subject_did` 的绑定默认只在邀请上下文内有效；不得自动发布为全局 handle、联系人或组织成员资格。
