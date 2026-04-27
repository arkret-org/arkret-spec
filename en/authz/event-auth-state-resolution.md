# Event Authorization and State Resolution

This file is the English companion for the detailed Chinese draft in `../../zh/authz/event-auth-state-resolution.md`.

It defines Space versions, event authorization, state resolution, redaction, soft-fail handling, and Space upgrades.

## Space Upgrade And Tombstone

Space upgrades use `cx.space.upgrade` within the same `space_id` in this draft. The upgrade event must be signed by an actor with upgrade/admin capability and must cover `target_schema_profile`, `target_reducer_profile`, `migration_policy`, `compatibility_mode`, and `replacement_ref`.

Nodes that do not support the target profile MUST stop accepting writes that depend on the new semantics; they MAY continue read-only display of pre-upgrade accepted history. Upgrades MUST NOT rewrite historical event hashes.

If a Space is closed, replaced, or migrated to a new Space, it MUST use an explicit `cx.space.tombstone` state event. Tombstone changes future writes and default presentation; it does not delete history. A tombstoned Space rejects ordinary new writes and only allows maintenance events such as redaction, export, legal hold, account lifecycle, or migration proof. A replacement Space must be independently verified and does not automatically inherit access to old history.

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
        "service_did": "did:web:index.acme.example",
        "service_type": "index_node",
        "purposes": ["search", "notification", "preview"],
        "visibility": "derived_plaintext"
      }
    ]
  }
}
```

Services absent from this state event may only receive public content, encrypted envelopes, irreversible hashes, minimum routing metadata, or policy-allowed stripped previews. Revocation or replacement follows normal state resolution; after the effective point, old services MUST NOT receive non-encrypted private content.


