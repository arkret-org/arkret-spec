# Sidecar recovery and conformance closure

Status: resolved

## Finding

The dedicated Sidecar list deliberately exposes the Sidecar and its backing Circle but not the
unbounded set of hosted private context locators. A new controller device therefore had no
normative, mechanical way to discover the private Strand and `agent_sidecar_of` Relation needed
to rebuild Event-truth exchange projections. Existing prose also described digest, cache,
privacy, revoke, publish, accepted request identity, and hosted UI behavior without independently
registered executable vectors.

## Resolution

`spec/v1/zh/models/sidecar.md` now requires complete controller-self pagination of Sidecar views
and Realm Event history, followed by unique pairing of controller-authored private
`ak.strand.create` and `ak.relation.create(kind=agent_sidecar_of)` Events in the exact backing
Circle effective scope. Incomplete pagination, repeated cursors, ambiguous candidates, or any
Realm/controller/scope mismatch remain unresolved and non-echo. This reuses accepted Event truth,
adds no discovery endpoint, and does not expose private locators through ordinary projections.

Eight independent vectors now cover context locator recovery, canonical sibling digest,
union-history frontier reconciliation, the non-disclosure surface matrix, revoke fail-closed,
explicit publish, accepted request identity, and the Chrome/Edge hosted UI matrix. Each vector is
registered in `vector-registry.json`, represented in `agent-sidecar-fixture.json`, and required by
the named Sidecar runner.

## Security properties

- Unauthorized callers cannot distinguish a Sidecar structural Event from a nonexistent object.
- Event query results used for recovery retain the complete accepted Event Envelope needed for
  canonical digest verification.
- Partial history never enables echo, terminal state, or request redelivery.
- Lifecycle revocation stops new work without fabricating an exchange terminal.
- Explicit publish is an allowlisted shared Event and cannot serialize private Event history.
