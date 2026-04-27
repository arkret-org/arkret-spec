# Federation

Contrix federation connects Principal Servers and their delegated repo, sync, index, identity, and blob services across domains.

Federation relies on DID service identities, signed service requests, idempotent transactions, cross-domain Space joins, and backfill authorization. It does not require an independent third-party distribution service; Space operations move between participating Principal Servers or explicitly delegated Space Hosts.

## Service Identity

Each Principal Server, Repo, and Index node MUST have its own service DID. DID Document `service.type` uses protocol registered names such as `ContrixPrincipalServer`; service `describe` responses use runtime `service_type` values such as `principal_server`. Federation authentication MUST verify the binding between service DID, endpoint, request signature, and declared service type.

## Push Flow

When `server-alpha.com` receives a new op for a cross-domain Space and another participant Principal Server `server-beta.com` also serves that Space:

1. `server-alpha.com` detects that the op belongs to a cross-domain Space.
2. It resolves the peer Principal Server from Space policy, membership, and service delegation.
3. It binds the transaction to a destination service DID and a service binding snapshot.
4. It sends the signed op envelope to `server-beta.com`.
5. `server-beta.com` verifies actor signature, Space policy, service delegation, service binding, and causality before accepting.

The transaction body SHOULD include:

```json
{
  "origin": "did:web:server-alpha.com",
  "destination": "did:web:server-beta.com",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "service_binding_ref": {
    "space_policy_hash": "sha256:...",
    "membership_frontier": ["cx:evt:..."],
    "destination_service_type": "principal_server"
  },
  "ops": []
}
```

Recipient service binding rules:

- An actor DID MAY declare its controlled or delegated `ContrixPrincipalServer` endpoint.
- Organization DID or Space policy MAY assign a Principal Server for organization members, managed devices, or a specific Space.
- `sync_endpoints` list only shared Space Hosts or organization Principal Servers explicitly delegated by Space policy; it does not authorize arbitrary third parties to receive private content.
- Federation transactions MUST bind destination service DID, Space policy hash/version, membership frontier, and target endpoint.
- After service delegation revocation or member removal, non-encrypted private content MUST NOT be pushed to the old service DID after the effective causal point; historical backfill must be re-evaluated under the new visibility and history policy.

## Space Host / Sync Endpoints

Space metadata MAY contain `sync_endpoints` for explicitly delegated shared Space Hosts or organization Principal Servers:

```json
{
  "space_id": "cx:space:01JS0SP000000000000000000",
  "sync_endpoints": [
    {
      "did": "did:web:server-alpha.com",
      "endpoint": "https://server-alpha.com/api/v1",
      "role": "primary",
      "service_type": "principal_server",
      "plaintext_visible": true
    }
  ]
}
```

If `plaintext_visible` is true, the service DID MUST also appear in Space policy `plaintext_visible_services`. If false, the service may only receive public content, encrypted envelopes, irreversible hashes, or policy-allowed stripped previews.

