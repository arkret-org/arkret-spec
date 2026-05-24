---
title: Third-Party Invites
---

## 1. 目标

去中心化协议通常假设所有的主键都是其原生的密码学标识符（如 DID）。然而，在现实协作中，用户经常需要邀请**尚未注册或不知道其 DID** 的外部人员（如通过电子邮件地址或手机号）。

本规范定义了如何通过**第三方标识符 (3PID - Third-Party Identifier)** 安全地将外部用户邀请到 Realm，并在他们注册并创建 DID 后认领这些邀请。

## 2. 身份验证代理机制

由于外部的邮箱或手机号无法自己生成非对称密钥对和 DID，邀请流程 MUST 借助一个**身份验证服务 (Identity Verification Service)** 来充当代理。

这个代理服务通常是发起邀请的用户所在的 Principal Server、组织控制的 Identity Verification Service，或 Realm policy 明确允许的第三方验证服务。服务 DID、用途、过期时间和可见性 MUST 写入 invite metadata 或 Realm policy。

## 3. 邀请流程

### 3.1 创建待定邀请 (Pending Invite)

当 Alice 想通过电子邮件 `bob@example.com` 邀请 Bob 加入 Realm 时：

1. **发起盲化邀请**：Alice 的客户端向她的 Principal Server 或授权的 Identity Verification Service 提交一个针对 3PID 的邀请。公开持久化 Event 中 MUST NOT 写入明文邮箱、手机号或可枚举的未加盐哈希。
2. **生成邀请令牌**：验证服务生成至少 128 bit 熵的随机 `invite_token`，并生成独立 `token_salt`。`invite_token` MUST 只通过外部通知渠道发送给被邀请人，不得写入公开 Event。
3. **写入占位符 Event**：Alice 向 Realm 提交一个特殊的 `cx.invite.third_party` Event，其 `payload` 为：

```json schema=schemas/event-payload.schema.json#/$defs/invite_payload
{
  "invite": {
    "id": "cx:invite:0196419b-1000-7000-8000-000000000000",
    "schema": "cx.schema.invite.v1",
    "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
    "inviter": "did:web:alice.example",
    "third_party_id": {
      "display_name_hint": "external invite",
      "token_commitment": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "token_salt_id": "salt-2026-04-28-invite-001",
      "oob_code_kind": "offline_token",
      "token_entropy_bits": 128,
      "verification_service_did": "did:web:identity.alice.example",
      "verification_public_key": "did:web:identity.alice.example#invite-001",
      "max_claims": 1
    },
    "join_rule_snapshot": {
      "join_rule": "invite"
    },
    "expires_at": "2026-05-05T00:00:00Z",
    "state": "pending",
    "created_at": "2026-04-28T00:00:00Z"
  },
  "expires_at": "2026-05-05T00:00:00Z"
}
```

`token_commitment` 是盐化承诺；`token_salt` 原值只保存在验证服务的私有状态或加密审计记录中。`oob_code_kind` 是 wire-level discriminator：`offline_token` 表示 OOB code 自身满足 ≥128-bit 熵并按 commitment 校验；`lookup` 表示短码只作为服务端私有 lookup 表索引，必须走 pepper/HMAC 存储与限速。该结构的 object 形态由 [`invite.schema.json`](../../artifacts/schemas/invite.schema.json) 的 `third_party_id` 定义。`verification_public_key` 是验证服务生成的临时签名公钥，用于后续 claim / 认领验证。若需要在 UI 显示目标邮箱，应只在邀请者本地私有状态中保存，或以 E2EE 方式保存给有权查看邀请详情的管理员。

### 3.2 发送外部通知

身份验证服务通过传统渠道（SMTP 邮件、SMS）将包含链接的邀请发送给该 3PID。

外部通知 URL **MUST** 把 `invite_token` 放在 **URL fragment**（`#token=...`）或要求 out-of-band code 录入，**MUST NOT** 把 token 放在 URL query string 或 path segment 中。原因：

