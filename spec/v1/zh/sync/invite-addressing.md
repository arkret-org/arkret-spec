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

base v1 invite **MUST NOT** 依赖 `ak.find.directory.read.resolve_handle(intent="invite" | "member_add")` 才能投递。Handle 是人类可读入口，不是邀请投递授权；实现不得把猜到的 `<localpart>:<domain>` 字符串自动升级成可投递邀请。用户 MAY 显式发布 handle 并允许 verified handle 作为 first-contact / invite 入口，但接收方仍必须把解析结果归约为 `subject_id`、可验证 handle claim 与 `invite_receive_policy` 判定。

邀请目标的规范输入是显式 `invite_address`：

```json
{
  "subject_id": "ak:did_core:webvh:z2dmjBobExample",
  "recipient_service_id": "ak:did_core:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc",
  "service_resolution": {
    "current_record_url": "https://ps.bob.example/_arkret/open/services/ak%3Adid_core%3Awebvh%3AzGiUQcWG9yy3Z9pMs15w7JHgc/resolution"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `subject_id` | `did_core_id` | MUST | 被邀请 principal / holder 的稳定业务身份；不是可直接解析的 DID。 |
| `recipient_service_id` | `did_core_id` | MUST | 接收 invite delivery 的 Principal Server 稳定 service identity。 |
| `service_resolution` | `service_resolution_carrier` | MUST | `recipient_service_id` 的首跳路由材料；形态必须是完整 signed record 的 `inline`，或 `current_record_url` 加可选 `pinned_record_digest`。 |
| `recipient_service_kind` | const | MAY | 若出现，MUST 等于 `principal_server`；默认省略。 |

`recipient_service_id` 在 v1 中只表示 Principal Server。它 **MUST NOT** 指向 notary、shared Principal Server sync surface、push gateway、Directory 或任意第三方服务。将来如果需要组织、群组或其它接收服务形态，必须定义独立 locator / delivery schema，不得把 `recipient_service_kind` 扩成宽枚举后复用本 schema。

invite/locator 的权威首跳仍是必填 current `service_resolution`；它不得只携 future notice 或 mirror hint。schema MAY 允许一个可选、transport-only 的 `route_assistance`：其中 `handover_notice` 最多一份，必须是该 `recipient_service_id` 的完整 target-signed active `ServiceRouteHandoverNotice`；`mirror_hints[]` 最多四项，每项只含 mirror service `did_core_id` 及其独立 `service_resolution_carrier`，不得含 mirror 自签的 target URL。该对象不进入 `ak.invite.create` 的授权语义，不替代 `invite_delivery_target`，接收方 MAY 忽略。

使用 `route_assistance` 时仍必须执行 [`service-surface.md` §2.6](./service-surface.md) 与 [`federation.md` §6.4](./federation.md)：notice 只能在 basis/time window 匹配时引导取得正式 successor；mirror hint 只有在 requester/target 的 Realm-scoped 授权独立成立时才能查询。invite/locator token 的到期时间不能延长 record、notice 或 mirror carrier 的有效期，notice 或 mirror 也不能延长 token；任一组成部分到期都按自己的边界 fail closed。为避免披露 Realm topology，producer 只能列出 signed invite 与 inviter 当前 member delivery binding 已向 invitee Principal Server 授权的有界路由提示，不得附完整成员列表。

## 2. Introduction Evidence

每个私有 invite delivery request **MUST** 携带 `introduction_evidence`，说明邀请方为什么可以尝试联系被邀请方。schema 见 [`invite-delivery-request.schema.json`](../../artifacts/schemas/invite-delivery-request.schema.json)。

| `kind` | 信任强度 | 说明 |
| --- | --- | --- |
| `locator_ref` | 高 | 被邀请方主动生成 / 交付的在线 locator ref。默认推荐。 |
| `consent_grant` | 高 | 邀请者出示被邀请方主动签发给邀请者的 `ak.consent.grant`(scope `invite` 或 `any`)的 `consent_grant_ref`。信任来源与 `locator_ref` 同构:都是被邀请方主动交付给邀请者的授权材料。已是联系人(互授 invite consent)拉群走此 kind,**无需 locator URL**。 |
| `shared_realm` | 高 | 邀请者与被邀请者已经同在某个 Realm；接收方按本地 policy 判断该 Realm 是否可信。 |
| `handle_claim` | 发现信任 | 邀请者通过 verified handle claim 找到 `subject_id`。它证明 holder 或受信 issuer 将某 handle 披露为可解析入口，但**不**证明 holder 已同意该邀请者联系自己。默认 SHOULD quarantine 或 drop；只有 subject policy 与部署约束都允许时才可 notify。 |
| `same_principal_server` | 中 / 部署相关 | 双方由同一个 Principal Server 承载；适合组织或个人同域场景。 |
| `explicit_address` | 弱 | 邀请者只提供 `subject_id + recipient_service_id + service_resolution`；等价于“我知道或猜测这个地址及其可验证首跳材料”。默认 SHOULD quarantine 或 drop。 |

`explicit_address` 是合法但最低信任 evidence。接收方 **MUST NOT** 因为请求格式正确就通知用户；必须先应用 subject 私有 `invite_receive_policy`。

引入信任分档(normative):**高信任档** = `{locator_ref, consent_grant, shared_realm}`;**发现信任档** = `{handle_claim}`;**低信任档** = `{same_principal_server, explicit_address, 无 / 非法 evidence}`。该分档同时决定 §5 的分级披露行为。

`consent_grant` evidence 的接收方验证:`consent_grant_ref` 指向的 `ak.consent.grant` 在被邀请方(`invite_address.subject_id`)的 consent cell 中仍是 active grant dot，且 `peer == inviter`、`consent_scope ∈ {invite, any}`、未过期未撤销。验证通过即按高信任处理。`consent_grant_ref` 校验失败时，接收方 MUST 降级按 `explicit_address`(低信任)处理，MUST NOT 因为携带了 evidence 字段就放行。

`handle_claim` evidence 的接收方验证: `handle_claim.handle == evidence.handle`，`handle_claim.subject == invite_address.subject_id`，`binding_state=verified`，`expires_at` 未过期，`proofs[]` 有效，issuer / Directory / visibility / audience 满足 subject policy 与部署约束。若 handle claim 携带 `member_delivery_binding`，还 MUST 校验 `handle_claim.member_delivery_binding.recipient_service_id == invite_address.recipient_service_id`；若 evidence 携带 `member_delivery_binding_candidate`，还 MUST 校验 `candidate.subject_id == invite_address.subject_id`、`candidate.handle == evidence.handle`、`candidate.member_delivery_binding.recipient_service_id == invite_address.recipient_service_id`、`candidate.intent == "invite"`、`audience` 匹配当前邀请上下文且 proof 有效。任何校验失败 MUST 降级按 `explicit_address` 处理，MUST NOT 因为 handle 字符串可解析就通知用户。

## 3. 在线 Principal Locator

二维码 / 链接默认承载在线 locator ref，不承载完整 signed locator。

### 3.1 认证发行、轮换与撤销

locator 只能由 subject 当前 Principal Server 的认证 self surface 管理；客户端不得自行铸造 token。v1 定义：

| operation | HTTP binding | 语义 |
| --- | --- | --- |
| `ak.self.invite_locator.command.issue` | `POST /_arkret/self/invite-locators` | 为 session actor 发行新 locator。body 可含 `ttl_seconds`（默认 900，范围 60..3600）、`one_time_use`（默认 false）与可选 `display_hint`。`subject_id`、`recipient_service_id` 与当前 `service_resolution` 均由服务端从认证 session、本机 service identity 和已验证 route record 推导，MUST NOT 由客户端提交。 |
| `ak.self.invite_locator.command.rotate` | `POST /_arkret/self/invite-locators/rotate` | 在同一 durable transaction 中撤销 `locator_id` 指向的旧 locator 并返回全新 locator/token。旧 locator 不存在、已撤销、已消费或不属于 session actor 时 MUST 返回 `not_found`，不得替调用方泄露归属或状态。 |
| `ak.self.invite_locator.command.revoke` | `POST /_arkret/self/invite-locators/revoke` | 撤销属于 session actor 的 locator；对同一已撤销 locator 的重复请求是 idempotent success。不存在、不属于 actor 或已消费的 locator 返回 `not_found`。 |

issue / rotate 的成功响应是 `principal-locator.schema.json#/$defs/invite_locator_issue_outcome`，其中 `locator_token` 是以 CSPRNG 生成、至少含 192 bit 熵且只返回一次的 bearer secret；响应 MUST 携带 `Cache-Control: private, no-store`，服务端 MUST NOT 持久化 raw token，任何中间层也不得缓存响应体。revoke 成功响应是 `#/$defs/invite_locator_revoke_outcome`；同一 principal 对已撤销 locator 的重试 MUST 返回首次撤销记录的原始 `revoked_at`，不得用重试时刻改写它。这些 self operation 使用普通 session + PoP 写认证；locator 归属绑定 principal account，而不是某个 device/session，因此同一 principal 的其它有效 session MAY 轮换或撤销它。

