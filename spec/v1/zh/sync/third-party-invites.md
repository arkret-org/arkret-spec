---
title: Third-Party Invites
status: candidate
normative: true
stability: v1
updated: 2026-09-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

去中心化协议通常假设所有的主键都是其原生的密码学标识符（如 DID）。然而，在现实协作中，用户经常需要邀请**尚未注册或不知道其 DID** 的外部人员（如通过电子邮件地址或手机号）。

本规范定义了如何通过**第三方标识符 (3PID - Third-Party Identifier)** 安全地将外部用户邀请到 Realm，并在他们注册并创建 DID 后认领这些邀请。

## 2. 身份验证代理机制

由于外部的邮箱或手机号无法自己生成非对称密钥对和 DID，邀请流程 MUST 借助一个**身份验证服务 (Identity Verification Service)** 来充当代理。

这个代理服务通常是发起邀请的用户所在的 Station、组织控制的 Identity Verification Service，或 Realm policy 明确允许的第三方验证服务。服务 DID、用途、过期时间和可见性 MUST 写入 invite metadata 或 Realm policy。该验证服务 DID 只负责 3PID claim；Bob 后续只向自己的 Station 提交 invite-accept，后者才可按 signed invite / 当前 joined-joined-member ActorId routing projection 使用有界 `join_candidates[]` 转发，二者不得混用。

### 2.1 验证服务威胁假设（normative）

第三方邀请把"谁持有该 3PID"的判定**完全委托**给 `verification_id`。因此本机制的信任根中，`verification_id` 是一个**受信第三方**：

- **威胁假设**：`verification_id` 的妥协（私钥失窃、运营方作恶、SMTP / SMS 投递链被控制）**等价于该 3PID 邀请被完全控制**——被妥协的验证服务可以把 token 绑定到攻击者 DID 并签发貌似合法的 `binding_proof`。`subject_proof`（§4.3 step 5）只能保证"binding_proof 中声明的 subject DID 同意被绑定"，无法在验证服务本身作恶时把 token 重新导回真实 3PID 持有人。实现与部署方 MUST 在威胁模型中把验证服务视为与该 3PID 邀请同等级别的信任主体，不得当作纯粹无信任的中继。
- **Allowlist（MUST）**：由于验证服务是该 3PID 邀请的信任根（其妥协等价于邀请被完全控制，见上一条），信任根 MUST NOT 由 invite metadata 任意带入。唯一 canonical carrier 是当前 accepted `ak.realm.policy_bundle.payload.allowed_third_party_invite_verification_ids`：它是 service DID 的全量替换集合，省略与 `[]` 都表示 deny-all；更高 `policy_revision` 省略旧 DID 即完成撤销，不存在独立 tombstone。Invite 创建时只能从这个当前集合选择并绑定 `verification_id`；invite metadata 只记录选择结果，绝不成为授权来源。任何**未**落入该集合的 `verification_id` MUST NOT 被接受。`ak.invite.claim` 的 `binding_proof.verification_id` 不在当前集合内时，reducer 与接收 Station sync surface MUST 在所有接受 3PID claim 的路径上拒绝该 claim（对外仍按 §6 不可枚举响应处理）。该约束是可测试门槛：给定一份其 `verification_id` 不属于目标 Realm 当前显式授权集的 `ak.invite.claim`，符合规范的 reducer 与 Station sync surface必须拒绝其转换为 membership，且不得因 `subject_proof`（§4.3 step 5）有效而放行。
- **组织背书增强（informative）**：高安全 / audited / 企业 Realm MAY 在上述 MUST allowlist 之上叠加更强的验证服务可信度证明，例如要求验证服务 DID 由组织目录背书的 Verifiable Credential 声明、由 OIDC / SCIM 目录证明覆盖，或要求两个独立验证服务对同一 3PID 绑定各自签发见证 receipt（双服务见证），使任何单一验证服务的妥协都不足以独自完成 3PID 绑定。本条为增强建议，不改变上面 allowlist MUST 门槛对所有 Realm 的强制性。
- **二次确认通道（高安全 Realm，SHOULD / MUST）**：高安全 / audited / 企业 Realm SHOULD 要求一条独立于验证服务的二次确认通道（例如已在该 Realm 中的成员对 Bob 身份的带外确认、组织目录核对、或独立信道的人工 approval），使单一验证服务的妥协不足以让攻击者完成加入；声明该要求的高安全 Realm policy 中此条为 MUST。

## 3. 邀请流程

### 3.1 创建待定邀请 (Pending Invite)

当 Alice 想通过电子邮件 `bob@example.com` 邀请 Bob 加入 Realm 时：

1. **发起盲化邀请**：Alice 的客户端经 `ak.open.third_party_invite.command.provision.v1` 向她的 Station 或授权的 Identity Verification Service 提交一个针对 3PID 的邀请；该预配入口的完整合同见 §7.2。公开持久化 Event 中 MUST NOT 写入明文邮箱、手机号或可枚举的未加盐哈希。
2. **生成邀请令牌**：验证服务按所选模式生成随机 `invite_token`（offline_token 至少 128 bit 熵；lookup 见 §3.2），并生成独立 `token_salt`。`invite_token` MUST 只通过外部通知渠道发送给被邀请人，不得写入公开 Event。投递只在 §7.5 的回绑激活完成后进行。
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

### 3.1.1 两种模式的 commitment 与 token 字符空间（normative）

治理接纳与当前邀请权限由服务器按 [`server-trusted-results.md`](./server-trusted-results.md) 验证。
普通客户端消费自己 Station 的结果并核对请求与待签材料绑定，不收集或重放治理闭包。
独立 Identity Verification Service 属于服务验证角色，不能把调用者自报的成功当作已接受邀请；
完整 DID 的 method adapter 投影匹配仅检查标识绑定，不代替主体认证或历史授权。

`offline_token` 与 `lookup` 的公开 `third_party_invite` 都 MUST 携带 `token_commitment`，其固定算法为
`SHA-256(token_salt || UTF8(invite_token))`，输出 `sha256:<lowercase hex>`。`token_salt` MUST 是每邀请
独立生成的 256-bit 随机秘密，只留在验证服务；lookup 的 pepper/HMAC 索引不能替代这个 claim 绑定承诺。
lookup MUST 携带 `lookup_table_ref`、`pepper_id`，MUST NOT 携带 `token_salt_id`、`token_entropy_bits`；
offline_token MUST 携带 `token_salt_id`、`token_entropy_bits >= 128`，MUST NOT 携带 lookup 字段。
两种模式 MUST 使用同一公开 commitment 完成 present outcome、binding proof transcript 与 claim 的逐字匹配。

