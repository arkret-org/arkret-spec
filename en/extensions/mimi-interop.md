# MIMI Interoperability

## 1. Goal

This document defines the Contrix MIMI interoperability profile. It does not turn Contrix core into a room-first protocol. Instead, it defines a testable **MIMI Provider Facade** around the Contrix Space / Repo / DID / capability model so MLS-backed Contrix Spaces and Channels can interoperate with MIMI providers.

`cx.profile.mimi_interop.v1` pins these draft versions:

- `draft-ietf-mimi-protocol-06`
- `draft-ietf-mimi-content-08`
- `draft-ietf-mimi-room-policy-03`
- `draft-kohbrok-mimi-identifiers-01`

These are Internet-Drafts. Implementations MUST declare the draft versions they support in `server/describe` and the MIMI provider directory. Wire changes caused by later drafts MUST be handled by a new interop profile version, not by changing `space_version=1` core state semantics.

## 2. Roles

| MIMI role | Contrix mapping |
| --- | --- |
| Provider | `mimi_provider_facade` service DID, usually exposed by a Principal Server or delegated Space Host. |
| Hub provider | Space Host / Principal Server that owns the MIMI room URI and provides MIMI fanout and groupInfo. |
| Follower provider | Remote provider participating in the MIMI room; represented as a federation peer or Applet bridge peer. |
| User / client | Contrix principal DID + device id, optionally pairwise DID or room-scoped pseudonym. |
| Room | MIMI projection of a Contrix Space, Channel, or Topic. |

The MIMI facade is not a new source of truth. Native Contrix truth remains signed Events, auth refs, state resolution, MLS-bound state roots, and reducer output. MIMI room state is an interoperability projection of that state.

## 3. Provider Discovery

MIMI-capable services MUST declare `service_type=mimi_provider_facade` in DID service discovery and `GET /api/v1/server/describe`.

Implementations SHOULD also expose:

```text
GET /.well-known/mimi-protocol-directory
GET /api/v1/mimi/provider-directory
```

The provider directory response MUST bind service DID, provider id, base URL, supported draft versions, endpoint list, MLS cipher suites, content profiles, room policy components, and signature proof. Clients and remote providers MUST verify service DID, HTTP Message Signature, TLS endpoint, DID service endpoint, and Space policy delegation.

## 4. Room Binding

Contrix objects exported as MIMI rooms MUST use `cx.mimi.room_binding`:

```json
{
  "kind": "cx.mimi.room_binding",
  "state_key": "mimi://example.com/rooms/01JSMIMI...",
  "content": {
    "profile": "cx.profile.mimi_interop.v1",
    "mimi_room_uri": "mimi://example.com/rooms/01JSMIMI...",
    "binding_scope": {
      "space_id": "cx:space:01JS0SP000000000000000000",
      "channel_id": "cx:channel:01JS...",
      "topic_id": null
    },
    "hub_provider": "did:web:mimi.example.com",
    "local_provider_role": "hub",
    "follower_providers": ["did:web:remote.example"],
    "mls_group_id": "base64url...",
    "content_profile": "application/mimi-content",
    "policy_component_root": "sha256:...",
    "created_at": "2026-04-30T00:00:00Z"
  }
}
```

Rules:

- `binding_scope.space_id` MUST reference an accepted Space. If `channel_id` or `topic_id` is present, the MIMI room timeline projects only that channel or topic.
- `hub_provider` MUST be delegated by Space policy, Organization DID, or participant DID.
- `local_provider_role` is `hub`, `follower`, or `bridge_only`.
- Creating, updating, or revoking a binding requires `cx.policy.manage`, `cx.space.admin`, or equivalent interop capability.
- E2EE MIMI rooms MUST bind `mls_group_id` and verify membership, policy, and capability through the MLS-bound application state root.

## 5. Endpoint Surface

Canonical operations:

| operation_id | HTTP binding | Meaning |
| --- | --- | --- |
| `cx.mimi.provider_directory` | `GET /mimi/provider-directory` | MIMI provider feature profile. |
| `cx.mimi.key_material` | `POST /mimi/key-material` | Claim MLS KeyPackage. |
| `cx.mimi.room_update` | `PUT /mimi/rooms/{room_id}/update` | Submit or forward room state / MLS update. |
| `cx.mimi.notify` | `POST /mimi/rooms/{room_id}/notify` | Provider-to-provider notification or fanout event. |
| `cx.mimi.submit_message` | `POST /mimi/rooms/{room_id}/messages` | Submit encrypted MIMI application message. |
| `cx.mimi.group_info` | `GET /mimi/rooms/{room_id}/group-info` | Fetch MLS groupInfo / room projection. |
| `cx.mimi.request_consent` | `POST /mimi/consent/request` | Request cross-provider contact or room invite consent. |
| `cx.mimi.update_consent` | `POST /mimi/consent/update` | Update consent state. |
| `cx.mimi.identifier_query` | `POST /mimi/identifiers/query` | Query reachability for a connection identifier or MIMI URI. |
| `cx.mimi.report_abuse` | `POST /mimi/report-abuse` | Submit abuse report, including E2EE frank evidence. |
| `cx.mimi.proxy_download` | `POST /mimi/proxy-download` | Proxy or oblivious asset download. |

All write endpoints MUST use HTTP Message Signatures or equivalent service proof and bind source service DID, destination service DID, provider id, MIMI room URI or target identifier, request canonical hash, created/expires, and body digest.

