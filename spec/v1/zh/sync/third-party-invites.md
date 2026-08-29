---
title: Third-Party Invites
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

去中心化协议通常假设所有的主键都是其原生的密码学标识符（如 DID）。然而，在现实协作中，用户经常需要邀请**尚未注册或不知道其 DID** 的外部人员（如通过电子邮件地址或手机号）。

本规范定义了如何通过**第三方标识符 (3PID - Third-Party Identifier)** 安全地将外部用户邀请到 Realm，并在他们注册并创建 DID 后认领这些邀请。

## 2. 身份验证代理机制

由于外部的邮箱或手机号无法自己生成非对称密钥对和 DID，邀请流程 MUST 借助一个**身份验证服务 (Identity Verification Service)** 来充当代理。

这个代理服务通常是发起邀请的用户所在的 Principal Server、组织控制的 Identity Verification Service，或 Realm policy 明确允许的第三方验证服务。服务 DID、用途、过期时间和可见性 MUST 写入 invite metadata 或 Realm policy。该验证服务 DID 只负责 3PID claim；Bob 后续只向自己的 Principal Server 提交 invite-accept，后者才可按 signed invite / 当前 joined-member delivery binding 使用有界 `join_candidates[]` 转发，二者不得混用。

### 2.1 验证服务威胁假设（normative）

第三方邀请把"谁持有该 3PID"的判定**完全委托**给 `verification_id`。因此本机制的信任根中，`verification_id` 是一个**受信第三方**：

- **威胁假设**：`verification_id` 的妥协（私钥失窃、运营方作恶、SMTP / SMS 投递链被控制）**等价于该 3PID 邀请被完全控制**——被妥协的验证服务可以把 token 绑定到攻击者 DID 并签发貌似合法的 `binding_proof`。`subject_proof`（§4.3 step 5）只能保证"binding_proof 中声明的 subject DID 同意被绑定"，无法在验证服务本身作恶时把 token 重新导回真实 3PID 持有人。实现与部署方 MUST 在威胁模型中把验证服务视为与该 3PID 邀请同等级别的信任主体，不得当作纯粹无信任的中继。
- **Allowlist（MUST）**：由于验证服务是该 3PID 邀请的信任根（其妥协等价于邀请被完全控制，见上一条），信任根 MUST NOT 由 invite metadata 任意带入。唯一 canonical carrier 是当前 accepted `ak.realm.policy_bundle.payload.allowed_third_party_invite_verification_ids`：它是 service DID 的全量替换集合，省略与 `[]` 都表示 deny-all；更高 `policy_revision` 省略旧 DID 即完成撤销，不存在独立 tombstone。Invite 创建时只能从这个当前集合选择并绑定 `verification_id`；invite metadata 只记录选择结果，绝不成为授权来源。任何**未**落入该集合的 `verification_id` MUST NOT 被接受。`ak.invite.claim` 的 `binding_proof.verification_id` 不在当前集合内时，reducer 与接收 Principal Server sync surface MUST 在所有接受 3PID claim 的路径上拒绝该 claim（对外仍按 §6 不可枚举响应处理）。该约束是可测试门槛：给定一份其 `verification_id` 不属于目标 Realm 当前显式授权集的 `ak.invite.claim`，符合规范的 reducer 与 Principal Server sync surface必须拒绝其转换为 membership，且不得因 `subject_proof`（§4.3 step 5）有效而放行。
- **组织背书增强（informative）**：高安全 / audited / 企业 Realm MAY 在上述 MUST allowlist 之上叠加更强的验证服务可信度证明，例如要求验证服务 DID 由组织目录背书的 Verifiable Credential 声明、由 OIDC / SCIM 目录证明覆盖，或要求两个独立验证服务对同一 3PID 绑定各自签发见证 receipt（双服务见证），使任何单一验证服务的妥协都不足以独自完成 3PID 绑定。本条为增强建议，不改变上面 allowlist MUST 门槛对所有 Realm 的强制性。
- **二次确认通道（高安全 Realm，SHOULD / MUST）**：高安全 / audited / 企业 Realm SHOULD 要求一条独立于验证服务的二次确认通道（例如已在该 Realm 中的成员对 Bob 身份的带外确认、组织目录核对、或独立信道的人工 approval），使单一验证服务的妥协不足以让攻击者完成加入；声明该要求的高安全 Realm policy 中此条为 MUST。