- URL query / path 会被 HTTP `Referer` 头泄露给第三方页面;
- 浏览器历史、邮件预览爬虫、URL preview 服务、HTTP access log、CDN log、SMTP gateway log 都会无差别记录 query / path;
- fragment 段不会随 HTTP 请求发送给服务端,也不进入 Referer 头;
- 这条规则与 [`api-conventions.md` §3](./api-conventions.md) 的 URL credential taxonomy 一致：invite token 是 capability-equivalent material，但 `#token=` 只是客户端 handoff，不是服务端认证入口。客户端读取 fragment 后 MUST 通过 JSON body 或 signed proof 提交 claim，MUST 使用 `history.replaceState` 或等价机制清除地址栏 fragment，且 MUST NOT 将 token 写入 route state、analytics、crash report、普通日志、local storage 或浏览器历史。

**Canonical 示例**（fragment 形式）：

```text
https://app.contrix.example/invite#token=<invite_token>
```

或 OOB code 形式（用户在已打开的客户端中手动录入）：

```text
邮件正文: Your invite code is XYZ7-K9MP-Q4LB-A2HN-V8RD-T6FW.
打开 Contrix → "我有邀请码" → 输入 XYZ7-K9MP-Q4LB-A2HN-V8RD-T6FW.
```

> **OOB code 熵约束（normative）**：上面 `XYZ7-K9MP-Q4LB-A2HN-V8RD-T6FW` 是说明性占位，**不**是允许的固定低熵格式。真实 OOB code MUST 满足下列**任一**模式才能被接受：
>
> 1. **离线可校验形态**：与 URL `#token=` 等价，MUST ≥ 128-bit 真随机熵（即至少 22 个 base32 字符或等价编码）。短分隔符（破折号）允许出现以方便用户录入，但不计入熵；编码字母表 MUST 排除易混字符（去掉 `0/O/1/I/L`），熵下限按剩余字母表大小重算。
> 2. **服务端 lookup 短码形态**：可以使用较短人类可读码（如示例 `XYZ-123-ABC`），但 MUST 全部满足：(a) 仅作为服务端私有 lookup 表的索引，token bytes 本身不参与 claim 校验；(b) 失败 claim 严格限速（每 IP / 设备 / 邀请者 同时 ≤ 5 次/分钟、≤ 50 次/天）；(c) 配合服务端 pepper / HMAC 存储，使短码无法离线枚举；(d) 短码 wire form 加入 `oob_code_kind="lookup"` 字段以便 wire-level 校验区分；(e) 同一短码命名空间下连续 3 次错误尝试 MUST invalidate 该 invite（强制邀请者重发）。
>
> 任何不能满足以上 (1) 或 (2) 全部条件的 OOB code 不得作为生产 wire 形态。conformance vector `cx.vector.invite.oob_code_entropy.v1` 覆盖短熵 OOB code claim 被拒、lookup 形态超限被 invalidate 两种情况。

**禁止形态**（reducer / 服务端 MUST 拒绝 inbound claim 携带这种 token 来源声明）：

```text
https://app.contrix.example/invite?token=<invite_token>&realm=cx:realm:...    ❌ token in query
https://app.contrix.example/invite/<invite_token>                              ❌ token in path
```

邮件/SMS 内容不得包含 Realm 私密名称、成员列表、历史摘要或其他未授权预览。验证服务 MUST 在 SMTP 网关上启用 sender domain restriction (SPF/DKIM/DMARC) 以防 token-bearing link 被 phishing 重用。

## 4. 认领流程 (Claiming)

当 Bob 收到邮件并点击链接，他在客户端完成了注册并获得了自己的 `did:webvh:QmZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:bob.example.com`（v1 core 默认 principal DID method 为 `did:webvh`，见 [identity-did.md §3](../identity/identity-did.md)；`personal_node` profile 的 Bob 可选 `did:web:bob.example.com`，其他 deployment profile 不得使用 `did:web` 作为长期 principal）。接下来他需要认领这个邀请。

### 4.1 出示 Token 与绑定