The facade first verifies the MIMI envelope, then maps it to a Contrix operation, event, or to-device message. The MIMI transport signature proves provider source only; it does not replace Actor DID/device signatures, MLS transcript validation, capability, or Space policy.

## 6. Key Material

`cx.mimi.key_material` MUST use the KeyPackage claim lifecycle in `device-crypto-verification.md`. Requests bind target identifier, intended MIMI room URI, Contrix `space_id`, required content and MLS capabilities, requester provider DID and proof, and whether minimal-metadata pseudonymous credentials are allowed.

Responses return claimed KeyPackages, `claim_id`, `keypackage_ref`, device binding, expiry, and capabilities. After Welcome succeeds, the KeyPackage MUST be consumed. Invisible users, unavailable devices, policy denied, and non-existent targets SHOULD use uniform failure behavior.

## 7. Message Submission

For `cx.mimi.submit_message`, the facade MUST:

1. Verify provider signature, room binding, destination, body digest, and replay window.
2. Verify MLS epoch and `cx.mimi.room_binding.mls_group_id`.
3. Verify the MLS-bound `application_state_ref`.
4. Map the MIMI content container to `cx.message.create`, `cx.message.revise`, `cx.message.redact`, `cx.reaction.add`, `cx.reaction.remove`, or `cx.relation.*`.
5. Preserve original MIMI envelope hash, provider id, message id, and accepted timestamp as interop metadata.
6. Return recoverable or fail-closed errors for missing authorization, epoch, content, or policy state.

MIMI provider accepted timestamps do not replace Contrix event creation truth. Native timeline order remains HLC / reducer based.

## 8. Content Mapping

MIMI facade MUST receive:

- `application/mimi-content`
- `text/plain;charset=utf-8`
- `text/markdown;variant=GFM-MIMI`

Mapping:

| Contrix | MIMI |
| --- | --- |
| `cx.content.text` plain | `text/plain;charset=utf-8` body part |
| `cx.content.text` markdown | `text/markdown;variant=GFM-MIMI` body part |
| `cx.content.composite` | MIMI multipart / body parts |
| `reply_context` + `replies_to` | MIMI reply behavior |
| `cx.reaction.add/remove` | MIMI reaction / unlike |
| `cx.message.revise` | MIMI edit |
| `cx.message.redact` | MIMI delete |
| `message_expiration` policy | MIMI expiring message field |
| attachment `blob_ref` | MIMI external content / asset reference |
| topic/thread relation | MIMI topic / threading field |

When sending to MIMI, the facade SHOULD generate the required or recommended MIMI media type and MAY include `application/vnd.contrix.content+json` as a proprietary alternative for lossless native content. Unknown MIMI extension fields MUST be preserved as original CBOR bytes or canonical hashes.

## 9. Room Policy Mapping

Contrix policy components map to MIMI room policy components:

| Contrix component | MIMI meaning |
| --- | --- |
| `roles` | room roles / capabilities |
| `preauth` | pre-authorized joins, join links, invite token |
| `history_sharing` | chat history policy |
| `asset` | upload domain, asset privacy, proxy download |
| `logging` | logging, retention, auditable disclosure |
| `bot` | bot / bridge / automated actor policy |
| `message_expiration` | message expiration |
| `operational` | fanout, limits, rate limits, failure behavior |

MIMI roles are only an interop projection. Contrix authorization still uses capabilities. Incoming MIMI role/policy updates MUST reduce to `cx.capability.*`, `cx.space.policy_components`, or concrete policy state and pass Contrix auth refs before they take effect.

## 10. Identifiers And Consent

MIMI identifiers MUST NOT become Contrix actors directly.

- MIMI provider identifier maps to service DID.
- MIMI user identifier maps to principal DID, pairwise DID, or pending invite proof.
- Connection identifier is discovery / consent input only.
- Display name is UI metadata only.

`cx.mimi.identifier_query` SHOULD use `cx.private_contact_discovery.v1`. `cx.mimi.request_consent` / `cx.mimi.update_consent` maps to holder-private consent state, invite, presentation request, or claim proof. Consent does not grant Space read/write permission.

## 11. Abuse Report And Proxy Download

`cx.mimi.report_abuse` maps to `cx.moderation.report`. E2EE reports SHOULD include message frank, encrypted evidence package, reporter signature, MIMI room id, provider id, and target event hash.

`cx.mimi.proxy_download` MUST follow `cx.space.asset_privacy_policy`. If policy requires `provider_proxy` or `ohttp_relay`, the facade MUST NOT return a direct object-store URL. Clients still verify content hash, ciphertext digest, and attachment metadata.

## 12. Conformance

`cx.profile.mimi_interop.v1` MUST test provider directory draft pinning, room binding lifecycle, KeyPackage single-use claim, content roundtrip, policy mapping, identifier-query privacy, consent isolation, E2EE report franking, proxy-download policy, and unsupported draft fail-closed behavior.

## 13. Decisions

Contrix v1 MIMI support is a facade profile:

- MIMI hub is not the Contrix truth source.
- MIMI room id does not replace `space_id`.
- MIMI user identifier does not replace DID.
- MIMI provider timestamp does not replace Contrix HLC / event hash.
- Capability / auth refs / policy server checks remain mandatory.