present 请求的 `invite_token` 接受去除展示分隔符后的 6..512 个 ASCII 字母、数字、`_` 或 `-`。
这只是两种模式共同的输入词法：服务 MUST 从已保存记录确定模式，不能由长度推断模式或降低 offline_token
的 128-bit 熵要求。lookup 短码 MUST 至少 6 位，继续执行 §3.2 的限速与三次失败失效规则。
`subject_did` MUST 是完整 method-native DID；验证服务 MUST 通过注册的 DID method adapter 检查其投影等于
`subject_account_id.principal_id`，MUST NOT 把 DidCoreId 字符串当作完整 DID 接受。

### 3.2 发送外部通知

身份验证服务通过传统渠道（SMTP 邮件、SMS）将包含链接的邀请发送给该 3PID。投递前置条件、投递意图持久化与可观察的投递状态见 §7.6。

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
> 1. **离线可校验形态**：与 URL `#token=` 等价，MUST ≥ 128-bit 真随机熵（即至少 26 个均匀随机 base32 字符或等价编码）。短分隔符（破折号）允许出现以方便用户录入，但不计入熵；编码字母表 MUST 排除易混字符（去掉 `0/O/1/I/L`），熵下限按剩余字母表大小重算。
> 2. **服务端 lookup 短码形态**：可以使用较短人类可读码（如示例 `XYZ-123-ABC`），但 MUST 全部满足：(a) 仅作为服务端私有 lookup 表的索引，原始 token bytes 不进入 claim，claim 仍须验证 §3.1.1 的公开 token_commitment；(b) 失败 claim 严格限速（每 IP / 设备 / 邀请者 同时 ≤ 5 次/分钟、≤ 50 次/天）；(c) 配合服务端 pepper / HMAC 存储，使短码无法离线枚举；(d) 短码 wire form 加入 `oob_code_kind="lookup"` 字段以便 wire-level 校验区分；(e) 同一短码命名空间下连续 3 次错误尝试 MUST invalidate 该 invite（强制邀请者重发）。
>
> 任何不能满足以上 (1) 或 (2) 全部条件的 OOB code 不得作为生产 wire 形态。conformance vector `ak.vector.invite.oob_code_entropy.v1` 覆盖短熵 OOB code claim 被拒、lookup 形态超限被 invalidate 两种情况。

**禁止形态**（验证服务的 token 出示端点 `ak.open.third_party_invite.command.present_token.v1`（§4.1）MUST 拒绝任何把 `invite_token` 放在请求 URL query string 或 path segment 中的请求，reason code 为 `third_party_invite_token_in_query`，且 SHOULD 立即作废该 token；这是端点在读取 body 之前对自己收到的 URL 做的判定，不依赖客户端自述来源。明文 token 不上 Event wire，reducer 只见 `token_commitment`（见 §4.2），因此该拒绝发生在出示端点而非 reducer）：

```text
forbidden: https://app.arkret.example/invite?token=<invite_token>&realm=ak:realm:...    token in query
forbidden: https://app.arkret.example/invite/<invite_token>                              token in path
```

邮件/SMS 内容不得包含 Realm 私密名称、成员列表、历史摘要或其他未授权预览。验证服务 MUST 在 SMTP 网关上启用 sender domain restriction (SPF/DKIM/DMARC) 以防 token-bearing link 被 phishing 重用。

## 4. 认领流程 (Claiming)

当 Bob 收到邮件并点击链接，他在客户端完成注册，持有完整 `did = did:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:bob.example.com`，其稳定业务身份为 `did_core_id = ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z`。接下来他需要认领这个邀请。

### 4.1 出示 Token 与绑定

Bob 的客户端通过 `ak.open.third_party_invite.command.present_token.v1`（`POST /_arkret/open/third-party-invites/present`，request body 为 [`invite.schema.json#/$defs/third_party_invite_present_request_body`](../../artifacts/schemas/invite.schema.json)）将 `invite_token`、intended `realm_id`、要绑定的 `subject_account_id`、用于独立验证的完整 `subject_did` 与客户端生成的 `claim_nonce` 提交给 Alice 的身份验证服务；token 只能在 JSON body 中出现（§3.2）。这是 v1 唯一的出示面：验证服务无论是 Station、组织 IVS 还是第三方服务，都 MUST 以该 operation 接收出示，客户端 MUST NOT 依赖私有端点。该 operation 只承担出示，MUST NOT 被当作 §7 私有材料生命周期的替代品；二者边界见 §7.8。
身份验证服务验证 token、过期时间、claim 次数和 Realm 绑定无误后，原子消费该 token，并使用之前预留的**临时私钥 (对应 3.1 节的 `verification_public_key`)** 签署一个**绑定证明 (Binding Proof)**，随 `invite_id` 与 `token_commitment` 一起返回（response 为 [`invite.schema.json#/$defs/third_party_invite_present_outcome`](../../artifacts/schemas/invite.schema.json)）；`binding_proof` 的形态是 [`event-payload.schema.json#/$defs/invite_claim_binding_proof`](../../artifacts/schemas/event-payload.schema.json)，与 §4.2 claim payload 中的 `binding_proof` 是同一个定义。Bob 对 `subject_account_id` 的控制权由 §4.2 的 `subject_proof` 证明，出示请求不另带设备证明。该证明声明：
“持有该 Token 的人现在对应的稳定业务身份是 `ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z`”。

**投递目标可审计（normative）**：由于验证服务是受信第三方（见 §2.1），其签发 `binding_proof` 时 MUST 在自身审计记录中记录该 token 在 §3.2 实际投递目标的 digest（例如 `delivery_target_digest = SHA-256(salt || canonical(3pid))`，使用与 `token_salt` 同级或独立的高熵 salt / pepper）。该 digest 不得写入公开持久化 Event（避免 3PID 枚举，与 §6 一致），但 MUST 进入验证服务的加密审计记录，使事后审计可以核对"该 token 是否被投递给 invite 声明的那个 3PID"。这样当验证服务被怀疑把 token 绑定到非声明 3PID（即把邀请重定向给攻击者）时，审计方可凭 invite 中声明的 3PID 重算 digest 与审计记录比对，检出该错配。

### 4.2 提交转换 Event

身份验证服务（或 Bob 代理）将该证明连同 Bob 的签名，打包成一个 `ak.invite.claim` Event 提交到 Realm。`payload` 为：

