# Discovery and Directory Draft

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
| `secret` | 仅本地或端到端加密上下文中可见；目录、Sync Service、Index 不应公开可枚举 metadata。 |

默认值：

- 新 Space 默认 `invite_only`。
- 新 Organization profile 默认 `listed`，但 MAY 设置为 `restricted` 或 `unlisted`。
- Pairwise / private DID 默认 `secret`。
- Public Persona DID 默认 `public` 或 `listed`，由 holder policy 决定。

## 3. Space Discoverability

Space discovery policy SHOULD 由 `cx.space.discovery` state event 表达：

```json
{
  "type": "cx.space.discovery",
  "state_key": "",
  "content": {
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
        "topic",
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
  "type": "cx.organization.discovery",
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
    "type": "detached_jws",
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

## 6. Directory Service

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

## 7. Service Surface

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

`search-spaces` request:

```json
{
  "query": "release",
  "scope": {
    "organization_did": "did:web:acme.example",
    "parent_space_id": null
  },
  "requester": "did:uuid:alice",
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
      "space_id": "cx:space:01JS0SP000000000000000000",
      "name": "Release Coordination",
      "topic": "Public release coordination",
      "discoverability": "listed",
      "join_rule": "knock_restricted",
      "history_visibility": "joined",
      "official_organizations": [
        "did:web:acme.example"
      ],
      "preview_ref": "cx:event:01JS0PV...",
      "source_refs": [
        "cx:event:space_create_hash",
        "cx:event:space_discovery_hash",
        "cx:event:space_organization_hash"
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

## 8. Parent Space and Organization Directory

Space hierarchy MAY aid discovery, but parent membership does not grant child membership or child read access.

Rules:

- Parent Space MAY list child Space previews only if child `cx.space.discovery.directory_visibility.parent_space_directory=true`.
- Organization directory MAY list Space previews only if Space discovery policy allows organization directory listing and the organization endorsement is valid.
- Removing a Space from an organization directory does not revoke membership or delete data.
- Revoking `cx.space.organization` endorsement MUST remove official directory badges once the directory catches up.

## 9. Security Requirements

Directory and discovery implementations MUST defend against:

- Space id enumeration
- alias guessing
- member count probing
- hidden organization probing
- private handle correlation
- pairwise DID correlation
- timing side channels that reveal hidden existence
- stale official badge after organization endorsement revocation

For high privacy deployments, clients SHOULD prefer invite links or encrypted out-of-band invitations over directory search.

## 10. Conformance

`cx.profile.directory.v1` MUST test:

- public Space search
- listed organization directory search
- restricted search with valid and invalid claim presentation
- unlisted exact resolve
- invite-only indistinguishable not_found
- official Space verification through `cx.space.organization`
- hidden pairwise DID exclusion
- stale result rejection after discovery policy update
