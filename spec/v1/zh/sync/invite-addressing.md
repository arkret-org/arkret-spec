---
title: Invite Addressing and Principal Locator
status: candidate
normative: true
stability: v1
updated: 2026-09-20
see_also:
  - service-http-binding.md
  - third-party-invites.md
  - ../identity/identity-handles.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 模型

Realm invite 的基础寻址模型是：

```text
invite_delivery = invite_address + introduction_evidence
```

base v1 invite **MUST NOT** 依赖 `ak.find.directory.read.resolve_handle.v1(intent="invite" | "member_add")` 才能投递。Handle 是人类可读入口，不是邀请投递授权；实现不得把猜到的 `<localpart>:<domain>` 字符串自动升级成可投递邀请。用户 MAY 显式发布 handle 并允许 verified handle 作为 first-contact / invite 入口，但接收方仍必须把解析结果归约为 exact `account_id`、可验证 handle claim 与 `invite_receive_policy` 判定。

邀请目标的规范输入是显式 `invite_address`：

```json fragment
{
  "account_id": {
    "principal_id": "ak:did_core:webvh:z2dmjBobExample",
    "station_id": "ak:did_core:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc"
  },
  "service_resolution": {
    "resolution_url": "https://ps.bob.example/_arkret/open/services/ak%3Adid_core%3Awebvh%3AzGiUQcWG9yy3Z9pMs15w7JHgc/resolution"
  }
}
```
| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `account_id` | `AccountId` | MUST | 被邀请 holder 的完整账号身份；`principal_id` 与 `station_id` 均不可省略或由上下文推断。 |
| `service_resolution` | `service_resolution_carrier` | MUST | `account_id.station_id` 的首跳路由材料；形态必须是完整 method evidence 的 `inline`，或 `resolution_url` 发现线索。 |

`account_id.station_id` 在 v1 中只表示托管该账号的 Station。它 **MUST NOT** 指向 Realm governance Station、push gateway、Directory 或任意第三方服务，除非该服务恰好也是该账号的托管 Station。客户端 MUST 从显式 AccountId 取得目标 Station，MUST NOT 从当前 session、URL 或 DID Document 补齐账号身份。

invite/locator 必须携带 `service_resolution` 作为发现载体。可选 transport-only `route_assistance.mirror_hints[]` 最多四项，每项包含 mirror service 的 `did_core_id` 和独立 `service_resolution_carrier`。镜像只能转交目标 DID 方法证据，不能自行授权目标入口。该对象不改变 invite 的业务授权或 exact invitee AccountId，接收方 MAY 忽略。

使用 `route_assistance` 时仍必须执行 [`service-surface.md` §2.6](./service-surface.md) 的独立方法验证、新鲜度及网络安全规则。提示不授予权限，不得扩展为部署级镜像列表或披露完整成员列表；locator/token 到期不延长路由缓存，缓存也不延长 token。

## 2. Introduction Evidence

每个私有 invite delivery request **MUST** 携带 `introduction_evidence`，说明邀请方为什么可以尝试联系被邀请方。schema 见 [`invite-delivery-request.schema.json`](../../artifacts/schemas/invite-delivery-request.schema.json)。`same_station` 不是可发送的 evidence 分支；它只能由接收端从已验身份派生。

| `kind` | 信任强度 | 说明 |
| --- | --- | --- |
| `locator_ref` | 高 | 被邀请方主动生成 / 交付的在线 locator ref。默认推荐。 |
| `consent_grant` | 高 | 邀请者出示被邀请方主动签发给邀请者的 `ak.consent.grant`(scope `invite` 或 `any`)的 `consent_grant_ref`。信任来源与 `locator_ref` 同构:都是被邀请方主动交付给邀请者的授权材料。已是联系人(互授 invite consent)拉群走此 kind,**无需 locator URL**。 |
| `shared_realm` | 高 | 邀请者与被邀请者已经同在某个 Realm；接收方按本地 policy 判断该 Realm 是否可信。 |
| `handle_claim` | 发现信任 | 邀请者通过 verified handle claim 找到 exact `account_id`。它证明 holder 或受信 issuer 将某 handle 披露为可解析入口，但**不**证明 holder 已同意该邀请者联系自己。默认 SHOULD quarantine 或 drop；只有 subject policy 与部署约束都允许时才可 notify。 |
| `same_station` | 中 / 部署相关 | receiver-only 分类：已验 invite Event 的 `actor_id` 必须是 account Actor，且其 `account_id.station_id` 与 `invite_address.account_id.station_id` 逐字相等。sender 不携带此 evidence。 |
| `explicit_address` | 弱 | 邀请者只提供 `account_id + service_resolution`；等价于“我知道或猜测这个地址及其可验证首跳材料”。默认 SHOULD quarantine 或 drop。 |

`explicit_address` 是合法但最低信任 evidence。接收方 **MUST NOT** 因为请求格式正确就通知用户；必须先应用 subject 私有 `invite_receive_policy`。

引入信任分档(normative):**高信任档** = `{locator_ref, consent_grant, shared_realm}`;**发现信任档** = `{handle_claim}`;**低信任档** = `{same_station, explicit_address, 无 / 非法 evidence}`。该分档同时决定 §5 的分级披露行为。

`consent_grant` evidence 的接收方验证:`consent_grant_ref` 指向的 `ak.consent.grant` 在被邀请方(`invite_address.account_id`)的 consent typed current result 中仍是 active grant dot，且 `peer == inviter`、`consent_scope ∈ {invite, any}`、未过期未撤销。验证通过即按高信任处理。`consent_grant_ref` 校验失败时，接收方 MUST 降级按 `explicit_address`(低信任)处理，MUST NOT 因为携带了 evidence 字段就放行。

`InviteAddress` 唯一收件身份是 `account_id`。`handle_claim` evidence 的接收方验证：`handle_claim.claim.handle == evidence.handle`，`handle_claim.claim.subject_account_id` MUST 精确等于 `invite_address.account_id`，`handle_claim.status=verified`，`as_of < fresh_until` 且当前时刻仍在该 signed freshness window 内，`claim.expires_at` 未过期，`claim.proofs[0..1]` 与顶层 `evidence` 均有效，`revocation` 为 null，且 `claim.issuer_id` / Directory / `claim.visibility` / `claim.audience` 满足该账号的 policy 与部署约束。任何校验失败 MUST 降级按低信任 explicit address 处理；不得从 handle、DID Document 或当前服务补齐 AccountId 分量。