```json schema=schemas/event-payload.schema.json#/$defs/invite_claim_payload
{
  "invite_id": "ak:invite:AfVi-FmTYttG2uQeB67y7GdHhOrWGxBe0QaDAOwYnK01",
  "subject_account_id": {
    "principal_id": "ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
    "station_id": "ak:did_core:webvh:z6mkStation"
  },
  "token_commitment": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "claim_nonce": "01JX7Z5Q9Y4K2M8N6P3R1T0V",
  "binding_proof": {
    "verification_id": "ak:did_core:webvh:z6TrH1Ntf6QjaSBbShfKTrNbt",
    "verification_method": "did:webvh:z6TrH1Ntf6QjaSBbShfKTrNbt:identity.alice.example#invite-001",
    "subject_account_id": {
      "principal_id": "ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
      "station_id": "ak:did_core:webvh:z6mkStation"
    },
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

`utf8("ak.invite.claim.binding_proof.v1\n") || canonical_json({audience:"arkret.invite.claim", binding_proof: unsigned_binding_proof, claim_nonce, invite_digest, invite_id, realm_id, subject_account_id, token_commitment, verification_id})`

其中 `unsigned_binding_proof` 是去掉 `signature` 字段后的 `binding_proof` object；`verification_id` 等于 `binding_proof.verification_id`；`invite_digest` 是从该 `invite_id` 唯一对应、已被同一 Realm authority 接受的 `ak.invite.third_party` create Event 冻结材料计算的 canonical digest：对 `canonical_json({invite_id, realm_id, expires_at, third_party_invite})` 取 `sha256:<hex>`。Reducer MUST 在同一 accepted authority cut 联合核对 create Event/Commit、纯状态 `invite_lifecycle=pending` 与当前 Realm policy，并用 create Event 的 `third_party_invite.verification_public_key` / `verification_method` 校验该签名；任何依赖不全都失败关闭，不能从旧 `realm_invites` 行、caller 自报或 receiver 当前投影补齐。只验证 `binding_proof` 裸 object、或不绑定 `invite_id` / `token_commitment` / `invite_digest` / `claim_nonce` 的证明 MUST reject。

### 4.3 Realm reducer 状态机转换

`ak.invite.claim` 是 Realm 控制面 reducer input。Station sync surface、验证服务和客户端 MAY 在入站路径做格式、签名、限速和不可枚举预拒绝，但它们不得成为 invite state 的真源；是否把某个 `ak.invite.third_party` 从 `pending` 推进到 `claimed`、是否产生后续 membership proposal / accept 权限，只能由目标 Realm 的 reducer 在同一状态机中决定。任何 projection、缓存或服务端本地表若与 reducer 结果冲突，MUST 以 reducer 结果为准并回滚派生状态。

Reducer 处理 `ak.invite.claim` 时 MUST 按下列顺序 fail closed；所有内部 reason code 对外仍按 §6 不可枚举响应处理：

在线初检与 RealmCommit finality 是两个时点：接收站初检及 current governance Station intake MUST 在适用的
serializable gate 读取 current invite/policy 与 barrier，阻断新的无效 claim；通过本地 producer proof 与授权验证仍仅是
`control_pending`。以下 reducer 步骤在覆盖 claim 的 RealmCommit 内执行该命令之前的**确切安全前态**（包含本 RealmCommit 先前成功命令）上执行，并校验
claim 的签名 authority-commit basis 与该 view 的关系。实际执行/投票或独立审计的历史重放 MUST 使用同一确切安全前态，禁止读取 receiver 当前
invite/policy、当前终态或墙钟。初检之后、covering RealmCommit 之前已生效的 revoke/policy change 可以阻断该
RealmCommit 对 claim 的纳入；claim 已经合法 committed 之后的变更则不得追溯改判。

治理结果消费 Station可按 [authority_commit-profiles §9](../sync/authority-commit-log.md) 认证 exact claim 的 command/command_effect，不重算以下历史 reducer 判断；初始 producer/subject/binding 签名、当前新动作与最终成员确认不变。

1. 从该 covering RealmCommit 内该命令的确切安全前态，按 `invite_id` 读取唯一已接受的 `ak.invite.third_party` create Event/Commit，并与纯状态 `invite_lifecycle="pending"` 联合核对；`token_commitment` 必须等于该 create Event 的冻结公开字段；不匹配、不存在、不是 3PID invite 或该 view 中已是终态时 MUST reject，且不得创建 membership proposal。依赖闭包不全时 MUST `revision_unavailable` / pending，MUST NOT 用缓存、caller 旧 basis 或 receiver 当前投影替代该 view。
2. 在任何签名接受前重算过期前置条件。**判定时点是 canonical、签名覆盖的量，MUST NOT 使用 receiver 本地墙钟 `now`（normative）**：
   - 比较对象固定为该 `ak.invite.claim` Event 自身的签名 `created_at`（进入 canonical bytes 与 `event_digest`，对所有 receiver 唯一确定）与已接受 create Event 在该 claim authority-commit basis 上的 `expires_at`。`invite.expires_at <= claim_event.created_at` 时 MUST 以 `expired_invite_token` 拒绝本次 claim。
   - 若该 claim 已被 RealmCommit 覆盖，同一判定 MUST 得到相同结果；receiver MUST NOT 因为重放 / backfill 发生在更晚的本地时刻而改判。该命令还必须满足 authority-commit 对显式期限的可信存在时间区间检查，不能只靠作者回填 created_at 绕过过期。这遵守确认安全序列的确定性重放约束（[`../authz/event-auth-state-resolution.md` §8](../authz/event-auth-state-resolution.md)）。
   - **被拒绝的 claim MUST NOT 产生任何共享 projected write（normative）**：它不写 invite typed current result、不写 membership proposal、不推进任何 projection。invite 的 `pending -> expired` 是**独立的、已登记的、可签名且可被 RealmCommit 覆盖的 state-changing Event**（由授权 writer 提交的 `ak.invite.revoke`，携带 `reason_code` 表达 `expired`，见 [`../models/governance-objects.md` §5.3](../models/governance-objects.md)），MUST NOT 由被拒 claim 的处理路径顺带写出——那样的 transition 没有独立 accepted Event / event digest，无法被另一 receiver 从 canonical history 重放，等于把 receiver-local timer 提升成共享真相源。
   - reducer 在读到 invite typed current result 已处于 `expired` 或任一终态时，按 step 1 的终态规则拒绝。token material / lookup pepper 的 zeroize 规则见 §6.1；zeroize 是**服务端本地清理义务**，不是共享 typed current result 状态，MUST NOT 反过来充当 invite state 的真源。
3. 验证 `binding_proof` 必须由已接受 create Event 的 `third_party_invite.verification_public_key` 签署，签名输入 MUST 是 §4.2 定义的 `ak.invite.claim.binding_proof.v1` transcript，并绑定 `subject_account_id`、`realm_id`、audience、过期时间、claim nonce、`invite_id`、`token_commitment` 与上述 create Event 派生的 invite digest；`binding_proof.subject_account_id`、`binding_proof.realm_id`、`binding_proof.claim_nonce` 与 payload 顶层字段不一致时 MUST reject。binding proof 畸形、签名不可验证或未通过本节 policy 复校验时，内部审计 reason 为 `claim_invalid`（对外仍按 §6 不可枚举响应处理）。
4. 从同一冻结 predecessor view 的 `realm_policy_bundle` typed current result 读取 `allowed_third_party_invite_verification_ids`，复校验 `binding_proof.verification_id` 在该集合中；字段缺失或空数组都是 deny-all。已接受 create Event 冻结的验证服务 DID 必须与 binding proof 一致，但创建时允许的 DID 不能重新授权一个在该 view 已被移除的 DID。该复校验必须在 reducer 内执行，不得因在线初检或验证服务已检查而跳过；不在集合中即拒绝，subject proof 有效也不能放行。依赖不全时 fail closed，不得退回 caller 旧 basis，亦不得用 receiver 当前 policy 推翻历史 RealmCommit。
5. 验证 `subject_proof` 来自 `subject_account_id` 的当前有效 verification method，防止验证服务把 token 绑定到攻击者 DID。该签名 MUST 覆盖 canonical transcript `utf8("ak.invite.claim.subject_proof.v1\n") || canonical_json({subject_account_id, invite_id, realm_id, token_commitment, claim_nonce, audience:"arkret.invite.claim", verification_id, binding_proof_digest})`，其中 `verification_id` 等于 `binding_proof.verification_id`，`binding_proof_digest` 是 `binding_proof` 的 canonical-JSON digest（`sha256:<hex>`）。这确保 subject 证明的语义是"我同意被这个特定验证服务签发的这个特定 `binding_proof` 绑定"，而不是泛化的"我同意加入"；据此，攻击者或被替换的验证服务无法把另一份 binding_proof / 另一个验证服务身份套用到同一 subject signature 上。只验证裸 DID 控制权、或不绑定 `invite_id` / `realm_id` / `token_commitment` / `claim_nonce` / `verification_id` / `binding_proof_digest` 的 subject proof MUST reject；`verification_id` 与 `binding_proof.verification_id` 不一致、或 `binding_proof_digest` 与 `binding_proof` 实际 canonical digest 不一致时同样 MUST reject。
   **v1 subject method 边界（normative）**：本步“当前有效”指覆盖 claim 的 Realm authority cut 所对应的已认证 DID 历史，而不是 verifier 执行时的当前文档。历史 DID authority 调用点登记为 `ak.verifier.invite.claim_subject_at_commit.v1`（`accepted_at_history`，`freshness_profile_id=null`）。先按 subject Account 的 principal 取得并认证原生 DID 历史，投影的 core MUST 与 `subject_account_id.principal_id` 逐字相等；再按 [`identity-did.md` §3.4](../identity/identity-did.md) 选择直接声明的历史 method 或该历史 WebVH effective update key 的标准 did:key method。不得把后者的 bare did:key 投影当成 subject identity。若无法固定该历史状态或方法证据，MUST 以 `claim_invalid` 拒绝且零写入，不得退回 verifier 当前 DID head。`#ak:device:` PCR device method 即使当前有效、或与 Event producer 的 method 相同，也 MUST 以 `claim_invalid` 拒绝且零写入。不得用本地当前 PCR 查询、producer proof 或 caller 自报 key 补齐 subject 的历史授权。
   对仅携带 core 的远端 subject，可把 Event producer method 的标准 WebVH bare DID 作为不可信定位提示；提示必须独立通过完整历史与 SCID/core 检查；完整 Account 的 Station 绑定由已签 subject transcript 与已认证 Event producer Account pair 对齐验证。它不提供 subject authority，不得用该 PCR device key 或 producer signature 代替原生 root 控制证明；已有 accepted resolution 的已认证 locator 优先。
