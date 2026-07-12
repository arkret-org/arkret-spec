---
title: Policy Server
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Policy Server 是可插拔的风险判断与治理服务，用于邀请、加入、媒体、消息、Applet、跨域联邦、目录发现、通话邀请等场景的预检查和审计。它类似 Matrix policy server / moderation policy 的思想，但在 Arkret 中不替代 capability authorization。

## 2. Policy Server Declaration

Realm 可通过 state event 声明策略服务：

```json
{
  "kind": "ak.realm.policy_server",
  "payload": {
    "server_id": "did:webvh:z9oyrNdJAoqkAh5Remo6dZUdV:policy.example.com",
    "endpoint": "https://policy.example.com/_arkret/self/policy/check",
    "public_keys": [
      "did:webvh:z9oyrNdJAoqkAh5Remo6dZUdV:policy.example.com#key-1"
    ],
    "applies_to": [
      "join",
      "invite",
      "message",
      "media",
      "applet",
      "directory",
      "call",
      "federation"
    ],
    "policy_sources": [
      {"kind": "ak.realm.moderation_policy"},
      {"kind": "ak.organization.moderation_policy"}
    ],
    "abuse_profile_ref": "ak.policy:abuse-v1",
    "fail_mode": "soft_deny",
    "cache_ttl_seconds": 300
  }
}
```

声明该事件需要 `ak.policy.manage` capability。

`policy_sources[]` 中每一项 MUST 是 `{"kind": "<event_kind>"}` 形态的 object（如示例所示）。Reducer / Policy Server canonical transcript 仅接受 object form；不接受裸字符串简写——若实现需要把字符串映射到 object，必须在客户端构造 Event 之前完成，使写到 wire 上的形态始终是 canonical object，避免 signature/hash transcript 在不同实现之间不一致。

### 2.1 policy_sources 不可解析时 fail-closed（normative）

`policy_sources[]` 中任一 referenced policy event（如 `ak.realm.moderation_policy` / `ak.organization.moderation_policy`）在 Policy Server 评估某请求时，于该请求的当前 seal view 下**缺失、未被任何 accepted Seal 覆盖、被 redact / tombstone、或解析为 `⊥`（多 head 冲突）**时，Policy Server **MUST** 把该 policy source 视为不可解析，并按该 `ak.realm.policy_server` declaration 的 `fail_mode` 处理（§6；未显式声明 `fail_mode` 时缺省即 `closed`），**MUST NOT** 把"policy source 不可解析"等同于"该 source 为空 policy / 无规则"而按 allow 放行。

- `fail_mode=closed`（含缺省）：不可解析时该路径请求 MUST 拒绝（`hard_deny`，`reason_code="policy_violation"` 或部署声明的更具体码）。
- `fail_mode=soft_deny`：MUST 阻止默认客户端提交，MAY 允许 proposal / 重试。
- `fail_mode=quarantine`：可提交但进入 quarantine。
- `fail_mode=open`：仅在 declaration 显式声明且非公开 Realm 时才允许按基础授权继续（§6 对 `open` 的硬约束适用）。

被 redact 是不可解析的一种：一个被 redact 的 moderation_policy event MUST NOT 被解释为"放开该 policy 维度"。多个 policy_sources 中只要有任一不可解析，整体即按上述 fail_mode 处理，MUST NOT 因其余 source 可解析就跳过缺失 source 的治理维度。

## 3. Check Request