## 3. 邀请流程

### 3.1 创建待定邀请 (Pending Invite)

当 Alice 想通过电子邮件 `bob@example.com` 邀请 Bob 加入 Realm 时：

1. **发起盲化邀请**：Alice 的客户端向她的 Principal Server 或授权的 Identity Verification Service 提交一个针对 3PID 的邀请。公开持久化 Event 中 MUST NOT 写入明文邮箱、手机号或可枚举的未加盐哈希。
2. **生成邀请令牌**：验证服务生成至少 128 bit 熵的随机 `invite_token`，并生成独立 `token_salt`。`invite_token` MUST 只通过外部通知渠道发送给被邀请人，不得写入公开 Event。
3. **写入占位符 Event**：Alice 向 Realm 提交一个特殊的 `ak.invite.third_party` Event，其 `payload` 为：

```json schema=schemas/event-payload.schema.json#/$defs/invite_third_party_create_payload
{
  "third_party_invite": {
    "display_name_hint": "external invite",
    "token_commitment": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "token_salt_id": "salt-2026-04-28-invite-001",
    "oob_code_kind": "offline_token",
    "token_entropy_bits": 128,
    "verification_id": "ak:did_core:webvh:z6TrH1Ntf6QjaSBbShfKTrNbt",
    "verification_public_key": "did:webvh:z6TrH1Ntf6QjaSBbShfKTrNbt:identity.alice.example#invite-001",
    "max_claims": 1
  },
  "expires_at": "2026-05-05T00:00:00.000Z"
}
```

`token_commitment` 是盐化承诺；`token_salt` 原值只保存在验证服务的私有状态或加密审计记录中。`oob_code_kind` 是 wire-level discriminator：`offline_token` 表示 OOB code 自身满足 ≥128-bit 熵并按 commitment 校验；`lookup` 表示短码只作为服务端私有 lookup 表索引，必须走 pepper/HMAC 存储与限速。该结构的 object 形态由 [`invite.schema.json`](../../artifacts/schemas/invite.schema.json) 的 `third_party_invite` 定义。`verification_public_key` 是验证服务生成的临时签名公钥，用于后续 claim / 认领验证。若需要在 UI 显示目标邮箱，应只在邀请者本地私有状态中保存，或以 E2EE 方式保存给有权查看邀请详情的管理员。

### 3.2 发送外部通知

身份验证服务通过传统渠道（SMTP 邮件、SMS）将包含链接的邀请发送给该 3PID。

外部通知 URL **MUST** 把 `invite_token` 放在 **URL fragment**（`#token=...`）或要求 out-of-band code 录入，**MUST NOT** 把 token 放在 URL query string 或 path segment 中。原因：

- URL query / path 会被 HTTP `Referer` 头泄露给第三方页面;
- 浏览器历史、邮件预览爬虫、URL preview 服务、HTTP access log、CDN log、SMTP gateway log 都会无差别记录 query / path;
- fragment 段不会随 HTTP 请求发送给服务端，也不进入 Referer 头;
- 这条规则与 [`api-conventions.md` §3](./api-conventions.md) 的 URL credential taxonomy 一致：invite token 是 capability-equivalent material，但 `#token=` 只是客户端 handoff，不是服务端认证入口。客户端读取 fragment 后 MUST 通过 JSON body 或 signed proof 提交 claim，MUST 使用 `history.replaceState` 或等价机制清除地址栏 fragment，且 MUST NOT 将 token 写入 route state、analytics、crash report、普通日志、local storage 或浏览器历史。

**Canonical 示例**（fragment 形式）：

```text
https://app.arkret.example/invite#token=<invite_token>
```

或 OOB code 形式（用户在已打开的客户端中手动录入）：

```text
邮件正文: Your invite code is XYZ7-K9MP-Q4LB-A2HN-V8RD-T6FW.
打开 Arkret → "我有邀请码" → 输入 XYZ7-K9MP-Q4LB-A2HN-V8RD-T6FW.
```

