# Client Sync

This file is the English companion for the detailed Chinese draft in `../../zh/sync/client-sync.md`.

It defines client-facing incremental sync streams over Contrix repo, Sync Service, and index services.

The name does not imply separate sync v1/v2 protocol generations in the current draft.

The canonical client sync endpoint is `POST /api/v1/sync` (`cx.clientSync`). It is distinct from `GET /api/v1/sync/subscribe` for Space operation stream subscription and `GET /api/v1/sync/backfill` for historical backfill.