6. 在同一 authority 提交事务中，以候选 claim Event 对照已有 accepted claim Event 与可从 committed Event 重建的耐久派生索引，检查 `(invite_id, claim_nonce)` 与 `token_commitment` 两类一次性约束：同一 `(invite_id, claim_nonce)` 的重复 claim、或同一 `token_commitment` 已有 accepted claim projection，均 MUST 以 `duplicate_conflict` 拒绝。v1 base wire 中 `third_party_invite.max_claims` MUST 恒为 `1`；任何大于 `1` 或缺失后被解释为多用 token 的写入 MUST `schema_violation` / `duplicate_conflict` fail closed。该检查必须与 `invite_lifecycle` 的 `pending -> claimed` transition 原子提交，不能依赖入站服务的幂等表作为唯一保护。
7. 验证通过后，reducer MUST 在同一 authority 提交事务中接受唯一 `ak.invite.claim` Event/Commit、把 `invite_lifecycle` 从 `pending` 原子推进到 `claimed`，并更新可从该已接受 Event 重建的耐久派生索引。`claimed_by=subject_account_id`、`claim_event_ref`、`claim_nonce_digest`、`token_commitment`、`verification_id` 与 `claimed_at` 均从该 exact accepted claim Event 派生，不是 `invite_lifecycle` 的字段；随后该占位符邀请正式转变为针对 `subject_account_id` 的标准 `ak.invite.create` 或等价 membership proposal。`ak.invite.claim` 本身不直接绕过 Realm join policy 写入 `ak.member.state{membership="join"}`；最终 join 仍由 `subject_account_id` 通过 `ak.invite.accept` 或 profile 声明的等价 membership proposal 路径完成；reducer MUST 在同一 accepted authority cut 按 `invite_id` 解析唯一 accepted claim Event 的 exact ref 与 Commit，核对其 `subject_account_id` 与 accept/proposal 的 author 或 subject，不能仅凭 lifecycle 的 `claimed` 字符串放行。该核对不增添 accept payload 字段。

验证服务 / 接收 Station sync surface SHOULD 维护 `(invite_id, claim_nonce)` 去重 set，TTL 至少覆盖 `invite.expires_at + 24h`，用于在进入 reducer 仲裁前降低重放成本；该服务侧 set 不是状态真源。已接受 claim 的 nonce 由上述同事务唯一性永久约束；被拒 claim 不产生共享 projected write，服务侧对被拒 nonce 的重放缓存只是私有反滥用状态，不得冒充 canonical accepted claim。该 set 的 key SHOULD 存储为 HMAC / hash，不得持久化明文 invite token；对外失败形态仍按 §6 的不可枚举响应处理。

> **Conformance vector（normative）**：上述 reducer 闭环由 `ak.vector.invite.claim_reducer_state_machine.v1` 覆盖（登记于 `artifacts/registry/vector-registry.json`，fixture 位于 [`invite-claim-security-fixture.json`](../../artifacts/fixtures/invite-claim-security-fixture.json)）：正路径必须产生 `pending -> claimed` 与 membership proposal；token commitment mismatch、allowlist 复校验失败、claim nonce 重放、过期 claim 四类负路径均不得产生共享 projected write。过期终态须由独立 accepted `ak.invite.revoke` 推进。

