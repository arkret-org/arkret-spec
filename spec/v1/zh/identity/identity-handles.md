---
title: Handle 与 Claim 证明
---

## 1. 目标

Handle 是人类可读入口，不是权限主键。  
Contrix 使用 DID 作为稳定主体，用可验证 claim / attestation 表达 handle、组织成员、邮箱控制权和其他动态属性。

本文定义：

- handle 格式
- handle 到 DID 的解析
- 双向绑定验证
- pairwise DID 隐私模型
- 选择性披露 / 不可链接 presentation

## 2. Handle 原则

### 2.1 Handle 不是主键

协议层 MUST NOT 把以下内容作为 grant subject 或 Event actor：

- handle
- 邮箱
- 域名用户名
- 组织命名空间字符串，例如 `alice:google.com`

正确模型：

```text
grant subject = DID
authorization condition = verified claim / attestation
```

### 2.2 Handle 可以迁移

Handle MAY 变更、冻结、迁移或重新绑定。  
历史 Event 仍然保留原 DID 作为 actor，因此 handle 被回收不会改变历史责任主体。

### 2.3 标识角色与可见性

实现 MUST 区分以下标识**角色**。这些角色不是按字符串形态划分的：同一字符串可以在不同上下文中扮演不同角色（例如 `alice@example.com` 在通讯录发现阶段是 Connection Identifier；若 holder 主动通过 `alsoKnownAs` 公布则升格为 Handle）。区分点是 **holder 意图、可见性默认与验证路径**，不在字符串本身。实现 MAY 用同一存储承载，但 MUST 在协议输出（DID Document、Space history、grant subject、MLS credential、directory query 响应）中按角色应用对应可见性规则。

| 角色 | 可见性默认 | 验证路径 | 协议主体 |
| --- | --- | --- | --- |
| Connection Identifier | 关系私有；仅在发现 / 邀请 / consent 阶段使用 | provider 可达性证明 + invite / consent 流程 | 否 |
| Handle | 可发布；公开或半公开别名 | DNS / HTTPS well-known 双向绑定 + DID Document `alsoKnownAs` 或受信 issuer claim | 否 |
| Administrative Identifier | 组织本地；不出协议线 | 组织 governance / 内部 Directory | 否 |
| Display Name | UI 展示 | 无 | 否 |
| Principal DID | 公开或 pairwise；按 disclosure policy 控制 | DID resolver + 签名 | 是 |

示例字符串与可能扮演的角色：

- `alice@example.com`、`+86 138...`、通讯录用户名、外部账号 ID → Connection Identifier；若 holder 主动公布可升格为 Handle。
- `alice.example.com`、`@alice:example.org`、`google.example/users/alice` → Handle（DNS handle 或外部体系 alias）。
- 组织账号、计费账号、客服账号、受管员工编号 → Administrative Identifier。
- `Alice Zhang`、昵称 → Display Name。
- `did:webvh:...`、`did:web:...`、`did:key:...` → Principal DID。

规则：

- Connection Identifier 只用于发现、consent、邀请或一次性绑定证明。它不得自动写入 DID Document、Space history、membership event、grant subject 或 MLS credential。
- Provider、Directory 或 Auth Server 证明某个 connection identifier 可达时，输出仍 MUST 归约为 DID 或 pending invite proof，并带有 purpose、audience、expiry 和 issuer proof。
- 同一 principal 可以为不同 provider、组织或 Space 使用不同 connection identifier 和 pairwise DID。实现不得要求全局唯一 connection identifier。
- Connection identifier 与 DID 的绑定默认是关系私有状态。除非 holder 明确发布为 handle 或 VC claim，其他 Space 成员和 federation peer 不得获得该映射。
- 同一字符串从 Connection Identifier 升格为 Handle MUST 经过 holder 显式 disclosure（写入 `alsoKnownAs`、签发 VC claim、或发布到 Directory）；实现不得在用户未授权时自动升格，也不得仅凭 provider 可达性证明把 connection identifier 公开为 handle。
- Administrative Identifier 是组织本地概念。协议层只规定它不得作为协议主体、不得作为 grant subject、不得作为 Event actor、不得在跨组织 federation 输出中泄露；其内部分配、回收和绑定规则由组织 governance 决定，超出本规范范围。
- Display name 是可变 metadata，不得被用于 ACL、grant、audit attribution 或 sender verification。

