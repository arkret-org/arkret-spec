# Glossary

This file is the English companion for the detailed Chinese draft in `../../zh/overview/glossary.md`.

It defines the common terminology used across Contrix, including identity, core objects, authorization, sync, federation, devices, encryption, media, notifications, and account lifecycle terms.

## Service Terms

| Term | Definition |
| --- | --- |
| Principal Server | A service boundary controlled by a principal or explicitly delegated through DID / Space policy. It may host repo, sync, index, blob, push, and policy capabilities. Product layers may call it a Home Server. |
| Sync Service | The Space incremental sync capability exposed by a Principal Server. It handles subscription, backfill, deduplication, ephemeral signaling, and controlled distribution. It is not an independent third-party server role or a truth source. |
| Plaintext-visible Service | A service explicitly delegated by Space policy, principal DID, or organization DID to receive or store non-E2EE private bodies, attachment previews, full-text indexes, notification summaries, embeddings, or reversible derived summaries. |