**v1 base wire 范围（normative）**：v1 base conformance 仅支持 `invite` / `restricted` join-rule Realm 的 third-party claim 接续到 `ak.invite.create`（或等价 membership proposal）路径，如上述步骤 7 所述。v1 不定义独立 join-application/review 协议，因此 `knock_restricted` Realm 上的 third-party claim **不属于 v1 base conformance**，验证服务 MUST 以 `unsupported_join_rule` 拒绝。

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
- claim 成功后，外部 3PID 与 `subject_account_id` 的绑定默认只在邀请上下文内有效；不得自动发布为全局 handle、联系人或组织成员资格。

### 6.1 失败 / 异常清理状态机（normative）

第三方邀请的 wire 状态机覆盖正常路径之外的失败 / 邀请者状态变化 / token 泄漏。各 invite typed current result 状态转换由 reducer 强制：

| 触发条件 | 状态转换 | 行为 |
| --- | --- | --- |
| `expires_at` 已过（由授权 writer 观察并提交显式 Event） | `pending -> expired` | 该 transition MUST 由授权 writer 提交的显式 `ak.invite.revoke`（`reason_code` 表达 expired）承载，是可签名、可被 RealmCommit 覆盖的 state-changing Event；MUST NOT 由本地计时器或被拒 claim 的处理路径顺带写出（§4.3 step 2）。在该 Event 被接受之前，claim 仍按 §4.3 step 2 以签名 `created_at` 与 `expires_at` 比较后拒绝，判定对所有 receiver 与所有重放时点一致。服务端 MUST 在 24h 内 zeroize `token_salt` / lookup pepper material，并 GC active commitment 记录（本地清理义务，不是共享状态）。 |
| 邮件 / SMS 发送失败（gateway 5xx / bounce / DKIM fail） | `pending → send_failed` | 邀请者 UI MUST 显式提示发送失败；服务端 MUST NOT 假装成功；MAY 在 retry budget 内自动重试（建议 ≤ 3 次，指数退避）。**与 `expired` 同一承载形态**：retry 耗尽后的 `send_failed` transition MUST 由授权 writer 提交的显式 `ak.invite.revoke`（`target_state="send_failed"`，`reason` 表达投递失败原因）承载，是可签名、可被 RealmCommit 覆盖的 state-changing Event；MUST NOT 由投递重试循环或本地计时器顺带写出，投递失败本身只是该 writer 提交前的观察。`reason` 是唯一的失败原因载体，MUST NOT 另造 `send_failure_reason` 字段，且 MUST NOT 泄漏 3PID 明文、token 原文或验证码。服务端 MUST 在 24h 内 zeroize token material；邀请者 MAY 手动重发（产生新 `invite_id` + 新 token + 新 commitment）。`send_failed` 是终态方向：**MUST NOT 回到 `pending`**——重发是新 invite，不是旧 typed current result 复活。 |
| 邀请者失去 `ak.invite.third_party` capability（grant revoke、role change） | `pending → revoked_by_capability_loss` | 后续 claim MUST `capability_denied` 拒绝；commitment 立即从 active set 中移除，`token_salt` / lookup pepper material MUST 在 24h 内 zeroize。 |
| 邀请者主动离开 Realm（`ak.member.state` → `leave`/`ban`/`remove`） | `pending → revoked_by_inviter_left` | 同上 capability loss 处理；邀请不随邀请者继承到其他成员。 |
| token 泄漏 / 怀疑泄漏（邀请者或 admin 发起 `ak.invite.revoke`） | `pending → revoked` | 立即拒绝任何 claim；`token_salt` / lookup pepper material MUST 在 24h 内 zeroize；客户端 UI MUST 显示"邀请已撤销"。 |
| claim 成功 | `pending → claimed` | 同一 `token_commitment` 第二次 claim MUST `duplicate_conflict`；claim 接受后 `token_salt` / lookup pepper material MUST 在 24h 内 zeroize，只保留不可枚举 audit receipt。 |
| OOB lookup 形态失败次数超限（§3） | `pending → invalidated_by_rate_limit` | 强制邀请者重发；`token_salt` / lookup pepper material MUST 在 24h 内 zeroize；不暴露具体失败次数给攻击者。 |

**两个消费点的悬挂态（normative）**：第三方邀请有**两个不同信任域的消费点**，二者之间无强一致：§4.1 验证服务端**原子消费 token**（签发 `binding_proof` 后该 token 即用尽），与 §4.3 step 4 reducer 侧**原子标记 pending invite 为 `claimed`**。当 token 已在验证服务侧消费、但承载该 `binding_proof` 的 `ak.invite.claim` Event 投递失败、被 reducer 拒绝或进入 quarantine（reducer 侧 invite 仍停留在 `pending`）时，二者处于不一致的悬挂态。规范要求：

- 一旦验证服务消费了某 token 并签发了 `binding_proof`，该 token MUST 被验证服务视为**已用尽**，即使后续未观察到对应 `ak.invite.claim` 在 Realm 落地为 `claimed`。验证服务 MUST NOT 对同一 token 重新签发第二份指向不同 / 相同 subject 的 `binding_proof`。
- 因此 claim 在 reducer 侧未落地（被拒 / quarantine / 投递丢失）时，该 invite 不能仅靠重发原 token 恢复；与 §6.1 状态机一致，邀请者 MUST 通过重发**新 `invite_id` + 新 token + 新 commitment** 来重试（等同于 §6.1 `send_failed` / `revoked` 后的重发路径），不得复用已消费 token。
- 验证服务 MAY 为该已消费 token 保留一个**可恢复窗口**（仅用于把同一份已签发 `binding_proof` 幂等重投递给 Realm，例如网络瞬断后的重试），但该窗口 MUST 绑定同一 `(invite_id, claim_nonce, subject_account_id, binding_proof_digest)`，不得用于把 token 重新绑定到其它 subject；窗口耗尽后 MUST 按上一条要求邀请者重发新 invite。

> **Conformance vector（normative）**：上述"已消费 token 不得重绑到其他 subject"是防邀请重定向的关键安全不变量，由具名 conformance vector `ak.vector.invite.consumed_token_resubject_rejected.v1` 覆盖（登记于 `artifacts/registry/vector-registry.json`，向量数据见 `artifacts/fixtures/security-closure-fixture.json`），断言风格与既有 `ak.vector.invite.oob_code_entropy.v1`（§3）、`ak.vector.invite.failure_indistinguishable.v1`（§6.1）邀请向量对齐。该向量的意图：验证服务对**同一已消费 token**收到指向**不同 `subject_account_id`** 的第二次签发请求时 MUST 拒绝（不签发第二份 `binding_proof`）；仅当请求绑定同一 `(invite_id, claim_nonce, subject_account_id, binding_proof_digest)` 时才允许在可恢复窗口内幂等重投递同一份既有 `binding_proof`。向量同时断言：reducer 侧对承载已消费 token 重绑到不同 subject 的 `ak.invite.claim` Event MUST 以 `duplicate_conflict` 拒绝。

