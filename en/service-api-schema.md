# Service API Schema

Core services:

- identity: resolve DID and fetch logs/receipts
- repo: submit/fetch commits and ops
- relay: subscribe, backfill, distribute snapshot pointers
- index: query materialized views
- blob: upload/download content-addressed blobs
- authz: check effective permissions

All write requests follow `api-conventions.md` idempotency and error rules.