服务端 durable locator record MUST 至少保存：`locator_id`、`token_digest`（唯一索引）、`subject_id`、`recipient_service_id`、`service_resolution`、`issued_at`、`expires_at`、`one_time_use`、`display_hint?`、`revoked_at?`、`consumed_at?`。`token_digest` MUST 使用 `sha256:<lowercase_hex>`，raw token MUST NOT 出现在数据库、audit log、analytics、crash report 或 durable event。resolve 成功时，返回的签名 `principal_locator.locator_ref_digest` MUST 精确等于该 record 的 `token_digest`，且 `subject_id`、`recipient_service_id`、`service_resolution`、有效期与 `display_hint?` 必须从同一 record 派生，不得信任 resolve 调用方输入这些字段。每个 subject 同时 active locator 的 v1 上限为 16；达到上限时 issue MUST fail closed（`rate_limited` 或 `failed_precondition`），不得隐式撤销调用方未指定的 locator。

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

```json
{
  "locator_token": "base64url-token-with-at-least-128-bit-entropy"
}
```

`locator_token` **MUST** 只通过 JSON body 或等价 signed proof 提交，**MUST NOT** 出现在 URL path、query string、Referer、普通 access log、analytics、crash report、local storage 或浏览器历史中。客户端读取 fragment 后 **MUST** 清理地址栏与本地临时状态。

