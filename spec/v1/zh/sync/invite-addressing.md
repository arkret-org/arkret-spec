---
title: Invite Addressing and Principal Locator
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - service-http-binding.md
  - third-party-invites.md
  - ../identity/identity-handles.md
  - ../governance/member-delivery-binding.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 模型

Realm invite 的基础寻址模型是：

```text
invite_delivery = invite_address + introduction_evidence
```

base v1 invite **MUST NOT** 依赖 `ck.find.directory.query.resolve_handle(intent="invite" | "member_add")` 才能投递。Handle 是人类可读入口，不是邀请投递授权；实现不得把猜到的 `<localpart>:<domain>` 字符串自动升级成可投递邀请。用户 MAY 显式发布 handle 并允许 verified handle 作为 first-contact / invite 入口，但接收方仍必须把解析结果归约为 `subject_id`、可验证 handle claim 与 `invite_receive_policy` 判定。

邀请目标的规范输入是显式 `invite_address`：

```json
{
  "subject_id": "did:webvh:z2dmjBobExample:users.bob.example:bob",
  "recipient_service_did": "did:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc:ps.bob.example"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `subject_id` | DID | MUST | 被邀请的 principal / holder DID。v1 core 默认使用 `did:webvh`；`did:web` 仅在 `personal_node` deployment profile 或其它显式 method policy 允许时可作为 principal DID。 |
| `recipient_service_did` | DID | MUST | 接收 invite delivery 的 Principal Server service DID。 |
| `recipient_service_type` | const | MAY | 若出现，MUST 等于 `principal_server`；默认省略。 |

`recipient_service_did` 在 v1 中只表示 Principal Server。它 **MUST NOT** 指向 notary、shared Sync Service、push gateway、Directory 或任意第三方服务。将来如果需要组织、群组或其它接收服务形态，必须定义独立 locator / delivery schema，不得把 `recipient_service_type` 扩成宽枚举后复用本 schema。

## 2. Introduction Evidence

每个私有 invite delivery request **MUST** 携带 `introduction_evidence`，说明邀请方为什么可以尝试联系被邀请方。schema 见 [`invite-delivery-request.schema.json`](../../artifacts/schemas/invite-delivery-request.schema.json)。

| `kind` | 信任强度 | 说明 |
| --- | --- | --- |
| `locator_ref` | 高 | 被邀请方主动生成 / 交付的在线 locator ref。默认推荐。 |
| `consent_grant` | 高 | 邀请者出示被邀请方主动签发给邀请者的 `ck.consent.grant`(scope `invite` 或 `any`)的 `consent_grant_ref`。信任来源与 `locator_ref` 同构:都是被邀请方主动交付给邀请者的授权材料。已是联系人(互授 invite consent)拉群走此 kind,**无需 locator URL**。 |
| `shared_realm` | 中 | 邀请者与被邀请者已经同在某个 Realm；接收方按本地 policy 判断该 Realm 是否可信。 |
| `handle_claim` | 发现信任 | 邀请者通过 verified handle claim 找到 `subject_id`。它证明 holder 或受信 issuer 将某 handle 披露为可解析入口，但**不**证明 holder 已同意该邀请者联系自己。默认 SHOULD quarantine 或 drop；只有 subject policy 与部署约束都允许时才可 notify。 |
| `same_principal_server` | 中 / 部署相关 | 双方由同一个 Principal Server 承载；适合组织或个人同域场景。 |
| `explicit_address` | 弱 | 邀请者只提供 `subject_id + recipient_service_did`；等价于“我知道或猜测这个地址”。默认 SHOULD quarantine 或 drop。 |

`explicit_address` 是合法但最低信任 evidence。接收方 **MUST NOT** 因为请求格式正确就通知用户；必须先应用 subject 私有 `invite_receive_policy`。

引入信任分档(normative):**高信任档** = `{locator_ref, consent_grant, shared_realm}`;**发现信任档** = `{handle_claim}`;**低信任档** = `{same_principal_server, explicit_address, 无 / 非法 evidence}`。该分档同时决定 §5 的分级披露行为。

`consent_grant` evidence 的接收方验证:`consent_grant_ref` 指向的 `ck.consent.grant` 在被邀请方(`invite_address.subject_id`)的 consent cell 中仍是 active grant dot，且 `peer == inviter`、`consent_scope ∈ {invite, any}`、未过期未撤销。验证通过即按高信任处理。`consent_grant_ref` 校验失败时，接收方 MUST 降级按 `explicit_address`(低信任)处理，MUST NOT 因为携带了 evidence 字段就放行。

`handle_claim` evidence 的接收方验证: `handle_claim.handle == evidence.handle`，`handle_claim.subject == invite_address.subject_id`，`binding_state=verified`，`expires_at` 未过期，`proofs[]` 有效，issuer / Directory / visibility / audience 满足 subject policy 与部署约束。若 handle claim 携带 `member_delivery_binding`，还 MUST 校验 `handle_claim.member_delivery_binding.recipient_service_did == invite_address.recipient_service_did`；若 evidence 携带 `member_delivery_binding_candidate`，还 MUST 校验 `candidate.subject_id == invite_address.subject_id`、`candidate.handle == evidence.handle`、`candidate.member_delivery_binding.recipient_service_did == invite_address.recipient_service_did`、`candidate.intent == "invite"`、`audience` 匹配当前邀请上下文且 proof 有效。任何校验失败 MUST 降级按 `explicit_address` 处理，MUST NOT 因为 handle 字符串可解析就通知用户。

## 3. 在线 Principal Locator

二维码 / 链接默认承载在线 locator ref，不承载完整 signed locator。

推荐 QR / link 文本：

```text
https://ps.bob.example/_arkret/open/invite-locators/resolve#token=<locator_token>
```

扫描方客户端读取 fragment 后，向同一 origin 提交：

```text
POST /_arkret/open/invite-locators/resolve
```

body：

```json
{
  "locator_token": "base64url-token-with-at-least-128-bit-entropy"
}
```

`locator_token` **MUST** 只通过 JSON body 或等价 signed proof 提交，**MUST NOT** 出现在 URL path、query string、Referer、普通 access log、analytics、crash report、local storage 或浏览器历史中。客户端读取 fragment 后 **MUST** 清理地址栏与本地临时状态。

token 要求：

- `locator_token` SHOULD 是不透明 server-side handle；服务端私有状态保存 `subject_id`、`recipient_service_did`、TTL、撤销状态与接收策略。
- `locator_token` MUST 至少 128 bit 熵；base64url 无 padding 编码时 128 bit 约为 22 字符，192 bit 为 32 字符。高安全部署 SHOULD 使用 192 bit 或更高，但 128 bit 已满足 v1 floor。
- `locator_token` MUST NOT 是明文可解码的 `base64url(JSON)`，也不得在 token 明文中携带 `subject_id`、`recipient_service_did`、`expires_at`、策略状态或其它可识别 invitee 的材料。若部署需要 stateless token，payload MUST 先做 authenticated encryption；调用方仍只把它当 opaque bearer secret。
- token MUST be unguessable、可撤销、可设置短 TTL，并 MAY 设置一次性使用。
- endpoint 对不存在、过期、撤销、策略拒绝的对外响应 MUST byte-identical 或等价不可区分（含 status / body / headers）；timing 侧信道按 [`conformance/conformance-vectors.md`](../conformance/conformance-vectors.md) `ck.vector.invite.failure_indistinguishable.v1`（§9.7）收口（timing 差异 SHOULD ≤ 50ms，高安全 profile MUST 用 jitter / padding）。仅服务端 audit log MAY 记录具体 reason_code。
- endpoint 返回体 MUST 是签名 `principal_locator`；调用方不能只信任 HTTPS URL。

## 4. `principal_locator`

`principal_locator` 是被邀请方 Principal Server 返回的、可验证的 invite address assertion。schema id 为 `ck.schema.principal_locator.v1`。

最小形态：

```json
{
  "schema": "ck.schema.principal_locator.v1",
  "subject_id": "did:webvh:z2dmjBobExample:users.bob.example:bob",
  "recipient_service_did": "did:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc:ps.bob.example",
  "issued_at": "2026-06-07T10:00:00Z",
  "expires_at": "2026-06-07T10:15:00Z",
  "locator_ref_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "proofs": [
    {
      "proof_purpose": "recipient_service_acceptance",
      "proof": {
        "kind": "detached_jws",
        "verification_method": "did:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc:ps.bob.example#server-key-1",
        "alg": "EdDSA",
        "payload_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "created_at": "2026-06-07T10:00:00Z",
        "jws": "..."
      }
    }
  ]
}
```

验证规则：

1. `subject_id` 是被邀请主体；`recipient_service_did` 是接收 invite delivery 的 Principal Server service DID。
2. `recipient_service_type` 若出现 MUST 等于 `principal_server`。
3. `locator_ref_digest` 绑定私有 locator ref material；raw token 不得写入 Realm durable event。
4. `proof.payload_digest` MUST 覆盖 `canonical_json(principal_locator_without_proofs)`。
5. `proofs[]` MUST 至少包含 `recipient_service_acceptance`；高安全 / audited / enterprise 部署 SHOULD 同时要求 `subject_locator_authorization`。
6. 若缺少 `subject_locator_authorization`，verifier MUST 通过 DID Document、account binding 或 service delegation 证明 `recipient_service_did` 有权代表 `subject_id` 发布 locator。

`principal_locator` 不是 membership grant、不是 invite accept proof、不是 `member_delivery_binding`。它只证明“可以把这次邀请投递给这个 Principal Server 处理”。

## 5. 接收策略

被邀请方 Principal Server 按 subject 私有 `invite_receive_policy` 决定哪些 evidence 可以通知用户。schema id 为 `ck.schema.invite_receive_policy.v1`。

```json
{
  "schema": "ck.schema.invite_receive_policy.v1",
  "subject_id": "did:webvh:z2dmjBobExample:users.bob.example:bob",
  "allowed_introduction_kinds": [
    "locator_ref",
    "consent_grant",
    "shared_realm",
    "handle_claim",
    "same_principal_server"
  ],
  "handle_claim_behavior": "quarantine",
  "explicit_address_behavior": "quarantine",
  "unknown_invites": "drop",
  "allowed_handle_domains": [
    "bob.example"
  ],
  "trusted_handle_issuers": [],
  "trusted_directory_services": [],
  "trusted_realm_ids": [],
  "trusted_principal_services": [],
  "blocked_principal_services": [],
  "blocked_subjects": [],
  "disclosure": {
    "high_trust": "outcome",
    "discovery_trust": "opaque",
    "low_trust": "opaque"
  }
}
```

规则：

- **缺省 policy（subject 未发布 `invite_receive_policy` 时）MUST fail closed（normative）**：接收方 MUST 采用保守默认——`allowed_introduction_kinds` 仅含**高信任档** `{locator_ref, consent_grant, shared_realm}`;**发现信任档** `{handle_claim}` 与**低信任档** `{same_principal_server, explicit_address}` 默认 `quarantine`（SHOULD）或 `drop`，MUST NOT 仅凭 evidence 格式正确就触发用户通知。上方示例把 `handle_claim` 与 `same_principal_server` 列入 allowlist，是 subject / 部署的显式可达性配置，**不是协议默认**;`same_principal_server` 与 `explicit_address` 同属低信任档（§2），默认处置对称——不得让"同一 Principal Server 上的任意账户"仅凭同域承载即向同域任意 subject 发起会触发通知的邀请（同域无授权骚扰开口）。
- `allowed_introduction_kinds` 是 allowlist；未列出的 evidence MUST NOT 触发用户通知。`consent_grant` 是受推荐的高信任 kind:把它加入 allowlist 即允许"已互授 invite consent 的联系人"直接邀请，而无需 locator URL。
- `handle_claim_behavior` 取值为 `drop | quarantine | notify`；省略时 MUST 视为 `quarantine`。把 `handle_claim` 配为 `notify` 表示 holder 显式希望别人可通过已发布 handle 发起邀请通知；该选择仍受 §5.2 部署约束限制。实现 MUST NOT 把任何 connection identifier、未 verified handle、过期/revoked handle claim 或未授权 restricted handle 当成 `handle_claim` evidence。
- `explicit_address_behavior` 取值为 `drop | quarantine | notify`；默认 SHOULD 是 `quarantine` 或 `drop`。把低信任档 evidence（`same_principal_server` / `explicit_address`）配为 `notify` 是部署对该档的显式放宽，MUST 经部署有意配置，不得作为缺省。
- `blocked_handle_domains` 先于 allowlist 生效，命中时 MUST 按策略拒绝处理。`allowed_handle_domains` 若非空，`handle_claim.handle` 的 domain MUST 是列表中的 canonical IDNA A-label 精确域名；子域名不自动继承，必须显式列出。`trusted_handle_issuers` / `trusted_directory_services` 若非空，issuer 或 `resolved_by` MUST 命中对应 allowlist。
- `unknown_invites` 取值为 `drop | quarantine`；无 evidence 或不合规 evidence 不得默认 notify。
- `blocked_subjects` 是按 peer subject DID 的黑名单(对等 `blocked_principal_services` 的服务粒度)。inviter 命中时，delivery MUST `drop`，且 §5.1 披露 MUST 强制为 `opaque`，以免黑名单经回包侧信道泄露。
- policy 是 subject/private state，不得写入目标 Realm event log。

### 5.1 分级披露(graded disclosure，normative)

`invite_receive_policy.disclosure` 决定 delivery outcome 回送给邀请者的结果粒度，按 §2 引入信任分档区分:

- `disclosure.high_trust`(默认 `outcome`):作用于高信任档 `{locator_ref, consent_grant, shared_realm}`。
- `disclosure.discovery_trust`(默认 `opaque`):作用于发现信任档 `{handle_claim}`。
- `disclosure.low_trust`(默认 `opaque`):作用于低信任档 `{same_principal_server, explicit_address, 无 / 非法 evidence}`。

`disclosure_level` 语义:

- `opaque`:`invite_delivery_outcome` 只返回 generic `status`(`accepted | duplicate | deferred`),MUST NOT 携带 `disclosed_outcome`，且对 exists / not-exists / quarantine / drop 各情形不可区分。这是反枚举 / 反侧信道的默认。
- `outcome`:`invite_delivery_outcome` MAY 携带 `disclosed_outcome`(`delivered | blocked | quarantined`)，把真实处理结果告知邀请者。

设计意图:对**已建立信任的来源**(已互授 invite consent 的联系人、对方主动给的 locator、已同在 Realm)，邀请失败能给邀请者明确反馈，避免"联系人加不进却不知为何"的 UX 黑洞；对**可发现但未建立关系的来源**(handle_claim)与**陌生人**(explicit_address)默认保持不可区分。`blocked_subjects` 命中者无论 disclosure 设置一律 `opaque`。`disclosure` 整体省略时按默认 `high_trust=outcome / discovery_trust=opaque / low_trust=opaque`。

### 5.2 部署接收约束（normative）

Principal Server MAY 发布部署 / 管理员级 `receive_policy_constraints`。该对象是 subject 私有 `invite_receive_policy` 的**上限**，不是默认放宽项。有效接收策略按交集计算：

```text
effective_receive_policy =
  subject invite_receive_policy
  ∩ Principal Server receive_policy_constraints
  ∩ applicable organization / realm policy constraints
