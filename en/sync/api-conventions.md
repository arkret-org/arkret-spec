# API Conventions

Contrix APIs exchange UTF-8 JSON over HTTPS by default.

Common requirements:

- canonical JSON fields use snake_case
- production endpoints use HTTPS
- write endpoints support idempotency
- errors use a stable `error.code`
- pagination uses opaque cursors
- services expose feature discovery
- browser-facing services support CORS preflight
- authentication does not replace capability checks
- auth/OIDC service discovery does not replace DID principal binding

Authentication and authorization servers may be separate. Service discovery SHOULD expose auth metadata such as:

```json
{
  "auth_metadata": {
    "oauth_issuer": "https://auth.example.com",
    "openid_configuration": "https://auth.example.com/.well-known/openid-configuration",
    "token_endpoint_auth_methods": ["private_key_jwt", "client_secret_basic"],
    "supported_grant_types": ["authorization_code", "refresh_token"],
    "did_binding_methods": ["session_grant", "did_http_signature"],
    "required_audience": "https://server.example/api/v1"
  }
}
```

OAuth/OIDC `sub`, email, username, or client id MUST NOT be used directly as `actor_id`, grant subject, or event sender. A login session must be bound to a DID principal / device through a verifiable session grant, device binding, or DID proof, and resource servers must verify issuer, audience, expiry, replay protection, and grant status.

Standard error envelope:

```json
{
  "ok": false,
  "error": {
    "code": "capability_denied",
    "message": "actor does not have permission",
    "retry_after_ms": null,
    "details": {}
  },
  "request_id": "cx:req:..."
}
```