## 3. 在线 Principal Locator

二维码 / 链接默认承载在线 locator ref，不承载完整 signed locator。

### 3.1 认证发行、轮换与撤销

locator 只能由 subject 当前 Station 的认证 self surface 管理；客户端不得自行铸造 token。v1 定义：

| operation | HTTP binding | 语义 |
| --- | --- | --- |
| `ak.self.invite_locator.command.issue.v1` | `POST /_arkret/self/invite-locators` | 为 session actor 发行新 locator。body 可含 `ttl_seconds`（默认 900，范围 60..3600）、`one_time_use`（默认 false）与可选 `display_hint`。`account_id` 与当前 `service_resolution` 均由服务端从认证 session、本机 service identity 和已验证 route record 推导，MUST NOT 由客户端提交。 |
| `ak.self.invite_locator.command.rotate.v1` | `POST /_arkret/self/invite-locators/rotate` | 在同一 durable transaction 中撤销 `locator_id` 指向的旧 locator 并返回全新 locator/token。旧 locator 不存在、已撤销、已消费或不属于 session actor 时 MUST 返回 `not_found`，不得替调用方泄露归属或状态。 |
| `ak.self.invite_locator.command.revoke.v1` | `POST /_arkret/self/invite-locators/revoke` | 撤销属于 session actor 的 locator；对同一已撤销 locator 的重复请求是 idempotent success。不存在、不属于 actor 或已消费的 locator 返回 `not_found`。 |

issue / rotate 的成功响应是 `principal-locator.schema.json#/$defs/invite_locator_issue_outcome`，其中 `locator_token` 是以 CSPRNG 生成、至少含 192 bit 熵且只返回一次的 bearer secret；响应 MUST 携带 `Cache-Control: private, no-store`，服务端 MUST NOT 持久化 raw token，任何中间层也不得缓存响应体。revoke 成功响应是 `#/$defs/invite_locator_revoke_outcome`；同一 AccountId 对已撤销 locator 的重试 MUST 返回首次撤销记录的原始 `revoked_at`，不得用重试时刻改写它。这些 self operation 使用普通 session + PoP 写认证；locator 归属绑定 principal account，而不是某个 device/session，因此同一 AccountId 的其它有效 session MAY 轮换或撤销它。

服务端 durable locator record MUST 至少保存：`locator_id`、`token_digest`（唯一索引）、`account_id`、`service_resolution`、`issued_at`、`expires_at`、`one_time_use`、`display_hint?`、`revoked_at?`、`consumed_at?`。`token_digest` MUST 使用 `sha256:<lowercase_hex>`，raw token MUST NOT 出现在数据库、audit log、analytics、crash report 或 durable event。resolve 成功时，返回的签名 `principal_locator.locator_ref_digest` MUST 精确等于该 record 的 `token_digest`，且 `account_id`、`service_resolution`、有效期与 `display_hint?` 必须从同一 record 派生，不得信任 resolve 调用方输入这些字段。每个 exact AccountId 同时 active locator 的 v1 上限为 16；达到上限时 issue MUST fail closed（`rate_limited` 或 `failed_precondition`），不得隐式撤销调用方未指定的 locator。

rotate 必须是“发行新 token + 原子撤销旧 token”，不另设 refresh alias；客户端点击刷新时调用 rotate，并用返回的新 token 替换进程内显示值。rotate 省略 `ttl_seconds` 时 MUST 保留旧 record 的已授予 lifetime（`expires_at - issued_at`），省略 `one_time_use` 时 MUST 保留旧值，省略 `display_hint` 时 MUST 保留旧 hint；仅显式 `display_hint:null` 清除 hint，避免普通刷新静默扩大可用性或丢失展示信息。若 rotate 的 transport outcome 不确定，客户端 MUST NOT 直接调用 issue：它必须先对旧 `locator_id` 调用幂等 revoke，取得成功或可确认的终态，使旧 token 确定失效，再以 fresh request 调用 issue；首次 rotate 若已提交但响应丢失，其不可恢复的新 token 只作为短 TTL orphan 等待过期。`one_time_use=true` 时，resolve 在读取 record、检查 TTL/撤销/策略并准备成功响应的同一原子操作中写入 `consumed_at`；并发 resolve 最多一个成功。消费是 resolve 的内部状态迁移，不定义独立公开 consume operation。

### 3.2 OOB handoff 与 resolve

推荐 QR / link 文本：

```text
https://ps.bob.example/_arkret/open/invite-locators/resolve#token=<locator_token>
```

扫描方客户端读取 fragment 后，向同一 origin 提交：

```text
POST /_arkret/open/invite-locators/resolve
```

body：

```json fragment
{
  "locator_token": "base64url-token-with-at-least-128-bit-entropy"
}
```
`locator_token` **MUST** 只通过 JSON body 或等价 signed proof 提交，**MUST NOT** 出现在 URL path、query string、Referer、普通 access log、analytics、crash report、local storage 或浏览器历史中。客户端读取 fragment 后 **MUST** 清理地址栏与本地临时状态。

token 要求：

- `locator_token` SHOULD 是不透明 server-side handle；服务端私有状态保存 `account_id`、`service_resolution`、TTL、撤销状态与接收策略。
- `locator_token` MUST 至少 192 bit 熵（与 §3.1 签发要求同一数值，不存在更低的验收下界）；base64url 无 padding 编码时 192 bit 为 32 字符。
- `locator_token` MUST NOT 是明文可解码的 `base64url(JSON)`，也不得在 token 明文中携带 `account_id`、`expires_at`、策略状态或其它可识别 invitee 的材料。若部署需要 stateless token，payload MUST 先做 authenticated encryption；调用方仍只把它当 opaque bearer secret。
- token MUST be unguessable、可撤销、可设置短 TTL，并 MAY 设置一次性使用。
- endpoint 对不存在、过期、撤销、策略拒绝的对外响应 MUST byte-identical 或等价不可区分（含 status / body / headers）；timing 侧信道按 [`conformance/conformance-vectors.md`](../conformance/conformance-vectors.md) `ak.vector.invite.failure_indistinguishable.v1`（§9.7）收口（timing 差异 SHOULD ≤ 50ms，高安全 profile MUST 用 jitter / padding）。仅服务端 audit log MAY 记录具体 reason_code。
- endpoint 返回体 MUST 是签名 `principal_locator`；调用方不能只信任 HTTPS URL。