```

约束规则：

- 部署约束只能让 subject 更不容易被联系，MUST NOT 把 subject 从更隐私的设置强制放宽为可通知。若 subject 选择 `drop`，管理员不能通过约束把结果提升为 `quarantine` 或 `notify`。
- `permitted_introduction_kinds` 与 `forbidden_introduction_kinds` 先于 subject allowlist 生效；任一约束拒绝的 evidence kind MUST 按 `drop` 或 indistinguishable policy denial 处理。
- 行为强度排序为 `drop < quarantine < notify`。`handle_claim_max_behavior`、`explicit_address_max_behavior` 与 `unknown_invites_max_behavior` 是上限；effective behavior 取 subject 行为与上限中更严格者。
- `disclosure_max` 是部署 / 管理员对 §5.1 分级披露粒度的上限，按 §2 引入信任分档给出 `{high_trust_max, discovery_trust_max, low_trust_max}`，取值同 `disclosure_level` 枚举（`opaque < outcome`，opaque 更保守）。字段或某档省略表示该档不设部署级披露上限。**effective disclosure 取 subject `invite_receive_policy.disclosure` 与 `disclosure_max` 中更保守（更接近 `opaque`）者**，使部署可以把 subject 自愿设为 `outcome` 的披露强制收紧为 `opaque`（反枚举 / 反侧信道），但 MUST NOT 把 subject 设为 `opaque` 的披露放宽为 `outcome`。该交集与上面的行为交集独立计算：先按行为上限定 drop / quarantine / notify，再按 `disclosure_max` 定 outcome 是否可回送。`blocked_subjects` / `blocked_principal_services` 命中时仍无条件强制 `opaque`，不受 `disclosure_max` 影响。
- `allowed_handle_domains`、`trusted_handle_issuers`、`trusted_directory_services`、`trusted_principal_services`、`accepted_subject_did_methods` 是部署级 allowlist；字段省略表示该维度不设部署级上限，字段存在且为空数组表示不接受该维度的任何候选。非空时必须命中。未命中 MUST 视为策略拒绝，不得通过响应区分“存在但被策略拒绝”和“不存在”。
- `blocked_principal_services` 命中时 MUST `drop` 且强制 `opaque`。

示例：

```json
{
  "policy_version": "2026-06-21",
  "applies_to": ["invite_delivery", "contact_request"],
  "permitted_introduction_kinds": [
    "locator_ref",
    "consent_grant",
    "shared_realm",
    "handle_claim"
  ],
  "handle_claim_max_behavior": "quarantine",
  "explicit_address_max_behavior": "drop",
  "allowed_handle_domains": ["acme.example"],
  "trusted_handle_issuers": ["did:webvh:z43vHHHeh32Hnyv6t7X3t33Xs:directory.acme.example"],
  "trusted_directory_services": ["did:webvh:z43vHHHeh32Hnyv6t7X3t33Xs:directory.acme.example"],
  "accepted_subject_did_methods": ["did:webvh"]
}
```

## 6. Durable Event Boundary

`ck.invite.create` 是 Realm durable event。它可以携带可公开审计的 delivery target 与 evidence digest，但不得携带 locator token、raw `introduction_evidence` 或 `invite_receive_policy`。

```json
{
  "invite_id": "ak:invite:0196419b-0000-7000-8000-000000000010",
  "invitee": "did:webvh:z2dmjBobExample:users.bob.example:bob",
  "invite_delivery_target": {
    "recipient_service_did": "did:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc:ps.bob.example"
  },
  "introduction_evidence_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "expires_at": "2026-06-14T10:00:00Z"
}
```

Rules:

- `payload.invitee` MUST equal `invite_address.subject_id`.
- `payload.invite_delivery_target.recipient_service_did` MUST equal `invite_address.recipient_service_did`.
- `payload.invite_delivery_target.recipient_service_type` MAY appear; if present, it MUST be `principal_server`.
- `introduction_evidence_digest = digest(canonical_json(private_delivery_introduction_evidence))`，用于审计关联，不得泄露 raw locator token。
- 普通定向邀请的取消 / 拒绝 MUST 使用 `ck.invite.cancel`，payload 为 `InviteRefPayload`（`invite_id`，可选 `reason`）。被邀请者本人提交时表示拒绝并写入 `rejected`；邀请者或 Realm 管理 actor 提交时表示撤销尚未接受的 pending invite 并写入 `revoked`。
- `ck.invite.revoke` MUST 用于第三方/token invite 的撤销或等价高风险撤销路径，payload 同样为 `InviteRefPayload`；reducer MUST 将 live invite 写入 `revoked`，并清除可认领 token material。直接 DID 邀请不需要通过 `ck.invite.revoke` 才能从成员管理 UI 撤销。

## 7. 私有 Invite Delivery

邀请方 Principal Server 使用：

```text
POST /_arkret/peer/invites
operation_id = ck.peer.invites.command.submit
```

request body 为 `ck.schema.invite_delivery_request.v1`。接收方 Principal Server MUST：

1. 验证 service-to-service authentication，绑定 Source/Destination service DID、trust domain、Request-Canonical-Digest、Content-Digest 与 idempotency key。
2. 验证 `Destination-Service-DID == invite_address.recipient_service_did`。
3. 验证 `invite_event.kind == "ck.invite.create"`、Event signature、Realm capability、`invite_id` 与 `realm_id`。
4. 验证 `invite_event.payload.invitee == invite_address.subject_id`。
5. 验证 `invite_event.payload.invite_delivery_target.recipient_service_did == invite_address.recipient_service_did`。
6. 验证 `introduction_evidence`，并核对 `introduction_evidence_digest`。对 `consent_grant` evidence,MUST 按 §2 校验 `consent_grant_ref` 是被邀请方给 inviter 的 active `invite` / `any` grant dot；校验失败 MUST 降级为低信任 `explicit_address` 处理。对 `handle_claim` evidence,MUST 按 §2 校验 handle claim、issuer / Directory trust、domain allowlist、expiry、audience、handle claim 自带的 `member_delivery_binding`（若存在）和可选 `member_delivery_binding_candidate`；校验失败 MUST 降级为低信任 `explicit_address` 处理。
7. 计算 effective receive policy:先取 subject 私有 `invite_receive_policy`，再与 §5.2 `receive_policy_constraints` 及适用组织 / Realm 约束求交集。随后查 `blocked_subjects`(命中 inviter 即 `drop` 且强制 opaque)与 `blocked_principal_services`；再按 effective `allowed_introduction_kinds`、`handle_claim_behavior`、`explicit_address_behavior`、`unknown_invites` 决定 drop / quarantine / notify。
8. 返回 receive outcome:按 §5.1 分级披露。发现信任档、低信任档或 `blocked_subjects` 命中时默认返回 generic `status`(opaque),MUST NOT 通过响应泄露 subject 是否存在或策略如何处理；高信任档且 `disclosure.high_trust=outcome` 时 MAY 在 `disclosed_outcome` 回送真实结果。仅当 subject 与部署约束都允许 `disclosure.discovery_trust=outcome` 时，`handle_claim` MAY 回送真实结果。

## 8. Describe Capabilities

支持 invite addressing 的 Principal Server SHOULD 在 `ServiceDescribe.supported_operations` 中声明：

- `ck.open.invite_locator.query.resolve`
- `ck.peer.invites.command.submit`

它 MAY 在 `x_invite_addressing` 扩展字段中给出粗粒度能力：

```json
{
  "x_invite_addressing": {
    "supported_introduction_kinds": [
      "locator_ref",
      "consent_grant",
      "shared_realm",
      "handle_claim",
      "same_principal_server",
      "explicit_address"
    ],
    "recommended_introduction_kind": "locator_ref",
    "handle_claim_default_behavior": "quarantine",
    "explicit_address_default_behavior": "quarantine"
  },
  "receive_policy_constraints": {
    "policy_version": "2026-06-21",
    "applies_to": ["invite_delivery", "contact_request"],
    "permitted_introduction_kinds": [
      "locator_ref",
      "consent_grant",
      "shared_realm",
      "handle_claim"
    ],
    "handle_claim_max_behavior": "quarantine",
    "explicit_address_max_behavior": "drop",
    "allowed_handle_domains": ["acme.example"]
  }
}
```

Directory 服务若支持 handle lookup，也 MAY 在 `ServiceDescribe` 或 `ck.find.directory.query.describe` 的扩展字段中声明：

```json
{
  "x_handle_resolution": {
    "invite_enabled": false,
    "member_add_enabled": false
  }
}
```

base clients MUST NOT require `resolve_handle(intent="invite" | "member_add")` to create or deliver an invite.

## 9. Handle 与 Mention 边界

`ck.find.directory.query.resolve_handle(intent="contact_request" | "invite" | "member_add")` 是可选 Directory 能力，不是 base first-contact / invite / member-add 的安全关键路径。Directory 即使返回 `member_delivery_binding` 或旧式 `MemberDeliveryBindingCandidate`，也只能作为可验证 builder evidence 或 `handle_claim` introduction evidence；reducer 仍 MUST 按 Join Policy 与 [`member-delivery-binding.md`](../governance/member-delivery-binding.md) 重新物化。

Realm 内 mention 不依赖公网 handle resolve。客户端在用户输入 `@alice:acme.example` 时 MUST 先从当前 Realm roster、MemberIdentity subject disclosure、内联 signed `handle_claims[]` 或本地已授权 claim cache 中解析到 `subject_id`。发送 Message 前必须持久化 DID-sealed mention reference；handle 字符串只能作为 audit / search metadata。

已知 `subject_id` 需要显示当前 handle 时，客户端 MAY 使用 roster 内联 `handle_claims[]` 或 `ck.find.directory.query.list_handles_for_subject`。这条 subject -> current handles 路径不得反向用来发现未知主体、发起 invite delivery 或构造 membership grant；只有 holder/issuer 已发布 verified handle claim，且 subject policy 与部署约束允许 `handle_claim` evidence 时，客户端才可把 handle 解析结果作为 first-contact / invite 的 introduction evidence。
