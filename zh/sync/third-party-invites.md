# Third-Party Invites Draft

## 1. 目标

去中心化协议通常假设所有的主键都是其原生的密码学标识符（如 DID）。然而，在现实协作中，用户经常需要邀请**尚未注册或不知道其 DID** 的外部人员（如通过电子邮件地址或手机号）。

本规范定义了如何通过**第三方标识符 (3PID - Third-Party Identifier)** 安全地将外部用户邀请到 Space，并在他们注册并创建 DID 后认领这些邀请。

## 2. 身份验证代理机制

由于外部的邮箱或手机号无法自己生成非对称密钥对和 DID，邀请流程 MUST 借助一个**身份验证服务 (Identity Verification Service)** 来充当代理。

这个代理服务通常是发起邀请的用户所在的 Homeserver 或组织控制的 Identity Node。

## 3. 邀请流程

### 3.1 创建待定邀请 (Pending Invite)

当 Alice 想通过电子邮件 `bob@example.com` 邀请 Bob 加入 Space 时：

1. **发起盲化邀请**：Alice 的客户端向她的 Sync Service 提交一个针对 3PID 的邀请。为了保护隐私，不应在公开的持久化 Repo 中直接写入明文邮箱。
2. **生成邀请令牌**：Alice 的身份验证服务生成一个随机的、高熵的 `Invite Token`。
3. **写入占位符 Op**：Alice 向 Space Repo 提交一个特殊的 `cx.invite.third_party` 操作：

```json
{
  "type": "cx.invite.third_party",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "display_name": "bob@example.com (Pending)",
  "token_hash": "sha256:d4e5f6g7h8i9...",
  "public_key": "z6Mkf..."
}
```

*注：`token_hash` 是邀请令牌的哈希。`public_key` 是身份验证服务生成的临时签名公钥，用于未来验证认领。*

### 3.2 发送外部通知

身份验证服务通过传统渠道（SMTP 邮件、SMS）将包含链接的邀请发送给该 3PID：
`https://app.contrix.example/invite?token=<Invite Token>&space=cx:space:...`

## 4. 认领流程 (Claiming)

当 Bob 收到邮件并点击链接，他在客户端完成了注册并获得了自己的 `did:web:bob.example.com`。接下来他需要认领这个邀请。

### 4.1 出示 Token 与绑定

Bob 的客户端将 `Invite Token` 和自己新生成的 DID 提交给 Alice 的身份验证服务。
身份验证服务验证 Token 无误后，使用之前预留的**临时私钥 (对应 3.1 节的 `public_key`)** 签署一个**绑定证明 (Binding Proof)**，声明：
“持有该 Token 的人现在对应的 DID 是 `did:web:bob.example.com`”。

### 4.2 提交转换 Op

身份验证服务（或 Bob 代理）将该证明连同 Bob 的签名，打包成一个 `cx.invite.claim` 操作提交到 Space Repo：

```json
{
  "type": "cx.invite.claim",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "subject_did": "did:web:bob.example.com",
  "token": "<Invite Token 原文>",
  "binding_signature": "<身份验证服务的签名>"
}
```

### 4.3 状态机转换

Space 中的其他节点（Sync Service / Index）在收到该 Op 时：
1. 计算 `token` 的哈希，必须匹配 `cx.invite.third_party` 中的 `token_hash`。
2. 验证 `binding_signature` 必须由对应的 `public_key` 签署。
3. 如果验证通过，该占位符邀请正式转变为针对 `did:web:bob.example.com` 的标准 `cx.invite.create`。
4. 随后 Bob 按照正常流程发送 `cx.invite.accept` 加入 Space。

## 5. E2EE 场景的兼容性

对于端到端加密的 Space，MLS (Message Layer Security) 组无法包含一个没有公钥的邮件地址。

因此，在 Pending Invite 阶段，Bob 是**不在** MLS 组中的，无法加密或解密任何内容。
只有当 Bob 认领了邀请（4.3 节）并获得了 DID 和相应的客户端初始化密钥包 (KeyPackage) 时，Alice 或群管理员才会向他发送 MLS `Welcome` 消息，将他正式引入加密组。

## 6. 后续待细化

- 邀请的过期时间与吊销 (Revocation)
- 为保护用户隐私的加盐哈希策略 (防止通过爆破字典反查 `token_hash` 获取邮箱)