## 4. `principal_locator`

`principal_locator` 是被邀请方 Station 返回的、可验证的 invite address assertion。schema id 为 `ak.schema.principal_locator.v1`。

最小形态：

```json fragment
{
  "schema": "ak.schema.principal_locator.v1",
  "account_id": {
    "principal_id": "ak:did_core:webvh:z2dmjBobExample",
    "station_id": "ak:did_core:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc"
  },
  "service_resolution": {
    "resolution_url": "https://ps.bob.example/_arkret/open/services/ak%3Adid_core%3Awebvh%3AzGiUQcWG9yy3Z9pMs15w7JHgc/resolution"
  },
  "issued_at": "2026-06-07T10:00:00Z",
  "expires_at": "2026-06-07T10:15:00Z",
  "locator_ref_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "proofs": [
    {
      "proof_purpose": "recipient_service_acceptance",
      "proof": {
        "kind": "detached_jws",
        "verification_method": "did:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc:ps.bob.example#server-key-1",
        "payload_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "created_at": "2026-06-07T10:00:00Z",
        "jws": "..."
      }
    }
  ]
}
```
验证规则：

1. `account_id` MUST 是完整 closed AccountId；`service_resolution` MUST 对应 `account_id.station_id`。
2. recipient-service proof 的已验证 signer service DID MUST 等于 `account_id.station_id`；holder proof 若出现，其已验证 principal core MUST 等于 `account_id.principal_id`，且签名覆盖完整 AccountId。
3. `locator_ref_digest` 绑定私有 locator ref material；raw token 不得写入 Realm durable event。
4. `proof.payload_digest` MUST 覆盖 `canonical_json(principal_locator_without_proofs)`。
5. `proofs[]` MUST 至少包含 `recipient_service_acceptance`；高安全 / audited / enterprise 部署 SHOULD 同时要求 `subject_locator_authorization`。
6. verifier MUST 验证 `service_resolution` 得到当前方法验证后的 `AuthenticatedServiceResolution`，确认 `service_id == account_id.station_id`、`project(normalized_did_document.did) == account_id.station_id`、freshness 与 endpoint binding。Station MUST 仅为经认证 self operation 选定的同一 AccountId 签发 locator；holder proof 的附加要求仍按第 5 步执行，不得用独立 delivery-binding 对象补齐 AccountId。

`principal_locator` 不是 membership grant，也不是 invite accept proof。它只证明该 exact AccountId 与 Station service resolution 的寻址关系。

## 5. 接收策略

被邀请方 Station 按 subject 私有 `invite_receive_policy` 决定哪些 evidence 可以通知用户。schema id 为 `ak.schema.invite_receive_policy.v1`。

```json fragment
{
  "schema": "ak.schema.invite_receive_policy.v1",
  "account_id": {
    "principal_id": "ak:did_core:webvh:z2dmjBobExample",
    "station_id": "ak:did_core:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc"
  },
  "holder_allowed_introduction_kinds": [
    "locator_ref",
    "consent_grant",
    "shared_realm",
    "handle_claim",
    "same_station"
  ],
  "handle_claim_behavior": "quarantine",
  "explicit_address_behavior": "quarantine",
  "unknown_invites": "drop",
  "consent_profile": "default",
  "new_source_quota": {
    "new_sources_per_window": 2,
    "new_sources_per_retention": 20
  },
  "allowed_handle_domains": [
    "bob.example"
  ],
  "trusted_handle_issuer_ids": [],
  "trusted_directory_ids": [],
  "trusted_realm_ids": [],
  "trusted_source_ids": [],
  "denied_source_ids": [],
  "denied_actor_ids": [],
  "disclosure": {
    "high_trust": "outcome",
    "discovery_trust": "opaque",
    "low_trust": "opaque"
  }
}
```
规则：

- **缺省 policy（subject 未发布 `invite_receive_policy` 时）MUST fail closed（normative）**：接收方 MUST 采用保守默认——`holder_allowed_introduction_kinds` 仅含**高信任档** `{locator_ref, consent_grant, shared_realm}`;**发现信任档** `{handle_claim}` 与**低信任档** `{same_station, explicit_address}` 默认 `quarantine`（SHOULD）或 `drop`，MUST NOT 仅凭 evidence 格式正确就触发用户通知。上方示例把 `handle_claim` 与 `same_station` 列入 allowlist，是 subject / 部署的显式可达性配置，**不是协议默认**;`same_station` 与 `explicit_address` 同属低信任档（§2），默认处置对称——不得让"同一 Station 上的任意账户"仅凭同域承载即向同域任意 subject 发起会触发通知的邀请（同域无授权骚扰开口）。
- `holder_allowed_introduction_kinds` 是 allowlist；未列出的 evidence MUST NOT 触发用户通知。`consent_grant` 是受推荐的高信任 kind:把它加入 allowlist 即允许"已互授 invite consent 的联系人"直接邀请，而无需 locator URL。
- `handle_claim_behavior` 取值为 `drop | quarantine | notify`；省略时 MUST 视为 `quarantine`。把 `handle_claim` 配为 `notify` 表示 holder 显式希望别人可通过已发布 handle 发起邀请通知；该选择仍受 §5.2 部署约束限制。实现 MUST NOT 把任何 connection identifier、未 verified handle、过期/revoked handle claim 或未授权 restricted handle 当成 `handle_claim` evidence。
- `explicit_address_behavior` 取值为 `drop | quarantine | notify`；默认 SHOULD 是 `quarantine` 或 `drop`。把低信任档 evidence（`same_station` / `explicit_address`）配为 `notify` 是部署对该档的显式放宽，MUST 经部署有意配置，不得作为缺省。
- `denied_handle_domains` 先于 allowlist 生效，命中时 MUST 按策略拒绝处理。`allowed_handle_domains` 若非空，`handle_claim.claim.handle` 的 domain MUST 是列表中的 canonical IDNA A-label 精确域名；子域名不自动继承，必须显式列出。`trusted_handle_issuer_ids` / `trusted_directory_ids` 若非空，`handle_claim.claim.issuer_id` 或 `resolved_by` MUST 命中对应 allowlist。
- `unknown_invites` 取值为 `drop | quarantine`；无 evidence 或不合规 evidence 不得默认 notify。
- `consent_profile` 取值为 `default | require_explicit_consent`；省略时 MUST 视为 `default`。它是 holder 对 [`../identity/consent-model.md` §6.1](../identity/consent-model.md) invite consent gate 强度的**唯一** carrier：`require_explicit_consent` 下只有第 7 步已验证的 `consent_grant` evidence 可以 notify，其余 evidence（含高信任档 `locator_ref` / `shared_realm`、`handle_claim`、`same_station`、`explicit_address` 与无 evidence）一律静默 `drop`——不 quarantine、不计 `new_source_quota`、不写任何 holder-private typed current result，且 §5.1 披露强制为 `opaque`（`status="deferred"`、无 `disclosed_outcome`），不受 `disclosure` / `disclosure_max` 影响。该字段是 subject 私有 state：不进入 `ServiceDescribe`，requester 与 peer Station MUST NOT 能观察；§5.2 部署约束没有对应字段——部署只能经行为上限与 `disclosure_max` 收紧，不能替 holder 选择 profile。它与 Realm 级 `preauth.consent_required` 相互独立。
- `new_source_quota` 是 holder 对"此前未见过的新来源 peer"进入 quarantine inbox 的私有上限，两个成员均为 integer ≥ 0，`0` 表示锁死新来源。它只能把 holder 变得更不可达：effective 值取subject 值与 §5.2 部署 `max_*` 中更小者，省略成员取部署 `default_*`。判定算法、identity key 与ledger 语义由 [`../identity/consent-model.md` §6.1.1](../identity/consent-model.md) 唯一定义；本字段只是它的 holder 侧 carrier，超限后的处置仍是同一 opaque `deferred`。
- `denied_actor_ids` 是按 exact peer ActorId 的黑名单；inviter 命中时，delivery MUST `drop`，且 §5.1 披露 MUST 强制为 `opaque`，以免黑名单经回包侧信道泄露。同 principal core 异 Station 的 account Actor 不得互相命中。`trusted_source_ids` / `denied_source_ids` 是另一独立维度，只匹配已认证 transport source service DID，不代表 inviter，也不得替代 `denied_actor_ids`。
- policy 是 exact AccountId 的私有 state，不得写入目标 Realm event log。`policy.account_id` MUST 等于认证 holder 的完整 AccountId；同 principal 在另一 Station 的 policy、consent、quarantine、设备与通知不得继承或合并。