Claim 成功但 MLS Welcome / KeyPackage 派发尚未完成时，成员资格可以先进入 `claimed` / joined projection，但该成员对加密正文的客户端状态 MUST 走 [`client-sync.md` §15](./client-sync.md) 的 `decryption_pending` / timeout / recovery 机制；不得把 Welcome 缺失解释为 claim 回滚。KeyPackage 耗尽、过期或与 required capabilities 不匹配不得通过 claim 响应泄露远端库存状态；目标 endpoint 的客户端只按本地 inventory ledger、已观测的 claim/Welcome 生命周期与包自身 `expires_at` 执行 single-flight bounded refill。未观察 claim 在包自身到期前造成的临时库存缺口属于 [`device-lifecycle.md` §9](../crypto-media/device-lifecycle.md) 明确的不保证窗口，不得据此新增 owner inventory/终态通知或复活已领取包；新的 Welcome 到达后再按普通 MLS governance binding 校验恢复。

**统一不可枚举响应（normative）**：claim 失败响应 MUST NOT 区分上表 6 种失败触发（`claim 成功` 行不是失败触发）；对外仅返回统一 `not_found`（或同形态错误），让攻击者无法通过响应差异判断 token 是否存在、是否过期、是否被撤销、邀请者是否离开 Realm。具体 reason_code 仅写入服务端 audit log。这条规则覆盖 §6 的"失败响应不得泄露 token 是否存在"。`ak.vector.invite.failure_indistinguishable.v1` 覆盖这 6 种失败触发对外返回 byte-identical 响应（含 timing 类，差异 ≤ 50ms）。

## 7. 私有材料生命周期（normative）

### 7.1 生命周期与操作总览

§3.1 的分工要求验证服务自己生成并保管 `invite_token`、`token_salt` 或 lookup pepper 以及每邀请临时私钥，邀请者只签署公开字段。因此从制码到投递之间必须有一条完整的标准载体链：私有材料先被**预配**，邀请 Event 被 author 并按 Realm 规则**接受**，验证服务再凭受限**接受证据**把私有记录**回绑激活**到那一份 exact invite，然后才**投递**，并且任一阶段崩溃后都收敛到确定结果。

| 阶段 | 标准载体 | 边界 |
| --- | --- | --- |
| 预配 | `ak.open.third_party_invite.command.provision.v1` | 服务生成并保管秘密，只返回公开材料与 `provisioning_id`（§7.2） |
| author 与接受 | `ak.invite.third_party` Event 经 `ak.self.events.command.submit.v1` 摄取 | 复用非锚点 state-changing Event 接受流程，Invite ID 由该 Event 派生（§7.3） |
| 接受证据 | `ak.self.third_party_invite.read.acceptance_attestation.v1` | 自己 Station 签发用途受限、audience 绑定的接受证据（§7.4） |
| 回绑激活 | `ak.open.third_party_invite.command.activate.v1` | 把 exact invite 与私有记录一次性绑定并落地投递意图（§7.5） |
| 投递与观察 | `ak.open.third_party_invite.read.provisioning_status.v1` | 带外投递进度与生命周期读取面（§7.6） |
| 崩溃恢复 | 预配、激活与状态读取自身的幂等、清理与恢复规则 | 见 §7.7 |

验证服务无论是邀请者所在 Station、组织的 Identity Verification Service 还是 Realm policy 授权的第三方（§2），都 MUST 以这四个已登记 operation 承载该生命周期，MUST NOT 用私有 HTTP 面、实现内部接线或部署本地约定替代其中任何一段。同一部署内部 MAY 直接执行这些步骤，但内部接线 MUST NOT 被当作独立验证服务所需互操作合同的替身。

秘密方向是单向的：`invite_token`、`token_salt`、lookup pepper、每邀请临时私钥与私有投递目标 MUST 只存在于验证服务的私有状态与加密审计记录中。它们 MUST NOT 出现在任何 Realm Event、account-data typed current result、通知、`ServiceDescribe`、状态读取响应或普通日志中；邀请 Event author 得到的只有公开材料与不可枚举的 `provisioning_id`。反方向同样封闭：公开 `token_commitment` 与 `verification_public_key` 是单向承诺与公钥，MUST NOT 被用来推导、重建或"恢复"上述任何私有材料。

### 7.2 预配 provisioning（normative）

`ak.open.third_party_invite.command.provision.v1`（`POST /_arkret/open/third-party-invites/provision`，request body 为 [`invite.schema.json#/$defs/third_party_invite_provision_request_body`](../../artifacts/schemas/invite.schema.json)，response 为同文件的 `third_party_invite_provision_outcome`）是 v1 唯一的发行入口。

**认证与绑定**：请求 MUST 由发起邀请者签名，签名 transcript 为
`utf8("ak.third_party_invite_provision_request_proof.v1\n") || canonical_json({audience, context:"ak.third_party_invite_provision_request_proof.v1", created_at, domain, issuer, operation_id:"ak.open.third_party_invite.command.provision.v1", payload_digest, verification_method})`，其中 `issuer` 等于 `inviter_account_id`，`payload_digest` 是去掉 `signature` 后完整 request body 的 canonical-JSON digest，`audience` 等于 `verification_id`。验证服务 MUST 校验：`signature.verification_method` 是 `inviter_account_id.principal_id` 的当前有效 verification method；`audience` 等于本服务 DID；`created_at` 落在不超过 300 秒的新鲜窗口内；同一 `(issuer, payload_digest, created_at)` 只被接受一次。出示面的开放访问属性 MUST NOT 套用到本入口：没有可验证签名的请求一律不生成任何材料。

**服务侧生成**：验证服务 MUST 自己生成并持久化随机 `invite_token`、每邀请独立的 256-bit `token_salt`（`lookup` 模式另加受限速的 pepper/HMAC 索引）、每邀请临时签名密钥对，以及私有投递目标与其 §4.1 的 `delivery_target_digest`。返回给 author 的 MUST 只包含可逐字放入 `ak.invite.third_party` payload 的公开 `third_party_invite` 对象、经 §6 上限钳制后的实际 `expires_at`、`activation_expires_at` 与不可枚举的 `provisioning_id`。响应 MUST NOT 包含 token、salt、pepper、临时私钥或 `delivery_target_uri`。

**预配不是授权**：预配阶段尚未形成 Realm Invite。验证服务 MUST NOT 声称存在 pending Invite，MUST NOT 分配 `invite_id`，MUST NOT 投递任何可兑换材料，也 MUST NOT 因为预配成功就接受后续出示。`provisioning_id` 只寻址私有记录，MUST NOT 进入公开 Event，MUST NOT 被解释成邀请权限或激活授权。当前邀请权限与验证服务 allowlist 的判定归 §7.5 的接受证据与 §4.3 的 reducer 复校验；本入口只执行认证、模式支持与反滥用检查。