token 要求：

- `locator_token` SHOULD 是不透明 server-side handle；服务端私有状态保存 `subject_id`、`recipient_service_id`、`service_resolution`、TTL、撤销状态与接收策略。
- `locator_token` MUST 至少 192 bit 熵（与 §3.1 签发要求同一数值，不存在更低的验收下界）；base64url 无 padding 编码时 192 bit 为 32 字符。
- `locator_token` MUST NOT 是明文可解码的 `base64url(JSON)`，也不得在 token 明文中携带 `subject_id`、`recipient_service_id`、`expires_at`、策略状态或其它可识别 invitee 的材料。若部署需要 stateless token，payload MUST 先做 authenticated encryption；调用方仍只把它当 opaque bearer secret。
- token MUST be unguessable、可撤销、可设置短 TTL，并 MAY 设置一次性使用。
- endpoint 对不存在、过期、撤销、策略拒绝的对外响应 MUST byte-identical 或等价不可区分（含 status / body / headers）；timing 侧信道按 [`conformance/conformance-vectors.md`](../conformance/conformance-vectors.md) `ak.vector.invite.failure_indistinguishable.v1`（§9.7）收口（timing 差异 SHOULD ≤ 50ms，高安全 profile MUST 用 jitter / padding）。仅服务端 audit log MAY 记录具体 reason_code。
- endpoint 返回体 MUST 是签名 `principal_locator`；调用方不能只信任 HTTPS URL。

## 4. `principal_locator`

`principal_locator` 是被邀请方 Principal Server 返回的、可验证的 invite address assertion。schema id 为 `ak.schema.principal_locator.v1`。

最小形态：