### 5.1 分级披露(graded disclosure，normative)

`invite_receive_policy.disclosure` 决定 delivery outcome 回送给邀请者的结果粒度，按 §2 引入信任分档区分:

- `disclosure.high_trust`(默认 `outcome`):作用于高信任档 `{locator_ref, consent_grant, shared_realm}`。
- `disclosure.discovery_trust`(默认 `opaque`):作用于发现信任档 `{handle_claim}`。
- `disclosure.low_trust`(默认 `opaque`):作用于低信任档 `{same_station, explicit_address, 无 / 非法 evidence}`。

`disclosure_level` 语义:

- `opaque`:`invite_delivery_outcome` 只返回 generic `status`(`accepted | duplicate | deferred`),MUST NOT 携带 `disclosed_outcome`，且对 exists / not-exists / quarantine / drop 各情形不可区分。这是反枚举 / 反侧信道的默认。
- `outcome`:`invite_delivery_outcome` MAY 携带 `disclosed_outcome`，把真实处理结果告知邀请者。**`disclosed_outcome` 的封闭枚举只有 `delivered | blocked` 两值。**

**quarantine MUST NOT 被回送（normative）**：`disclosed_outcome` 的上界由 [`../identity/consent-model.md` §6.1.1](../identity/consent-model.md) 的不可区分 `MUST NOT` 决定。`delivered` 与 `blocked` 回答的是“这次投递是否被**接收方策略**放行”，属于本节设计意图内的反馈；而“invite 进入 holder quarantine inbox”回答的是 **holder 的 consent 决策尚未作出**——那是 consent-model §6.1 明确的 holder-private 状态，等价于回答“holder 未对该 requester 授予 active invite grant”。高信任档只说明 inviter 已知 holder 存在，泄露的不是 existence 而是 consent 状态，因此**不构成**可以回送的理由。

**quarantine 的 wire 落点固定为 `status="deferred"` 且不携带 `disclosed_outcome`**：`deferred` 与“正在重试投递”、“holder 侧尚未处理”共用同一语义，因而不构成对 quarantine 的可区分指示。该映射在所有信任档、所有 `disclosure` 取值下一致，不因 `high_trust=outcome` 而改变。

设计意图:对**已建立信任的来源**(已互授 invite consent 的联系人、对方主动给的 locator、已同在 Realm)，邀请被接收方策略拒绝时能给邀请者明确反馈，避免"联系人加不进却不知为何"的 UX 黑洞；对**可发现但未建立关系的来源**(handle_claim)与**陌生人**(explicit_address)默认保持不可区分。`denied_actor_ids` 命中者无论 disclosure 设置一律 `opaque`。`disclosure` 整体省略时按默认 `high_trust=outcome / discovery_trust=opaque / low_trust=opaque`。

### 5.2 部署接收约束（normative）

Station MAY 发布部署 / 管理员级 `receive_policy_constraints`。该对象是 subject 私有 `invite_receive_policy` 的**上限**，不是默认放宽项。有效接收策略按交集计算：

```text
effective_receive_policy =
  subject invite_receive_policy
  ∩ Station receive_policy_constraints
  ∩ applicable organization / realm policy constraints
```

约束规则：

