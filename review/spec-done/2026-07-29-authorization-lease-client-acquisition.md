# Authorization lease client acquisition is undefined

Status: closed (2026-07-29)  
Closed by: `ak.self.authorization_leases.command.issue` plus its schema, OpenAPI binding, profile and fixture at the current HEAD.
Detected by: `cotest` joint-full run `20260729-043955`  
Affected surfaces: Account Authority, Principal Server, clients, offline publication, conformance

## Problem

`authz/offline-publication.md` requires every initial Event publication to carry an
authority-issued `AuthorizationLease`. A client must not mint this object because its basis,
authority-set reference, expiry, and proofs are assertions made by the accepted authorization
authority.

The current v1 operation registry, typed schemas, and HTTP binding do not define an operation by
which an authenticated device obtains or renews such a lease. As a result, a conforming client has
no executable path from account re-authorization to first Event publication.

The genesis case is additionally circular. `AuthorizationLease.basis_ref` currently permits only
an accepted Seal or a complete accepted multi-leaf Seal basis, while both ordinary Realm bootstrap
and Principal Control Realm bootstrap occur before that Realm has any accepted Seal. Nevertheless,
`ak.self.events.command.submit` requires an `EventInitialSubmission` for every bootstrap Event.
There is therefore no schema-valid basis value that can authorize the first Seal's own anchor unit.

This is observable in the current Inkson implementation:

- `authorization_lease::initial_submission` correctly fails closed when no covering lease exists.
- `authorization_lease::install_lease` has no production caller.
- Principal bootstrap cannot publish its closed create/authorize unit and reports that the account
  must be re-authorized, but re-authorization cannot return or fetch the required protocol object.

## Impact

- First Principal Control Realm publication is blocked.
- Realm/message authoring is blocked after a lease expires or is cleared.
- Offline authoring cannot determine whether it holds a usable publication window.
- Session-grant possession and DPoP authentication cannot be translated into the distinct,
  basis-bound publication authority required by the Event submit contract.
- End-to-end and Agent Journey tests cannot complete without inventing authority material in the
  client or using a noncanonical test bypass.

## Required design decisions

The closure must define one canonical flow, including:

1. The issuing service and trust surface for Principal Control Realm and ordinary Realm scopes.
   The design must also define a non-circular, cryptographically bound genesis authorization basis;
   it cannot reference the not-yet-created Realm's accepted Seal.
2. A typed operation, request/response schemas, operation-registry entry, HTTP binding, and service
   discovery/profile obligations.
3. Request binding to actor, authorized device, exact `scope_ref`, action, accepted basis,
   authority set, audience, holder key, challenge, issued-at, expiry, and replay protection.
4. Whether a session-grant exchange may return leases atomically or whether lease issuance is a
   separate command; the protocol must not require a client-visible intermediate bearer exchange.
5. Renewal/re-authorization semantics, including narrowing, expiry, revocation, device-generation
   change, authority-set rotation, response loss, idempotent retry, and concurrent requests.
6. Offline rules: maximum duration, storage and clearing requirements, clock skew, and the exact
   fail-closed behavior when the accepted basis cannot be proven.
7. Issuance and verification conformance vectors, including wrong actor/device/scope/action/basis,
   stale authority set, expired lease, replay, and renewal after revocation.

## Proposed closure

Register `ak.self.authorization_leases.command.issue` at
`POST /_arkret/self/authorization-leases`. Its request carries the final, signed Event or ordered
Event batch that the client intends to publish:

```text
AuthorizationLeaseIssueRequest {
  events: Event[1..500]
}
```

The response preserves request order and returns exactly one lease for every Event:

```text
AuthorizationLeaseIssueOutcome {
  authorization_leases: AuthorizationLease[1..500]
}
```

The authenticated Principal Server is the issuer and audience. Before issuing anything it MUST run
the same actor/session, device generation, Event proof, registry, Realm policy, CBA, capability,
frontier, and closed-unit validation that the later submit will run. Issuance is not a reservation
and does not commit an Event, advance a frontier, or guarantee later acceptance. It only attests
that the named actor/device may first-publish the matching action against the named basis until the
bounded expiry.

For an ordinary Event, the lease basis is copied from the Event's already accepted `seal_ref` or
complete `seal_basis`; the server MUST resolve and validate that basis before signing. The lease
`action` is a registered capability action whose `target_event_kinds` contains the Event kind, and
its `risk_tier` is copied from the capability action registry. The server MUST select an action
that the actor actually holds at that basis; it cannot choose a weaker convenient action.

For the three registered genesis families only—ordinary Realm founding units, self-principal PCR
bootstrap units, and managed Agent PCR create bound to an accepted controller delegation—
`basis_ref` may instead be:

```text
{
  "anchor_unit": {
    "realm_id": "ak:realm:...",
    "event_digests": ["sha256:...", "..."],
    "unit_digest": "sha256:..."
  }
}
```

`unit_digest = sha256(canonical_json({realm_id,event_digests}))`, with Event digests in required
unit order. This is not a general unaccepted-state basis. It is valid only when the issuer has
validated one complete registered closed anchor unit, including its root/enrollment authority
proofs, creator/session binding, notary declaration, exact order, actor chain, and zero prior Realm
state. A submitter MUST use the same complete unit and parallel leases; any digest/order/cardinality
change fails before persistence.

The endpoint is idempotent by canonical request digest under the standard `Idempotency-Key` header.
An identical retry returns byte-identical leases and expiry; reuse with different bytes is
`duplicate_conflict`. Leases use the authenticated session's device id, the issuer's current
basis-resolved authority-set reference, an audience containing the issuing service DID, and the
normal risk-tier TTL ceilings. Session/device revocation, generation change, authority-set change,
or basis staleness blocks new issuance; already issued leases remain bounded by their signed expiry
and normal revocation policy.

Clients MAY request a replacement before expiry. They MUST key held leases by actor, device, scope,
action, basis and authority-set digest; clear them on sign-out/account switch/device revocation;
and fail closed when acquisition cannot be completed. Offline publication uses only a previously
installed unexpired lease and never calls this operation implicitly while offline.

## Non-solutions

- Client-side lease minting or fixture signatures in production code.
- Treating a session grant as an implicit authorization lease.
- Pointing `basis_ref` at a not-yet-accepted or fabricated genesis Seal.
- An unregistered `/_arkret/*` route.
- Omitting the lease for bootstrap, UI, development mode, or “online” publication.
- Widening one Realm-scoped lease to another scope or action.

## Closure criteria

- Canonical prose, registries, schemas, OpenAPI, profile matrix, and conformance vectors agree.
- Shared SDK owns the wire DTOs and typed client calls.
- The issuing authority returns a verifiable lease through the canonical flow.
- Inkson installs, persists, renews, expires, and clears leases without minting them.
- Soland validates the same shared type and basis/authority proofs.
- A real browser can register, bootstrap a Principal, create a Realm, publish while offline within
  the lease window, reconnect, and fail closed after expiry/revocation.
- The issue moves to `review/spec-done` only after the full joint and Agent Journey evidence passes.
