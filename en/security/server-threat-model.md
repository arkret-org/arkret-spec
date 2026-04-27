# Server Threat Model (Abuse and Anti-fraud)

This file is the English companion for the Chinese draft in `../../zh/security/server-threat-model.md`.

It documents common server-side abuse patterns (open federation ingress, brute-force auth, spam flood, spoofing, replay,
resource exhaustion, enumeration) and maps them to Contrix hardening controls
(`policy-server.md`, `moderation.md`, `federation.md`, `api-conventions.md`).

Service discovery poisoning includes tampering with `sync_endpoints`, `service_did`, `plaintext_visible_services`, and organization / Space endorsements, because these values affect propagation paths and plaintext visibility boundaries.