- 部署约束只能让 subject 更不容易被联系，MUST NOT 把 subject 从更隐私的设置强制放宽为可通知。若 subject 选择 `drop`，管理员不能通过约束把结果提升为 `quarantine` 或 `notify`。
- `deployment_allowed_introduction_kinds` 与 `deployment_denied_introduction_kinds` 先于 subject allowlist 生效；任一约束拒绝的 evidence kind MUST 按 `drop` 或 indistinguishable policy denial 处理。
- 行为强度排序为 `drop < quarantine < notify`。`handle_claim_max_behavior`、`explicit_address_max_behavior` 与 `unknown_invites_max_behavior` 是上限；effective behavior 取 subject 行为与上限中更严格者。
- `disclosure_max` 是部署 / 管理员对 §5.1 分级披露粒度的上限，按 §2 引入信任分档给出 `{high_trust_max, discovery_trust_max, low_trust_max}`，取值同 `disclosure_level` 枚举（`opaque < outcome`，opaque 更保守）。字段或某档省略表示该档不设部署级披露上限。**effective disclosure 取 subject `invite_receive_policy.disclosure` 与 `disclosure_max` 中更保守（更接近 `opaque`）者**，使部署可以把 subject 自愿设为 `outcome` 的披露强制收紧为 `opaque`（反枚举 / 反侧信道），但 MUST NOT 把 subject 设为 `opaque` 的披露放宽为 `outcome`。该交集与上面的行为交集独立计算：先按行为上限定 drop / quarantine / notify，再按 `disclosure_max` 定 outcome 是否可回送。`denied_actor_ids` / `denied_source_ids` 命中时仍无条件强制 `opaque`，不受 `disclosure_max` 影响。
- `allowed_handle_domains`、`trusted_handle_issuer_ids`、`trusted_directory_ids`、`trusted_source_ids`、`accepted_subject_did_methods` 是部署级 allowlist；字段省略表示该维度不设部署级上限，字段存在且为空数组表示不接受该维度的任何候选。非空时必须命中。未命中 MUST 视为策略拒绝，不得通过响应区分“存在但被策略拒绝”和“不存在”。
- `denied_source_ids` 命中时 MUST `drop` 且强制 `opaque`。
- `applies_to` 是本对象**筛选面**的封闭列举，取值 `invite_delivery | contact_request`，省略等于两条全选。它只筛选 introduction-evidence 与分级披露类成员——`deployment_allowed_introduction_kinds`、`deployment_denied_introduction_kinds`、三个 `*_max_behavior`、`disclosure_max`，以及 handle domain / handle issuer / directory / source / DID method 各表。**`new_source_quota` 不受 `applies_to` 筛选**，见下一条。[`../identity/consent-model.md` §6.1.1](../identity/consent-model.md) 的 first-contact admission 面不携带 introduction evidence、也不参与 §5.1 分级披露，上述成员在该面上没有可筛选的对象，因此本枚举**不**为它新增取值。
- `new_source_quota` 是 [`../identity/consent-model.md` §6.1.1](../identity/consent-model.md) per-holder 新来源限速的**唯一**部署 carrier。字段与缺省：`window_seconds`（86400）、`default_new_sources_per_window`（3）、`max_new_sources_per_window`（10）、`retention_seconds`（2592000）、`default_new_sources_per_retention`（30）、`max_new_sources_per_retention`（200）。**省略该对象或任一字段不等于关闭 quota**，缺省即上表值；MUST 不变式 `max_* ≥ default_*` 与 `retention_seconds ≥ window_seconds` 由 validator 强制，违反者整个 constraints 对象以 `schema_violation` 拒绝。该 quota 与本节其它上限的交集独立计算：先按行为上限定 drop / quarantine / notify，命中 quarantine 后才在 admission chokepoint 执行 quota 判定。**该对象 MUST NOT 被 `applies_to` 筛选（normative）**：它是 [`../identity/consent-model.md` §6.1.1.3](../identity/consent-model.md) holder admission chokepoint 的阈值，invite delivery、contact delivery 与 consent request 三条面共用同一份 ledger 与同一组阈值，因此 `applies_to` 取何值都不改变它对三条面无条件生效。

示例：

```json fragment
{
  "policy_version": "2026-06-21",
  "applies_to": ["invite_delivery", "contact_request"],
  "deployment_allowed_introduction_kinds": [
    "locator_ref",
    "consent_grant",
    "shared_realm",
    "handle_claim"
  ],
  "handle_claim_max_behavior": "quarantine",
  "explicit_address_max_behavior": "drop",
  "new_source_quota": {
    "window_seconds": 86400,
    "default_new_sources_per_window": 3,
    "max_new_sources_per_window": 10,
    "retention_seconds": 2592000,
    "default_new_sources_per_retention": 30,
    "max_new_sources_per_retention": 200
  },
  "allowed_handle_domains": ["acme.example"],
  "trusted_handle_issuer_ids": ["ak:did_core:webvh:z43vHHHeh32Hnyv6t7X3t33Xs"],
  "trusted_directory_ids": ["ak:did_core:webvh:z43vHHHeh32Hnyv6t7X3t33Xs"],
  "accepted_subject_did_methods": ["did:webvh"]
}
```
## 6. Durable Event Boundary

`ak.invite.create` 是 Realm durable Event。genesis payload MUST 只携 exact `invitee_account_id`、`introduction_evidence_digest` 与 `expires_at`；Invite ID 从 Event ID 派生，MUST NOT 在 genesis payload 重复携带。
路由材料、locator token、raw `introduction_evidence` 与 `invite_receive_policy` MUST NOT 进入 durable payload。

```json fragment
{
  "invitee_account_id": {
    "principal_id": "ak:did_core:webvh:z2dmjBobExample",
    "station_id": "ak:did_core:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc"
  },
  "introduction_evidence_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "expires_at": "2026-06-14T10:00:00Z"
}
```
规则：

- `payload.invitee_account_id` MUST 与 `invite_address.account_id` 完整相等，不得只比较 principal。
- destination service 只从 `invitee_account_id.station_id` 派生；service resolution 与 route assistance 只在私有 transport carrier 中出现，MUST NOT 要求 durable Event 镜像它们。
- `introduction_evidence_digest = digest(canonical_json(private_delivery_introduction_evidence))`，用于审计关联，不得泄露 raw locator token。
- 普通定向邀请的取消 / 拒绝 MUST 使用 `ak.invite.cancel` 的 `invite_cancel_payload`：`invite_id`、与持久化目标完整相等的 `invitee_account_id`、`target_state` 及该 schema 允许的诊断字段。invitee 本人拒绝写入 `rejected`；inviter 或获授权管理 actor 撤销写入 `revoked`。reducer MUST 从 Invite 前态确认 exact invitee，第三方/token placeholder 或缺少 invitee 的前态 MUST 以 `failed_precondition` / `invite_kind_requires_revoke` 原子拒绝；不得信任请求补出的身份。该 Event 只推进 Invite lifecycle，不写 `member.state`。
- `ak.invite.revoke` 使用独立 `invite_revoke_payload`，只推进 Invite lifecycle；指向尚未绑定账号的 3PID placeholder 时 MUST NOT 携带 `invitee_account_id`。取消或撤销不会合成 membership `leave` 写入。完整终态规则见 [`governance-objects.md` §5.3](../models/governance-objects.md)。