> **OOB code 熵约束（normative）**：上面 `XYZ7-K9MP-Q4LB-A2HN-V8RD-T6FW` 是说明性占位，**不**是允许的固定低熵格式。真实 OOB code MUST 满足下列**任一**模式才能被接受：
>
> 1. **离线可校验形态**：与 URL `#token=` 等价，MUST ≥ 128-bit 真随机熵（即至少 22 个 base32 字符或等价编码）。短分隔符（破折号）允许出现以方便用户录入，但不计入熵；编码字母表 MUST 排除易混字符（去掉 `0/O/1/I/L`），熵下限按剩余字母表大小重算。
> 2. **服务端 lookup 短码形态**：可以使用较短人类可读码（如示例 `XYZ-123-ABC`），但 MUST 全部满足：(a) 仅作为服务端私有 lookup 表的索引，token bytes 本身不参与 claim 校验；(b) 失败 claim 严格限速（每 IP / 设备 / 邀请者 同时 ≤ 5 次/分钟、≤ 50 次/天）；(c) 配合服务端 pepper / HMAC 存储，使短码无法离线枚举；(d) 短码 wire form 加入 `oob_code_kind="lookup"` 字段以便 wire-level 校验区分；(e) 同一短码命名空间下连续 3 次错误尝试 MUST invalidate 该 invite（强制邀请者重发）。
>
> 任何不能满足以上 (1) 或 (2) 全部条件的 OOB code 不得作为生产 wire 形态。conformance vector `ak.vector.invite.oob_code_entropy.v1` 覆盖短熵 OOB code claim 被拒、lookup 形态超限被 invalidate 两种情况。

**禁止形态**（reducer / 服务端 MUST 拒绝 inbound claim 携带这种 token 来源声明）：

```text
forbidden: https://app.arkret.example/invite?token=<invite_token>&realm=ak:realm:...    token in query
forbidden: https://app.arkret.example/invite/<invite_token>                              token in path
```

邮件/SMS 内容不得包含 Realm 私密名称、成员列表、历史摘要或其他未授权预览。验证服务 MUST 在 SMTP 网关上启用 sender domain restriction (SPF/DKIM/DMARC) 以防 token-bearing link 被 phishing 重用。

## 4. 认领流程 (Claiming)

当 Bob 收到邮件并点击链接，他在客户端完成注册，持有完整 `did = did:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:bob.example.com`，其稳定业务身份为 `did_core_id = ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z`。接下来他需要认领这个邀请。

### 4.1 出示 Token 与绑定

Bob 的客户端将 `invite_token`、自己的 `did_core_id`、用于独立验证的 `did`、设备证明和 intended Realm 提交给 Alice 的身份验证服务。
身份验证服务验证 token、过期时间、claim 次数和 Realm 绑定无误后，原子消费该 token，并使用之前预留的**临时私钥 (对应 3.1 节的 `verification_public_key`)** 签署一个**绑定证明 (Binding Proof)**，声明：
“持有该 Token 的人现在对应的稳定业务身份是 `ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z`”。

**投递目标可审计（normative）**：由于验证服务是受信第三方（见 §2.1），其签发 `binding_proof` 时 MUST 在自身审计记录中记录该 token 在 §3.2 实际投递目标的 digest（例如 `delivery_target_digest = SHA-256(salt || canonical(3pid))`，使用与 `token_salt` 同级或独立的高熵 salt / pepper）。该 digest 不得写入公开持久化 Event（避免 3PID 枚举，与 §6 一致），但 MUST 进入验证服务的加密审计记录，使事后审计可以核对"该 token 是否被投递给 invite 声明的那个 3PID"。这样当验证服务被怀疑把 token 绑定到非声明 3PID（即把邀请重定向给攻击者）时，审计方可凭 invite 中声明的 3PID 重算 digest 与审计记录比对，检出该错配。

### 4.2 提交转换 Event

身份验证服务（或 Bob 代理）将该证明连同 Bob 的签名，打包成一个 `ak.invite.claim` Event 提交到 Realm。`payload` 为：

