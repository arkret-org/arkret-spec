# Sync Conformance Vectors

This file is the English placeholder for the detailed Chinese draft in `../zh/sync-conformance-vectors.md`.

It defines conformance vectors for Client Sync ordering, pagination gaps, snapshot frontiers, causal barriers, MLS epoch backfill, decryption recovery, and fail-closed behavior for removed members.

The Chinese draft is currently normative for detailed examples and expected outputs.

## 1. Added Federation Snapshot Bootstrap Coverage

Additional vectors include a federation pull-path bootstrap assist scenario:

- `cx.vector.sync.snapshot_bootstrap.v1`
- `cx.vector.sync.view_projection_profiles.v1`

Expected behavior in English:

- `GET /api/v1/federation/pull-operations` MAY include `snapshot_bootstrap` in response.
- Receivers MUST validate snapshot signature and frontier before using the snapshot-assisted checkpoint.
- If validation fails, implementation MUST fall back to operation-only replay (or equivalent recovery path) and may mark the peer degraded.
- Operations replay must start from the advertised `snapshot_frontier`, never as an unauthenticated new genesis.

Standard View projection profile vectors cover collection, timeline, graph, document, and composite responses. Kanban/list/table/calendar/gantt/queue/matrix presets validate through `CollectionProjectionResponse`; chat/thread/forum/activity/context timeline presets validate through `TimelineProjectionResponse`; tree validates through `GraphProjectionResponse`; dashboard validates through `CompositeProjectionResponse`. Implementations must validate the corresponding fixtures in `artifacts/fixtures/sync-fixture.json` against the OpenAPI response profiles.

