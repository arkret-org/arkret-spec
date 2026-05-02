# Event Authorization and State Resolution

This file is the English companion for the detailed Chinese draft in `../../zh/authz/event-auth-state-resolution.md`.

It defines Space versions, event authorization, state resolution, redaction, soft-fail handling, and Space upgrades.

Before authorization and state resolution, receivers MUST validate HLC format and clock window. The v1 `5 minutes` value is the default hard future-skew ceiling for detecting impossible or forged future time; it is not the default ordering trust window for high-risk state events. Events beyond the hard ceiling MUST be rejected or quarantined and MUST NOT participate in winner selection.

Implementations and Space / reducer profiles SHOULD declare a smaller `expected_future_skew_ms`. When unspecified, server-originated writes SHOULD use 30 seconds as expected drift, and high-risk state events such as capability, membership, policy, MLS epoch, service binding, and Space upgrade SHOULD use 10 seconds or a smaller operationally justified window. Mobile, offline, or weakly synchronized profiles MAY use wider expected drift, but HLC MUST NOT override missing causal dependencies, `actor_seq` rollback, or revoke freshness. A candidate outside expected / observed drift SHOULD soft-fail or enter quarantine until backfill or policy checks confirm it. HLC is an ordering input only after schema, signature, authorization, clock-window, and causal-dependency checks pass.

## Space Upgrade And Tombstone

Space upgrades use `cx.space.upgrade` within the same `space_id` in this draft. Backward-compatible field additions may be enforced directly. Upgrades that introduce a new critical feature, authorization rule, reducer rule, or encryption semantic MUST use a multi-phase flow: `announcement`, optional `readiness_check`, then `enforcement`. The upgrade event must be signed by an actor with upgrade/admin capability and must cover `phase`, `target_schema_profile`, `target_reducer_profile`, `migration_policy`, `compatibility_mode`, `replacement_ref`, activation frontier / HLC, and readiness conditions.

Announcement does not allow writes that depend on the new semantics. Readiness receipts describe service / bridge / client capability only and do not replace local schema, authorization, or reducer validation. Enforcement MUST reference the announcement, satisfy readiness conditions or record an admin override, and bind the activation causal frontier. Nodes that do not support the target profile MUST stop accepting writes that depend on the new semantics after enforcement; they MAY continue read-only display of pre-upgrade accepted history or compatibility projections. Downgrade proxies MUST NOT translate away new authorization / reducer semantics and re-sign them as ordinary old-profile writes. Upgrades MUST NOT rewrite historical event hashes.

If a Space is closed, replaced, or migrated to a new Space, it MUST use an explicit `cx.space.tombstone` state event. Tombstone changes future writes and default presentation; it does not delete history. A tombstoned Space rejects ordinary new writes and only allows maintenance events such as redaction, export, legal hold, account lifecycle, or migration proof. A replacement Space must be independently verified and does not automatically inherit access to old history.

## Redaction And Erasure Boundary

`cx.redaction` is verifier-visible content masking. It is not a promise of global physical deletion.

When a Space policy, account lifecycle rule, legal request, or retention policy requires hard erasure, a service MAY delete local payload bytes, blob bytes, thumbnails, full-text indexes, embeddings, previews, and reversible derived content only after it has an accepted redaction, `cx.account.status{status="erasure_pending"}`, signed erasure receipt, retention expiry, or equivalent auditable authority. The service MUST retain a minimal verification stub containing the original event id, the original Event envelope digest / proof `payload_hash` needed to verify the event graph, redaction event id, erasure reason code, executing service DID, execution time, and signed receipt. It MUST NOT rewrite the original event hash, signature, or causal references.

The stub MUST NOT additionally retain standalone content hashes, payload-only digests, unsalted search fingerprints, or other verifier material that allows offline enumeration of erased low-entropy plaintext. If an audit process must commit to erased plaintext before deletion, it MUST use a per-event random salt or HMAC / pepper commitment; the secret is retained only inside a legal-hold boundary or destroyed according to the erasure policy. Existing event digests may already have replicated to other nodes or receipts, so hard erasure cannot promise removal of every hash trace. Privacy-sensitive plaintext Spaces SHOULD use E2EE or encrypted-content payload profiles so persistent verifiers expose ciphertext digests or irreversible routing hashes rather than plaintext content digests.

Backfill after hard erasure returns a redacted or erased stub, not the original plaintext and not a fabricated replacement event. Legal hold or audit retention blocks hard erasure, but default views must still honor accepted redaction. For E2EE content, key destruction prevents future access only; the protocol cannot erase plaintext already decrypted, exported, or copied by authorized members.

## Plaintext-Visible Services

Non-E2EE / non-content-encrypted private Spaces MUST explicitly declare services that may receive plaintext or reversible derived content:

```json
{
  "kind": "cx.space.plaintext_visible_services",
  "state_key": "",
  "content": {
    "services": [
      {
        "service_did": "did:web:server.acme.example",
        "service_type": "principal_server",
        "purposes": ["repo", "sync", "backfill"],
        "visibility": "private_plaintext"
      },
      {
        "service_did": "did:web:search.acme.example",
        "service_type": "delegated_search",
        "purposes": ["search", "notification", "preview"],
        "visibility": "derived_plaintext"
      }
    ]
  }
}
```

Services absent from this state event may only receive public content, encrypted envelopes, irreversible hashes, minimum routing metadata, or policy-allowed stripped previews. Revocation or replacement follows normal state resolution; after the effective point, old services MUST NOT receive non-encrypted private content.

## Policy Components And History Sharing

Complex Spaces SHOULD express policy as components instead of one large policy object. `cx.space.policy_components` can reference components for roles, preauthorization, asset privacy, logging, bot/Applet/agent participation, message expiration, operational limits, and history sharing. The component set SHOULD produce a `component_root` that is covered by the MLS-bound `policy_root`.

Roles are compatibility and UI bundles only; they do not replace capability checks.

E2EE Spaces that allow new members to receive pre-join history keys MUST declare `cx.space.history_sharing_policy`. That policy binds:

- roles or capabilities allowed to share history
- maximum shareable range
- whether automatic sharing is allowed
- whether an audit event is required before key material is sent
- withholding reasons such as unverified device, history not visible, or policy denied

History sharing weakens forward secrecy. Clients MUST make this visible before join and MUST check membership, device trust, history visibility, capability, and policy before sharing MLS history key material.

History key sharing MUST be bounded to the recipient principal, recipient device, epoch / range, policy hash, audit event, and sending-device signature. Ordinary clients MUST NOT retain old epoch plaintext secrets indefinitely just in case future members need history. Long-term retention requires protected key backup, an explicit Archive / Audit Node, or a legal-hold boundary with declared scope, audit duties, and revocation behavior.