```json
{
  "schema": "ak.schema.principal_locator.v1",
  "subject_id": "ak:did_core:webvh:z2dmjBobExample",
  "recipient_service_id": "ak:did_core:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc",
  "service_resolution": {
    "current_record_url": "https://ps.bob.example/_arkret/open/services/ak%3Adid_core%3Awebvh%3AzGiUQcWG9yy3Z9pMs15w7JHgc/resolution"
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

1. `subject_id` 是被邀请主体的 `did_core_id`；`recipient_service_id` 是接收 invite delivery 的 Principal Server service `did_core_id`；`service_resolution` 是与后者匹配的首跳 carrier。
2. `recipient_service_kind` 若出现 MUST 等于 `principal_server`。
3. `locator_ref_digest` 绑定私有 locator ref material；raw token 不得写入 Realm durable event。
4. `proof.payload_digest` MUST 覆盖 `canonical_json(principal_locator_without_proofs)`。
5. `proofs[]` MUST 至少包含 `recipient_service_acceptance`；高安全 / audited / enterprise 部署 SHOULD 同时要求 `subject_locator_authorization`。
6. verifier MUST 验证 `service_resolution` 得到当前 signed `ServiceResolutionRecord`，确认 `record.service_id == recipient_service_id`、`project(record.full_id) == recipient_service_id`、freshness 与 endpoint binding；若缺少 `subject_locator_authorization`，还 MUST 通过 account binding 或 service delegation 证明该 service `did_core_id` 有权代表 `subject_id` 发布 locator。

`principal_locator` 不是 membership grant、不是 invite accept proof、不是 `member_delivery_binding`。它只证明“可以把这次邀请投递给这个 Principal Server 处理”。

## 5. 接收策略

被邀请方 Principal Server 按 subject 私有 `invite_receive_policy` 决定哪些 evidence 可以通知用户。schema id 为 `ak.schema.invite_receive_policy.v1`。

```json
{
  "schema": "ak.schema.invite_receive_policy.v1",
  "subject_id": "ak:did_core:webvh:z2dmjBobExample",
  "holder_allowed_introduction_kinds": [
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
  "denied_principal_services": [],
  "denied_subjects": [],
  "disclosure": {
    "high_trust": "outcome",
    "discovery_trust": "opaque",
    "low_trust": "opaque"
  }
}
```

规则：

- **缺省 policy（subject 未发布 `invite_receive_policy` 时）MUST fail closed（normative）**：接收方 MUST 采用保守默认——`holder_allowed_introduction_kinds` 仅含**高信任档** `{locator_ref, consent_grant, shared_realm}`;**发现信任档** `{handle_claim}` 与**低信任档** `{same_principal_server, explicit_address}` 默认 `quarantine`（SHOULD）或 `drop`，MUST NOT 仅凭 evidence 格式正确就触发用户通知。上方示例把 `handle_claim` 与 `same_principal_server` 列入 allowlist，是 subject / 部署的显式可达性配置，**不是协议默认**;`same_principal_server` 与 `explicit_address` 同属低信任档（§2），默认处置对称——不得让"同一 Principal Server 上的任意账户"仅凭同域承载即向同域任意 subject 发起会触发通知的邀请（同域无授权骚扰开口）。
- `holder_allowed_introduction_kinds` 是 allowlist；未列出的 evidence MUST NOT 触发用户通知。`consent_grant` 是受推荐的高信任 kind:把它加入 allowlist 即允许"已互授 invite consent 的联系人"直接邀请，而无需 locator URL。
- `handle_claim_behavior` 取值为 `drop | quarantine | notify`；省略时 MUST 视为 `quarantine`。把 `handle_claim` 配为 `notify` 表示 holder 显式希望别人可通过已发布 handle 发起邀请通知；该选择仍受 §5.2 部署约束限制。实现 MUST NOT 把任何 connection identifier、未 verified handle、过期/revoked handle claim 或未授权 restricted handle 当成 `handle_claim` evidence。
- `explicit_address_behavior` 取值为 `drop | quarantine | notify`；默认 SHOULD 是 `quarantine` 或 `drop`。把低信任档 evidence（`same_principal_server` / `explicit_address`）配为 `notify` 是部署对该档的显式放宽，MUST 经部署有意配置，不得作为缺省。
- `denied_handle_domains` 先于 allowlist 生效，命中时 MUST 按策略拒绝处理。`allowed_handle_domains` 若非空，`handle_claim.handle` 的 domain MUST 是列表中的 canonical IDNA A-label 精确域名；子域名不自动继承，必须显式列出。`trusted_handle_issuers` / `trusted_directory_services` 若非空，issuer 或 `resolved_by` MUST 命中对应 allowlist。
- `unknown_invites` 取值为 `drop | quarantine`；无 evidence 或不合规 evidence 不得默认 notify。
- `denied_subjects` 是按 peer subject DID 的黑名单(对等 `denied_principal_services` 的服务粒度)。inviter 命中时，delivery MUST `drop`，且 §5.1 披露 MUST 强制为 `opaque`，以免黑名单经回包侧信道泄露。
- policy 是 subject/private state，不得写入目标 Realm event log。

### 5.1 分级披露(graded disclosure，normative)

`invite_receive_policy.disclosure` 决定 delivery outcome 回送给邀请者的结果粒度，按 §2 引入信任分档区分:

- `disclosure.high_trust`(默认 `outcome`):作用于高信任档 `{locator_ref, consent_grant, shared_realm}`。
- `disclosure.discovery_trust`(默认 `opaque`):作用于发现信任档 `{handle_claim}`。
- `disclosure.low_trust`(默认 `opaque`):作用于低信任档 `{same_principal_server, explicit_address, 无 / 非法 evidence}`。

`disclosure_level` 语义:

- `opaque`:`invite_delivery_outcome` 只返回 generic `status`(`accepted | duplicate | deferred`),MUST NOT 携带 `disclosed_outcome`，且对 exists / not-exists / quarantine / drop 各情形不可区分。这是反枚举 / 反侧信道的默认。
- `outcome`:`invite_delivery_outcome` MAY 携带 `disclosed_outcome`，把真实处理结果告知邀请者。**`disclosed_outcome` 的封闭枚举只有 `delivered | blocked` 两值。**

**quarantine MUST NOT 被回送（normative）**：`disclosed_outcome` 的上界由 [`../identity/consent-model.md` §6.1.1](../identity/consent-model.md) 的不可区分 `MUST NOT` 决定。`delivered` 与 `blocked` 回答的是“这次投递是否被**接收方策略**放行”，属于本节设计意图内的反馈；而“invite 进入 holder quarantine inbox”回答的是 **holder 的 consent 决策尚未作出**——那是 consent-model §2.1 / §6.1.2 明确的 holder-private 状态，等价于回答“holder 未对该 requester 授予 active invite grant”。高信任档只说明 inviter 已知 holder 存在，泄露的不是 existence 而是 consent 状态，因此**不构成**可以回送的理由。

**quarantine 的 wire 落点固定为 `status="deferred"` 且不携带 `disclosed_outcome`**：`deferred` 与“正在重试投递”、“holder 侧尚未处理”共用同一语义，因而不构成对 quarantine 的可区分指示。该映射在所有信任档、所有 `disclosure` 取值下一致，不因 `high_trust=outcome` 而改变。

设计意图:对**已建立信任的来源**(已互授 invite consent 的联系人、对方主动给的 locator、已同在 Realm)，邀请被接收方策略拒绝时能给邀请者明确反馈，避免"联系人加不进却不知为何"的 UX 黑洞；对**可发现但未建立关系的来源**(handle_claim)与**陌生人**(explicit_address)默认保持不可区分。`denied_subjects` 命中者无论 disclosure 设置一律 `opaque`。`disclosure` 整体省略时按默认 `high_trust=outcome / discovery_trust=opaque / low_trust=opaque`。

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
- `deployment_allowed_introduction_kinds` 与 `deployment_denied_introduction_kinds` 先于 subject allowlist 生效；任一约束拒绝的 evidence kind MUST 按 `drop` 或 indistinguishable policy denial 处理。
- 行为强度排序为 `drop < quarantine < notify`。`handle_claim_max_behavior`、`explicit_address_max_behavior` 与 `unknown_invites_max_behavior` 是上限；effective behavior 取 subject 行为与上限中更严格者。
- `disclosure_max` 是部署 / 管理员对 §5.1 分级披露粒度的上限，按 §2 引入信任分档给出 `{high_trust_max, discovery_trust_max, low_trust_max}`，取值同 `disclosure_level` 枚举（`opaque < outcome`，opaque 更保守）。字段或某档省略表示该档不设部署级披露上限。**effective disclosure 取 subject `invite_receive_policy.disclosure` 与 `disclosure_max` 中更保守（更接近 `opaque`）者**，使部署可以把 subject 自愿设为 `outcome` 的披露强制收紧为 `opaque`（反枚举 / 反侧信道），但 MUST NOT 把 subject 设为 `opaque` 的披露放宽为 `outcome`。该交集与上面的行为交集独立计算：先按行为上限定 drop / quarantine / notify，再按 `disclosure_max` 定 outcome 是否可回送。`denied_subjects` / `denied_principal_services` 命中时仍无条件强制 `opaque`，不受 `disclosure_max` 影响。
- `allowed_handle_domains`、`trusted_handle_issuers`、`trusted_directory_services`、`trusted_principal_services`、`accepted_subject_did_methods` 是部署级 allowlist；字段省略表示该维度不设部署级上限，字段存在且为空数组表示不接受该维度的任何候选。非空时必须命中。未命中 MUST 视为策略拒绝，不得通过响应区分“存在但被策略拒绝”和“不存在”。
- `denied_principal_services` 命中时 MUST `drop` 且强制 `opaque`。

示例：

```json
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
  "allowed_handle_domains": ["acme.example"],
  "trusted_handle_issuers": ["ak:did_core:webvh:z43vHHHeh32Hnyv6t7X3t33Xs"],
  "trusted_directory_services": ["ak:did_core:webvh:z43vHHHeh32Hnyv6t7X3t33Xs"],
  "accepted_subject_did_methods": ["did:webvh"]
}
```

## 6. Durable Event Boundary

`ak.invite.create` 是 Realm durable event。它可以携带可公开审计的 delivery target 与 evidence digest，但不得携带 locator token、raw `introduction_evidence` 或 `invite_receive_policy`。

```json
{
  "invite_id": "ak:invite:Abj5gHx39exHIgzuk86fNT8bpu2gCRDb7GNYroQrpLi_",
  "invitee": "ak:did_core:webvh:z2dmjBobExample",
  "invite_delivery_target": {
    "recipient_service_id": "ak:did_core:webvh:zGiUQcWG9yy3Z9pMs15w7JHgc",
    "service_resolution": {
      "current_record_url": "https://ps.bob.example/_arkret/open/services/ak%3Adid_core%3Awebvh%3AzGiUQcWG9yy3Z9pMs15w7JHgc/resolution"
    }
  },
  "introduction_evidence_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "expires_at": "2026-06-14T10:00:00Z"
}
```

Rules:

- `payload.invitee` MUST equal `invite_address.subject_id`.
- `payload.invite_delivery_target.recipient_service_id` MUST equal `invite_address.recipient_service_id`.
- `payload.invite_delivery_target.service_resolution` MUST 与 `invite_address.service_resolution` 逐字节相等；接收方仍须独立验证其指向或内联的 signed record，不得把 carrier 当作授权。
- `payload.invite_delivery_target.recipient_service_kind` MAY appear; if present, it MUST be `principal_server`.
- `introduction_evidence_digest = digest(canonical_json(private_delivery_introduction_evidence))`，用于审计关联，不得泄露 raw locator token。
- 普通定向邀请的取消 / 拒绝 MUST 使用 `ak.invite.cancel`，payload 使用 `invite_cancel_payload`：`invite_id`、与目标 invite 逐字节相等的 `invitee`、`target_state`，以及可选 `reason`。被邀请者本人提交时表示拒绝并写入 `rejected`；邀请者或 Realm 管理 actor 提交时表示撤销尚未接受的 pending invite 并写入 `revoked`。reducer MUST 先从持久化 Invite 前态确认 `invitee` 存在；第三方/token invite 或无 `invitee` 前态必须以 `failed_precondition` / `invite_kind_requires_revoke` 拒绝，不能信任请求补出的 `invitee`。同一 Move 的 registered reducer contract MUST 同时投影 `member.state:<invitee>` 的 `invite -> leave`，见 [`../models/governance-objects.md` §5.3](../models/governance-objects.md)。
- `ak.invite.revoke` MUST 用于第三方/token invite 的撤销或等价高风险撤销路径，payload 使用同一引用形态；指向定向 DID invite 时 `invitee` 必填并原子写入 `invite -> leave`，指向尚无 DID 主体的 3PID placeholder 时不得携带 `invitee`、也不得写 member cell。reducer MUST 将 live invite 写入对应终态，并清除可认领 token material。直接 DID 邀请不需要通过 `ak.invite.revoke` 才能从成员管理 UI 撤销。

## 7. 私有 Invite Delivery

客户端在 `ak.invite.create` 被邀请方 Principal Server 接受后，必须把 raw
`introduction_evidence` 交给邀请方 Principal Server 启动私有投递：

```text
POST /_arkret/self/invites/dispatch
operation_id = ak.self.invites.command.dispatch
```

请求 body 使用 `ak.schema.invite_delivery_request.v1#/$defs/self_invite_dispatch_request`，只携
`invite_event_id`、`invite_address`、`introduction_evidence` 与 `idempotency_key`。服务端 MUST 以
`invite_event_id` 读取自己已接受并持久化的 canonical Event bytes；客户端不得回声、代签、重新 author
或重建该 Event。两条前置的拒绝语义是封闭的：Event 未被本服务接受 MUST
`failed_precondition` / `invite_event_unaccepted`；持久化 Event 的签署者不等于当前认证 session actor
MUST `failed_precondition` / `invite_event_actor_mismatch`。两类拒绝 MUST NOT 产生任何投递、outbox
入队或 holder-private 写入。由于 self wire 不再承载 Event bytes，不存在客户端 Event bytes
不一致的协议分支。

