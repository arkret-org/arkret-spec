---
title: Invite Addressing and Principal Locator
status: candidate
normative: true
stability: v1
updated: 2026-06-07
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

base v1 invite **MUST NOT** 依赖 `ck.find.directory.resolve_handle(intent="invite" | "member_add")` 才能投递。Handle 是人类可读入口，不是邀请投递授权；实现不得把猜到的 `<localpart>:<domain>` 字符串自动升级成可投递邀请。

邀请目标的规范输入是显式 `invite_address`：

```json
{
  "subject_id": "did:web:bob.example",
  "recipient_service_did": "did:web:ps.bob.example"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `subject_id` | DID | MUST | 被邀请的 principal / holder DID。 |
| `recipient_service_did` | DID | MUST | 接收 invite delivery 的 Principal Server service DID。 |
| `recipient_service_type` | const | MAY | 若出现，MUST 等于 `principal_server`；默认省略。 |

`recipient_service_did` 在 v1 中只表示 Principal Server。它 **MUST NOT** 指向 anchorer、shared Sync Service、push gateway、Directory 或任意第三方服务。将来如果需要组织、群组或其它接收服务形态，必须定义独立 locator / delivery schema，不得把 `recipient_service_type` 扩成宽枚举后复用本 schema。

## 2. Introduction Evidence

每个私有 invite delivery request **MUST** 携带 `introduction_evidence`，说明邀请方为什么可以尝试联系被邀请方。schema 见 [`invite-delivery-request.schema.json`](../../artifacts/schemas/invite-delivery-request.schema.json)。

| `kind` | 信任强度 | 说明 |
| --- | --- | --- |
| `locator_ref` | 高 | 被邀请方主动生成 / 交付的在线 locator ref。默认推荐。 |
| `shared_realm` | 中 | 邀请者与被邀请者已经同在某个 Realm；接收方按本地 policy 判断该 Realm 是否可信。 |
| `same_principal_server` | 中 / 部署相关 | 双方由同一个 Principal Server 承载；适合组织或个人同域场景。 |
| `explicit_address` | 弱 | 邀请者只提供 `subject_id + recipient_service_did`；等价于“我知道或猜测这个地址”。默认 SHOULD quarantine 或 drop。 |

`explicit_address` 是合法但最低信任 evidence。接收方 **MUST NOT** 因为请求格式正确就通知用户；必须先应用 subject 私有 `invite_receive_policy`。

## 3. 在线 Principal Locator

二维码 / 链接默认承载在线 locator ref，不承载完整 signed locator。

推荐 QR / link 文本：

```text
https://ps.bob.example/_cokret/open/invite-locators/resolve#token=<locator_token>
```

扫描方客户端读取 fragment 后，向同一 origin 提交：

```text
POST /_cokret/open/invite-locators/resolve
```

body：

```json
{
  "locator_token": "base64url-token-with-at-least-128-bit-entropy"
}
```

`locator_token` **MUST** 只通过 JSON body 或等价 signed proof 提交，**MUST NOT** 出现在 URL path、query string、Referer、普通 access log、analytics、crash report、local storage 或浏览器历史中。客户端读取 fragment 后 **MUST** 清理地址栏与本地临时状态。

token 要求：

- `locator_token` MUST 至少 128 bit 熵；高安全部署 SHOULD 使用 192 bit 或更高。
- token MUST 不可枚举、可撤销、可设置短 TTL，并 MAY 设置一次性使用。
- endpoint 对不存在、过期、撤销、策略拒绝的响应 MUST 尽量不可区分。
- endpoint 返回体 MUST 是签名 `principal_locator`；调用方不能只信任 HTTPS URL。

## 4. `principal_locator`

`principal_locator` 是被邀请方 Principal Server 返回的、可验证的 invite address assertion。schema id 为 `ck.schema.principal_locator.v1`。

最小形态：

```json
{
  "schema": "ck.schema.principal_locator.v1",
  "subject_id": "did:web:bob.example",
  "recipient_service_did": "did:web:ps.bob.example",
  "issued_at": "2026-06-07T10:00:00Z",
  "expires_at": "2026-06-07T10:15:00Z",
  "locator_ref_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "proofs": [
    {
      "proof_purpose": "recipient_service_acceptance",
      "proof": {
        "kind": "detached_jws",
        "verification_method": "did:web:ps.bob.example#server-key-1",
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
  "subject_id": "did:web:bob.example",
  "allowed_introduction_kinds": [
    "locator_ref",
    "shared_realm",
    "same_principal_server"
  ],
  "explicit_address_behavior": "quarantine",
  "unknown_invites": "drop",
  "trusted_realm_ids": [],
  "trusted_principal_services": [],
  "blocked_principal_services": []
}
```

规则：

- `allowed_introduction_kinds` 是 allowlist；未列出的 evidence MUST NOT 触发用户通知。
- `explicit_address_behavior` 取值为 `drop | quarantine | notify`；默认 SHOULD 是 `quarantine` 或 `drop`。
- `unknown_invites` 取值为 `drop | quarantine`；无 evidence 或不合规 evidence 不得默认 notify。
- policy 是 subject/private state，不得写入目标 Realm event log。

## 6. Durable Event Boundary

`ck.invite.create` 是 Realm durable event。它可以携带可公开审计的 delivery target 与 evidence digest，但不得携带 locator token、raw `introduction_evidence` 或 `invite_receive_policy`。

```json
{
  "invite_id": "ck:invite:0196419b-0000-7000-8000-000000000010",
  "invitee": "did:web:bob.example",
  "invite_delivery_target": {
    "recipient_service_did": "did:web:ps.bob.example"
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

## 7. 私有 Invite Delivery

邀请方 Principal Server 使用：

```text
POST /_cokret/peer/invites
operation_id = ck.peer.invites.submit
```

request body 为 `ck.schema.invite_delivery_request.v1`。接收方 Principal Server MUST：

1. 验证 service-to-service authentication，绑定 Source/Destination service DID、trust domain、Request-Canonical-Digest、Content-Digest 与 idempotency key。
2. 验证 `Destination-Service-DID == invite_address.recipient_service_did`。
3. 验证 `invite_event.kind == "ck.invite.create"`、Event signature、Realm capability、`invite_id` 与 `realm_id`。
4. 验证 `invite_event.payload.invitee == invite_address.subject_id`。
5. 验证 `invite_event.payload.invite_delivery_target.recipient_service_did == invite_address.recipient_service_did`。
6. 验证 `introduction_evidence`，并核对 `introduction_evidence_digest`。
7. 应用 `invite_receive_policy`。
8. 返回 generic receive outcome；除非 receiver policy 显式允许披露，否则 MUST NOT 通过响应泄露 subject 是否存在或策略如何处理。

## 8. Describe Capabilities

支持 invite addressing 的 Principal Server SHOULD 在 `ServiceDescribe.supported_operations` 中声明：

- `ck.open.invite_locator.resolve`
- `ck.peer.invites.submit`

它 MAY 在 `x_invite_addressing` 扩展字段中给出粗粒度能力：

```json
{
  "x_invite_addressing": {
    "supported_introduction_kinds": [
      "locator_ref",
      "shared_realm",
      "same_principal_server",
      "explicit_address"
    ],
    "recommended_introduction_kind": "locator_ref",
    "explicit_address_default_behavior": "quarantine"
  }
}
```

Directory 服务若支持 handle lookup，也 MAY 在 `ServiceDescribe` 或 `ck.find.directory.describe` 的扩展字段中声明：

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

`ck.find.directory.resolve_handle(intent="invite" | "member_add")` 是可选 Directory 能力，不是 base invite/member-add 的安全关键路径。Directory 即使返回 `member_delivery_binding` 或旧式 `MemberDeliveryBindingCandidate`，也只能作为可验证 builder evidence；reducer 仍 MUST 按 Join Policy 与 [`member-delivery-binding.md`](../governance/member-delivery-binding.md) 重新物化。

Realm 内 mention 不依赖公网 handle resolve。客户端在用户输入 `@alice:acme.example` 时 MUST 先从当前 Realm roster、MemberIdentity subject disclosure、内联 signed `handle_claims[]` 或本地已授权 claim cache 中解析到 `subject_id`。发送 Message 前必须持久化 DID-anchored mention reference；handle 字符串只能作为 audit / search metadata。

已知 `subject_id` 需要显示当前 handle 时，客户端 MAY 使用 roster 内联 `handle_claims[]` 或 `ck.find.directory.list_handles_for_subject`。这条 subject -> current handles 路径不得反向用来发现未知主体、发起 invite delivery 或构造 membership grant。
