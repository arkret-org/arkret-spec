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

- `discoverability=public` 的 Space MAY 被公共目录服务索引。
- `listed` Space MUST 仅出现在 `directory_visibility` 或 `directory_services` 明确允许的目录中。
- `restricted` Space MUST 在返回搜索结果前要求目录查询授权。
- `unlisted` Space MUST NOT 出现在关键字搜索，但在 policy 允许时 MAY 通过精确 id / alias / 签名 invite / parent edge 解析。
- 未授权 subject 对 `invite_only` 与 `secret` Space 的查询 MUST 返回 `not_found` 或与其不可区分的响应。
- 在未单独授权时，目录结果 MUST NOT 包含事件历史、成员列表、policy 原文、MLS 状态、隐藏 parent/child edge 或完整组织治理链。

`anti_enumeration.member_count_mode` 取值 normative：

| 模式 | 行为 |
| --- | --- |
| `exact` | 返回精确成员数；仅在 `discoverability ∈ {public, listed}` 时允许。 |
| `bucketed` | 返回**封闭 bucket** 之一：`1-10` / `11-50` / `51-100` / `101-500` / `501-2000` / `2000+`。Directory 实现 MUST 使用本 bucket grid，不得自定义粒度（防止粒度差异成为枚举侧信道）。请求方收到不在此枚举的 bucket 字符串 MUST 视作 `invalid_response` 并丢弃。 |
| `omit` | 不返回成员数；任何隐含的 hint（如返回组员数组的 length）也 MUST 被裁剪。 |

`unlisted` / `invite_only` / `secret` Space 的 `member_count_mode` 默认 `omit`；显式声明 `bucketed` 时必须遵守上述 bucket grid。

`join_rule` 只控制加入流程。公开可发现的 Space MAY 仍要求 invite、knock 或 restricted join。不可发现的 Space MAY 对持有私有链接的成员保持 `join_rule=public`，但除非配套强反垃圾策略，否则不推荐。

`history_visibility` 只控制历史读取范围。`discoverability=public` MUST NOT 隐含 `history_visibility=world_readable`。

### 3.x `discoverability × join_rule × history_visibility` 兼容矩阵（normative）

下表声明 v1 在三组维度上**允许 / 禁止 / 不推荐**的组合。`✓` = 允许；`!` = 允许但 SHOULD 在 Space create 时显示警告；`✗` = MUST 拒绝（reducer 在 `cx.space.policy_components` accept 时返回 `policy_combination_invalid`）。本表不替代 §3 与上方各 enum 的语义；当某条规则与本表冲突时，更严格者（拒绝/警告）优先。

| discoverability ↓ \ join_rule → | `public` | `invite` | `knock` | `restricted` | `knock_restricted` | `closed` |
| --- | --- | --- | --- | --- | --- | --- |
| `public` | ✓ | ✓ | ✓ | ✓ | ✓ | ! |
| `listed` | ! | ✓ | ✓ | ✓ | ✓ | ! |
| `restricted` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `unlisted` | ✗ | ✓ | ! | ✓ | ✓ | ✓ |
| `invite_only` | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ |
| `secret` | ✗ | ✓ | ✗ | ✗ | ✗ | ✓ |

`history_visibility` 与上述任一组合搭配时的额外约束：

- `world_readable` MUST NOT 与 `discoverability ∈ {invite_only, secret}` 同时声明（拒绝）。
- `world_readable` 与 `discoverability ∈ {unlisted, restricted}` 同时声明 MUST 在 join warning 显式告知（"任何持有 link 的方都可读取全部历史"）。
- `shared` / `invited` / `joined` 与所有 discoverability 组合兼容。
- `restricted` 历史可见性 MUST 与显式 history-sharing policy 一致；与 `discoverability=public` 组合时仍 SHOULD 限制 lazy member preview 防止枚举。

实现 MUST 在 `cx.space.policy_components` reducer 接受前用本表校验当前 effective 状态；变更任一字段使组合落入 `✗` 时 MUST 返回 `policy_combination_invalid` 并保留旧值。本表是 v1 wire 互操作的最小集，profile 可以**收紧**但不得放宽。

## 4. Organization 可发现性

Organization discovery policy SHOULD 通过组织 profile 状态或 governance registry 记录表达：

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

## 5. Actor 与 Handle 可发现性

Actor / Principal 发现 MUST 尊重 holder 隐私：

- 公开 persona MAY 出现在公共用户目录中。
- Pairwise DID、私有 DID、设备 DID 与隐私敏感的 agent DID 默认 MUST NOT 出现在公共目录中。
- Handle 搜索 MUST 仅返回绑定公开或 holder 已显式授权披露的 handle。
- Presence、common Space、组织成员与联系人图谱 MUST NOT 通过搜索排序或自动补全泄露。

在共享 Space 中查询未知 actor profile，仅允许在渲染已授权内容（如显示名、头像）所必需的范围内进行；MUST NOT 借此泄露无关 handle 或组织账号。

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
      "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
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
        "cx:event:36531ccc-395a-7455-9880-000000000000",
        "cx:event:36531cd0-e580-7bb1-a8ab-310000000000",
        "cx:event:36531c0c-4155-7fd5-a082-b15662000000"
      ]
    }
  ],
  "next_cursor": null
}
```

未授权对隐藏资源的精确 resolve SHOULD 返回：

```json
{
  "ok": false,
  "error": {
    "code": "not_found",
    "message": "not found"
  }
}
```

实现 SHOULD 对"不存在"与"未授权访问的隐藏资源"使用相同的 status、相同时延等级与相同响应结构。

## 9. Parent Space 与 Organization Directory

Space 层级 MAY 协助发现，但 parent 成员资格不授予 child 成员资格或 child 读权限。

规则：

- Parent Space MAY 列出 child Space 预览，仅当 child 的 `cx.space.discovery` payload 中 `directory_visibility.parent_space_directory=true` 时成立。
- Organization 目录 MAY 列出 Space 预览，仅当 Space discovery policy 允许组织目录列出且组织背书有效时成立。
- 把 Space 从组织目录中移除不会撤销成员资格或删除数据。
- 撤销 `cx.space.organization` 背书 MUST 使官方目录徽章在目录刷新后被移除。

## 10. 安全要求

目录与发现实现 MUST 防御：

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

在高隐私部署中，客户端 SHOULD 优先使用 invite 链接或加密的带外邀请，而不是目录搜索。

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