这个 self operation 只接受 raw evidence 并启动投递，不把它写入 Realm history。目标
`recipient_service_id` 等于本机 service id 时，服务端 MUST 从下述接收验证的**第 4 步**开始执行同一套
验证、receive policy 与 holder-private projection；第 1–3 步是 service-to-service 专属绑定，本地分支
MUST 以"已认证 self session + 上述两条 accepted-event 前置"作为等价绑定，MUST NOT 合成 federation
trust header、伪造 peer session 或自签 S2S 认证材料来走 peer 路径。目标为其它 Principal Server 时，
服务端 MUST 把 exact canonical request body 交给下述 peer operation，并以 body 内 `idempotency_key`
绑定 durable retry / outbox。客户端在投递结果不确定时 MUST 用同一 body 与同一 `idempotency_key`
重试，不得替换 evidence 或 `invite_event_id`。

邀请方 Principal Server 使用：

```text
POST /_arkret/peer/invites
operation_id = ak.peer.invites.command.submit
```

request body 为 `ak.schema.invite_delivery_request.v1`。接收方 Principal Server MUST：

1. 验证 service-to-service authentication，绑定 Source/Destination service `did_core_id`、trust domain、Content-Digest 与 idempotency key；接收方从已验证的 exact canonical body bytes 内部计算 request digest。
2. 验证 `Destination-Service-ID == invite_address.recipient_service_id`。
3. 验证 `invite_address.service_resolution`，要求 signed record 的 `service_id` 等于 `recipient_service_id`、adapter 投影 `project(full_id)` 等于该 `did_core_id`，并校验 freshness、service kind 与实际 target URL；carrier 不能单独授权投递。
4. 验证 `invite_event.kind == "ak.invite.create"`、Event signature、Realm capability、`invite_id` 与 `realm_id`。
5. 验证 `invite_event.payload.invitee == invite_address.subject_id`。
6. 验证 `invite_event.payload.invite_delivery_target.recipient_service_id == invite_address.recipient_service_id`，且两处 `service_resolution` 逐字节相等。
   可选 `route_assistance` 只存在于 delivery transport；不得要求它写入或匹配 durable invite Event，也不得把它当作本步骤的授权证据。