```http
POST /_arkret/self/policy/check
Authorization: Bearer <service_token>
Content-Type: application/json
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `service_signature` | required | Policy Server 授权凭证；MUST 绑定调用服务 DID。 |
| `request_id` | body | `string` | required | 请求 ID，用于日志和幂等追踪。 |
| `realm_id` | body | `id` | required | 相关 Realm；进入 cache key、policy transcript 和 obligation `bound_to.realm_id`。纯账号级检查 MUST 使用 principal control Realm id。 |
| `request_canonical_digest` | body | `sha256:<hash>` | required | 被检查请求或事件 preview 的 canonical hash。 |
| `action` | body | `string` | required | 待检查动作，例如 `ak.message.create`。 |
| `actor_id` | body | `did` | required | 发起动作的 Actor DID。 |
| `device_id` | body | `id` | optional | 发起设备。 |
| `source` | body | `object` | required | 调用来源摘要。 |
| `source.service_id` | body | `did` | required | 调用服务 DID。 |
| `source.service_type` | body | `string` | required | 调用服务类型。 |
| `source.source_ip_digest` | body | `sha256:<hash>` | optional | 来源 IP 的 keyed 不可链接派生值；派生与轮换规则见 §3.1。MUST NOT 是对 IP 地址的裸 SHA-256。 |
| `source.signed_transport` | body | `boolean` | required | 请求是否由签名 transport 保护。 |
| `event_preview` | body | `object` | optional | 最小披露事件预览。 |
| `auth_context` | body | `object` | optional | membership、capability、origin service 等授权上下文。 |

请求示例（非完整 schema）：

```json schema=openapi/arkret-service-api.openapi.yaml#/components/schemas/PolicyCheckRequestBody
{
  "request_id": "polreq_01",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "request_canonical_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "action": "ak.message.create",
  "actor_id": "did:webvh:...",
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "source": {
    "service_id": "did:webvh:z5CVGhWHEfRe1HhKLRueCrxfD:server.example",
    "service_type": "principal_server",
    "source_ip_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "signed_transport": true
  },
  "event_preview": {
    "kind": "ak.message.create",
    "content_digest": "sha256:...",
    "redacted_content": {
      "mentions": ["did:webvh:z4Uy7eEwDuHWSxMT2dHWEWPip:bob.example.com"],
      "media": [{"blob_id": "blob:...", "mime": "image/png"}]
    }
  },
  "auth_context": {
    "membership": "join",
    "capability_ids": ["grant:..."],
    "origin_service": "did:webvh:z5CVGhWHEfRe1HhKLRueCrxfD:server.example"
  }
}
```

请求 MUST 使用最小披露。E2EE 内容不得为策略检查强制明文上传；客户端 MAY 提供本地分类标签、hash、媒体 metadata 或用户确认的 report snippet。

### 3.1 `source.source_ip_digest` 派生（normative）

`source_ip_digest` 只用于限速、滥用聚类等策略维度，不用于身份识别。IP 地址空间很小，裸 hash 可被字典枚举，并可跨服务、跨 realm、跨时间关联请求来源，因此：

- 该值 MUST 是调用服务私有 secret 下的 keyed 派生，例如 `HMAC-SHA256(policy_source_secret[salt_epoch], canonical_json({service_id, ip_or_prefix, salt_epoch}))`；wire 形态仍为 `sha256:<64 hex>`——`sha256:` 前缀表示 32 字节摘要容器，**不**表示对 IP 地址的裸 SHA-256。实现 MUST NOT 直接对 IPv4/IPv6 地址或其简单变形做无 key hash。
- `policy_source_secret` MUST NOT 上 wire，MUST 按 salt epoch 轮换；同一来源 IP 在不同 epoch 的派生值 MUST 互不可链接。epoch 长度由部署 profile 决定，SHOULD 不超过限速窗口所需的最小期限。
- 派生命名空间 MUST 绑定调用服务（如把 `service_id` 纳入派生输入）；secret 不得跨服务或跨 realm 复用，使 Policy Server 或旁观者无法据此跨服务关联同一来源。
- relay / OHTTP 等高隐私部署形态（见 [`../security/server-threat-model.md`](../security/server-threat-model.md)）下，调用方 MAY 省略该字段，或以不可链接限速 token（如 Privacy Pass 类机制，informative）替代 IP 维度；Policy Server MUST 容忍该字段缺失。

## 4. Decision

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `request_id` | `string` | required | 回显请求 ID。 |
| `bound_to` | `object` | required | Policy Server 回签的请求绑定；MUST 至少包含 `realm_id`、`actor_id`、`action`、`request_canonical_digest`、`policy_server_id`，调用方缓存或复用 decision 前必须逐字段比较。 |
| `bound_to.realm_id` | `id` | required | 等于 request `realm_id`。 |
| `bound_to.actor_id` | `did` | required | 等于 request `actor_id`。 |
| `bound_to.action` | `string` | required | 等于 request `action`。 |
| `bound_to.request_canonical_digest` | `sha256:<hash>` | required | 等于 request `request_canonical_digest`。 |
| `bound_to.policy_server_id` | `did` | required | 签发该 decision 的 Policy Server DID；必须与 declaration `server_id` 和 `signature.kid` 控制者一致。 |
| `decision` | `enum(allow,soft_deny,hard_deny,quarantine,require_review)` | required | 策略决策。 |
| `reason_code` | `string` | required | 稳定原因码。 |
| `expires_at` | `datetime` | required | 决策缓存过期时间。 |
| `auth_state_digest` | `sha256:<hash>` | required | 生成该 decision 时采用的 accepted authorization state hash；调用方命中缓存或跨服务复核时 MUST 与当前值比较。 |
| `policy_frontier_digest` | `sha256:<hash>` | required | 生成该 decision 时采用的 policy source frontier / digest。 |
| `membership_frontier_digest` | `sha256:<hash>` | required | 生成该 decision 时采用的 membership / role frontier digest。 |
| `next_retry_at` | `datetime` | optional | 可重试时间，仅限限流/退避场景。 |
| `obligations` | `object[]` | optional | 调用方必须执行的附加动作。 |
| `signature` | `signature` | required | Policy Server 对决策的签名。 |
| `signature.kid` | `did-url` | required | 签名 key id。 |
| `signature.sig` | `base64url string` | required | detached signature。 |

`policy_frontier_digest` 与 `membership_frontier_digest` 是可跨 issuer 复算的 filtered state roots，不是 issuer-local opaque 值。二者 MUST 复用 [`event-auth-state-resolution.md` §6.2.1/§6.2.2](./event-auth-state-resolution.md#621-治理-state_root-的-merkle-计算规则normative) 的 JCS leaf、排序、hash suite 与 RFC 6962 组合规则：

- `policy_frontier_digest` 枚举 decision `bound_to.realm_id` 当前 accepted Seal view 中全部 non-`⊥` policy control cell（`ak.component.realm.*policy*`、join rule、history visibility、policy components、media service，以及 profile 明确登记的 policy family）。
- `membership_frontier_digest` 枚举同一 Seal view 中全部影响 `bound_to.actor_id` 的 Realm/Circle membership、account lifecycle、device trust/authorization 与 role cell。
- 每个 leaf 都是 `canonical_json({"cell":"<cell_wire_id>","state":{"value":<lattice_value>}})` 的 UTF-8 bytes；按 cell id 升序，`leaf=H(0x00||bytes)`、`node=H(0x01||left||right)`，奇数节点原样提升，空集用 `H("")`。

签发者与 verifier MUST 从 decision 绑定的 Seal/frontier 独立枚举并重算；漏报一个 cell、使用本地到达顺序或无法证明 frontier inclusion 时，该结构化比较路径失败，跨 issuer receiver 必须走 §5.1 的本地重跑分支。

响应示例（非完整 schema）：

```json schema=openapi/arkret-service-api.openapi.yaml#/components/schemas/PolicyCheckOutcome
{
  "request_id": "polreq_01",
  "bound_to": {
    "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
    "actor_id": "did:webvh:...",
    "action": "ak.message.create",
    "request_canonical_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "policy_server_id": "did:webvh:z9oyrNdJAoqkAh5Remo6dZUdV:policy.example.com"
  },
  "decision": "allow",
  "reason_code": "ok",
  "expires_at": "2026-04-26T00:05:00Z",
  "auth_state_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "policy_frontier_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "membership_frontier_digest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "next_retry_at": "2026-04-26T00:05:30Z",
  "obligations": [
    {"type": "rate_limit", "bucket": "message", "remaining": 20}
  ],
  "signature": {
    "kid": "did:webvh:z9oyrNdJAoqkAh5Remo6dZUdV:policy.example.com#key-1",
    "sig": "base64url..."
  }
}
```

`decision` 取值：

- `allow`
- `soft_deny`
- `hard_deny`
- `quarantine`
- `require_review`

`hard_deny` MAY 使事件被 reject；`quarantine` MUST 使事件进入 quarantine；`soft_deny` SHOULD 阻止默认客户端提交，但 Sync Service MAY 接收并保留为策略软拒绝记录；`require_review` 生成 proposal/review strand。

`reason_code` SHOULD 至少覆盖：

- `ok`
- `spam_flood`
- `invite_token_risk`
- `session_credential_replay_risk`
- `auth_threat`
- `spoof_like`
- `malware_media`
- `replay_suspect`
- `policy_violation`
- `fork_risk`
- `resolver_risk`
- `topology_risk`
- `snapshot_risk`

`obligations` 可用于返回风控动作（例如 `rate_limit`、`challenge`、`review_hold`、`drop_attachment`）。
`next_retry_at` SHOULD 仅在限流/退避路径返回。

#### 4.1 Obligation `challenge` Wire Schema

`type=challenge` 是 join、message、media 路径上通用的运行时挑战 obligation。客户端按下表组装 `gate_proofs[]` 或 envelope-级 challenge proof 后重提原始 Event：

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `type` | yes | `"challenge"` |  |
| `challenge_id` | yes | `string` | 由 issuer 生成的 unique id；客户端在重提 Event 时回填到 `challenge_proof.challenge_id`。 |
| `kinds` | yes | `enum(captcha, pow, attested_human, idp_oidc)[]` | 客户端 MAY 任选其一完成。 |
| `issuer` | yes | `did` | 颁发挑战的服务 DID；客户端 MUST 校验 proof signature 来自该 DID。 |
| `endpoint` | yes | `url` | 客户端获取挑战物料 / 提交解答的 HTTPS endpoint。 |
| `max_proof_age` | yes | `duration` | proof 自签发起的有效期；reducer 拒绝过期 proof。 |
| `must_satisfy_before_resubmit` | no | `boolean` | 默认 `true`。 |
| `bound_to` | yes | `object` | 见下；显式绑定 challenge 到具体 Event / actor / device，防止 proof 复用。 |

`bound_to` 子字段：

```json
{
  "actor_id": "did:webvh:z2dmjYwAPJzv5CZsnAzt8auVZRn1GfuxhpK2t3Q3K3rj4B1x:users.example:bob",
  "action": "member.application",
  "request_canonical_digest": "sha256:...",
  "device_id": "ak:device:..."
}
```

> `bound_to.action` 必须等于被授权动作的规范名称。`member.application` / `member.application.review` / `member.application.cancel` 当前是 candidate workflow concept/action 名称（不是 v1 wire `Event.kind`，见 [`../conformance/schema-registry.md` §4.1](../conformance/schema-registry.md)），因此示例与 candidate reducer 校验都用裸名。已注册的 Event（如 `ak.member.state`）则继续使用 `ak.*` 前缀。

`challenge` obligation 中的 `bound_to.request_canonical_digest` 是**被 challenge 的原始请求 hash**，不是包含 `challenge_proof` 自身的重提 Event hash。计算规则：

1. 首次 `/_arkret/self/policy/check` 时，调用方对原始 Event preview / application private record body 做 JCS canonical SHA-256，作为 `request_canonical_digest`。
2. 客户端重提时可以在 `gate_proofs[]` 或 envelope proof 区追加 runtime challenge proof；reducer 重新计算 hash 时 MUST 先移除 runtime challenge proof 条目（`gate_id="runtime:<challenge_id>"` 或等价 envelope proof 字段），再按同一 JCS 规则计算。
3. provider 签发的 proof MUST 绑定该原始 hash、`challenge_id`、`actor_id`、`action`、`realm_id?`、`device_id?`、`expires_at` 和 issuer。实现 MUST NOT 要求 proof 内 hash 等于“包含 proof 自身的最终 Event hash”，否则会形成自引用 transcript。

provider 颁发的 challenge proof 形态：

```json
{
  "challenge_id": "chg_01HXY9PM0AB6Y7VN2C7M4WG5KQ",
  "issued_by": "did:webvh:zaeuR1WGwz5pkZueKCmyqGFqu:captcha.example",
  "issued_at": "2026-04-26T00:00:00Z",
  "expires_at": "2026-04-26T00:05:00Z",
  "bound_to": { "...": "echo of obligation.bound_to" },
  "proof_method": "captcha-v1 | pow-sha256 | webauthn-attestation | oidc-id-token",
  "proof_value": "base64url:...",
  "signature": {
    "kid": "did:webvh:zaeuR1WGwz5pkZueKCmyqGFqu:captcha.example#key-1",
    "sig": "base64url:..."
  }
}
```

reducer 校验顺序：

1. provider signature 有效，`kid` 与 obligation `issuer` 匹配；
2. `expires_at > now`；
3. `bound_to` 必须存在；`bound_to.actor_id` 等于 Event envelope `actor_id`，`bound_to.action` 等于 Event kind，`bound_to.request_canonical_digest` 等于按 §4.1 proof-stripped 规则重算出的原始请求 canonical hash；
4. `challenge_id` 在 reducer 的 nonce 缓存中尚未消费；写入成功后入缓存（最少缓存到 `expires_at`）。

任一项失败 `failed_precondition`，`reason_code="challenge_proof_invalid"`。

Join 路径上 `challenge` proof 进入 `ak.member.state{join}.gate_proofs[]` 或 candidate `member.application.gate_proofs[]`（`member.application` 当前不是 v1 wire `Event.kind`），使用 `gate_id="runtime:<challenge_id>"`，并以 `challenge_proof.challenge_id` 作为唯一匹配键；verifier MUST NOT 依赖占位 gate id 选择 challenge proof。运行时 challenge 与静态 `challenge_response` gate 共享同一 verifier 实现。详见 [`../governance/join-policy.md` §11](../governance/join-policy.md)。

## 5. Signature and Replay Protection

Policy decision 签名输入 MUST 包含：

- `request_id`
- `bound_to.request_canonical_digest`
- `bound_to.realm_id`（被评估对象所属的 Realm ID;**v1 normative**）
- `bound_to.actor_id`（被评估 actor DID;**v1 normative**）
- `bound_to.action`（被评估的 capability action token）
- `bound_to.policy_server_id`
- decision
- reason_code
- expires_at
- auth_state_digest
- policy_frontier_digest
- membership_frontier_digest
- Policy Server id
- key id

`request_canonical_digest` MUST 是 [RFC 8785](https://datatracker.ietf.org/doc/html/rfc8785) JSON Canonicalization Scheme (JCS) 在该请求 body 上的 SHA-256 digest（hex 或 base64url，与 hash 字段 prefix `sha256:` 一致）。本规范锁定 JCS 形态以保证跨实现 hash 输入一致；任何"按 service-private 算法计算 canonical hash"的实现 MUST NOT 与其他 conformant 实现互通，且 MUST NOT 声明通过 v1 conformance。

节点 MUST 拒绝过期 decision。缓存 decision 时 MUST 以 `(bound_to.realm_id, bound_to.actor_id, bound_to.action, bound_to.request_canonical_digest, auth_state_digest)` 五元组为 key，或在 cache entry 中携带 `auth_state_digest` 并在每次命中时与当前 accepted auth state hash constant-time 比较；不一致 MUST 回退完整授权判定。`auth_state_digest` 的定义与 fast-path capability cache 相同（见 [`capabilities.md` §18.1](./capabilities.md)），覆盖当前 capability grant/revoke、membership、policy、必要 claim status、device/session control seal 和相关 state event canonical digest。TTL 只能作为额外上限，不能掩盖 auth state 变化。不得仅按 `request_canonical_digest` 索引——后者会让一个 (realm, actor) 的 allow decision 泄漏到具有相同 body hash 但不同 (realm, actor) 上下文的请求中(攻击者可在 Realm A 中触发一次合法 allow,再在 Realm B 中用相同请求 body 通过缓存复用，从而绕过 Realm B 的实际 policy)。

接收方 MUST 同时校验:

1. signature 由 `policy_server_id` 的当前 active verification method 签发;
2. `bound_to` 必须存在，且 `bound_to.realm_id` / `bound_to.actor_id` / `bound_to.action` / `bound_to.request_canonical_digest` 与本次 request 完全一致;
3. `expires_at > now`;
4. `auth_state_digest`、`policy_frontier_digest`、`membership_frontier_digest` 与本地 accepted authorization / policy / membership frontier 一致；不一致 MUST 回退完整授权判定或重新请求 policy check;
5. 该 decision 未被同一 policy_server 后续的 `ak.moderation.decision.lift` 或 sealed control override 撤销。

Frontier 比较必须区分“本地落后”和“本地更新”。若本地 accepted authorization / policy / membership frontier 严格晚于 decision 绑定的 frontier（即本地已看到 decision 签发后发生的 grant revoke、membership 变化、policy 变化或相关 state digest 变化），receiver MUST fail closed 并重新请求 `/_arkret/self/policy/check`；不得把旧 decision 复用到更新后的 auth state。只有本地 frontier 可证明小于或等于 decision frontier，且 decision 仍在 `expires_at` 窗口内时，才可把不一致视为本地落后并按完整授权 / 补拉路径处理。

#### 5.1 跨 issuer 复用 decision 的比较基准（normative）

`auth_state_digest` 在跨实现 wire 上是 **issuer-local opaque commitment**（见 [`capabilities.md` §18.1](./capabilities.md)）：除非具体 deployment profile 声明了可复算的 auth-state canonical encoding，第三方 verifier **无法逐字重算**签发者的 `auth_state_digest`。因此上文"`auth_state_digest` 与本地 accepted auth state 一致"的逐字比较步骤，**只对签发该 decision 的同一 Policy Server（同 issuer）自缓存复用成立**——签发者复用自己签发的 decision 时，可逐字比较自己产生的 opaque digest。

**跨 issuer 复用（接收方 ≠ decision 签发者，典型为联邦 §9 收到 origin 附带的 decision）时**：接收方 **MUST NOT** 依赖对 `auth_state_digest` 的逐字比较来判定 decision 仍有效（它无法逐字重算该 opaque 值，逐字比较步骤不可执行）。接收方 MUST 改用下列二者之一：

1. **比较结构化 frontier digest**：用 `policy_frontier_digest` 与 `membership_frontier_digest`（这两者绑定可按 `auth_frontier` 取得的 accepted policy / membership frontier，而非纯 issuer-local opaque commitment）与接收方本地按相同 frontier 解析出的值比较，并按上文"本地落后 vs 本地更新"规则裁决；或
2. **本地重跑**：接收方按 §9 在本地重新执行 capability/auth 验证与（如配置）本地 `/_arkret/self/policy/check`，不复用 origin decision 的授权判定。

接收方 MUST NOT 把"无法逐字重算 `auth_state_digest`"解释为"digest 校验通过"或"授权通过"——这正是 [`capabilities.md` §18.1](./capabilities.md) 对 opaque digest 的 verifier 纪律。只有同 issuer 自缓存路径可逐字比 `auth_state_digest`；跨 issuer 路径的安全判定 MUST 来自 frontier digest 比较或本地重跑。该规则与 §9「MUST NOT 因 origin policy allow 而跳过本地 capability/auth 验证」一致。

**CBA basis 例外（normative）**：reducer 评估 Event 时，DataEvent 只读取自身 `seal_ref` 指向的控制面 view，Control Move 只读取自身 `seal_basis` 指向的控制面 view；同一 ordered submit batch 的前序 Event 不会提前推进后续 Event 的授权基准。若同批内 revoke + 依赖该 grant 的 Event 同时到达，Policy Server fast-path cache MUST 按该 Event 的 CBA basis 评估，不得用同批后置 revoke 直接 deny；跨 Seal 延迟 revoke 仍按 §18 freshness fail closed。

> **取舍与残留风险（informative）**：上述例外意味着同一 CBA basis 下的并发 in-flight 操作不会被同批后置 revoke 阻断——actor 若能把"撤销前最后一批写入"与撤销自身塞进同一 batch / 同一 basis，这些写入会按撤销前 basis 通过。对依赖**即时**撤销的高风险 grant（如紧急吊销被盗 agent key），紧急 revoke 不能跨越本例外立即生效；此类场景 SHOULD 把相关 cell family 声明为 `sealed=true` 或走 sealed control override / fork quarantine 路径，使紧急 revoke 跨越 CBA basis 例外立即生效。该残留风险与 [`event-auth-state-resolution.md` §4.3](./event-auth-state-resolution.md) 的撤销新鲜度窗口取舍同源。

## 6. Failure Mode

`fail_mode`：

- `open`：策略服务不可用时继续基础授权。
- `soft_deny`：默认客户端阻止提交，但允许 proposal 或稍后重试。
- `quarantine`：可提交但进入 quarantine。
- `closed`：不可用时拒绝提交。

**缺省 fail-closed（normative）**：`ak.realm.policy_server` declaration 未显式声明 `fail_mode` 时，实现 **MUST** 按 `closed` 处理，**MUST NOT** 把缺省解释为 `open`，也 **MUST NOT** 把缺省解释为 `soft_deny`。`soft_deny` 作为 fail mode 只有在 `ak.realm.policy_server` declaration（或部署 profile）**显式声明** `fail_mode=soft_deny` 时才适用——显式声明本身即非"未声明"情形，故不与"缺省即 `closed`"冲突。任何把"未声明"等同 fail-open 的实现 MUST NOT 声明通过 v1 conformance——否则 Policy Server 宕机时全部内容风控（spam、malware_media、replay_suspect、rate_limit）会被静默跳过。

公共开放 Realm **MUST NOT** 使用 `open`；声明了 `open` 的公开 Realm declaration，reducer / receiver MUST 以 `schema_violation` 拒绝，或要求显式 break-glass + 审计声明后才接受。关键安全 Realm MAY 使用 `closed`，但必须提供人工 break-glass capability。

## 7. Relationship to Capability Authorization

Policy Server 不创建权限。事件必须先通过 capability authorization，再考虑 policy decision。即：

- 无 capability + policy allow = reject。
- 有 capability + policy hard_deny = reject 或 quarantine。
- 有 capability + policy unavailable = 按 fail_mode。

Policy Server MAY 执行 Realm 级与组织级的 blocklist、allowlist、rate limit、滥用声誉与内容风险标签。除非 holder 明确使用其自控的私有 policy 服务，Policy Server MUST NOT 检查个人 blocklist。

### 7.0 两套 resource selector kind 词表（normative）

协议存在**两套独立的 resource selector kind 词表**，适用范围不同，MUST NOT 互相套用：

| 词表 | 权威源 | kind 集合 | 适用范围 |
| --- | --- | --- | --- |
| **Capability resource selector** | [`resource-selector.schema.json`](../../artifacts/schemas/resource-selector.schema.json) / [`resource-selector-grammar.md`](./resource-selector-grammar.md) §3.1 | 18 项：`realm` / `space` / `circle` / `strand` / `message` / `morph` / `object` / `relation` / `view` / `event` / `actor` / `schema` / `policy` / `invite` / `notification` / `read_cursor` / `blob` / `*` | capability grant 的 `resources[]`，表达细粒度授权 scope。 |
| **Policy rule resource** | [`policy.schema.json`](../../artifacts/schemas/policy.schema.json) `rule.resource[].kind` | 5 项：`realm` / `strand` / `space` / `object` / `service` | 与 capability 词表部分重叠：前四项取自 capability 词表并在 policy 层收窄；`service` 是 policy 专属治理 kind。 |

适用规则：

- Policy rule 的 `resource[].kind` **MUST** 取自上表 5 项词表。在 policy rule 中误用 capability-only kind（如 `message` / `circle` / `notification` / `read_cursor` / `morph` / `relation` / `view` / `invite` 等）MUST 被 schema 拒绝（`policy.schema.json` 的 `enum` 不含它们），实现 MUST NOT 在本地放宽该 enum。
- 需要比 5 项粒度更细的对象级治理时，policy rule MUST 用 `kind:"object"` + `ref`（canonical object id）表达，而不是新增 capability-only kind。
- 两套词表**不统一**是有意设计：capability 词表面向细粒度授权，policy 词表面向粗粒度治理；实现 MUST NOT 把 capability selector 的 kind 当作 policy rule 的合法 kind，policy rule 校验只能接受上表 5 项词表。

### 7.1 Moderation State 必须进入控制面

Policy Server decision 是 out-of-band 的签名决策，本身不进入 Realm Seal 覆盖集。只有 `allow` 与 `soft_deny`（仅阻止 default client 提交）可以仅在本地或 fast path 上生效；任何会改变其他 peer 对事件可见性、可写性、可分发性判断的 decision——`hard_deny`、`quarantine`、`require_review`——MUST 通过 Control Move 写入控制面并由 accepted Seal 覆盖。否则不同 Principal Server 在同一 Realm 上对同一事件作出不一致决策，会形成跨 peer 的 split-brain：A 把消息 quarantine 隐藏，B 直接 allow，两边客户端看到的 Realm 状态从此分叉。

为此 v1 引入 `ak.component.moderation_state.v1` cell family：

- `cell_family = ak.component.moderation_state.v1`
- `cell_subject` = `payload.target_ref` 的 canonical 字符串；`target_ref` 可指向 event 或 object，但 reducer MUST 只从这一单字段派生 cell subject，避免同一目标因别名字段分裂成不同 cell。
- `lattice = or_set`，`bottom = expose`。每个 add tag 形如 `<decision_kind>:<issuer_did>:<request_canonical_digest>`，确保不同 issuer 的同类决策可以并存且幂等。

对应 wire event：

- `ak.moderation.decision` — 由持有 `ak.realm.moderation_policy` 或 `ak.policy.manage` 的 actor 签发的 Control Move，在 `ak.component.moderation_state.v1:<target>` control cell 上写一个 `or_set add` effect。
- `ak.moderation.decision.lift` — 在同一 cell 上写 `or_set remove` effect，针对此前 add 的 tag。
- 两者的 `refs[role=authorized_by]` SHOULD 引用对应 Policy Server signed decision（role=`policy_decision`）作为风险决策证据；该 ref 不参与签名校验等价性，仅用于审计和回放。Policy Server signed decision 本身不是 capability 来源——签发 Control Move 的 actor 必须独立持有 `ak.realm.moderation_policy` 或 `ak.policy.manage`。

Reducer 与所有读路径 MUST：

- 在控制面 Control Move 被 accepted Seal 覆盖后把 moderation state cell 的当前 value 暴露给后续 Control Move precondition、DataEvent 授权判定与 query / projection executor。
- 对包含 `quarantine` / `hard_deny` 决策的目标，禁止派生层（search、inbox、notification、view）按未 quarantine 处理；命中时返回 `moderated_hidden` 占位符或省略，并保留 audit trail。
- 对包含 `require_review` 决策的目标，按 review proposal 状态机展示，不允许默认渲染。
- `ak.moderation.decision.lift` 解除决策时，受影响的 search / projection cache MUST 立即重算。

**多 decision fold（normative）**：`ak.component.moderation_state.v1` 是 OR-Set，多个 active add 是正常值。对当前路径适用的 entries 必须按 [`content-moderation.md` §2.6](../governance/content-moderation.md#26-moderation-决策-must-sealed) 的封闭收紧序 `hard_deny > quarantine > require_review > none` 求 effective verdict；同级多 entry 幂等合并并保留全部审计来源。实现不得把普通多 entry 集合误判为 split，也不得用 HLC / 到达顺序选一个 issuer。active `require_review` add 同时是 pending-review 真相源，其 allow / quarantine / hard-deny 解除路径必须使用该节规定的原子 lift / replacement batch。

Policy Server fast path 与 sealed control decision 的关系：

- Fast path 上，Policy Server 返回 `quarantine` / `hard_deny` 后，origin Principal Server SHOULD **同步** 提交 `ak.moderation.decision` Control Move。Control Move 提交前 origin 节点 MAY 本地隐藏目标作为优化，但**不得**以 fast-path 决策永久代替 sealed control decision。
- 若 origin 节点 24 小时内（或 Realm policy 声明的更短窗口）未能把 fast-path quarantine 提升为 sealed control decision，处理方式 MUST 按未能提升的根因分类，不得对所有失败统一静默解除：
  - **(a) 传输 / 可用性类**——Seal issuer unreachable、`temporarily_unavailable`、控制面 fork quarantine、提交超时等纯可达性故障：窗口到期后 MUST 解除本地隐藏并退回到 sealed control state 实际值。这避免单一 origin 在 Seal 故障期间无限期隔离他人内容。**但自动退回 allow 前，origin MUST 产出可验证的不可达证据**——即按 [`event-auth-state-resolution.md` §7.2](./event-auth-state-resolution.md) 的 receipt SLA 超时证明 / censorship evidence（如对 Seal issuer 的签名提交回执缺失证明、超时计时锚定到 frontier 的可验证记录），并把该证据写入 moderation history trail（§7.1 "Fast-path 退回的协议通知规则" 的独立 moderation history）。仅凭 origin **自报**"传输失败"而无可验证证据时，MUST NOT 享受本（a）类自动退回 allow，而 MUST 按下方（b）类升级为 `require_review`（或保持隐藏并向 Realm 审核方告警）。这避免恶意 origin 通过谎报"传输失败"把一条本应进入 sealed control 的隔离决策静默漂白成 allow。
  - **(b) reducer 主动拒绝类**——Control Move 被 reducer 以 capability / 权限原因拒绝（例如 origin actor 失去 `ak.realm.moderation_policy` capability，或 `failed_precondition` 源于授权 / 前置条件不成立而非传输故障）：此时窗口到期 SHOULD 升级为 `require_review`，或保持隐藏并向 Realm 审核方告警，**不得**静默解除本地隐藏。理由是该类失败表明决策的授权基础本身存疑，静默解除会让一条可能合规的审核意图被悄悄丢弃。实现 MUST 能区分这两类原因（传输 / 可用性 vs reducer 授权拒绝），并据此选择解除或升级 / 保持隐藏。
- Receiver 节点收到 fast-path quarantine signaling（Policy Server 签名）但无对应 sealed Control Move 时，MAY 临时隐藏目标作为风险缓解，但 MUST 在 query / projection / sync surface 中把该目标标记为 `moderation_control_pending`，并在 sealed decision 抵达后按 sealed control state 重新投影。GUI 客户端、CLI、bot 或审计消费者如何呈现该状态属于产品层；协议只要求状态可见、可订阅且不被误投影为最终 sealed decision。

**Fast-path 退回的协议通知规则**：当 fast-path quarantine 因 24h 升级失败而被解除时，receiver MUST：

- 在 query / projection / sync surface 中发布 `reason_code=moderation_control_lifted` 与受影响 object refs，使已观察该 Realm 的订阅者能把本地 `moderation_control_pending` 状态切换为 sealed control state 的当前值。
- 在独立 moderation history trail 中保留 `quarantine_attempted_at`、`lifted_at`、`reason` 与可验证的退回证据；该 trail 不是普通 message redaction history。
- 若部署提供 push / notification binding，MAY 使用平台支持的更新或撤回机制发送 revocation hint；该 hint 是 transport-specific optimization，不得作为 sealed control state 的唯一真相源，也不得重新发送原始通知。
- audit / search / projection 应从那一刻起按 sealed control state 重建受影响 view；缓存中曾被 fast-path 隐藏的 entry MUST 立即失效。

### 7.2 错误码与 reason_code 扩展

引入 sealed moderation control state 后，`reason_code` 集合扩展：

- `moderation_control_pending` — fast-path quarantine 已记录，但 sealed Control Move 未到达。
- `moderation_control_lifted` — 此前 sealed quarantine 已被 `ak.moderation.decision.lift` 解除。
- `moderation_control_split` — moderation cell 在当前 control view 下出现真正不可 join 的损坏状态（例如同一 add identity 对应不同 canonical bytes、remove provenance 无法验证或 registry/lattice 证据不一致）；所有引用该 cell 的 read / write / distribute / policy-check 路径 MUST fail closed，`reason="moderation_state_conflict"`，query / projection / sync surface MUST 暴露冲突状态而不得默默选 winner。普通 OR-Set 多 active entries **不是** split，必须按 §7.1 的 deterministic strictest fold 处理。

## 8. Antifraud Mapping from Server Abuse Practice

服务端中对“开放联邦入口”“垃圾泛滥”“地址枚举”“内容扫描”“重放放大”的常见防护可直接映射到策略服务：

- **反开放联邦入口**：来自未声明 `source.service_id` 的联邦请求先降级到 `rate_limited` 或 `soft_deny`，只有在策略显式 allowlist 后才恢复 normal allow。
- **反爆发**：策略决策返回中可携带 `rate_limit` `obligation`，要求源服务在 `next_retry_at` 之前退避。
- **反假源**：`source.signed_transport=true` 且 service key 可校验时可放行；未签名来源只能走更严格决策分支并写入审计。
- **反重放**：`request_id` 与 `request_canonical_digest` 一起构成 decision 缓存键；不同 payload 使用同一 `request_id` MUST 触发 `duplicate_conflict` 语义。
- **反钓鱼/内容滥发**：对媒体只传递 `content_digest`、`content_type`、扫描标签；需要二次确认的内容转为 `quarantine` 而非直接拒收。
- **反枚举**：对未授权目录查询与 join 探测使用统一错误码，不暴露存在性差异；这条规则同时应写入 directory/filter 层。

策略服务实现 SHOULD 引用 [server-threat-model.md](../security/server-threat-model.md) 中“3. 对照：协议内映射与处理”作为联邦威胁基线，并确保本地 policy decision 与本地 `capability/auth` 顺序一致。

## 9. Federation

跨域事件的 origin service MAY 附带 policy decision。接收方：

- MUST 验证 decision 签名。
- MAY 运行本地 Policy Server 再次检查。
- MUST 保留所有 hard_deny/quarantine decision 的 audit record。
- MUST NOT 因 origin policy allow 而跳过本地 capability/auth 验证。

## 10. Privacy

Policy Server 默认不是内容接收者。实现 MUST：

- 对 E2EE Realm 默认只发送 metadata。
- 对媒体默认发送 hash、MIME、尺寸、扫描标签，不发送原始 bytes。
- 对 handle、email、phone 等标识符使用 blinded token，除非用户或管理员明确授权。
- 在 audit log 中记录向 Policy Server 披露了哪些字段。