## 3. Handle 格式

本文无修饰使用 `Handle` 时，指更宽泛的人类可读标识。`DNS handle` 是可通过 DNS / HTTPS well-known 双向验证的 handle 子类，初版推荐作为公共 persona handle：

- `alice.example.com`
- `ops.example.com`
- `agent.release.example.com`

组织内部、bridge 或外部协议 MAY 使用非 DNS handle / alias，但它仍然只是属性：

- `alice@google.com`
- `alice:google.com`
- `google.example/users/alice`
- `@alice:example.org`

这些字符串本身不证明组织成员资格。

Matrix-style identifier（如 `@alice:example.org`）MAY 作为用户可见 handle、登录名、联系人搜索项或 bridge alias，但不是 DNS handle。实现 MUST 保留其外部体系、localpart、domain / origin server 与大小写规范化规则；不得把它直接当作 DID、grant subject、Event actor 或未验证的组织成员证明。

## 4. Handle 绑定

公开 persona DID MAY 使用：

```json
{
  "alsoKnownAs": [
    "contrix://alice.example.com"
  ]
}
```

Pairwise DID、临时 DID、设备 DID、agent 执行 DID 和隐私敏感关系 DID SHOULD NOT 强制绑定公开 handle。

## 5. Handle 解析

推荐双通道解析：

1. DNS TXT：`_contrix.<handle>`
2. HTTPS well-known：`https://<handle>/.well-known/contrix-did`

DNS / HTTPS well-known 适用于 DNS 风格 handle。对于 `@alice:example.org`、`alice@google.com` 或其他非 DNS handle，解析 MAY 通过组织 Directory、Auth / Account Server、bridge registry 或受信 issuer claim 完成，但解析结果仍然 MUST 归约到 DID 和可验证绑定证据。

Well-known 示例：

```json
{
  "did": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example"
}
```

## 6. 双向验证

客户端解析 handle 得到 DID 后，MUST 继续解析 DID Document，并验证：

```text
did_document.alsoKnownAs contains contrix://<handle>
```

若双向验证失败，客户端 MUST NOT 把该 handle 当作可信绑定。

DNS TXT 只能作为发现通道。若使用 DNS TXT 直接声明 handle 绑定，客户端 MUST 满足以下至少一项才可显示为 verified：

- DNSSEC validation 成功，且 TXT 内容绑定 handle、DID、service DID、created_at、expires_at 和 signature / hash commitment。
- TXT 记录内的绑定声明由目标 DID、Organization DID 或受信 issuer 签名，客户端能通过 DID resolver / VC 验证该签名。
- HTTPS well-known 或 Directory / VC presentation 提供等价的签名绑定证据。

未启用 DNSSEC 且没有可验证签名的 DNS 结果只能作为 unverified discovery hint，MUST NOT 作为 grant subject、Organization membership、official Space 或 verified handle 的依据。

### 6.1 缓存与失效

Handle 解析结果是带时间边界的绑定，不是永久身份事实。

缓存规则：

- verified handle cache MUST 绑定 `handle`、`did`、解析通道、DID Document version / digest、alsoKnownAs proof、issuer proof（如有）、verified_at、expires_at 和 resolver policy。
- DNS / HTTPS 解析结果的 TTL MUST 不超过底层 DNS TTL、HTTPS response cache headers、签名绑定 `expires_at`、DID Document cache TTL 和本地 resolver policy 上限中的最小值。未提供 TTL 时，verified cache SHOULD 不超过 24 小时；高风险授权或组织背书 SHOULD 使用更短 TTL 或实时 status check。
- 当 DID Document 移除对应 `alsoKnownAs`、issuer claim 被 revoke / expired、well-known 绑定变更、DNSSEC validation 失败、handle 被解析到不同 DID、或 resolver policy 更新时，缓存 MUST 失效或降级为 unverified。
- Handle 转让或撤销时，resolver、Directory 或旧持有者的 Principal Server SHOULD 发送 profile-registered cache invalidation signal，使订阅该 handle 的客户端尽快失效缓存，不必等待 TTL 自然过期。标准 `cx.*` invalidation kind 必须先进入 event registry；未注册的 `cx.handle.*` 名称不得作为 v1 wire kind 使用。
- Handle 转让不改变历史 Event 的 actor DID、签名责任或 audit attribution。历史 `@mention`、profile snapshot 或 message text MAY 保留当时显示字符串，但安全敏感 UI 必须能显示事件实际 DID，并在当前 handle 解析与历史 sender DID 不一致时标记为 handle changed / transferred。
- 授权、grant subject、membership、MLS credential 和 audit attribution MUST 使用 DID / verified claim，而不是缓存中的 handle 字符串。缓存失效不得自动撤销 DID 已签名的历史事件；只影响后续显示、发现和基于 handle claim 的条件化授权。