7. 验证 `introduction_evidence`，并核对 `introduction_evidence_digest`。对 `consent_grant` evidence,MUST 按 §2 校验 `consent_grant_ref` 是被邀请方给 inviter 的 active `invite` / `any` grant dot；校验失败 MUST 降级为低信任 `explicit_address` 处理。对 `handle_claim` evidence,MUST 按 §2 校验 handle claim、issuer / Directory trust、domain allowlist、expiry、audience、handle claim 自带的 `member_delivery_binding`（若存在）和可选 `member_delivery_binding_candidate`；校验失败 MUST 降级为低信任 `explicit_address` 处理。
8. 计算 effective receive policy:先取 subject 私有 `invite_receive_policy`，再与 §5.2 `receive_policy_constraints` 及适用组织 / Realm 约束求交集。随后查 `denied_subjects`(命中 inviter 即 `drop` 且强制 opaque)与 `denied_principal_services`；再按 effective `holder_allowed_introduction_kinds`、`handle_claim_behavior`、`explicit_address_behavior`、`unknown_invites` 决定 drop / quarantine / notify。
9. 返回 receive outcome:按 §5.1 分级披露。发现信任档、低信任档或 `denied_subjects` 命中时默认返回 generic `status`(opaque),MUST NOT 通过响应泄露 subject 是否存在或策略如何处理；高信任档且 `disclosure.high_trust=outcome` 时 MAY 在 `disclosed_outcome` 回送真实结果(`delivered | blocked` 两值)。仅当 subject 与部署约束都允许 `disclosure.discovery_trust=outcome` 时，`handle_claim` MAY 回送真实结果。**invite 进入 holder quarantine inbox 时，无论信任档与 `disclosure` 取值，一律返回 `status="deferred"` 且 MUST NOT 携带 `disclosed_outcome`**，并与“限速静默丢弃 / 超时丢弃 / holder 不存在 / holder policy deny”落在同一响应与 timing 等价类（[`../identity/consent-model.md` §6.1.1](../identity/consent-model.md)）。

