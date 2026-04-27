# Federation Wire Protocol

Federation uses DID-authenticated service-to-service transactions.

Required areas:

- HTTP Message Signatures
- idempotent transactions
- cross-domain join
- backfill authorization
- frontier exchange
- fork detection
- quarantine queue

Relay and repo services MUST verify event signatures, schema, capabilities, and source service authority.

