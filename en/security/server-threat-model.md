# Server Threat Model (Abuse and Anti-fraud)

This file is the English companion for the Chinese draft in `../../zh/security/server-threat-model.md`.

It documents common server-side abuse patterns (open federation ingress, brute-force auth, spam flood, spoofing, replay,
resource exhaustion, enumeration, URL credential leakage, media header probes) and maps them to Contrix hardening controls
(`policy-server.md`, `moderation.md`, `federation.md`, `api-conventions.md`).

Service discovery poisoning includes tampering with `sync_endpoints`, `service_did`, `plaintext_visible_services`, and organization / Space endorsements, because these values affect propagation paths and plaintext visibility boundaries.

Current hardening rules include:

- protected endpoints reject query-string authentication and redact sensitive URL fields from logs
- HTTP rate limits prefer `Retry-After`, with `retry_after_ms` kept for body diagnostics and non-HTTP bindings
- private blob `HEAD`, `Range`, redirects, `Content-Length`, `Content-Type`, and `Content-Disposition` share the same authorization context and must not leak invisible resources
- federation requests bind `origin`, `destination`, target URI, content digest, and canonical request hash in the service signature transcript

