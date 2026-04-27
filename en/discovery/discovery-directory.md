# Discovery and Directory Draft

## 1. Scope

Contrix must clearly separate:

- resource discoverability
- previewability
- read/write access

Discoverability does not imply read; read does not imply join; join does not imply write.

This document defines discovery for Space, Organization, Actor, and Applet, directory services, and anti-enumeration requirements.

## 2. Discoverability Levels

`discoverability` values:

| Value | Meaning |
| --- | --- |
| `public` | Visible to public index and search. |
| `listed` | Listed in allowed directories or organization pages but not necessarily public search. |
| `restricted` | Visible only to holders satisfying verifiable conditions such as membership, organization claim, or invited state. |
| `unlisted` | Not included in search; MAY be resolved by exact id/alias/invite link or parent edge when policy allows. |
| `invite_only` | Uninvited or non-proof subjects should not learn existence; responses should blur with non-existence. |
| `secret` | Visible only in local or E2EE context; directories/relays should not expose enumerable metadata. |

Defaults:

- New Space defaults to `invite_only`.
- New Organization profile defaults to `listed` but MAY be `restricted` or `unlisted`.
- Pairwise/private DID defaults to `secret`.
- Public persona DID defaults to `public` or `listed` according to holder policy.

## 3. Space Discoverability

Space discoverability SHOULD be expressed by `cx.space.discovery` state:

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

Rules:

- `discoverability=public` MAY be indexed by public directory services.
- `listed` Space MUST be listed only by directories explicitly allowed by `directory_visibility` / `directory_services`.
- `restricted` Space MUST require authorization checks before returning search result.
- `unlisted` Space MUST NOT appear in keyword search, but MAY resolve via exact alias/id/invite path.
- `invite_only` and `secret` queries from unauthorized subjects MUST return `not_found` or equivalent response.
- Directory results MUST NOT return event history, full member lists, raw policy, MLS state, hidden edges, or full governance chain unless separately authorized.

`join_rule` only controls join process; discoverability and join can be configured independently.

## 4. Organization Discoverability

Organization discoverability SHOULD be represented by profile state or governance registry:

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

Organizations may be public, restricted, or unlisted. A resolvable DID alone MUST NOT expose member list, service topology, or governance strategy.

Directory clients SHOULD verify:

1. Organization DID is resolvable.
2. Discovery profile is signed by organization DID or governance service.
3. Each official Space is checked against `cx.space.organization`.
4. Directory service DID is trusted by organization policy or trust framework.

## 5. Actor and Handle Discoverability

Actor / Principal discovery MUST preserve holder privacy:

- Public persona MAY appear in public directory.
- Pairwise/private DID, device DID, sensitive agent DID MUST NOT appear by default.
- Handle search MUST only return handles with public binding or holder permission.
- Presence/common-space/organization-membership/contact graph MUST NOT leak through ranking or autocomplete.

Unknown actor profile lookup in shared space is only for rendering authorized content (display name, avatar), not unrelated handles.

## 6. Directory Service

Directory service is a derivative index layer, not source of truth. It MAY index:

- public/listed Space previews
- public organization profile
- public persona profile
- applet metadata
- public handle records

Directory service MUST:

- expose service DID and feature profile
- apply auth filter before returning each result
- return stable pagination cursor
- provide freshness and source refs
- avoid leaking hidden existence via distinct errors

Directory service MUST NOT:

- list `invite_only` / `secret` resources to unauthorized parties
- expose full member lists without explicit permission
- expose private handles / pairwise DID / disclosure policy
- rank hidden resources in a way that leaks existence

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

Response:

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

Unauthorized hidden resource resolve SHOULD return:

```json
{
  "ok": false,
  "error": {
    "code": "not_found",
    "message": "not found"
  }
}
```

Implementations SHOULD keep status, latency class, and shape the same for missing vs unauthorized hidden resources.

## 8. Parent Space and Organization Directory

Space hierarchy can assist discovery, but parent membership does not imply child membership or read access.

Rules:

- Parent space MAY list child previews only when `directory_visibility.parent_space_directory=true`.
- Organization directory MAY list a child when policy allows and organization endorsement is valid.
- Removing a Space from org directory does not revoke membership or erase data.
- Revoking `cx.space.organization` endorsement MUST remove official directory badge once directory catches up.

## 9. Security Requirements

Directory implementations MUST defend:

- Space id enumeration
- alias guessing
- member count probing
- hidden organization probing
- private handle correlation
- pairwise DID correlation
- timing side-channels that reveal hidden existence
- stale official badge after endorsement revocation

For high-privacy deployments, clients SHOULD prefer invite links or encrypted out-of-band invitation instead of plain search.

## 10. Conformance

`cx.profile.directory.v1` SHOULD test:

- public space search
- listed organization search
- restricted search with valid/invalid claim presentation
- unlisted exact resolve
- invite-only indistinguishable not_found
- official space verification through `cx.space.organization`
- hidden pairwise exclusion
- stale result rejection after discovery policy update