## 7. 私有 Invite Delivery

客户端在 `ak.invite.create` 被邀请方 Station 接受后，必须把 raw
`introduction_evidence` 交给邀请方 Station 启动私有投递：

```text
POST /_arkret/self/invites/dispatch
operation_id = ak.self.invites.command.dispatch.v1
```

请求 body 使用 `ak.schema.invite_delivery_request.v1#/$defs/self_invite_dispatch_request_body`，只携
`schema=ak.schema.invite_delivery_request.v1`、`invite_event_id`、`invite_address`、`introduction_evidence` 与 `idempotency_key`。服务端 MUST 以
`invite_event_id` 读取自己已接受并持久化的 canonical Event bytes；客户端不得回声、代签、重新 author
或重建该 Event。两条前置的拒绝语义是封闭的：Event 未被本服务接受 MUST
`failed_precondition` / `invite_event_unaccepted`；持久化 Event 的签署者不等于当前认证 session actor
MUST `failed_precondition` / `invite_event_actor_mismatch`。两类拒绝 MUST NOT 产生任何投递、outbox
入队或 holder-private 写入。由于 self wire 不再承载 Event bytes，不存在客户端 Event bytes
不一致的协议分支。

这个 self operation 只接受 raw evidence 并启动投递，不把它写入 Realm history。目标
`invite_address.account_id.station_id` 等于本机 service id 时，服务端 MUST 从下述接收验证的**第 4 步**开始执行同一套
验证、receive policy 与 holder-private projection；第 1–3 步是 service-to-service 专属绑定，本地分支
MUST 以"已认证 self session + 上述两条 accepted-event 前置"作为等价绑定，MUST NOT 合成 federation
trust header、伪造 peer session 或自签 S2S 认证材料来走 peer 路径。本地已接受 Event 的 producer / admission 验证可以复用其准入结果；两条投递分支均不重放 Realm 授权闭包，也不依赖接收方持有 Realm 状态。目标为其它 Station 时，服务端 MUST 用持久化 Event 与请求中的寻址和 introduction evidence 构造 exact canonical request body，
交给下述 peer operation，并以 body 内 `idempotency_key` 绑定 durable retry / outbox。客户端在投递结果不确定时 MUST 用同一 body 与同一 `idempotency_key`
重试，不得替换 evidence 或 `invite_event_id`。

邀请方 Station 使用：

```text
POST /_arkret/peer/invites
operation_id = ak.peer.invites.command.submit.v1
```

request body 为 `ak.schema.invite_delivery_request.v1`。接收方 Station MUST：

1. 验证 service-to-service authentication，绑定 Source/Destination service `did_core_id`、trust domain、Content-Digest 与 idempotency key；接收方从已验证的 exact canonical body bytes 内部计算 request digest。
2. 验证 `Destination-Service-ID == invite_address.account_id.station_id`。
3. 验证 `invite_address.service_resolution`，要求完整证据的 `service_id` 等于 `invite_address.account_id.station_id`、adapter 投影 `project(did)` 等于该 `did_core_id`，并校验 freshness、service kind 与实际 target URL；carrier 不能单独授权投递。
4. 验证 invite_event.kind 为 ak.invite.create、内容绑定的 Event / Invite ID、Realm ID、producer 签名、可携带的 producer signer evidence 与原始授权。验证必须复用现有 Event proof 合同，从请求携带闭包或本地已验证缓存重算 `signer_resolution_evidence_ref` 并解析 exact producer key；不得相信发送者自报公钥、仅使用 Source-Service-ID，或要求账号原站在线。first-contact receiver 缺少闭包成员时只能 pending，并可按通用 dependency resolution 从任一获授权且能提供精确 content-addressed 对象的来源补齐；来源身份不进入 Event 授权结果。保留目标、有效期及重放约束。
   投递仅证明已认证发送者发出邀请，**不验证或宣称**其 Realm 管理权限、成员资格或邀请 durable acceptance。接收方 MUST NOT 为投递求值成员级 Realm 授权闭包、要求本地 accepted RealmCommit 或获取 Realm peer dependencies。请求不承载邀请专用 authority-commit bundles；普通 authority-commit、RealmCommit 签名和 signer authority 准入规则保持不变。正常加入 / 同步负责 Realm 授权及 durable acceptance，投递不得物化 Realm、membership、accepted RealmCommit、projection 或 checkpoint。
   本步在 holder 查询、policy、consent、quota 与任何写入之前执行。结构错误返回 schema_violation，无效签名或 proof 绑定返回已注册的 signature_invalid；请求体仍受现有 8 MiB 上限约束。未能验证的 authority ref 不得作为任何可信状态或授权依据。