## 7. Verified Claim

Handle、组织成员、邮箱控制权和角色 SHOULD 通过 credential / attestation 表达。

授权判断 MUST 检查：

- issuer 是否被目标 Space / Policy 信任
- subject DID 是否匹配当前 actor
- claim 是否在有效期内
- claim 是否未撤销
- claim 内容是否满足 grant constraint
- presentation 是否绑定当前 verifier challenge / domain

## 8. 隐私保护型 Handle 证明

DID Document MUST NOT 被用作跨组织身份画像。公开或半公开 DID Document MUST NOT 直接列出以下信息，除非主体明确希望这些信息被关联：

- `alice@google.com`
- `alice@facebook.com`
- 第三方 profile URL
- 跨组织账号名
- 可关联多个 persona 的相同 service endpoint
- 可关联多个 persona 的相同 verification method

## 9. 标准依据

本设计与以下 W3C 文档一致：

- DID Core 隐私章节要求公开 DID Document 避免个人数据，并提醒 service endpoint、verification method 复用会带来关联风险。
- DID Core 建议使用 pairwise DID 降低跨关系关联。
- VC Data Model v2.0 定义 selective disclosure、unlinkable disclosure，并说明 zero-knowledge proof mechanism 可用于证明而不披露全部属性。
- VC DI BBS Cryptosuites 定义 `bbs-2023` base proof、derived proof、selective pointers 和 unlinkable proof 机制。

## 10. 推荐方案：Google 与 Facebook Handle

对 `alice@google.com` 和 `alice@facebook.com`：

1. Alice 为 Google 关系使用 `did:key:z6Mkgpairwise...`
2. Alice 为 Facebook 关系使用 `did:key:z6Mkfpairwise...`
3. 两个 DID MUST NOT 复用相同 verification method、专用 service endpoint、endpoint 用户名、`alsoKnownAs` 或公开 profile URL
4. Google 或受信 issuer 给 `did:key:z6Mkgpairwise...` 签发 `ContrixOrgMembershipCredential`
5. Facebook 或受信 issuer 给 `did:key:z6Mkfpairwise...` 签发独立 credential
6. 面向 Google verifier 时，wallet 只生成 Google 相关 presentation
7. Google verifier MUST NOT 要求披露 Facebook credential、Facebook DID 或跨域 subject identifier

## 11. Credential 示例

如果 verifier 只需要知道“该主体拥有 Google 组织内有效账号”，presentation SHOULD 披露抽象 claim：

```json
{
  "type": ["verifiable_credential", "contrix_org_membership_credential"],
  "issuer": "did:web:google.example",
  "credentialSubject": {
    "id": "did:key:z6Mkgpairwise...",
    "org": "did:web:google.example",
    "member": true,
    "handle_verified": true
  },
  "validFrom": "2026-04-26T00:00:00Z",
  "validUntil": "2026-07-26T00:00:00Z",
  "credentialStatus": {
    "type": "privacy_preserving_status_list"
  }
}
```

如果确实需要显示 Google handle，presentation MAY 披露：

```json
{
  "credentialSubject": {
    "id": "did:key:z6Mkgpairwise...",
    "handle": "alice@google.com",
    "handle_verified": true
  }
}
```

该 disclosure MUST 绑定单一 verifier challenge / domain，并且 MUST NOT 自动披露其他组织 handle。

## 12. Presentation Request

Verifier MUST 使用最小披露请求，不得请求“所有 alias”或“所有账号”。

```json
{
  "type": "contrix_presentation_request",
  "audience": "did:web:google.example",
  "domain": "google.example",
  "challenge": "cx_chal_01J...",
  "accepted_issuers": [
    "did:web:google.example",
    "did:web:trusted-hr.example"
  ],
  "required_claims": [
    {
      "type": "contrix_org_membership_credential",
      "constraints": {
        "org": "did:web:google.example",
        "member": true
      },
      "disclosure": "abstract"
    }
  ],
  "forbidden_claims": [
    "other_handles",
    "external_accounts",
    "global_flow_identifier"
  ]
}
```