```json schema=schemas/event-payload.schema.json#/$defs/invite_claim_payload
{
  "invite_id": "ak:invite:AfVi-FmTYttG2uQeB67y7GdHhOrWGxBe0QaDAOwYnK01",
  "subject_id": "ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
  "token_commitment": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "claim_nonce": "01JX7Z5Q9Y4K2M8N6P3R1T0V",
  "binding_proof": {
    "verification_id": "ak:did_core:webvh:z6TrH1Ntf6QjaSBbShfKTrNbt",
    "verification_method": "did:webvh:z6TrH1Ntf6QjaSBbShfKTrNbt:identity.alice.example#invite-001",
    "subject_id": "ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
    "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
    "audience": "arkret.invite.claim",
    "claim_nonce": "01JX7Z5Q9Y4K2M8N6P3R1T0V",
    "expires_at": "2026-05-05T00:00:00.000Z",
    "signature": "c2ln"
  },
  "subject_proof": {
    "verification_method": "did:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:bob.example.com#device-1",
    "signature_algorithm": "Ed25519",
    "transcript_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "signature": "c2ln"
  }
}
```

`binding_proof.signature` 的签名输入 MUST 使用域分隔 transcript：

`utf8("ak.invite.claim.binding_proof.v1\n") || canonical_json({audience:"arkret.invite.claim", binding_proof: unsigned_binding_proof, claim_nonce, invite_digest, invite_id, realm_id, subject_id, token_commitment, verification_id})`

其中 `unsigned_binding_proof` 是去掉 `signature` 字段后的 `binding_proof` object；`verification_id` 等于 `binding_proof.verification_id`；`invite_digest` 是 reducer 当前 pending invite cell 的 canonical digest，计算对象为 `canonical_json({invite_id, realm_id, expires_at, third_party_invite})` 后取 `sha256:<hex>`，其中 `third_party_invite` MUST 使用该 invite cell 内的当前字段值。Reducer MUST 用 invite cell 记录的 `verification_public_key` / `verification_method` 校验该签名；只验证 `binding_proof` 裸 object、或不绑定 `invite_id` / `token_commitment` / `invite_digest` / `claim_nonce` 的证明 MUST reject。

### 4.3 Realm reducer 状态机转换

`ak.invite.claim` 是 Realm 控制面 reducer input。Principal Server sync surface、验证服务和客户端 MAY 在入站路径做格式、签名、限速和不可枚举预拒绝，但它们不得成为 invite state 的真源；是否把某个 `ak.invite.third_party` 从 `pending` 推进到 `claimed`、是否产生后续 membership proposal / accept 权限，只能由目标 Realm 的 reducer 在同一状态机中决定。任何 projection、缓存或服务端本地表若与 reducer 结果冲突，MUST 以 reducer 结果为准并回滚派生状态。

Reducer 处理 `ak.invite.claim` 时 MUST 按下列顺序 fail closed；所有内部 reason code 对外仍按 §6 不可枚举响应处理：

1. 从当前 accepted Realm frontier 读取目标 invite cell，按 `invite_id` 与 `token_commitment` 匹配一条 `state="pending"` 的 `ak.invite.third_party`；`token_commitment` 不一致、invite 不存在、不是 3PID invite、或已进入 `claimed` / `expired` / `revoked` / `send_failed` / `invalidated_by_rate_limit` 等非 pending 状态时 MUST reject，且不得创建 membership proposal。**pending 判定的撤销新鲜度（normative）**：reducer 判定 invite cell 仍为 `pending` 所依据的控制面 basis MUST 在目标 Realm 的 `revocation_freshness_window_ms` 内仍新鲜；无法确认该 basis 未漏看 `ak.invite.revoke`、邀请者 capability loss、邀请者 leave/ban/remove 或等价撤销 transition 时，MUST fail closed（拒绝本次 claim 或 quarantine 待 backfill 后重判），MUST NOT 用陈旧 candidate 视图放行高风险 claim。
2. 在任何签名接受前重算过期前置条件。**判定时点是 canonical、签名覆盖的量，MUST NOT 使用 receiver 本地墙钟 `now`（normative）**：
   - 比较对象固定为该 `ak.invite.claim` Event 自身的签名 `created_at`（进入 canonical bytes 与 `event_digest`，对所有 receiver 唯一确定）与 invite cell 在该 claim CBA basis 上的 `expires_at`。`invite.expires_at <= claim_event.created_at` 时 MUST 以 `expired_invite_token` 拒绝本次 claim。
   - 若该 claim 已被 Seal 覆盖，同一判定 MUST 得到相同结果；receiver MUST NOT 因为重放 / backfill 发生在更晚的本地时刻而改判。这是 `apply_seal` 与 `J(L)` "不依赖本地时钟、对同一依赖集合为纯函数" 硬约束的直接推论（[`../authz/event-auth-state-resolution.md` §6.3](../authz/event-auth-state-resolution.md)）。
   - **被拒绝的 claim MUST NOT 产生任何共享 projected write（normative）**：它不写 invite cell、不写 membership proposal、不推进任何 lattice。invite 的 `pending -> expired` 是**独立的、已登记的、可签名且可被 Seal 覆盖的 Control Move**（由授权 writer 提交的 `ak.invite.revoke`，携带 `reason_code` 表达 `expired`，见 [`../models/governance-objects.md` §5.3](../models/governance-objects.md)），MUST NOT 由被拒 claim 的处理路径顺带写出——那样的 transition 没有独立 accepted Event / event digest，无法被另一 receiver 从 canonical history 重放，等于把 receiver-local timer 提升成共享真相源。
   - reducer 在读到 invite cell 已处于 `expired` 或任一终态时，按 step 1 的终态规则拒绝。token material / lookup pepper 的 zeroize 规则见 §6.1；zeroize 是**服务端本地清理义务**，不是共享 cell 状态，MUST NOT 反过来充当 invite state 的真源。
