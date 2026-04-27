# Conformance Suite (Interoperability Test Plan)

## 1. Goal

Move the draft into an implementable interoperability surface by forcing repeatable behavior across:

- canonical operations
- reducer convergence (especially auth/state)
- redaction and redacted field preservation
- capability and delegated authorization
- repo, sync, index, E2EE, applet, and policy-server interoperability

This version does not introduce a new space version. Compatibility evolution is handled in `space_version=1` through explicit profile gating and deprecation policy.

## 2. Test Profiles

- `cx.profile.minimal_client.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.repo_node.v1`
- `cx.profile.principal_server.v1`
- `cx.profile.index_node.v1`
- `cx.profile.identity_registry.v1`
- `cx.profile.blob_node.v1`
- `cx.profile.applet_bridge.v1`
- `cx.profile.enterprise_client.v1`
- `cx.profile.agent_runtime.v1`

## 3. OpenAPI and Transport Mapping

### 3.1 OpenAPI shape

Each implementation must verify:

- required HTTP operations for identity/repo/sync/index/blob/authz
- stable `operationId` mappings in `service-api-schema.md`
- transport-mapping consistency (HTTP ↔ gRPC/WebSocket/SSE/MQ) for at least selected canary vectors

### 3.2 Canonical envelope

- canonical JSON generation and canonicalization errors
- stable op/event hash under cross-service replay
- deterministic handling of nonce/idempotency keys

## 4. Vector Layers

### 4.1 Existing layers

- `sync-conformance-vectors.md`: timeline order, pagination gaps, snapshot frontier, MLS epoch backfill, decryption pending.
- `encoding-conformance-vectors.md`: canonical JSON, digests, signature bindings, HLC, cursor, encrypted envelope digest.
- `state-resolution-conformance-vectors.md`: state conflict, deterministic winner, and conflict record fixtures.
- `redaction-conformance-vectors.md`: redaction preserve fields and index/audit consistency fixtures.
- `capability-conformance-vectors.md`: delegation chain, revoke rollback, approval constraint fixtures.

### 4.2 State Resolution (new baseline)

- `cx.vector.state_resolution.conflict_membership.v1`
  - concurrent membership state for one `(kind, state_key)`.
  - expected: deterministic winner chain, full conflict record, stable replay results.
- `cx.vector.state_resolution.capability_rebind.v1`
  - concurrent grant/revoke/regrant with auth-state dependency.
  - expected: only auth-valid candidates win; invalid candidates are dropped.
- `cx.vector.state_resolution.schema_update.v1`
  - concurrent updates to space-level governance states.
  - expected: priority ordering + deterministic tie-break applies.

### 4.3 Redaction (new baseline)

- `cx.vector.redaction.preserve_fields.v1`
  - redaction of event with allowed + denied fields.
  - expected: keep redacted envelope fields only; remove mutable content fields exactly as spec.
- `cx.vector.redaction.policy_scope.v1`
  - redaction in encrypted/plain, historical/frozen space cases.
  - expected: index and audit views remain consistent; no physical delete assumptions.

### 4.4 Capability (new baseline)

- `cx.vector.capability.delegate_chain.v1`
  - grant delegation chain with selector constraints.
- `cx.vector.capability.revoke_rollback.v1`
  - effect of revoke on historical auth checks.
- `cx.vector.capability.approval_constraint.v1`
  - approval constrained action without approval must go to proposal/quarantine path, not pass.

## 5. Component Matrix (required tests)

| Component | MUST | SHOULD |
| --- | --- | --- |
| Minimal/Full Client | filters, pagination, state_after, decryption_pending | snapshot frontier, causal wait |
| Repo Node | submitCommit, idempotent op writes, commit digest checks, signature validation | snapshot generation, receipt |
| Principal Server | sync-stream resume, backfill ordering, duplicate suppression, encrypted envelope forward | multi-upstream federation, snapshot pointers |
| Index Node | query reconstruction, authorization filtering, wait-for frontier, stale markers | notification materialization |
| E2EE Client | epoch recovery, to-device, removed-member fail-closed | local plaintext search coordination |
| Applet Bridge | registration signature, transaction idempotency, namespace conflicts, unauthorized write rejection | portal-space mapping |
| Policy Server | decision signing, replay protection, hard_deny/quarantine semantics | federation secondary checks |
| Identity Registry | DID log continuity, witness receipt, method adapter metadata | witness-only, read replica |

## 6. Delivery

- Implementations SHOULD publish vector pass/fail results per profile.
- Each failure must include a minimal reproducible fixture.
- A profile cannot be marked interoperable until all MUST vectors pass.
- The suite remains under `space_version=1`; no space migration to a new version is allowed in this draft.