Wallet MUST 展示将要披露的 claim。  
Wallet SHOULD 拒绝或警告请求无关 handle、global subject identifier、credential id 或不必要人口属性的 presentation request。

## 13. Proof Profile

Contrix SHOULD 支持：

- `sd_jwt_vc`：适合广泛 JOSE 互操作和 claim 级选择性披露
- `vc_di_bbs_2023`：适合需要不可链接 derived proof 的高隐私场景

需要不可链接 presentation 时，MUST 使用实际支持 unlinkability 的 proof mechanism。实现不得仅因为使用 VC 就宣称零知识或不可链接。

使用 `vc_di_bbs_2023` 时：

- issuer 创建 base proof 并只交给 holder
- holder 使用 selected claim pointers 创建 derived proof
- verifier 验证 derived proof、issuer key、challenge、domain 和 audience
- verifier MUST NOT 收到未披露 claim、base proof 或无关 credential identifier

## 14. Status 与撤销

Credential status check MUST 避免 verifier 驱动的关联追踪。

实现 SHOULD 使用：

- privacy-preserving status list
- cached status material
- verifier-independent revocation proof

实现 SHOULD NOT 要求 verifier 在每次 presentation 时把唯一 credential id、subject DID 或 handle 提交给中心化 status endpoint。

## 15. 授权语义

Capability policy MAY 依赖 verified claim，但 grant subject 仍然是 DID。

正确：

```text
grant subject = did:key:z6Mkgpairwise...
condition = has valid contrix_org_membership_credential where org = did:web:google.example
```

错误：

```text
grant subject = alice@google.com
```

如果 holder 后续为另一个组织出示不同 pairwise DID，除非 holder 显式提供 linking proof，否则 verifier MUST 将其视为独立隐私上下文。

## 16. Progressive Disclosure（渐进披露）

本节定义 Contrix 隐私信息渐进披露的端到端实现方案。渐进披露用于让 holder 只向特定 verifier / organization 披露完成某项验证所需的最小身份信息，例如：

- 对 Google 披露 `alice@google.com`
- 对 Facebook 披露 `alice@facebook.com`
- 对某 Space 只证明"我是某组织当前成员"，不披露具体 handle
- 对某 verifier 证明年龄、角色、认证等级、设备可信度等属性

核心原则：

- DID Document 不承载跨组织身份画像。
- Handle 不是权限主键。
- 披露决策在 holder wallet 本地完成。
- 原始 credential、base proof、pairwise key 和 disclosure policy 默认只保存在 holder 私有域。
- TSP 是可选私密传输层，不是披露策略引擎。

### 16.1 参与方

| 角色 | 定义 |
| --- | --- |
| Holder | 持有 credential、handle claim、pairwise DID 和 disclosure policy 的主体。 |
| Wallet | Holder 控制的本地或私有同步组件，负责策略匹配、proof 派生、发送和 receipt 保存。 |
| Issuer | 签发 credential / claim / attestation 的组织或服务。 |
| Verifier | 请求 presentation 的服务、组织、Space、Applet 或 agent。 |
| Represented Organization | Verifier 声称代表的组织 DID / VID。 |
| Transport | TSP、HTTP/JWE、DIDComm-like envelope、to-device、MLS DM 等 presentation 传输方式。 |

### 16.2 数据对象

#### 16.2.1 Presentation Request

```json
{
  "kind": "cx.identity.presentation_request",
  "request_id": "cx:req:pres01j0000000000000000000",
  "verifier_did": "did:web:login.google.example",
  "represented_org": "did:web:google.example",
  "domain": "google.example",
  "challenge": "cx_chal_01J...",
  "purpose": "space_join",
  "accepted_issuers": ["did:web:google.example"],
  "required_claims": [
    {
      "claim_type": "contrix_org_membership_credential",
      "constraints": {
        "org": "did:web:google.example",
        "member": true
      },
      "disclosure": "abstract"
    }
  ],
  "optional_claims": [
    {
      "claim_type": "verified_handle",
      "fields": ["handle"],
      "disclosure": "explicit"
    }
  ],
  "forbidden_claims": [
    "other_handles",
    "external_accounts",
    "global_flow_identifier",
    "credential_id"
  ],
  "transport_hints": ["tsp", "http_jwe", "didcomm_like"],
  "expires_at": "2026-04-26T00:05:00Z"
}
```

