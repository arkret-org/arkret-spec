# `admission_capabilities` and `target_event_kinds` are not required to agree

Status: open (2026-07-31)
Detected by: `cotest` live harness migration to the Realm authority-root model
Affected surfaces: capability action registry, event kind registry, every receiver
that decides "does this grant authorize this Event kind?"

## Problem

A capability-gated event kind names the actions that admit it in
`admission_capabilities`. A capability action names the kinds it covers in
`target_event_kinds`. Nothing requires the two to be reciprocal, and today they
are not:

| event kind | `admission_capabilities` | listed back in that action's `target_event_kinds`? |
| --- | --- | --- |
| `ak.member.state` | `ak.realm.admin` | no |
| `ak.organization.moderation_policy` | `ak.policy.manage` | no |
| `ak.mimi.room_binding` | `ak.policy.manage`, `ak.realm.admin` | no |

Three of the four kinds that carry an explicit `admission_capabilities` list are
asymmetric.

This matters because a receiver has to pick one direction to answer "does this
grant authorize this kind?", and the two directions give different answers. A
receiver that reads `target_event_kinds` — which is what the aggregate-coverage
rules in `zh/authz/capabilities.md` §5.0.1 and §10.1 are written against —
concludes that **no** registered action authorizes `ak.member.state`, so no grant
can ever admit it. A receiver that reads `admission_capabilities` concludes that
`ak.realm.admin` does.

`ak.realm.owner` does not cover `ak.member.state` either (it is not among the
aggregate's 107 kinds), so under the `target_event_kinds` reading, adding a
member outside the closed genesis unit is unauthorizable by any principal.

## What the lint gate does and does not check

`tools/lint_artifacts.py` validates that each name in `admission_capabilities`
resolves to a registered action. It does not check the reverse edge. The
prose↔registry equivalence gate described in `capabilities.md` §5 covers
`target_event_kinds` against the §5.1–§5.6 prose enumeration, not against
`admission_capabilities`, so this drift passes every current gate.

## Question for the spec

Which field is authoritative for admission, and what invariant should the lint
enforce?

1. **Reciprocity.** `kind ∈ action.target_event_kinds ⟺ action ∈
   kind.admission_capabilities`, enforced bidirectionally by lint. This is the
   simplest rule, but it grows the aggregate admin actions' coverage sets — and
   §5.0.1 fixes those sets behind an RFC precisely to stop authority creep, so
   the three additions would each need that treatment.
2. **`admission_capabilities` is authoritative for admission**, and
   `target_event_kinds` is only the grant-authority / narrowing surface. Then
   the aggregate-coverage rules need to say so explicitly, and every receiver
   that currently answers admission from `target_event_kinds` is reading the
   wrong field.
3. **`target_event_kinds` is authoritative** and the three
   `admission_capabilities` entries are stale. Then `ak.member.state` has no
   admitting action at all and needs one.

## Current implementation state

`cotest`'s harness treats an action as covering a kind when **either** direction
says so (`src/harness/client.rs`, `action_covers_kind`). That is a test-tool
workaround chosen so the harness does not silently encode an answer to the
question above; it should be replaced by whichever rule the spec settles on.
