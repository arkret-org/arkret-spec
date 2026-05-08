---
title: Discovery and Directory
---

## 1. 目标

Contrix 需要明确区分三件事：

- 资源是否可被发现。
- 资源是否可被预览。
- 主体是否可加入、读取或写入资源。

发现不等于读取，读取不等于加入，加入不等于写入。实现 MUST NOT 用 `join_rule` 或 `history_visibility` 代替 discoverability policy。

本文定义 Space、Organization、Actor 和 Applet 的发现模型、目录服务和防枚举要求。

## 2. 发现级别

`discoverability` 取值：

| 值 | 含义 |
| --- | --- |
| `public` | 可被公共目录索引和搜索。 |
| `listed` | 可在指定目录、组织页、父 Space 或受信目录中列出，但不一定进入全网公共搜索。 |
| `restricted` | 只有满足可验证条件的请求方可发现，例如组织成员、受邀者、共同 Space 成员或持有特定 claim 的主体。 |
| `unlisted` | 不进入目录搜索；知道精确 id、alias、邀请链接或 parent edge 的主体 MAY 尝试解析。 |
| `invite_only` | 未被邀请或未持有 invite proof 的主体不得得知其存在；查询应返回与不存在相同的错误。 |
| `secret` | 仅本地或端到端加密上下文中可见；目录、Sync Service 和受托 search / projection 服务不应公开可枚举 metadata。 |

默认值：

- 新 Space 默认 `invite_only`。
- 新 Organization profile 默认 `listed`，但 MAY 设置为 `restricted` 或 `unlisted`。
- Pairwise / private DID 默认 `secret`。
- Public Persona DID 默认 `public` 或 `listed`，由 holder policy 决定。

## 3. Space Discoverability

Space discovery policy SHOULD 由 `cx.space.discovery` state event 表达：

```json
{
  "kind": "cx.space.discovery",
  "payload": {
    "discoverability": "listed",
    "directory_visibility": {
      "public_directory": false,
      "organization_directory": true,
      "parent_space_directory": true
    },
    "preview": {
      "mode": "stripped_state",
      "fields": [
        "name",
        "avatar",
        "summary",
        "owning_organizations",
        "join_rule",
        "member_count_bucket"
      ]
    },
    "allowed_discoverers": [
      {
        "type": "claim",
        "claim_type": "org_membership",
        "organization": "did:web:acme.example",
        "issuer": "did:web:acme.example"
      }
    ],
    "directory_services": [
      "did:web:directory.acme.example"
    ],
    "anti_enumeration": {
      "require_exact_alias_for_unlisted": true,
      "member_count_mode": "bucketed",
      "not_found_blinding": true
    }
  }
}
```

规则：

- `discoverability=public` MAY be indexed by public directory services.
- `listed` Space MUST only be listed in directories explicitly allowed by `directory_visibility` or `directory_services`.
- `restricted` Space MUST require directory query authorization before returning search results.
- `unlisted` Space MUST NOT appear in keyword search, but MAY resolve by exact id / alias / signed invite / parent edge if policy allows.
- `invite_only` and `secret` Space queries by unauthorized subjects MUST return `not_found` or an indistinguishable response.
- Directory result MUST NOT include event history, member list, raw policy, MLS state, hidden parent/child edges, or full organization governance chain unless separately authorized.

`join_rule` 只控制加入流程。公开可发现的 Space MAY still require invite、knock 或 restricted join。不可发现的 Space MAY still have `join_rule=public` for holders of a private link, but this is discouraged unless anti-spam policy is strong.

`history_visibility` 只控制历史读取范围。`discoverability=public` MUST NOT imply `history_visibility=world_readable`。

## 4. Organization Discoverability

Organization discovery policy SHOULD be represented by organization profile state or governance registry record:

```json
{
  "kind": "cx.organization.discovery",
  "organization_did": "did:web:acme.example",
  "discoverability": "public",
  "profile_visibility": {
    "name": "public",
    "logo": "public",
    "description": "public",
    "official_spaces": "listed",
    "members": "restricted",
    "services": "listed"
  },
  "directory_services": [
    "did:web:directory.acme.example"
  ],
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:web:acme.example#governance-key-1",
    "jws": "..."
  }
}
```