3. 验证 `binding_proof` 必须由该 invite 记录中的 `verification_public_key` 签署，签名输入 MUST 是 §4.2 定义的 `ak.invite.claim.binding_proof.v1` transcript，并绑定 `subject_id`、`realm_id`、audience、过期时间、claim nonce、`invite_id`、`token_commitment` 与 invite cell digest；`binding_proof.subject_id`、`binding_proof.realm_id`、`binding_proof.claim_nonce` 与 payload 顶层字段不一致时 MUST reject。
4. 从 claim CBA basis 的当前 accepted `ak.component.realm.policy_bundle.v1` cell 读取 `allowed_third_party_invite_verification_ids`，复校验 `binding_proof.verification_id` 在该集合中；字段缺失或空数组都是 deny-all。Invite 创建时绑定的 DID 也必须与 binding proof 一致，但 invite metadata 不能把一个当前已移除的 DID重新授权。该复校验必须在 reducer 内执行；不能因为验证服务、Auth Server、接收 Principal Server sync surface 或历史 invite metadata 已经校验过而跳过。不在授权集内的 `verification_id` MUST reject，且不得因后续 `subject_proof` 有效而放行。**该复校验 MUST 绑定 revocation freshness（normative）**：reducer 判定该集合所依据的 bundle cell Seal basis MUST 在目标 Realm 的 `revocation_freshness_window_ms` 内仍新鲜；不得用陈旧 basis 把一个**可能已被撤销**的 `verification_id` 当作仍在授权集内放行。由于验证服务的妥协等价于该 3PID 邀请被完全控制（§2.1），3PID claim 属高风险写入：当 reducer 无法在窗口内确认 bundle basis 新鲜时，MUST fail closed——拒绝该 claim 或 quarantine 待 backfill 到足够新鲜的控制面 basis 后重判，MUST NOT 在 freshness 未知时接受 claim。
5. 验证 `subject_proof` 来自 `subject_id` 的当前有效 verification method，防止验证服务把 token 绑定到攻击者 DID。该签名 MUST 覆盖 canonical transcript `utf8("ak.invite.claim.subject_proof.v1\n") || canonical_json({subject_id, invite_id, realm_id, token_commitment, claim_nonce, audience:"arkret.invite.claim", verification_id, binding_proof_digest})`，其中 `verification_id` 等于 `binding_proof.verification_id`，`binding_proof_digest` 是 `binding_proof` 的 canonical-JSON digest（`sha256:<hex>`）。这确保 subject 证明的语义是"我同意被这个特定验证服务签发的这个特定 `binding_proof` 绑定"，而不是泛化的"我同意加入"；据此，攻击者或被替换的验证服务无法把另一份 binding_proof / 另一个验证服务身份套用到同一 subject signature 上。只验证裸 DID 控制权、或不绑定 `invite_id` / `realm_id` / `token_commitment` / `claim_nonce` / `verification_id` / `binding_proof_digest` 的 subject proof MUST reject；`verification_id` 与 `binding_proof.verification_id` 不一致、或 `binding_proof_digest` 与 `binding_proof` 实际 canonical digest 不一致时同样 MUST reject。
6. 在 reducer state 中检查 `(invite_id, claim_nonce)` 与 `token_commitment` 两类一次性约束：同一 `(invite_id, claim_nonce)` 的重复 claim、或同一 `token_commitment` 已有 accepted claim projection，均 MUST 以 `duplicate_conflict` 拒绝。v1 base wire 中 `third_party_invite.max_claims` MUST 恒为 `1`；任何大于 `1` 或缺失后被解释为多用 token 的写入 MUST `schema_violation` / `duplicate_conflict` fail closed。该检查必须与 invite cell 的 `pending -> claimed` transition 原子提交，不能依赖入站服务的幂等表作为唯一保护。
7. 验证通过后，reducer MUST 原子投影 claim writes：invite cell `pending -> claimed`，记录 `claimed_by=subject_id`、`claim_event_ref`、`claim_nonce_digest`、`token_commitment`、`verification_id` 与 `claimed_at` 等派生投影字段；随后该占位符邀请正式转变为针对 `subject_id` 的标准 `ak.invite.create` 或等价 membership proposal。`ak.invite.claim` 本身不直接绕过 Realm join policy 写入 `ak.member.state{membership="join"}`；最终 join 仍由 `subject_id` 通过 `ak.invite.accept` 或 profile 声明的等价 membership proposal 路径完成，reducer MUST 校验 accept/proposal 引用的是这次 accepted claim Event。

