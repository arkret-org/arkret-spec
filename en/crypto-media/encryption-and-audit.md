# Encryption and Auditability

Contrix uses MLS (RFC 9420) for group E2EE.

Auditable E2EE is explicit and transparent: compliance actors must be visible group members, and access must produce signed audit events before plaintext is released.

Bridge boundaries and Applets must not silently downgrade encrypted content into non-E2EE networks.

## MLS-Bound Application State

For E2EE Spaces, `cx.mls.commit` MUST authenticate an application state reference that covers at least:

- `space_id`
- `mls_group_id`
- previous and next MLS epoch
- membership frontier
- policy root
- capability root when relevant
- room metadata hash
- reducer profile

Clients MUST verify that the referenced Contrix state is accepted under `event-auth-state-resolution.md` before accepting the MLS epoch. If the state root cannot be backfilled or the hash does not match, the epoch is `decryption_pending` or `state_mismatch` and MUST NOT be used for new plaintext decryption.

Implementations SHOULD place this state reference in MLS AppSync, GroupContext extension, or an equivalent MLS application-state extension. If unavailable, it MUST be covered by the signed Event and the MLS Commit transcript hash.

## KeyPackage Claim Lifecycle

MLS KeyPackages are single-use materials, not reusable public records. E2EE implementations MUST model them as:

```text
published -> claimed -> consumed
          -> expired
          -> revoked
```

A claim MUST bind requester principal/service DID, device proof, intended Space or room id, required content/cipher capabilities, claim nonce, expiry, and Welcome routing service. A claimed KeyPackage MUST NOT be reused for another room, requester, or Welcome. Welcome processing MUST verify `keypackage_ref` / `claim_id`, device trust, expiry, revocation status, and principal binding.

## Minimal-Metadata Spaces

High-privacy Spaces MAY enable `cx.mls.minimal_metadata_space.v1`. MLS leaf credentials may use room-scoped pseudonymous credentials. The real principal DID, device identity, display profile, and optional handle are carried in an E2EE `cx.identity_link` visible only to room members.

Routing services may route by pseudonym, Space id, epoch, and event id; they MUST NOT require plaintext principal DID mapping unless Space policy explicitly declares the disclosure purpose, audience, expiry, and audit behavior.

## AAD Visibility

Encrypted-envelope AAD is controlled by Space `aad_visibility` policy:

- `hidden`: default; no stable message id in provider-visible metadata.
- `routing_hash`: expose only an irreversible routing hash.
- `opaque_id`: expose opaque event/message id for delivery diagnosis.
- `debug`: short-lived audited debugging profile.

Privacy Spaces SHOULD use `hidden` or `routing_hash`. Debug or enterprise profiles MUST declare the choice in policy and MUST NOT put body text, filenames, mentions, reply excerpts, or sender handles into AAD.