Organization 可以是公开的、受限的或不可列举的。实现 MUST NOT 因为组织 DID 可解析，就公开组织成员列表、官方 Space 列表、服务拓扑或治理策略全文。

客户端展示组织搜索结果时 SHOULD verify：

1. Organization DID 可解析。
2. discovery policy 或 profile 由组织 DID / governance service 签名。
3. 如果结果声称包含 official Space，仍需验证每个 Space 的 `cx.space.organization` 背书。
4. 目录服务 DID 被组织 DID 声明或被本地 trust policy 接受。

## 5. Actor and Handle Discoverability

Actor / Principal discovery MUST respect holder privacy:

- Public persona MAY appear in public user directory.
- Pairwise DID, private DID, device DID and sensitive agent DID MUST NOT appear in public directory by default.
- Handle search MUST return only handles whose binding is public or whose holder granted disclosure.
- Presence, common Space, organization membership and contact graph MUST NOT be leaked through search ranking or autocomplete.

Unknown actor profile lookup in a shared Space is allowed only to the extent required for rendering authorized content, for example display name and avatar. It must not reveal unrelated handles or organization accounts.

## 6. Private Contact Discovery

通讯录式发现比普通目录搜索更敏感。实现 MAY 支持 `cx.private_contact_discovery.v1`，用于在不上传明文通讯录、不让目录服务同时获得 requester DID 与目标 connection identifier 的前提下发现可联系主体。

### 6.1 Profile 目标

- Discovery Provider 不应同时获得 requester 的稳定 DID 和原始邮箱/手机号/用户名。
- 请求应使用 batch、padding、rate limit 和 time-bound proof，避免逐个枚举。
- 发现结果应返回最小可联系材料，而不是完整 profile 或关系图谱。
- 协议 MUST 定义"private discovery 能回答什么"——并显式声明不能回答什么——避免实现私自扩展导致隐私退化。

### 6.2 v1 core 形态：Set-Membership PSI（双轮 OPRF）

v1 core `cx.private_contact_discovery.v1` profile 明确限定为 **set-membership PSI**：客户端只能问"我已知的 connection identifier 集合中，哪些在 provider 的可联系集合内？"，回答严格是布尔位图，不附带任何额外 reachability claim、profile 或 metadata。

实现 MUST 使用基于 OPRF（Oblivious Pseudorandom Function）的两轮协议（推荐 RFC 9497 VOPRF 或 Signal CDSI 风格）：

1. **Round 1 — Blind**：客户端按 RFC 9497 OPRF 流程对每个本地 connection identifier 计算 `blind = OPRF.Blind(identifier_canonical_bytes)`；提交 `{batch_id, blinded[]}` 给 provider。Provider 对每个 `blinded[i]` 用其 OPRF secret key 计算 `evaluation[i] = OPRF.BlindEvaluate(sk, blinded[i])` 并返回。Provider 看不到 raw identifier；客户端 unblind 后得到 `derived[i]`。
2. **Round 2 — Match**：客户端在第二个独立请求中提交 `{batch_id, derived_hash_prefix[]}`（每条发送 derived 的固定前缀，长度由 provider 在第一轮响应中声明）。Provider 仅在自己的 OPRF-evaluated 可联系集合中按前缀比较，返回固定基数（dummy padding 到 batch size）的命中位图。
3. **披露**：客户端只在 user 在 UI 中显式确认联系或发起邀请时，才向目标 principal 的 provider 披露自己的 DID、pairwise DID、presentation 或 connection identifier 原文。该披露走 §6 / consent-model 的 invite + consent 流程，不在 PSI 协议范围内。

OPRF 选择：

- v1 core 强制要求 RFC 9497 VOPRF（验证 OPRF），ciphersuite 至少包含 `OPRF(ristretto255, SHA-512)`。
- Provider OPRF secret key MUST 周期轮换（默认 ≥ 7 天 / ≤ 90 天）；轮换后客户端持有的 derived 缓存自动失效，避免长期跨域关联。
- Provider MUST 在 `server/describe.discovery` 暴露当前 ciphersuite、key epoch、batch size / padding 上限。

### 6.3 请求形态（非完整 schema）

第一轮（blind）：