验证服务 / 接收 Principal Server sync surface SHOULD 维护 `(invite_id, claim_nonce)` 去重 set，TTL 至少覆盖 `invite.expires_at + 24h`，用于在进入 reducer 仲裁前降低重放成本；该服务侧 set 不是状态真源。任一 nonce 一旦被 reducer 作为 accepted 或 rejected claim 观察到，后续携带同一 `(invite_id, claim_nonce)` 的 claim Event MUST 被 reducer 拒绝，即使前一次 claim 未成为 invite cell winner。该 set 的 key SHOULD 存储为 HMAC / hash，不得持久化明文 invite token；对外失败形态仍按 §6 的不可枚举响应处理。

> **Conformance vector（normative）**：上述 reducer 闭环由 `ak.vector.invite.claim_reducer_state_machine.v1` 覆盖（登记于 `artifacts/registry/vector-registry.json`，fixture 位于 `artifacts/fixtures/security-closure-fixture.json`）：正路径必须产生 `pending -> claimed` 与 membership proposal；token commitment mismatch、allowlist 复校验失败、claim nonce 重放、expired cleanup 四类负路径均不得产生 membership proposal。

**v1 base wire 范围（normative）**：v1 base conformance 仅支持 `invite` / `restricted` join-rule Realm 的 third-party claim 接续到 `ak.invite.create`（或等价 membership proposal）路径，如上述步骤 7 所述。knock_restricted Realm 的 third-party 接续依赖 candidate join-policy profile（见 [`../governance/join-policy.md` §7.5](../governance/join-policy.md)）、目标 Realm 精确 `ak.realm.admin` reviewer grant，以及 `member.application` candidate kind（见 [`operations-sync.md`](operations-sync.md)），**不属于 v1 base conformance**；部署 MUST 在 `ak.find.directory.read.describe.v1` / `ak.self.account.read.describe.v1` 中显式声明该 candidate profile 后才可在 `knock_restricted` Realm 上使用 third-party claim 流程，否则验证服务 MUST 以 `unsupported_join_rule` 拒绝该 token claim。

## 5. E2EE 场景处理

对于端到端加密的 Realm，MLS (Message Layer Security) 组无法包含一个没有公钥的邮件地址。

因此，在 Pending Invite 阶段，Bob 是**不在** MLS 组中的，无法加密或解密任何内容。
只有当 Bob 认领了邀请（4.3 节）并获得了 DID 和相应的客户端初始化密钥包 (KeyPackage) 时，Alice 或群管理员才会向他发送 MLS `Welcome` 消息，将他正式引入加密组。

## 6. 过期、撤销与隐私要求