Bob 的客户端将 `invite_token`、自己的 DID、设备证明和 intended Realm 提交给 Alice 的身份验证服务。
身份验证服务验证 token、过期时间、claim 次数和 Realm 绑定无误后，原子消费该 token，并使用之前预留的**临时私钥 (对应 3.1 节的 `verification_public_key`)** 签署一个**绑定证明 (Binding Proof)**，声明：
“持有该 Token 的人现在对应的 DID 是 `did:webvh:QmZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:bob.example.com`”。

### 4.2 提交转换 Event

身份验证服务（或 Bob 代理）将该证明连同 Bob 的签名，打包成一个 `cx.invite.claim` Event 提交到 Realm。`payload` 为：

```json schema=schemas/event-payload.schema.json#/$defs/invite_payload
{
  "invite_id": "cx:invite:0196419b-1000-7000-8000-000000000000",
  "subject_id": "did:webvh:QmZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:bob.example.com",
  "token_commitment": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "claim_nonce": "01JX7Z5Q9Y4K2M8N6P3R1T0V",
  "binding_proof": {
    "verification_service_did": "did:web:identity.alice.example",
    "verification_method": "did:web:identity.alice.example#invite-001",
    "subject_id": "did:webvh:QmZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:bob.example.com",
    "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
    "audience": "contrix.invite.claim",
    "claim_nonce": "01JX7Z5Q9Y4K2M8N6P3R1T0V",
    "expires_at": "2026-05-05T00:00:00Z",
    "signature": "c2ln"
  },
  "subject_proof": {
    "verification_method": "did:webvh:QmZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:bob.example.com#device-1",
    "alg": "EdDSA",
    "signature": "c2ln"
  }
}
```

### 4.3 状态机转换

Realm 中的其他节点（Sync Service / 客户端本地 projection）在收到该 Event 时：
1. 匹配 `token_commitment` 与未过期、未撤销、未认领的 `cx.invite.third_party`。
2. 验证 `binding_proof` 必须由对应的 `verification_public_key` 签署，并绑定 `subject_id`、`realm_id`、audience、过期时间和 claim nonce。
3. 验证 `subject_proof` 来自 Bob DID 的当前有效 verification method，防止验证服务把 token 绑定到攻击者 DID。
4. 原子标记 pending invite 为 `claimed`；同一个 `token_commitment` 的第二次认领 MUST reject。
5. 如果验证通过，该占位符邀请正式转变为针对 `did:webvh:QmZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:bob.example.com` 的标准 `cx.invite.create` 或等价 membership proposal。
6. 随后 Bob 按照正常流程发送 `cx.invite.accept` 加入 Realm。

验证服务 / 接收 Sync Service MUST 维护 `(invite_id, claim_nonce)` 去重 set，TTL 至少覆盖 `invite.expires_at + 24h`。任一 nonce 一旦进入该 set，后续携带同一 `(invite_id, claim_nonce)` 的 claim Event MUST 在进入 reducer 仲裁前拒绝，即使前一次 claim 最终因其它原因未成为 winner。该 set 的 key SHOULD 存储为 HMAC / hash，不得持久化明文 invite token；对外失败形态仍按 §6 的不可枚举响应处理。

## 5. E2EE 场景处理

对于端到端加密的 Realm，MLS (Message Layer Security) 组无法包含一个没有公钥的邮件地址。

因此，在 Pending Invite 阶段，Bob 是**不在** MLS 组中的，无法加密或解密任何内容。
只有当 Bob 认领了邀请（4.3 节）并获得了 DID 和相应的客户端初始化密钥包 (KeyPackage) 时，Alice 或群管理员才会向他发送 MLS `Welcome` 消息，将他正式引入加密组。

## 6. 过期、撤销与隐私要求

