# Glossary

This file is the English companion for the detailed Chinese draft in `../../zh/overview/glossary.md`.

It defines the common terminology used across Contrix, including identity, core objects, authorization, sync, federation, devices, encryption, media, notifications, and account lifecycle terms.

## Service Terms

| Term | Definition |
| --- | --- |
| Identity Resolution Infrastructure | Umbrella term for DID method resolvers, registries, witnesses, watchers, OOBI discovery, or method-specific verifiers. It proves DID control history, key state, and service delegation; it does not decide whether a DID may log in to an organization or access organization data. `did:key` may need only a local resolver; `did:keri` usually needs KERI logs, witnesses, watchers, or OOBI. |
| Principal Server | A service boundary controlled by a principal or explicitly delegated through DID / Space policy. It may host repo, sync, index, blob, push, and policy capabilities. Its `service_type` should be `principal_server`. |
| Auth / Account Server | Service handling passkeys, OIDC, SSO, device pairing, session grants, account recovery, and soft logout. It proves service-account login and binds it to DID / device; it does not directly prove DID control and does not need to share an operator with the DID resolver. |
| Repo Server | Concrete server form of `Repo Service`, providing commit submission, Operation / commit reads, repo sync, and audit replay. |
| Sync Service | The Space incremental sync capability exposed by a Principal Server. It handles subscription, backfill, deduplication, ephemeral signaling, and controlled distribution. It is not an independent third-party server role or a truth source. |
| Plaintext-visible Service | A service explicitly delegated by Space policy, principal DID, or organization DID to receive or store non-E2EE private bodies, attachment previews, full-text indexes, notification summaries, embeddings, or reversible derived summaries. |
| Device / Key Server | Service for to-device messages, one-time keys, fallback keys, device lists, and key-backup metadata. Device trust still comes from signature chains. |
| Applet Server | Service hosting Applet / bridge / bot / portal / ghost actor logic. Writes still require capability, namespace, and signatures. |
| Agent Runtime Server | Service executing agent runs, tool calls, memory promotion, and external agent protocol handoff. Outputs become protocol facts only after being written back to Repo / Space. |
| Realtime Media Server | Service providing ICE config, TURN/STUN, SFU/MCU, recording, or call assistance. |
| Moderation / Compliance Server | Service providing reports, review queues, server ACLs, policy lists, appeals, legal hold, and erasure workflows. |