- 所有可被认领或接受的 invite MUST 携带 `expires_at`；`ak.invite.third_party` 的 v1 base profile 硬上限为 7 天，高安全 / audited / 企业 Realm 硬上限为 24 小时。需要更长生命周期的部署 MUST 声明扩展 profile，并要求额外 revalidation proof。
- 邀请者或 Realm 管理员 MAY 发布 `ak.invite.revoke` 撤销 pending invite。撤销后任何 claim MUST reject。
- 验证服务 MUST 对 token claim 做限速、IP / device 风险控制和重放检测；失败响应不得泄露 token 是否存在、Realm 是否存在或 3PID 是否被邀请。
- Event 中不得出现明文 3PID、未加盐 3PID hash、token 原文、短信验证码或邮件验证码。需要审计时只能保存加密审计记录、salt id、token commitment、发送时间和服务签名。
- `token_salt` MUST 按邀请或批次高熵生成，不能使用全局常量 salt。低熵 3PID 的承诺必须加入服务私有 pepper 或改用不公开的 lookup table，防止离线字典爆破。
- claim 成功后，外部 3PID 与 `subject_id` 的绑定默认只在邀请上下文内有效；不得自动发布为全局 handle、联系人或组织成员资格。

### 6.1 失败 / 异常清理状态机（normative）

第三方邀请的 wire 状态机覆盖正常路径之外的失败 / 邀请者状态变化 / token 泄漏。各 invite cell 状态转换由 reducer 强制：

| 触发条件 | 状态转换 | 行为 |
| --- | --- | --- |
| `expires_at` 已过（由授权 writer 观察并提交显式 Move） | `pending -> expired` | 该 transition MUST 由授权 writer 提交的显式 `ak.invite.revoke`（`reason_code` 表达 expired）承载，是可签名、可被 Seal 覆盖的 Control Move；MUST NOT 由本地计时器或被拒 claim 的处理路径顺带写出（§4.3 step 2）。在该 Move 被接受之前，claim 仍按 §4.3 step 2 以签名 `created_at` 与 `expires_at` 比较后拒绝，判定对所有 receiver 与所有重放时点一致。服务端 MUST 在 24h 内 zeroize `token_salt` / lookup pepper material，并 GC active commitment 记录（本地清理义务，不是共享状态）。 |
| 邮件 / SMS 发送失败（gateway 5xx / bounce / DKIM fail） | `pending → send_failed` | 邀请者 UI MUST 显式提示发送失败；服务端 MUST NOT 假装成功；MAY 在 retry budget 内自动重试（建议 ≤ 3 次，指数退避）。**与 `expired` 同一承载形态**：retry 耗尽后的 `send_failed` transition MUST 由授权 writer 提交的显式 `ak.invite.revoke`（`target_state="send_failed"`，`reason` 表达投递失败原因）承载，是可签名、可被 Seal 覆盖的 Control Move；MUST NOT 由投递重试循环或本地计时器顺带写出，投递失败本身只是该 writer 提交前的观察。`reason` 是唯一的失败原因载体，MUST NOT 另造 `send_failure_reason` 字段，且 MUST NOT 泄漏 3PID 明文、token 原文或验证码。服务端 MUST 在 24h 内 zeroize token material；邀请者 MAY 手动重发（产生新 `invite_id` + 新 token + 新 commitment）。`send_failed` 是终态方向：**MUST NOT 回到 `pending`**——重发是新 invite，不是旧 cell 复活。 |
| 邀请者失去 `ak.invite.third_party` capability（grant revoke、role change） | `pending → revoked_by_capability_loss` | 后续 claim MUST `capability_denied` 拒绝；commitment 立即从 active set 中移除，`token_salt` / lookup pepper material MUST 在 24h 内 zeroize。 |
| 邀请者主动离开 Realm（`ak.member.state` → `leave`/`ban`/`remove`） | `pending → revoked_by_inviter_left` | 同上 capability loss 处理；邀请不随邀请者继承到其他成员。 |
| token 泄漏 / 怀疑泄漏（邀请者或 admin 发起 `ak.invite.revoke`） | `pending → revoked` | 立即拒绝任何 claim；`token_salt` / lookup pepper material MUST 在 24h 内 zeroize；客户端 UI MUST 显示"邀请已撤销"。 |
| claim 成功 | `pending → claimed` | 同一 `token_commitment` 第二次 claim MUST `duplicate_conflict`；claim 接受后 `token_salt` / lookup pepper material MUST 在 24h 内 zeroize，只保留不可枚举 audit receipt。 |
| OOB lookup 形态失败次数超限（§3） | `pending → invalidated_by_rate_limit` | 强制邀请者重发；`token_salt` / lookup pepper material MUST 在 24h 内 zeroize；不暴露具体失败次数给攻击者。 |

