---
akp: AKP-0017
title: Controller-scoped Agent Mention Selector
normative: false
stability: v1
updated: 2026-06-11
status: accepted
created: 2026-06-11
authors:
  - chris@acroidea.com
depends_on: [AKP-0008, AKP-0016]
discussion: internal (no public URL)
merged_into:
  - spec/v1/artifacts/schemas/agent-selector-claim.schema.json
  - spec/v1/artifacts/schemas/directory-operations.schema.json
  - spec/v1/artifacts/registry/contract-catalog.json
  - spec/v1/artifacts/registry/operation-registry.json
  - spec/v1/artifacts/profiles/conformance-profiles.json
  - spec/v1/zh/models/common-fields.md
  - spec/v1/zh/models/actor.md
  - spec/v1/zh/models/strand-and-message.md
  - spec/v1/zh/identity/identity-handles.md
  - spec/v1/zh/discovery/discovery-directory.md
  - spec/v1/zh/discovery/profiles-presence.md
  - spec/v1/zh/sync/service-surface.md
  - spec/v1/zh/sync/service-http-binding.md
  - spec/v1/zh/sync/transport-bindings.md
  - spec/v1/zh/conformance/schema-registry.md
  - spec/v1/zh/conformance/conformance-profiles.md
  - spec/v1/zh/conformance/conformance-vectors.md
---

> Historical rationale only. Normative text lives in the merged files listed above.

## Summary

Native personal agents SHOULD NOT need public handles. This AKP standardizes a controller-scoped input selector:

```text
@<controller-handle>/<agent_slug>
```

The selector is only a compose-time alias. Before persistence it MUST resolve to a structured mention node whose `subject_id` is the agent principal DID. The controller handle and slug MAY be retained only as audit / fallback metadata.

## Decisions

- `ak.schema.agent_selector_claim.v1` is the authoritative binding for `(controller_subject, agent_slug) -> agent subject`. The claim is signed by the controller or an issuer explicitly authorized by that controller, and carries the same visibility / audience / expiry / revocation posture as handle-layer claims.
- `agent_slug` is an optional Actor Profile projection hint for native personal agents. It is not authoritative by itself, and MUST NOT be inferred from the `did:webvh` `agents/<slug>` hosting path.
- For a given verified controller, a current visible selector MUST resolve to at most one active native personal agent. Missing, invisible, revoked, expired, or ambiguous claims fail closed.
- `ak.find.directory.resolve_agent_selector` is the exact Directory/profile resolver for cross-roster, CLI, and bridge use. It is not a search surface and MUST NOT support prefix, fuzzy, or candidate-list lookup.
- Any cross-roster / Directory / bridge selector resolve surface MUST use an anti-enumeration response: unauthorized, absent, hidden, revoked, expired, and ambiguous outcomes are indistinguishable to the requester.
- The selector never becomes a grant subject, actor attribution field, membership key, delivery key, Directory search key, or audit attribution source.
- Historical mentions remain bound to the persisted agent `subject_id`; slug changes affect only future input parsing.