```json
{
  "profile": "cx.private_contact_discovery.v1",
  "phase": "blind",
  "batch_id": "cx:batch:01JS...",
  "ciphersuite": "OPRF-ristretto255-SHA512",
  "key_epoch": 14,
  "blinded_elements": ["base64url...", "base64url..."],
  "padding_count": 128
}
```

第二轮（match）：

```json
{
  "profile": "cx.private_contact_discovery.v1",
  "phase": "match",
  "batch_id": "cx:batch:01JS...",
  "key_epoch": 14,
  "derived_prefixes": ["base64url-16bytes...", "base64url-16bytes..."]
}
```

### 6.4 规则

- Raw email、phone number、address-book label、local contact name 和未加盐低熵 hash MUST NOT 被发送给公共 Directory，包括第一轮的 OPRF input（OPRF Blind 已经做了 unlinkable 化，但实现仍 MUST 在客户端先做 normalization + canonical encoding，杜绝把明文写入 audit log）。
- Provider MUST 对 batch 大小、padding count、失败响应、计时和 result cardinality 做反枚举处理；不存在、不可发现、policy-denied 和 OPRF mismatch 在 wire 上 SHOULD 保持相同响应形态与延迟分布。
- Provider MUST NOT 在第二轮返回 reachability proof、handle verified claim、组织成员资格、Space membership 或读取权限。这些声明只能通过后续 invite + consent 流程获得。
- Private discovery 结果**仅** 证明"在 provider 当前可联系集合中存在 OPRF derived 与某项匹配的条目"——不证明该条目对应的真实身份、handle、活跃度或意愿。客户端 UI MUST 把它表述为"可能可联系"而不是"已确认存在"。
- 高隐私客户端 SHOULD 为每个 provider 或关系使用 pairwise DID，并在 consent 完成前避免披露全局 public persona DID。
- 实现 MUST NOT 在同一 OPRF key epoch 内允许同一 client 提交超过 `max_psi_queries_per_epoch`（默认 1）次 batch；超过后 provider 返回 `psi_quota_exhausted`。这避免攻击者用同一 OPRF key 对大量 identifier 做枚举；新 key epoch 自动重置。

### 6.5 v1 不再使用 "Reachability Proof"

早期草案使用 provider 返回的 time-bound signed reachability proof 作为客户端对外披露的凭据。该设计要求 provider 对每个 blinded identifier 单独签发 proof 才能让对方 verify，但若让 verifier 验证 proof，verifier 必须知道 proof 绑定到哪个 identifier——这把"谁向谁披露过什么"的隐私收益又交回去了。v1 移除该机制；私域披露统一走 invite + consent 流程，invite 自身的 commitment + 唯一性由 [`sync/third-party-invites.md`](../sync/third-party-invites.md) 保证。

支持旧 reachability proof 的实现 MUST 在 `server/describe.discovery` 中标记 `legacy_reachability_proof=true`，并 MUST 在 v1 conformance 报告中标记为 `pending_psi_migration`；core conformance 不再以 reachability proof 作为输出形态。

## 7. Directory Service

Directory Service 是派生索引服务，不是真相源。它 MAY index:

- public / listed Space preview metadata
- organization public profile
- public persona profile
- applet protocol metadata
- verified handle records that are intended to be public

Directory Service MUST:

- expose its service DID and feature profile
- apply authorization filtering before returning each result
- return stable pagination cursors
- indicate result freshness and source refs
- avoid leaking existence through distinct errors for hidden resources

Directory Service MUST NOT:

- list `invite_only` or `secret` resources to unauthorized subjects
- expose full member lists unless explicitly allowed
- expose private handles, pairwise DID, disclosure policy or credential contents
- rank hidden resources in a way that reveals their existence

## 8. Service Surface

Recommended operations:

```text
GET /api/v1/directory/describe
POST /api/v1/directory/search-spaces
POST /api/v1/directory/resolve-space
POST /api/v1/directory/search-organizations
POST /api/v1/directory/resolve-organization
POST /api/v1/directory/search-actors
POST /api/v1/directory/resolve-handle
```

字段级定义：