5. 验证 `invite_event.payload.invitee_account_id == invite_address.account_id`，必须比较完整 AccountId。
6. 验证 durable invite Event 未携带独立 route material；可选 `route_assistance` 只存在于 delivery transport，MUST NOT 要求它写入或匹配 durable Event，也 MUST NOT 把它当作授权证据。
7. 验证 `introduction_evidence`，并核对 `introduction_evidence_digest`。`consent_grant` 必须是 exact invitee AccountId 给 inviter 的 active `invite` / `any` grant dot；`handle_claim` 必须逐字绑定 `invite_address.account_id`、issuer / Directory trust、domain allowlist、expiry 与 audience。分类顺序固定为：有效高信任 evidence，其次有效 `handle_claim`，其次接收端派生 `same_station`，最后 `explicit_address`。派生 `same_station` 只比较已验 invite Event account Actor 的 `account_id.station_id` 与 `invite_address.account_id.station_id`，不得使用 `Source-Service-ID` 或实际 ingress service。证据无效且不满足同 Station 时降级为低信任 `explicit_address`，不得直接通知或物化 membership。
8. 计算 effective receive policy:先取 subject 私有 `invite_receive_policy`，再与 §5.2 `receive_policy_constraints` 及适用组织 / Realm 约束求交集。随后查 `denied_actor_ids`（与已验 invite Event 的完整 inviter ActorId 精确匹配；命中即 `drop` 且强制 opaque）与 `denied_source_ids`；再按 effective `holder_allowed_introduction_kinds`、`handle_claim_behavior`、`explicit_address_behavior`、`unknown_invites` 决定 drop / quarantine / notify。若 subject `invite_receive_policy.consent_profile = require_explicit_consent` 且第 7 步分类结果不是已验证 `consent_grant`，MUST 在此静默 `drop` 并强制 opaque——不 quarantine、不执行 quota 判定、不写任何 holder-private typed current result（[`../identity/consent-model.md` §6.1](../identity/consent-model.md) step 2）。判定为 quarantine 时，MUST 在写 quarantine typed current result 之前于 admission chokepoint 执行 [`../identity/consent-model.md` §6.1.1](../identity/consent-model.md) 的 per-holder 新来源 quota 判定（effective 值来自本节 subject `new_source_quota` 与 §5.2 部署 `new_source_quota` 的交集）；超限即静默丢弃，不写 ledger、不写 typed current result，且与本节其它不可区分情形返回同一 opaque outcome。
9. 返回 receive outcome:按 §5.1 分级披露。发现信任档、低信任档或 `denied_actor_ids` 命中时默认返回 generic `status`(opaque),MUST NOT 通过响应泄露 subject 是否存在或策略如何处理；高信任档且 `disclosure.high_trust=outcome` 时 MAY 在 `disclosed_outcome` 回送真实结果(`delivered | blocked` 两值)。仅当 subject 与部署约束都允许 `disclosure.discovery_trust=outcome` 时，`handle_claim` MAY 回送真实结果。**invite 进入 holder quarantine inbox 时，无论信任档与 `disclosure` 取值，一律返回 `status="deferred"` 且 MUST NOT 携带 `disclosed_outcome`**，并与“限速静默丢弃 / 超时丢弃 / holder 不存在 / holder policy deny”落在同一响应与 timing 等价类（[`../identity/consent-model.md` §6.1.1](../identity/consent-model.md)）；`require_explicit_consent` profile 下的静默 drop 是该等价类的「holder policy deny」成员，同样只返回 `status="deferred"` 且无 `disclosed_outcome`。

notify 分支的 holder-private 投递承载是 account-data 私有 typed current result，key 为 `ak.account.invite_delivery`（登记于 [`account-data-key-registry.json`](../../artifacts/registry/account-data-key-registry.json)）。typed current result value 是**明文** JSON，MUST 符合 `ak.schema.invite_delivery.v1`（[`invite-delivery.schema.json`](../../artifacts/schemas/invite-delivery.schema.json)），不是 `ak.schema.account_data_encrypted_value.v1` envelope：该 typed current result 由接收方 Station 在投递路径写入，服务端无法产出 holder 客户端加密的 envelope；`invite_token` 本就是服务端基础设施签发并持有的私有 locator，明文存储不改变其信任边界。value 外层为 `schema` / `updated_at` / `delivery_entries[]`，每个 entry 携带 `invite_id` / `realm_id` / `inviter_account_id` / `invite_token` / `authority_locator_hints` / `received_at` / `expires_at`；`inviter_account_id` 必须逐字复制已接受 Invite Event 的完整账号，不能只存 principal 后猜 Station。`authority_locator_hints` 直接引用 `ak.schema.realm_join_candidate.v1`，必须有 1..8 项、按 `service_id` UTF-8 bytes 严格升序且以该 id 语义唯一；locator 不复制 `realm_id` 或时间，scope 与有效期只取 enclosing delivery entry。invite 未过期或 endpoint 可达都不能替代 nonce-bound current assertion。

写入语义是封闭的：

- 该 typed current result 是 [`../models/account-data.md` §5](../models/account-data.md) 的 server-versioned CAS whole-value register：每次写入携带 `expected_server_revision`，冲突时写入方 MUST 重读当前值、按本节规则重新合并后重试，重试 MUST 有界（至多 3 次）；重试耗尽 MUST 放弃本次投递写入并以内部冲突失败，MUST NOT 以 stale revision 强行覆盖。
- 每次写入 MUST 先清除 `expires_at <= now` 的过期 entry，再按 `invite_id` 去重（同一 `invite_id` 的重复投递替换旧 entry，不重复占位），随后 append 新 entry；结果超过 200 条上限时 MUST 从 `received_at` 最旧的 entry 开始逐出，直至不超过 200 条。
- entry 的 `expires_at` MUST 取自 invite Event payload 的 `expires_at`；payload 未携带时服务端 MUST 以该 Event 的 `created_at` 加 7 天兜底。`expires_at <= now` 的 entry 是 stale 的：客户端 MUST NOT 用它执行 accept，并 MUST 在读取时按 `expires_at` 过滤。
- 写入被 CAS 接受时，服务端 MUST 在同一事务推进 account subscribe 的 Station-CAS 投影位置，使 holder 的全部 active devices 可通过顶层 `account_data.station_cas` 的 cursor-covered upsert 取得 accepted revision/value；删除使用显式 remove。服务端 MAY 另以 `ak.account_data.update` actor-private device update 做低延迟唤醒，该 envelope 使用 `DeviceMessageSender::Service { sender_id }` 分支：`recipient_account_id == holder`，`sender_id` 等于 `recipient_account_id.station_id` 与当前接收 Station 的 service identity；该分支不携 `sender_account_id`，不伪造 origin device，不走 holder device revocation gate，也不排除任一 active holder device。to-device 不是权威投影；离线或错过它的设备从 account subscribe baseline/catch-up 恢复，list/get 只作诊断与定点恢复。CAS 冲突或其它未接受写入不得推进投影或 fanout。
- private delivery material（含 `invite_token`）MUST NOT 物化到 Invite 对象或任何 Realm state（[`../models/governance-objects.md` §5.3](../models/governance-objects.md)）；该 typed current result 是 directed invite token 送达被邀请方设备的唯一规范私有承载。

### 7.1 定向邀请的加入前预览（normative）

被邀请方在接受前查看 Realm 的**唯一来源**是已验证邀请中的完整 `inviter_account_id.station_id`。被邀请者自己的
Station、另一成员 Station、Realm governance Station、独立 Directory 与实际投递使用的 `Source-Service-ID` MUST NOT 替代该身份；
同一 principal 在不同 Station 上的账号不可互换。Station 固定的是 service 身份而不是永不变化的 URL：端点发现、
方法证据与新鲜度复用现有 `AuthenticatedServiceResolution`，同一 service 合法更新端点不改变来源，失联 MUST NOT
通过替换服务身份兜底。

调用方式固定为**自己的 Station 代理并验证**：