notify 分支的 holder-private 投递承载是 account-data 私有 cell，key 为 `ak.account.invite_delivery`（登记于 [`account-data-key-registry.json`](../../artifacts/registry/account-data-key-registry.json)）。cell value 是**明文** JSON，MUST 符合 `ak.schema.invite_delivery.v1`（[`invite-delivery.schema.json`](../../artifacts/schemas/invite-delivery.schema.json)），不是 `ak.schema.account_data_encrypted_value.v1` envelope：该 cell 由接收方 Principal Server 在投递路径写入，服务端无法产出 holder 客户端加密的 envelope；`invite_token` 本就是服务端基础设施签发并持有的私有 locator，明文存储不改变其信任边界。value 外层为 `schema` / `updated_at` / `entries[]`，每个 entry 携带 `invite_id` / `realm_id` / `inviter` / `invite_token` / `received_at` / `expires_at`。

写入语义是封闭的：

- 该 cell 是 [`../models/account-data.md` §5](../models/account-data.md) 的 server-versioned CAS whole-value register：每次写入携带 `expected_revision`，冲突时写入方 MUST 重读当前值、按本节规则重新合并后重试，重试 MUST 有界（至多 3 次）；重试耗尽 MUST 放弃本次投递写入并以内部冲突失败，MUST NOT 以 stale revision 强行覆盖。
- 每次写入 MUST 先清除 `expires_at <= now` 的过期 entry，再按 `invite_id` 去重（同一 `invite_id` 的重复投递替换旧 entry，不重复占位），随后 append 新 entry；结果超过 200 条上限时 MUST 从 `received_at` 最旧的 entry 开始逐出，直至不超过 200 条。
- entry 的 `expires_at` MUST 取自 invite Event payload 的 `expires_at`；payload 未携带时服务端 MUST 以该 Event 的 `created_at` 加 7 天兜底。`expires_at <= now` 的 entry 是 stale 的：客户端 MUST NOT 用它执行 accept，并 MUST 在读取时按 `expires_at` 过滤。
- 写入被 CAS 接受后，服务端 MUST 以 `ak.account_data.update` actor-private device update 把已接受的 revision 与完整 value fanout 到 holder 的全部 active devices。该 envelope 使用 `DeviceMessageSender::Service { sender_service_id }` 分支：`sender_principal_id == recipient_principal_id == holder`，`sender_service_id` 等于当前接收 Principal Server 的 service identity；不伪造 origin device，不走 holder device revocation gate，也不排除任一 active holder device。fanout 只是实时加速路径；离线或错过 fanout 的设备 MUST 能直接经 `ak.self.account_data.read.list` 或 `ak.self.account_data.resource.get` 回读该 CAS cell 补取（account-data 天然是可回读的 register），两条路径读到的 revision/value 必须一致。CAS 冲突或其它未接受写入不得 fanout。
- private delivery material（含 `invite_token`）MUST NOT 物化到 Invite 对象或任何 Realm state（[`../models/governance-objects.md` §5.3](../models/governance-objects.md)）；该 cell 是 directed invite token 送达被邀请方设备的唯一规范私有承载。

