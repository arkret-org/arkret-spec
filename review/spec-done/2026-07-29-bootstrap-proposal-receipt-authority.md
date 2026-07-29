# Closed-genesis proposal receipt authority is ambiguous

Status: closed (2026-07-29)  
Closed by: the closed-genesis ingress authority rule in `spec/v1/zh/authz/cba-profiles.md` section 3.
Detected by: `cotest` real-browser onboarding run `20260729-064857`  
Affected surfaces: CBA proposal ingress, Principal Control Realm bootstrap, Realm bootstrap

## Problem

Every accepted Control Move must have an immutable `ControlProposalReceipt`. The normal issuer is
the Realm's current authority set. A closed genesis unit, however, creates that authority set. In a
self-principal PCR the founding notary is the newly authorized device, so the Principal Server
cannot sign as that not-yet-effective device authority. Requiring the current notary to acknowledge
the unit is circular and made real onboarding fail with `quorum_unreachable`.

The protocol distinguished publication admission authority from Seal notarization for
`AuthorizationLease`, but did not say which authority acknowledges proposal ingress during the
same pre-authority closed genesis window.

## Proposed closure

For the registered closed genesis families only, the Principal Server that completed full
pre-admission and issued the unit's `AuthorizationLease`s MAY also issue the proposal receipts.
Those receipts:

- use the same `authority_set_digest` as the parallel leases;
- bind each exact Event digest and the genesis Realm;
- are signed by the lease-issuing service and remain mere ingress acknowledgements;
- do not authorize a Move, create accepted state, or substitute for the founding notary;
- are stored atomically with the pending closed unit and returned byte-identically on duplicate;
- expire and enter the normal bounded-decision/health path if the client does not submit a valid
  founding Seal.

If an effective Realm notary authority already exists, the ordinary authority-set receipt path is
mandatory. A service MUST NOT use the genesis ingress exception for reanchor, recovery, or any
ordinary Control Move.

The first accepted Seal remains signed by the founding notary declared by the closed unit. Its
validation must independently recompute the complete genesis state and does not trust the proposal
receipt as authorization or finality.

## Closure criteria

- Canonical CBA and bootstrap prose state the narrow exception and signer verification rules.
- Soland uses the lease authority digest only for a validated closed genesis unit.
- Ordinary and reanchor submissions cannot select the exception.
- Positive self-PCR/Realm genesis and negative forged/mismatched receipt tests pass.
- Real browser onboarding and the federated Agent Journey pass.
- Move this issue to `review/spec-done` only after those checks pass.