**反滥用**：验证服务 MUST 按 `(inviter_account_id, realm_id, source_ip_bucket)` 限速并计量未激活预配的并发数量，超限时返回 `rate_limited` 或 `quota_exceeded`。请求的 `oob_code_kind` 或投递方案不被实现时 MUST 返回 `unsupported_feature`，MUST NOT 静默降级为另一种模式或另一条投递渠道。所有失败响应 MUST NOT 泄露其它邀请者、Realm 或 3PID 是否存在。

### 7.3 author 与接受（normative）

邀请者 MUST 把预配返回的 `third_party_invite` 与 `expires_at` 逐字放入 `ak.invite.third_party` payload，经 `ak.self.events.command.submit.v1` 提交，并按非锚点 state-changing Event 规则等待 Realm 接受。Invite ID 沿用创建 Event 派生规则（见 [`../models/governance-objects.md` §5.3](../models/governance-objects.md)），MUST NOT 在预配阶段另造，也 MUST NOT 由验证服务代签用户 Event。

对公开材料的任何编辑都会使该 invite 不可激活：验证服务在 §7.5 逐成员比对预配记录与 Station 签名 attestation 中由已接受 create Event 锁定的材料，不采纳后来呈报的值去覆盖自己冻结的材料。若 Event 被拒绝或被放弃，邀请者 MUST 重新预配并 author 新 invite（新 `invite_id`、新 token、新 commitment），MUST NOT 复用旧 `provisioning_id`。

### 7.4 接受证据 acceptance attestation（normative）

自己 Station 是治理接纳与当前权限的验证方（[`server-trusted-results.md` §1](./server-trusted-results.md)）。`ak.self.third_party_invite.read.acceptance_attestation.v1`（`POST /_arkret/self/third-party-invites/acceptance-attestation`）把该验证结果表达为一份用途受限、可移植的签名对象 [`invite.schema.json#/$defs/third_party_invite_acceptance_attestation`](../../artifacts/schemas/invite.schema.json)。

Station 在签发前 MUST 在同一 current accepted serializable gate 中确认：调用会话的完整 AccountId 就是该 `ak.invite.third_party` create Event 的 author；同 cut 已验 create Event/Commit 且纯状态 `invite_lifecycle` 处于 `pending`；请求的 `verification_id` 与该已接受 create Event 的冻结 `third_party_invite.verification_id` 一致且仍在当前 `allowed_third_party_invite_verification_ids` 集合内（§2.1）。任一条不成立时，不可见、非本人 author 与非 pending 统一返回 §6 的 `not_found`；无法证明 current checkpoint 完整时返回 `revision_unavailable`，MUST NOT 用陈旧 basis 签发。

签名 transcript 为
`utf8("ak.third_party_invite_acceptance_attestation_proof.v1\n") || canonical_json({audience, context:"ak.third_party_invite_acceptance_attestation_proof.v1", created_at, domain, issuer, operation_id:"ak.self.third_party_invite.read.acceptance_attestation.v1", payload_digest, verification_method})`，其中 `issuer` 等于 `station_id`，`payload_digest` 是去掉 `signature` 后完整 attestation 对象的 canonical-JSON digest。

该对象 MUST 同时绑定 `station_id`、`verification_id`、`realm_id`、`invite_id`、`inviter_account_id`、`provisioning_id`、exact 公开 `third_party_invite`、`invite_expires_at`、`invite_state`、`accepted_commit_id`、`observed_at` 与自身 `expires_at`；`signature.audience` MUST 逐字等于 `verification_id`。用途分离由已登记签名 context 承担：在其它 object family 的 context 下签出的签名在此 MUST NOT 通过验证，因此不另设常量用途字段。`expires_at` 由签发 Station 的 attestation service policy 选择，MUST 不早于 `observed_at` 且 MUST NOT 晚于 `invite_expires_at`；后续 revoke 阻断新 attestation，不追溯改写已签 attestation 的显式有效期。它只授权激活其中命名的那一份预配记录：MUST NOT 被解释为治理读取权、成员枚举权或对其它 invite、Realm、验证服务的授权。Station 自任验证服务时同样按本节判定并复用本地已验证状态，但 MUST NOT 因为同进程就跳过上述绑定。

调用方 MUST 只把该对象原样交给 §7.5 的激活请求，MUST NOT 修改任何成员，也 MUST NOT 自行重算或替换 `invite_digest`。

### 7.5 回绑激活 activation（normative）

`ak.open.third_party_invite.command.activate.v1`（`POST /_arkret/open/third-party-invites/activate`，request body 为 [`invite.schema.json#/$defs/third_party_invite_activation_request_body`](../../artifacts/schemas/invite.schema.json)）把一份预配记录唯一绑定到一份已接受 invite。

验证服务 MUST 按下列顺序 fail closed：

1. 解析 `provisioning_id`；未知句柄、属于其它邀请者的句柄与已删除记录统一返回 `not_found`。
2. 校验 `provisioning_id` 等于 `acceptance_attestation.provisioning_id`；不等时返回 `not_found`。
3. 解析 `station_id` 并验证 attestation 签名。服务 DID 与其当前签名密钥经 `ak.open.service.read.resolution.v1` 取得，`signature.verification_method` MUST 投影到 `station_id`。签名不可验证、签名 context 不是 `ak.third_party_invite_acceptance_attestation_proof.v1`、`signature.audience` 或 `verification_id` 不是本服务，或 `invite_state` 不是 `pending` 时，内部审计原因为 `third_party_invite_acceptance_missing`。
4. 校验显式有效期：attestation 的 `expires_at` MUST 尚未到达，且 `observed_at` 不得晚于 `expires_at`，`expires_at` 也不得晚于 `invite_expires_at`。独立验证服务仅按这些签名字段判定；不满足时内部审计原因为 `third_party_invite_acceptance_stale`，MUST NOT 用过期 attestation 落地绑定。
5. 校验 `activation_expires_at` 未过；已过时记录进入 `expired`，内部审计原因为 `third_party_invite_provisioning_expired`。
6. 逐成员比对：attestation 的 `realm_id`、`inviter_account_id`、`invite_expires_at` 与完整 `third_party_invite` 对象 MUST 与预配时冻结的记录逐字相等，内部审计原因为 `third_party_invite_material_mismatch`。服务 MUST NOT 采纳后来呈报的值去覆盖冻结材料。
7. 按 §4.2 从已验签 attestation 中由 Station 同 cut 已接受 create Event 锁定的材料重算 `invite_digest`，计算对象为 `canonical_json({invite_id, realm_id, expires_at, third_party_invite})`，其中 `expires_at` 取 attestation 的 `invite_expires_at`。调用方自报的 digest MUST NOT 被接受。
8. 原子提交唯一绑定与投递意图，并返回首次 `activated_at`。同一预配记录 MUST 只绑定一份 invite：指向不同 `invite_id`、`realm_id` 或 author 的第二份 attestation MUST 以 `duplicate_conflict` 拒绝，内部审计原因为 `third_party_invite_provisioning_already_bound`，且 MUST NOT 换绑、换密钥或重发 token。

