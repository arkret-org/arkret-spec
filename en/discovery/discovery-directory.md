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
| `secret` | Visible only in local or E2EE context; directories/Principal Servers should not expose enumerable metadata. |

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

## 6. Private Contact Discovery

Address-book style discovery is more sensitive than ordinary directory search. Implementations MAY support `cx.private_contact_discovery.v1` to discover reachable subjects without uploading raw contact identifiers or letting the Discovery Provider observe both requester DID and raw connection identifier.

Profile goals:

- Provider should not learn both requester stable DID and raw email/phone/username.
- Requests use batching, padding, rate limiting, time-bound proofs, and anti-enumeration behavior.
- Results return minimal reachability material, not full profiles or social graph.

Recommended flow:

1. Client normalizes connection identifiers locally and computes blinded tokens.
2. Client submits a padded blinded batch over anonymized or identity-separated transport.
3. Provider returns time-bound signed reachability proofs for discoverable entries.
4. Client discloses its DID, pairwise DID, or presentation only when the user confirms contact or invite.

Raw email, phone, address-book labels, local contact names, and unsalted low-entropy hashes MUST NOT be sent to public Directory services.

## 7. Directory Service

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

Field-level definitions:

| operation_id | Required fields | Optional fields | Response fields | Constraints |
| --- | --- | --- | --- | --- |
| `cx.directory.describe` | none | none | `service_did: did`; `resource_types: string[]`; `discovery_profiles: string[]`; `restricted_query_proof: boolean?` | `public_metadata`; rate-limitable. |
| `cx.directory.search_spaces` | none | `query: string`; `organization_did: did`; `parent_space_id: id`; `requester: did`; `proofs: proof[]`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | Filter every result by discoverability, requester proof, and Space policy; hidden resources must not leak existence. |
| `cx.directory.resolve_space` | one of `space_id: id`, `alias: string`, `invite_token: string`, `signed_link: string` | `requester: did`; `proofs: proof[]` | `space_preview: object`; `stripped_state: object[]?`; `join_rule: string?`; `via_services: did[]?` | Invite / restricted / secret Spaces use uniform `not_found` for unauthorized requests. |
| `cx.directory.search_organizations` | none | `query: string`; `claims: object`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | Only public or authorized-discoverable organizations. |
| `cx.directory.resolve_organization` | one of `organization_did: did` or `handle: string` | `proofs: proof[]` | `organization_preview: object`; `did_document_ref: string?`; `endorsements: object[]?` | Organization resolution does not disclose members, Space lists, or service topology. |
| `cx.directory.search_actors` | none | `query: string`; `space_id: id`; `organization_did: did`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?` | Must not reveal pairwise/private DIDs or undisclosed organization accounts. |
| `cx.directory.resolve_handle` | `handle: string` | `expected_did: did`; `proof_challenge: string` | `did: did`; `handle: string`; `verified: boolean`; `claims: object[]?` | Private handles require presentation. |

`search-spaces` request example (not a complete schema):

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

Response example (not a complete schema):

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

## 9. Parent Space and Organization Directory

Space hierarchy can assist discovery, but parent membership does not imply child membership or read access.

Rules:

- Parent space MAY list child previews only when `directory_visibility.parent_space_directory=true`.
- Organization directory MAY list a child when policy allows and organization endorsement is valid.
- Removing a Space from org directory does not revoke membership or erase data.
- Revoking `cx.space.organization` endorsement MUST remove official directory badge once directory catches up.

## 10. Security Requirements

Directory implementations MUST defend:

- Space id enumeration
- alias guessing
- member count probing
- hidden organization probing
- private handle correlation
- pairwise DID correlation
- raw connection identifier leakage
- private contact graph reconstruction
- timing side-channels that reveal hidden existence
- stale official badge after endorsement revocation

For high-privacy deployments, clients SHOULD prefer invite links or encrypted out-of-band invitation instead of plain search.

## 11. Conformance

`cx.profile.directory.v1` SHOULD test:

- public space search
- listed organization search
- restricted search with valid/invalid claim presentation
- unlisted exact resolve
- invite-only indistinguishable not_found
- official space verification through `cx.space.organization`
- hidden pairwise exclusion
- stale result rejection after discovery policy update
- private contact discovery does not disclose raw connection identifiers
