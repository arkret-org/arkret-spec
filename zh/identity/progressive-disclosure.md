# Progressive Disclosure

## 1. 目标

本文定义 Contrix 隐私信息渐进披露的端到端实现方案。

渐进披露用于让 holder 只向特定 verifier / organization 披露完成某项验证所需的最小身份信息，例如：

- 对 Google 披露 `alice@google.com`
- 对 Facebook 披露 `alice@facebook.com`
- 对某 Space 只证明“我是某组织当前成员”，不披露具体 handle
- 对某 verifier 证明年龄、角色、认证等级、设备可信度等属性

核心原则：

- DID Document 不承载跨组织身份画像。
- Handle 不是权限主键。
- 披露决策在 holder wallet 本地完成。
- 原始 credential、base proof、pairwise key 和 disclosure policy 默认只保存在 holder 私有域。
- TSP 是可选私密传输层，不是披露策略引擎。

## 2. 参与方

| 角色 | 定义 |
| --- | --- |
| Holder | 持有 credential、handle claim、pairwise DID 和 disclosure policy 的主体。 |
| Wallet | Holder 控制的本地或私有同步组件，负责策略匹配、proof 派生、发送和 receipt 保存。 |
| Issuer | 签发 credential / claim / attestation 的组织或服务。 |
| Verifier | 请求 presentation 的服务、组织、Space、Applet 或 agent。 |
| Represented Organization | Verifier 声称代表的组织 DID / VID。 |
| Transport | TSP、HTTP/JWE、DIDComm-like envelope、to-device、MLS DM 等 presentation 传输方式。 |

## 3. 数据对象

### 3.1 Presentation Request

```json
{
  "type": "cx.identity.presentation_request",
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
    "global_subject_identifier",
    "credential_id"
  ],
  "transport_hints": ["tsp", "http_jwe", "didcomm_like"],
  "expires_at": "2026-04-26T00:05:00Z"
}
```

Verifier MUST sign the request or send it through an authenticated relationship. Wallet MUST bind response proofs to `challenge`, `domain`, `verifier_did`, and `represented_org`.

### 3.2 Disclosure Policy

```json
{
  "type": "cx.identity.disclosure_policy",
  "policy_id": "cx:policy:d1sc01j0000000000000000000",
  "holder_did": "did:uuid:holder_root_or_pairwise",
  "audience": {
    "org_did": "did:web:google.example",
    "verifier_dids": ["did:web:login.google.example"],
    "tsp_vids": ["did:webs:google.example:verifier"]
  },
  "allowed_claims": [
    {
      "claim_type": "verified_handle",
      "issuer": "did:web:google.example",
      "subject_did": "did:uuid:g_pairwise...",
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
    "global_subject_identifier",
    "credential_id"
  ],
  "requires_user_consent": true,
  "expires_at": "2026-07-26T00:00:00Z"
}
```

Disclosure policy 是 holder-private state，默认 MUST NOT 写入公共 Space。

### 3.3 Presentation Response

```json
{
  "type": "cx.identity.presentation_response",
  "request_id": "cx:req:pres01j0000000000000000000",
  "holder_subject": "did:uuid:g_pairwise...",
  "proof_profile": "vc_di_bbs_2023",
  "presentation": {},
  "disclosed_fields": [
    "credential_subject.org",
    "credential_subject.member",
    "credential_subject.handle_verified"
  ],
  "presentation_hash": "sha256:...",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Response MUST NOT contain undisclosed fields, base proof, unrelated credential identifiers, other organization handles, or global subject identifiers.

### 3.4 Disclosure Receipt

```json
{
  "type": "cx.identity.disclosure_receipt",
  "receipt_id": "cx:receipt:d1sc01j0000000000000000000",
  "request_id": "cx:req:pres01j0000000000000000000",
  "holder_did": "did:uuid:g_pairwise...",
  "verifier_did": "did:web:login.google.example",
  "represented_org": "did:web:google.example",
  "presentation_hash": "sha256:...",
  "proof_profile": "vc_di_bbs_2023",
  "transport": "tsp",
  "tsp_relationship_id": "tsp:rel:...",
  "disclosed_fields": [
    "credential_subject.org",
    "credential_subject.member"
  ],
  "withheld_fields": [
    "credential_subject.handle",
    "other_handles"
  ],
  "created_at": "2026-04-26T00:00:00Z"
}
```

Receipt 是 holder-private audit record。Receipt MUST NOT contain withheld values.

## 4. 组织和 Verifier 确认

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

## 5. Proof Profile Selection

Wallet SHOULD choose proof profile by privacy requirement:

| Requirement | Recommended profile |
| --- | --- |
| Broad compatibility | `sd_jwt_vc` |
| Claim-level selective disclosure | `sd_jwt_vc` or `vc_di_bbs_2023` |
| Unlinkable derived proof | `vc_di_bbs_2023` or another unlinkable proof suite |
| Simple service assertion | detached JWS claim, if unlinkability is not required |

Implementations MUST NOT claim zero-knowledge or unlinkability unless the selected proof suite actually provides it and the presentation omits stable correlators.

## 6. Storage Model

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

## 7. Transport Selection

Transport selection order:

1. `tsp` if both parties support it and policy requires metadata privacy.
2. `http_jwe` using verifier DID/service key.
3. `didcomm_like` envelope if supported by both parties.
4. `to_device` if verifier is a known Contrix device/service endpoint.
5. `mls_dm` if holder and verifier share an encrypted DM Space.

If policy requires nested/routed metadata privacy and verifier lacks TSP or equivalent, wallet MUST reject or request explicit user override.

## 8. End-to-End Flow

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

## 9. Failure Codes

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

## 10. Security Requirements

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