- 所有可被认领或接受的 invite MUST 携带 `expires_at`；`cx.invite.third_party` 的 v1 base profile 硬上限为 7 天，高安全 / audited / 企业 Realm 硬上限为 24 小时。需要更长生命周期的部署 MUST 声明扩展 profile，并要求额外 revalidation proof。
- 邀请者、Realm 管理员或 policy server MAY 发布 `cx.invite.revoke` 撤销 pending invite。撤销后任何 claim MUST reject。
- 验证服务 MUST 对 token claim 做限速、IP / device 风险控制和重放检测；失败响应不得泄露 token 是否存在、Realm 是否存在或 3PID 是否被邀请。
- Event 中不得出现明文 3PID、未加盐 3PID hash、token 原文、短信验证码或邮件验证码。需要审计时只能保存加密审计记录、salt id、token commitment、发送时间和服务签名。
- `token_salt` MUST 按邀请或批次高熵生成，不能使用全局常量 salt。低熵 3PID 的承诺必须加入服务私有 pepper 或改用不公开的 lookup table，防止离线字典爆破。
- claim 成功后，外部 3PID 与 `subject_id` 的绑定默认只在邀请上下文内有效；不得自动发布为全局 handle、联系人或组织成员资格。

### 6.1 失败 / 异常清理状态机（normative）

第三方邀请的 wire 状态机覆盖正常路径之外的失败 / 邀请者状态变化 / token 泄漏。各 invite cell 状态转换由 reducer 强制：

| 触发条件 | 状态转换 | 行为 |
| --- | --- | --- |
| `expires_at <= now` | `pending → expired` | 任何 claim MUST `expired_invite_token` 拒绝；服务端 MUST 在 24h 内 zeroize `token_salt` / lookup pepper material，并 GC active commitment 记录。 |
| 邮件 / SMS 发送失败（gateway 5xx / bounce / DKIM fail） | `pending → send_failed`（携带 `send_failure_reason`） | 邀请者 UI MUST 显式提示发送失败；服务端 MUST NOT 假装成功；MAY 在 retry budget 内自动重试（建议 ≤ 3 次，指数退避）。retry 耗尽后 transition 为 `send_failed`，服务端 MUST 在 24h 内 zeroize token material；邀请者 MAY 手动重发（产生新 `invite_id` + 新 token + 新 commitment）。 |
| 邀请者失去 `cx.invite.create_third_party` capability（grant revoke、role change） | `pending → revoked_by_capability_loss` | 后续 claim MUST `capability_denied` 拒绝；commitment 立即从 active set 中移除，`token_salt` / lookup pepper material MUST 在 24h 内 zeroize。 |
| 邀请者主动离开 Realm（`cx.member.state` → `leave`/`ban`/`remove`） | `pending → revoked_by_inviter_left` | 同上 capability loss 处理；邀请不随邀请者继承到其他成员。 |
| token 泄漏 / 怀疑泄漏（邀请者或 admin 发起 `cx.invite.revoke`） | `pending → revoked` | 立即拒绝任何 claim；`token_salt` / lookup pepper material MUST 在 24h 内 zeroize；客户端 UI MUST 显示"邀请已撤销"。 |
| claim 成功 | `pending → claimed` | 同一 `token_commitment` 第二次 claim MUST `duplicate_conflict`；claim 接受后 `token_salt` / lookup pepper material MUST 在 24h 内 zeroize，只保留不可枚举 audit receipt。 |
| OOB lookup 形态失败次数超限（§3） | `pending → invalidated_by_rate_limit` | 强制邀请者重发；`token_salt` / lookup pepper material MUST 在 24h 内 zeroize；不暴露具体失败次数给攻击者。 |

**统一不可枚举响应（normative）**：claim 失败响应 MUST 不区分上面 7 种触发；对外仅返回统一 `not_found`（或同形态错误），让攻击者无法通过响应差异判断 token 是否存在、是否过期、是否被撤销、邀请者是否离开 Realm。具体 reason_code 仅写入服务端 audit log。这条规则覆盖 §6 的"失败响应不得泄露 token 是否存在"。`cx.vector.invite.failure_indistinguishable.v1` 覆盖上面 7 种触发对外返回 byte-identical 响应（含 timing 类，差异 ≤ 50ms）。