仅有 Event 哈希、Event 签名、HTTP 成功或调用者自报的 `invite_id` 与 `invite_digest` MUST NOT 代替接受证据。验证服务 MUST NOT 为激活要求任意治理读取权，也 MUST NOT 临时增加未登记 HTTP 接口。

第 3 至第 7 步的细分原因只对已经用可验证 attestation 寻址到一份存在的预配记录的调用方可见；其余一切失败保持 §6 的统一不可枚举形态。激活成功本身不改变 Realm invite typed current result：typed current result 仍停留在 `pending`，直到 §4.3 的 claim 或授权 writer 的 `ak.invite.revoke` 推进它。

### 7.6 投递与状态观察（normative）

只有 `provisioning_state` 为 `activated` 时才允许按 §3.2 投递。投递意图 MUST 与绑定同事务持久化，因此进程重启后投递循环可以恢复；恢复只投递同一份有效邀请，MUST NOT 生成第二份 token 或第二份可兑换材料。外部邮件或短信网关可能重复送达，实现 MUST NOT 声称外部渠道恰好送达一次。

`ak.open.third_party_invite.read.provisioning_status.v1`（`POST /_arkret/open/third-party-invites/status`）是 v1 唯一的生命周期与投递观察面。`provisioning_id` 是全部查询凭证，MUST 只出现在 JSON body。响应 MUST NOT 携带 token、salt、pepper、临时私钥、`delivery_target_uri` 或任何 3PID 派生值，也 MUST NOT 透露被邀请人是否已打开邀请。未知句柄、属于其它邀请者的句柄与已删除记录 MUST 不可区分。

`delivery_state` 为 `failed` 只表示服务已耗尽重试预算。Realm 可见的状态迁移仍按 §6.1 由授权 writer 提交携 `target_state="send_failed"` 的 `ak.invite.revoke` 承载；验证服务的私有投递循环 MUST NOT 直接改写 Realm invite typed current result。已激活邀请被撤销、过期、邀请者失权或退出时，记录 MUST 进入 `revoked` 并停止投递与出示，材料清理沿用 §6.1。

### 7.7 崩溃恢复、幂等与清理（normative）

- **预配响应丢失**：同一认证主体、同一 `request_id` 与逐字相同的 canonical 意图 MUST 返回原公开材料与原 `provisioning_id`；同一 `request_id` 换目标、Realm、`verification_id`、模式或有效期 MUST 以 `duplicate_conflict` 拒绝，MUST NOT 生成第二套材料。
- **Event 被拒、放弃或长期未接受**：预配记录在 `activation_expires_at` 之后 MUST 进入 `expired`，按 §6.1 在 24h 内 zeroize token 与 pepper 材料并从 active commitment 索引中移除。过期记录 MUST NOT 复活；其 `request_id` 在记录保留期内继续按上一条判定，保留期结束后同一 `request_id` MUST 被拒绝而不是静默铸造新材料。
- **激活响应丢失、并发调用或进程重启**：绑定与投递意图持久化后，逐字相同的重试、并发重复请求与重启后重试 MUST 返回同一份 `third_party_invite_activation_outcome`，包含首次 `activated_at`。
- **崩溃点**：在铸造材料与持久化预配记录之间崩溃时，调用方按 `request_id` 重试；服务 MUST 要么恢复出同一条记录，要么当作从未发生并铸造一次且仅一次的新材料，MUST NOT 留下无法寻址却仍可出示的孤儿材料。在持久化绑定与写入投递意图之间崩溃时，恢复后 MUST 先补齐投递意图再投递。
- **状态读取是恢复入口**：调用方在任一响应丢失后 MUST 先读 §7.6 的状态，再决定重试预配还是重试激活；MUST NOT 直接重新预配来"修复"一份已激活的记录。
- **清理**：终态（`consumed`、`expired`、`revoked`）后的 token、salt、pepper 与临时私钥 MUST 在 24h 内 zeroize，只保留不可枚举的加密审计记录。zeroize 是服务端本地清理义务，MUST NOT 反过来充当 Realm invite state 的真源（§4.3 step 2）。

> **Conformance vector（normative）**：§7.2、§7.5 与 §7.7 的预配幂等、接受证据判定、唯一回绑与崩溃恢复由 `ak.vector.invite.provisioning_activation_binding.v1` 覆盖（登记于 `artifacts/registry/vector-registry.json`，fixture 位于 `artifacts/fixtures/service-closure-hardening-fixture.json`）。

### 7.8 与 present 的边界与 bundle 广告（normative）

§4.1 的 `ak.open.third_party_invite.command.present_token.v1` 只承担**出示**：被邀请人用带外取得的 `invite_token` 换取一份 `binding_proof`。它 MUST NOT 被解释成私有材料生命周期的替代品——它不生成材料、不绑定 invite、不承载投递，也无法在没有 §7.2 与 §7.5 的情况下产生可验的 `binding_proof`：签发 `binding_proof` 需要的临时私钥与 token 记录只由预配生成、只由激活绑定到 exact invite。反过来，§7 登记的四个 operation MUST NOT 签发 `binding_proof`、消费 token 或接受被邀请人出示；出示的原子消费、可恢复窗口与不可重绑规则完全由 §6.1 决定。

部署 MUST 只在同时满足下列全部条件时，才在 `ServiceDescribe.supported_operation_bundles` 中广告 `ak.operation_bundle.station.third_party_invite_handoff.v1`：

- 该 bundle 登记的每一个 member operation 都在其已登记路径上真实可用；
- 存在一条完整闭环，从 `ak.open.third_party_invite.command.provision.v1` 开始，经 author 与接受、`ak.self.third_party_invite.read.acceptance_attestation.v1`、`ak.open.third_party_invite.command.activate.v1`、真实带外投递，直到 `ak.open.third_party_invite.command.present_token.v1` 成功签发 `binding_proof`，全程只使用已登记 operation；
- `offline_token` 与 `lookup` 两种模式各自跑通该闭环。

下列做法 MUST NOT 被计入上述条件，且其存在本身不构成对该 bundle 的支持：实现私有 HTTP 面或 `/_arkret/_conformance/*` 端点；直接向数据库或密钥库灌入 token、salt、pepper 或临时私钥；只在测试构建中存在的成功分支；以及任何绕过 §7.5 接受证据判定的捷径。路由存在、负例通过或 schema 校验通过都不足以广告该 bundle。