**两个消费点的悬挂态（normative）**：第三方邀请有**两个不同信任域的消费点**，二者之间无强一致：§4.1 验证服务端**原子消费 token**（签发 `binding_proof` 后该 token 即用尽），与 §4.3 step 4 reducer 侧**原子标记 pending invite 为 `claimed`**。当 token 已在验证服务侧消费、但承载该 `binding_proof` 的 `ak.invite.claim` Event 投递失败、被 reducer 拒绝或进入 quarantine（reducer 侧 invite 仍停留在 `pending`）时，二者处于不一致的悬挂态。规范要求：

- 一旦验证服务消费了某 token 并签发了 `binding_proof`，该 token MUST 被验证服务视为**已用尽**，即使后续未观察到对应 `ak.invite.claim` 在 Realm 落地为 `claimed`。验证服务 MUST NOT 对同一 token 重新签发第二份指向不同 / 相同 subject 的 `binding_proof`。
- 因此 claim 在 reducer 侧未落地（被拒 / quarantine / 投递丢失）时，该 invite 不能仅靠重发原 token 恢复；与 §6.1 状态机一致，邀请者 MUST 通过重发**新 `invite_id` + 新 token + 新 commitment** 来重试（等同于 §6.1 `send_failed` / `revoked` 后的重发路径），不得复用已消费 token。
- 验证服务 MAY 为该已消费 token 保留一个**可恢复窗口**（仅用于把同一份已签发 `binding_proof` 幂等重投递给 Realm，例如网络瞬断后的重试），但该窗口 MUST 绑定同一 `(invite_id, claim_nonce, subject_id, binding_proof_digest)`，不得用于把 token 重新绑定到其它 subject；窗口耗尽后 MUST 按上一条要求邀请者重发新 invite。

> **Conformance vector（normative）**：上述"已消费 token 不得重绑到其他 subject"是防邀请重定向的关键安全不变量，由具名 conformance vector `ak.vector.invite.consumed_token_resubject_rejected.v1` 覆盖（登记于 `artifacts/registry/vector-registry.json`，向量数据见 `artifacts/fixtures/security-closure-fixture.json`），断言风格与既有 `ak.vector.invite.oob_code_entropy.v1`（§3）、`ak.vector.invite.failure_indistinguishable.v1`（§6.1）邀请向量对齐。该向量的意图：验证服务对**同一已消费 token**收到指向**不同 `subject_id`** 的第二次签发请求时 MUST 拒绝（不签发第二份 `binding_proof`）；仅当请求绑定同一 `(invite_id, claim_nonce, subject_id, binding_proof_digest)` 时才允许在可恢复窗口内幂等重投递同一份既有 `binding_proof`。向量同时断言：reducer 侧对承载已消费 token 重绑到不同 subject 的 `ak.invite.claim` Event MUST 以 `duplicate_conflict` 拒绝。

Claim 成功但 MLS Welcome / KeyPackage 派发尚未完成时，成员资格可以先进入 `claimed` / joined projection，但该成员对加密正文的客户端状态 MUST 走 [`client-sync.md` §15](./client-sync.md) 的 `decryption_pending` / timeout / recovery 机制；不得把 Welcome 缺失解释为 claim 回滚。KeyPackage 耗尽、过期或与 required capabilities 不匹配不得通过 claim 响应泄露远端库存状态；目标 endpoint 的客户端只按本地 inventory ledger 与已观测的 claim/Welcome 生命周期执行 single-flight bounded refill，新的 Welcome 到达后再按普通 MLS governance binding 校验恢复。

**统一不可枚举响应（normative）**：claim 失败响应 MUST NOT 区分上表 6 种失败触发（`claim 成功` 行不是失败触发）；对外仅返回统一 `not_found`（或同形态错误），让攻击者无法通过响应差异判断 token 是否存在、是否过期、是否被撤销、邀请者是否离开 Realm。具体 reason_code 仅写入服务端 audit log。这条规则覆盖 §6 的"失败响应不得泄露 token 是否存在"。`ak.vector.invite.failure_indistinguishable.v1` 覆盖这 6 种失败触发对外返回 byte-identical 响应（含 timing 类，差异 ≤ 50ms）。