- 客户端只调用 `ak.self.realm_join.read.preview.v1`（`POST /_arkret/self/realm-joins/preview`）。请求体是 closed
  `realm-join-intake.schema.json#/$defs/self_preview_request_body`，字段依次为 `request_id`、`account_id`、`target`。
  `account_id` MUST 逐字等于已认证会话的完整账号，其 Station MUST 是本服务。
- `target.selector = "invite"` 时，字段逐字取自 §7 的 `ak.account.invite_delivery` entry（`realm_id`、`invite_id`、
  `inviter_account_id`、`invite_token`），Station MUST 只向该 `inviter_account_id.station_id` 取预览。
  该 Station 就是本服务时，MUST 走等价的本地路径，MUST NOT 合成 federation trust header 或自签 S2S 材料。
  其余 selector 走 Directory 发现输入面，由本 Station 独立验证后才成为结果。
- 远端分支使用 `ak.peer.realm_join.read.preview.v1`（`POST /_arkret/peer/realm-joins/preview`）。请求体只携
  `request_id`、`realm_id`、`requester_account_id`、`invite_id`、`invite_token`。调用方 MUST 使用 §3.2 的服务间认证
  并绑定 Source/Destination service DID、trust domain 与 Content-Digest，且 `Destination-Service-ID` 等于
  `inviter_account_id.station_id`、`requester_account_id.station_id` 等于 `Source-Service-ID`。
  **MUST NOT 透传被邀请者的本地 bearer / session 凭据**，也 MUST NOT 用它换取任意来源的读取。

持有方 Station MUST：

1. 在自身**已接受状态**中定位 exact `invite_id`，核对 `invite_token`、邀请逐字绑定 `requester_account_id` 的完整
   AccountId、未过期且未撤销；
2. 求值 effective `ak.realm.preview_policy` 的 `audiences` 是否覆盖该 invited audience，并只按其 `fields` 披露；
3. 返回 closed `peer_preview_outcome`，逐字回显 `request_id`、`realm_id`、`requester_account_id`、`invite_id`，
   并给出 `preview`、`observed_at`、`expires_at`。响应 MUST NOT 回显 `invite_token`，MUST NOT 携带
   `join_candidates`、`source_refs`、`stale` 或 `divergent`，也 MUST NOT 携带正文历史、成员列表、policy 原文、
   隐藏 edge 或 E2EE 明文。

策略允许但没有可披露内容时，MUST 返回只含必填成员的最小 `preview`，MUST NOT 因此扩张读取。未知 Realm、未知或
不匹配的邀请、非该被邀请者的 Station、已撤销／过期凭据以及 Realm 未声明有效 preview policy，MUST 共用一个与
不存在不可区分的失败，并按 §3.2 同口径固定 timing bucket。来源不可达是可重试的上游失败，MUST NOT 换源。

自己的 Station 返回 closed `self_preview_outcome`：逐字回显 `request_id`、`account_id`，给出解析后的 canonical
`realm_id`、绑定本次 target 的 `request_digest`、披露来源 `source`（`inviter_station` / `local` / `directory`）、
`preview`、`observed_at` 与 `expires_at`。客户端 MUST 只核对目标、用途、请求与来源绑定后展示；MUST NOT 直连
来源 Station、MUST NOT 选择转发候选，也 MUST NOT 把预览当作 membership、加入承诺或已验证的 Realm 治理。
预览成功不产生任何加入副作用；正式加入仍走 [`federation.md` §5.3](./federation.md) 与加入准备合同。
邀请本身不保证存在名称或头像；`title` / `avatar_blob_ref` / `summary` 等只是策略许可后的展示信息。

## 8. Describe Capabilities

支持 invite addressing 的 Station MUST 广告能展开出下列精确 `http_json` pair 的 registered operation bundle：

- `ak.self.invite_locator.command.issue.v1`
- `ak.self.invite_locator.command.rotate.v1`
- `ak.self.invite_locator.command.revoke.v1`
- `ak.self.invites.command.dispatch.v1`
- `ak.open.invite_locator.read.resolve.v1`
- `ak.peer.invites.command.submit.v1`

它同时 MUST 在 `supported_features[]` 声明 `ak.feature.invite_addressing.v1`，并在 registered `invite_addressing` 字段给出可协商能力：

```json fragment
{
  "invite_addressing": {
    "supported_introduction_kinds": [
      "locator_ref",
      "consent_grant",
      "shared_realm",
      "handle_claim",
      "same_station",
      "explicit_address"
    ],
    "handle_claim_max_behavior": "quarantine",
    "explicit_address_max_behavior": "drop"
  },
  "receive_policy_constraints": {
    "policy_version": "2026-06-21",
    "applies_to": ["invite_delivery", "contact_request"],
    "deployment_allowed_introduction_kinds": [
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
Directory 服务若支持 handle lookup，也 MAY 在 `ServiceDescribe` 或 `ak.find.directory.read.describe.v1` 的扩展字段中声明：

```json fragment
{
  "x_handle_resolution": {
    "invite_enabled": false,
    "member_add_enabled": false
  }
}
```
base clients MUST NOT require `resolve_handle(intent="invite" | "member_add")` to create or deliver an invite.

## 9. Handle 与 Mention 边界

`ak.find.directory.read.resolve_handle.v1(intent="contact_request" | "invite" | "member_add")` 是可选 Directory 能力，不是 base first-contact / invite / member-add 的安全关键路径。Directory 只可返回逐字绑定 exact AccountId 的可验证 handle claim；reducer 仍 MUST 按 Join Policy 验证 target holder acceptance，不能把解析成功当作 membership。

Realm 内 mention 不依赖公网 handle resolve。客户端在用户输入 `@alice:acme.example` 时 MUST 先从当前 Realm roster、MemberIdentity subject disclosure、内联 signed `handle_claims[]` 或本地已授权 claim cache 中解析到 `subject_account_id`。发送 Message 前必须持久化 DID-committed mention reference；handle 字符串只能作为 audit / search metadata。

已知 `subject_account_id` 需要显示当前 handle 时，客户端 MAY 使用 roster 内联 `handle_claims[]` 或 `ak.find.directory.read.list_handles_for_subject.v1`。这条 subject -> current handles 路径不得反向用来发现未知主体、发起 invite delivery 或构造 membership grant；只有 holder/issuer 已发布 verified handle claim，且 subject policy 与部署约束允许 `handle_claim` evidence 时，客户端才可把 handle 解析结果作为 first-contact / invite 的 introduction evidence。
