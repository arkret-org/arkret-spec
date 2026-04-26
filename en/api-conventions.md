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