| operation_id | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `cx.directory.describe` | 无 | 无 | `service_did: did`; `resource_types: string[]`; `discovery_profiles: string[]`; `restricted_query_proof: boolean?` | `public_metadata`; 可限流。 |
| `cx.directory.search_spaces` | 无 | `query: string`; `organization_did: did`; `parent_space_id: id`; `requester: did`; `proofs: proof[]`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | MUST 按 discoverability、requester proof 和 Space policy 逐项过滤；隐藏资源不得泄露存在性。 |
| `cx.directory.resolve_space` | 至少一个：`space_id: id`、`alias: string`、`invite_token: string`、`signed_link: string` | `requester: did`; `proofs: proof[]` | `space_preview: object`; `stripped_state: object[]?`; `join_rule: string?`; `via_services: did[]?` | invite / restricted / secret Space 对未授权请求使用统一 `not_found`。 |
| `cx.directory.search_organizations` | 无 | `query: string`; `claims: object`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | 仅返回公开或授权可发现组织。 |
| `cx.directory.resolve_organization` | 至少一个：`organization_did: did` 或 `handle: string` | `proofs: proof[]` | `organization_preview: object`; `did_document_ref: string?`; `endorsements: object[]?` | 解析组织不等于公开成员、Space 列表或服务拓扑。 |
| `cx.directory.search_actors` | 无 | `query: string`; `space_id: id`; `organization_did: did`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | 不得泄露 pairwise/private DID 或未披露组织账号。 |
| `cx.directory.resolve_handle` | `handle: string` | `expected_did: did`; `proof_challenge: string` | `did: did`; `handle: string`; `verified: boolean`; `claims: object[]?` | private handle 需要 presentation。 |

`search-spaces` 请求示例（非完整 schema）：

```json
{
  "query": "release",
  "scope": {
    "organization_did": "did:web:acme.example",
    "parent_space_id": null
  },
  "requester": "did:web:alice.example.com",
  "proofs": [
    "cx:presentation:..."
  ],
  "limit": 20,
  "cursor": null
}
```

Result:

```json
{
  "results": [
    {
      "space_id": "cx:space:01js0sp0000000000000000000",
      "name": "Release Coordination",
      "summary": "Public release coordination",
      "discoverability": "listed",
      "join_rule": "knock_restricted",
      "history_visibility": "joined",
      "official_organizations": [
        "did:web:acme.example"
      ],
      "preview_ref": "cx:event:01JS0PV...",
      "source_refs": [
        "cx:event:spacecreatehash00000000000",
        "cx:event:spaced1sc0veryhash00000000",
        "cx:event:space0rgan1zat10nhash00000"
      ]
    }
  ],
  "next_cursor": null
}
```

Unauthorized exact resolve of hidden resources SHOULD return:

```json
{
  "ok": false,
  "error": {
    "code": "not_found",
    "message": "not found"
  }
}
```

Implementations SHOULD use the same status, timing class and response shape for nonexistent and unauthorized hidden resources.

## 9. Parent Space and Organization Directory

Space hierarchy MAY aid discovery, but parent membership does not grant child membership or child read access.

Rules:

- Parent Space MAY list child Space previews only if child's `cx.space.discovery` payload has `directory_visibility.parent_space_directory=true`.
- Organization directory MAY list Space previews only if Space discovery policy allows organization directory listing and the organization endorsement is valid.
- Removing a Space from an organization directory does not revoke membership or delete data.
- Revoking `cx.space.organization` endorsement MUST remove official directory badges once the directory catches up.

## 10. Security Requirements

Directory and discovery implementations MUST defend against:

- Space id enumeration
- alias guessing
- member count probing
- hidden organization probing
- private handle correlation
- pairwise DID correlation
- raw connection identifier leakage
- private contact graph reconstruction
- timing side channels that reveal hidden existence
- stale official badge after organization endorsement revocation

For high privacy deployments, clients SHOULD prefer invite links or encrypted out-of-band invitations over directory search.

## 11. Conformance

Directory-capable implementations MUST test:

- public Space search
- listed organization directory search
- restricted search with valid and invalid claim presentation
- unlisted exact resolve
- invite-only indistinguishable not_found
- official Space verification through `cx.space.organization`
- hidden pairwise DID exclusion
- stale result rejection after discovery policy update
- private contact discovery does not disclose raw connection identifiers