## 8. Describe Capabilities

支持 invite addressing 的 Principal Server SHOULD 在 `ServiceDescribe.supported_operations` 中声明：

- `ak.self.invite_locator.command.issue`
- `ak.self.invite_locator.command.rotate`
- `ak.self.invite_locator.command.revoke`
- `ak.self.invites.command.dispatch`
- `ak.open.invite_locator.read.resolve`
- `ak.peer.invites.command.submit`

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

Directory 服务若支持 handle lookup，也 MAY 在 `ServiceDescribe` 或 `ak.find.directory.read.describe` 的扩展字段中声明：

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

`ak.find.directory.read.resolve_handle(intent="contact_request" | "invite" | "member_add")` 是可选 Directory 能力，不是 base first-contact / invite / member-add 的安全关键路径。Directory 即使返回 `member_delivery_binding` 或旧式 `MemberDeliveryBindingCandidate`，也只能作为可验证 builder evidence 或 `handle_claim` introduction evidence；reducer 仍 MUST 按 Join Policy 与 [`member-delivery-binding.md`](../governance/member-delivery-binding.md) 重新物化。

Realm 内 mention 不依赖公网 handle resolve。客户端在用户输入 `@alice:acme.example` 时 MUST 先从当前 Realm roster、MemberIdentity subject disclosure、内联 signed `handle_claims[]` 或本地已授权 claim cache 中解析到 `subject_id`。发送 Message 前必须持久化 DID-sealed mention reference；handle 字符串只能作为 audit / search metadata。

已知 `subject_id` 需要显示当前 handle 时，客户端 MAY 使用 roster 内联 `handle_claims[]` 或 `ak.find.directory.read.list_handles_for_subject`。这条 subject -> current handles 路径不得反向用来发现未知主体、发起 invite delivery 或构造 membership grant；只有 holder/issuer 已发布 verified handle claim，且 subject policy 与部署约束允许 `handle_claim` evidence 时，客户端才可把 handle 解析结果作为 first-contact / invite 的 introduction evidence。
