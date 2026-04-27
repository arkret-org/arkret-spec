# Event Authorization and State Resolution

This file is the English companion for the detailed Chinese draft in `../../zh/authz/event-auth-state-resolution.md`.

It defines Space versions, event authorization, state resolution, redaction, soft-fail handling, and Space upgrades.

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


