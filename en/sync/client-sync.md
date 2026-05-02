# Client Sync

This file is the English companion for the detailed Chinese draft in `../../zh/sync/client-sync.md`.

It defines client-facing incremental sync streams over Contrix repo and Sync Service.

The name does not imply separate sync v1/v2 protocol generations in the current draft.

The canonical client sync endpoint is `POST /api/v1/sync` (`cx.sync.client_sync`). It is distinct from `GET /api/v1/sync/subscribe` for Space operation stream subscription and `GET /api/v1/sync/backfill` for historical backfill.

If a response has `timeline.limited=true`, clients MUST use backfill or pagination to repair the gap and MUST NOT assume the timeline is continuous. Expired sync tokens return `sync_token_expired`; clients should fall back to initial sync or snapshot-assisted initial sync while keeping unconfirmed offline writes.

Recovery flow:

1. Keep the last `next_batch`, filter hash, unconfirmed local writes, and last verified frontier.
2. On `sync_token_expired` or `stale_frontier`, call `sync/describe` or `sync/snapshot-head` to fetch the current frontier and recommended snapshot.
3. Verify snapshot signature, signer authority, state hash, frontier, and chunk digests before adopting it.
4. Backfill from the snapshot frontier or the server-provided backfill start, then resume `sync/subscribe` or `POST /sync`.
5. If snapshot validation fails, fall back to repo history replay or operation-only backfill and mark the source degraded if appropriate.

Request fields:

| Field | Location | Type | Required | Meaning and constraints |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` or `device proof` | required | Must bind the current principal / device. |
| `since` | body | `token` | optional | Previous `next_batch`; omitted for initial sync. |
| `timeout_ms` | body | `int` | optional | Long-poll wait limit. |
| `set_presence` | body | `enum(online,offline,unavailable)` | optional | Presence update for the current device. |
| `filter` | body | `object` | optional | Filter object. |
| `subscriptions` | body | `object` | optional | Sliding-sync style Space subscription config. |

Response fields:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `next_batch` | `token` | required | Opaque token for the next sync call. |
| `spaces` | `object` | optional | Native Contrix Space sync result. |
| `to_device` | `object` | optional | To-device messages for the current device. |
| `device_lists` | `object` | optional | Device-list changes. |
| `presence` | `object` | optional | Presence events. |
| `account_data` | `object` | optional | Actor-private account data. |
| `notifications` | `object` | optional | Notification deltas. |

Over-limit requests return `rate_limited`, `payload_too_large`, or `invalid_param` with `Retry-After`, `retry_after_ms`, or `limits` details as applicable.