Verifier MUST sign the request or send it through an authenticated relationship. Wallet MUST bind response proofs to `challenge`, `domain`, `verifier_did`, and `represented_org`.

#### 16.2.2 Disclosure Policy

```json
{
  "kind": "cx.identity.disclosure_policy",
  "policy_id": "cx:policy:d1sc01j0000000000000000000",
  "holder_did": "did:web:holder.example.com",
  "audience": {
    "org_did": "did:web:google.example",
    "verifier_dids": ["did:web:login.google.example"],
    "tsp_vids": ["did:webs:google.example:verifier"]
  },
  "allowed_claims": [
    {
      "claim_type": "verified_handle",
      "issuer": "did:web:google.example",
      "subject_did": "did:key:z6Mkgpairwise...",
      "disclosure": "explicit",
      "fields": ["handle"],
      "value_constraints": {
        "handle": "alice@google.com"
      }
    }
  ],
  "forbidden_fields": [
    "other_handles",
    "external_accounts",
    "global_flow_identifier",
    "credential_id"
  ],
  "requires_user_consent": true,
  "expires_at": "2026-07-26T00:00:00Z"
}
```

Disclosure policy 是 holder-private state，默认 MUST NOT 写入公共 Space。

#### 16.2.3 Presentation Response

```json
{
  "kind": "cx.identity.presentation_response",
  "request_id": "cx:req:pres01j0000000000000000000",
  "holder_subject": "did:key:z6Mkgpairwise...",
  "proof_profile": "vc_di_bbs_2023",
  "presentation": {},
  "disclosed_fields": [
    "credentialSubject.org",
    "credentialSubject.member",
    "credentialSubject.handle_verified"
  ],
  "presentation_hash": "sha256:...",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Response MUST NOT contain undisclosed fields, base proof, unrelated credential identifiers, other organization handles, or global subject identifiers.

#### 16.2.4 Disclosure Receipt

```json
{
  "kind": "cx.identity.disclosure_receipt",
  "receipt_id": "cx:receipt:d1sc01j0000000000000000000",
  "request_id": "cx:req:pres01j0000000000000000000",
  "holder_did": "did:key:z6Mkgpairwise...",
  "verifier_did": "did:web:login.google.example",
  "represented_org": "did:web:google.example",
  "presentation_hash": "sha256:...",
  "proof_profile": "vc_di_bbs_2023",
  "transport": "tsp",
  "tsp_relationship_id": "tsp:rel:...",
  "disclosed_fields": [
    "credentialSubject.org",
    "credentialSubject.member"
  ],
  "withheld_fields": [
    "credentialSubject.handle",
    "other_handles"
  ],
  "created_at": "2026-04-26T00:00:00Z"
}
```

Receipt 是 holder-private audit record。Receipt MUST NOT contain withheld values.

### 16.3 组织和 Verifier 确认

Wallet MUST NOT 只凭域名、邮箱后缀、TLS 证书或 UI 文案确定组织。

Verifier MUST prove authority by one of:

- represented organization DID signs the presentation request directly.
- represented organization signs a service authorization claim for verifier DID.
- trust registry / governance registry maps verifier VID to represented organization.
- Space policy lists verifier DID as trusted issuer/verifier for the requested purpose.

Service authorization claim:

```json
{
  "issuer": "did:web:google.example",
  "subject": "did:web:login.google.example",
  "claim_type": "org_service_authorization",
  "service": "contrix_verifier",
  "valid_until": "2026-07-26T00:00:00Z"
}
```

### 16.4 Proof Profile Selection

Wallet SHOULD choose proof profile by privacy requirement:

| Requirement | Recommended profile |
| --- | --- |
| Broad verifier support | `sd_jwt_vc` |
| Claim-level selective disclosure | `sd_jwt_vc` or `vc_di_bbs_2023` |
| Unlinkable derived proof | `vc_di_bbs_2023` or another unlinkable proof suite |
| Simple service assertion | detached JWS claim, if unlinkability is not required |

Implementations MUST NOT claim zero-knowledge or unlinkability unless the selected proof suite actually provides it and the presentation omits stable correlators.

### 16.5 Storage Model

| Data | Location | Encryption |
| --- | --- | --- |
| raw credential / base proof | wallet local encrypted store or holder private account data | device key / recovery key |
| pairwise DID private keys | device secret storage | hardware-backed when available |
| disclosure policy | holder private account data | E2EE to holder devices |
| presentation request | temporary inbox or encrypted private account data | verifier-holder transport encryption |
| presentation response | sent only to verifier; optional local encrypted copy | TSP / JWE / DIDComm-like / MLS DM |
| disclosure receipt | holder private account data | E2EE to holder devices |
| status / revocation cache | wallet cache or holder private account data | E2EE to holder devices |

Sync Service / service operator MUST NOT learn raw credential contents, base proofs, full disclosure policies, or undisclosed handles.

### 16.6 Transport Selection

Transport selection order:

1. `tsp` if both parties support it and policy requires metadata privacy.
2. `http_jwe` using verifier DID/service key.
3. `didcomm_like` envelope if supported by both parties.
4. `to_device` if verifier is a known Contrix device/service endpoint.
5. `mls_dm` if holder and verifier share an encrypted DM Space.

If policy requires nested/routed metadata privacy and verifier lacks TSP or equivalent, wallet MUST reject or request explicit user override.

### 16.7 End-to-End Flow

1. Verifier sends signed `cx.identity.presentation_request`.
2. Wallet verifies verifier DID/VID and represented organization authority.
3. Wallet checks request against disclosure policy.
4. Wallet prompts holder if `requires_user_consent=true` or request exceeds known policy.
5. Wallet selects pairwise DID and matching credential.
6. Wallet checks status using privacy-preserving status material.
7. Wallet derives proof using selected proof profile.
8. Wallet sends response over selected transport.
9. Verifier validates proof, issuer, status, challenge, domain, audience and freshness.
10. Wallet writes disclosure receipt to holder private account data.

### 16.8 Failure Codes

| code | Meaning |
| --- | --- |
| `verifier_not_authorized` | Verifier cannot prove authority for represented organization. |
| `policy_denied` | Holder disclosure policy denies the request. |
| `consent_required` | User approval is required before disclosure. |
| `unsupported_proof_profile` | No mutually acceptable proof profile. |
| `transport_privacy_required` | Policy requires TSP/nested/routed or equivalent but unavailable. |
| `credential_not_found` | Holder has no matching credential. |
| `credential_expired` | Matching credential expired. |
| `status_unavailable` | Revocation/status material unavailable. |
| `overbroad_request` | Request asks for unrelated handles, credential ids or global identifiers. |

### 16.9 Security Requirements

Wallet MUST:

- default to minimum disclosure.
- reject request for all handles / all aliases.
- reject unrelated organization handles.
- bind proof to verifier challenge, domain and audience.
- avoid online status checks that reveal holder identity to a central service.
- store receipts without undisclosed values.
- separate pairwise DID keys and service endpoints across organizations.

Verifier MUST:

- request only necessary claims.
- not require global subject identifier unless policy explicitly permits and holder consents.
- not request credential id if unlinkability is required.
- treat different pairwise DID presentations as separate subjects unless holder provides linking proof.

## 17. v1 互操作要求

- Handle ABNF 必须限制为可规范化、大小写明确、禁止控制字符和混淆分隔符的字符串；DNS 风格 handle 使用 IDNA 处理后再验证，显示层必须防同形混淆。
- DNS TXT record 格式 MUST 绑定 handle、DID、service DID、created_at、expires_at 和 signature / hash commitment；过期或不匹配时不得显示 verified。
- Well-known response schema MUST 返回 subject DID、handle、issuer、proof、validity、service binding 和 optional challenge；客户端必须做双向验证。
- Credential schema、presentation request、disclosure policy 和 disclosure receipt 必须绑定 holder DID、verifier DID、audience、challenge、domain、disclosed fields、withheld fields 和 proof profile。
- Status list profile MUST 支持凭证撤销和暂停。授权依赖的 credential 无法确认状态时 MUST fail closed。
- BBS / SD-JWT VC conformance vectors MUST 覆盖选择性披露、challenge/domain 绑定、错误 issuer、过期凭证、撤销凭证和 pairwise DID unlinkability。
